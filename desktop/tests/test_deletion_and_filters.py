from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication
import pytest

from desktop.app.importers.official_list import read_official_file
from desktop.app.ui.pages.pending import PendingPage
from desktop.app.ui.pages.room_changes import RoomChangesPage
from desktop.app.ui.pages.maintenance import MaintenancePage
from desktop.app.ui.pages.staff_accounts import StaffAccountsPage


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_official_roster_csv_importable():
    records = read_official_file("official_students_roster.csv")
    assert len(records) == 40
    for r in records:
        assert r["card_id"].startswith("20243701")
        assert len(r["first_name"]) > 0
        assert len(r["last_name"]) > 0
        assert r["gender"] in ("male", "female")
        assert r["university"] == "Université Abou Bekr Belkaïd - Tlemcen"
        assert r["birth_date"] is not None


def test_pending_page_filters_and_deletion_rules(qapp):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "s-1",
            "card_id": "202437010001",
            "first_name": "Amine",
            "last_name": "Benali",
            "gender": "male",
            "status": "pending",
            "university": "Université Abou Bekr Belkaïd - Tlemcen",
            "faculty": "Faculté de Technologie",
            "birth_date": "2003-04-12",
            "phone": "0550123456",
            "email": "amine@test.dz",
            "study_level": "L3",
            "wilaya": "Tlemcen",
            "created_at": "2026-10-10T12:00:00Z",
        },
        {
            "id": "s-2",
            "card_id": "202437010002",
            "first_name": "Yasmine",
            "last_name": "Mansouri",
            "gender": "female",
            "status": "active",
            "university": "Université Abou Bekr Belkaïd - Tlemcen",
            "faculty": "Faculté de Médecine",
            "birth_date": "2004-09-25",
            "phone": "0550987654",
            "email": "yasmine@test.dz",
            "study_level": "M1",
            "wilaya": "Oran",
            "created_at": "2026-10-09T10:00:00Z",
        },
        {
            "id": "s-3",
            "card_id": "202437010003",
            "first_name": "Mohamed",
            "last_name": "Belkacem",
            "gender": "male",
            "status": "rejected",
            "rejection_reason": "Incomplete academic file: missing residence registration slip",
            "reviewed_at": "2026-10-12T14:30:00Z",
            "university": "Université Abou Bekr Belkaïd - Tlemcen",
            "faculty": "Faculté des Sciences",
            "birth_date": "2002-11-15",
            "phone": "0550555555",
            "email": "mohamed@test.dz",
            "study_level": "L2",
            "wilaya": "Tlemcen",
            "created_at": "2026-10-08T09:00:00Z",
        },
    ]

    with patch("desktop.app.ui.pages.pending.official_lookup", return_value={"202437010001": {"first_name": "Amine"}}):
        page = PendingPage(mock_client)

    # 1. Check filter buttons presence and default state
    assert hasattr(page, "btn_pending")
    assert hasattr(page, "btn_approved")
    assert hasattr(page, "btn_rejected")
    assert hasattr(page, "btn_all")
    assert page.btn_pending.isChecked()
    assert page.filter_mode == "pending"

    # Pending filter shows 1 record
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "202437010001"
    assert "Pending" in page.table.item(0, 3).text()

    # Selecting pending student: delete_btn MUST BE DISABLED
    page.table.selectRow(0)
    assert not page.delete_btn.isEnabled()
    assert "Pending applications cannot be deleted" in page.delete_btn.toolTip()
    assert page.approve_btn.isEnabled()

    # 2. Switch filter to Approved: shows s-2 (active)
    page.btn_approved.click()
    assert page.filter_mode == "approved"
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "202437010002"
    assert "Approved" in page.table.item(0, 3).text()

    # Selecting approved student: delete_btn MUST BE ENABLED; approve_btn disabled
    page.table.selectRow(0)
    assert page.delete_btn.isEnabled()
    assert not page.approve_btn.isEnabled()
    assert "already approved" in page.approve_btn.toolTip()

    # 3. Switch filter to Rejected: shows s-3 (rejected)
    page.btn_rejected.click()
    assert page.filter_mode == "rejected"
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "202437010003"
    assert "Rejected" in page.table.item(0, 3).text()

    # Selecting rejected student: delete_btn MUST BE ENABLED
    page.table.selectRow(0)
    assert page.delete_btn.isEnabled()
    assert page.approve_btn.isEnabled()
    assert page.reject_btn.text() == "Edit Rejection Reason"

    # Detail text must show rejection reason for desk inquiries
    detail_content = page.detail_text.toPlainText()
    assert "REJECTION REASON (Desk Inquiry Reference)" in detail_content
    assert "Incomplete academic file" in detail_content


