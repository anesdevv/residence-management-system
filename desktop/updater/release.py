"""GitHub release payload parsing (pure apart from URL validation)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from desktop.version import __version__

from . import config
from .versioning import format_version, is_newer, parse_tag, parse_version

__all__ = ["ReleaseError", "ReleaseInfo", "parse_published_at", "parse_release"]


class ReleaseError(Exception):
    """A release payload could not be used.

    ``code`` is a short machine-readable identifier (``missing_assets``,
    ``bad_asset_name``, ``size_limit``, ``bad_host``, ``malformed``).
    """

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = str(code)
        super().__init__(message or self.code)


@dataclass(frozen=True)
class ReleaseInfo:
    version: tuple[int, int, int]
    version_str: str
    tag: str
    name: str
    notes: str
    published_at: str | None
    published_dt: datetime | None
    installer_name: str
    installer_url: str
    installer_size: int
    checksum_url: str
    checksum_size: int
    html_url: str


def parse_published_at(text: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp (``Z`` or numeric offset) as aware UTC."""
    if not isinstance(text, str):
        return None
    value = text.strip()
    if not value:
        return None
    if value.endswith(("Z", "z")):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _flag(payload: dict, key: str) -> bool:
    value = payload.get(key, False)
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ReleaseError("malformed", f"{key} must be a boolean")
    return value


def _required_int(asset: dict, key: str) -> int:
    value = asset.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReleaseError("malformed", f"asset {key} must be an integer")
    return value


def _required_str(asset: dict, key: str) -> str:
    value = asset.get(key)
    if not isinstance(value, str):
        raise ReleaseError("malformed", f"asset {key} must be a string")
    return value


def _looks_like_installer(name: str) -> bool:
    lowered = name.lower()
    if lowered.startswith("setup-resivo"):
        return True
    return lowered.endswith(".exe") and "resivo" in lowered


def _validate_download(url: str) -> None:
    # Imported lazily: http imports ReleaseError from this module.
    from .http import validate_download_url

    validate_download_url(url)


def parse_release(payload, current_version=__version__):
    """Return a :class:`ReleaseInfo` when ``payload`` offers a newer build.

    ``None`` is returned for drafts, prereleases, invalid tags and versions
    that are not strictly newer than ``current_version``.  Structural problems
    raise :class:`ReleaseError` with an explicit ``code``.
    """
    if not isinstance(payload, dict):
        raise ReleaseError("malformed", "release payload must be an object")
    if _flag(payload, "draft") or _flag(payload, "prerelease"):
        return None

    tag = payload.get("tag_name")
    if tag is None:
        return None
    if not isinstance(tag, str):
        raise ReleaseError("malformed", "tag_name must be a string")
    version = parse_tag(tag)
    if version is None:
        return None
    if not is_newer(version, current_version):
        return None

    version_str = format_version(version)

    raw_assets = payload.get("assets", [])
    if raw_assets is None:
        raw_assets = []
    if not isinstance(raw_assets, list):
        raise ReleaseError("malformed", "assets must be a list")

    installer_asset: dict | None = None
    checksum_asset: dict | None = None
    for entry in raw_assets:
        if not isinstance(entry, dict):
            raise ReleaseError("malformed", "asset entry must be an object")
        name = entry.get("name")
        if not isinstance(name, str):
            raise ReleaseError("malformed", "asset name must be a string")
        if name == config.CHECKSUM_ASSET_NAME:
            checksum_asset = entry
            continue
        match = config.ASSET_NAME_PATTERN.fullmatch(name)
        if match is not None:
            captured = parse_version(match.group(1))
            if captured != version:
                raise ReleaseError(
                    "bad_asset_name",
                    "installer asset version does not match the release tag",
                )
            installer_asset = entry
        elif _looks_like_installer(name):
            raise ReleaseError("bad_asset_name", "unexpected installer asset name")

    if installer_asset is None or checksum_asset is None:
        raise ReleaseError("missing_assets", "release is missing required assets")

    installer_state = installer_asset.get("state", "uploaded")
    if installer_state != "uploaded":
        raise ReleaseError("missing_assets", "installer asset is not uploaded")
    installer_size = _required_int(installer_asset, "size")
    if installer_size <= 0:
        raise ReleaseError("missing_assets", "installer asset is empty")
    if installer_size > config.MAX_DOWNLOAD_BYTES:
        raise ReleaseError("size_limit", "installer asset exceeds the size limit")
    installer_url = _required_str(installer_asset, "browser_download_url")
    _validate_download(installer_url)

    checksum_state = checksum_asset.get("state", "uploaded")
    if checksum_state != "uploaded":
        raise ReleaseError("missing_assets", "checksum asset is not uploaded")
    checksum_size = _required_int(checksum_asset, "size")
    if checksum_size <= 0:
        raise ReleaseError("missing_assets", "checksum asset is empty")
    if checksum_size > config.MAX_CHECKSUM_BYTES:
        raise ReleaseError("size_limit", "checksum asset exceeds the size limit")
    checksum_url = _required_str(checksum_asset, "browser_download_url")
    _validate_download(checksum_url)

    published_at = payload.get("published_at")
    if published_at is not None and not isinstance(published_at, str):
        raise ReleaseError("malformed", "published_at must be a string")

    notes = payload.get("body") or ""
    if not isinstance(notes, str):
        raise ReleaseError("malformed", "body must be a string")
    name = payload.get("name") or tag
    if not isinstance(name, str):
        raise ReleaseError("malformed", "name must be a string")
    html_url = payload.get("html_url") or ""
    if not isinstance(html_url, str):
        raise ReleaseError("malformed", "html_url must be a string")

    return ReleaseInfo(
        version=version,
        version_str=version_str,
        tag=tag,
        name=name,
        notes=notes,
        published_at=published_at,
        published_dt=parse_published_at(published_at),
        installer_name=_required_str(installer_asset, "name"),
        installer_url=installer_url,
        installer_size=installer_size,
        checksum_url=checksum_url,
        checksum_size=checksum_size,
        html_url=html_url,
    )
