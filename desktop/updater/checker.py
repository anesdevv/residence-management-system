"""Update checking against the GitHub releases API (pure I/O orchestration)."""

from __future__ import annotations

from dataclasses import dataclass
import http.client as _httpclient
import json
import logging
import os
from pathlib import Path
import time
from typing import Callable
from uuid import uuid4

from desktop.version import __version__

from . import config
from . import http as _http_module
from .release import ReleaseError, ReleaseInfo, parse_release

__all__ = [
    "CheckResult",
    "ETagCache",
    "check_for_update",
    "default_cache_path",
]

_log = logging.getLogger("resivo.updater")

CheckKind = str

_FRIENDLY_ERRORS = {
    "missing_assets": "The release is missing its installer or checksum file.",
    "bad_asset_name": "The release contains an unexpected file name.",
    "bad_host": "The download host is not trusted.",
    "size_limit": "The release is larger than the allowed limit.",
    "malformed": "The update information is malformed.",
}


@dataclass(frozen=True)
class CheckResult:
    kind: CheckKind
    release: ReleaseInfo | None = None
    message: str = ""
    checked_at: float = 0.0
    retry_at: float | None = None
    etag: str | None = None
    code: str = ""


class ETagCache:
    """Small JSON cache holding the last ETag and release payload."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def load(self) -> dict:
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, ValueError, UnicodeDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        etag = data.get("etag")
        payload = data.get("payload")
        if not isinstance(etag, str) or not isinstance(payload, dict):
            return {}
        return {"etag": etag, "payload": payload}

    def save(self, etag: str, payload: dict) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        tmp = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump({"etag": str(etag or ""), "payload": payload}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def default_cache_path() -> Path:
    return config.updates_dir() / "check_cache.json"


def _now() -> float:
    return time.time()


def _log_offline() -> CheckResult:
    _log.warning("update check: offline")
    return CheckResult("offline", message="Could not reach the update server.", checked_at=_now())


def _log_rate_limited(retry_at: float | None) -> CheckResult:
    _log.warning("update check: rate limited")
    return CheckResult(
        "rate_limited",
        message="GitHub rate limit reached. Please try again later.",
        checked_at=_now(),
        retry_at=retry_at,
    )


def _error(code: str, checked_at: float, etag: str | None = None) -> CheckResult:
    _log.warning("update failed: %s", code)
    return CheckResult(
        "error",
        message=_FRIENDLY_ERRORS.get(code, "The update check failed."),
        checked_at=checked_at,
        etag=etag,
        code=code,
    )


def _parse_retry_after(value: str, now: float) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value.strip())
    except (TypeError, ValueError):
        return None
    return now + max(0.0, seconds)


def _parse_reset(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return None


def _retry_at(response, now: float) -> float | None:
    retry_after = response.header("Retry-After")
    relative = _parse_retry_after(retry_after, now)
    reset = _parse_reset(response.header("X-RateLimit-Reset"))
    if response.status == 429 and relative is not None:
        return relative
    if reset is not None:
        return reset
    if relative is not None:
        return relative
    return None


def _release_result(payload: dict, current_version) -> CheckResult:
    checked_at = _now()
    try:
        release = parse_release(payload, current_version)
    except ReleaseError as exc:
        return _error(exc.code, checked_at)
    if release is None:
        _log.info("update check: up to date")
        return CheckResult("up_to_date", message="You are up to date.", checked_at=checked_at)
    _log.info("update available v%s", release.version_str)
    return CheckResult("available", release=release, checked_at=checked_at)


def _decode_payload(body: bytes) -> dict | None:
    try:
        decoded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


def check_for_update(
    current_version: str | tuple[int, int, int] = __version__,
    cache_path: str | os.PathLike[str] | None = None,
    http: Callable | None = None,
) -> CheckResult:
    """Check the latest GitHub release and report a :class:`CheckResult`.

    Never raises for network, payload or server problems; the caller gets an
    ``offline``, ``rate_limited`` or ``error`` result instead.
    """
    getter = http if http is not None else _http_module.http_get
    cache = ETagCache(cache_path if cache_path is not None else default_cache_path())
    cached = cache.load()

    headers = {
        "Accept": config.ACCEPT_HEADER,
        "User-Agent": config.USER_AGENT,
        "X-GitHub-Api-Version": config.API_VERSION_HEADER,
    }
    cached_etag = cached.get("etag") or ""
    if cached_etag:
        headers["If-None-Match"] = cached_etag

    try:
        response = getter(config.GITHUB_API_URL, headers=headers, timeout=config.API_TIMEOUT_S)
    except ReleaseError as exc:
        return _error(exc.code, _now())
    except (OSError, _httpclient.HTTPException):
        return _log_offline()
    except Exception:  # pragma: no cover - defensive, never leak a traceback
        return _error("unexpected", _now())

    status = int(getattr(response, "status", 0) or 0)

    if status == 304:
        payload = cached.get("payload")
        if not isinstance(payload, dict):
            return _error("no_cached_payload", _now(), cached_etag or None)
        result = _release_result(payload, current_version)
        response_etag = response.header("ETag") or cached_etag or None
        return CheckResult(
            result.kind,
            release=result.release,
            message=result.message,
            checked_at=result.checked_at,
            etag=response_etag,
            code=result.code,
        )

    if status == 200:
        checked_at = _now()
        payload = _decode_payload(getattr(response, "body", b"") or b"")
        if payload is None:
            return _error("invalid_response", checked_at)
        new_etag = response.header("ETag") or ""
        cache.save(new_etag, payload)
        result = _release_result(payload, current_version)
        return CheckResult(
            result.kind,
            release=result.release,
            message=result.message,
            checked_at=result.checked_at,
            etag=new_etag or None,
            code=result.code,
        )

    if status == 404:
        _log.info("update check: no releases")
        return CheckResult(
            "no_releases",
            message="No releases have been published yet.",
            checked_at=_now(),
        )

    if status in (403, 429):
        return _log_rate_limited(_retry_at(response, _now()))

    return _error(f"http_{status}", _now())
