"""Tests for Task 1: modifying, adding, deleting, and clearing official roster entries."""

import time
from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QDialog

from desktop.app.ui.pages import official_list as official_mod
from desktop.app.ui.pages.official_list import (
    ClearAllRosterDialog,
    OfficialListPage,
    OfficialResidentDialog,
    _ADMIN_MODIFY_TOOLTIP,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def _drain_tasks(qapp, monkeypatch):
    monkeypatch.setattr(official_mod.QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(official_mod.QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(official_mod.QMessageBox, "critical", lambda *args, **kwargs: None)
    yield
    QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()


def wait_until(qapp, predicate, timeout=4.0):
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


class FakeOfficialClient:
    def __init__(self, rows):
        self.rows = [dict(r) for r in rows]
        self.rpc_calls = []

    def table(self, name):
        client = self

        class Query:
            def select(self, *_args, **_kwargs):
                return self

            def order(self, *_args, **_kwargs):
                return self

            def eq(self, *_args, **_kwargs):
                return self

            def execute(self):
                if name == "students":
                    return FakeResponse([{"card_id": "202437010001", "status": "pending"}])
                return FakeResponse(deepcopy(client.rows))

        return Query()

    def rpc(self, name, params=None):
        client = self
        params = dict(params or {})

        class Call:
            def execute(self):
                client.rpc_calls.append((name, deepcopy(params)))
                if name == "update_official_resident":
                    old_id = params.get("p_old_card_id")
                    new_id = params.get("p_card_id")
                    if new_id != old_id and any(r["card_id"] == new_id for r in client.rows):
                        raise Exception(f"Card ID {new_id} already exists in official roster")
                    for r in client.rows:
                        if r["card_id"] == old_id:
                            r["card_id"] = new_id
                            r["first_name"] = params.get("p_first_name")
                            r["last_name"] = params.get("p_last_name")
                            r["birth_date"] = params.get("p_birth_date")
                            r["gender"] = params.get("p_gender")
                            r["university"] = params.get("p_university")
                            r["faculty"] = params.get("p_faculty")
                            return FakeResponse(dict(r))
                    raise Exception(f"Official resident not found with card ID {old_id}")

                if name == "add_official_resident":
                    new_id = params.get("p_card_id")
                    if any(r["card_id"] == new_id for r in client.rows):
                        raise Exception(f"Card ID {new_id} already exists in official roster")
                    row = {
                        "card_id": new_id,
                        "first_name": params.get("p_first_name"),
                        "last_name": params.get("p_last_name"),
                        "birth_date": params.get("p_birth_date"),
                        "gender": params.get("p_gender"),
                        "university": params.get("p_university"),
                        "faculty": params.get("p_faculty"),
                    }
                    client.rows.append(row)
                    return FakeResponse(row)

                if name == "delete_official_residents":
                    card_ids = set(params.get("p_card_ids") or [])
                    before = len(client.rows)
                    client.rows = [r for r in client.rows if r["card_id"] not in card_ids]
                    return FakeResponse(before - len(client.rows))

                if name == "clear_official_residents":
                    count = len(client.rows)
                    client.rows = []
                    return FakeResponse(count)

                return FakeResponse(None)

        return Call()


def sample_roster():
    return [
        {
            "card_id": "202437010001",
            "first_name": "Amine",
            "last_name": "Benali",
            "birth_date": "2003-04-12",
            "gender": "male",
            "university": "Université Abou Bekr Belkaïd - Tlemcen",
            "faculty": "Faculté de Technologie",
        },
        {
            "card_id": "202437010002",
            "first_name": "Yasmine",
            "last_name": "Mansouri",
            "birth_date": "2003-06-03",
            "gender": "female",
            "university": "Université Abou Bekr Belkaïd - Tlemcen",
            "faculty": "Faculté de Médecine",
        },
    ]


def test_non_admin_sees_no_write_actions(qapp, monkeypatch):
    """Staff cannot add, edit, delete or clear roster records."""
    monkeypatch.setattr("desktop.app.client.current_role", lambda _client: "staff")
    client = FakeOfficialClient(sample_roster())
    page = OfficialListPage(client)

    assert page.role == "staff"
    assert not page.import_btn.isEnabled()
    assert not page.add_btn.isEnabled()
    assert not page.edit_btn.isEnabled()
    assert not page.delete_selected_btn.isEnabled()
    assert not page.delete_all_btn.isEnabled()

    assert page.add_btn.toolTip() == _ADMIN_MODIFY_TOOLTIP
    assert page.edit_btn.toolTip() == _ADMIN_MODIFY_TOOLTIP
    assert page.delete_selected_btn.toolTip() == _ADMIN_MODIFY_TOOLTIP
    assert page.delete_all_btn.toolTip() == _ADMIN_MODIFY_TOOLTIP

    # Even if invoked directly, action handlers reject non-admin without calling RPC
    page.on_add()
    page.on_edit()
    page.on_delete_selected()
    page.on_delete_all()
    assert len(client.rpc_calls) == 0
    page.close()


def test_edit_official_resident_success(qapp, monkeypatch):
    """Admin can edit an official resident entry and update the roster."""
    monkeypatch.setattr("desktop.app.client.current_role", lambda _client: "admin")
    client = FakeOfficialClient(sample_roster())
    page = OfficialListPage(client)

    # Select the first row
    page.table.selectRow(0)
    assert page.edit_btn.isEnabled()

    # Create dialog with row 0 data and modify first name
    dlg = OfficialResidentDialog(page, client=client, mode="edit", initial_data=page.rows[0])
    dlg.first_name_edit.setText("Mohamed")
    dlg.on_save()

    assert dlg.result_data is not None
    assert dlg.result_data["first_name"] == "Mohamed"
    assert any(c[0] == "update_official_resident" for c in client.rpc_calls)

    # Trigger on_edit with accepted dialog mock
    class FakeAcceptedEditDialog:
        def __init__(self, *args, **kwargs):
            self.card_id_edit = MagicMock(text=lambda: "202437010001")
            self.first_name_edit = MagicMock(text=lambda: "Mohamed")
            self.last_name_edit = MagicMock(text=lambda: "Benali")

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(official_mod, "OfficialResidentDialog", FakeAcceptedEditDialog)
    page.on_edit(0)

    assert page.result_banner.property("kind") == "success"
    assert "Updated record" in page.result_banner._message.text()
    page.close()


def test_edit_official_resident_duplicate_card_id_error(qapp, monkeypatch):
    """Editing to an existing card_id shows an inline collision error and does not accept."""
    monkeypatch.setattr("desktop.app.client.current_role", lambda _client: "admin")
    client = FakeOfficialClient(sample_roster())

    dlg = OfficialResidentDialog(None, client=client, mode="edit", initial_data=sample_roster()[0])
    # Attempt to change card_id of row 0 to that of row 1 ("202437010002")
    dlg.card_id_edit.setText("202437010002")
    dlg.on_save()

    assert dlg.result_data is None
    assert not dlg.error_banner.isHidden()
    assert "already exists" in dlg.error_banner._message.text().lower()
    dlg.close()


def test_delete_selected_entries(qapp, monkeypatch):
    """Admin can delete selected entries from the official roster."""
    monkeypatch.setattr("desktop.app.client.current_role", lambda _client: "admin")
    client = FakeOfficialClient(sample_roster())
    page = OfficialListPage(client)

    page.table.selectRow(0)
    assert page.delete_selected_btn.isEnabled()

    # User confirms deletion
    monkeypatch.setattr(official_mod.ConfirmDialog, "ask", lambda *args, **kwargs: True)
    page.on_delete_selected()

    assert wait_until(qapp, lambda: not page._action_busy and not page._reload_busy)
    assert any(c[0] == "delete_official_residents" for c in client.rpc_calls)
    assert len(client.rows) == 1
    assert page.result_banner.property("kind") == "success"
    assert "deleted 1" in page.result_banner._message.text().lower()
    page.close()


def test_delete_all_requires_typed_confirmation(qapp, monkeypatch):
    """Clear all entries requires typing DELETE before the button is enabled."""
    dlg = ClearAllRosterDialog(total_count=10, matching_pending=3)
    assert not dlg.delete_button.isEnabled()

    dlg.confirm_input.setText("del")
    assert not dlg.delete_button.isEnabled()

    dlg.confirm_input.setText("delete")
    assert not dlg.delete_button.isEnabled()

    dlg.confirm_input.setText("DELETE")
    assert dlg.delete_button.isEnabled()

    dlg.delete_button.click()
    assert dlg.confirmed is True
    dlg.close()


def test_delete_all_executes_clear_rpc(qapp, monkeypatch):
    """Admin running delete all clears the entire admissions roster."""
    monkeypatch.setattr("desktop.app.client.current_role", lambda _client: "admin")
    client = FakeOfficialClient(sample_roster())
    page = OfficialListPage(client)

    class FakeClearDialog:
        def __init__(self, *args, **kwargs):
            self.confirmed = True

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(official_mod, "ClearAllRosterDialog", FakeClearDialog)
    page.on_delete_all()

    assert wait_until(qapp, lambda: not page._action_busy and not page._reload_busy)
    assert any(c[0] == "clear_official_residents" for c in client.rpc_calls)
    assert len(client.rows) == 0
    assert page.result_banner.property("kind") == "success"
    assert "cleared admissions roster" in page.result_banner._message.text().lower()
    page.close()


def test_pending_match_badge_refresh_triggered(qapp, monkeypatch):
    """Roster modifications notify PendingPage to refresh its match badges."""
    monkeypatch.setattr("desktop.app.client.current_role", lambda _client: "admin")
    client = FakeOfficialClient(sample_roster())
    mock_pending = MagicMock()

    page = OfficialListPage(client, pending_page=mock_pending)
    signals_received = []
    page.roster_changed.connect(lambda: signals_received.append(True))

    page._notify_roster_changed()

    assert len(signals_received) == 1
    assert mock_pending.reload.call_count == 1
    page.close()
