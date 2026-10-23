"""Tests for C2 and C3: Segmented filter order, default selection, All view, and live sync preservation."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from desktop.app.ui.pages.maintenance import MaintenancePage
from desktop.app.ui.pages.pending import PendingPage
from desktop.app.ui.pages.room_changes import RoomChangesPage

_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


class FakeQuery:
    def __init__(self, data=None):
        self._data = data or []

    def select(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self._data)


class FakeClient:
    def __init__(self, maintenance_rows=None, pending_rows=None, room_change_rows=None):
        self._maintenance_rows = maintenance_rows or []
        self._pending_rows = pending_rows or []
        self._room_change_rows = room_change_rows or []

    def table(self, name):
        if name == "maintenance_reports":
            return FakeQuery(self._maintenance_rows)
        if name == "students":
            return FakeQuery(self._pending_rows)
        if name == "room_change_requests":
            return FakeQuery(self._room_change_rows)
        if name in ("rooms", "official_admissions", "profiles"):
            return FakeQuery([])
        return FakeQuery([])


def test_filter_bars_exact_order_on_all_three_pages():
    client = FakeClient()
    m_page = MaintenancePage(client)
    r_page = RoomChangesPage(client)
    p_page = PendingPage(client)

    # C2: Maintenance page: All - Pending - In progress - Resolved
    assert list(m_page.segments.buttons.keys()) == ["all", "pending", "in_progress", "resolved"]

    # C3: Room changes page: All - Pending - Approved - Rejected
    assert list(r_page.segments.buttons.keys()) == ["all", "pending", "approved", "rejected"]

    # C3: Pending accounts page: All - Pending - Approved - Rejected
    assert list(p_page.segments.buttons.keys()) == ["all", "pending", "approved", "rejected"]


def test_filter_bars_default_selection_is_pending():
    client = FakeClient()
    m_page = MaintenancePage(client)
    r_page = RoomChangesPage(client)
    p_page = PendingPage(client)

    assert m_page.filter_mode == "pending"
    assert m_page.btn_pending.isChecked()
    assert not m_page.btn_all.isChecked()

    assert r_page.filter_mode == "pending"
    assert r_page.btn_pending.isChecked()
    assert not r_page.btn_all.isChecked()

    assert p_page.filter_mode == "pending"
    assert p_page.btn_pending.isChecked()
    assert not p_page.btn_all.isChecked()


def test_room_changes_all_filter_and_rejection_reason():
    rows = [
        {
            "id": "rc-1",
            "student_id": "s-1",
            "current_room_id": "r-1",
            "target_room_id": "r-2",
            "status": "pending",
            "reason": "Quiet study required",
            "created_at": "2026-10-20T10:00:00Z",
            "students": {"first_name": "Karim", "last_name": "A", "card_id": "1001"},
            "from_room": {"block": "A", "number": "101"},
            "to_room": {"block": "B", "number": "202"},
        },
        {
            "id": "rc-2",
            "student_id": "s-2",
            "current_room_id": "r-3",
            "target_room_id": "r-4",
            "status": "approved",
            "reason": "Closer to faculty",
            "created_at": "2026-10-21T10:00:00Z",
            "students": {"first_name": "Fatima", "last_name": "B", "card_id": "1002"},
            "from_room": {"block": "A", "number": "103"},
            "to_room": {"block": "C", "number": "301"},
        },
        {
            "id": "rc-3",
            "student_id": "s-3",
            "current_room_id": "r-5",
            "target_room_id": "r-6",
            "status": "rejected",
            "reason": "Wants ground floor",
            "decision_note": "No ground floor rooms available for male students",
            "decided_at": "2026-10-22T10:00:00Z",
            "created_at": "2026-10-22T08:00:00Z",
            "students": {"first_name": "Bilal", "last_name": "C", "card_id": "1003"},
            "from_room": {"block": "B", "number": "205"},
            "to_room": {"block": "B", "number": "102"},
        },
    ]
    client = FakeClient(room_change_rows=rows)
    page = RoomChangesPage(client)

    # Default is pending -> only rc-1 visible
    assert page.filter_mode == "pending"
    assert not page.table.isRowHidden(0)
    assert page.table.isRowHidden(1)
    assert page.table.isRowHidden(2)

    # Click 'All' -> all 3 rows visible
    page.btn_all.click()
    assert page.filter_mode == "all"
    assert not page.table.isRowHidden(0)
    assert not page.table.isRowHidden(1)
    assert not page.table.isRowHidden(2)

    # Select the rejected row in 'All' view -> rejection reason card is visible and displays decision note
    page.table.selectRow(2)
    assert not page.rejection_card.isHidden()
    assert "No ground floor rooms available" in page.rejection_body.text()

    # Search works in 'All' view
    page.search.set_text("Bilal")
    page.filter_table()
    assert page.table.isRowHidden(0)
    assert page.table.isRowHidden(1)
    assert not page.table.isRowHidden(2)

    # LiveSync preserves 'All' filter and search
    page.apply_live_data(rows)
    assert page.filter_mode == "all"
    assert page.search.text() == "Bilal"
    assert not page.table.isRowHidden(2)


def test_pending_applications_all_filter():
    students = [
        {"id": "p-1", "card_id": "20240001", "first_name": "Amina", "last_name": "D", "university": "Tlemcen", "status": "pending"},
        {"id": "p-2", "card_id": "20240002", "first_name": "Yacine", "last_name": "E", "university": "Oran", "status": "active"},
        {"id": "p-3", "card_id": "20240003", "first_name": "Samir", "last_name": "F", "university": "Algiers", "status": "rejected", "rejection_reason": "Ineligible"},
    ]
    client = FakeClient(pending_rows=students)
    page = PendingPage(client)

    # Default is pending -> 1 row visible
    assert page.filter_mode == "pending"
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "20240001"

    # Switch to 'All' -> all 3 students shown
    page.btn_all.click()
    assert page.filter_mode == "all"
    assert page.table.rowCount() == 3

    # Counts
    assert "3" in page.btn_all.text()
    assert "1" in page.btn_pending.text()
    assert "1" in page.btn_approved.text()
    assert "1" in page.btn_rejected.text()

    # Search works in 'All' (PendingPage filters by rebuilding table)
    page.search.set_text("Amina")
    page.apply_filter()
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "20240001"
