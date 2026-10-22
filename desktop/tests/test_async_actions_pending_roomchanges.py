"""Async action safety for the pending and room-change pages.

The GUI thread must return immediately when a decision handler is invoked, the
network work must run on ``TaskRunner``'s thread pool, and controls/data must be
restored on both success and failure.
"""

import os
import time
from copy import deepcopy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QDialog

from desktop.app.ui.pages import pending as pending_mod
from desktop.app.ui.pages import room_changes as room_changes_mod
from desktop.app.ui.pages.pending import PendingPage
from desktop.app.ui.pages.room_changes import RoomChangesPage


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
    def __init__(self, data):
        self.data = data


class FakeQuery:
    """Small postgrest-ish fake; every builder call returns itself."""

    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self._eq = []
        self._single = False
        self._delete = False

    def select(self, *_args, **_kwargs):
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
        delay = self.client.table_delays.get(self.table_name, 0)
        if delay:
            time.sleep(delay)

        if self._delete:
            self.client.delete_calls.append(self.table_name)
            if self.client.delete_data_none:
                return FakeResponse(None)
            rows = self.client.data_for(self.table_name)
            removed = [
                row for row in list(rows)
                if all(row.get(column) == value for column, value in self._eq)
            ]
            for row in removed:
                rows.remove(row)
            # PostgREST represents deletes: an empty list means no row matched.
            return FakeResponse(deepcopy(removed))

        if self.client.read_error is not None and self.table_name == "students":
            raise self.client.read_error

        rows = deepcopy(self.client.data_for(self.table_name))
        if self._single:
            return FakeResponse(rows[0] if rows else None)
        return FakeResponse(rows)


class FakeRpcCall:
    def __init__(self, client, name, params):
        self.client = client
        self.name = name
        self.params = params

    def execute(self):
        self.client.rpc_calls.append((self.name, deepcopy(self.params)))
        if self.client.rpc_delay:
            time.sleep(self.client.rpc_delay)
        if self.client.rpc_error is not None:
            raise self.client.rpc_error
        if self.name in ("reject_room_change", "approve_room_change"):
            row = self.client.request(self.params.get("p_request"))
            if row is None:
                raise RuntimeError("pending request not found")
            updated = deepcopy(row)
            if self.name == "reject_room_change":
                updated.update({
                    "status": "rejected",
                    "decision_note": self.params.get("p_reason"),
                    "decided_by": "staff-1",
                    "decided_at": "2026-10-20T14:30:00Z",
                })
            else:
                updated.update({
                    "status": "approved",
                    "decision_note": None,
                    "decided_by": "staff-1",
                    "decided_at": "2026-10-20T14:30:00Z",
                })
            row.update(updated)
            # The real RPC returns the bare table row, without select() joins.
            updated.pop("students", None)
            updated.pop("staff", None)
            return FakeResponse(updated)
        if self.name in ("approve_student", "reject_student"):
            student_id = self.params.get("p_student")
            row = next(
                (item for item in self.client.data_for("students")
                 if str(item.get("id")) == str(student_id)),
                None,
            )
            if row is None:
                raise RuntimeError("student not found")
            if self.name == "approve_student":
                row.update({
                    "status": "active",
                    "room_id": self.params.get("p_room"),
                    "rejection_reason": None,
                    "reviewed_by": "staff-1",
                    "reviewed_at": "2026-10-20T14:30:00Z",
                })
            else:
                row.update({
                    "status": "rejected",
                    "room_id": None,
                    "rejection_reason": self.params.get("p_reason"),
                    "reviewed_by": "staff-1",
                    "reviewed_at": "2026-10-20T14:30:00Z",
                })
            return FakeResponse(deepcopy(row))
        if self.name == "delete_student":
            student_id = str(self.params.get("p_student"))
            rows = self.client.data_for("students")
            row = next(
                (item for item in rows if str(item.get("id")) == student_id),
                None,
            )
            if row is None:
                raise RuntimeError("student not found")
            if row.get("status") == "pending":
                raise RuntimeError(
                    "cannot delete pending application; approve or reject first"
                )
            rows.remove(row)
            return FakeResponse(None)
        return FakeResponse(None)


class FakeClient:
    def __init__(self, students=None, rooms=None, requests=None):
        self.tables = {
            "students": list(students or []),
            "rooms": list(rooms or []),
            "room_change_requests": list(requests or []),
        }
        self.table_delays = {}
        self.rpc_delay = 0.0
        self.rpc_error = None
        self.rpc_calls = []
        self.read_error = None
        self.delete_calls = []
        self.delete_data_none = False

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


