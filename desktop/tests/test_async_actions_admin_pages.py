"""Async action safety for the staff, official-roster and settings pages.

Every handler must return to the GUI thread immediately while its Supabase call
sleeps, mutate only through :class:`TaskRunner`, disable the controls involved,
and recover (with a human-readable message) on failure. The staff page must
never call ``auth.get_user()`` per selection.
"""

import os
import time
from copy import deepcopy
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from desktop.app.ui.pages import official_list as official_mod
from desktop.app.ui.pages import settings as settings_mod
from desktop.app.ui.pages import staff_accounts as staff_mod
from desktop.app.ui.pages.official_list import OfficialListPage
from desktop.app.ui.pages.settings import SettingsPage
from desktop.app.ui.pages.staff_accounts import StaffAccountsPage


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def _drain_tasks(qapp, monkeypatch):
    """Never let a background worker outlive a test.

    Depends on ``monkeypatch`` so queued callbacks still see the tests' fake
    dialogs when they are drained (a late success handler must not open a real
    modal message box during teardown).
    """
    yield
    QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()


@pytest.fixture(autouse=True)
def _no_health_worker(monkeypatch):
    """The settings page must not spawn its real 5 s health poller in tests."""
    monkeypatch.setattr(settings_mod.McpHealthWorker, "start", lambda self: None)


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


class FakeMessageBox:
    """Stand-in for ``QMessageBox``; records instead of opening modal dialogs."""

    Yes = True
    No = False
    questions = []
    informations = []
    criticals = []
    warnings = []

    @classmethod
    def reset(cls):
        cls.questions = []
        cls.informations = []
        cls.criticals = []
        cls.warnings = []

    @classmethod
    def question(cls, *_args, **_kwargs):
        cls.questions.append(_args)
        return cls.Yes

    @classmethod
    def information(cls, *_args, **_kwargs):
        cls.informations.append(_args)

    @classmethod
    def critical(cls, *_args, **_kwargs):
        cls.criticals.append(_args)

    @classmethod
    def warning(cls, *_args, **_kwargs):
        cls.warnings.append(_args)


# ----------------------------------------------------------------- staff page
class FakeAuth:
    def __init__(self, user_id="admin-id", error=None):
        self.user_id = user_id
        self.error = error
        self.get_user_calls = 0

    def get_user(self):
        self.get_user_calls += 1
        if self.error is not None:
            raise self.error
        return SimpleNamespace(user=SimpleNamespace(id=self.user_id))


class StaffClient:
    """Minimal ``admin-users`` Edge Function fake."""

    def __init__(
        self,
        rows,
        user_id="admin-id",
        user_error=None,
        list_delay=0.0,
        create_delay=0.0,
        delete_delay=0.0,
        create_error=None,
        delete_error=None,
    ):
        self.staff = [dict(row) for row in rows]
        self.auth = FakeAuth(user_id=user_id, error=user_error)
        self.functions = self
        self.list_delay = list_delay
        self.create_delay = create_delay
        self.delete_delay = delete_delay
        self.create_error = create_error
        self.delete_error = delete_error
        self.invoke_calls = []
        self.rpc_calls = []

    def invoke(self, _name, invoke_options=None):
        body = dict((invoke_options or {}).get("body") or {})
        action = body.get("action")
        self.invoke_calls.append((action, body))

        if action == "list_staff":
            if self.list_delay:
                time.sleep(self.list_delay)
            return deepcopy(self.staff)

        if action == "create_staff":
            if self.create_delay:
                time.sleep(self.create_delay)
            if self.create_error is not None:
                return {"error": self.create_error}
            self.staff.append(
                {
                    "id": f"staff-new-{len(self.staff)}",
                    "full_name": body.get("full_name", ""),
                    "position": body.get("position", ""),
                }
            )
            return {"ok": True}

        if action == "delete_staff":
            if self.delete_delay:
                time.sleep(self.delete_delay)
            if self.delete_error is not None:
                return {"error": self.delete_error}
            self.staff = [row for row in self.staff if row.get("id") != body.get("id")]
            return {"ok": True}

        return {"ok": True}

    def rpc(self, name, params=None):
        client = self

        class Call:
            def execute(self):
                client.rpc_calls.append((name, deepcopy(params)))
                return FakeResponse(None)

        return Call()

    def actions(self, action):
        return [body for recorded, body in self.invoke_calls if recorded == action]


def staff_rows():
    return [
        {"id": "admin-id", "full_name": "Admin Officer", "position": "Head of Residence"},
        {"id": "staff-other-id", "full_name": "Reception Officer", "position": "Reception Desk"},
        {"id": "staff-third-id", "full_name": "Housing Officer", "position": "Housing"},
    ]


