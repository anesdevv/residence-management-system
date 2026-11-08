"""Measure JSON payload size of list queries before (wildcard) and after (explicit column selection).

Simulates exact PostgREST JSON serialization of database records matching the schema of
seed_large.sql (20k students, 5k rooms, 50k tickets, 5k roster, 5k room changes, 20 blocks).
"""

from __future__ import annotations

import json
import uuid


def generate_benchmark_data():
    blocks_data = [
        {
            "id": str(uuid.uuid4()),
            "name": chr(65 + i),
            "gender": "male" if i % 2 == 0 else "female",
            "description": f"Residential Block {chr(65 + i)} with full amenities and student housing facilities for academic year.",
            "created_at": "2026-09-01T08:00:00.000Z",
            "updated_at": "2026-10-15T12:30:00.000Z",
        }
        for i in range(20)
    ]

    rooms_data = [
        {
            "id": str(uuid.uuid4()),
            "block": chr(65 + (i % 20)),
            "floor": i % 5,
            "number": f"{100 + (i % 250):03d}",
            "capacity": 1 + (i % 3),
            "gender": "male" if (i % 20) % 2 == 0 else "female",
            "created_at": "2026-09-01T08:00:00.000Z",
            "updated_at": "2026-10-15T12:30:00.000Z",
        }
        for i in range(5000)
    ]

    # 4,000 pending students (out of 20,000 total)
    pending_students_data = [
        {
            "id": str(uuid.uuid4()),
            "card_id": f"CARD-{1000000 + i}",
            "first_name": f"StudentFirst{i}",
            "last_name": f"StudentLast{i}",
            "birth_date": "2003-05-15",
            "gender": "male" if i % 2 == 1 else "female",
            "phone": f"0550{i % 900000 + 100000:06d}",
            "email": f"student{i}@university.edu",
            "university": "University of Tlemcen",
            "faculty": ["Computer Science", "Medicine", "Law", "Economics"][i % 4],
            "study_level": ["L1", "L2", "L3", "M1", "M2", "Doctorat"][i % 6],
            "wilaya": "Tlemcen",
            "status": "pending",
            "rejection_reason": None,
            "room_id": None,
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": "2026-10-01T10:00:00.000Z",
            "updated_at": "2026-10-01T10:00:00.000Z",
        }
        for i in range(4000)
    ]

    # 5,000 official roster records
    official_residents_data = [
        {
            "id": str(uuid.uuid4()),
            "card_id": f"CARD-{1000000 + i}",
            "first_name": f"OfficialFirst{i}",
            "last_name": f"OfficialLast{i}",
            "birth_date": "2003-05-15",
            "gender": "male" if i % 2 == 1 else "female",
            "university": "University of Tlemcen",
            "faculty": ["Computer Science", "Medicine", "Law", "Economics"][i % 4],
            "created_at": "2026-08-15T09:00:00.000Z",
        }
        for i in range(5000)
    ]

    # 50,000 maintenance reports
    maintenance_data = [
        {
            "id": str(uuid.uuid4()),
            "student_id": str(uuid.uuid4()),
            "category": ["plumbing", "electrical", "furniture", "internet", "other"][i % 5],
            "description": f"Fault report #{i}: Persistent leakage observed around bathroom fixtures and piping joints requiring technician maintenance.",
            "photo_path": f"faults/ticket_{i}.jpg" if i % 3 == 0 else None,
            "status": ["pending", "in_progress", "resolved"][i % 3],
            "staff_note": f"Technician dispatched for ticket #{i} during morning round." if i % 2 == 0 else None,
            "handled_by": str(uuid.uuid4()) if i % 3 != 0 else None,
            "created_at": "2026-10-05T14:20:00.000Z",
            "updated_at": "2026-10-06T09:15:00.000Z",
            "students": {
                "first_name": f"StudentFirst{i % 4000}",
                "last_name": f"StudentLast{i % 4000}",
                "card_id": f"CARD-{1000000 + (i % 4000)}",
            },
        }
        for i in range(50000)
    ]

    # 5,000 room change requests
    room_changes_data = [
        {
            "id": str(uuid.uuid4()),
            "student_id": str(uuid.uuid4()),
            "current_room_id": str(uuid.uuid4()),
            "preferred_room_id": str(uuid.uuid4()),
            "reason": f"Request #{i}: Seeking reassignment closer to department laboratories and accessible study halls.",
            "status": ["pending", "approved", "rejected"][i % 3],
            "decision_note": f"Decision note #{i}: Capacity verified and processed by administrative staff." if i % 3 != 0 else None,
            "decided_by": str(uuid.uuid4()) if i % 3 != 0 else None,
            "decided_at": "2026-10-10T11:00:00.000Z" if i % 3 != 0 else None,
            "created_at": "2026-10-08T09:30:00.000Z",
            "updated_at": "2026-10-10T11:00:00.000Z",
            "students": {
                "first_name": f"StudentFirst{i % 4000}",
                "last_name": f"StudentLast{i % 4000}",
                "gender": "male" if i % 2 == 0 else "female",
                "card_id": f"CARD-{1000000 + (i % 4000)}",
            },
            "staff": {
                "full_name": f"StaffOfficer {1 + (i % 5)}",
            } if i % 3 != 0 else None,
        }
        for i in range(5000)
    ]

    # 5,000 active residents
    residents_data = [
        {
            "id": str(uuid.uuid4()),
            "card_id": f"CARD-{1000000 + i}",
            "first_name": f"ResidentFirst{i}",
            "last_name": f"ResidentLast{i}",
            "birth_date": "2002-11-20",
            "gender": "male" if i % 2 == 0 else "female",
            "phone": f"0550{i % 900000 + 100000:06d}",
            "email": f"resident{i}@university.edu",
            "university": "University of Tlemcen",
            "faculty": ["Computer Science", "Medicine", "Law", "Economics"][i % 4],
            "study_level": ["L2", "L3", "M1", "M2"][i % 4],
            "wilaya": "Tlemcen",
            "status": "active",
            "rejection_reason": None,
            "room_id": str(uuid.uuid4()),
            "reviewed_by": str(uuid.uuid4()),
            "reviewed_at": "2026-09-10T10:00:00.000Z",
            "created_at": "2026-09-01T08:00:00.000Z",
            "updated_at": "2026-09-10T10:00:00.000Z",
            "rooms": {
                "block": chr(65 + (i % 20)),
                "number": f"{100 + (i % 250):03d}",
                "floor": i % 5,
            },
        }
        for i in range(5000)
    ]

    return {
        "blocks": blocks_data,
        "rooms": rooms_data,
        "pending": pending_students_data,
        "official": official_residents_data,
        "maintenance": maintenance_data,
        "room_changes": room_changes_data,
        "residents": residents_data,
    }


