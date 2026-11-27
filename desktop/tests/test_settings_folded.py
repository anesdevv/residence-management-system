"""Tests for folded, organized Settings sections and visual polish contracts."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from desktop.app.ui.components import CollapsibleCard
from desktop.app.ui.main_window import MainWindow
from desktop.app.ui.pages import settings as settings_mod
from desktop.app.ui.pages.settings import SettingsPage
from desktop.app.ui.updates_ui import UpdatesSection
from desktop.i18n import t
from desktop.updater.state import UpdateState


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_stub_update_service():
    from PySide6.QtCore import QObject, Signal

    class _StubService(QObject):
        state_changed = Signal(str, object)
        check_finished = Signal(object)
        progress_changed = Signal(int, int)
        download_cancelled = Signal()
        error_occurred = Signal(str, str)
        available_changed = Signal(bool)

        def __init__(self):
            super().__init__()
            self.state = UpdateState.IDLE
            self.release = None
            self.installer_path = None
            self.silent = False

        def is_busy(self):
            return False

        def is_skipped(self, _ver):
            return False

        def check(self, silent=False):
            pass

        def start_download(self):
            pass

        def cancel_download(self):
            pass

        def skip_current(self):
            pass

        def reset(self):
            pass

    return _StubService()


def _make_client():
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = {
        "writes_enabled": False,
        "residence_name": "Cité Universitaire · Tlemcen",
        "residence_gender": "male",
    }
    return client


def test_settings_sections_start_folded_and_open_on_click(qapp, monkeypatch):
    monkeypatch.setattr(settings_mod, "current_role", lambda _c: "admin")
    monkeypatch.setattr(settings_mod.McpHealthWorker, "start", lambda self: None)
    service = _make_stub_update_service()
    page = SettingsPage(_make_client(), role="admin", update_service=service)
    try:
        sections = [
            page.residence_card,
            page.general_card,
            page.notif_card,
            page.security_card,
            page.updates_section.card,
            page.dev_card,
            page.about_widget,
        ]
        for card in sections:
            assert isinstance(card, CollapsibleCard)
            assert card.is_expanded() is False
            assert card._body_container.isHidden() is True

        # Clicking header opens the section; clicking again folds it back
        page.general_card.header_btn.click()
        assert page.general_card.is_expanded() is True
        assert page.general_card._body_container.isHidden() is False

        page.general_card.header_btn.click()
        assert page.general_card.is_expanded() is False
        assert page.general_card._body_container.isHidden() is True
    finally:
        page.close()


def test_settings_open_section_and_live_summaries(qapp, monkeypatch):
    monkeypatch.setattr(settings_mod, "current_role", lambda _c: "admin")
    monkeypatch.setattr(settings_mod.McpHealthWorker, "start", lambda self: None)
    page = SettingsPage(_make_client(), role="admin")
    try:
        assert page.residence_card.is_expanded() is False
        page.open_section("residence")
        assert page.residence_card.is_expanded() is True

        # Notification summary tracks master toggle
        page.notif_master_cb.setChecked(False)
        assert page.notif_card._summary_label.text() == t("settings.summary_off")
        page.notif_master_cb.setChecked(True)
        assert t("settings.summary_on") in page.notif_card._summary_label.text()

        # Developer mode summary tracks toggle
        page.dev_checkbox.setChecked(True)
        assert page.dev_card._summary_label.text() == t("settings.summary_developer")
    finally:
        page.close()


def test_main_window_residence_banner_opens_folded_residence_section(qapp, monkeypatch):
    monkeypatch.setattr("desktop.app.ui.main_window.LiveSyncWorker.start", lambda self: None)
    monkeypatch.setattr("desktop.app.ui.pages.settings.McpHealthWorker.start", lambda self: None)
    mw = MainWindow(_make_client(), role="admin")
    try:
        mw.residence_settings_btn.click()
        assert mw.stack.currentWidget() is mw.settings_page
        assert mw.settings_page.residence_card.is_expanded() is True
        assert mw.settings_page.general_card.is_expanded() is False
    finally:
        mw._shutdown_workers(500)
        mw.close()


def test_standalone_updates_section_remains_unfolded(qapp):
    section = UpdatesSection(_make_stub_update_service())
    try:
        assert not isinstance(section.card, CollapsibleCard)
        assert section.check_button.isVisibleTo(section)
    finally:
        section.deleteLater()


def test_settings_responsive_full_width_and_two_column_on_fullscreen(qapp, monkeypatch):
    from PySide6.QtWidgets import QBoxLayout

    monkeypatch.setattr(settings_mod, "current_role", lambda _c: "admin")
    monkeypatch.setattr(settings_mod.McpHealthWorker, "start", lambda self: None)
    page = SettingsPage(_make_client(), role="admin", update_service=_make_stub_update_service())
    try:
        # Narrow/normal window: full-width single column
        page.resize(900, 640)
        page.show()
        qapp.processEvents()
        assert page._columns_layout.direction() == QBoxLayout.Direction.TopToBottom
        assert page._left_col.width() >= page.scroll_area.viewport().width() - 80

        # Full-screen / wide viewport: two balanced side-by-side columns filling the width
        page.resize(1670, 1020)
        qapp.processEvents()
        assert page._columns_layout.direction() == QBoxLayout.Direction.LeftToRight
        assert page._right_col.x() > page._left_col.x()
        assert page._right_col.geometry().right() >= page.scroll_area.viewport().width() - 80
    finally:
        page.close()
