"""Tests for the Student Profile Dialog (StudentInfoCardDialog).

Verifies full profile rendering, empty value formatting ('Not provided',
'No room assigned', 'Not reviewed yet'), single-gender mode hiding,
active-without-room warning pill and banner, roster cross-check states,
and off-thread detail enrichment with retry.
"""

from __future__ import annotations

import time
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from desktop.app.ui.infocard import StudentInfoCardDialog
from desktop.app.ui.components import KeyValueRow


def wait_until(qapp, predicate, timeout=4.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


@pytest.fixture
def sample_complete_student() -> dict:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "card_id": "90000001",
        "first_name": "Karim",
        "last_name": "Benali",
        "gender": "male",
        "birth_date": "2003-05-14",
        "university": "Université de Tlemcen",
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


@pytest.fixture
def sample_sparse_student() -> dict:
    return {
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


def _extract_fact_rows(dlg: StudentInfoCardDialog) -> dict[str, str]:
    """Helper to extract label -> value mapping from KeyValueList."""
    result = {}
    for row in dlg.facts.findChildren(KeyValueRow):
        result[row.name_label.text().strip()] = row.val_label.text().strip()
    return result


def test_complete_student_profile_rendering(qapp, sample_complete_student):
    dlg = StudentInfoCardDialog(
        None,
        sample_complete_student,
        official_roster_data={"card_id": "90000001", "first_name": "Karim", "last_name": "Benali", "gender": "male"},
        residence_gender=None,
    )
    facts = _extract_fact_rows(dlg)

    assert dlg.name_label.text() == "Karim Benali"
    assert "90000001" in facts["Student card ID"]
    assert facts["Full name"] == "Karim Benali"
    assert facts["Status"] == "Active resident"
    assert facts["Gender"] == "Male"
    assert "2003" in facts["Date of birth"]
    assert facts["University"] == "Université de Tlemcen"
    assert facts["Faculty"] == "Faculté des Sciences"
    assert facts["Study level"] == "Master 1"
    assert facts["Wilaya"] == "Oran"
    assert facts["Contact phone"] == "0550112233"
    assert facts["Contact email"] == "karim.benali@univ-tlemcen.dz"
    assert "Nadia Haddad" in facts["Review"]

    # Housing card
    housing_rows = {}
    for row in dlg.housing_facts.findChildren(KeyValueRow):
        housing_rows[row.name_label.text().strip()] = row.val_label.text().strip()
    assert "Block A" in housing_rows["Assigned room"]
    assert "101" in housing_rows["Assigned room"]
    assert dlg.no_room_banner.isHidden()

    # Roster match banner
    assert not dlg.roster_banner.isHidden()
    assert dlg.roster_banner._kind == "success"
    assert not dlg.active_no_room_pill.isVisible()


def test_sparse_student_displays_not_provided_no_dashes(qapp, sample_sparse_student):
    dlg = StudentInfoCardDialog(
        None,
        sample_sparse_student,
        official_roster_data=None,
        residence_gender=None,
    )
    facts = _extract_fact_rows(dlg)

    # Empty values must be specific strings, NEVER bare dashes
    for label, val in facts.items():
        assert val != "—", f"Fact row {label!r} displayed bare dash instead of specific string"

    assert facts["University"] == "Not provided"
    assert facts["Faculty"] == "Not provided"
    assert facts["Study level"] == "Not provided"
    assert facts["Wilaya"] == "Not provided"
    assert facts["Contact phone"] == "Not provided"
    assert facts["Contact email"] == "Not provided"
    assert facts["Date of birth"] == "Not provided"
    assert facts["Review"] == "Not reviewed yet"

    # Housing
    housing_rows = {}
    for row in dlg.housing_facts.findChildren(KeyValueRow):
        housing_rows[row.name_label.text().strip()] = row.val_label.text().strip()
    assert housing_rows["Assigned room"] == "No room assigned yet"


def test_active_resident_with_no_room_warning(qapp, sample_sparse_student):
    """An ACTIVE resident without an assigned room gets amber warnings."""
    dlg = StudentInfoCardDialog(
        None,
        sample_sparse_student,
        official_roster_data=None,
        residence_gender=None,
    )

    # Active with no room -> amber pill is visible
    assert not dlg.active_no_room_pill.isHidden()
    assert dlg.active_no_room_pill.text() == "Active but no room assigned: check the allocation"

    # Housing card shows warning banner
    assert not dlg.no_room_banner.isHidden()
    assert dlg.no_room_banner._kind == "warning"
    assert "Active but no room assigned" in dlg.no_room_banner._message.text()


def test_single_gender_mode_omits_gender_row(qapp, sample_complete_student):
    """In single-gender mode, the Gender row is hidden/omitted from the facts list."""
    # When single-gender is active
    dlg_single = StudentInfoCardDialog(
        None,
        sample_complete_student,
        official_roster_data=None,
        residence_gender="male",
    )
    facts_single = _extract_fact_rows(dlg_single)
    assert "Gender" not in facts_single

    # When co-ed / residence gender is unset
    dlg_coed = StudentInfoCardDialog(
        None,
        sample_complete_student,
        official_roster_data=None,
        residence_gender=None,
    )
    facts_coed = _extract_fact_rows(dlg_coed)
    assert "Gender" in facts_coed
    assert facts_coed["Gender"] == "Male"


def test_roster_match_pending_vs_active(qapp):
    """Cross-check admissions roster: pending gets danger banner, active gets neutral info."""
    pending_student = {
        "id": "s-pending",
        "card_id": "99990001",
        "first_name": "Samir",
        "last_name": "Test",
        "status": "pending",
    }
    active_student = {
        "id": "s-active",
        "card_id": "99990002",
        "first_name": "Amina",
        "last_name": "Test",
        "status": "active",
        "rooms": {"block": "B", "floor": 2, "number": "205"},
    }

    # Pending student not in roster -> error banner
    dlg_pending = StudentInfoCardDialog(None, pending_student, official_roster_data=None)
    assert dlg_pending.roster_banner._kind == "error"
    assert "Not found on the admissions roster" in dlg_pending.roster_banner._title.text()
    assert "Audit the physical dossier" in dlg_pending.roster_banner._message.text()

    # Active student not in roster -> info banner (quiet neutral note)
    dlg_active = StudentInfoCardDialog(None, active_student, official_roster_data=None)
    assert dlg_active.roster_banner._kind == "info"
    assert "Approved without a roster match" in dlg_active.roster_banner._title.text()


def test_roster_match_with_differing_fields(qapp, sample_complete_student):
    """When roster matches but fields differ, warning banner lists differing fields."""
    roster_with_diff = {
        "card_id": "90000001",
        "first_name": "Karim",
        "last_name": "Ben Ali",  # Differing last name
        "birth_date": "2003-01-01",  # Differing birth date
        "gender": "male",
    }
    dlg = StudentInfoCardDialog(
        None,
        sample_complete_student,
        official_roster_data=roster_with_diff,
    )
    assert dlg.roster_banner._kind == "warning"
    assert "Official roster differences" in dlg.roster_banner._message.text()
    assert "Full name" in dlg.roster_banner._message.text()
    assert "Date of birth" in dlg.roster_banner._message.text()


def test_off_thread_enrichment_success(qapp, sample_complete_student):
    """Background enrichment loads full profile and updates dialog."""
    client = MagicMock()
    stub_student = {
        "id": sample_complete_student["id"],
        "card_id": "90000001",
        "first_name": "Karim",
        "last_name": "Benali",
        "status": "active",
    }

    with patch("desktop.app.ui.infocard.get_student_profile", return_value=sample_complete_student):
        dlg = StudentInfoCardDialog(None, stub_student, client=client, student_id=stub_student["id"])
        assert wait_until(qapp, lambda: not dlg.tasks.is_busy())

    facts = _extract_fact_rows(dlg)
    assert facts["University"] == "Université de Tlemcen"
    assert facts["Faculty"] == "Faculté des Sciences"
    assert facts["Wilaya"] == "Oran"
    assert dlg.error_banner.isHidden()


def test_off_thread_enrichment_failure_and_retry(qapp):
    """Background enrichment failure shows error banner with working retry."""
    client = MagicMock()
    stub_student = {
        "id": "s-err",
        "card_id": "90000099",
        "first_name": "Error",
        "last_name": "Student",
        "status": "active",
    }

    with patch("desktop.app.ui.infocard.get_student_profile", side_effect=RuntimeError("Network timeout")):
        dlg = StudentInfoCardDialog(None, stub_student, client=client, student_id=stub_student["id"])
        assert wait_until(qapp, lambda: not dlg.tasks.is_busy())

    assert not dlg.error_banner.isHidden()
    assert "Network timeout" in dlg.error_banner._message.text() or "Could not load" in dlg.error_banner._title.text()

    # Retry with success
    recovered_data = dict(stub_student)
    recovered_data["university"] = "Université Récupérée"
    with patch("desktop.app.ui.infocard.get_student_profile", return_value=recovered_data):
        dlg.retry_btn.click()
        assert wait_until(qapp, lambda: not dlg.tasks.is_busy())

    assert dlg.error_banner.isHidden()
    facts = _extract_fact_rows(dlg)
    assert facts["University"] == "Université Récupérée"