def filter_dict(d: dict, keys: list[str]) -> dict:
    res = {}
    for k in keys:
        if k in d:
            res[k] = d[k]
    return res


def measure():
    data = generate_benchmark_data()

    # Query 1 & 2: official_residents
    # Baseline: * (id, card_id, first_name, last_name, birth_date, gender, university, faculty, created_at)
    # Optimized: card_id, first_name, last_name, birth_date, gender, university, faculty
    off_base_json = json.dumps(data["official"]).encode("utf-8")
    off_opt_cols = ["card_id", "first_name", "last_name", "birth_date", "gender", "university", "faculty"]
    off_opt_json = json.dumps([filter_dict(r, off_opt_cols) for r in data["official"]]).encode("utf-8")

    # Query 3 & 4: pending_students (4,000 pending)
    # Baseline: * (all columns including updated_at)
    # Optimized: explicit list omitting updated_at
    pend_base_json = json.dumps(data["pending"]).encode("utf-8")
    pend_opt_cols = [
        "id", "card_id", "first_name", "last_name", "birth_date", "gender", "phone", "email",
        "university", "faculty", "study_level", "wilaya", "status", "rejection_reason",
        "room_id", "reviewed_by", "reviewed_at", "created_at"
    ]
    pend_opt_json = json.dumps([filter_dict(r, pend_opt_cols) for r in data["pending"]]).encode("utf-8")

    # Query 5 & 6: maintenance_reports (50,000 tickets)
    # Baseline: *, students(first_name, last_name, card_id) (includes handled_by)
    # Optimized: explicit columns (omits handled_by)
    maint_base_json = json.dumps(data["maintenance"]).encode("utf-8")
    maint_opt_cols = [
        "id", "student_id", "category", "description", "photo_path", "status",
        "staff_note", "created_at", "updated_at", "students"
    ]
    maint_opt_json = json.dumps([filter_dict(r, maint_opt_cols) for r in data["maintenance"]]).encode("utf-8")

    # Query 7 & 8: room_change_requests (5,000 requests)
    # Baseline: *, students(...), staff(...)
    # Optimized: explicit list of all read columns
    rc_base_json = json.dumps(data["room_changes"]).encode("utf-8")
    rc_opt_cols = [
        "id", "student_id", "current_room_id", "preferred_room_id", "reason", "status",
        "decision_note", "decided_by", "decided_at", "created_at", "updated_at",
        "students", "staff"
    ]
    rc_opt_json = json.dumps([filter_dict(r, rc_opt_cols) for r in data["room_changes"]]).encode("utf-8")

    # Query 9 & 10: residents (5,000 active students)
    # Baseline: *, rooms(...) (includes rejection_reason, reviewed_by, reviewed_at, updated_at)
    # Optimized: explicit columns without unused review/rejection columns
    res_base_json = json.dumps(data["residents"]).encode("utf-8")
    res_opt_cols = [
        "id", "card_id", "first_name", "last_name", "birth_date", "gender", "phone", "email",
        "university", "faculty", "study_level", "wilaya", "status", "room_id", "created_at",
        "rooms"
    ]
    res_opt_json = json.dumps([filter_dict(r, res_opt_cols) for r in data["residents"]]).encode("utf-8")

    # Query 11: rooms (5,000 rooms)
    # Baseline: * (id, block, floor, number, capacity, gender, created_at, updated_at)
    # Optimized: id, block, floor, number, capacity, gender (omits created_at, updated_at)
    rooms_base_json = json.dumps(data["rooms"]).encode("utf-8")
    rooms_opt_cols = ["id", "block", "floor", "number", "capacity", "gender"]
    rooms_opt_json = json.dumps([filter_dict(r, rooms_opt_cols) for r in data["rooms"]]).encode("utf-8")

    # Query 12: blocks (20 blocks)
    # Baseline: * (id, name, gender, description, created_at, updated_at)
    # Optimized: id, name, gender (omits description, created_at, updated_at)
    blocks_base_json = json.dumps(data["blocks"]).encode("utf-8")
    blocks_opt_cols = ["id", "name", "gender"]
    blocks_opt_json = json.dumps([filter_dict(r, blocks_opt_cols) for r in data["blocks"]]).encode("utf-8")

    results = [
        ("Rooms Table", "rooms", 5000, len(rooms_base_json), len(rooms_opt_json)),
        ("Residential Blocks", "blocks", 20, len(blocks_base_json), len(blocks_opt_json)),
        ("Official Roster (lookup & page)", "official_residents", 5000, len(off_base_json), len(off_opt_json)),
        ("Pending Applications & Live-Sync", "students", 4000, len(pend_base_json), len(pend_opt_json)),
        ("Active Residents", "students + rooms", 5000, len(res_base_json), len(res_opt_json)),
        ("Maintenance Reports & Live-Sync", "maintenance_reports + students", 50000, len(maint_base_json), len(maint_opt_json)),
        ("Room Changes & Live-Sync", "room_change_requests + students/staff", 5000, len(rc_base_json), len(rc_opt_json)),
    ]

    print(f"{'Target Query':<36} | {'Rows':<6} | {'Baseline':<12} | {'Optimized':<12} | {'Savings':<10} | {'% Reduction':<12}")
    print("-" * 100)
    total_base = 0
    total_opt = 0
    for name, tbl, rows, b_size, o_size in results:
        savings = b_size - o_size
        pct = (savings / b_size) * 100 if b_size > 0 else 0
        total_base += b_size
        total_opt += o_size
        b_str = f"{b_size / 1024:.1f} KB" if b_size < 1024 * 1024 else f"{b_size / (1024 * 1024):.2f} MB"
        o_str = f"{o_size / 1024:.1f} KB" if o_size < 1024 * 1024 else f"{o_size / (1024 * 1024):.2f} MB"
        s_str = f"{savings / 1024:.1f} KB" if savings < 1024 * 1024 else f"{savings / (1024 * 1024):.2f} MB"
        print(f"{name:<36} | {rows:<6} | {b_str:<12} | {o_str:<12} | {s_str:<10} | {pct:.1f}%")

    print("-" * 100)
    tot_s = total_base - total_opt
    tot_pct = (tot_s / total_base) * 100
    print(f"{'TOTAL ACROSS ALL QUERIES':<36} | {'-':<6} | {total_base / (1024*1024):.2f} MB     | {total_opt / (1024*1024):.2f} MB     | {tot_s / (1024*1024):.2f} MB   | {tot_pct:.1f}%")


if __name__ == "__main__":
    measure()
