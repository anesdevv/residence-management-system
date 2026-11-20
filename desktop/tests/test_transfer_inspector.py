"""Tests for Transfer Inspector (Phase 3: Room Changes): ordering, formatting, enrichment, empty states, copy summary."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QGuiApplication
import pytest

from desktop.app.ui.pages.room_changes import (
    RoomChangesPage,
    _format_dt,
    _format_room_text,
    _format_room_summary,
)
from desktop.i18n import init as init_i18n, t


@pytest.fixture(autouse=True)
def setup_i18n():
    init_i18n("en")


@pytest.fixture(autouse=True)
def _drain_tasks(qapp):
    """Never let a background worker outlive a test."""
    yield
    QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()


def test_format_room_text_formatting():
    # Case 1: Room with block, floor, number
    room = {"block": "A", "floor": 1, "number": "104"}
    val, meta, is_empty = _format_room_text(room, is_target=False)
    assert val == "Block A · Room 104"
    assert "Floor 1" in meta
    assert is_empty is False

    # Case 2: Room without floor
    room = {"block": "B", "floor": None, "number": "205"}
    val, meta, is_empty = _format_room_text(room, is_target=True)
    assert val == "Block B · Room 205"
    assert is_empty is False

    # Case 3: Target room with None (no preference)
    val, meta, is_empty = _format_room_text(None, is_target=True)
    assert val == "No preference"
    assert is_empty is True

    # Case 4: Current room with None (no room assigned)
    val, meta, is_empty = _format_room_text(None, is_target=False)
    assert val == "No room assigned"
    assert is_empty is True


def test_format_room_summary():
    room = {"block": "A", "floor": 1, "number": "104"}
    summary = _format_room_summary(room, is_target=False)
    assert summary == "Block A · Floor 1 · Room 104"

    # Fallback to room_id if room object is None
    summary_id = _format_room_summary(None, is_target=False, room_id="room-uuid-1234")
    assert summary_id == "Room ID: room-uuid-1234"

    # No preference
    summary_pref = _format_room_summary(None, is_target=True)
    assert summary_pref == "No preference"


def test_format_dt_strips_iso_and_microseconds():
    raw_ts = "2026-11-12 22:28:37.75375+00:00"
    formatted = _format_dt(raw_ts)
    assert "+00:00" not in formatted
    assert "75375" not in formatted
    assert "2026" in formatted
    assert "22:28" in formatted


def test_transfer_inspector_layout_and_elements(qapp):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "rcr-101",
            "student_id": "s-101",
            "current_room_id": "r-1",
            "preferred_room_id": "r-2",
            "reason": "Requesting relocation closer to the computer science lab.",
            "status": "pending",
            "decision_note": None,
            "decided_by": None,
            "decided_at": None,
            "created_at": "2026-11-12 22:28:37.75375+00:00",
            "updated_at": "2026-11-13 22:28:37.75375+00:00",
            "students": {
                "first_name": "Test",
                "last_name": "Student 7",
                "card_id": "90000007",
                "gender": "male",
            },
            "staff": None,
        }
    ]

    page = RoomChangesPage(mock_client)
    page.table.selectRow(0)

    # 1. Identity block with status pill and View Profile button
    assert page.name_label.text() == "Test Student 7"
    assert "90000007" in page.meta_label.text()
    assert page.status_pill.text() == "Pending"
    assert hasattr(page, "view_profile_btn")
    assert page.view_profile_btn.text() == "View profile"

    # 2. Current room and Requested room cards
    assert hasattr(page, "current_card")
    assert hasattr(page, "target_card")
    assert hasattr(page, "target_bar")

    # 3. Reason block
    assert hasattr(page, "motive_block")
    assert "Requesting relocation closer" in page.motive_block.body.text()
    assert bool(page.motive_block.body.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse)

    # 4. Key facts
    facts_rows = page.facts._rows
    assert len(facts_rows) >= 3  # Submitted, Last update, Decision note
    labels = [r.name_label.text() for r in facts_rows]
    assert "Submitted" in labels
    assert "Last update" in labels
    assert "Decision note" in labels

    # 5. Status actions
    assert page.approve_btn.isEnabled()
    assert page.reject_btn.isEnabled()
    assert page.delete_btn.isEnabled()
    assert page.copy_summary_btn.isEnabled()


def test_transfer_inspector_rejected_view_shows_rejection_card(qapp):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "rcr-202",
            "student_id": "s-202",
            "current_room_id": "r-1",
            "preferred_room_id": "r-2",
            "reason": "Need a quieter room",
            "status": "rejected",
            "decision_note": "Capacity exceeded in target dormitory block.",
            "decided_by": "staff-1",
            "decided_at": "2026-11-13T10:00:00Z",
            "created_at": "2026-11-12T08:00:00Z",
            "updated_at": "2026-11-13T10:00:00Z",
            "students": {
                "first_name": "Karim",
                "last_name": "Belkacem",
                "card_id": "202437010088",
            },
            "staff": {"full_name": "Admin Director"},
        }
    ]

    page = RoomChangesPage(mock_client)
    page.set_filter("rejected")
    page.table.selectRow(0)

    # Rejection card should be visible (not hidden)
    assert page.rejection_card.isHidden() is False
    assert "Capacity exceeded in target dormitory block." in page.rejection_body.text()
    assert "Admin Director" in page.rejection_meta.text()
    assert "Karim Belkacem" in page.rejection_student_label.text()
    assert "Need a quieter room" in page.rejection_motive_label.text()

    # Processed requests cannot be decided again
    assert not page.approve_btn.isEnabled()
    assert not page.reject_btn.isEnabled()
    assert page.delete_btn.isEnabled()


def test_transfer_inspector_copy_summary(qapp):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "rcr-303",
            "student_id": "s-303",
            "current_room_id": None,
            "preferred_room_id": None,
            "reason": "Change room please",
            "status": "pending",
            "decision_note": None,
            "decided_by": None,
            "decided_at": None,
            "created_at": "2026-11-12T08:00:00Z",
            "updated_at": "2026-11-12T08:00:00Z",
            "students": {
                "first_name": "Sarah",
                "last_name": "Lounis",
                "card_id": "202437010099",
            },
        }
    ]

    page = RoomChangesPage(mock_client)
    page.table.selectRow(0)

    summary = page._build_copy_summary(page.selected())
    assert "RESIDENT: Sarah Lounis (Card ID: 202437010099)" in summary
    assert "STATUS: Pending" in summary
    assert "CURRENT ROOM: No room assigned" in summary
    assert "REQUESTED ROOM: No preference" in summary
    assert "REASON: Change room please" in summary

    # Copy to clipboard
    page.on_copy_summary()
    clipboard_text = QGuiApplication.clipboard().text()
    assert clipboard_text == summary


def test_transfer_inspector_detail_enrichment(qapp):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "rcr-404",
            "student_id": "s-404",
            "current_room_id": "r-1",
            "preferred_room_id": "r-2",
            "reason": "Ground floor requested",
            "status": "pending",
            "created_at": "2026-11-12T08:00:00Z",
            "updated_at": "2026-11-12T08:00:00Z",
            "students": {
                "first_name": "Nabil",
                "last_name": "Amrani",
                "card_id": "202437010055",
            },
        }
    ]

    detail_data = {
        "id": "rcr-404",
        "current_room": {"id": "r-1", "block": "A", "floor": 2, "number": "201"},
        "preferred_room": {"id": "r-2", "block": "B", "floor": 0, "number": "002", "capacity": 2, "occupied": 1},
    }

    with patch("desktop.app.ui.pages.room_changes.get_room_change_detail", return_value=detail_data):
        page = RoomChangesPage(mock_client)
        page.table.selectRow(0)

        # Let the task runner process
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and "Block B" not in page.target_value.text():
            qapp.processEvents()
            time.sleep(0.02)

        # After detail is loaded, current room and requested room are updated with block and room
        assert "Block A · Room 201" in page.current_value.text()
        assert "Floor 2" in page.current_meta.text()
        assert "Block B · Room 002" in page.target_value.text()
        assert "Floor 0" in page.target_meta.text()
        assert page.target_bar.isHidden() is False
        assert page.target_bar._occupied == 1
        assert page.target_bar._capacity == 2
        page.close()
