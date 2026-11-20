"""Unit tests for the explicit detail fetchers in desktop/app/client.py.

Covers:
- get_ticket_detail(ticket_id)
- get_room_change_detail(request_id)
- get_student_profile(student_id)
- Handling of None/invalid IDs
- UUID vs card_id resolution
- Nested embedded relations normalization and fallbacks
- Official roster comparison calculation
"""

from __future__ import annotations

import pytest
from desktop.app.client import (
    get_ticket_detail,
    get_room_change_detail,
    get_student_profile,
    invalidate_official_lookup_cache,
)


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, table_name, data):
        self.table_name = table_name
        self.all_data = data
        self._eq_filters = []
        self._limit = None

    def select(self, projection):
        return self

    def eq(self, column, value):
        self._eq_filters.append((column, value))
        return self

    def limit(self, count):
        self._limit = count
        return self

    def order(self, *args, **kwargs):
        return self

    def execute(self):
        rows = list(self.all_data)
        for col, val in self._eq_filters:
            rows = [r for r in rows if str(r.get(col)) == str(val)]
        if self._limit is not None:
            rows = rows[: self._limit]
        return FakeResponse(rows)


class MockDetailClient:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {
            "maintenance_reports": [],
            "room_change_requests": [],
            "students": [],
            "rooms": [],
            "staff": [],
            "official_residents": [],
        }

    def table(self, name: str):
        return FakeQuery(name, self.tables.get(name, []))


@pytest.fixture(autouse=True)
def clean_cache():
    invalidate_official_lookup_cache()
    yield
    invalidate_official_lookup_cache()


def test_get_ticket_detail_full():
    client = MockDetailClient()
    client.tables["maintenance_reports"] = [
        {
            "id": "t-1",
            "student_id": "s-1",
            "category": "plumbing",
            "description": "Leaky faucet in bathroom",
            "photo_path": "photos/leak.jpg",
            "status": "pending",
            "staff_note": "Awaiting plumber",
            "handled_by": "staff-1",
            "created_at": "2026-11-12T10:00:00Z",
            "updated_at": "2026-11-13T10:00:00Z",
            "students": {
                "id": "s-1",
                "card_id": "20230001",
                "first_name": "Karim",
                "last_name": "Benali",
                "gender": "male",
                "phone": "0555123456",
                "email": "karim@test.dz",
                "status": "active",
                "room_id": "r-1",
                "rooms": {"id": "r-1", "block": "A", "floor": 1, "number": "101", "capacity": 2},
            },
            "staff": {"id": "staff-1", "full_name": "Admin Director", "position": "Director"},
        }
    ]

    res = get_ticket_detail(client, "t-1")
    assert res is not None
    assert res["id"] == "t-1"
    assert res["category"] == "plumbing"
    assert res["description"] == "Leaky faucet in bathroom"
    assert res["students"]["first_name"] == "Karim"
    assert res["room"]["block"] == "A"
    assert res["room"]["number"] == "101"
    assert res["staff"]["full_name"] == "Admin Director"


def test_get_ticket_detail_room_fallback():
    client = MockDetailClient()
    client.tables["rooms"] = [
        {"id": "r-2", "block": "B", "floor": 2, "number": "204", "capacity": 2}
    ]
    # In mock or raw data where nested rooms wasn't joined, but room_id is on student
    client.tables["maintenance_reports"] = [
        {
            "id": "t-2",
            "student_id": "s-2",
            "category": "electricity",
            "description": "No power",
            "status": "pending",
            "students": {
                "id": "s-2",
                "card_id": "20230002",
                "first_name": "Amina",
                "last_name": "Saidi",
                "room_id": "r-2",
            },
        }
    ]

    res = get_ticket_detail(client, "t-2")
    assert res is not None
    assert res["room"] is not None
    assert res["room"]["block"] == "B"
    assert res["room"]["number"] == "204"


def test_get_ticket_detail_none():
    client = MockDetailClient()
    assert get_ticket_detail(client, None) is None
    assert get_ticket_detail(client, "") is None
    assert get_ticket_detail(client, "non-existent") is None


