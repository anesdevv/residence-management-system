"""Room-change status views (P2): Rejected/Approved inspection + live sync.

Covers the four-view segmented control, the rejection desk-inquiry record,
selection by id after decisions, merge-based live refresh and the pending-only
sidebar badge.
"""

import os
import time
from copy import deepcopy
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from desktop.app.ui.live_sync import LiveSyncWorker
from desktop.app.ui.main_window import MainWindow
from desktop.app.ui.pages import room_changes as room_changes_mod
from desktop.app.ui.pages.room_changes import RoomChangesPage

STAMP = "2026-10-20T14:30:00Z"
SHOWN_STAMP = "2026-10-20 14:30:00"


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def _drain_tasks(qapp):
    """Never let a background worker outlive a test."""
    yield
    QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()


def wait_until(qapp, predicate, timeout=4.0):
    """Process GUI events until ``predicate()`` or the deadline."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    qapp.processEvents()
    return bool(predicate())


class FakeResponse:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count if count is not None else (len(data) if data is not None else 0)


class FakeQuery:
    """Small postgrest-ish fake; filters count rows at execute time."""

    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self._eq = []
        self._single = False
        self._delete = False
        self._count = False

    def select(self, *_args, **kwargs):
        self._count = kwargs.get("count") == "exact"
        return self

    def order(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self._eq.append((column, value))
        return self

    def single(self):
        self._single = True
        return self

    def delete(self):
        self._delete = True
        return self

    def execute(self):
        rows = deepcopy(self.client.data_for(self.table_name))
        for column, value in self._eq:
            rows = [row for row in rows if row.get(column) == value]

        if self._delete:
            target = self.client.data_for(self.table_name)
            removed = [
                row for row in list(target)
                if all(row.get(column) == value for column, value in self._eq)
            ]
            for row in removed:
                target.remove(row)
            # PostgREST represents deletes: an empty list means no row matched.
            return FakeResponse(deepcopy(removed))

        if self.table_name == "room_change_requests":
            self.client.room_change_selects += 1
            # Mirror the ``staff(full_name)`` embed of the page's select().
            for row in rows:
                decider = str(row.get("decided_by") or "")
                if decider and not row.get("staff"):
                    name = self.client.staff_names.get(decider)
                    if name:
                        row["staff"] = {"full_name": name}

        if self._single:
            return FakeResponse(rows[0] if rows else None)
        return FakeResponse(rows, count=len(rows) if self._count else None)


class FakeRpcCall:
    def __init__(self, client, name, params):
        self.client = client
        self.name = name
        self.params = params

    def execute(self):
        self.client.rpc_calls.append((self.name, deepcopy(self.params)))
        if self.name == "reject_room_change":
            row = self.client.request(self.params.get("p_request"))
            if row is None:
                raise RuntimeError("pending request not found")
            updated = deepcopy(row)
            updated.update({
                "status": "rejected",
                "decision_note": self.params.get("p_reason"),
                "decided_by": "staff-1",
                "decided_at": STAMP,
            })
            row.update(updated)
            return FakeResponse(self._bare_row(updated))
        if self.name == "approve_room_change":
            row = self.client.request(self.params.get("p_request"))
            if row is None:
                raise RuntimeError("pending request not found")
            updated = deepcopy(row)
            updated.update({
                "status": "approved",
                "decision_note": None,
                "decided_by": "staff-1",
                "decided_at": STAMP,
            })
            row.update(updated)
            return FakeResponse(self._bare_row(updated))
        return FakeResponse(None)

    @staticmethod
    def _bare_row(row):
        """The real RPC returns the table row without the select() joins."""
        bare = deepcopy(row)
        bare.pop("students", None)
        bare.pop("staff", None)
        return bare


class FakeClient:
    def __init__(self, requests=None, students=None, reports=None):
        self.tables = {
            "room_change_requests": list(requests or []),
            "students": list(students or []),
            "maintenance_reports": list(reports or []),
            "rooms": [],
        }
        self.rpc_calls = []
        self.room_change_selects = 0
        self.staff_names = {"staff-1": "Nadia Haddad"}

    def table(self, name):
        return FakeQuery(self, name)

    def rpc(self, name, params=None):
        return FakeRpcCall(self, name, params)

    def data_for(self, name):
        return self.tables.setdefault(name, [])

    def request(self, request_id):
        return next(
            (row for row in self.data_for("room_change_requests")
             if str(row.get("id")) == str(request_id)),
            None,
        )


def request_row(
    request_id="rcr-1",
    status="pending",
    first_name="Walid",
    last_name="Khelifi",
    card_id="202437010009",
    reason="Quiet study environment",
    decision_note=None,
    decided_at=None,
    staff_name=None,
    current_room_id="room-current",
    preferred_room_id="room-preferred",
):
    row = {
        "id": request_id,
        "student_id": f"st-{request_id}",
        "current_room_id": current_room_id,
        "preferred_room_id": preferred_room_id,
        "reason": reason,
        "status": status,
        "created_at": "2026-10-12T10:00:00Z",
        "updated_at": "2026-10-12T10:00:00Z",
        "decision_note": decision_note,
        "decided_at": decided_at,
        "students": {
            "first_name": first_name,
            "last_name": last_name,
            "gender": "female" if first_name == "Yasmine" else "male",
            "card_id": card_id,
        },
    }
    if staff_name:
        row["decided_by"] = "staff-1"
        row["staff"] = {"full_name": staff_name}
    return row


def row_index(page, request_id):
    return next(
        index for index, row in enumerate(page.rows)
        if str(row.get("id")) == str(request_id)
    )


def patch_reject_prompt(monkeypatch, reason="Room is needed by another resident"):
    calls = []

    def prompt(*_args, **_kwargs):
        calls.append(1)
        return reason, True

    monkeypatch.setattr(room_changes_mod.QInputDialog, "getMultiLineText", prompt)
    return calls


# --------------------------------------------------------------- rejection
def test_reject_keeps_row_switches_to_rejected_and_shows_desk_record(qapp, monkeypatch):
    client = FakeClient(requests=[request_row()])
    patch_reject_prompt(monkeypatch)

    page = RoomChangesPage(client)
    assert page.filter_mode == "pending"
    page.table.selectRow(0)
    assert page.selected()["id"] == "rcr-1"

    page.on_reject()
    assert wait_until(qapp, lambda: not page._working and page.filter_mode == "rejected")

    # The RPC result must never delete the row from the local data.
    assert len(page.all_rows) == 1
    assert page.all_rows[0]["id"] == "rcr-1"
    assert page.all_rows[0]["status"] == "rejected"
    assert len(client.tables["room_change_requests"]) == 1
    assert client.rpc_calls == [
        (
            "reject_room_change",
            {"p_request": "rcr-1", "p_reason": "Room is needed by another resident"},
        )
    ]

    # Rejected view lists it and selects it immediately.
    assert page.filter_mode == "rejected"
    assert page.selected() is not None
    assert page.selected()["id"] == "rcr-1"
    assert page.table.isRowHidden(row_index(page, "rcr-1")) is False

    # Counts follow every view (zeros hide the count badge).
    assert "1" in page.btn_rejected.text()
    assert "1" in page.btn_all.text()
    assert page.btn_pending.text() == "Pending"

    # Desk-inquiry rejection card: reason, decider, date, student, rooms, motive.
    assert page.rejection_card.isHidden() is False
    assert page.rejection_overline.text() == "Rejection reason (desk inquiry reference)"
    assert "Room is needed by another resident" in page.rejection_body.text()
    assert "Nadia Haddad" in page.rejection_meta.text()
    assert SHOWN_STAMP in page.rejection_meta.text()
    assert "Walid Khelifi" in page.rejection_student_label.text()
    assert "202437010009" in page.rejection_student_label.text()
    assert "room-current" in page.rejection_rooms_label.text()
    assert "room-preferred" in page.rejection_rooms_label.text()
    assert "Quiet study environment" in page.rejection_motive_label.text()

    detail = page.detail_text.toPlainText()
    assert "REJECTION REASON (Desk Inquiry Reference)" in detail
    assert "Room is needed by another resident" in detail
    assert "Nadia Haddad" in detail
    assert SHOWN_STAMP in detail

    # Processed rows cannot be decided again; deletion stays explicit.
    assert not page.approve_btn.isEnabled()
    assert not page.reject_btn.isEnabled()
    assert page.delete_btn.isEnabled()

    # Pending view must no longer list it; the copy follows the view.
    page.btn_pending.click()
    assert page.filter_mode == "pending"
    assert page.table.isRowHidden(row_index(page, "rcr-1")) is True
    assert page.stack.currentWidget() is page.empty_state
    assert page.empty_title_label.text() == "No pending transfer requests"

    # And it is still there under Rejected.
    page.btn_rejected.click()
    assert page.table.isRowHidden(row_index(page, "rcr-1")) is False
    assert page.table.item(row_index(page, "rcr-1"), 1).text() == "Rejected"
    page.close()


def test_reject_requires_non_empty_reason_and_keeps_pending_row(qapp, monkeypatch):
    client = FakeClient(requests=[request_row()])
    patch_reject_prompt(monkeypatch, reason="   ")

    page = RoomChangesPage(client)
    page.table.selectRow(0)
    page.on_reject()

    assert client.rpc_calls == []
    assert page.action_banner.property("kind") == "warning"
    assert "rejection reason is required" in page.action_banner._message.text().lower()
    assert page.filter_mode == "pending"
    assert page.all_rows[0]["status"] == "pending"
    page.close()


# ---------------------------------------------------------------- approval
def test_approve_keeps_row_and_switches_to_approved_view(qapp, monkeypatch):
    client = FakeClient(requests=[request_row()], students=[])
    client.tables["rooms"] = [{
        "id": "room-new", "block": "B", "number": "12", "floor": 1,
        "capacity": 2, "gender": "male",
    }]
    monkeypatch.setattr(
        room_changes_mod.QInputDialog,
        "getItem",
        lambda *_args, **_kwargs: ("Block B — Room 12 (2/2 free) | id=room-new", True),
    )

    page = RoomChangesPage(client)
    page.table.selectRow(0)
    page.on_approve()

    assert wait_until(qapp, lambda: not page._working and page.filter_mode == "approved")
    assert len(page.all_rows) == 1
    assert page.all_rows[0]["status"] == "approved"
    assert page.selected()["id"] == "rcr-1"
    assert page.table.isRowHidden(row_index(page, "rcr-1")) is False
    assert not page.approve_btn.isEnabled()
    assert not page.reject_btn.isEnabled()
    page.close()


# ------------------------------------------- decision vs. stale snapshots
def test_rpc_row_accepts_dict_and_single_item_list():
    assert room_changes_mod._rpc_row(FakeResponse({"id": "rcr-1"})) == {"id": "rcr-1"}
    assert room_changes_mod._rpc_row(FakeResponse([{"id": "rcr-1"}])) == {"id": "rcr-1"}


def test_reject_rpc_row_wins_over_stale_pending_snapshot(qapp, monkeypatch):
    """The RPC row is the source of truth even when the refetch still says pending."""
    pending = request_row(reason="Quiet study environment")
    client = FakeClient(requests=[pending])
    patch_reject_prompt(monkeypatch, reason="No capacity in the requested block")

    page = RoomChangesPage(client)
    stale = deepcopy(pending)
    stale_without_embeds = deepcopy(stale)
    stale_without_embeds.pop("students")
    # The follow-up read replica has not caught up yet.
    page._fetch_requests = lambda: [stale_without_embeds]

    page.table.selectRow(0)
    page.on_reject()
    assert wait_until(qapp, lambda: not page._working and page.filter_mode == "rejected")

    assert len(page.all_rows) == 1
    assert page.all_rows[0]["status"] == "rejected"
    assert page.all_rows[0]["decision_note"] == "No capacity in the requested block"
    assert page.filter_mode == "rejected"
    assert page.selected()["id"] == "rcr-1"
    assert page.table.isRowHidden(row_index(page, "rcr-1")) is False
    # The RPC row has no joins; the locally held students embed is preserved.
    assert _student_name(page.selected()) == "Walid Khelifi"
    assert "No capacity in the requested block" in page.rejection_body.text()
    assert "Rejected" == page.table.item(row_index(page, "rcr-1"), 1).text()

    # A later stale live tick and a stale manual refresh never regress it.
    page.apply_live_data([deepcopy(stale)])
    assert page.all_rows[0]["status"] == "rejected"
    assert page.all_rows[0]["decision_note"] == "No capacity in the requested block"
    assert page.selected()["status"] == "rejected"
    assert page.filter_mode == "rejected"

    page._apply_snapshot([deepcopy(stale)])
    assert page.all_rows[0]["status"] == "rejected"
    assert page.all_rows[0]["decision_note"] == "No capacity in the requested block"
    assert page.selected()["status"] == "rejected"
    assert page.filter_mode == "rejected"
    page.close()


def test_approve_rpc_row_wins_over_stale_pending_snapshot(qapp, monkeypatch):
    pending = request_row()
    client = FakeClient(requests=[pending], students=[])
    client.tables["rooms"] = [{
        "id": "room-new", "block": "B", "number": "12", "floor": 1,
        "capacity": 2, "gender": "male",
    }]
    monkeypatch.setattr(
        room_changes_mod.QInputDialog,
        "getItem",
        lambda *_args, **_kwargs: ("Block B — Room 12 (2/2 free) | id=room-new", True),
    )

    page = RoomChangesPage(client)
    stale = deepcopy(pending)
    stale_without_embeds = deepcopy(stale)
    stale_without_embeds.pop("students")
    page._fetch_requests = lambda: [stale_without_embeds]

    page.table.selectRow(0)
    page.on_approve()
    assert wait_until(qapp, lambda: not page._working and page.filter_mode == "approved")

    assert len(page.all_rows) == 1
    assert page.all_rows[0]["status"] == "approved"
    assert page.filter_mode == "approved"
    assert page.selected()["id"] == "rcr-1"
    assert page.table.isRowHidden(row_index(page, "rcr-1")) is False
    assert _student_name(page.selected()) == "Walid Khelifi"

    page.apply_live_data([deepcopy(stale)])
    assert page.all_rows[0]["status"] == "approved"
    assert page.selected()["status"] == "approved"
    assert page.filter_mode == "approved"

    page._apply_snapshot([deepcopy(stale)])
    assert page.all_rows[0]["status"] == "approved"
    assert page.selected()["status"] == "approved"
    assert page.filter_mode == "approved"
    page.close()


def _student_name(row):
    student = row.get("students") or {}
    if isinstance(student, list):
        student = student[0] if student else {}
    return f"{student.get('first_name', '')} {student.get('last_name', '')}".strip()


# ------------------------------------------------------- live-sync merge/UI
def test_live_refresh_preserves_rejected_row_view_search_and_selection(qapp):
    rejected = request_row(
        "rcr-1",
        status="rejected",
        decision_note="Original refusal reason",
        decided_at=STAMP,
        staff_name="Nadia Haddad",
    )
    pending = request_row(
        "rcr-2",
        status="pending",
        first_name="Yasmine",
        last_name="Mansouri",
        card_id="202437010022",
    )
    client = FakeClient(requests=[rejected, pending])
    page = RoomChangesPage(client)

    page.set_filter("rejected")
    page.search.set_text("Walid")
    page.filter_table()
    index = row_index(page, "rcr-1")
    page.table.selectRow(index)
    assert page.selected()["id"] == "rcr-1"
    assert page.rejection_body.text().find("Original refusal reason") >= 0

    updated = deepcopy(rejected)
    updated["decision_note"] = "Updated refusal reason"
    page.apply_live_data([pending, updated])

    # View, search text and selection all survive the live refresh.
    assert page.filter_mode == "rejected"
    assert page.search.text() == "Walid"
    assert page.selected() is not None
    assert page.selected()["id"] == "rcr-1"
    assert page.table.isRowHidden(row_index(page, "rcr-1")) is False
    assert "Updated refusal reason" in page.rejection_body.text()
    assert "Nadia Haddad" in page.rejection_meta.text()
    assert SHOWN_STAMP in page.rejection_meta.text()

    # The complete all-status snapshot is authoritative for membership: the
    # rejected request is absent, so it was deleted elsewhere and is removed
    # (a ghost row must never linger). View and search survive the removal.
    page.apply_live_data([pending])
    assert page.filter_mode == "rejected"
    assert page.search.text() == "Walid"
    assert [row["id"] for row in page.all_rows] == ["rcr-2"]
    assert page.selected() is None
    assert page.table.rowCount() == 1
    assert page.stack.currentWidget() is page.empty_state
    assert page.empty_title_label.text() == "No rejected transfer requests"
    assert "1" in page.btn_all.text()
    page.close()


def test_live_snapshot_removes_request_deleted_by_another_admin(qapp):
    pending = request_row("rcr-1", status="pending")
    rejected = request_row(
        "rcr-2",
        status="rejected",
        first_name="Yasmine",
        last_name="Mansouri",
        card_id="202437010022",
        decision_note="No capacity",
        decided_at=STAMP,
        staff_name="Nadia Haddad",
    )
    page = RoomChangesPage(FakeClient(requests=[pending, rejected]))

    page.set_filter("all")
    page.search.set_text("Walid")
    page.table.selectRow(row_index(page, "rcr-1"))
    assert page.selected()["id"] == "rcr-1"

    # The other admin deleted rcr-2: the complete snapshot no longer has it.
    page.apply_live_data([deepcopy(pending)])

    assert [row["id"] for row in page.all_rows] == ["rcr-1"]
    assert page.table.rowCount() == 1
    assert page.filter_mode == "all"
    assert page.search.text() == "Walid"
    assert page.selected()["id"] == "rcr-1"
    assert "1" in page.btn_all.text()
    assert page.btn_rejected.text() == "Rejected"
    page.close()


def test_search_by_name_or_card_id_combines_with_status_view(qapp):
    rows = [
        request_row("rcr-1", status="pending", first_name="Walid", last_name="Khelifi",
                    card_id="202437010009"),
        request_row("rcr-2", status="rejected", first_name="Yasmine", last_name="Mansouri",
                    card_id="202437010022", decision_note="No capacity", decided_at=STAMP,
                    staff_name="Nadia Haddad"),
        request_row("rcr-3", status="approved", first_name="Karim", last_name="Haddad",
                    card_id="202437010033"),
    ]
    page = RoomChangesPage(FakeClient(requests=rows))

    page.set_filter("all")
    page.search.set_text("yasmine")
    page.filter_table()
    assert [row["id"] for row in page.visible_rows()] == ["rcr-2"]

    page.search.set_text("202437010033")
    page.filter_table()
    assert [row["id"] for row in page.visible_rows()] == ["rcr-3"]

    # The status view still constrains the card-ID search.
    page.set_filter("pending")
    assert page.visible_rows() == []
    assert page.stack.currentWidget() is page.empty_state
    assert page.empty_title_label.text() == "No pending transfer requests"

    page.search.set_text("202437010022")
    page.set_filter("rejected")
    assert [row["id"] for row in page.visible_rows()] == ["rcr-2"]
    page.close()


def test_search_matches_reason_and_decision_note(qapp):
    rows = [
        request_row("rcr-1", status="pending", reason="Needs a quiet study room"),
        request_row(
            "rcr-2",
            status="rejected",
            first_name="Yasmine",
            last_name="Mansouri",
            card_id="202437010022",
            reason="Closer to family",
            decision_note="No capacity in the requested block",
            decided_at=STAMP,
            staff_name="Nadia Haddad",
        ),
    ]
    page = RoomChangesPage(FakeClient(requests=rows))
    page.set_filter("all")

    page.search.set_text("quiet study")
    page.filter_table()
    assert [row["id"] for row in page.visible_rows()] == ["rcr-1"]

    page.search.set_text("capacity")
    page.filter_table()
    assert [row["id"] for row in page.visible_rows()] == ["rcr-2"]

    page.search.set_text("closer to family")
    page.filter_table()
    assert [row["id"] for row in page.visible_rows()] == ["rcr-2"]

    page.search.set_text("no such text")
    page.filter_table()
    assert page.visible_rows() == []
    assert page.stack.currentWidget() is page.empty_state
    page.close()


def test_non_pending_rows_cannot_be_approved_or_rejected(qapp, monkeypatch):
    rows = [
        request_row("rcr-1", status="approved", decision_note=None, decided_at=STAMP,
                    staff_name="Nadia Haddad"),
        request_row("rcr-2", status="rejected", decision_note="No capacity",
                    decided_at=STAMP, staff_name="Nadia Haddad"),
    ]
    client = FakeClient(requests=rows)
    prompts = patch_reject_prompt(monkeypatch)
    monkeypatch.setattr(
        room_changes_mod.QInputDialog,
        "getItem",
        lambda *_args, **_kwargs: pytest.fail("room picker must not open"),
    )

    page = RoomChangesPage(client)
    page.set_filter("all")

    for request_id in ("rcr-1", "rcr-2"):
        page.table.selectRow(row_index(page, request_id))
        assert not page.approve_btn.isEnabled()
        assert not page.reject_btn.isEnabled()
        page.on_approve()
        page.on_reject()

    assert client.rpc_calls == []
    assert prompts == []
    assert page.action_banner.property("kind") == "warning"
    assert "Only pending" in page.action_banner._message.text()
    page.close()


def test_delete_removes_row_locally_without_refetch(qapp, monkeypatch):
    client = FakeClient(requests=[
        request_row("rcr-1"),
        request_row("rcr-2", first_name="Yasmine", last_name="Mansouri",
                    card_id="202437010022"),
    ])
    monkeypatch.setattr(room_changes_mod.ConfirmDialog, "ask", lambda *_args, **_kwargs: True)

    page = RoomChangesPage(client)
    page.set_filter("all")
    page.table.selectRow(0)
    assert page.selected()["id"] == "rcr-1"

    client.room_change_selects = 0
    refetches = []
    page._fetch_requests = lambda: refetches.append(1) or []
    page.on_delete()
    assert wait_until(qapp, lambda: not page._working)

    # No refetch at all, so a stale read cannot re-seed the deleted row.
    assert refetches == []
    assert client.room_change_selects == 0
    assert [row["id"] for row in page.all_rows] == ["rcr-2"]
    assert [row["id"] for row in client.tables["room_change_requests"]] == ["rcr-2"]
    assert page.table.rowCount() == 1
    assert page.filter_mode == "all"
    assert page.selected() is None
    assert not page.delete_btn.isEnabled()
    assert page.action_banner.property("kind") == "success"
    page.close()


def test_delete_tombstone_blocks_stale_snapshot_resurrection(qapp, monkeypatch):
    client = FakeClient(requests=[
        request_row("rcr-1"),
        request_row("rcr-2", first_name="Yasmine", last_name="Mansouri"),
    ])
    monkeypatch.setattr(room_changes_mod.ConfirmDialog, "ask", lambda *_args, **_kwargs: True)

    page = RoomChangesPage(client)
    page.set_filter("all")
    page.table.selectRow(row_index(page, "rcr-1"))
    page.on_delete()
    assert wait_until(qapp, lambda: not page._working)
    assert [row["id"] for row in page.all_rows] == ["rcr-2"]

    # A read that started before the delete still carries the deleted row.
    stale = [
        request_row("rcr-1"),
        request_row("rcr-2", first_name="Yasmine", last_name="Mansouri",
                    reason="Closer to the study hall"),
    ]
    page._apply_snapshot(stale)
    assert [row["id"] for row in page.all_rows] == ["rcr-2"]

    # The next live tick (with a real change) must not resurrect it either.
    live = deepcopy(stale)
    live[1]["updated_at"] = "2026-10-21T08:00:00Z"
    page.apply_live_data(live)
    assert [row["id"] for row in page.all_rows] == ["rcr-2"]
    assert page.table.rowCount() == 1
    assert page.filter_mode == "all"
    page.close()


def test_delete_of_already_removed_row_is_not_reported_as_success(
    qapp, monkeypatch
):
    client = FakeClient(requests=[request_row("rcr-1")])
    monkeypatch.setattr(room_changes_mod.ConfirmDialog, "ask", lambda *_args, **_kwargs: True)

    page = RoomChangesPage(client)
    page.set_filter("all")
    page.table.selectRow(0)
    # Another administrator deleted the request after this client loaded it.
    client.tables["room_change_requests"].clear()

    page.on_delete()
    assert wait_until(qapp, lambda: not page._working)

    assert page.all_rows == []
    assert page.table.rowCount() == 0
    assert page.action_banner.property("kind") == "warning"
    message = page.action_banner._message.text()
    assert "no longer exists" in message
    assert "successfully" not in message
    page.close()


# --------------------------------------- committed decision, failed refresh
def test_reject_survives_a_failed_follow_up_snapshot(qapp, monkeypatch):
    client = FakeClient(requests=[request_row()])
    patch_reject_prompt(monkeypatch, reason="No capacity in the requested block")
    page = RoomChangesPage(client)
    page.table.selectRow(0)

    def fail_fetch():
        raise RuntimeError("read replica offline")

    page._fetch_requests = fail_fetch
    page.on_reject()
    assert wait_until(qapp, lambda: not page._working)

    # The RPC row is applied even though the follow-up read failed.
    assert len(page.all_rows) == 1
    assert page.all_rows[0]["status"] == "rejected"
    assert page.all_rows[0]["decision_note"] == "No capacity in the requested block"
    assert page.filter_mode == "rejected"
    assert page.selected()["id"] == "rcr-1"
    assert page.action_banner.property("kind") == "success"
    assert not page.error_banner.isHidden()
    assert "read replica offline" in page.error_banner._message.text()
    page.close()


def test_approve_survives_a_failed_follow_up_snapshot(qapp, monkeypatch):
    client = FakeClient(requests=[request_row()], students=[])
    client.tables["rooms"] = [{
        "id": "room-new", "block": "B", "number": "12", "floor": 1,
        "capacity": 2, "gender": "male",
    }]
    monkeypatch.setattr(
        room_changes_mod.QInputDialog,
        "getItem",
        lambda *_args, **_kwargs: ("Block B — Room 12 (2/2 free) | id=room-new", True),
    )
    page = RoomChangesPage(client)
    page.table.selectRow(0)

    def fail_fetch():
        raise RuntimeError("read replica offline")

    page._fetch_requests = fail_fetch
    page.on_approve()
    assert wait_until(qapp, lambda: not page._working)

    assert len(page.all_rows) == 1
    assert page.all_rows[0]["status"] == "approved"
    assert page.filter_mode == "approved"
    assert page.selected()["id"] == "rcr-1"
    assert page.action_banner.property("kind") == "success"
    assert not page.error_banner.isHidden()
    assert "read replica offline" in page.error_banner._message.text()
    page.close()


# ------------------------------------------------------------ badge / worker
def test_live_sync_worker_fetches_all_statuses(qapp):
    rows = [
        request_row("rcr-1", status="pending"),
        request_row("rcr-2", status="rejected", decision_note="No capacity",
                    decided_at=STAMP, staff_name="Nadia Haddad"),
        request_row("rcr-3", status="approved", decided_at=STAMP,
                    staff_name="Nadia Haddad"),
    ]
    client = FakeClient(
        requests=rows,
        students=[{"id": "s-1", "first_name": "Amine", "last_name": "Benali",
                   "card_id": "202437010001", "status": "pending"}],
        reports=[],
    )
    worker = LiveSyncWorker(client, interval_ms=10)
    payloads = []
    worker.sync_tick.connect(payloads.append)
    worker.start()
    try:
        assert wait_until(qapp, lambda: bool(payloads))
    finally:
        worker.stop()
        assert worker.wait(3000)
    qapp.processEvents()

    payload = payloads[0]
    statuses = {row["id"]: row["status"] for row in payload["pending_requests"]}
    assert statuses == {"rcr-1": "pending", "rcr-2": "rejected", "rcr-3": "approved"}
    assert payload["room_change_requests"] == payload["pending_requests"]


def test_main_window_badge_counts_only_pending_and_passes_all_rows():
    class _ShellStub:
        def __init__(self):
            self.status_bar = MagicMock()
            self.nav = MagicMock()
            self.overview_page = MagicMock()
            self.pending_page = MagicMock()
            self.maintenance_page = MagicMock()
            self.room_changes_page = MagicMock()
            self._last_tick_at = None
            self.live_state = None

        def _set_live_state(self, state):
            self.live_state = state

    rows = [
        request_row("rcr-1", status="pending"),
        request_row("rcr-2", status="rejected", decision_note="No capacity",
                    decided_at=STAMP, staff_name="Nadia Haddad"),
        request_row("rcr-3", status="approved", decided_at=STAMP,
                    staff_name="Nadia Haddad"),
    ]
    shell = _ShellStub()
    MainWindow.on_live_sync_tick(shell, {
        "pending_students": [],
        "reports": [],
        "open_reports_count": 0,
        "room_change_requests": rows,
        "timestamp": "12:00:00",
    })

    shell.nav.set_badge.assert_any_call("room_changes", 1)
    shell.room_changes_page.apply_live_data.assert_called_once_with(rows)
    shell.overview_page.apply_live_data.assert_called_once_with(0, 0, 1, None)
    message = shell.status_bar.showMessage.call_args[0][0]
    assert "Transfers: 1" in message
