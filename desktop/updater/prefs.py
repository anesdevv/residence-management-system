"""Persisted updater preferences backed by ``QSettings``."""

from __future__ import annotations

import time

from PySide6.QtCore import QSettings

from . import config

__all__ = [
    "get_auto_check",
    "get_install_error",
    "get_last_check",
    "get_notified_version",
    "get_skipped_version",
    "reset_for_tests",
    "set_auto_check",
    "set_install_error",
    "set_last_check",
    "set_notified_version",
    "set_skipped_version",
    "should_auto_check",
]

_ORGANIZATION = "RESIVO"
_APPLICATION = "StaffConsole"
_DAY_SECONDS = 24 * 60 * 60


def _settings() -> QSettings:
    return QSettings(_ORGANIZATION, _APPLICATION)


def _key(name: str) -> str:
    return config.preference_key(name)


def _as_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def get_auto_check(default: bool = True) -> bool:
    return _as_bool(_settings().value(_key("auto_check"), default), default)


def set_auto_check(enabled: bool) -> None:
    _settings().setValue(_key("auto_check"), bool(enabled))


def get_skipped_version() -> str:
    value = _settings().value(_key("skipped_version"), "")
    return "" if value is None else str(value)


def set_skipped_version(version: str | None) -> None:
    settings = _settings()
    text = (version or "").strip()
    if text:
        settings.setValue(_key("skipped_version"), text)
    else:
        settings.remove(_key("skipped_version"))


def get_last_check() -> float:
    value = _settings().value(_key("last_check"), 0.0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def set_last_check(epoch: float) -> None:
    try:
        _settings().setValue(_key("last_check"), float(epoch))
    except (TypeError, ValueError):
        _settings().setValue(_key("last_check"), 0.0)


def get_notified_version() -> str:
    value = _settings().value(_key("notified_version"), "")
    return "" if value is None else str(value)


def set_notified_version(version: str | None) -> None:
    settings = _settings()
    text = (version or "").strip()
    if text:
        settings.setValue(_key("notified_version"), text)
    else:
        settings.remove(_key("notified_version"))


def should_auto_check(now: float | None = None) -> bool:
    if not get_auto_check():
        return False
    current = time.time() if now is None else float(now)
    last = get_last_check()
    if last <= 0:
        return True
    return (current - last) >= _DAY_SECONDS


def get_install_error() -> str:
    """Message saved when the installer could not be started (survives restart)."""
    value = _settings().value(_key("install_error"), "")
    return "" if value is None else str(value)


def set_install_error(message: str | None) -> None:
    settings = _settings()
    text = (message or "").strip()
    if text:
        settings.setValue(_key("install_error"), text)
    else:
        settings.remove(_key("install_error"))


def reset_for_tests() -> None:
    """Remove every ``updates/*`` preference (test helper)."""
    settings = _settings()
    prefix = config.preference_key("")
    try:
        keys = list(settings.allKeys())
    except Exception:  # pragma: no cover - defensive
        keys = []
    for key in keys:
        if str(key).startswith(prefix):
            settings.remove(key)
    settings.sync()