def student(
    student_id="s-1",
    status="pending",
    first_name="Amine",
    last_name="Benali",
    gender="male",
    card_id="202437010001",
):
    return {
        "id": student_id,
        "card_id": card_id,
        "first_name": first_name,
        "last_name": last_name,
        "gender": gender,
        "status": status,
        "university": "Université Abou Bekr Belkaïd - Tlemcen",
        "faculty": "Faculté de Technologie",
        "birth_date": "2003-04-12",
        "phone": "0550123456",
        "email": "student@test.dz",
        "study_level": "L3",
        "wilaya": "Tlemcen",
        "created_at": "2026-10-10T12:00:00Z",
    }


def request_row(request_id="rcr-1", status="pending", first_name="Walid", last_name="Khelifi"):
    return {
        "id": request_id,
        "student_id": "st-1",
        "reason": "Quiet study environment",
        "status": status,
        "created_at": "2026-10-12T10:00:00Z",
        "students": {
            "first_name": first_name,
            "last_name": last_name,
            "gender": "male",
            "card_id": "202437010009",
        },
    }


def room(room_id="r-1"):
    return {
        "id": room_id,
        "block": "A",
        "number": "01",
        "floor": 1,
        "capacity": 2,
        "gender": "male",
    }


@pytest.fixture
def pending_env(monkeypatch):
    monkeypatch.setattr(pending_mod, "official_lookup", lambda _client: {})
    monkeypatch.setattr(pending_mod, "room_occupancy", lambda _client: {})


@pytest.fixture
def room_changes_env(monkeypatch):
    monkeypatch.setattr(room_changes_mod, "official_lookup", lambda _client: {})
    monkeypatch.setattr(room_changes_mod, "room_occupancy", lambda _client: {})


def patch_pending_reject_prompt(monkeypatch, reason="Missing residence certificate"):
    calls = []

    def prompt(*_args, **_kwargs):
        calls.append(1)
        return reason, True

    monkeypatch.setattr(pending_mod.QInputDialog, "getMultiLineText", prompt)
    return calls


def patch_room_changes_reject_prompt(monkeypatch, reason="Not eligible for a transfer"):
    calls = []

    def prompt(*_args, **_kwargs):
        calls.append(1)
        return reason, True

    monkeypatch.setattr(room_changes_mod.QInputDialog, "getMultiLineText", prompt)
    return calls


# --------------------------------------------------------------- pending page
def test_pending_reject_returns_immediately_and_restores_controls(qapp, pending_env, monkeypatch):
    client = FakeClient(students=[student()])
    client.rpc_delay = 0.45
    patch_pending_reject_prompt(monkeypatch)

    page = PendingPage(client)
    page.set_filter("all")
    page.table.selectRow(0)
    assert page.reject_btn.isEnabled()

    started = time.monotonic()
    page.on_reject()
    elapsed = time.monotonic() - started

    assert elapsed < 0.25
    assert not page.approve_btn.isEnabled()
    assert not page.reject_btn.isEnabled()
    assert not page.delete_btn.isEnabled()
    assert not page.refresh_btn.isEnabled()
    assert not page.busy_banner.isHidden()
    assert "Working" in page.busy_banner._title.text()

    # A selection/detail repaint during the action must not re-enable controls.
    page.show_detail()
    assert not page.reject_btn.isEnabled()

    assert wait_until(qapp, lambda: not page._working)
    assert len(client.rpc_calls) == 1
    assert client.rpc_calls[0] == (
        "reject_student",
        {"p_student": "s-1", "p_reason": "Missing residence certificate"},
    )
    assert page.reject_btn.isEnabled()
    assert page.busy_banner.isHidden()
    assert page.action_banner.property("kind") == "success"
    page.close()


