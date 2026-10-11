import pytest

def test_student_cannot_approve_student(student_client):
    with pytest.raises(Exception):
        student_client.rpc("approve_student", {"p_student": None, "p_room": None}).execute()


def test_staff_approve_then_reject_flow(staff_client):
    # Find the seeded female room for the seeded male student's gender mismatch check.
    rooms = staff_client.table("rooms").select("id, gender").execute().data
    male_room = next(r["id"] for r in rooms if r["gender"] == "male")
    student = staff_client.table("students").select("id").eq("card_id", "20230001").single().execute().data

    approved = staff_client.rpc("approve_student", {
        "p_student": student["id"], "p_room": male_room,
    }).execute().data
    assert approved["status"] == "active"
    assert approved["room_id"] == male_room

    # Gender mismatch test
    female_room = next(r["id"] for r in rooms if r["gender"] == "female")
    with pytest.raises(Exception):
        staff_client.rpc("approve_student", {
            "p_student": student["id"], "p_room": female_room,
        }).execute()


def test_student_update_contact(student_client):
    updated = student_client.rpc("update_my_contact", {
        "p_phone": "0550000099", "p_email": "updated@test.com",
    }).execute().data
    assert updated["phone"] == "0550000099"
    assert updated["email"] == "updated@test.com"

    # Restore original phone
    student_client.rpc("update_my_contact", {
        "p_phone": "0550000001", "p_email": "",
    }).execute()