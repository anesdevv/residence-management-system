"""Defensive Win32 runtime queries wrapped with safe fallbacks."""

from __future__ import annotations

import logging
import platform
import struct
import sys
from typing import Any

_log = logging.getLogger("resivo.platform")


def is_64bit_process() -> bool:
    """Return True when the current Python/EXE process is 64-bit."""
    return struct.calcsize("P") * 8 == 64


def is_64bit_os() -> bool:
    """Return True when running on a 64-bit operating system."""
    try:
        machine = platform.machine().lower()
        return machine in ("amd64", "x86_64", "arm64") or sys.maxsize > 2**32
    except Exception:
        return is_64bit_process()


def set_app_user_model_id(app_id: str) -> bool:
    """Safely configure the Windows taskbar AppUserModelID."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        shell32 = ctypes.windll.shell32
        fn = shell32.SetCurrentProcessExplicitAppUserModelID
        fn.argtypes = [wintypes.LPCWSTR]
        fn.restype = ctypes.c_long
        hr = fn(app_id)
        return hr == 0
    except Exception as exc:  # pragma: no cover - older/non-desktop Windows builds
        _log.warning("Could not set process AppUserModelID: %s", exc)
        return False


def get_windows_version_info() -> dict[str, Any]:
    """Return OS version, build number, and Windows 10/11 compatibility details."""
    info: dict[str, Any] = {
        "platform": sys.platform,
        "release": platform.release(),
        "version": platform.version(),
        "major": None,
        "minor": None,
        "build": None,
        "is_64bit_os": is_64bit_os(),
        "is_64bit_process": is_64bit_process(),
    }
    if sys.platform != "win32":
        return info
    try:
        winver = sys.getwindowsversion()
        info["major"] = int(winver.major)
        info["minor"] = int(winver.minor)
        info["build"] = int(winver.build)
    except Exception as exc:  # pragma: no cover
        _log.debug("getwindowsversion failed: %s", exc)
    return info


def create_named_mutex(name: str):
    """Create (or open) a process-wide named mutex and return its handle.

    Inno Setup's ``AppMutex`` directive waits for this exact name, so the
    installer can close a running RÉSIVO before replacing its files.  The
    handle is intentionally kept for the whole process lifetime; Windows
    releases it on exit.
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        create = kernel32.CreateMutexW
        create.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        create.restype = wintypes.HANDLE
        handle = create(None, False, str(name))
        if handle:
            return handle
        _log.warning("Could not create the named application mutex")
    except Exception as exc:  # pragma: no cover - exotic Windows runtimes
        _log.warning("Could not create the named application mutex: %s", exc)
    return None


def release_named_mutex(handle: Any) -> None:
    """Close a mutex handle returned by :func:`create_named_mutex`."""
    if not handle or sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.CloseHandle(handle)
    except Exception as exc:  # pragma: no cover
        _log.debug("CloseHandle failed: %s", exc)


def get_dpi_info(app: Any = None) -> dict[str, Any]:
    """Read process DPI awareness and primary screen scale factor safely."""
    result: dict[str, Any] = {
        "system_dpi": None,
        "scale_percent": None,
        "device_pixel_ratio": None,
        "awareness": "unknown",
    }
    if sys.platform == "win32":
        try:
            import ctypes

            user32 = ctypes.windll.user32
            get_dpi = getattr(user32, "GetDpiForSystem", None)
            if callable(get_dpi):
                get_dpi.argtypes = []
                get_dpi.restype = ctypes.c_uint
                dpi = int(get_dpi())
                if dpi > 0:
                    result["system_dpi"] = dpi
                    result["scale_percent"] = round((dpi / 96.0) * 100)
        except Exception as exc:  # pragma: no cover - Windows 10 <1607 fallback
            _log.debug("GetDpiForSystem unavailable: %s", exc)

        try:
            import ctypes

            user32 = ctypes.windll.user32
            get_ctx = getattr(user32, "GetThreadDpiAwarenessContext", None)
            get_aw = getattr(user32, "GetAwarenessFromDpiAwarenessContext", None)
            if callable(get_ctx) and callable(get_aw):
                get_ctx.argtypes = []
                get_ctx.restype = ctypes.c_void_p
                get_aw.argtypes = [ctypes.c_void_p]
                get_aw.restype = ctypes.c_int
                code = int(get_aw(get_ctx()))
                result["awareness"] = {
                    0: "unaware",
                    1: "system",
                    2: "per_monitor",
                }.get(code, f"code:{code}")
        except Exception as exc:  # pragma: no cover
            _log.debug("DpiAwareness query unavailable: %s", exc)

    if app is not None:
        try:
            screen = app.primaryScreen()
            if screen is not None:
                dpr = float(screen.devicePixelRatio())
                logical_dpi = float(screen.logicalDotsPerInch())
                result["device_pixel_ratio"] = dpr
                if result["system_dpi"] is None and logical_dpi > 0:
                    result["system_dpi"] = round(logical_dpi)
                if result["scale_percent"] is None:
                    result["scale_percent"] = round(dpr * 100)
        except Exception:  # pragma: no cover
            pass
    return result
