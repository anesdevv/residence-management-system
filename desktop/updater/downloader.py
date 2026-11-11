"""Download, verify and clean installers.

Progress callbacks run on the worker thread performing the download; UI code
must marshal them onto the GUI thread (for example with a Qt signal).
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Callable, Iterator
from uuid import uuid4

from . import config
from . import http as _http_module
from .http import validate_download_url
from .release import ReleaseError, ReleaseInfo
from .verify import constant_time_equal, has_pe_header, parse_checksums, sha256_file

__all__ = [
    "DownloadCancelled",
    "UpdateError",
    "clean_updates_dir",
    "download_installer",
    "fetch_checksums",
]

ProgressCallback = Callable[[int, int], None]
CancelCheck = Callable[[], bool]


class DownloadCancelled(Exception):
    """The user cancelled an in-progress download."""


class UpdateError(Exception):
    """A download/verification step failed; ``code`` is machine readable."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = str(code)
        super().__init__(message or self.code)


def _is_cancelled(cancel: CancelCheck | None) -> bool:
    if cancel is None:
        return False
    try:
        if hasattr(cancel, "is_set"):
            return bool(cancel.is_set())
        return bool(cancel())
    except Exception:  # pragma: no cover - a broken cancel hook must not crash
        return False


def _unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _content_length(response) -> int | None:
    raw = response.header("Content-Length")
    if not raw:
        return None
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _download_headers() -> dict[str, str]:
    return {
        "User-Agent": config.USER_AGENT,
        "Accept": "application/octet-stream",
    }


def _checksum_headers() -> dict[str, str]:
    return {
        "User-Agent": config.USER_AGENT,
        "Accept": "text/plain",
    }


def fetch_checksums(
    url: str,
    *,
    http: Callable | None = None,
    timeout: float = config.API_TIMEOUT_S,
    cancel: CancelCheck | None = None,
) -> dict[str, str]:
    """Fetch and parse a ``SHA256SUMS.txt`` asset."""
    try:
        validate_download_url(url)
    except ReleaseError as exc:
        raise UpdateError(exc.code) from exc
    if _is_cancelled(cancel):
        raise DownloadCancelled()

    getter = http if http is not None else _http_module.http_get
    try:
        response = getter(url, headers=_checksum_headers(), timeout=timeout)
    except ReleaseError as exc:
        raise UpdateError(exc.code) from exc
    except OSError as exc:
        raise UpdateError("offline") from exc

    if int(getattr(response, "status", 0) or 0) != 200:
        raise UpdateError("checksum_failed")

    if _is_cancelled(cancel):
        raise DownloadCancelled()

    body = getattr(response, "body", b"") or b""
    if not isinstance(body, (bytes, bytearray)):
        raise UpdateError("checksum_failed")
    declared = _content_length(response)
    if declared is not None and declared > config.MAX_CHECKSUM_BYTES:
        raise UpdateError("oversize")
    if len(body) > config.MAX_CHECKSUM_BYTES:
        raise UpdateError("oversize")

    try:
        text = bytes(body).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UpdateError("checksum_failed") from exc
    return parse_checksums(text)


def _validate_installer_name(name: str) -> None:
    if not isinstance(name, str) or Path(name).name != name:
        raise UpdateError("bad_asset_name")
    if config.ASSET_NAME_PATTERN.fullmatch(name) is None:
        raise UpdateError("bad_asset_name")


def _buffered_chunks(body) -> Iterator[bytes]:
    for offset in range(0, len(body), config.CHUNK_SIZE):
        yield bytes(body[offset : offset + config.CHUNK_SIZE])


def _write_chunks(handle, chunks, total, progress, cancel) -> int:
    downloaded = 0
    if progress is not None:
        progress(0, total)
    for chunk in chunks:
        if _is_cancelled(cancel):
            raise DownloadCancelled()
        if not chunk:
            continue
        downloaded += len(chunk)
        if downloaded > total or downloaded > config.MAX_DOWNLOAD_BYTES:
            raise UpdateError("oversize")
        handle.write(chunk)
        if progress is not None:
            progress(downloaded, total)
    return downloaded


