"""RÉSIVO — Windows autostart (Run key & StartupApproved management).

Isolated per-user registry access for launching RÉSIVO when Windows starts.
Uses Python's built-in winreg module under HKEY_CURRENT_USER.
Never requires administrator privileges and never modifies HKEY_LOCAL_MACHINE.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from typing import Any

from PySide6.QtCore import QLockFile, QSettings

_log = logging.getLogger("resivo.autostart")

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_APPROVED_KEY_PATH = (
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
)
VALUE_NAME = "RESIVO"

# For testing override
_force_supported: bool | None = None
_force_winreg: Any = None


def _get_winreg():
    if _force_winreg is not None:
        return _force_winreg
    if sys.platform == "win32":
        import winreg
        return winreg
    return None


def is_supported() -> bool:
    """True only on Windows and when running as the frozen EXE."""
    if _force_supported is not None:
        return _force_supported
    if sys.platform != "win32":
        return False
    return bool(getattr(sys, "frozen", False))


def get_state() -> str:
    """Return the current autostart state.

    Possible returns:
      - 'unsupported': not running on Windows or running from source code.
      - 'disabled': Run key value does not exist.
      - 'disabled_by_windows': Run value exists, but Windows Startup settings disabled it.
      - 'enabled': Run value exists and is active.
    """
    if not is_supported():
        return "unsupported"

    reg = _get_winreg()
    if reg is None:
        return "unsupported"

    # 1. Check if the value exists in the Run key
    try:
        with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, reg.KEY_READ) as key:
            _val, _ = reg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return "disabled"
    except OSError as exc:
        _log.warning("Failed to read autostart Run key: %s", exc)
        return "disabled"

    # 2. Check if Windows disabled it in StartupApproved
    try:
        with reg.OpenKey(
            reg.HKEY_CURRENT_USER, STARTUP_APPROVED_KEY_PATH, 0, reg.KEY_READ
        ) as key:
            raw_bytes, _ = reg.QueryValueEx(key, VALUE_NAME)
            if isinstance(raw_bytes, (bytes, bytearray)) and len(raw_bytes) > 0:
                first_byte = raw_bytes[0]
                # In Windows StartupApproved:
                # 0x02 or 0x06 = Enabled
                # 0x03 or 0x07 = Disabled by user in Task Manager / Windows Settings
                if first_byte in (0x03, 0x07):
                    return "disabled_by_windows"
    except FileNotFoundError:
        # Not present in StartupApproved means default enabled
        pass
    except OSError as exc:
        _log.warning("Failed to read StartupApproved key: %s", exc)

    return "enabled"


def format_command(exe_path: str | Path | None = None) -> str:
    """Format quoted executable path followed by --autostart flag."""
    if exe_path is None:
        exe_path = sys.executable
    resolved = str(Path(exe_path).resolve())
    return f'"{resolved}" --autostart'


def _clear_startup_approved_disabled() -> None:
    """Delete the StartupApproved entry so Windows does not suppress startup."""
    reg = _get_winreg()
    if reg is None:
        return
    try:
        with reg.OpenKey(
            reg.HKEY_CURRENT_USER, STARTUP_APPROVED_KEY_PATH, 0, reg.KEY_SET_VALUE
        ) as key:
            reg.DeleteValue(key, VALUE_NAME)
            _log.info("Cleared StartupApproved disabled flag for %s", VALUE_NAME)
    except FileNotFoundError:
        pass
    except OSError as exc:
        _log.warning("Could not clear StartupApproved value: %s", exc)


def enable(exe_path: str | Path | None = None) -> tuple[bool, str | None]:
    """Write the Run value with the quoted current EXE path and --autostart.

    Returns (True, None) on success, or (False, error_message) on failure.
    """
    if not is_supported():
        return False, "Available in the installed app (EXE) only."

    reg = _get_winreg()
    if reg is None:
        return False, "Windows registry is not available on this platform."

    cmd = format_command(exe_path)
    try:
        with reg.CreateKey(reg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
            reg.SetValueEx(key, VALUE_NAME, 0, reg.REG_SZ, cmd)
        _log.info("Enabled autostart with command: %s", cmd)

        # Clear any disabled flag previously set by Windows Task Manager
        _clear_startup_approved_disabled()
        return True, None
    except (OSError, PermissionError) as exc:
        _log.error("Failed to enable Windows autostart: %s", exc)
        return False, f"Could not enable Windows autostart: {exc}"


def disable() -> tuple[bool, str | None]:
    """Delete the Run value.

    No error if it does not exist. Returns (True, None) on success or
    (False, error_message) on failure.
    """
    if sys.platform != "win32" and _force_winreg is None:
        return True, None

    reg = _get_winreg()
    if reg is None:
        return True, None

    try:
        with reg.OpenKey(
            reg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, reg.KEY_SET_VALUE
        ) as key:
            try:
                reg.DeleteValue(key, VALUE_NAME)
                _log.info("Deleted autostart Run value for %s", VALUE_NAME)
            except FileNotFoundError:
                pass
        _clear_startup_approved_disabled()
        return True, None
    except FileNotFoundError:
        return True, None
    except (OSError, PermissionError) as exc:
        _log.error("Failed to disable Windows autostart: %s", exc)
        return False, f"Could not disable Windows autostart: {exc}"


def repair(exe_path: str | Path | None = None) -> bool:
    """Repair stale registry command if the EXE was moved or reinstalled.

    If the Run value exists and its command differs from the current EXE path,
    rewrites it. If the value does not exist, does nothing (never re-enables).
    """
    if not is_supported():
        return False

    reg = _get_winreg()
    if reg is None:
        return False

    cmd = format_command(exe_path)
    try:
        with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, reg.KEY_READ) as key:
            val, _ = reg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        # Run value does not exist: never re-enable silently
        return False
    except OSError as exc:
        _log.warning("Could not read Run key during repair check: %s", exc)
        return False

    if str(val).strip() != cmd:
        _log.info("Repairing moved autostart path: was %r, now %r", val, cmd)
        try:
            with reg.OpenKey(
                reg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, reg.KEY_SET_VALUE
            ) as key:
                reg.SetValueEx(key, VALUE_NAME, 0, reg.REG_SZ, cmd)
            return True
        except OSError as exc:
            _log.error("Failed to rewrite autostart path: %s", exc)
            return False

    return False


def get_start_minimized_setting() -> bool:
    """Get 'Start minimized to the taskbar' preference from QSettings."""
    settings = QSettings("RESIVO", "StaffConsole")
    val = settings.value("general/start_minimized", False)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return bool(val)


def set_start_minimized_setting(enabled: bool) -> None:
    """Set 'Start minimized to the taskbar' preference in QSettings."""
    settings = QSettings("RESIVO", "StaffConsole")
    settings.setValue("general/start_minimized", bool(enabled))


def bring_pid_to_front(target_pid: int) -> bool:
    """Bring the top-level window belonging to target_pid to the foreground on Windows."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        found_hwnd = None

        def enum_windows_callback(hwnd, _lparam):
            nonlocal found_hwnd
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == target_pid:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    found_hwnd = hwnd
                    return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        cb = WNDENUMPROC(enum_windows_callback)
        user32.EnumWindows(cb, 0)

        if found_hwnd:
            # 9 = SW_RESTORE
            user32.ShowWindow(found_hwnd, 9)
            user32.SetForegroundWindow(found_hwnd)
            return True
    except Exception as exc:  # pragma: no cover
        _log.warning("Could not bring existing window to front: %s", exc)
    return False


def acquire_single_instance(
    lock_path: Path, is_autostart: bool
) -> tuple[QLockFile | None, int | None]:
    """Single-instance guard using QLockFile in a per-user location.

    Returns (lock_file, None) if lock is successfully acquired.
    If another instance is running:
      - If launched with --autostart: exits silently (returns None, 0).
      - If launched normally: brings the existing window to front and exits (returns None, 0).
    """
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _log.warning("Could not create lockfile parent directory: %s", exc)

    lock = QLockFile(str(lock_path))
    lock.setStaleLockTime(30000)

    if not lock.tryLock(100):
        # Already running!
        if is_autostart:
            _log.info(
                "RÉSIVO is already running; autostart instance exiting silently."
            )
            return None, 0

        _log.info("RÉSIVO is already running; restoring existing window.")
        lock_info = lock.getLockInfo()
        if lock_info:
            pid = lock_info[0]
            if pid:
                bring_pid_to_front(pid)
        return None, 0

    return lock, None
