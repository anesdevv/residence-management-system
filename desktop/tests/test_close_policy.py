"""Unit tests for C7: ClosePolicy, CloseConfirmDialog, and closing confirmation."""

from unittest.mock import MagicMock, patch
import pytest

from PySide6.QtCore import QSettings
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QDialog

from desktop.app.ui.close_policy import (
    CloseConfirmDialog,
    ClosePolicy,
    get_confirm_close_setting,
    set_confirm_close_setting,
)
from desktop.app.ui.pages.settings import SettingsPage


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_close_policy_pure_logic():
    # 1. Normal state (not busy, session not ending) follows setting
    assert ClosePolicy.should_confirm(True, False, False) is True
    assert ClosePolicy.should_confirm(False, False, False) is False

    # 2. Busy state ALWAYS confirms, even if setting is False
    assert ClosePolicy.should_confirm(False, True, False) is True
    assert ClosePolicy.should_confirm(True, True, False) is True

    # 3. Session ending NEVER confirms (never blocks OS reboot/shutdown)
    assert ClosePolicy.should_confirm(True, False, True) is False
    assert ClosePolicy.should_confirm(False, False, True) is False
    assert ClosePolicy.should_confirm(True, True, True) is False
    assert ClosePolicy.should_confirm(False, True, True) is False


def test_settings_persistence(monkeypatch):
    test_settings = {}
    monkeypatch.setattr(QSettings, "value", lambda self, key, default=None: test_settings.get(key, default))
    monkeypatch.setattr(QSettings, "setValue", lambda self, key, val: test_settings.__setitem__(key, val))

    set_confirm_close_setting(False)
    assert get_confirm_close_setting() is False

    set_confirm_close_setting(True)
    assert get_confirm_close_setting() is True


def test_close_confirm_dialog_normal(qapp, monkeypatch):
    test_settings = {}
    monkeypatch.setattr(QSettings, "value", lambda self, key, default=None: test_settings.get(key, default))
    monkeypatch.setattr(QSettings, "setValue", lambda self, key, val: test_settings.__setitem__(key, val))

    dlg = CloseConfirmDialog(is_busy=False)
    assert dlg.windowTitle() == "Close RÉSIVO?"
    assert dlg.cancel_btn.isDefault()
    assert dlg.confirm_btn.text() == "Close app"
    assert dlg.dont_ask_checkbox is not None
    assert not dlg.dont_ask_checkbox.isChecked()

    # Cancel rejects dialog
    dlg.cancel_btn.click()
    assert dlg.result() == QDialog.DialogCode.Rejected

    # Dialog with "Don't ask me again" checked updates setting on accept
    dlg2 = CloseConfirmDialog(is_busy=False)
    dlg2.dont_ask_checkbox.setChecked(True)
    dlg2.confirm_btn.click()
    assert dlg2.result() == QDialog.DialogCode.Accepted
    assert get_confirm_close_setting() is False


def test_close_confirm_dialog_busy(qapp):
    dlg = CloseConfirmDialog(is_busy=True)
    assert dlg.windowTitle() == "Close RÉSIVO?"
    assert dlg.confirm_btn.text() == "Close anyway"
    # When busy, "Don't ask me again" is suppressed
    assert dlg.dont_ask_checkbox is None


def test_settings_page_confirm_close_toggle(qapp, monkeypatch):
    test_settings = {}
    monkeypatch.setattr(QSettings, "value", lambda self, key, default=None: test_settings.get(key, default))
    monkeypatch.setattr(QSettings, "setValue", lambda self, key, val: test_settings.__setitem__(key, val))

    mock_client = MagicMock()
    page = SettingsPage(mock_client)

    assert hasattr(page, "confirm_close_checkbox")
    assert page.confirm_close_checkbox.text() == "Confirm before closing the app"

    # Toggle off
    page.confirm_close_checkbox.setChecked(False)
    assert get_confirm_close_setting() is False

    # Toggle on
    page.confirm_close_checkbox.setChecked(True)
    assert get_confirm_close_setting() is True


def test_main_window_close_event_handling(qapp, monkeypatch):
    from desktop.app.ui.main_window import MainWindow
    from PySide6.QtWidgets import QWidget

    mock_client = MagicMock()
    mock_client.auth.get_user.return_value = MagicMock(user=MagicMock(email="admin@test.dz", id="1"))
    mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data={"role": "admin"}
    )

    dummy_page = lambda *args, **kwargs: QWidget()
    monkeypatch.setattr("desktop.app.ui.main_window.LiveSyncWorker.start", lambda self: None)

    with patch("desktop.app.ui.main_window.resolve_role", return_value="admin"), \
         patch("desktop.app.ui.main_window.remember_role"), \
         patch("desktop.app.ui.main_window.OverviewPage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.PendingPage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.ResidentsPage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.RoomsPage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.MaintenancePage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.RoomChangesPage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.OfficialListPage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.StaffAccountsPage", side_effect=dummy_page), \
         patch("desktop.app.ui.main_window.SettingsPage", side_effect=dummy_page):

        win = MainWindow(mock_client)
        win.show()
        qapp.processEvents()

        # 1. User cancels close dialog: event ignored
        with patch("desktop.app.ui.main_window.CloseConfirmDialog.exec", return_value=QDialog.DialogCode.Rejected):
            event = QCloseEvent()
            win.closeEvent(event)
            assert not event.isAccepted()
            assert not win._shutdown_confirmed

        # 2. User confirms close dialog: workers shut down and close accepted
        with patch("desktop.app.ui.main_window.CloseConfirmDialog.exec", return_value=QDialog.DialogCode.Accepted), \
             patch.object(win, "_shutdown_workers", return_value=True), \
             patch.object(win, "_workers_running", return_value=False):
            event = QCloseEvent()
            win.closeEvent(event)
            assert event.isAccepted()
            assert win._shutdown_confirmed

        # 3. request_quit calls close
        with patch.object(win, "close") as mock_close:
            win.request_quit()
            assert mock_close.called

        win.hide()
