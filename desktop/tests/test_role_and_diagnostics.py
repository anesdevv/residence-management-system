"""Step 4 regression tests: role verification, retry states and diagnostics.

Qt runs offscreen; every Supabase call is faked.  The main-window tests patch
the page classes with plain QWidget factories, exactly like the existing suite,
so no page performs network I/O or starts worker threads.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from desktop.app import config as config_mod
from desktop.app.client import (
    RoleLookupError,
    current_role,
    forget_role,
    remember_role,
    resolve_role,
)
from desktop.app.logging_setup import log_path
from desktop.app.ui import login_window as login_mod
from desktop.app.ui import main_window as main_mod
from desktop.app.ui.login_window import LoginWindow
from desktop.app.ui.main_window import MainWindow
from desktop.app.ui.pages import official_list as official_mod
from desktop.app.ui.pages import settings as settings_mod
from desktop.app.ui.pages.official_list import OfficialListPage
from desktop.app.ui.pages.settings import SettingsPage


_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


@pytest.fixture
def qapp():
    return _qapp


@pytest.fixture(autouse=True)
def _drain_workers(qapp):
    yield
    QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()


def wait_until(qapp, predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


# --------------------------------------------------------------------- client
class _FakeQuery:
    def __init__(self, client):
        self.client = client

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def single(self):
        return self

    def execute(self):
        self.client.profile_calls += 1
        return SimpleNamespace(data={"role": self.client.role_value})


class _FakeAuth:
    def __init__(self, client):
        self.client = client
        self._in_memory_session = SimpleNamespace(
            user=SimpleNamespace(id="user-1", email="staff@test.local")
        )
        self._persist_session = False

    def get_user(self):
        self.client.get_user_calls += 1
        return SimpleNamespace(user=SimpleNamespace(id="user-1", email="staff@test.local"))

    def get_session(self):
        raise AssertionError("stored-session reads must not refresh the token")

    def sign_out(self):
        pass


class RoleClient:
    def __init__(self, role_value=" Admin "):
        self.role_value = role_value
        self.profile_calls = 0
        self.get_user_calls = 0
        self.auth = _FakeAuth(self)

    def table(self, name):
        assert name == "profiles"
        return _FakeQuery(self)


def test_resolve_role_normalizes_and_caches(qapp):
    client = RoleClient(" ADMIN ")
    try:
        assert resolve_role(client) == "admin"
        assert resolve_role(client) == "admin"  # cache hit: no second query
        assert client.get_user_calls == 1
        assert client.profile_calls == 1

        assert remember_role(client, " Staff ") == "staff"
        assert current_role(client) == "staff"
        assert client.profile_calls == 1
    finally:
        forget_role(client)


def test_role_lookup_failure_raises_and_current_role_returns_none():
    class BrokenClient:
        @property
        def auth(self):
            raise RuntimeError("Network offline")

    client = BrokenClient()
    with pytest.raises(RoleLookupError) as excinfo:
        resolve_role(client)
    message = str(excinfo.value)
    assert "Network offline" in message
    assert config_mod.SUPABASE_ANON_KEY not in message
    assert current_role(client) is None


# ---------------------------------------------------------------- main window
_PAGE_NAMES = [
    "OverviewPage",
    "PendingPage",
    "ResidentsPage",
    "RoomsPage",
    "MaintenancePage",
    "RoomChangesPage",
    "OfficialListPage",
    "StaffAccountsPage",
    "SettingsPage",
]


class RecordingSettings(QWidget):
    def __init__(self, client):
        super().__init__()
        self.roles = []

    def set_role(self, role):
        self.roles.append(role)


class RecordingOfficialList(QWidget):
    def __init__(self, client, **_kwargs):
        super().__init__()
        self.roles = []

    def set_role(self, role):
        self.roles.append(role)


def _patch_main_pages(monkeypatch, settings_factory=None, staff_factory=None):
    for name in _PAGE_NAMES:
        if name == "SettingsPage" and settings_factory is not None:
            factory = settings_factory
        elif name == "StaffAccountsPage" and staff_factory is not None:
            factory = staff_factory
        elif name == "OfficialListPage":
            factory = RecordingOfficialList
        else:
            # Late role promotion passes defer_initial_load/current_uid to the
            # staff page only; accepting **kwargs keeps these stubs reusable.
            factory = lambda client, **_kwargs: QWidget()
        monkeypatch.setattr(f"desktop.app.ui.main_window.{name}", factory)
    monkeypatch.setattr(main_mod.LiveSyncWorker, "start", lambda self: None)


@pytest.mark.parametrize(
    ("role", "expect_staff_page"),
    [("admin", True), ("staff", False), ("ADMIN", True)],
)
def test_main_window_role_is_case_insensitive_and_gates_staff_page(
    qapp, monkeypatch, role, expect_staff_page
):
    calls = []
    monkeypatch.setattr(
        main_mod, "current_role", lambda _client: calls.append(1) or "staff"
    )
    _patch_main_pages(monkeypatch)

    window = MainWindow(MagicMock(), role=role)
    _qapp.processEvents()

    assert window.role == role.strip().lower()
    assert calls == []  # supplied role is used without another lookup
    assert ("Staff accounts" in window.pages) is expect_staff_page
    expected_label = "Administrator" if expect_staff_page else "Housing staff"
    assert window.role_pill.text() == expected_label
    assert window.role_banner.isHidden()

    window.close()
    _qapp.processEvents()


def test_main_window_unverified_role_shows_banner_and_retries(qapp, monkeypatch):
    monkeypatch.setattr(main_mod, "current_role", lambda _client: None)
    _patch_main_pages(monkeypatch, settings_factory=RecordingSettings)

    window = MainWindow(object())
    _qapp.processEvents()

    assert window.role is None
    assert not window.role_banner.isHidden()
    assert window.role_pill.text() == "Role not verified"
    assert "Housing staff" not in window.role_pill.text()
    assert "Staff accounts" not in window.pages
    assert window.role_retry_btn.text() == "Retry"

    monkeypatch.setattr(main_mod, "resolve_role", lambda _client: "admin")
    window.role_retry_btn.click()
    assert wait_until(qapp, lambda: window.role == "admin")

    assert window.role_pill.text() == "Administrator"
    assert window.role_banner.isHidden()
    assert "Staff accounts" in window.pages
    assert window.settings_page.roles[-1] == "admin"
    assert window.official_list_page.roles[-1] == "admin"

    window.close()
    _qapp.processEvents()


def test_main_window_retry_failure_keeps_banner_and_shows_reason(qapp, monkeypatch):
    monkeypatch.setattr(main_mod, "current_role", lambda _client: None)
    _patch_main_pages(monkeypatch)

    window = MainWindow(object())

    def fail(_client):
        raise RoleLookupError("Network offline")

    monkeypatch.setattr(main_mod, "resolve_role", fail)
    window.role_retry_btn.click()
    assert wait_until(
        qapp, lambda: not window._role_retry_running and window.role_retry_btn.isEnabled()
    )

    assert window.role is None
    assert not window.role_banner.isHidden()
    assert "Network offline" in window.role_banner._message.text()
    assert "Staff accounts" not in window.pages

    window.close()
    _qapp.processEvents()


class BlockingStaffPage(QWidget):
    """Fake staff page: the legacy synchronous path would block the GUI here."""

    builds = []

    def __init__(self, client, defer_initial_load=False, current_uid=None):
        if not defer_initial_load:
            # Stand-in for the old auth + staff-list round-trip.
            time.sleep(1.0)
        super().__init__()
        self.__class__.builds.append((defer_initial_load, current_uid))
        self.reloads = 0
        self.reload()

    def reload(self):
        self.reloads += 1


class SyncGuardClient:
    """Counts synchronous auth/list calls made during the retry slot."""

    def __init__(self):
        self.get_user_calls = 0
        self.invoke_calls = 0
        self.auth = SimpleNamespace(
            get_session=lambda: None,
            get_user=self._forbidden_get_user,
        )
        self.functions = SimpleNamespace(invoke=self._forbidden_invoke)

    def _forbidden_get_user(self):
        self.get_user_calls += 1
        raise AssertionError("synchronous auth lookup during role retry")

    def _forbidden_invoke(self, *_args, **_kwargs):
        self.invoke_calls += 1
        raise AssertionError("synchronous staff list during role retry")


def test_main_window_retry_defers_staff_page_without_blocking(qapp, monkeypatch):
    BlockingStaffPage.builds = []
    monkeypatch.setattr(main_mod, "current_role", lambda _client: None)
    _patch_main_pages(monkeypatch, staff_factory=BlockingStaffPage)
    client = SyncGuardClient()

    window = MainWindow(client)
    monkeypatch.setattr(main_mod, "resolve_role", lambda _client: "admin")

    started = time.monotonic()
    window.role_retry_btn.click()
    assert wait_until(
        qapp, lambda: window.role == "admin" and "Staff accounts" in window.pages
    )
    elapsed = time.monotonic() - started

    # A synchronous constructor would have slept for a second in the slot.
    assert elapsed < 0.5
    assert BlockingStaffPage.builds == [(True, None)]
    assert client.get_user_calls == 0
    assert client.invoke_calls == 0
    assert window.pages["Staff accounts"].reloads == 1

    # Repeated retries must not build another page or duplicate the nav row.
    page_builds = len(BlockingStaffPage.builds)
    nav_rows = window.nav.count()
    window._on_role_retry_success("admin")
    _qapp.processEvents()
    assert len(BlockingStaffPage.builds) == page_builds
    assert window.nav.count() == nav_rows

    window.close()
    _qapp.processEvents()


# -------------------------------------------------------------------- settings
class _RpcCall:
    def execute(self):
        return SimpleNamespace(data={"writes_enabled": False})


class SettingsRoleClient:
    def __init__(self):
        self.auth = _FakeAuth(self)
        self.get_user_calls = 0
        self.profile_calls = 0
        self.role_value = "admin"
        self.rpc_calls = []

    def table(self, name):
        assert name == "profiles"
        return _FakeQuery(self)

    def rpc(self, name, params=None):
        self.rpc_calls.append(name)
        return _RpcCall()


def _settings_env(monkeypatch):
    monkeypatch.setattr(settings_mod, "_read_mcp_token", lambda: "tok-1234")
    started = []
    monkeypatch.setattr(
        settings_mod.McpHealthWorker, "start", lambda self: started.append(1)
    )
    return started


def test_settings_admin_role_enables_developer_mode(qapp, monkeypatch):
    started = _settings_env(monkeypatch)
    monkeypatch.setattr(settings_mod, "current_role", lambda _client: "ADMIN")
    client = SettingsRoleClient()

    page = SettingsPage(client)

    assert page.role == "admin"
    assert page._role_unverified is False
    assert page.dev_checkbox.isEnabled()
    assert not page.writes_checkbox.isHidden()
    assert started  # health poller started for admins
    page.close()


def test_settings_staff_role_promotion_reloads_writes_async(qapp, monkeypatch):
    started = _settings_env(monkeypatch)
    monkeypatch.setattr(settings_mod, "current_role", lambda _client: "staff")
    client = SettingsRoleClient()

    page = SettingsPage(client)
    assert page.role == "staff"
    assert not page.dev_checkbox.isEnabled()
    assert page.writes_checkbox.isHidden()
    assert client.rpc_calls == []  # staff construction does not load settings
    assert started == []

    page.set_role(" ADMIN ")
    assert page.role == "admin"
    assert page.dev_checkbox.isEnabled()
    assert not page.writes_checkbox.isHidden()
    assert started  # poller starts on promotion

    # Promotion starts exactly one async settings read; the checkbox becomes
    # usable once that read lands (no Settings reopen required).
    assert wait_until(qapp, lambda: client.rpc_calls == ["mcp_get_settings"])
    assert wait_until(qapp, lambda: page.writes_checkbox.isEnabled())
    assert client.rpc_calls == ["mcp_get_settings"]
    assert page._writes_available is True

    # A repeat set_role with the same admin role must not reload again.
    page.set_role("admin")
    _qapp.processEvents()
    assert client.rpc_calls == ["mcp_get_settings"]
    page.close()


def test_settings_uses_cached_role_without_profile_query(qapp, monkeypatch):
    _settings_env(monkeypatch)
    client = SettingsRoleClient()
    remember_role(client, " Admin ")
    try:
        page = SettingsPage(client)
        assert page.role == "admin"
        assert page._role_unverified is False
        assert page.dev_checkbox.isEnabled()
        assert client.get_user_calls == 0  # cached session, no auth round-trip
        assert client.profile_calls == 0  # no profile table query
        page.close()
    finally:
        forget_role(client)


def test_read_mcp_token_uses_executable_folder_when_frozen(monkeypatch, tmp_path):
    exe_dir = tmp_path / "install"
    (exe_dir / "mcp").mkdir(parents=True)
    (exe_dir / "mcp" / ".env").write_text(
        "MCP_AUTH_TOKEN=frozen-token\n", encoding="utf-8"
    )
    monkeypatch.setattr(settings_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(settings_mod.sys, "executable", str(exe_dir / "RESIVO.exe"))
    monkeypatch.setattr(
        settings_mod.sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False
    )

    assert settings_mod._read_mcp_token() == "frozen-token"


# ---------------------------------------------------------------- official list
class _FakeRosterMessageBox:
    warnings = []

    @classmethod
    def warning(cls, *args, **_kwargs):
        cls.warnings.append(args)


def test_official_list_set_role_gates_import_and_handler_stays_guarded(
    qapp, monkeypatch
):
    _FakeRosterMessageBox.warnings = []
    monkeypatch.setattr(official_mod, "QMessageBox", _FakeRosterMessageBox)
    monkeypatch.setattr("desktop.app.client.current_role", lambda _client: " Staff ")
    client = MagicMock()
    client.table.return_value.select.return_value.order.return_value.execute.return_value = (
        SimpleNamespace(data=[])
    )

    page = OfficialListPage(client)
    assert page.role == "staff"
    assert not page.import_btn.isEnabled()

    page.set_role(" ADMIN ")
    assert page.role == "admin"
    assert page.import_btn.isEnabled()

    page.set_role("staff")
    assert page.role == "staff"
    assert not page.import_btn.isEnabled()

    # Even a direct call (button bypassed) is rejected by the handler.
    page.on_import("official.csv")
    assert len(_FakeRosterMessageBox.warnings) == 1
    assert client.rpc.call_count == 0
    page.close()


# ----------------------------------------------------------------------- login
class _FakeMainWindow:
    instances = []

    def __init__(self, client, role=None):
        self.client = client
        self.role = role
        self.shown = False
        self.__class__.instances.append(self)

    def show(self):
        self.shown = True


def _login_setup(monkeypatch, resolve):
    _FakeMainWindow.instances = []
    monkeypatch.setattr(login_mod, "make_client", lambda: object())
    monkeypatch.setattr(login_mod, "sign_in", lambda *_args: None)
    monkeypatch.setattr(login_mod, "resolve_role", resolve)
    monkeypatch.setattr(login_mod, "remember_role", MagicMock())
    monkeypatch.setattr(main_mod, "MainWindow", _FakeMainWindow)
    window = LoginWindow()
    window.email.setText("admin@test.local")
    window.password.setText("secret")
    return window


def test_login_role_failure_keeps_window_and_offers_retry(qapp, monkeypatch):
    def fail(_client):
        raise RoleLookupError("Network offline")

    window = _login_setup(monkeypatch, fail)
    window.attempt()

    assert window.status.text() == login_mod._ROLE_ERROR_TEXT
    assert window.button.text() == "Retry role check"
    assert window.button.isEnabled()
    assert _FakeMainWindow.instances == []
    assert "window" not in window.__dict__
    assert login_mod.remember_role.call_count == 0

    # Retrying after the connection recovers opens the console with the role.
    monkeypatch.setattr(login_mod, "resolve_role", lambda _client: "admin")
    window.attempt()
    assert len(_FakeMainWindow.instances) == 1
    assert _FakeMainWindow.instances[0].role == "admin"
    assert _FakeMainWindow.instances[0].shown is True
    assert login_mod.remember_role.call_args.args[1] == "admin"
    window.close()


class _LoginClient:
    def __init__(self):
        self.sign_outs = 0
        self.auth = SimpleNamespace(sign_out=self._sign_out)

    def _sign_out(self):
        self.sign_outs += 1


def _login_retry_env(monkeypatch):
    """Login window whose first role check fails, then succeeds."""
    _FakeMainWindow.instances = []
    client = _LoginClient()
    sign_ins = []
    state = {"fail_role": True}

    def resolve(_client):
        if state["fail_role"]:
            raise RoleLookupError("Network offline")
        return "staff"

    monkeypatch.setattr(login_mod, "make_client", lambda: client)
    monkeypatch.setattr(
        login_mod, "sign_in", lambda _client, email, pwd: sign_ins.append((email, pwd))
    )
    monkeypatch.setattr(login_mod, "resolve_role", resolve)
    monkeypatch.setattr(login_mod, "remember_role", MagicMock())
    monkeypatch.setattr(main_mod, "MainWindow", _FakeMainWindow)

    window = LoginWindow()
    window.email.setText("old@test.local")
    window.password.setText("old-secret")
    window.attempt()
    assert window._role_retry_pending is True
    assert not window.switch_account_btn.isHidden()
    return window, client, sign_ins, state


def test_login_retry_uses_edited_credentials(qapp, monkeypatch):
    window, client, sign_ins, state = _login_retry_env(monkeypatch)
    assert sign_ins == [("old@test.local", "old-secret")]

    state["fail_role"] = False
    window.email.setText("new@test.local")
    window.password.setText("new-secret")
    window.attempt()

    # Edited credentials are a new sign-in, not a role retry on the old session.
    assert sign_ins == [
        ("old@test.local", "old-secret"),
        ("new@test.local", "new-secret"),
    ]
    assert client.sign_outs == 1
    assert len(_FakeMainWindow.instances) == 1
    assert _FakeMainWindow.instances[0].role == "staff"
    assert window._role_retry_pending is False
    assert window._pending_credentials is None
    window.close()


def test_login_role_retry_offers_account_switch(qapp, monkeypatch):
    window, client, sign_ins, state = _login_retry_env(monkeypatch)

    window.switch_account_btn.click()

    assert client.sign_outs == 1
    assert window._role_retry_pending is False
    assert window._pending_credentials is None
    assert window.button.text() == "Sign in"
    assert window.button.isEnabled()
    assert window.password.text() == ""
    assert window.switch_account_btn.isHidden()
    assert window.error_banner.isHidden()

    state["fail_role"] = False
    window.email.setText("other@test.local")
    window.password.setText("other-secret")
    window.attempt()

    assert sign_ins[-1] == ("other@test.local", "other-secret")
    assert len(_FakeMainWindow.instances) == 1
    assert _FakeMainWindow.instances[0].role == "staff"
    window.close()


def test_login_admin_role_is_passed_to_main_window(qapp, monkeypatch):
    window = _login_setup(monkeypatch, lambda _client: " Admin ")
    window.attempt()

    assert len(_FakeMainWindow.instances) == 1
    opened = _FakeMainWindow.instances[0]
    assert opened.role == "admin"
    assert opened.client is window.client
    assert opened.shown is True
    assert login_mod.remember_role.call_args.args[1] == "admin"
    window.close()


# ------------------------------------------------------------- settings footer (C1)
def test_about_diagnostics_removed_and_settings_in_footer(qapp, monkeypatch):
    _patch_main_pages(monkeypatch)
    window = MainWindow(MagicMock(), role="staff")
    _qapp.processEvents()

    # About & Diagnostics button and dialog are gone
    assert not hasattr(window, "about_diagnostics_btn")
    assert window.findChild(QPushButton, "aboutDiagnosticsButton") is None

    # Settings is in the sidebar footer
    assert hasattr(window, "settings_btn")
    settings_btn = window.findChild(QPushButton, "settingsButton")
    assert settings_btn is not None
    assert settings_btn.text() == "Settings"
    assert settings_btn.toolTip() == "Settings"

    # Settings appears ONLY ONCE: in the footer, NOT as a row in window.nav
    assert "settings" not in window.nav._by_key
    assert all(row._label_text != "Settings" for row in window.nav._rows)

    # Initially Overview is selected
    assert window.stack.currentWidget() == window.overview_page

    # Clicking Settings button switches the stack to settings_page and deselects nav
    settings_btn.click()
    _qapp.processEvents()
    assert window.stack.currentWidget() == window.settings_page
    assert window.nav.currentRow() == -1

    # Clicking a nav row switches back
    window.nav.setCurrentRow(1)
    _qapp.processEvents()
    assert window.stack.currentWidget() == window.pending_page
    assert not settings_btn.isChecked()

    window.close()
    _qapp.processEvents()


# ---------------------------------------------------------------------- config
def test_config_error_is_clear_and_never_includes_values(monkeypatch):
    monkeypatch.setattr(config_mod, "SUPABASE_URL", "")
    monkeypatch.setattr(config_mod, "SUPABASE_ANON_KEY", "super-secret-key-value")
    message = config_mod.config_error()
    assert message is not None
    assert "SUPABASE_URL" in message
    assert "super-secret-key-value" not in message

    monkeypatch.setattr(config_mod, "SUPABASE_URL", "not a URL")
    monkeypatch.setattr(config_mod, "SUPABASE_ANON_KEY", "another-secret")
    message = config_mod.config_error()
    assert message is not None
    assert "not a valid" in message
    assert "another-secret" not in message

    monkeypatch.setattr(config_mod, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config_mod, "SUPABASE_ANON_KEY", "public-anon")
    assert config_mod.config_error() is None


def test_frozen_config_prefers_the_exe_folder(monkeypatch, tmp_path):
    exe_dir = tmp_path / "install"
    bundle_dir = tmp_path / "bundle"
    monkeypatch.setattr(config_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_mod.sys, "executable", str(exe_dir / "RESIVO.exe"))
    monkeypatch.setattr(config_mod.sys, "_MEIPASS", str(bundle_dir), raising=False)

    candidates = config_mod._env_candidates()
    assert candidates == [exe_dir / ".env", bundle_dir / ".env"]
