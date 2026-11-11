"""Phase 1 tests: non-blocking, responsive sign-in with busy UI & idle warm-up."""

from __future__ import annotations

import os
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThreadPool, QTimer
from PySide6.QtWidgets import QApplication

from desktop.app.client import warm_connection
from desktop.app.ui import login_window as login_mod
from desktop.app.ui import main_window as main_mod
from desktop.app.ui.login_window import LoginWindow
from desktop.i18n import t

_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


@pytest.fixture
def qapp():
    return _qapp


@pytest.fixture(autouse=True)
def _drain_pool(qapp, monkeypatch):
    yield
    QThreadPool.globalInstance().waitForDone(5000)
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


class _FakeMainWindow:
    instances = []

    def __init__(self, client, role=None):
        self.client = client
        self.role = role
        self.shown = False
        self.__class__.instances.append(self)

    def show(self):
        self.shown = True

    def raise_(self):
        pass

    def activateWindow(self):
        pass


class _Heartbeat:
    def __init__(self, interval_ms: int = 25):
        self.timer = QTimer()
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self._tick)
        self._last: float | None = None
        self.largest_gap_ms = 0.0
        self.ticks = 0

    def start(self):
        self._last = time.perf_counter()
        self.timer.start()

    def _tick(self):
        now = time.perf_counter()
        if self._last is not None:
            gap = (now - self._last) * 1000.0
            if gap > self.largest_gap_ms:
                self.largest_gap_ms = gap
        self._last = now
        self.ticks += 1

    def stop(self):
        self.timer.stop()


def test_sign_in_gives_immediate_busy_feedback_and_never_freezes_gui(qapp, monkeypatch, _drain_pool):
    _FakeMainWindow.instances = []
    client = SimpleNamespace(auth=SimpleNamespace(sign_out=lambda: None))
    monkeypatch.setattr(login_mod, "make_client", lambda: client)
    monkeypatch.setattr(main_mod, "MainWindow", _FakeMainWindow)
    monkeypatch.setattr(login_mod, "remember_role", MagicMock())

    def slow_sign_in(_client, _email, _pwd):
        time.sleep(0.35)

    def slow_resolve_role(_client):
        time.sleep(0.25)
        return "admin"

    monkeypatch.setattr(login_mod, "sign_in", slow_sign_in)
    monkeypatch.setattr(login_mod, "resolve_role", slow_resolve_role)

    win = LoginWindow()
    win.email.setText("admin@test.local")
    win.password.setText("Secret123!")
    win.show()
    qapp.processEvents()

    hb = _Heartbeat(interval_ms=25)
    try:
        hb.start()
        t0 = time.perf_counter()

        win.button.click()
        qapp.processEvents()
        feedback_ms = (time.perf_counter() - t0) * 1000.0

        # Busy state appears immediately (< 100 ms) while worker runs in background
        assert feedback_ms < 100.0
        assert win._busy is True
        assert not win.button.isEnabled()
        assert not win.email.isEnabled()
        assert not win.password.isEnabled()
        assert not win.remember_checkbox.isEnabled()
        assert win.button.text() == t("login.signing_in")
        assert not win.busy_bar.isHidden()

        # Wait for phase update to Checking role...
        saw_role_phase = _wait_until(
            qapp, lambda: win.button.text() == t("login.checking_role") or len(_FakeMainWindow.instances) == 1, timeout=2.0
        )
        assert saw_role_phase

        # Wait for transition to MainWindow
        opened = _wait_until(qapp, lambda: len(_FakeMainWindow.instances) == 1, timeout=3.0)
        assert opened is True
        assert _FakeMainWindow.instances[0].shown is True
        assert _FakeMainWindow.instances[0].role == "admin"
        assert hb.largest_gap_ms < 150.0, f"GUI blocked during login: {hb.largest_gap_ms:.1f} ms"
        assert hb.ticks >= 8
    finally:
        hb.stop()
        win.close()