def test_staff_delete_returns_immediately_and_restores_controls(qapp, monkeypatch):
    FakeMessageBox.reset()
    monkeypatch.setattr(staff_mod, "QMessageBox", FakeMessageBox)
    client = StaffClient(staff_rows(), delete_delay=0.45)

    page = StaffAccountsPage(client)
    assert page.table.rowCount() == 3
    page.table.selectRow(1)
    assert page.delete_btn.isEnabled()

    started = time.monotonic()
    page.on_delete()
    page.on_delete()  # duplicate submission must be ignored
    elapsed = time.monotonic() - started

    assert elapsed < 0.25
    assert not page.delete_btn.isEnabled()
    assert page.delete_btn.text() == "Working..."
    assert not page.create_btn.isEnabled()
    assert not page.refresh_btn.isEnabled()
    assert len(FakeMessageBox.questions) == 1
    assert wait_until(qapp, lambda: len(client.actions("delete_staff")) == 1)

    assert wait_until(qapp, lambda: not page._action_busy and not page._list_busy)
    assert len(client.actions("delete_staff")) == 1
    assert page.delete_btn.text() == "Delete selected staff account"
    assert page.create_btn.isEnabled()
    assert page.refresh_btn.isEnabled()
    # The selected row was deleted: no stale selection may enable the action.
    assert page.selected() is None
    assert not page.delete_btn.isEnabled()
    page.table.selectRow(1)  # remaining officer
    assert page.delete_btn.isEnabled()
    page.close()


def test_staff_create_returns_immediately_and_double_submit_writes_once(qapp, monkeypatch):
    FakeMessageBox.reset()
    monkeypatch.setattr(staff_mod, "QMessageBox", FakeMessageBox)
    client = StaffClient(staff_rows(), create_delay=0.45)

    page = StaffAccountsPage(client)
    page.full_name.setText("New Officer")
    page.position.setText("Housing Officer")
    page.email.setText("new@univ-tlemcen.dz")
    page.password.setText("secret123")

    started = time.monotonic()
    page.on_create()
    page.on_create()  # duplicate submission must be ignored
    elapsed = time.monotonic() - started

    assert elapsed < 0.25
    assert not page.create_btn.isEnabled()
    assert page.create_btn.text() == "Working..."
    assert not page.delete_btn.isEnabled()
    assert not page.refresh_btn.isEnabled()
    assert wait_until(qapp, lambda: len(client.actions("create_staff")) == 1)

    assert wait_until(qapp, lambda: not page._action_busy and not page._list_busy)
    assert len(client.actions("create_staff")) == 1
    assert page.create_btn.isEnabled()
    assert page.create_btn.text() == "Create staff account"
    assert page.refresh_btn.isEnabled()
    assert page.full_name.text() == ""
    assert page.table.rowCount() == 4
    assert page.table.item(3, 0).text() == "New Officer"
    page.close()


def test_staff_create_failure_shows_message_and_preserves_form(qapp, monkeypatch):
    FakeMessageBox.reset()
    monkeypatch.setattr(staff_mod, "QMessageBox", FakeMessageBox)
    client = StaffClient(staff_rows(), create_error="Email already registered")

    page = StaffAccountsPage(client)
    page.full_name.setText("New Officer")
    page.email.setText("new@univ-tlemcen.dz")
    page.password.setText("secret123")

    page.on_create()

    assert wait_until(qapp, lambda: not page._action_busy)
    assert len(FakeMessageBox.criticals) == 1
    message = FakeMessageBox.criticals[0][2]
    assert "Email already registered" in message
    assert "Traceback" not in message
    assert page.create_btn.isEnabled()
    assert page.create_btn.text() == "Create staff account"
    assert page.email.text() == "new@univ-tlemcen.dz"
    assert page.full_name.text() == "New Officer"
    assert page.table.rowCount() == 3
    page.close()


def test_staff_selection_uses_cached_user_id(qapp, monkeypatch):
    FakeMessageBox.reset()
    monkeypatch.setattr(staff_mod, "QMessageBox", FakeMessageBox)
    client = StaffClient(staff_rows())

    page = StaffAccountsPage(client)
    assert client.auth.get_user_calls == 1

    page.table.selectRow(0)
    assert not page.delete_btn.isEnabled()
    assert "cannot delete your own" in page.delete_btn.toolTip()

    page.table.selectRow(1)
    assert page.delete_btn.isEnabled()
    assert page.delete_btn.toolTip() == ""

    page.table.selectRow(0)
    page.table.selectRow(1)
    page.table.selectRow(0)
    assert client.auth.get_user_calls == 1  # never per selection
    page.close()


