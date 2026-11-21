"""Offscreen visual screenshot capture for Ticket Inspector, Transfer Inspector,
and Student Profile Dialog (both complete and sparse student records).

Generates PNG proof files saved into docs/screenshots/inspectors/.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication

from desktop.app.ui.infocard import StudentInfoCardDialog
from desktop.app.ui.pages.maintenance import MaintenancePage
from desktop.app.ui.pages.room_changes import RoomChangesPage


SCREENSHOT_DIR = Path("docs/screenshots/inspectors")


@pytest.fixture(autouse=True)
def ensure_screenshot_dir():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def test_capture_ticket_inspector_screenshot(qapp):
    client = MagicMock()
    page = MaintenancePage(client)
    page.resize(1100, 700)

    ticket = {
        "id": "d0000000-0000-0000-0000-000000000001",
        "category": "plumbing",
        "status": "pending",
        "description": "Continuous water leaking from the cold water valve under the bathroom sink basin. Needs washer replacement.",
        "created_at": "2026-11-12T10:15:30Z",
        "updated_at": "2026-11-12T11:45:00Z",
        "resolved_at": None,
        "staff_note": None,
        "photo_path": None,
        "students": {
            "id": "c0000000-0000-0000-0000-000000000001",
            "card_id": "90000001",
            "first_name": "Karim",
            "last_name": "Benali",
        },
        "rooms": {
            "block": "A",
            "floor": 1,
            "number": "101",
        },
    }
    page.apply_live_data([ticket])
    page.table.selectRow(0)
    qapp.processEvents()

    inspector = page.panel
    inspector.resize(420, 680)
    qapp.processEvents()

    pixmap = inspector.grab()
    out_path = SCREENSHOT_DIR / "ticket_inspector.png"
    pixmap.save(str(out_path), "PNG")
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_capture_transfer_inspector_screenshot(qapp):
    client = MagicMock()
    page = RoomChangesPage(client)
    page.resize(1100, 700)

    request = {
        "id": "e0000000-0000-0000-0000-000000000001",
        "status": "pending",
        "reason": "Requesting room transfer to Block B to share accommodation with study partner from the same academic faculty.",
        "created_at": "2026-11-12T14:20:00Z",
        "updated_at": "2026-11-12T14:20:00Z",
        "decision_note": None,
        "decided_by": None,
        "decided_at": None,
        "students": {
            "id": "c0000000-0000-0000-0000-000000000001",
            "card_id": "90000001",
            "first_name": "Karim",
            "last_name": "Benali",
        },
        "current_room": {
            "block": "A",
            "floor": 1,
            "number": "101",
            "capacity": 2,
        },
        "preferred_room": {
            "block": "B",
            "floor": 2,
            "number": "204",
            "capacity": 2,
        },
    }
    page.apply_live_data([request])
    page.table.selectRow(0)
    qapp.processEvents()

    inspector = page.panel
    inspector.resize(420, 680)
    qapp.processEvents()

    pixmap = inspector.grab()
    out_path = SCREENSHOT_DIR / "transfer_inspector.png"
    pixmap.save(str(out_path), "PNG")
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_capture_student_profile_complete_screenshot(qapp):
    complete_student = {
        "id": "11111111-1111-1111-1111-111111111111",
        "card_id": "90000001",
        "first_name": "Karim",
        "last_name": "Benali",
        "gender": "male",
        "birth_date": "2003-05-14",
        "university": "Université Abou Bekr Belkaïd",
        "faculty": "Faculté des Sciences",
        "study_level": "Master 1",
        "wilaya": "Oran",
        "phone": "0550112233",
        "email": "karim.benali@univ-tlemcen.dz",
        "status": "active",
        "created_at": "2026-09-01T10:00:00Z",
        "reviewed_by": "22222222-2222-2222-2222-222222222222",
        "reviewed_at": "2026-09-05T14:30:00Z",
        "staff": {
            "full_name": "Nadia Haddad",
            "position": "Housing Officer",
        },
        "rooms": {
            "id": "room-101",
            "block": "A",
            "floor": 1,
            "number": "101",
            "capacity": 2,
        },
    }
    dlg = StudentInfoCardDialog(
        None,
        complete_student,
        official_roster_data={"card_id": "90000001", "first_name": "Karim", "last_name": "Benali", "gender": "male"},
        residence_gender=None,
    )
    dlg.resize(620, 680)
    qapp.processEvents()

    pixmap = dlg.grab()
    out_path = SCREENSHOT_DIR / "student_profile_complete.png"
    pixmap.save(str(out_path), "PNG")
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_capture_student_profile_sparse_screenshot(qapp):
    sparse_student = {
        "id": "33333333-3333-3333-3333-333333333333",
        "card_id": "90000007",
        "first_name": "Test",
        "last_name": "Student 7",
        "gender": None,
        "birth_date": None,
        "university": "",
        "faculty": None,
        "study_level": None,
        "wilaya": None,
        "phone": None,
        "email": None,
        "status": "active",
        "created_at": "2026-11-12T22:28:37Z",
        "reviewed_by": None,
        "reviewed_at": None,
        "rooms": None,
    }
    dlg = StudentInfoCardDialog(
        None,
        sparse_student,
        official_roster_data=None,
        residence_gender=None,
    )
    dlg.resize(620, 680)
    qapp.processEvents()

    pixmap = dlg.grab()
    out_path = SCREENSHOT_DIR / "student_profile_sparse.png"
    pixmap.save(str(out_path), "PNG")
    assert out_path.exists()
    assert out_path.stat().st_size > 0