def download_installer(
    release: ReleaseInfo,
    *,
    dest_dir: str | os.PathLike[str] | None = None,
    progress: ProgressCallback | None = None,
    cancel: CancelCheck | None = None,
    http: Callable | None = None,
) -> Path:
    """Download, verify and atomically place ``release.installer_name``.

    Returns the final installer path.  Verification failures remove the
    partial file and raise :class:`UpdateError` with an explicit code.
    """
    destination = Path(dest_dir) if dest_dir is not None else config.updates_dir()
    destination.mkdir(parents=True, exist_ok=True)

    _validate_installer_name(release.installer_name)

    try:
        validate_download_url(release.installer_url)
    except ReleaseError as exc:
        raise UpdateError(exc.code) from exc

    total = int(release.installer_size)
    if total <= 0:
        raise UpdateError("size_mismatch")
    if total > config.MAX_DOWNLOAD_BYTES:
        raise UpdateError("oversize")

    checksums = fetch_checksums(
        release.checksum_url,
        http=http,
        timeout=config.DOWNLOAD_TIMEOUT_S,
        cancel=cancel,
    )
    expected = checksums.get(release.installer_name.lower(), "")
    if not expected:
        raise UpdateError("missing_checksum")

    if _is_cancelled(cancel):
        raise DownloadCancelled()

    getter = http if http is not None else _http_module.http_get
    temp_path = destination / f".{uuid4().hex}.part"
    downloaded = 0
    created = False
    try:
        descriptor = os.open(
            temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        created = True
        with os.fdopen(descriptor, "wb") as handle:
            if http is not None:
                # Test / injected transport: the fake already returns a body.
                response = getter(
                    release.installer_url,
                    headers=_download_headers(),
                    timeout=config.DOWNLOAD_TIMEOUT_S,
                )
                if int(getattr(response, "status", 0) or 0) != 200:
                    raise UpdateError("download_failed")
                declared = _content_length(response)
                if declared is not None and declared != total:
                    raise UpdateError("size_mismatch")
                body = getattr(response, "body", b"") or b""
                if not isinstance(body, (bytes, bytearray)):
                    raise UpdateError("download_failed")
                downloaded = _write_chunks(
                    handle,
                    _buffered_chunks(bytes(body)),
                    total,
                    progress,
                    cancel,
                )
            else:
                # Production: stream to disk, never buffering the installer.
                with _http_module.open_stream(
                    release.installer_url,
                    headers=_download_headers(),
                    timeout=config.DOWNLOAD_TIMEOUT_S,
                ) as response:
                    if response.status != 200:
                        raise UpdateError("download_failed")
                    declared = _content_length(response)
                    if declared is not None and declared != total:
                        raise UpdateError("size_mismatch")
                    downloaded = _write_chunks(
                        handle,
                        response.chunks(config.CHUNK_SIZE),
                        total,
                        progress,
                        cancel,
                    )
            handle.flush()
            os.fsync(handle.fileno())

        if downloaded != total or temp_path.stat().st_size != total:
            raise UpdateError("size_mismatch")

        actual = sha256_file(temp_path)
        if not constant_time_equal(actual, expected):
            raise UpdateError("checksum_mismatch")
        if not has_pe_header(temp_path):
            raise UpdateError("bad_pe")

        target = destination / release.installer_name
        os.replace(temp_path, target)
        created = False
        return target
    except DownloadCancelled:
        if created:
            _unlink(temp_path)
        raise
    except UpdateError:
        if created:
            _unlink(temp_path)
        raise
    except ReleaseError as exc:
        if created:
            _unlink(temp_path)
        raise UpdateError(exc.code) from exc
    except OSError as exc:
        if created:
            _unlink(temp_path)
        raise UpdateError("download_failed") from exc
    except BaseException:
        # Includes progress-callback failures and KeyboardInterrupt: never
        # leave a partial installer behind.
        if created:
            _unlink(temp_path)
        raise


def clean_updates_dir(
    dest_dir: str | os.PathLike[str] | None = None,
    keep: str | os.PathLike[str] | None = None,
) -> int:
    """Delete partial downloads and stale ``Setup-RESIVO-*.exe`` installers.

    ``keep`` (typically the just-downloaded installer) is preserved; the ETag
    cache is never touched.  Returns the number of files removed.
    """
    destination = Path(dest_dir) if dest_dir is not None else config.updates_dir()
    if not destination.is_dir():
        return 0
    keep_resolved: Path | None = None
    if keep is not None:
        try:
            keep_resolved = Path(keep).resolve()
        except OSError:  # pragma: no cover - defensive
            keep_resolved = None

    removed = 0
    try:
        entries = list(destination.iterdir())
    except OSError:
        return 0
    for entry in entries:
        try:
            if not entry.is_file():
                continue
        except OSError:
            continue
        name = entry.name
        if name == "check_cache.json":
            continue
        if name.endswith(".part"):
            _unlink(entry)
            removed += 1
            continue
        if fnmatch.fnmatch(name.lower(), "setup-resivo-*.exe"):
            if keep_resolved is not None:
                try:
                    if entry.resolve() == keep_resolved:
                        continue
                except OSError:  # pragma: no cover - defensive
                    pass
            _unlink(entry)
            removed += 1
    return removed
