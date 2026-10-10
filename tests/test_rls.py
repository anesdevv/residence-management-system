import pytest


def test_anon_cannot_read_students(anon_client):
    resp = anon_client.table("students").select("id").execute()
    assert resp.data == []


def test_student_reads_only_self(student_client):
    resp = student_client.table("students").select("id, card_id").execute()
    assert len(resp.data) == 1
    assert resp.data[0]["card_id"] == "20230001"


def test_staff_reads_all_students(staff_client):
    resp = staff_client.table("students").select("id").execute()
    assert len(resp.data) >= 1


def test_student_cannot_insert_official_residents(student_client):
    with pytest.raises(Exception):
        student_client.table("official_residents").insert(
            {"card_id": "99999999", "first_name": "Hack", "last_name": "Attempt"}
        ).execute()