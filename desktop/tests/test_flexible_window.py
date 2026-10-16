import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QWidget
from desktop.app.ui.main_window import MainWindow
from desktop.app.ui.login_window import LoginWindow
from desktop.app.ui.pages.maintenance import MaintenancePage
from desktop.app.ui.pages.pending import PendingPage
from desktop.app.ui.pages.room_changes import RoomChangesPage
from desktop.app.ui.pages.staff_accounts import StaffAccountsPage


_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


@pytest.fixture
def qapp():
    return _qapp


def test_window_minimum_sizes(qapp, monkeypatch):
    monkeypatch.setattr("desktop.app.ui.main_window.current_role", lambda c: "admin")
    monkeypatch.setattr("desktop.app.ui.main_window.LiveSyncWorker.start", lambda self: None)
    monkeypatch.setattr("desktop.app.ui.pages.settings.McpHealthWorker.start", lambda self: None)
    for p in [
        "OverviewPage", "PendingPage", "ResidentsPage", "RoomsPage",
        "MaintenancePage", "RoomChangesPage", "OfficialListPage",
        "StaffAccountsPage", "SettingsPage",
    ]:
        monkeypatch.setattr(f"desktop.app.ui.main_window.{p}", lambda client: QWidget())

    mw = MainWindow(object())
    assert mw.minimumSize().width() == 980
    assert mw.minimumSize().height() == 640
    mw.close()
    _qapp.processEvents()

    lw = LoginWindow()
    assert lw.minimumSize().width() == 380
    assert lw.minimumSize().height() == 480
    lw.close()
    _qapp.processEvents()


def test_page_panel_min_max_widths(qapp, monkeypatch):
    # Mock reload to prevent network calls and warning dialogs
    monkeypatch.setattr(MaintenancePage, "reload", lambda self: None)
    monkeypatch.setattr(PendingPage, "reload", lambda self: None)
    monkeypatch.setattr(RoomChangesPage, "reload", lambda self: None)
    monkeypatch.setattr(StaffAccountsPage, "reload", lambda self: None)

    client = object()

    # Maintenance inspector: min 360 / max 520
    m_page = MaintenancePage(client)
    m_inspector = m_page.detail_text.parentWidget()
    assert m_inspector.minimumWidth() == 360
    assert m_inspector.maximumWidth() == 520
    m_page.close()

    # Pending detail: min 340 / max 460
    p_page = PendingPage(client)
    p_detail = p_page.detail_text.parentWidget()
    assert p_detail.minimumWidth() == 340
    assert p_detail.maximumWidth() == 460
    p_page.close()

    # Room changes detail: min 340 / max 480
    rc_page = RoomChangesPage(client)
    rc_detail = rc_page.detail_text.parentWidget()
    assert rc_detail.minimumWidth() == 340
    assert rc_detail.maximumWidth() == 480
    rc_page.close()

    # Staff accounts form: min 340 / max 460
    s_page = StaffAccountsPage(client)
    card = s_page.full_name.parentWidget()
    while card and not isinstance(card, QFrame):
        card = card.parentWidget()
    assert card is not None
    assert card.minimumWidth() == 340
    assert card.maximumWidth() == 460
    s_page.close()

    _qapp.processEvents()
