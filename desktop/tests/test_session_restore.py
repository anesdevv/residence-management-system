"""Tests for Phase 2: Stay signed in until Windows restarts integration.

Covers startup restore, role verification, failure modes (auth error, reboot,
network timeout), remember setting, language restart banner, and GUI responsiveness.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication, QWidget

from desktop.app.timeouts import NetworkError, NetworkTimeoutError
from desktop.app.ui.login_window import LoginWindow
from desktop.app.ui.main_window import MainWindow
from desktop.app.ui.pages.settings import SettingsPage
from desktop.auth.session_store import (
    FakeBackend,
    SessionManager,
    SessionStore,
    get_remember_session_setting,
    set_remember_session_setting,
)
from desktop.i18n import set_saved_language, t
from desktop.main import launch_application

_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


@pytest.fixture
def qapp():
    return _qapp


def wait_until(qapp, predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


# ---------------------------------------------------------------------------
# Mocks
# ---------------------------------------------------------------------------
class MockAuth:
    def __init__(self):
        self._in_memory_session: Any = None
        self._callbacks: list[Callable] = []
        self.set_session_calls: list[tuple[str, str]] = []
        self.sign_out_calls: int = 0
        self.set_session_error: Exception | None = None

    def on_auth_state_change(self, callback: Callable):
        self._callbacks.append(callback)
        return SimpleNamespace(unsubscribe=lambda: None)

    def set_session(self, access_token: str, refresh_token: str):
        self.set_session_calls.append((access_token, refresh_token))
        if self.set_session_error:
            raise self.set_session_error
        self._in_memory_session = SimpleNamespace(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=1900000000,
            user=SimpleNamespace(id="usr_123", email="staff@test.local"),
        )
        return SimpleNamespace(session=self._in_memory_session)

    def get_user(self):
        return SimpleNamespace(user=SimpleNamespace(id="usr_123", email="staff@test.local"))

    def get_session(self):
        return self._in_memory_session

    def sign_out(self):
        self.sign_out_calls += 1
        self._in_memory_session = None


class MockClient:
    def __init__(self, role: str = "admin"):
        self.auth = MockAuth()
        self.role_value = role
        self.profile_calls = 0
        self.profile_lookup_error: Exception | None = None

    def table(self, name: str):
        class MockQuery:
            def __init__(self, client):
                self.client = client

            def select(self, *_args, **_kwargs):
                return self

            def eq(self, *_args, **_kwargs):
                return self

            def single(self):
                return self

            def execute(self):
                if self.client.profile_lookup_error:
                    raise self.client.profile_lookup_error
                self.client.profile_calls += 1
                return SimpleNamespace(data={"role": self.client.role_value})

        return MockQuery(self)


_PAGE_NAMES = [
    "OverviewPage",
    "PendingPage",
    "ResidentsPage",
    "RoomsPage",
    "MaintenancePage",
    "RoomChangesPage",
    "OfficialListPage",
    "StaffAccountsPage",
    "SettingsPage",
]


def _patch_main_pages(monkeypatch):
    import sys
    for name in _PAGE_NAMES:
        for prefix in ("desktop.app.ui.main_window", "app.ui.main_window"):
            try:
                monkeypatch.setattr(f"{prefix}.{name}", lambda client, **_kwargs: QWidget())
            except Exception:
                pass
    for mod_name in ("desktop.app.ui.main_window", "app.ui.main_window"):
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
            if hasattr(mod, "LiveSyncWorker"):
                monkeypatch.setattr(mod.LiveSyncWorker, "start", lambda self: None)
    for mod_name in ("desktop.app.ui.pages.settings", "app.ui.pages.settings"):
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
            if hasattr(mod, "McpHealthWorker"):
                monkeypatch.setattr(mod.McpHealthWorker, "start", lambda self: None)


@pytest.fixture
def clean_settings():
    set_remember_session_setting(True)
    yield
    set_remember_session_setting(True)


@pytest.fixture
def fake_backend():
    return FakeBackend(logon_session_id="0:5555", boot_epoch=1700000000)


@pytest.fixture
def test_session_manager(tmp_path: Path, fake_backend):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    return SessionManager(store=store)


# ---------------------------------------------------------------------------
# Test 1: Restore succeeds -> MainWindow opens directly (admin vs staff)
# ---------------------------------------------------------------------------
def test_restore_succeeds_admin_vs_staff(qapp, monkeypatch, test_session_manager):
    _patch_main_pages(monkeypatch)

    # Pre-populate store with valid session
    test_session_manager.store.save(
        {
            "access_token": "tok_valid_acc",
            "refresh_token": "tok_valid_ref",
            "expires_at": 1800000000,
            "user_id": "usr_123",
        },
        remember=True,
    )

    # 1. Test Admin
    client_admin = MockClient(role="admin")
    launch_application(
        app=qapp,
        client=client_admin,
        session_manager_instance=test_session_manager,
        exec_loop=False,
    )
    finished = wait_until(qapp, lambda: getattr(qapp, "_main_window", None) is not None, timeout=3.0)
    assert finished is True
    main_win = getattr(qapp, "_main_window", None)
    assert isinstance(main_win, MainWindow)
    assert getattr(main_win, "role", None) == "admin"
    assert "Staff accounts" in main_win.pages
    main_win.close()
    qapp._main_window = None

    # 2. Test Staff
    client_staff = MockClient(role="staff")
    launch_application(
        app=qapp,
        client=client_staff,
        session_manager_instance=test_session_manager,
        exec_loop=False,
    )
    finished = wait_until(qapp, lambda: getattr(qapp, "_main_window", None) is not None, timeout=3.0)
    assert finished is True
    main_win_staff = getattr(qapp, "_main_window", None)
    assert isinstance(main_win_staff, MainWindow)
    assert getattr(main_win_staff, "role", None) == "staff"
    assert "Staff accounts" not in main_win_staff.pages
    main_win_staff.close()
    qapp._main_window = None


# ---------------------------------------------------------------------------
# Test 2: Restore fails with auth error -> file cleared, LoginWindow shown
# ---------------------------------------------------------------------------
def test_restore_fails_auth_error(qapp, monkeypatch, test_session_manager):
    test_session_manager.store.save(
        {
            "access_token": "tok_expired_acc",
            "refresh_token": "tok_expired_ref",
            "expires_at": 1800000000,
            "user_id": "usr_123",
        },
        remember=True,
    )
    assert test_session_manager.store.session_file.exists()

    client = MockClient()
    client.auth.set_session_error = Exception("Invalid Refresh Token")

    launch_application(
        app=qapp,
        client=client,
        session_manager_instance=test_session_manager,
        exec_loop=False,
    )
    finished = wait_until(qapp, lambda: getattr(qapp, "_main_window", None) is not None, timeout=3.0)
    assert finished is True
    login_win = getattr(qapp, "_main_window", None)
    assert isinstance(login_win, LoginWindow)
    assert not test_session_manager.store.session_file.exists()
    assert login_win.error_banner.isVisible()
    assert login_win.error_banner._message.text() == t("login.session_expired")
    login_win.close()
    qapp._main_window = None


# ---------------------------------------------------------------------------
# Test 3: Restore fails with Windows restart -> file cleared, LoginWindow shown
# ---------------------------------------------------------------------------
def test_restore_fails_windows_restart(qapp, monkeypatch, tmp_path):
    # Backend that created the session had logon_session_id="0:1111"
    store_backend_old = FakeBackend(logon_session_id="0:1111", boot_epoch=1700000000)
    store = SessionStore(backend=store_backend_old, storage_dir=tmp_path)
    store.save(
        {
            "access_token": "tok_reboot_acc",
            "refresh_token": "tok_reboot_ref",
            "expires_at": 1800000000,
            "user_id": "usr_123",
        },
        remember=True,
    )
    assert store.session_file.exists()

    # Now Windows restarted, current logon_session_id is "0:2222"
    current_backend = FakeBackend(logon_session_id="0:2222", boot_epoch=1700000000)
    store_current = SessionStore(backend=current_backend, storage_dir=tmp_path)
    manager = SessionManager(store=store_current)

    client = MockClient()
    launch_application(
        app=qapp,
        client=client,
        session_manager_instance=manager,
        exec_loop=False,
    )
    finished = wait_until(qapp, lambda: getattr(qapp, "_main_window", None) is not None, timeout=3.0)
    assert finished is True
    login_win = getattr(qapp, "_main_window", None)
    assert isinstance(login_win, LoginWindow)
    assert not store.session_file.exists()
    assert login_win.error_banner.isVisible()
    assert login_win.error_banner._message.text() == t("login.session_rebooted")
    login_win.close()
    qapp._main_window = None


# ---------------------------------------------------------------------------
# Test 4: Restore fails with network timeout -> file KEPT, MainWindow opens
# ---------------------------------------------------------------------------
def test_restore_fails_network_timeout(qapp, monkeypatch, test_session_manager):
    _patch_main_pages(monkeypatch)

    test_session_manager.store.save(
        {
            "access_token": "tok_net_acc",
            "refresh_token": "tok_net_ref",
            "expires_at": 1800000000,
            "user_id": "usr_123",
        },
        remember=True,
    )
    assert test_session_manager.store.session_file.exists()

    client = MockClient()
    client.auth.set_session_error = NetworkTimeoutError("Timed out contacting Supabase")
    client.profile_lookup_error = NetworkTimeoutError("Timed out contacting Supabase")

    launch_application(
        app=qapp,
        client=client,
        session_manager_instance=test_session_manager,
        exec_loop=False,
    )
    finished = wait_until(qapp, lambda: getattr(qapp, "_main_window", None) is not None, timeout=3.0)
    assert finished is True
    main_win = getattr(qapp, "_main_window", None)
    assert isinstance(main_win, MainWindow)
    # File must be preserved!
    assert test_session_manager.store.session_file.exists()
    # Offline role check shows banner
    assert getattr(main_win, "role", None) is None
    main_win.close()
    qapp._main_window = None


# ---------------------------------------------------------------------------
# Test 5: Sign out deletes file and revokes; closing does NOT delete file
# ---------------------------------------------------------------------------
def test_sign_out_deletes_file_and_closing_keeps_file(qapp, monkeypatch, test_session_manager):
    _patch_main_pages(monkeypatch)

    # Save session
    test_session_manager.store.save(
        {
            "access_token": "tok_so_acc",
            "refresh_token": "tok_so_ref",
            "expires_at": 1800000000,
            "user_id": "usr_123",
        },
        remember=True,
    )
    assert test_session_manager.store.session_file.exists()

    client = MockClient(role="admin")
    window = MainWindow(client, role="admin")

    # Monkeypatch session_manager in main_window to use our test store
    monkeypatch.setattr("desktop.app.ui.main_window.session_manager", test_session_manager)

    # 1. Closing does NOT delete the session file
    window.close()
    qapp.processEvents()
    assert test_session_manager.store.session_file.exists()

    # 2. Sign-out DOES delete the session file and revokes on server
    window = MainWindow(client, role="admin")
    window._finish_sign_out(show_login=False)
    # Drain workers
    wait_until(qapp, lambda: not window.tasks.is_busy("sign-out"), timeout=3.0)
    qapp.processEvents()

    assert not test_session_manager.store.session_file.exists()
    assert client.auth.sign_out_calls >= 1
    window.close()


# ---------------------------------------------------------------------------
# Test 6: Remember setting OFF -> no file after login, login required on next launch
# ---------------------------------------------------------------------------
def test_remember_setting_off(qapp, monkeypatch, test_session_manager):
    _patch_main_pages(monkeypatch)

    set_remember_session_setting(False)
    assert get_remember_session_setting() is False

    client = MockClient(role="admin")
    login_win = LoginWindow(
        client=client,
        session_manager=test_session_manager,
    )
    assert login_win.remember_checkbox.isChecked() is False

    # Simulate sign in
    login_win.email.setText("staff@univ-tlemcen.dz")
    login_win.password.setText("SecretPass123!")
    login_win.attempt()
    assert wait_until(qapp, lambda: not login_win._busy)
    qapp.processEvents()

    # Session file must NOT be created when remember is False
    assert not test_session_manager.store.session_file.exists()

    # On next launch, LoginWindow should open directly
    launch_application(
        app=qapp,
        client=client,
        session_manager_instance=test_session_manager,
        exec_loop=False,
    )
    qapp.processEvents()
    next_win = getattr(qapp, "_main_window", None)
    assert isinstance(next_win, LoginWindow)
    next_win.close()
    qapp._main_window = None

    set_remember_session_setting(True)


# ---------------------------------------------------------------------------
# Test 7: Checkbox default is checked
# ---------------------------------------------------------------------------
def test_checkbox_default_checked(qapp, clean_settings, test_session_manager):
    set_remember_session_setting(True)
    win = LoginWindow(session_manager=test_session_manager)
    assert win.remember_checkbox.isChecked() is True

    # Toggling updates QSettings
    win.remember_checkbox.setChecked(False)
    assert get_remember_session_setting() is False

    win.remember_checkbox.setChecked(True)
    assert get_remember_session_setting() is True
    win.close()


# ---------------------------------------------------------------------------
# Test 8: Language restart message reflects remember setting
# ---------------------------------------------------------------------------
def test_language_restart_banner_reflects_remember_setting(qapp, monkeypatch, clean_settings):
    monkeypatch.setattr("desktop.app.ui.pages.settings.McpHealthWorker.start", lambda self: None)
    set_saved_language("en")
    client = MockClient(role="admin")
    page = SettingsPage(client=client)
    page.show()
    qapp.processEvents()

    # When remember setting is ON:
    set_remember_session_setting(True)
    page.lang_combo.setCurrentIndex(1)
    page._on_language_changed(1)  # toggle language to fr
    qapp.processEvents()
    assert page.lang_restart_banner.isVisible()
    assert page.lang_restart_banner._message.text() == t("settings.restart_banner_message")

    # When remember setting is OFF:
    set_remember_session_setting(False)
    page.lang_combo.setCurrentIndex(0)
    page._on_language_changed(0)  # toggle language to en
    qapp.processEvents()
    assert page.lang_restart_banner.isVisible()
    assert page.lang_restart_banner._message.text() == t("settings.restart_banner_message_need_login")
    if hasattr(page, "health_worker"):
        page.health_worker.stop()
    page.close()


# ---------------------------------------------------------------------------
# Test 9: Autostart + start-minimized restores minimized
# ---------------------------------------------------------------------------
def test_autostart_start_minimized_restores_minimized(qapp, monkeypatch, test_session_manager):
    _patch_main_pages(monkeypatch)

    test_session_manager.store.save(
        {
            "access_token": "tok_min_acc",
            "refresh_token": "tok_min_ref",
            "expires_at": 1800000000,
            "user_id": "usr_123",
        },
        remember=True,
    )

    monkeypatch.setattr("desktop.platform.autostart.get_start_minimized_setting", lambda: True)

    client = MockClient(role="admin")
    launch_application(
        app=qapp,
        client=client,
        session_manager_instance=test_session_manager,
        is_autostart=True,
        exec_loop=False,
    )
    finished = wait_until(qapp, lambda: getattr(qapp, "_main_window", None) is not None, timeout=3.0)
    assert finished is True
    main_win = getattr(qapp, "_main_window", None)
    assert isinstance(main_win, MainWindow)
    assert main_win.isMinimized()
    main_win.close()
    qapp._main_window = None


# ---------------------------------------------------------------------------
# Test 10: Workers start only after role check
# ---------------------------------------------------------------------------
def test_workers_start_only_after_role_check(qapp, monkeypatch, test_session_manager):
    test_session_manager.store.save(
        {
            "access_token": "tok_denied_acc",
            "refresh_token": "tok_denied_ref",
            "expires_at": 1800000000,
            "user_id": "usr_denied",
        },
        remember=True,
    )

    # Role is student (denied)
    client = MockClient(role="student")
    launch_application(
        app=qapp,
        client=client,
        session_manager_instance=test_session_manager,
        exec_loop=False,
    )
    finished = wait_until(qapp, lambda: getattr(qapp, "_main_window", None) is not None, timeout=3.0)
    assert finished is True
    win = getattr(qapp, "_main_window", None)
    # MainWindow must never be instantiated: LoginWindow shown with access denied!
    assert isinstance(win, LoginWindow)
    assert win.error_banner.isVisible()
    assert win.error_banner._message.text() == t("login.access_denied")
    # Session must be wiped
    assert not test_session_manager.store.session_file.exists()
    win.close()
    qapp._main_window = None


# ---------------------------------------------------------------------------
# Test 11: GUI event loop stays responsive during restore (< 150 ms intervals)
# ---------------------------------------------------------------------------
class EventLoopHeartbeat:
    def __init__(self, interval_ms: int = 30):
        self.interval_ms = interval_ms
        self.timer = QTimer()
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self._on_tick)
        self.tick_count = 0
        self.largest_gap_ms = 0.0
        self.gaps = []
        self._last_tick: float | None = None

    def start(self):
        self._last_tick = time.monotonic()
        self.timer.start()

    def _on_tick(self):
        now = time.monotonic()
        if self._last_tick is not None:
            gap_ms = (now - self._last_tick) * 1000.0
            self.gaps.append(round(gap_ms, 1))
            if gap_ms > self.largest_gap_ms:
                self.largest_gap_ms = gap_ms
        self._last_tick = now
        self.tick_count += 1

    def stop(self):
        self.timer.stop()


def test_gui_event_loop_responsive_during_restore(qapp, monkeypatch, test_session_manager):
    _patch_main_pages(monkeypatch)

    test_session_manager.store.save(
        {
            "access_token": "tok_slow_acc",
            "refresh_token": "tok_slow_ref",
            "expires_at": 1800000000,
            "user_id": "usr_123",
        },
        remember=True,
    )

    client = MockClient(role="admin")

    # Introduce deliberate 0.5s network latency inside set_session
    original_set_session = client.auth.set_session

    def _slow_set_session(acc, ref):
        time.sleep(0.5)
        return original_set_session(acc, ref)

    client.auth.set_session = _slow_set_session

    heartbeat = EventLoopHeartbeat(interval_ms=30)
    heartbeat.start()

    launch_application(
        app=qapp,
        client=client,
        session_manager_instance=test_session_manager,
        exec_loop=False,
    )

    # Stop heartbeat as soon as restore completes, so we measure event loop
    # responsiveness strictly during the background restore operation.
    if hasattr(qapp, "_startup_bridge") and qapp._startup_bridge is not None:
        qapp._startup_bridge.restore_done.connect(lambda *_: heartbeat.stop())

    finished = wait_until(qapp, lambda: getattr(qapp, "_main_window", None) is not None, timeout=5.0)
    heartbeat.stop()

    assert finished is True
    assert isinstance(getattr(qapp, "_main_window", None), MainWindow)
    # Event loop heartbeat must never exceed 150 ms gap during off-thread restore
    assert heartbeat.largest_gap_ms < 150.0, f"GUI frozen during restore: {heartbeat.largest_gap_ms} ms"
    assert heartbeat.tick_count >= 5

    getattr(qapp, "_main_window", None).close()
    qapp._main_window = None