def test_staff_missing_user_id_disables_delete_safely(qapp, monkeypatch):
    FakeMessageBox.reset()
    monkeypatch.setattr(staff_mod, "QMessageBox", FakeMessageBox)
    client = StaffClient(staff_rows(), user_error=RuntimeError("no session"))

    page = StaffAccountsPage(client)
    assert client.auth.get_user_calls == 1
    page.table.selectRow(1)

    assert not page.delete_btn.isEnabled()
    assert "could not be verified" in page.delete_btn.toolTip()

    page.on_delete()  # direct call must not write either
    assert client.actions("delete_staff") == []
    assert client.auth.get_user_calls == 1
    page.close()


def test_staff_deferred_initial_load_skips_sync_identity_and_list(qapp, monkeypatch):
    FakeMessageBox.reset()
    monkeypatch.setattr(staff_mod, "QMessageBox", FakeMessageBox)
    client = StaffClient(staff_rows())

    page = StaffAccountsPage(client, defer_initial_load=True, current_uid="admin-id")
    assert client.auth.get_user_calls == 0  # no synchronous identity lookup
    assert not page._initializing

    assert wait_until(qapp, lambda: not page._list_busy)
    assert page.table.rowCount() == 3
    page.table.selectRow(0)
    assert not page.delete_btn.isEnabled()  # cached id protects self
    assert "cannot delete your own" in page.delete_btn.toolTip()
    page.close()


# ------------------------------------------------------------- official page
class OfficialClient:
    def __init__(self, rows, import_result=None, query_delay=0.0, query_error=None,
                 import_delay=0.0, import_error=None):
        self.rows = [dict(row) for row in rows]
        self.import_result = import_result
        self.query_delay = query_delay
        self.query_error = query_error
        self.import_delay = import_delay
        self.import_error = import_error
        self.import_calls = []
        self.query_calls = 0

    def table(self, _name):
        client = self

        class Query:
            def select(self, *_args, **_kwargs):
                return self

            def order(self, *_args, **_kwargs):
                return self

            def execute(self):
                client.query_calls += 1
                if client.query_delay:
                    time.sleep(client.query_delay)
                if client.query_error is not None:
                    raise client.query_error
                return FakeResponse(deepcopy(client.rows))

        return Query()

    def rpc(self, name, params=None):
        client = self

        class Call:
            def execute(self):
                client.import_calls.append((name, deepcopy(params)))
                if client.import_delay:
                    time.sleep(client.import_delay)
                if client.import_error is not None:
                    raise client.import_error
                if name == "import_official_residents" and isinstance(params, dict):
                    client.rows = [dict(row) for row in (params.get("p_rows") or [])]
                return FakeResponse(client.import_result)

        return Call()


def roster_rows():
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


def test_official_import_returns_immediately_and_restores_controls(qapp, monkeypatch):
    monkeypatch.setattr("desktop.app.client.current_role", lambda _client: "admin")
    parsed = {"calls": 0}

    def fake_read(path):
        parsed["calls"] += 1
        return [dict(row) for row in roster_rows()]

    monkeypatch.setattr(official_mod, "read_official_file", fake_read)
    client = OfficialClient([], import_result=2, import_delay=0.45)

    page = OfficialListPage(client)
    assert page.role == "admin"
    assert page.import_btn.isEnabled()

    started = time.monotonic()
    page.on_import("official.csv")
    page.on_import("official.csv")  # duplicate submission must be ignored
    elapsed = time.monotonic() - started

    assert elapsed < 0.25
    assert not page.import_btn.isEnabled()
    assert page.import_btn.text() == "Working..."
    assert not page.refresh_btn.isEnabled()
    assert wait_until(qapp, lambda: len(client.import_calls) == 1)

    assert wait_until(qapp, lambda: not page._import_busy and not page._reload_busy)
    assert len(client.import_calls) == 1
    assert parsed["calls"] == 1
    assert page.import_btn.isEnabled()
    assert page.import_btn.text() == "Import list"
    assert page.refresh_btn.isEnabled()
    assert page.result_banner.property("kind") == "success"
    assert "Imported 2" in page.result_banner._message.text()
    assert page.table.rowCount() == 2
    page.close()


def test_official_import_parse_failure_shows_banner_and_keeps_data(qapp, monkeypatch):
    monkeypatch.setattr("desktop.app.client.current_role", lambda _client: "admin")

    def broken_read(_path):
        raise ValueError("missing card_id column")

    monkeypatch.setattr(official_mod, "read_official_file", broken_read)
    client = OfficialClient(roster_rows())

    page = OfficialListPage(client)
    assert len(page.rows) == 2

    page.on_import("broken.csv")

    assert wait_until(qapp, lambda: not page._import_busy)
    assert page.import_btn.isEnabled()
    assert page.import_btn.text() == "Import list"
    assert page.result_banner.property("kind") == "error"
    assert "missing card_id column" in page.result_banner._message.text()
    assert "Traceback" not in page.result_banner._message.text()
    assert len(page.rows) == 2
    assert client.import_calls == []
    page.close()