def test_double_click_or_reentry_blocked_while_busy(qapp, monkeypatch):
    _FakeMainWindow.instances = []
    sign_in_calls = []
    client = SimpleNamespace(auth=SimpleNamespace(sign_out=lambda: None))
    monkeypatch.setattr(login_mod, "make_client", lambda: client)
    monkeypatch.setattr(main_mod, "MainWindow", _FakeMainWindow)
    monkeypatch.setattr(login_mod, "remember_role", MagicMock())

    def counted_sign_in(_client, email, pwd):
        time.sleep(0.15)
        sign_in_calls.append((email, pwd))

    monkeypatch.setattr(login_mod, "sign_in", counted_sign_in)
    monkeypatch.setattr(login_mod, "resolve_role", lambda _c: "staff")

    win = LoginWindow()
    win.email.setText("staff@test.local")
    win.password.setText("Secret123!")

    win.attempt()
    win.attempt()
    win.password.returnPressed.emit()
    qapp.processEvents()

    assert _wait_until(qapp, lambda: len(_FakeMainWindow.instances) == 1, timeout=3.0)
    assert len(sign_in_calls) == 1
    assert len(_FakeMainWindow.instances) == 1
    win.close()


def test_auth_failure_restores_controls_and_clears_busy(qapp, monkeypatch):
    _FakeMainWindow.instances = []
    client = SimpleNamespace(auth=SimpleNamespace(sign_out=lambda: None))
    monkeypatch.setattr(login_mod, "make_client", lambda: client)
    monkeypatch.setattr(main_mod, "MainWindow", _FakeMainWindow)

    def bad_sign_in(_client, _email, _pwd):
        time.sleep(0.1)
        raise RuntimeError("Invalid login credentials")

    monkeypatch.setattr(login_mod, "sign_in", bad_sign_in)

    win = LoginWindow()
    win.email.setText("admin@test.local")
    win.password.setText("wrong")
    win.attempt()
    qapp.processEvents()
    assert win._busy is True

    assert _wait_until(qapp, lambda: not win._busy, timeout=3.0)
    assert win.button.isEnabled()
    assert win.email.isEnabled()
    assert win.password.isEnabled()
    assert win.remember_checkbox.isEnabled()
    assert win.button.text() == t("login.sign_in")
    assert win.busy_bar.isHidden()
    assert win.password.text() == ""
    assert not win.error_banner.isHidden()
    assert _FakeMainWindow.instances == []
    win.close()


def test_closing_login_window_mid_auth_discards_result(qapp, monkeypatch):
    _FakeMainWindow.instances = []
    finished = threading.Event()
    client = SimpleNamespace(auth=SimpleNamespace(sign_out=lambda: None))
    monkeypatch.setattr(login_mod, "make_client", lambda: client)
    monkeypatch.setattr(main_mod, "MainWindow", _FakeMainWindow)
    monkeypatch.setattr(login_mod, "remember_role", MagicMock())

    def slow_sign_in(_client, _email, _pwd):
        time.sleep(0.18)
        finished.set()

    monkeypatch.setattr(login_mod, "sign_in", slow_sign_in)
    monkeypatch.setattr(login_mod, "resolve_role", lambda _c: "admin")

    win = LoginWindow()
    win.email.setText("admin@test.local")
    win.password.setText("Secret123!")
    win.attempt()
    qapp.processEvents()
    win.close()
    qapp.processEvents()

    assert finished.wait(timeout=2.0)
    QThreadPool.globalInstance().waitForDone(2000)
    qapp.processEvents()
    assert _FakeMainWindow.instances == []


def test_warm_connection_is_safe_offline_and_cancelable():
    warm_connection(None)

    class _ExplodingHttp:
        def get(self, *_a, **_kw):
            raise ConnectionError("offline")

        def head(self, *_a, **_kw):
            raise ConnectionError("offline")

    broken_client = SimpleNamespace(
        auth=SimpleNamespace(_http_client=_ExplodingHttp(), _url="https://invalid.example.local/auth/v1"),
        postgrest=SimpleNamespace(session=_ExplodingHttp(), base_url="https://invalid.example.local/rest/v1"),
    )
    warm_connection(broken_client)

    calls = []
    tracked_client = SimpleNamespace(
        auth=SimpleNamespace(
            _http_client=SimpleNamespace(get=lambda url, **_kw: calls.append(url)),
            _url="https://valid.example.local/auth/v1",
        ),
        postgrest=SimpleNamespace(
            session=SimpleNamespace(head=lambda url, **_kw: calls.append(url)),
            base_url="https://valid.example.local/rest/v1",
        ),
    )
    cancelled = threading.Event()
    cancelled.set()
    warm_connection(tracked_client, cancel_event=cancelled)
    assert calls == []

    warm_connection(tracked_client)
    assert calls == [
        "https://valid.example.local/auth/v1/health",
        "https://valid.example.local/rest/v1/",
    ]