def test_pending_approve_loads_rooms_then_runs_rpc_off_thread(qapp, pending_env, monkeypatch):
    client = FakeClient(students=[student()], rooms=[room()])
    client.table_delays["rooms"] = 0.15
    client.rpc_delay = 0.4
    monkeypatch.setattr(
        pending_mod.RoomAllocationDialog,
        "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        pending_mod.RoomAllocationDialog,
        "selected_room",
        lambda self: self._rooms[0],
    )
    monkeypatch.setattr(
        pending_mod.RoomAllocationDialog,
        "selected_room_id",
        lambda self: self._rooms[0]["id"],
    )

    page = PendingPage(client)
    page.set_filter("all")
    page.table.selectRow(0)

    started = time.monotonic()
    page.on_approve()
    elapsed = time.monotonic() - started

    assert elapsed < 0.25
    assert not page.approve_btn.isEnabled()
    assert not page.busy_banner.isHidden()

    assert wait_until(qapp, lambda: len(client.rpc_calls) == 1)
    assert wait_until(qapp, lambda: not page._working)
    assert client.rpc_calls[0] == (
        "approve_student",
        {"p_student": "s-1", "p_room": "r-1"},
    )
    # The RPC row is authoritative: the student is active even though the
    # follow-up snapshot/filter may still have shown the old pending frame.
    assert page.selected()["status"] == "active"
    assert not page.approve_btn.isEnabled()
    assert page.busy_banner.isHidden()
    page.close()


def test_pending_reject_failure_shows_inline_message_and_recovers(qapp, pending_env, monkeypatch):
    client = FakeClient(students=[student()])
    client.rpc_error = RuntimeError("permission denied by the server")
    patch_pending_reject_prompt(monkeypatch)

    page = PendingPage(client)
    page.table.selectRow(0)
    page.on_reject()

    assert wait_until(qapp, lambda: not page._working)
    assert page.action_banner.property("kind") == "error"
    assert "permission denied by the server" in page.action_banner._message.text()
    assert "Traceback" not in page.action_banner._message.text()
    assert page.reject_btn.isEnabled()
    assert page.table.rowCount() == 1
    assert page.selected()["id"] == "s-1"
    page.close()


def test_pending_double_invocation_calls_rpc_once(qapp, pending_env, monkeypatch):
    client = FakeClient(students=[student()])
    client.rpc_delay = 0.3
    prompts = patch_pending_reject_prompt(monkeypatch)

    page = PendingPage(client)
    page.table.selectRow(0)
    page.on_reject()
    page.on_reject()

    assert len(prompts) == 1
    assert wait_until(qapp, lambda: not page._working)
    assert len(client.rpc_calls) == 1
    page.close()


def test_pending_delete_with_disappearing_selection_does_not_crash(qapp, pending_env, monkeypatch):
    client = FakeClient(
        students=[
            student(student_id="s-2", status="active", card_id="202437010002"),
            student(
                student_id="s-3",
                status="active",
                first_name="Yasmine",
                last_name="Mansouri",
                gender="female",
                card_id="202437010003",
            ),
        ]
    )
    client.rpc_delay = 0.15
    monkeypatch.setattr(pending_mod.ConfirmDialog, "ask", lambda *_args, **_kwargs: True)

    page = PendingPage(client)
    page.set_filter("all")
    page.table.selectRow(0)
    assert page.selected()["id"] == "s-2"

    page.on_delete()
    # Another resident disappears while the delete worker is still running; the
    # old current index must not start inspecting a different row.
    client.tables["students"] = [
        row for row in client.tables["students"] if row["id"] == "s-2"
    ]

    assert wait_until(qapp, lambda: not page._working)
    assert page.table.rowCount() == 1
    assert page.selected() is None
    page.show_detail()  # stale selection must stay safe
    assert not page.delete_btn.isEnabled()
    assert page.action_banner.property("kind") == "success"
    page.close()


def test_pending_delete_failure_keeps_row_and_never_falls_back_to_table(
    qapp, pending_env, monkeypatch
):
    client = FakeClient(students=[student(student_id="s-4", status="active")])
    client.rpc_error = RuntimeError("not authorized")
    monkeypatch.setattr(pending_mod.ConfirmDialog, "ask", lambda *_args, **_kwargs: True)

    page = PendingPage(client)
    page.set_filter("all")
    page.table.selectRow(0)
    page.on_delete()

    assert wait_until(qapp, lambda: not page._working)
    assert page.action_banner.property("kind") == "error"
    assert "not authorized" in page.action_banner._message.text()
    assert page.table.rowCount() == 1
    assert page.selected()["id"] == "s-4"
    # A raw students-table delete would bypass delete_student's guards.
    assert client.delete_calls == []
    page.close()


