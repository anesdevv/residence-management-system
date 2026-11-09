"""Unit tests for Minimize to System Tray feature in RÉSIVO desktop app."""

from unittest.mock import MagicMock, patch
import pytest

from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QDialog, QSystemTrayIcon, QWidget

from desktop.app.ui.close_policy import (
    CloseConfirmDialog,
    get_minimize_to_tray_setting,
    set_minimize_to_tray_setting,
)
from desktop.app.ui.pages.settings import SettingsPage


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_minimize_to_tray_setting_persistence(monkeypatch):
    test_settings = {}
    monkeypatch.setattr(QSettings, "value", lambda self, key, default=None, **kwargs: test_settings.get(key, default))
    monkeypatch.setattr(QSettings, "setValue", lambda self, key, val: test_settings.__setitem__(key, val))

    # Default is True
    assert get_minimize_to_tray_setting() is True

    # Persist False
    set_minimize_to_tray_setting(False)
    assert get_minimize_to_tray_setting() is False

    # Persist True
    set_minimize_to_tray_setting(True)
    assert get_minimize_to_tray_setting() is True


def test_settings_page_minimize_tray_toggle(qapp, monkeypatch):
    test_settings = {}
    monkeypatch.setattr(QSettings, "value", lambda self, key, default=None, **kwargs: test_settings.get(key, default))
    monkeypatch.setattr(QSettings, "setValue", lambda self, key, val: test_settings.__setitem__(key, val))

    mock_client = MagicMock()
    page = SettingsPage(mock_client)

    assert hasattr(page, "minimize_tray_checkbox")
    assert page.minimize_tray_checkbox.text() == "Minimize to system tray"
    assert page.minimize_tray_checkbox.isChecked() is True

    # Toggle off
    page.minimize_tray_checkbox.setChecked(False)
    assert get_minimize_to_tray_setting() is False

    # Toggle back on
    page.minimize_tray_checkbox.setChecked(True)
    assert get_minimize_to_tray_setting() is True


def test_close_confirm_dialog_minimize_button(qapp):
    # When not busy, "Minimize to tray" button is available
    dlg = CloseConfirmDialog(is_busy=False)
    assert dlg.minimize_btn is not None
    assert dlg.minimize_btn.text() == "Minimize to tray"
    assert dlg.was_minimized_to_tray is False

    # Clicking minimize button sets was_minimized_to_tray and rejects dialog
    dlg.minimize_btn.click()
    assert dlg.was_minimized_to_tray is True
    assert dlg.result() == QDialog.DialogCode.Rejected

    # When busy, minimize button is None
    dlg_busy = CloseConfirmDialog(is_busy=True)
    assert dlg_busy.minimize_btn is None


def test_main_window_minimize_to_tray_lifecycle(qapp, monkeypatch):
    from desktop.app.ui.main_window import MainWindow

    mock_client = MagicMock()
    mock_client.auth.get_user.return_value = MagicMock(user=MagicMock(email="staff@univ-tlemcen.dz", id="staff-1"))
    mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data={"role": "staff"}
    )

    dummy_page = lambda *args, **kwargs: QWidget()
    monkeypatch.setattr("desktop.app.ui.main_window.LiveSyncWorker.start", lambda self: None)

    with patch("desktop.app.ui.main_window.resolve_role", return_value="staff"), \
         patch("desktop.app.ui.main_window.remember_role"), \
         patch("desktop.app.ui.main_window.OverviewPage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.PendingPage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.ResidentsPage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.RoomsPage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.MaintenancePage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.RoomChangesPage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.OfficialListPage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.SettingsPage", side_effect=dummy_page):

        win = MainWindow(mock_client, role="staff")
        win.show()
        qapp.processEvents()

        # Mock tray icon
        mock_tray = MagicMock()
        mock_tray.isVisible.return_value = True
        win.tray_icon = mock_tray

        # Initial state
        assert win._in_tray is False
        assert win.isVisible() is True

        # 1. Minimize to tray directly
        win.minimize_to_tray()
        assert win._in_tray is True
        assert win.isVisible() is False

        # 2. Restore from tray
        win._restore_from_tray()
        assert win._in_tray is False
        assert win.isVisible() is True

        # 3. Test tray activation toggle (active window -> minimize to tray)
        with patch.object(win, "isActiveWindow", return_value=True):
            win._on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
            assert win._in_tray is True

        # 4. Tray activation toggle (hidden window -> restore)
        win._on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
        assert win._in_tray is False

        # 5. Close event with minimize to tray choice
        fake_dlg = MagicMock()
        fake_dlg.exec.return_value = QDialog.DialogCode.Rejected
        fake_dlg.was_minimized_to_tray = True

        with patch("desktop.app.ui.main_window.CloseConfirmDialog", return_value=fake_dlg), \
             patch.object(win, "minimize_to_tray") as mock_min_tray:
            close_event = QCloseEvent()
            win.closeEvent(close_event)
            assert not close_event.isAccepted()
            assert mock_min_tray.called

        win.hide()