def test_room_changes_deletion_button(qapp):
    mock_client = MagicMock()
    query_mock = MagicMock()
    query_mock.execute.return_value.data = [
        {
            "id": "rcr-1",
            "student_id": "st-1",
            "reason": "Quiet study environment",
            "status": "pending",
            "created_at": "2026-10-12T10:00:00Z",
            "students": {"first_name": "Walid", "last_name": "Khelifi"},
        }
    ]
    query_mock.order.return_value = query_mock
    query_mock.eq.return_value = query_mock
    mock_client.table.return_value.select.return_value = query_mock

    page = RoomChangesPage(mock_client)
    assert hasattr(page, "delete_btn")
    assert not page.delete_btn.isEnabled()

    page.table.selectRow(0)
    assert page.delete_btn.isEnabled()


def test_maintenance_deletion_button(qapp):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "maint-1",
            "student_id": "st-1",
            "category": "plumbing",
            "description": "Leaking sink tap in bathroom",
            "status": "pending",
            "created_at": "2026-10-12T10:00:00Z",
            "students": {"first_name": "Sarah", "last_name": "Saidi"},
        }
    ]

    page = MaintenancePage(mock_client)
    assert hasattr(page, "delete_btn")
    assert not page.delete_btn.isEnabled()

    page.table.selectRow(0)
    assert page.delete_btn.isEnabled()


def test_staff_accounts_self_deletion_protection(qapp):
    mock_client = MagicMock()
    # Mock current authenticated user ID
    mock_user = MagicMock()
    mock_user.id = "staff-admin-id"
    mock_user_resp = MagicMock()
    mock_user_resp.user = mock_user
    mock_client.auth.get_user.return_value = mock_user_resp

    # Mock admin-users invoke returning staff list
    mock_client.functions.invoke.return_value = [
        {"id": "staff-admin-id", "full_name": "Admin Officer", "position": "Head of Residence"},
        {"id": "staff-other-id", "full_name": "Reception Officer", "position": "Reception Desk"},
    ]

    page = StaffAccountsPage(mock_client)
    assert hasattr(page, "delete_btn")
    assert not page.delete_btn.isEnabled()

    # Select self: delete button must remain DISABLED with self-deletion tooltip
    page.table.selectRow(0)
    assert not page.delete_btn.isEnabled()
    assert "cannot delete your own" in page.delete_btn.toolTip()

    # Select other staff member: delete button must BECOME ENABLED
    page.table.selectRow(1)
    assert page.delete_btn.isEnabled()
    assert page.delete_btn.toolTip() == ""


def test_live_sync_preserves_pending_page_filters(qapp):
    mock_client = MagicMock()
    initial_students = [
        {
            "id": "s-1",
            "card_id": "202437010001",
            "first_name": "Amine",
            "last_name": "Benali",
            "gender": "male",
            "status": "pending",
            "created_at": "2026-10-10T12:00:00Z",
        },
        {
            "id": "s-2",
            "card_id": "202437010002",
            "first_name": "Yasmine",
            "last_name": "Mansouri",
            "gender": "female",
            "status": "active",
            "created_at": "2026-10-09T10:00:00Z",
        },
    ]
    mock_client.table.return_value.select.return_value.order.return_value.execute.return_value.data = initial_students

    with patch("desktop.app.ui.pages.pending.official_lookup", return_value={}):
        page = PendingPage(mock_client)

    # Switch to Approved tab
    page.btn_approved.click()
    assert page.filter_mode == "approved"
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "202437010002"

    # Simulate LiveSyncWorker tick emitting a new pending student
    incoming_pending = [
        {
            "id": "s-1",
            "card_id": "202437010001",
            "first_name": "Amine",
            "last_name": "Benali",
            "gender": "male",
            "status": "pending",
            "created_at": "2026-10-10T12:00:00Z",
        },
        {
            "id": "s-3",
            "card_id": "202437010003",
            "first_name": "Karim",
            "last_name": "Haddad",
            "gender": "male",
            "status": "pending",
            "created_at": "2026-10-16T20:00:00Z",
        },
    ]
    page.apply_live_data(incoming_pending)

    # Approved tab must NOT be wiped or clobbered
    assert page.filter_mode == "approved"
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "202437010002"

    # Switching back to Pending tab now shows both pending students (s-1 and s-3)
    page.btn_pending.click()
    assert page.filter_mode == "pending"
    assert page.table.rowCount() == 2