def test_pending_delete_that_matched_no_row_reports_failure(
    qapp, pending_env, monkeypatch
):
    client = FakeClient(students=[student(student_id="s-6", status="active")])
    monkeypatch.setattr(pending_mod.ConfirmDialog, "ask", lambda *_args, **_kwargs: True)

    page = PendingPage(client)
    page.set_filter("all")
    page.table.selectRow(0)
    # The row was removed elsewhere after the table was loaded.
    client.tables["students"] = []
    page.on_delete()

    assert wait_until(qapp, lambda: not page._working)
    assert page.action_banner.property("kind") == "error"
    assert "student not found" in page.action_banner._message.text()
    assert page.table.rowCount() == 1
    assert client.delete_calls == []
    page.close()


def test_pending_delete_removes_locally_and_tombstones_stale_snapshot(
    qapp, pending_env, monkeypatch
):
    client = FakeClient(students=[student(student_id="s-5", status="active")])
    monkeypatch.setattr(pending_mod.ConfirmDialog, "ask", lambda *_args, **_kwargs: True)

    page = PendingPage(client)
    page.set_filter("all")
    page.table.selectRow(0)
    page.on_delete()

    assert wait_until(qapp, lambda: not page._working)
    assert page.table.rowCount() == 0
    assert page.action_banner.property("kind") == "success"
    assert "s-5" in page._deleted_ids
    assert client.delete_calls == []

    # A late snapshot still carrying the deleted student must not resurrect it.
    page._apply_snapshot(([student(student_id="s-5", status="active")], {}))
    assert page.table.rowCount() == 0
    assert page.all_rows == []
    page.close()


def test_pending_reject_success_survives_a_failed_follow_up_refresh(
    qapp, pending_env, monkeypatch
):
    client = FakeClient(students=[student()])
    patch_pending_reject_prompt(monkeypatch)

    page = PendingPage(client)
    page.set_filter("all")
    page.table.selectRow(0)
    client.read_error = RuntimeError("read timed out")

    page.on_reject()

    assert wait_until(qapp, lambda: not page._working)
    assert page.action_banner.property("kind") == "warning"
    assert "could not be refreshed" in page.action_banner._message.text()
    assert "read timed out" in page.action_banner._message.text()
    assert page.table.rowCount() == 1
    assert page.selected()["id"] == "s-1"
    assert page.selected()["status"] == "rejected"
    assert page.selected()["rejection_reason"] == "Missing residence certificate"
    page.close()


def test_pending_stale_live_tick_cannot_regress_or_duplicate_a_decision(
    qapp, pending_env, monkeypatch
):
    client = FakeClient(students=[student()])
    patch_pending_reject_prompt(monkeypatch)

    page = PendingPage(client)
    page.set_filter("all")
    page.table.selectRow(0)
    stale = deepcopy(student())
    page.on_reject()
    assert wait_until(qapp, lambda: not page._working)
    assert page.selected()["status"] == "rejected"

    page.apply_live_data([stale, deepcopy(stale)])

    assert page.table.rowCount() == 1
    assert len(page.all_rows) == 1
    assert page.all_rows[0]["status"] == "rejected"

    # A genuinely new application is still added exactly once.
    newcomer = student(student_id="s-9", card_id="202437010099", first_name="Nadia")
    page.apply_live_data([newcomer])
    assert page.table.rowCount() == 2
    assert sorted(row["id"] for row in page.all_rows) == ["s-1", "s-9"]
    page.close()


# ----------------------------------------------------------- room-change page
def test_room_changes_reject_returns_immediately_and_restores_controls(
    qapp, room_changes_env, monkeypatch
):
    client = FakeClient(requests=[request_row()])
    client.rpc_delay = 0.45
    patch_room_changes_reject_prompt(monkeypatch)

    page = RoomChangesPage(client)
    page.table.selectRow(0)

    started = time.monotonic()
    page.on_reject()
    elapsed = time.monotonic() - started

    assert elapsed < 0.25
    assert not page.approve_btn.isEnabled()
    assert not page.reject_btn.isEnabled()
    assert not page.delete_btn.isEnabled()
    assert not page.busy_banner.isHidden()

    assert wait_until(qapp, lambda: not page._working)
    assert len(client.rpc_calls) == 1
    assert client.rpc_calls[0] == (
        "reject_room_change",
        {"p_request": "rcr-1", "p_reason": "Not eligible for a transfer"},
    )
    assert page.refresh_btn.isEnabled()
    assert page.busy_banner.isHidden()
    assert page.action_banner.property("kind") == "success"
    assert page.filter_mode == "rejected"
    assert page.all_rows[0]["status"] == "rejected"
    assert not page.reject_btn.isEnabled()
    page.close()