def test_get_room_change_detail_full():
    client = MockDetailClient()
    client.tables["room_change_requests"] = [
        {
            "id": "rc-1",
            "student_id": "s-1",
            "current_room_id": "r-1",
            "preferred_room_id": "r-2",
            "reason": "Need a quieter room for exams",
            "status": "pending",
            "decision_note": None,
            "decided_by": None,
            "decided_at": None,
            "created_at": "2026-11-15T12:00:00Z",
            "updated_at": "2026-11-15T12:00:00Z",
            "students": {
                "id": "s-1",
                "card_id": "20230001",
                "first_name": "Karim",
                "last_name": "Benali",
                "gender": "male",
                "phone": "0555123456",
                "email": "karim@test.dz",
                "status": "active",
            },
            "staff": None,
            "current_room": {"id": "r-1", "block": "A", "floor": 1, "number": "101", "capacity": 2},
            "preferred_room": {"id": "r-2", "block": "B", "floor": 2, "number": "204", "capacity": 2},
        }
    ]

    res = get_room_change_detail(client, "rc-1")
    assert res is not None
    assert res["id"] == "rc-1"
    assert res["reason"] == "Need a quieter room for exams"
    assert res["current_room"]["block"] == "A"
    assert res["current_room"]["number"] == "101"
    assert res["preferred_room"]["block"] == "B"
    assert res["preferred_room"]["number"] == "204"
    assert res["students"]["first_name"] == "Karim"


def test_get_room_change_detail_fallback():
    client = MockDetailClient()
    client.tables["rooms"] = [
        {"id": "r-1", "block": "A", "floor": 1, "number": "101", "capacity": 2},
        {"id": "r-2", "block": "B", "floor": 2, "number": "204", "capacity": 2},
    ]
    client.tables["room_change_requests"] = [
        {
            "id": "rc-2",
            "student_id": "s-1",
            "current_room_id": "r-1",
            "preferred_room_id": "r-2",
            "reason": "Roommate conflict",
            "status": "pending",
        }
    ]

    res = get_room_change_detail(client, "rc-2")
    assert res is not None
    assert res["current_room"]["number"] == "101"
    assert res["preferred_room"]["number"] == "204"


def test_get_room_change_detail_none():
    client = MockDetailClient()
    assert get_room_change_detail(client, None) is None
    assert get_room_change_detail(client, "") is None
    assert get_room_change_detail(client, "non-existent") is None


def test_get_student_profile_match_and_diff():
    client = MockDetailClient()
    client.tables["students"] = [
        {
            "id": "e0000000-0000-0000-0000-000000000007",
            "card_id": "90000007",
            "first_name": "Test",
            "last_name": "Student 7",
            "birth_date": "2002-02-19",
            "gender": "male",
            "phone": "0550000007",
            "email": "test.student7@example.com",
            "university": "Test University of Tlemcen",
            "faculty": "Test Faculty of Science",
            "study_level": "L2",
            "wilaya": "Tlemcen",
            "status": "active",
            "room_id": "r-202",
            "rooms": {"id": "r-202", "block": "B", "floor": 2, "number": "202", "capacity": 2},
            "staff": {"id": "st-1", "full_name": "Staff Reviewer"},
            "reviewed_by": "st-1",
            "reviewed_at": "2026-11-10T12:00:00Z",
            "created_at": "2026-11-01T12:00:00Z",
            "updated_at": "2026-11-10T12:00:00Z",
        }
    ]
    # Official roster has a match with one difference (different birth_date)
    client.tables["official_residents"] = [
        {
            "card_id": "90000007",
            "first_name": "Test",
            "last_name": "Student 7",
            "birth_date": "2002-01-01",  # differs from 2002-02-19
            "gender": "male",
            "university": "Test University of Tlemcen",
            "faculty": "Test Faculty of Science",
        }
    ]

    # Look up by UUID
    res = get_student_profile(client, "e0000000-0000-0000-0000-000000000007")
    assert res is not None
    assert res["first_name"] == "Test"
    assert res["last_name"] == "Student 7"
    assert res["room"]["block"] == "B"
    assert res["room"]["number"] == "202"
    assert res["roster_match"] is True
    assert res["roster_differing_fields"] == ["birth_date"]

    # Look up by card_id
    res_card = get_student_profile(client, "90000007")
    assert res_card is not None
    assert res_card["id"] == "e0000000-0000-0000-0000-000000000007"


def test_get_student_profile_not_in_roster():
    client = MockDetailClient()
    client.tables["students"] = [
        {
            "id": "e0000000-0000-0000-0000-000000000008",
            "card_id": "90000008",
            "first_name": "Pending",
            "last_name": "Applicant",
            "status": "pending",
            "room_id": None,
        }
    ]
    client.tables["official_residents"] = []

    res = get_student_profile(client, "90000008")
    assert res is not None
    assert res["roster_match"] is False
    assert res["official_roster"] is None
    assert res["roster_differing_fields"] == []
    assert res["room"] is None
