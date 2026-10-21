import os
import threading
import time
from unittest.mock import MagicMock
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication, QPushButton, QWidget
from desktop.app.ui.main_window import MainWindow
from desktop.app.ui.login_window import LoginWindow


_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


@pytest.fixture
def qapp():
    return _qapp


def wait_until(qapp, predicate, timeout=4.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    qapp.processEvents()
    return bool(predicate())


def build_window(monkeypatch, client=None):
    monkeypatch.setattr("desktop.app.ui.main_window.current_role", lambda c: "admin")
    monkeypatch.setattr("desktop.app.ui.main_window.LiveSyncWorker.start", lambda self: None)
    monkeypatch.setattr("desktop.app.ui.pages.settings.McpHealthWorker.start", lambda self: None)
    for p in [
        "OverviewPage", "PendingPage", "ResidentsPage", "RoomsPage",
        "MaintenancePage", "RoomChangesPage", "OfficialListPage",
        "StaffAccountsPage", "SettingsPage",
    ]:
        monkeypatch.setattr(f"desktop.app.ui.main_window.{p}", lambda client: QWidget())
    return MainWindow(client or MagicMock())


def test_sign_out_button_exists(qapp, monkeypatch):
    monkeypatch.setattr("desktop.app.ui.main_window.current_role", lambda c: "admin")
    monkeypatch.setattr("desktop.app.ui.main_window.LiveSyncWorker.start", lambda self: None)
    monkeypatch.setattr("desktop.app.ui.pages.settings.McpHealthWorker.start", lambda self: None)
    for p in [
        "OverviewPage", "PendingPage", "ResidentsPage", "RoomsPage",
        "MaintenancePage", "RoomChangesPage", "OfficialListPage",
        "StaffAccountsPage", "SettingsPage",
    ]:
        monkeypatch.setattr(f"desktop.app.ui.main_window.{p}", lambda client: QWidget())

    mw = MainWindow(MagicMock())
    btn = mw.findChild(QPushButton, "signOutButton")
    assert btn is not None
    assert btn.text() == "Sign out"
    mw.close()
    _qapp.processEvents()


def test_shutdown_workers_method(qapp, monkeypatch):
    monkeypatch.setattr("desktop.app.ui.main_window.current_role", lambda c: "admin")
    monkeypatch.setattr("desktop.app.ui.main_window.LiveSyncWorker.start", lambda self: None)
    monkeypatch.setattr("desktop.app.ui.pages.settings.McpHealthWorker.start", lambda self: None)
    for p in [
        "OverviewPage", "PendingPage", "ResidentsPage", "RoomsPage",
        "MaintenancePage", "RoomChangesPage", "OfficialListPage",
        "StaffAccountsPage", "SettingsPage",
    ]:
        monkeypatch.setattr(f"desktop.app.ui.main_window.{p}", lambda client: QWidget())

    mw = MainWindow(MagicMock())
    assert hasattr(mw, "_shutdown_workers")

    # Mock sync_worker and health_worker
    mock_sync = MagicMock()
    mock_sync.isRunning.return_value = True
    mock_sync.wait.return_value = True
    mw.sync_worker = mock_sync

    mock_health = MagicMock()
    mock_health.isRunning.return_value = True
    mock_health.wait.return_value = True
    mw.settings_page.health_worker = mock_health

    mw._shutdown_workers()

    mock_sync.stop.assert_called_once()
    mock_health.stop.assert_called_once()
    mock_sync.isRunning.return_value = False
    mw.close()
    _qapp.processEvents()


def test_sign_out_flow(qapp, monkeypatch):
    monkeypatch.setattr("desktop.app.ui.main_window.current_role", lambda c: "admin")
    monkeypatch.setattr("desktop.app.ui.main_window.LiveSyncWorker.start", lambda self: None)
    monkeypatch.setattr("desktop.app.ui.pages.settings.McpHealthWorker.start", lambda self: None)
    for p in [
        "OverviewPage", "PendingPage", "ResidentsPage", "RoomsPage",
        "MaintenancePage", "RoomChangesPage", "OfficialListPage",
        "StaffAccountsPage", "SettingsPage",
    ]:
        monkeypatch.setattr(f"desktop.app.ui.main_window.{p}", lambda client: QWidget())

    mock_client = MagicMock()
    sign_out_threads = []
    mock_client.auth.sign_out.side_effect = lambda: sign_out_threads.append(
        QThread.currentThread()
    )
    mw = MainWindow(mock_client)
    mw.show()
    _qapp.processEvents()

    shutdown_called = []
    monkeypatch.setattr(
        mw, "_shutdown_workers", lambda *_args, **_kwargs: shutdown_called.append(True)
    )

    opened_windows = []
    fake_login_win = MagicMock()
    monkeypatch.setattr("desktop.app.ui.login_window.LoginWindow", lambda: fake_login_win)
    fake_login_win.show.side_effect = lambda: opened_windows.append(fake_login_win)

    mw.sign_out_btn.click()
    assert wait_until(qapp, lambda: len(opened_windows) == 1)
    assert len(shutdown_called) >= 1
    mock_client.auth.sign_out.assert_called_once()
    assert len(sign_out_threads) == 1
    assert sign_out_threads[0] is not qapp.thread()
    assert not mw.isVisible()


def test_minimize_menu_toggle(qapp, monkeypatch):
    monkeypatch.setattr("desktop.app.ui.main_window.current_role", lambda c: "admin")
    monkeypatch.setattr("desktop.app.ui.main_window.LiveSyncWorker.start", lambda self: None)
    monkeypatch.setattr("desktop.app.ui.pages.settings.McpHealthWorker.start", lambda self: None)
    for p in [
        "OverviewPage", "PendingPage", "ResidentsPage", "RoomsPage",
        "MaintenancePage", "RoomChangesPage", "OfficialListPage",
        "StaffAccountsPage", "SettingsPage",
    ]:
        monkeypatch.setattr(f"desktop.app.ui.main_window.{p}", lambda client: QWidget())

    mw = MainWindow(MagicMock())
    mw.show()
    _qapp.processEvents()

    sign_out_btn = mw.findChild(QPushButton, "signOutButton")
    toggle_btn = mw.findChild(QPushButton, "toggleMenuButton")

    assert sign_out_btn is not None
    assert toggle_btn is not None
    assert toggle_btn.text() == "Minimize menu"

    # Verify toggle button is positioned directly below sign out
    footer_layout = mw.sidebar_footer_layout
    sign_out_idx = footer_layout.indexOf(sign_out_btn)
    toggle_idx = footer_layout.indexOf(toggle_btn)
    assert toggle_idx == sign_out_idx + 1

    # Initial expanded state
    assert mw._sidebar_minimized is False
    assert mw.sidebar_widget.width() == 248
    assert sign_out_btn.text() == "Sign out"

    # Click to minimize
    toggle_btn.click()
    _qapp.processEvents()
    assert mw._sidebar_minimized is True
    assert mw.sidebar_widget.width() == 72
    assert toggle_btn.text() == ""
    assert toggle_btn.toolTip() == "Expand menu"
    assert sign_out_btn.text() == ""
    assert sign_out_btn.toolTip() == "Sign out"

    # Click to expand again
    toggle_btn.click()
    _qapp.processEvents()
    assert mw._sidebar_minimized is False
    assert mw.sidebar_widget.width() == 248
    assert toggle_btn.text() == "Minimize menu"
    assert sign_out_btn.text() == "Sign out"

    mw.close()
    _qapp.processEvents()


def test_shutdown_never_terminates_a_lock_holding_worker(qapp, monkeypatch):
    mw = build_window(monkeypatch)
    mock_sync = MagicMock()
    mock_sync.isRunning.return_value = True
    mock_sync.wait.return_value = False
    mw.sync_worker = mock_sync
    mw.settings_page.health_worker = MagicMock()
    mw.settings_page.health_worker.isRunning.return_value = False

    assert mw._shutdown_workers(wait_ms=10) is False
    mock_sync.stop.assert_called_once()
    mock_sync.terminate.assert_not_called()

    # Let the deferred close path finish on a clean state.
    mock_sync.isRunning.return_value = False
    mw.close()
    qapp.processEvents()


def test_sign_out_waits_for_a_running_worker_without_blocking(qapp, monkeypatch):
    client = MagicMock()
    mw = build_window(monkeypatch, client)
    mw.show()
    qapp.processEvents()

    mock_sync = MagicMock()
    mock_sync.isRunning.return_value = True
    mw.sync_worker = mock_sync
    mw.settings_page.health_worker = MagicMock()
    mw.settings_page.health_worker.isRunning.return_value = False

    opened = []
    fake_login = MagicMock()
    fake_login.show.side_effect = lambda: opened.append(fake_login)
    monkeypatch.setattr("desktop.app.ui.login_window.LoginWindow", lambda: fake_login)

    started = time.monotonic()
    mw.sign_out_btn.click()
    assert time.monotonic() - started < 0.3
    assert opened == []
    client.auth.sign_out.assert_not_called()
    assert not mw.sign_out_btn.isEnabled()
    assert mw.isVisible()

    # The worker finishes on its own; only then is the session signed out.
    mock_sync.isRunning.return_value = False
    assert wait_until(qapp, lambda: len(opened) == 1)
    client.auth.sign_out.assert_called_once()
    assert not mw.isVisible()
    qapp.processEvents()


def test_close_is_deferred_while_a_worker_is_still_running(qapp, monkeypatch):
    mw = build_window(monkeypatch)
    mw.show()
    qapp.processEvents()

    mock_sync = MagicMock()
    mock_sync.isRunning.return_value = True
    mw.sync_worker = mock_sync
    mw.settings_page.health_worker = MagicMock()
    mw.settings_page.health_worker.isRunning.return_value = False

    mw.close()
    qapp.processEvents()
    assert mw.isVisible()

    mock_sync.isRunning.return_value = False
    assert wait_until(qapp, lambda: not mw.isVisible())
    qapp.processEvents()


def test_close_during_sign_out_keeps_sign_out_and_skips_login(qapp, monkeypatch):
    client = MagicMock()
    mw = build_window(monkeypatch, client)
    mw.show()
    qapp.processEvents()

    started = threading.Event()
    release = threading.Event()

    def blocking_sign_out():
        started.set()
        assert release.wait(4.0)

    client.auth.sign_out.side_effect = blocking_sign_out

    opened = []
    fake_login = MagicMock()
    fake_login.show.side_effect = lambda: opened.append(fake_login)
    monkeypatch.setattr("desktop.app.ui.login_window.LoginWindow", lambda: fake_login)

    mw.sign_out_btn.click()
    assert started.wait(4.0)
    assert mw.isVisible()

    # Closing mid-request must not discard the sign-out, and must not populate
    # a login window after the operator asked the application to close.
    mw.close()
    qapp.processEvents()
    assert mw.isVisible()

    release.set()
    assert wait_until(qapp, lambda: not mw.isVisible())
    client.auth.sign_out.assert_called_once()
    assert opened == []
    qapp.processEvents()


def test_close_while_sign_out_waits_for_worker_keeps_intent(qapp, monkeypatch):
    client = MagicMock()
    mw = build_window(monkeypatch, client)
    mw.show()
    qapp.processEvents()

    mock_sync = MagicMock()
    mock_sync.isRunning.return_value = True
    mw.sync_worker = mock_sync
    mw.settings_page.health_worker = MagicMock()
    mw.settings_page.health_worker.isRunning.return_value = False

    opened = []
    fake_login = MagicMock()
    fake_login.show.side_effect = lambda: opened.append(fake_login)
    monkeypatch.setattr("desktop.app.ui.login_window.LoginWindow", lambda: fake_login)

    mw.sign_out_btn.click()
    # Sign-out is still waiting for the worker, so it has not started yet.
    client.auth.sign_out.assert_not_called()
    assert mw._pending_shutdown_action == "sign_out"

    # Close before the 100 ms shutdown poll runs.
    mock_sync.isRunning.return_value = False
    mw.close()
    assert wait_until(qapp, lambda: not mw.isVisible())

    client.auth.sign_out.assert_called_once()
    assert opened == []
    qapp.processEvents()


def test_failed_sign_out_clears_local_session_and_warns(qapp, monkeypatch):
    client = MagicMock()
    mw = build_window(monkeypatch, client)
    mw.show()
    qapp.processEvents()

    client.auth.sign_out.side_effect = RuntimeError("token=super-secret")

    opened = []
    fake_login = MagicMock()
    fake_login.show.side_effect = lambda: opened.append(fake_login)
    monkeypatch.setattr("desktop.app.ui.login_window.LoginWindow", lambda: fake_login)

    mw.sign_out_btn.click()
    assert wait_until(qapp, lambda: len(opened) == 1)

    client.auth._remove_session.assert_called_once()
    message = fake_login.show_error.call_args.args[0]
    assert "super-secret" not in message
    assert "token=[redacted]" in message
    assert not mw.isVisible()
    qapp.processEvents()