def test_room_changes_approve_loads_rooms_then_runs_rpc_off_thread(
    qapp, room_changes_env, monkeypatch
):
    client = FakeClient(requests=[request_row()], rooms=[room(room_id="room-1")])
    client.table_delays["rooms"] = 0.15
    client.rpc_delay = 0.4
    monkeypatch.setattr(
        room_changes_mod.QInputDialog,
        "getItem",
        lambda *_args, **_kwargs: (
            "Block A — Room 01 (2/2 free) | id=room-1",
            True,
        ),
    )

    page = RoomChangesPage(client)
    page.table.selectRow(0)

    started = time.monotonic()
    page.on_approve()
    elapsed = time.monotonic() - started

    assert elapsed < 0.25
    assert not page.approve_btn.isEnabled()

    assert wait_until(qapp, lambda: len(client.rpc_calls) == 1)
    assert wait_until(qapp, lambda: not page._working)
    assert client.rpc_calls[0] == (
        "approve_room_change",
        {"p_request": "rcr-1", "p_room": "room-1"},
    )
    assert page.filter_mode == "approved"
    assert page.all_rows[0]["status"] == "approved"
    assert not page.approve_btn.isEnabled()
    page.close()


def test_room_changes_actions_reject_non_pending_rows(qapp, room_changes_env):
    client = FakeClient(requests=[])
    page = RoomChangesPage(client)
    page.apply_live_data([request_row(status="approved")])
    page.table.selectRow(0)

    page.on_approve()
    page.on_reject()

    assert client.rpc_calls == []
    assert page.action_banner.property("kind") == "warning"
    assert "Only pending" in page.action_banner._message.text()
    page.close()


def test_room_changes_reject_failure_shows_inline_message(qapp, room_changes_env, monkeypatch):
    client = FakeClient(requests=[request_row()])
    client.rpc_error = RuntimeError("session expired")
    patch_room_changes_reject_prompt(monkeypatch)

    page = RoomChangesPage(client)
    page.table.selectRow(0)
    page.on_reject()

    assert wait_until(qapp, lambda: not page._working)
    assert page.action_banner.property("kind") == "error"
    assert "session expired" in page.action_banner._message.text()
    assert page.table.rowCount() == 1
    assert page.selected()["id"] == "rcr-1"
    assert page.reject_btn.isEnabled()
    page.close()


def test_room_changes_delete_with_disappearing_selection_does_not_crash(
    qapp, room_changes_env, monkeypatch
):
    client = FakeClient(
        requests=[
            request_row(),
            request_row(request_id="rcr-2", first_name="Yasmine", last_name="Mansouri"),
        ]
    )
    client.table_delays["room_change_requests"] = 0.15
    monkeypatch.setattr(room_changes_mod.ConfirmDialog, "ask", lambda *_args, **_kwargs: True)

    page = RoomChangesPage(client)
    page.table.selectRow(0)
    assert page.selected()["id"] == "rcr-1"

    page.on_delete()
    # The deleted request disappears; the remaining request takes its row index.
    client.tables["room_change_requests"] = client.tables["room_change_requests"][1:]

    assert wait_until(qapp, lambda: not page._working)
    assert page.table.rowCount() == 1
    assert page.selected() is None
    page.show_detail()
    assert not page.delete_btn.isEnabled()
    # The row disappeared during the delete: the DELETE matched nothing, so
    # the page reports "already removed" instead of claiming success.
    assert page.action_banner.property("kind") == "warning"
    assert "no longer exists" in page.action_banner._message.text()
    page.close()


def test_room_changes_delete_without_representation_is_not_success(
    qapp, room_changes_env, monkeypatch
):
    client = FakeClient(requests=[request_row()])
    client.delete_data_none = True
    monkeypatch.setattr(room_changes_mod.ConfirmDialog, "ask", lambda *_args, **_kwargs: True)

    page = RoomChangesPage(client)
    page.table.selectRow(0)
    page.on_delete()

    assert wait_until(qapp, lambda: not page._working)
    assert page.action_banner.property("kind") == "error"
    assert "did not confirm" in page.action_banner._message.text()
    assert page.table.rowCount() == 1
    assert page.selected()["id"] == "rcr-1"
    assert page._deleted_ids == set()
    page.close()
