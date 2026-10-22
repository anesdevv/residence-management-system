"""Async action safety for the maintenance and rooms pages.

Every Supabase call started by a page action must leave the GUI thread, reject
duplicate submissions, and restore the controls with a human-readable message
on failure.  These tests use a tiny in-memory Supabase double and the real
``TaskRunner`` (Qt global thread pool), with bounded waits that process events.
"""

from __future__ import annotations

import os
import time
import types
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from desktop.app.ui.pages import maintenance as maintenance_mod
from desktop.app.ui.pages import rooms as rooms_mod
from desktop.app.ui.pages.maintenance import MaintenancePage
from desktop.app.ui.pages.rooms import (
    BlockSetupDialog,
    ManageBlocksDialog,
    RoomsPage,
)


# --------------------------------------------------------------------- Qt
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def drain_tasks(qapp):
    """Never let a background write leak into the next test."""
    yield
    QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()


def wait_until(predicate, qapp, timeout=4.0):
    """Bounded wait that keeps the GUI event queue moving."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    qapp.processEvents()
    return bool(predicate())


# ------------------------------------------------------------ fake Supabase
class _Response:
    def __init__(self, data):
        self.data = data


class _FakeAuth:
    def __init__(self, client):
        self.client = client

    def get_user(self):
        if self.client.auth_delay:
            time.sleep(self.client.auth_delay)
        if self.client.auth_error:
            raise self.client.auth_error
        return types.SimpleNamespace(user=types.SimpleNamespace(id="staff-1"))


class _FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.payload = None
        self.filters = {}

    def select(self, *args, **kwargs):
        self.operation = "select"
        return self

    def order(self, *args, **kwargs):
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = dict(payload)
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = dict(payload)
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def execute(self):
        client = self.client
        if self.operation == "select":
            if self.name == "maintenance_reports":
                return _Response([dict(row) for row in client.maintenance_rows])
            if self.name == "rooms":
                return _Response([dict(row) for row in client.rooms])
            if self.name == "blocks":
                return _Response([dict(row) for row in client.blocks])
            if self.name == "students":
                client.student_queries += 1
                if client.occupants_delay:
                    time.sleep(client.occupants_delay)
                if client.occupants_error:
                    raise client.occupants_error
                room_id = self.filters.get("room_id")
                return _Response([
                    dict(row) for row in client.students
                    if room_id is None or row.get("room_id") == room_id
                ])
            return _Response([])

        if self.operation == "update":
            if self.name == "maintenance_reports":
                client.update_calls.append(dict(self.payload))
                if client.update_delay:
                    time.sleep(client.update_delay)
                if client.update_error:
                    raise client.update_error
                row_id = self.filters.get("id")
                for row in client.maintenance_rows:
                    if row.get("id") == row_id:
                        row.update(self.payload)
                return _Response([dict(row) for row in client.maintenance_rows])
            if self.name == "rooms":
                client.room_update_calls.append(dict(self.payload))
                if client.write_delay:
                    time.sleep(client.write_delay)
                if client.write_error:
                    raise client.write_error
                row_id = self.filters.get("id")
                for row in client.rooms:
                    if row.get("id") == row_id:
                        row.update(self.payload)
                return _Response([dict(row) for row in client.rooms])
            return _Response([])

        if self.operation == "insert":
            if self.name == "rooms":
                client.room_insert_calls.append(dict(self.payload))
                if client.write_delay:
                    time.sleep(client.write_delay)
                if client.write_error:
                    raise client.write_error
                created = dict(self.payload)
                created["id"] = f"room-{len(client.rooms) + 1}"
                client.rooms.append(created)
                return _Response([created])
            if self.name == "blocks":
                client.block_insert_calls.append(dict(self.payload))
                if client.write_delay:
                    time.sleep(client.write_delay)
                if client.write_error:
                    raise client.write_error
                created = dict(self.payload)
                created["id"] = f"block-{len(client.blocks) + 1}"
                client.blocks.append(created)
                return _Response([created])
            return _Response([])

        if self.operation == "delete":
            if self.name == "maintenance_reports":
                client.delete_calls.append(self.filters.get("id"))
                if client.delete_delay:
                    time.sleep(client.delete_delay)
                if client.delete_error:
                    raise client.delete_error
                row_id = self.filters.get("id")
                client.maintenance_rows = [
                    row for row in client.maintenance_rows if row.get("id") != row_id
                ]
                return _Response([])
            if self.name == "rooms":
                client.room_delete_calls.append(self.filters.get("id"))
                if client.delete_delay:
                    time.sleep(client.delete_delay)
                if client.delete_error:
                    raise client.delete_error
                row_id = self.filters.get("id")
                client.rooms = [row for row in client.rooms if row.get("id") != row_id]
                return _Response([])
            if self.name == "blocks":
                client.block_delete_calls.append(self.filters.get("id"))
                if client.delete_delay:
                    time.sleep(client.delete_delay)
                if client.delete_error:
                    raise client.delete_error
                row_id = self.filters.get("id")
                client.blocks = [row for row in client.blocks if row.get("id") != row_id]
                return _Response([])
            return _Response([])

        return _Response([])


class FakeClient:
    """Small Supabase stand-in with per-operation delays/errors."""

    def __init__(self, maintenance_rows=None, rooms=None, blocks=None, students=None):
        self.maintenance_rows = [dict(row) for row in (maintenance_rows or [])]
        self.rooms = [dict(row) for row in (rooms or [])]
        self.blocks = [dict(row) for row in (blocks or [])]
        self.students = [dict(row) for row in (students or [])]
        self.auth = _FakeAuth(self)

        self.update_calls = []
        self.delete_calls = []
        self.room_insert_calls = []
        self.room_update_calls = []
        self.room_delete_calls = []
        self.block_insert_calls = []
        self.block_delete_calls = []
        self.student_queries = 0

        self.update_delay = 0.0
        self.delete_delay = 0.0
        self.write_delay = 0.0
        self.auth_delay = 0.0
        self.occupants_delay = 0.0

        self.update_error = None
        self.delete_error = None
        self.write_error = None
        self.auth_error = None
        self.occupants_error = None

    def table(self, name):
        return _FakeTable(self, name)


def _ticket(ticket_id="m1", status="pending", **extra):
    row = {
        "id": ticket_id,
        "category": "plumbing",
        "description": "Leaking sink",
        "status": status,
        "created_at": "2026-10-12T10:00:00Z",
        "staff_note": None,
        "students": {"first_name": "Sarah", "last_name": "Saidi", "card_id": "2024001"},
    }
    row.update(extra)
    return row


def _room(room_id="r1", number="101", **extra):
    row = {
        "id": room_id,
        "block": "A",
        "floor": 1,
        "number": number,
        "capacity": 2,
        "gender": "male",
    }
    row.update(extra)
    return row


# ------------------------------------------------------------------ tests
def test_maintenance_status_returns_immediately_and_runs_in_background(qapp):
    client = FakeClient(maintenance_rows=[_ticket()])
    page = MaintenancePage(client)
    assert page.table.rowCount() == 1
    page.table.selectRow(0)

    client.update_delay = 0.60
    started = time.monotonic()
    with patch.object(
        maintenance_mod.QInputDialog,
        "getMultiLineText",
        return_value=("Dispatch plumber", True),
    ):
        page.set_status("in_progress")
    elapsed = time.monotonic() - started

    assert elapsed < 0.25, f"set_status blocked the GUI thread for {elapsed:.3f}s"
    assert page._actions_busy is True
    assert not page.in_progress_btn.isEnabled()
    assert page.in_progress_btn.text() == "Working..."
    assert (not page.error_banner.isHidden())

    assert wait_until(lambda: not page._actions_busy, qapp, timeout=5.0)
    assert client.update_calls and client.update_calls[0]["status"] == "in_progress"
    assert page.rows[0]["status"] == "in_progress"
    assert page.selected() is not None, "selection must survive the refresh"
    assert page.in_progress_btn.text() == "Mark in progress"
    assert page.resolved_btn.isEnabled()


def test_maintenance_status_failure_shows_message_and_restores_controls(qapp):
    client = FakeClient(maintenance_rows=[_ticket()])
    page = MaintenancePage(client)
    page.table.selectRow(0)

    client.update_delay = 0.15
    client.update_error = RuntimeError("service unavailable")

    with patch.object(
        maintenance_mod.QInputDialog,
        "getMultiLineText",
        return_value=("note", True),
    ):
        page.set_status("in_progress")

    assert not page.in_progress_btn.isEnabled()
    assert wait_until(lambda: not page._actions_busy, qapp)
    assert (not page.error_banner.isHidden())
    texts = " ".join(label.text() for label in page.error_banner.findChildren(QLabel))
    assert "service unavailable" in texts
    assert "Traceback" not in texts
    assert page.in_progress_btn.isEnabled()
    assert page.resolved_btn.isEnabled()
    assert page.table.rowCount() == 1
    assert page.rows[0]["status"] == "pending"


def test_maintenance_double_status_invocation_writes_once(qapp):
    client = FakeClient(maintenance_rows=[_ticket()])
    page = MaintenancePage(client)
    page.table.selectRow(0)
    client.update_delay = 0.35

    with patch.object(
        maintenance_mod.QInputDialog,
        "getMultiLineText",
        return_value=("note", True),
    ) as dialog:
        page.set_status("in_progress")
        page.set_status("in_progress")

    assert dialog.call_count == 1, "busy guard must reject the second submission"
    assert wait_until(lambda: not page._actions_busy, qapp)
    assert len(client.update_calls) == 1


def test_maintenance_delete_disables_button_and_restores_it(qapp):
    client = FakeClient(maintenance_rows=[_ticket("m1"), _ticket("m2")])
    page = MaintenancePage(client)
    page.table.selectRow(0)
    client.delete_delay = 0.35

    with patch.object(maintenance_mod.ConfirmDialog, "ask", return_value=True):
        page.on_delete()

    assert not page.delete_btn.isEnabled()
    assert page.delete_btn.text() == "Working..."
    assert wait_until(lambda: not page._actions_busy, qapp)
    assert page.delete_btn.text() == "Delete ticket"
    assert client.delete_calls == ["m1"]
    assert len(client.maintenance_rows) == 1
    assert page.table.rowCount() == 1

    page.table.selectRow(0)
    assert page.delete_btn.isEnabled()


def test_maintenance_stale_selection_after_refresh_does_not_crash(qapp):
    client = FakeClient(maintenance_rows=[_ticket()])
    page = MaintenancePage(client)
    page.table.selectRow(0)
    assert page.selected() is not None

    # A refresh removes the selected ticket; every action must tolerate it.
    page.apply_live_data([])
    page.table.setRowCount(0)

    with patch.object(maintenance_mod.QMessageBox, "information") as info:
        page.show_detail()
        page.on_delete()
        page.set_status("resolved")

    assert info.call_count >= 1
    assert client.delete_calls == []
    assert client.update_calls == []


class _AcceptedRoomDialog:
    """Stand-in for RoomSetupDialog that returns a valid payload."""

    result_data = {
        "block": "A",
        "floor": 1,
        "number": "102",
        "capacity": 2,
        "gender": "male",
    }

    def __init__(self, *args, **kwargs):
        pass

    def exec(self):
        return 1


def test_rooms_add_disables_controls_and_rejects_double_submission(qapp):
    client = FakeClient(rooms=[_room("r1"), _room("r2", "102")], blocks=[
        {"id": "b1", "name": "A", "gender": "male"}
    ])
    with patch.object(rooms_mod, "room_occupancy", return_value={}):
        page = RoomsPage(client)
        assert page.table.rowCount() == 2
        page.search_input.setText("10")
        page.filter_table()

        client.write_delay = 0.40
        with patch.object(rooms_mod, "RoomSetupDialog", _AcceptedRoomDialog):
            started = time.monotonic()
            page.on_add()
            page.on_add()  # second click while the first write is in flight
            elapsed = time.monotonic() - started

        assert elapsed < 0.25
        assert not page.add_btn.isEnabled()
        assert page.add_btn.text() == "Working..."
        assert wait_until(lambda: not page._actions_busy, qapp)
        assert len(client.room_insert_calls) == 1
        assert page.add_btn.isEnabled()
        assert page.add_btn.text() == "Add room"
        assert page.table.rowCount() == 3
        assert page.search_input.text() == "10", "search text must survive the refresh"


def test_rooms_add_failure_shows_message_and_keeps_data(qapp):
    client = FakeClient(rooms=[_room("r1")], blocks=[
        {"id": "b1", "name": "A", "gender": "male"}
    ])
    with patch.object(rooms_mod, "room_occupancy", return_value={}):
        page = RoomsPage(client)
        client.write_delay = 0.10
        client.write_error = RuntimeError("permission denied")

        with patch.object(rooms_mod, "RoomSetupDialog", _AcceptedRoomDialog):
            page.on_add()

        assert not page.add_btn.isEnabled()
        assert wait_until(lambda: not page._actions_busy, qapp)
        assert (not page.error_banner.isHidden())
        texts = " ".join(label.text() for label in page.error_banner.findChildren(QLabel))
        assert "permission denied" in texts
        assert "Traceback" not in texts
        assert page.add_btn.isEnabled()
        assert page.table.rowCount() == 1
        assert page.rows[0]["id"] == "r1"


def test_rooms_delete_disables_button_and_restores_it(qapp):
    client = FakeClient(rooms=[_room("r1"), _room("r2", "102")], blocks=[
        {"id": "b1", "name": "A", "gender": "male"}
    ])
    with patch.object(rooms_mod, "room_occupancy", return_value={}):
        page = RoomsPage(client)
        page.table.selectRow(0)
        client.delete_delay = 0.35

        with patch.object(
            rooms_mod.QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            page.on_delete()

        assert not page.delete_btn.isEnabled()
        assert page.delete_btn.text() == "Working..."
        assert wait_until(lambda: not page._actions_busy, qapp)
        assert page.delete_btn.text() == "Delete"
        assert page.delete_btn.isEnabled()
        assert client.room_delete_calls == ["r1"]
        assert page.table.rowCount() == 1


def test_room_info_lookup_is_off_thread_and_deduplicated(qapp):
    client = FakeClient(
        rooms=[_room("r1")],
        blocks=[{"id": "b1", "name": "A", "gender": "male"}],
        students=[{
            "card_id": "2024001",
            "first_name": "Sarah",
            "last_name": "Saidi",
            "faculty": "Science",
            "room_id": "r1",
            "status": "active",
        }],
    )
    opened = []

    class FakeInfoDialog:
        def __init__(self, parent, room_data, client_arg):
            opened.append((room_data, client_arg))

        def exec(self):
            return 0

        def deleteLater(self):
            pass

    with patch.object(rooms_mod, "room_occupancy", return_value={"r1": 1}), \
            patch.object(rooms_mod, "RoomInfoCardDialog", FakeInfoDialog):
        page = RoomsPage(client)
        client.occupants_delay = 0.40

        started = time.monotonic()
        page.on_row_double_clicked(0, 0)
        page.on_row_double_clicked(0, 0)
        elapsed = time.monotonic() - started

        assert elapsed < 0.25, "double-click lookup blocked the GUI thread"
        assert opened == []
        assert wait_until(lambda: bool(opened), qapp)
        assert client.student_queries == 1, "the second double-click must be ignored"

    room_data, dialog_client = opened[0]
    assert dialog_client is None, "the dialog must not run its own blocking query"
    assert room_data["occupants"][0]["card_id"] == "2024001"


def test_rooms_stale_selection_after_refresh_does_not_crash(qapp):
    client = FakeClient(rooms=[_room("r1"), _room("r2", "102")], blocks=[
        {"id": "b1", "name": "A", "gender": "male"}
    ])
    with patch.object(rooms_mod, "room_occupancy", return_value={}):
        page = RoomsPage(client)
        page.table.selectRow(1)

        # The selected room disappears between two refreshes.
        client.rooms = []
        page.reload()
        assert wait_until(
            lambda: not page._actions_busy and len(page.rows) == 0,
            qapp,
        )

        class _CancelledDialog:
            result_data = None

            def __init__(self, *args, **kwargs):
                pass

            def exec(self):
                return 0

        with patch.object(rooms_mod, "RoomSetupDialog", _CancelledDialog), \
                patch.object(rooms_mod.QMessageBox, "information") as info, \
                patch.object(
                    rooms_mod.QMessageBox,
                    "question",
                    return_value=QMessageBox.StandardButton.Cancel,
                ):
            page.on_edit()
            page.on_delete()
            page.on_row_double_clicked(5, 0)

        assert info.call_count >= 1
        assert client.room_delete_calls == []


def test_visible_block_dialog_saves_through_task_runner(qapp):
    client = FakeClient(blocks=[])
    dialog = BlockSetupDialog(client=client)
    dialog.show()
    qapp.processEvents()
    assert dialog.isVisible()

    client.write_delay = 0.30
    dialog.name_edit.setText("C")
    dialog.on_save()

    assert not dialog.save_btn.isEnabled()
    assert dialog.save_btn.text() == "Working..."
    assert wait_until(
        lambda: dialog.result_data is not None
        and dialog.save_btn.text() == "Create block",
        qapp,
    )
    assert dialog.result_data == {"name": "C", "gender": "female"}
    assert len(client.block_insert_calls) == 1
    dialog.close()
    qapp.processEvents()


def test_manage_blocks_delete_runs_in_background(qapp):
    client = FakeClient(
        rooms=[],
        blocks=[
            {"id": "b1", "name": "A", "gender": "male"},
            {"id": "b2", "name": "B", "gender": "female"},
        ],
    )
    dialog = ManageBlocksDialog(
        client=client,
        rooms=[],
        occupancy={},
        blocks=list(client.blocks),
    )
    assert dialog.table.rowCount() == 2

    client.delete_delay = 0.30
    with patch.object(
        rooms_mod.QMessageBox,
        "question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        dialog.on_delete_block(client.blocks[0])

    assert not dialog.add_block_btn.isEnabled()
    assert wait_until(lambda: not dialog._busy, qapp)
    assert client.block_delete_calls == ["b1"]
    assert dialog.add_block_btn.isEnabled()
    assert dialog.table.rowCount() == 1
    dialog.close()
    qapp.processEvents()


def test_maintenance_stages_are_exactly_three(qapp):
    client = FakeClient(maintenance_rows=[])
    page = MaintenancePage(client)
    assert [s[0] for s in maintenance_mod._STAGES] == ['pending', 'in_progress', 'resolved']
    assert list(page.segments.buttons.keys()) == ['pending', 'in_progress', 'resolved']
    assert 'under_review' not in page.segments.buttons


def test_legacy_under_review_ticket_displays_as_pending(qapp):
    client = FakeClient(maintenance_rows=[_ticket('m_old', status='under_review')])
    page = MaintenancePage(client)
    assert page.table.rowCount() == 1
    assert '1' in page.segments.buttons['pending'].text()
    assert maintenance_mod._stage_index('under_review') == 0
    kind, label = maintenance_mod._status_meta('under_review')
    assert label == 'Pending'
    page.table.selectRow(0)
    assert page.in_progress_btn.isEnabled()
    assert page.resolved_btn.isEnabled()
