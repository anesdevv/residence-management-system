"""RÉSIVO — Desktop Tables Scalability Benchmark (Step 0 & Verification)

Measures populate time, filter/search time, and repaint time at 2,000 and 5,000 rows
across all 7 table pages under offscreen Qt.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from desktop.app.ui.pages.pending import PendingPage
from desktop.app.ui.pages.residents import ResidentsPage
from desktop.app.ui.pages.rooms import RoomsPage
from desktop.app.ui.pages.maintenance import MaintenancePage
from desktop.app.ui.pages.room_changes import RoomChangesPage
from desktop.app.ui.pages.official_list import OfficialListPage
from desktop.app.ui.pages.staff_accounts import StaffAccountsPage


class FakeClient:
    def __init__(self):
        self.storage = self

    def from_(self, bucket):
        return self

    def create_signed_url(self, path, ttl):
        return None

    def table(self, name):
        return self

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def execute(self):
        return type("Resp", (), {"data": []})()

    def rpc(self, *a, **k):
        return self


def make_pending_data(n: int):
    rows = []
    official = {}
    for i in range(n):
        card = f"CARD{100000 + i}"
        status = "pending" if i % 3 == 0 else "active" if i % 3 == 1 else "rejected"
        rows.append({
            "id": f"stud_{i}",
            "card_id": card,
            "first_name": f"First{i}",
            "last_name": f"Last{i}",
            "birth_date": "2003-04-12",
            "gender": "male" if i % 2 == 0 else "female",
            "phone": "0555123456",
            "email": f"s{i}@univ-tlemcen.dz",
            "university": "University of Tlemcen",
            "faculty": "Science",
            "study_level": "L3",
            "wilaya": "Tlemcen",
            "status": status,
            "rejection_reason": "Incomplete file" if status == "rejected" else None,
            "room_id": f"room_{i % 50}" if status == "active" else None,
            "reviewed_by": "admin",
            "reviewed_at": "2026-11-01T12:00:00Z",
            "created_at": "2026-11-01T12:00:00Z",
        })
        if i % 2 == 0:
            official[card] = True
    return rows, official


def make_residents_data(n: int):
    rows = []
    official = {}
    for i in range(n):
        card = f"CARD{100000 + i}"
        block = f"B{i % 10}"
        num = str(100 + (i % 200))
        rows.append({
            "id": f"res_{i}",
            "card_id": card,
            "first_name": f"Resident{i}",
            "last_name": f"Family{i}",
            "birth_date": "2002-08-20",
            "gender": "male" if i % 2 == 0 else "female",
            "phone": "0661234567",
            "email": f"res{i}@univ-tlemcen.dz",
            "university": "University of Tlemcen",
            "faculty": "Medicine",
            "study_level": "M1",
            "wilaya": "Oran",
            "status": "active",
            "room_id": f"r_{i % 300}",
            "created_at": "2026-10-15T09:00:00Z",
            "rooms": {"block": block, "number": num, "floor": i % 4},
        })
        if i % 2 == 0:
            official[card] = True
    return rows, official


def make_rooms_data(n: int):
    rooms = []
    occupancy = {}
    blocks = [{"name": f"B{b}", "gender": "male" if b % 2 == 0 else "female"} for b in range(10)]
    for i in range(n):
        r_id = f"r_{i}"
        rooms.append({
            "id": r_id,
            "block": f"B{i % 10}",
            "floor": i % 4,
            "number": str(100 + (i % 300)),
            "gender": "male" if i % 2 == 0 else "female",
            "capacity": 2,
        })
        occupancy[r_id] = i % 3  # 0, 1, or 2 occupied
    return {"rows": rooms, "occupancy": occupancy, "blocks": blocks}


def make_maintenance_data(n: int):
    categories = ["plumbing", "electricity", "carpentry", "others"]
    statuses = ["pending", "in_progress", "resolved"]
    rows = []
    for i in range(n):
        rows.append({
            "id": f"maint_{i}",
            "student_id": f"s_{i}",
            "category": categories[i % 4],
            "description": f"Faucet leaking in bathroom {i} emergency repair needed",
            "status": statuses[i % 3],
            "created_at": "2026-11-05T14:30:00Z",
            "photo_path": None,
            "students": {
                "first_name": f"Student{i}",
                "last_name": f"Last{i}",
                "card_id": f"CARD{100000 + i}",
            },
        })
    return rows


def make_room_changes_data(n: int):
    statuses = ["pending", "approved", "rejected"]
    rows = []
    for i in range(n):
        st = statuses[i % 3]
        rows.append({
            "id": f"rc_{i}",
            "student_id": f"s_{i}",
            "reason": f"Requesting transfer to study floor {i} due to noise",
            "status": st,
            "created_at": "2026-11-04T10:00:00Z",
            "decision_note": f"Decision note {i}" if st != "pending" else None,
            "decided_by": "admin" if st != "pending" else None,
            "students": {
                "first_name": f"Student{i}",
                "last_name": f"Last{i}",
                "card_id": f"CARD{100000 + i}",
                "gender": "male" if i % 2 == 0 else "female",
            },
        })
    return rows


def make_roster_data(n: int):
    rows = []
    for i in range(n):
        rows.append({
            "card_id": f"CARD{100000 + i}",
            "first_name": f"OfficialFirst{i}",
            "last_name": f"OfficialLast{i}",
            "birth_date": "2002-05-15",
            "gender": "male" if i % 2 == 0 else "female",
            "university": "University of Tlemcen",
            "faculty": "Technology",
        })
    return rows


def make_staff_data(n: int):
    rows = []
    for i in range(n):
        rows.append({
            "id": f"staff_{i:04d}",
            "full_name": f"Staff Officer {i}",
            "position": "Housing Officer",
            "role": "staff",
        })
    return rows


def run_benchmarks():
    qapp = QApplication.instance()
    if qapp is None:
        qapp = QApplication([])

    client = FakeClient()
    row_counts = [2000, 5000]
    results = {}

    print(f"{'Page':<24} | {'Rows':<5} | {'Populate (ms)':<14} | {'Filter/Search (ms)':<18} | {'Repaint (ms)':<13}")
    print("-" * 84)

    for n in row_counts:
        # 1. PendingPage
        p_page = PendingPage(client)
        p_page.resize(1100, 700)
        p_page.show()
        qapp.processEvents()

        p_rows, p_off = make_pending_data(n)
        t0 = time.perf_counter()
        p_page._apply_snapshot((p_rows, p_off))
        qapp.processEvents()
        p_pop = (time.perf_counter() - t0) * 1000.0

        p_page.search.edit.setText("First50")
        t0 = time.perf_counter()
        p_page.apply_filter()
        qapp.processEvents()
        p_filt = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        _pix = p_page.grab()
        qapp.processEvents()
        p_paint = (time.perf_counter() - t0) * 1000.0
        p_page.close()
        p_page.deleteLater()
        qapp.processEvents()

        results.setdefault("PendingPage", {})[n] = (p_pop, p_filt, p_paint)
        print(f"{'Pending / Applications':<24} | {n:<5} | {p_pop:>14.2f} | {p_filt:>18.2f} | {p_paint:>13.2f}", flush=True)

        # 2. ResidentsPage
        res_page = ResidentsPage(client)
        res_page.resize(1100, 700)
        res_page.show()
        qapp.processEvents()

        res_rows, res_off = make_residents_data(n)
        res_page.official = res_off
        t0 = time.perf_counter()
        res_page._on_reload_success(res_rows)
        qapp.processEvents()
        res_pop = (time.perf_counter() - t0) * 1000.0

        res_page.search.edit.setText("Resident50")
        t0 = time.perf_counter()
        res_page.render()
        qapp.processEvents()
        res_filt = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        _pix = res_page.grab()
        qapp.processEvents()
        res_paint = (time.perf_counter() - t0) * 1000.0
        res_page.close()
        res_page.deleteLater()
        qapp.processEvents()

        results.setdefault("ResidentsPage", {})[n] = (res_pop, res_filt, res_paint)
        print(f"{'Residents':<24} | {n:<5} | {res_pop:>14.2f} | {res_filt:>18.2f} | {res_paint:>13.2f}", flush=True)

        # 3. RoomsPage
        rooms_page = RoomsPage(client)
        rooms_page.resize(1100, 700)
        rooms_page.show()
        qapp.processEvents()

        rm_snap = make_rooms_data(n)
        t0 = time.perf_counter()
        rooms_page._apply_snapshot(rm_snap)
        qapp.processEvents()
        rm_pop = (time.perf_counter() - t0) * 1000.0

        rooms_page.search_field.edit.setText("B2 150")
        t0 = time.perf_counter()
        rooms_page.filter_table()
        qapp.processEvents()
        rm_filt = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        _pix = rooms_page.grab()
        qapp.processEvents()
        rm_paint = (time.perf_counter() - t0) * 1000.0
        rooms_page.close()
        rooms_page.deleteLater()
        qapp.processEvents()

        results.setdefault("RoomsPage", {})[n] = (rm_pop, rm_filt, rm_paint)
        print(f"{'Rooms':<24} | {n:<5} | {rm_pop:>14.2f} | {rm_filt:>18.2f} | {rm_paint:>13.2f}", flush=True)

        # 4. MaintenancePage
        m_page = MaintenancePage(client)
        m_page.resize(1100, 700)
        m_page.show()
        qapp.processEvents()

        m_rows = make_maintenance_data(n)
        t0 = time.perf_counter()
        m_page.apply_live_data(m_rows, force=True)
        qapp.processEvents()
        m_pop = (time.perf_counter() - t0) * 1000.0

        m_page.search.edit.setText("leaking")
        t0 = time.perf_counter()
        m_page.apply_filter()
        qapp.processEvents()
        m_filt = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        _pix = m_page.grab()
        qapp.processEvents()
        m_paint = (time.perf_counter() - t0) * 1000.0
        m_page.close()
        m_page.deleteLater()
        qapp.processEvents()

        results.setdefault("MaintenancePage", {})[n] = (m_pop, m_filt, m_paint)
        print(f"{'Maintenance':<24} | {n:<5} | {m_pop:>14.2f} | {m_filt:>18.2f} | {m_paint:>13.2f}", flush=True)

        # 5. RoomChangesPage
        rc_page = RoomChangesPage(client)
        rc_page.resize(1100, 700)
        rc_page.show()
        qapp.processEvents()

        rc_rows = make_room_changes_data(n)
        t0 = time.perf_counter()
        rc_page.apply_live_data(rc_rows)
        qapp.processEvents()
        rc_pop = (time.perf_counter() - t0) * 1000.0

        rc_page.search.edit.setText("noise")
        t0 = time.perf_counter()
        rc_page.filter_table()
        qapp.processEvents()
        rc_filt = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        _pix = rc_page.grab()
        qapp.processEvents()
        rc_paint = (time.perf_counter() - t0) * 1000.0
        rc_page.close()
        rc_page.deleteLater()
        qapp.processEvents()

        results.setdefault("RoomChangesPage", {})[n] = (rc_pop, rc_filt, rc_paint)
        print(f"{'Room Changes':<24} | {n:<5} | {rc_pop:>14.2f} | {rc_filt:>18.2f} | {rc_paint:>13.2f}", flush=True)

        # 6. OfficialListPage
        off_page = OfficialListPage(client)
        off_page.resize(1100, 700)
        off_page.show()
        qapp.processEvents()

        off_rows = make_roster_data(n)
        t0 = time.perf_counter()
        off_page._apply_rows(off_rows)
        qapp.processEvents()
        off_pop = (time.perf_counter() - t0) * 1000.0

        off_page.search_field.edit.setText("OfficialFirst50")
        t0 = time.perf_counter()
        off_page.filter_table()
        qapp.processEvents()
        off_filt = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        _pix = off_page.grab()
        qapp.processEvents()
        off_paint = (time.perf_counter() - t0) * 1000.0
        off_page.close()
        off_page.deleteLater()
        qapp.processEvents()

        results.setdefault("OfficialListPage", {})[n] = (off_pop, off_filt, off_paint)
        print(f"{'Official Roster':<24} | {n:<5} | {off_pop:>14.2f} | {off_filt:>18.2f} | {off_paint:>13.2f}", flush=True)

        # 7. StaffAccountsPage
        staff_page = StaffAccountsPage(client)
        staff_page.resize(1100, 700)
        staff_page.show()
        qapp.processEvents()

        staff_rows = make_staff_data(n)
        t0 = time.perf_counter()
        staff_page._apply_rows(staff_rows)
        qapp.processEvents()
        staff_pop = (time.perf_counter() - t0) * 1000.0

        # No filter/search box
        staff_filt = 0.0

        t0 = time.perf_counter()
        _pix = staff_page.grab()
        qapp.processEvents()
        staff_paint = (time.perf_counter() - t0) * 1000.0
        staff_page.close()
        staff_page.deleteLater()
        qapp.processEvents()

        results.setdefault("StaffAccountsPage", {})[n] = (staff_pop, staff_filt, staff_paint)
        print(f"{'Staff Accounts':<24} | {n:<5} | {staff_pop:>14.2f} | {staff_filt:>18.2f} | {staff_paint:>13.2f}", flush=True)
        print("-" * 84, flush=True)

    return results


if __name__ == "__main__":
    run_benchmarks()