# --------------------------------------------------------------- settings page
class SettingsClient:
    def __init__(self, writes_enabled=False, get_error=None, set_error=None, set_delay=0.0):
        self.writes_enabled = writes_enabled
        self.get_error = get_error
        self.set_error = set_error
        self.set_delay = set_delay
        self.get_calls = 0
        self.set_calls = []

    def rpc(self, name, params=None):
        client = self

        class Call:
            def execute(self):
                if name == "mcp_get_settings":
                    client.get_calls += 1
                    if client.get_error is not None:
                        raise client.get_error
                    return FakeResponse({"writes_enabled": client.writes_enabled})
                if name == "mcp_set_writes_enabled":
                    client.set_calls.append(dict(params or {}))
                    if client.set_delay:
                        time.sleep(client.set_delay)
                    if client.set_error is not None:
                        raise client.set_error
                    client.writes_enabled = bool((params or {}).get("p_enabled"))
                    return FakeResponse(None)
                return FakeResponse(None)

        return Call()


@pytest.fixture
def settings_env(monkeypatch):
    monkeypatch.setattr(settings_mod, "current_role", lambda _client: "admin")
    monkeypatch.setattr(settings_mod, "_read_mcp_token", lambda: "tok-1234")
    FakeMessageBox.reset()
    monkeypatch.setattr(settings_mod, "QMessageBox", FakeMessageBox)


def test_settings_writes_toggle_async_and_double_submit_writes_once(qapp, settings_env):
    client = SettingsClient(writes_enabled=False, set_delay=0.45)
    page = SettingsPage(client)
    assert page.writes_checkbox.isEnabled()
    assert not page.writes_checkbox.isChecked()

    started = time.monotonic()
    page.writes_checkbox.setChecked(True)
    page._on_writes_toggled(True)  # duplicate submission must be ignored
    elapsed = time.monotonic() - started

    assert elapsed < 0.25
    assert not page.writes_checkbox.isEnabled()
    assert page.writes_note.text() == "Working..."
    assert wait_until(qapp, lambda: len(client.set_calls) == 1)

    assert wait_until(qapp, lambda: not page._writes_saving and not page._settings_loading)
    assert len(client.set_calls) == 1
    assert page.writes_checkbox.isEnabled()
    assert page.writes_checkbox.isChecked()
    assert page.writes_note.text().startswith("ChatGPT asks you to confirm")
    page.close()


def test_settings_writes_failure_reverts_and_reports(qapp, settings_env):
    client = SettingsClient(writes_enabled=False, set_error=RuntimeError("Supabase offline"))
    page = SettingsPage(client)

    page.writes_checkbox.setChecked(True)

    assert wait_until(qapp, lambda: not page._writes_saving)
    assert not page.writes_checkbox.isChecked()  # reverted to the DB state
    assert page.writes_checkbox.isEnabled()
    assert not page.writes_banner.isHidden()
    assert "reverted" in page.writes_banner._message.text()
    assert "Supabase offline" in page.writes_banner._message.text()
    assert len(FakeMessageBox.warnings) == 1
    assert "Supabase offline" in FakeMessageBox.warnings[0][2]
    assert page.writes_note.text().startswith("ChatGPT asks you to confirm")
    page.close()


def test_settings_load_failure_is_fail_safe(qapp, settings_env):
    client = SettingsClient(get_error=RuntimeError("network down"))
    page = SettingsPage(client)

    assert client.get_calls == 1
    assert not page.writes_checkbox.isEnabled()
    assert not page.writes_banner.isHidden()
    assert "network down" not in page.writes_banner._message.text()  # stable hint
    assert "stays disabled" in page.writes_banner._message.text()
    assert "Could not load" in page.writes_note.text()
    page.close()


def test_settings_reveal_and_copy_use_cached_role(qapp, monkeypatch):
    role_calls = []
    monkeypatch.setattr(settings_mod, "current_role", lambda _client: role_calls.append(1) or "admin")
    monkeypatch.setattr(settings_mod, "_read_mcp_token", lambda: "tok-1234")
    monkeypatch.setattr(settings_mod.McpHealthWorker, "start", lambda self: None)
    client = SettingsClient(writes_enabled=False)

    page = SettingsPage(client)
    assert len(role_calls) == 1  # construction only

    page.reveal_btn.click()
    assert page.token_label.text() == "tok-1234"
    assert len(role_calls) == 1

    page.token_copy_btn.click()
    assert QGuiApplication.clipboard().text() == "tok-1234"
    assert len(role_calls) == 1
    page.close()
