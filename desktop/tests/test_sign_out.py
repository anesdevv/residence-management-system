import os
from unittest.mock import MagicMock
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QWidget
from desktop.app.ui.main_window import MainWindow
from desktop.app.ui.login_window import LoginWindow


_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


@pytest.fixture
def qapp():
    return _qapp


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
    mw = MainWindow(mock_client)
    mw.show()
    _qapp.processEvents()

    shutdown_called = []
    monkeypatch.setattr(mw, "_shutdown_workers", lambda: shutdown_called.append(True))

    opened_windows = []
    fake_login_win = MagicMock()
    monkeypatch.setattr("desktop.app.ui.login_window.LoginWindow", lambda: fake_login_win)
    fake_login_win.show.side_effect = lambda: opened_windows.append(fake_login_win)

    mw.sign_out_btn.click()
    _qapp.processEvents()

    assert len(shutdown_called) >= 1
    mock_client.auth.sign_out.assert_called_once()
    assert len(opened_windows) == 1
    assert not mw.isVisible()
