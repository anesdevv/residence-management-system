"""Tests for Windows autostart, registry management, single-instance guard, and Settings UI."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import urllib.request
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from desktop.platform import autostart
from desktop.app.ui.pages.settings import SettingsPage


class MockWinreg:
    """In-memory mock for winreg module to isolate unit tests from system registry."""

    HKEY_CURRENT_USER = "HKCU"
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1
    REG_BINARY = 3

    def __init__(self):
        self.keys = {
            autostart.RUN_KEY_PATH: {},
            autostart.STARTUP_APPROVED_KEY_PATH: {},
        }
        self.raise_on_set = None
        self.raise_on_delete = None

    class _KeyHandle:
        def __init__(self, mock: MockWinreg, subkey: str, write: bool = False):
            self.mock = mock
            self.subkey = subkey
            self.write = write

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def OpenKey(self, root, subkey, reserved=0, access=0):
        if subkey not in self.keys:
            raise FileNotFoundError(f"Subkey not found: {subkey}")
        write = bool(access & self.KEY_SET_VALUE)
        return self._KeyHandle(self, subkey, write=write)

    def CreateKey(self, root, subkey):
        if subkey not in self.keys:
            self.keys[subkey] = {}
        return self._KeyHandle(self, subkey, write=True)

    def QueryValueEx(self, handle, name):
        store = self.keys.get(handle.subkey, {})
        if name not in store:
            raise FileNotFoundError(f"Value not found: {name}")
        return store[name]

    def SetValueEx(self, handle, name, reserved, val_type, value):
        if self.raise_on_set:
            raise self.raise_on_set
        self.keys.setdefault(handle.subkey, {})[name] = (value, val_type)

    def DeleteValue(self, handle, name):
        if self.raise_on_delete:
            raise self.raise_on_delete
        store = self.keys.get(handle.subkey, {})
        if name not in store:
            raise FileNotFoundError(f"Value not found: {name}")
        del store[name]


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

@pytest.fixture
def mock_reg(monkeypatch):
    """Fixture providing isolated mock winreg and forcing supported state."""
    reg = MockWinreg()
    monkeypatch.setattr(autostart, "_force_winreg", reg)
    monkeypatch.setattr(autostart, "_force_supported", True)
    return reg


@pytest.fixture
def clean_qsettings():
    """Ensure temporary QSettings scope for test isolation."""
    settings = QSettings("RESIVO", "StaffConsole")
    old_val = settings.value("general/start_minimized", None)
    yield settings
    if old_val is None:
        settings.remove("general/start_minimized")
    else:
        settings.setValue("general/start_minimized", old_val)


# ---------------------------------------------------------------------------
# Unit tests: Registry and autostart platform module
# ---------------------------------------------------------------------------

def test_is_supported_conditions(monkeypatch):
    monkeypatch.setattr(autostart, "_force_supported", None)

    # 1. Non-Windows OS -> Unsupported
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert not autostart.is_supported()

    # 2. Windows running from source (sys.frozen not set) -> Unsupported
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert not autostart.is_supported()

    # 3. Windows running as frozen EXE -> Supported
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert autostart.is_supported()


def test_format_command_with_spaces_and_accents():
    path = r"C:\Program Files\RÉSIVO Console\RESIVO.exe"
    cmd = autostart.format_command(path)
    expected = f'"{path}" --autostart'
    assert cmd == expected


def test_enable_writes_quoted_path_and_clears_startup_approved(mock_reg):
    fake_exe = r"C:\Apps\Residence Management\RESIVO.exe"
    # Seed a disabled flag in StartupApproved (byte 0x03)
    mock_reg.keys[autostart.STARTUP_APPROVED_KEY_PATH][autostart.VALUE_NAME] = (
        b"\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
        mock_reg.REG_BINARY,
    )

    success, err = autostart.enable(fake_exe)
    assert success is True
    assert err is None

    # Check Run key
    val, vtype = mock_reg.keys[autostart.RUN_KEY_PATH][autostart.VALUE_NAME]
    assert val == f'"{fake_exe}" --autostart'
    assert vtype == mock_reg.REG_SZ

    # Check StartupApproved disabled flag was cleared
    assert autostart.VALUE_NAME not in mock_reg.keys[autostart.STARTUP_APPROVED_KEY_PATH]


def test_disable_deletes_value_and_succeeds_if_missing(mock_reg):
    # Case 1: Value exists
    mock_reg.keys[autostart.RUN_KEY_PATH][autostart.VALUE_NAME] = (
        '"C:\\RESIVO.exe" --autostart',
        mock_reg.REG_SZ,
    )
    success, err = autostart.disable()
    assert success is True
    assert err is None
    assert autostart.VALUE_NAME not in mock_reg.keys[autostart.RUN_KEY_PATH]

    # Case 2: Value already missing -> safe no-op
    success, err = autostart.disable()
    assert success is True
    assert err is None


def test_get_state_all_variants(mock_reg, monkeypatch):
    # 1. Unsupported
    monkeypatch.setattr(autostart, "_force_supported", False)
    assert autostart.get_state() == "unsupported"

    # 2. Disabled (Run value missing)
    monkeypatch.setattr(autostart, "_force_supported", True)
    assert autostart.get_state() == "disabled"

    # 3. Enabled (Run value present, no StartupApproved restriction)
    mock_reg.keys[autostart.RUN_KEY_PATH][autostart.VALUE_NAME] = (
        '"C:\\RESIVO.exe" --autostart',
        mock_reg.REG_SZ,
    )
    assert autostart.get_state() == "enabled"

    # 4. Enabled with StartupApproved 0x02 (explicitly enabled by Windows)
    mock_reg.keys[autostart.STARTUP_APPROVED_KEY_PATH][autostart.VALUE_NAME] = (
        b"\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
        mock_reg.REG_BINARY,
    )
    assert autostart.get_state() == "enabled"

    # 5. Disabled by Windows (StartupApproved byte 0x03)
    mock_reg.keys[autostart.STARTUP_APPROVED_KEY_PATH][autostart.VALUE_NAME] = (
        b"\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
        mock_reg.REG_BINARY,
    )
    assert autostart.get_state() == "disabled_by_windows"

    # 6. Disabled by Windows (StartupApproved byte 0x07)
    mock_reg.keys[autostart.STARTUP_APPROVED_KEY_PATH][autostart.VALUE_NAME] = (
        b"\x07\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
        mock_reg.REG_BINARY,
    )
    assert autostart.get_state() == "disabled_by_windows"


def test_repair_moved_exe(mock_reg):
    old_exe = r"C:\OldDir\RESIVO.exe"
    new_exe = r"C:\NewDir\RESIVO.exe"

    # If key does NOT exist: do nothing (never re-enable silently)
    repaired = autostart.repair(new_exe)
    assert repaired is False
    assert autostart.VALUE_NAME not in mock_reg.keys[autostart.RUN_KEY_PATH]

    # If key exists pointing to old path: rewrite with new path
    mock_reg.keys[autostart.RUN_KEY_PATH][autostart.VALUE_NAME] = (
        f'"{old_exe}" --autostart',
        mock_reg.REG_SZ,
    )
    repaired = autostart.repair(new_exe)
    assert repaired is True
    val, _ = mock_reg.keys[autostart.RUN_KEY_PATH][autostart.VALUE_NAME]
    assert val == f'"{new_exe}" --autostart'

    # If key exists pointing to current path: no-op
    repaired = autostart.repair(new_exe)
    assert repaired is False


def test_start_minimized_preference_persistence(clean_qsettings):
    autostart.set_start_minimized_setting(True)
    assert autostart.get_start_minimized_setting() is True

    autostart.set_start_minimized_setting(False)
    assert autostart.get_start_minimized_setting() is False


def test_single_instance_guard(tmp_path, monkeypatch):
    lock_path = tmp_path / "resivo.lock"

    brought_to_front_pids = []
    monkeypatch.setattr(
        autostart, "bring_pid_to_front", lambda pid: brought_to_front_pids.append(pid) or True
    )

    # 1. Primary instance starts
    lock1, exit_code1 = autostart.acquire_single_instance(lock_path, is_autostart=False)
    assert lock1 is not None
    assert exit_code1 is None
    assert lock1.isLocked()

    # 2. Second instance starts with --autostart -> exits silently (code 0)
    lock2, exit_code2 = autostart.acquire_single_instance(lock_path, is_autostart=True)
    assert lock2 is None
    assert exit_code2 == 0
    assert len(brought_to_front_pids) == 0

    # 3. Second instance starts normally -> brings existing instance to front, exits (code 0)
    lock3, exit_code3 = autostart.acquire_single_instance(lock_path, is_autostart=False)
    assert lock3 is None
    assert exit_code3 == 0
    assert len(brought_to_front_pids) == 1
    assert brought_to_front_pids[0] == os.getpid()

    # 4. Primary instance exits / unlocks
    lock1.unlock()

    # 5. Subsequent instance can now acquire lock
    lock4, exit_code4 = autostart.acquire_single_instance(lock_path, is_autostart=False)
    assert lock4 is not None
    assert exit_code4 is None
    lock4.unlock()


# ---------------------------------------------------------------------------
# UI tests: SettingsPage autostart controls
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    client = MagicMock()
    client.auth.get_user.return_value = {"id": "staff-1", "email": "staff@resivo.dz"}
    client.rpc.return_value.execute.return_value.data = {"writes_enabled": False}
    return client


def test_settings_page_autostart_when_unsupported(qapp, monkeypatch, mock_client):
    monkeypatch.setattr(autostart, "_force_supported", False)
    page = SettingsPage(mock_client)

    assert not page.autostart_container.isHidden()
    assert not page.autostart_checkbox.isEnabled()
    assert not page.autostart_checkbox.isChecked()
    assert "Available in the installed app (EXE) only." in page.autostart_helper.text()
    assert not page.start_minimized_checkbox.isEnabled()


def test_settings_page_autostart_toggle_enable_and_disable(qapp, mock_reg, monkeypatch, mock_client):
    monkeypatch.setattr(autostart, "_force_supported", True)
    page = SettingsPage(mock_client)

    # Initial state: disabled in registry
    assert page.autostart_checkbox.isEnabled()
    assert not page.autostart_checkbox.isChecked()
    assert not page.start_minimized_checkbox.isEnabled()
    assert page.autostart_win_note.isHidden()

    # User turns ON switch
    page.autostart_checkbox.setChecked(True)
    assert page.autostart_checkbox.isChecked()
    assert page.start_minimized_checkbox.isEnabled()
    assert autostart.VALUE_NAME in mock_reg.keys[autostart.RUN_KEY_PATH]

    # User turns OFF switch
    page.autostart_checkbox.setChecked(False)
    assert not page.autostart_checkbox.isChecked()
    assert not page.start_minimized_checkbox.isEnabled()
    assert autostart.VALUE_NAME not in mock_reg.keys[autostart.RUN_KEY_PATH]


def test_settings_page_autostart_error_reverts_switch(qapp, mock_reg, monkeypatch, mock_client):
    monkeypatch.setattr(autostart, "_force_supported", True)
    mock_reg.raise_on_set = PermissionError("Access denied writing to HKCU")

    page = SettingsPage(mock_client)
    assert not page.autostart_checkbox.isChecked()

    # User attempts to turn ON switch
    page.autostart_checkbox.setChecked(True)

    # Error banner is visible with message and switch reverted to False
    assert not page.autostart_error_banner.isHidden()
    assert "Access denied" in page.autostart_error_banner._message.text()
    assert not page.autostart_checkbox.isChecked()
    assert not page.start_minimized_checkbox.isEnabled()


def test_settings_page_shows_disabled_by_windows_note(qapp, mock_reg, monkeypatch, mock_client):
    monkeypatch.setattr(autostart, "_force_supported", True)
    # Seed enabled in Run key, but disabled in StartupApproved
    mock_reg.keys[autostart.RUN_KEY_PATH][autostart.VALUE_NAME] = (
        '"C:\\RESIVO.exe" --autostart',
        mock_reg.REG_SZ,
    )
    mock_reg.keys[autostart.STARTUP_APPROVED_KEY_PATH][autostart.VALUE_NAME] = (
        b"\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
        mock_reg.REG_BINARY,
    )

    page = SettingsPage(mock_client)
    assert not page.autostart_checkbox.isChecked()
    assert not page.start_minimized_checkbox.isEnabled()
    assert not page.autostart_win_note.isHidden()
    assert "Turned off in Windows Startup settings" in page.autostart_win_note.text()


def test_no_network_call_or_worker_started_by_autostart(mock_reg, monkeypatch):
    network_calls = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: network_calls.append(args))

    autostart.is_supported()
    autostart.get_state()
    autostart.enable("C:\\RESIVO.exe")
    autostart.repair("C:\\RESIVO.exe")
    autostart.disable()
    autostart.get_start_minimized_setting()
    autostart.set_start_minimized_setting(True)

    assert len(network_calls) == 0
