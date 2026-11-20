"""Tests for Ticket Inspector (Phase 2): ordering, formatting, enrichment, empty states, copy summary."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
import pytest

from desktop.app.ui.pages.maintenance import MaintenancePage, _room_label, _format_dt
from desktop.i18n import init as init_i18n, t


@pytest.fixture(autouse=True)
def setup_i18n():
    init_i18n("en")


def test_room_label_formatting():
    # Case 1: Room with block, floor, number
    row = {"rooms": {"block": "A", "floor": 2, "number": "204"}}
    st = {}
    label, is_empty = _room_label(row, st)
    assert label == "Block A · Floor 2 · Room 204"
    assert is_empty is False

    # Case 2: Room without floor
    row = {"rooms": {"block": "B", "floor": None, "number": "101"}}
    label, is_empty = _room_label(row, st)
    assert label == "Block B · Room 101"
    assert is_empty is False

    # Case 3: Student has room embed
    row = {}
    st = {"rooms": {"block": "C", "floor": 1, "number": "12"}}
    label, is_empty = _room_label(row, st)
    assert label == "Block C · Floor 1 · Room 12"
    assert is_empty is False

    # Case 4: No room assigned
    row = {}
    st = {"room_id": None}
    label, is_empty = _room_label(row, st)
    assert label == "Resident has no room assigned"
    assert is_empty is True


def test_format_dt_strips_iso_and_microseconds():
    raw_ts = "2026-11-12 22:28:37.75375+00:00"
    formatted = _format_dt(raw_ts)
    assert "+00:00" not in formatted
    assert "75375" not in formatted
    assert "2026" in formatted
    assert "22:28" in formatted


def test_ticket_inspector_widget_order_and_elements(qapp):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "t-1",
            "student_id": "s-1",
            "category": "plumbing",
            "description": "Leaky faucet in bathroom sink.",
            "photo_path": None,
            "status": "pending",
            "staff_note": "Awaiting plumber dispatch.",
            "created_at": "2026-11-12 22:28:37.75375+00:00",
            "updated_at": "2026-11-13 22:28:37.75375+00:00",
            "students": {
                "first_name": "Test",
                "last_name": "Student 7",
                "card_id": "90000007",
            },
        }
    ]

    page = MaintenancePage(mock_client)
    page.table.selectRow(0)

    # 1. Header
    assert page.category_label.text() == "Plumbing"
    assert page.status_pill.text() == "Pending"

    # 2. Resident identity with "View profile" button
    assert page.name_label.text() == "Test Student 7"
    assert page.card_label.text() == "Card ID 90000007"
    assert hasattr(page, "view_profile_btn")
    assert page.view_profile_btn.text() == "View profile"

    # 3. Description block
    assert hasattr(page, "desc_block")
    assert "Leaky faucet in bathroom sink." in page.desc_block.body.text()
    assert bool(page.desc_block.body.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse)

    # 4. Key facts
    facts_rows = page.facts._rows
    assert len(facts_rows) == 4
    labels = [r.name_label.text() for r in facts_rows]
    assert labels == ["Room", "Submitted", "Last update", "Resolved"]

    # Room starts as loading/no-room-assigned before detail enrich
    room_val = facts_rows[0].val_label.text()
    assert room_val in ("Resident has no room assigned", "Loading details...")

    # Submitted & Last update do not contain microseconds or +00:00
    sub_val = facts_rows[1].val_label.text()
    assert "+00:00" not in sub_val
    assert "2026" in sub_val

    # Resolved says "Not resolved yet" for pending ticket
    res_val = facts_rows[3].val_label.text()
    assert res_val == "Not resolved yet"
    assert facts_rows[3].val_label.property("role") == "muted" or "italic" in facts_rows[3].val_label.styleSheet()

    # 5. Fault photo
    assert page.photo_label.text() == "No photo attached by resident"

    # 6. Staff note
    assert "Awaiting plumber dispatch." in page.note_block.body.text()

    # 7. Stepper and action buttons
    assert hasattr(page, "stepper")
    assert page.in_progress_btn.isEnabled()
    assert page.resolved_btn.isEnabled()
    assert page.delete_btn.isEnabled()

    # 8. Copy summary button
    assert hasattr(page, "copy_summary_btn")
    assert page.copy_summary_btn.isEnabled()

    page.close()


def test_copy_summary_button_action(qapp):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "t-1",
            "student_id": "s-1",
            "category": "plumbing",
            "description": "Pipe leaking water.",
            "photo_path": None,
            "status": "pending",
            "staff_note": None,
            "created_at": "2026-11-12 22:28:37.75375+00:00",
            "updated_at": "2026-11-13 22:28:37.75375+00:00",
            "students": {
                "first_name": "Karim",
                "last_name": "Benali",
                "card_id": "202338012345",
            },
        }
    ]

    page = MaintenancePage(mock_client)
    page.table.selectRow(0)

    summary = page._build_copy_summary(page.selected())
    assert "CATEGORY: Plumbing" in summary
    assert "Resident: Karim Benali (Card ID: 202338012345)" in summary
    assert "Status: Pending" in summary
    assert "Pipe leaking water." in summary
    assert "+00:00" not in summary

    # Trigger click
    page.copy_summary_btn.click()
    clipboard = QGuiApplication.clipboard()
    if clipboard:
        assert clipboard.text() == summary

    page.close()


def test_detail_enrichment_updates_room_and_facts(qapp):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "t-1",
            "student_id": "s-1",
            "category": "electricity",
            "description": "Short circuit",
            "photo_path": None,
            "status": "pending",
            "staff_note": None,
            "created_at": "2026-11-12 22:28:37.75375+00:00",
            "updated_at": "2026-11-13 22:28:37.75375+00:00",
            "students": {
                "first_name": "Test",
                "last_name": "Student",
                "card_id": "90000007",
            },
        }
    ]

    detail_payload = {
        "id": "t-1",
        "student_id": "s-1",
        "category": "electricity",
        "description": "Short circuit in power socket",
        "photo_path": None,
        "status": "pending",
        "staff_note": "Electrician scheduled",
        "created_at": "2026-11-12 22:28:37.75375+00:00",
        "updated_at": "2026-11-13 22:28:37.75375+00:00",
        "students": {
            "id": "s-1",
            "card_id": "90000007",
            "first_name": "Test",
            "last_name": "Student",
            "rooms": {
                "id": "r-1",
                "block": "A",
                "floor": 2,
                "number": "204",
                "capacity": 2,
            },
        },
        "room": {
            "id": "r-1",
            "block": "A",
            "floor": 2,
            "number": "204",
            "capacity": 2,
        },
        "staff": None,
    }

    with patch("desktop.app.ui.pages.maintenance.get_ticket_detail", return_value=detail_payload):
        page = MaintenancePage(mock_client)
        page.table.selectRow(0)

        # Wait for TaskRunner background job
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            qapp.processEvents()
            room_text = page.facts._rows[0].val_label.text()
            if "Block A · Floor 2 · Room 204" in room_text:
                break
            time.sleep(0.02)

        assert page.facts._rows[0].val_label.text() == "Block A · Floor 2 · Room 204"
        assert "Short circuit in power socket" in page.desc_block.body.text()
        assert "Electrician scheduled" in page.note_block.body.text()

        page.close()


def test_double_click_and_view_profile_open_student_card(qapp):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "t-1",
            "student_id": "s-1",
            "category": "plumbing",
            "description": "Tap issue",
            "photo_path": None,
            "status": "pending",
            "staff_note": None,
            "created_at": "2026-11-12 22:28:37.75375+00:00",
            "updated_at": "2026-11-13 22:28:37.75375+00:00",
            "students": {
                "first_name": "Test",
                "last_name": "Student 7",
                "card_id": "90000007",
            },
        }
    ]

    opened_students = []

    def mock_show_student_card(student, roster):
        opened_students.append(student)

    with patch.object(MaintenancePage, "_show_student_card", side_effect=mock_show_student_card), \
         patch("desktop.app.ui.pages.maintenance.official_lookup", return_value={"90000007": {}}):
        page = MaintenancePage(mock_client)
        page.table.selectRow(0)

        # Click "View profile" button
        page.view_profile_btn.click()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not opened_students:
            qapp.processEvents()
            time.sleep(0.02)
        assert len(opened_students) == 1
        assert opened_students[0]["card_id"] == "90000007"

        # Double click row
        page.on_row_double_clicked(0, 0)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and len(opened_students) < 2:
            qapp.processEvents()
            time.sleep(0.02)
        assert len(opened_students) == 2

        page.close()
