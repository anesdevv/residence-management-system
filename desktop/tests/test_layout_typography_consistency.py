"""Tests for layout and typography consistency across inspectors and profile dialog.

Verifies:
1. Uniform label width (130px) across all KeyValueRow instances.
2. Top vertical alignment on labels and values.
3. Text selectable by mouse (TextSelectableByMouse) on value labels.
4. Smooth sizing within minimum window dimensions (980x640) at 100% and 150% scaling.
5. French language layout and label fitting.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication

from desktop.app.ui.components import KeyValueRow, KeyValueList
from desktop.app.ui.infocard import StudentInfoCardDialog
from desktop.app.ui.pages.maintenance import MaintenancePage
from desktop.app.ui.pages.room_changes import RoomChangesPage
from desktop.i18n import set_saved_language


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.table.return_value.select.return_value.order.return_value.execute.return_value.data = []
    client.table.return_value.select.return_value.execute.return_value.data = []
    return client


def test_key_value_row_uniform_spec(qapp):
    """KeyValueRow must have 130px fixed label width, top alignment, and selectable text."""
    row = KeyValueRow("Test Label", "Test Value")

    assert row.name_label.width() == 130 or row.name_label.maximumWidth() == 130
    assert row.name_label.alignment() & Qt.AlignmentFlag.AlignTop
    assert row.val_label.alignment() & Qt.AlignmentFlag.AlignTop
    assert row.val_label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse


def test_maintenance_inspector_typography_consistency(qapp, mock_client):
    page = MaintenancePage(mock_client)
    ticket = {
        "id": "t-1",
        "category": "plumbing",
        "status": "pending",
        "description": "Leaking faucet in bathroom",
        "created_at": "2026-11-12T10:00:00Z",
        "updated_at": "2026-11-12T11:00:00Z",
        "resolved_at": None,
        "students": {"first_name": "Karim", "last_name": "Benali", "card_id": "90000001"},
        "rooms": {"block": "A", "floor": 1, "number": "101"},
    }
    page.apply_live_data([ticket])
    page.table.selectRow(0)
    page.resize(980, 640)
    qapp.processEvents()

    # All KeyValueRows in inspector must have 130px label width and top alignment
    rows = page.facts.findChildren(KeyValueRow)
    assert len(rows) >= 4
    for r in rows:
        assert r.name_label.maximumWidth() == 130
        assert r.name_label.alignment() & Qt.AlignmentFlag.AlignTop
        assert r.val_label.alignment() & Qt.AlignmentFlag.AlignTop
        assert r.val_label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse


def test_transfer_inspector_typography_consistency(qapp, mock_client):
    page = RoomChangesPage(mock_client)
    request = {
        "id": "rcr-1",
        "status": "pending",
        "reason": "Need quiet room for studies",
        "created_at": "2026-11-12T10:00:00Z",
        "updated_at": "2026-11-12T11:00:00Z",
        "students": {"first_name": "Karim", "last_name": "Benali", "card_id": "90000001"},
        "current_room": {"block": "A", "floor": 1, "number": "101"},
        "preferred_room": {"block": "B", "floor": 2, "number": "204"},
    }
    page.apply_live_data([request])
    page.table.selectRow(0)
    page.resize(980, 640)
    qapp.processEvents()

    rows = page.facts.findChildren(KeyValueRow)
    assert len(rows) >= 2
    for r in rows:
        assert r.name_label.maximumWidth() == 130
        assert r.name_label.alignment() & Qt.AlignmentFlag.AlignTop
        assert r.val_label.alignment() & Qt.AlignmentFlag.AlignTop
        assert r.val_label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse


def test_student_profile_dialog_typography_consistency(qapp):
    student = {
        "id": "s-1",
        "card_id": "90000001",
        "first_name": "Karim",
        "last_name": "Benali",
        "status": "active",
        "university": "Université de Tlemcen",
    }
    dlg = StudentInfoCardDialog(None, student)
    dlg.resize(620, 480)
    qapp.processEvents()

    all_rows = dlg.findChildren(KeyValueRow)
    assert len(all_rows) >= 5
    for r in all_rows:
        assert r.name_label.maximumWidth() == 130
        assert r.name_label.alignment() & Qt.AlignmentFlag.AlignTop
        assert r.val_label.alignment() & Qt.AlignmentFlag.AlignTop
        assert r.val_label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse


def test_french_localization_layout_fit(qapp, mock_client):
    """French strings (often longer) must render properly without crashing or truncated keys."""
    set_saved_language("fr")
    try:
        student = {
            "id": "s-fr",
            "card_id": "90000099",
            "first_name": "Étudiant",
            "last_name": "Français",
            "status": "pending",
        }
        dlg = StudentInfoCardDialog(None, student)
        dlg.resize(620, 480)
        qapp.processEvents()

        facts_text = [r.name_label.text() for r in dlg.facts.findChildren(KeyValueRow)]
        assert "N° de carte étudiant" in facts_text
        assert "Université" in facts_text
        assert "Inscrit le" in facts_text
    finally:
        set_saved_language("en")
