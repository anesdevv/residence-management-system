"""Phase 2 regression tests: zero top-level ghost windows across UI & startup paths."""

from __future__ import annotations

import gc
import os
import sys
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.app.startup_debug import install_ghost_window_probe, uninstall_ghost_window_probe
from desktop.app.ui.components import (
    Card,
    DetailPanel,
    InlineBanner,
    PageHeader,
    RoomOccupancyBar,
    SearchField,
)
from desktop.app.ui.login_window import LoginWindow
from desktop.app.ui.main_window import MainWindow
from desktop.auth.session_store import FakeBackend, SessionManager, SessionStore
from desktop.main import launch_application

_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


@pytest.fixture
def qapp():
    return _qapp


@pytest.fixture(autouse=True)
def _cleanup_probe(qapp):
    uninstall_ghost_window_probe(qapp)
    gc.collect()
    qapp.processEvents()
    yield
    QThreadPool.globalInstance().waitForDone(5000)
    uninstall_ghost_window_probe(qapp)
    qapp.processEvents()


def _wait_until(qapp, predicate, timeout=5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    qapp.processEvents()
    return bool(predicate())


class _FakeResp:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count if count is not None else (len(data) if isinstance(data, list) else 0)


class _FakeQuery:
    def __init__(self, table: str):
        self.table = table
        self._filters: list[tuple[str, object]] = []

    def select(self, *_a, **_kw):
        return self

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def neq(self, *_a, **_kw):
        return self

    def order(self, *_a, **_kw):
        return self

    def range(self, *_a, **_kw):
        return self

    def single(self):
        return self

    def execute(self):
        if self.table == "profiles":
            return _FakeResp({"role": "admin"})
        if self.table == "students":
            rows = [
                {
                    "id": f"stu-{i}",
                    "card_id": f"2024370100{i:02d}",
                    "first_name": "Amine",
                    "last_name": f"Student{i}",
                    "birth_date": "2003-01-01",
                    "gender": "female",
                    "phone": "0550000000",
                    "email": f"stu{i}@example.com",
                    "university": "UABB",
                    "faculty": "Sci",
                    "study_level": "L1",
                    "wilaya": "Tlemcen",
                    "status": "pending" if i < 2 else "active",
                    "rejection_reason": None,
                    "room_id": "room-1" if i >= 2 else None,
                    "reviewed_by": None,
                    "reviewed_at": None,
                    "created_at": "2026-10-10T10:00:00Z",
                    "rooms": {"block": "A", "number": "101", "floor": 1} if i >= 2 else None,
                }
                for i in range(4)
            ]
            for col, val in self._filters:
                rows = [r for r in rows if r.get(col) == val]
            return _FakeResp(rows, count=len(rows))
        if self.table == "rooms":
            return _FakeResp([{"id": "room-1", "block": "B", "floor": 1, "number": "101", "capacity": 2}])
        if self.table == "blocks":
            return _FakeResp([{"id": "blk-b", "name": "B"}])
        if self.table == "official_residents":
            return _FakeResp([
                {
                    "card_id": "202437010000",
                    "first_name": "Amine",
                    "last_name": "Student0",
                    "birth_date": "2003-01-01",
                    "gender": "female",
                    "university": "UABB",
                    "faculty": "Sci",
                }
            ])
        if self.table == "maintenance_reports":
            return _FakeResp([
                {
                    "id": "rep-1",
                    "student_id": "stu-2",
                    "category": "plumbing",
                    "description": "Sink leak",
                    "photo_path": None,
                    "status": "pending",
                    "staff_note": None,
                    "created_at": "2026-10-12T10:00:00Z",
                    "updated_at": "2026-10-12T10:00:00Z",
                    "students": {"first_name": "Amine", "last_name": "Student2", "card_id": "202437010002"},
                }
            ])
        if self.table == "room_change_requests":
            return _FakeResp([
                {
                    "id": "rcr-1",
                    "student_id": "stu-2",
                    "current_room_id": "room-1",
                    "preferred_room_id": "room-1",
                    "reason": "Quiet room",
                    "status": "pending",
                    "decision_note": None,
                    "decided_by": None,
                    "decided_at": None,
                    "created_at": "2026-10-13T10:00:00Z",
                    "updated_at": "2026-10-13T10:00:00Z",
                    "students": {"first_name": "Amine", "last_name": "Student2", "gender": "female", "card_id": "202437010002"},
                    "staff": None,
                }
            ])
        return _FakeResp([])


class _FakeAuth:
    def __init__(self):
        self._in_memory_session = SimpleNamespace(
            access_token="acc",
            refresh_token="ref",
            expires_at=1900000000,
            user=SimpleNamespace(id="admin-1", email="admin@univ-tlemcen.dz", user_metadata={"full_name": "Admin"}),
        )

    def sign_in_with_password(self, _creds):
        return SimpleNamespace(session=self._in_memory_session, user=self._in_memory_session.user)

    def set_session(self, _acc, _ref):
        return SimpleNamespace(session=self._in_memory_session, user=self._in_memory_session.user)

    def get_user(self):
        return SimpleNamespace(user=self._in_memory_session.user)

    def sign_out(self):
        pass


class _FakeClient:
    def __init__(self):
        self.auth = _FakeAuth()
        self.functions = SimpleNamespace(
            invoke=lambda name, **_kw: b'[{"id":"admin-1","full_name":"Admin","position":"Administrator"}]'
            if name == "admin-users"
            else b"{}"
        )

    def table(self, name: str):
        return _FakeQuery(name)

    def rpc(self, name: str, _params=None):
        def _exec():
            if name == "overview_stats":
                return _FakeResp({"pending": 2, "reports": 1, "requests": 1, "occupancy": 2})
            if name == "get_room_occupancy":
                return _FakeResp([{"room_id": "room-1", "occupied": 2}])
            if name == "get_residence_public":
                return _FakeResp({"residence_name": "Cité Universitaire · Tlemcen", "residence_gender": "female"})
            if name == "get_residence_settings_admin":
                return _FakeResp({
                    "residence_name": "Cité Universitaire · Tlemcen",
                    "residence_gender": "female",
                    "last_changed_at": "2026-11-11T09:00:00Z",
                    "last_changed_by_name": "Admin",
                })
            if name == "mcp_get_settings":
                return _FakeResp({"writes_enabled": True})
            return _FakeResp({})

        return SimpleNamespace(execute=_exec)


def test_shared_components_emit_zero_ghost_windows(qapp):
    probe = install_ghost_window_probe(qapp, whitelist={"LoginWindow", "MainWindow"}, force=True)
    probe.clear()

    widgets = [
        PageHeader("Title"),
        PageHeader("Title", "Subtitle text"),
        InlineBanner("info", title="Heads up", message="Details here"),
        InlineBanner("warning", title="Only title", message=""),
        InlineBanner("error", title=None, message="Only message"),
        InlineBanner("success", title="", message=""),
        Card("Card Title", "Card Subtitle", icon="info"),
        Card(),
        DetailPanel(320, 460),
        RoomOccupancyBar(2, 4),
        RoomOccupancyBar(4, 4),
        SearchField("Search…"),
    ]
    qapp.processEvents()
    for w in widgets:
        w.close()

    assert probe.unexpected_events == [], [
        (e.event_type, e.class_name, e.stack) for e in probe.unexpected_events
    ]


def test_login_to_main_window_and_navigation_zero_ghost_windows(qapp, tmp_path):
    probe = install_ghost_window_probe(qapp, whitelist={"LoginWindow", "MainWindow"}, force=True)
    probe.clear()

    store = SessionStore(backend=FakeBackend(), storage_dir=tmp_path)
    sm = SessionManager(store=store)
    client = _FakeClient()

    login = LoginWindow(client=client, session_manager=sm)
    login.email.setText("admin@univ-tlemcen.dz")
    login.password.setText("Secret123!")
    login.show()
    qapp.processEvents()

    login.attempt()
    assert _wait_until(qapp, lambda: isinstance(getattr(login, "window", None), MainWindow), timeout=5.0)
    mw: MainWindow = login.window
    qapp.processEvents()

    # Visit all navigation rows + settings + toggle sidebar
    for idx in range(mw.nav.count()):
        mw.nav.setCurrentRow(idx)
        qapp.processEvents()
    mw.settings_btn.click()
    qapp.processEvents()
    toggle_btn = mw.findChild(QPushButton, "toggleMenuButton")
    if toggle_btn is not None:
        toggle_btn.click()
        qapp.processEvents()
        toggle_btn.click()
        qapp.processEvents()

    assert probe.unexpected_events == [], [
        (e.event_type, e.class_name, e.window_title, e.stack) for e in probe.unexpected_events
    ]

    mw._shutdown_confirmed = True
    mw.close()
    _wait_until(qapp, lambda: not mw.isVisible(), timeout=3.0)
    login.close()


def test_session_restore_and_restarted_startup_zero_ghost_windows(qapp, monkeypatch, tmp_path):
    probe = install_ghost_window_probe(qapp, whitelist={"LoginWindow", "MainWindow"}, force=True)
    probe.clear()

    store = SessionStore(backend=FakeBackend(), storage_dir=tmp_path)
    sm = SessionManager(store=store)
    store.save(
        {
            "access_token": "tok_a",
            "refresh_token": "tok_r",
            "expires_at": 1900000000,
            "user_id": "admin-1",
        },
        remember=True,
    )
    client = _FakeClient()

    monkeypatch.setattr(sys, "argv", [sys.argv[0], "--restarted"])
    launch_application(
        app=qapp,
        client=client,
        session_manager_instance=sm,
        exec_loop=False,
    )
    assert _wait_until(qapp, lambda: isinstance(getattr(qapp, "_main_window", None), MainWindow), timeout=5.0)
    mw = qapp._main_window
    qapp.processEvents()

    assert probe.unexpected_events == [], [
        (e.event_type, e.class_name, e.window_title, e.stack) for e in probe.unexpected_events
    ]

    mw._shutdown_confirmed = True
    mw.close()
    _wait_until(qapp, lambda: not mw.isVisible(), timeout=3.0)
    qapp._main_window = None
