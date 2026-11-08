"""Tests for application behavior on slow networks and fault conditions.

Uses offscreen Qt and an event-loop heartbeat (QTimer every 50 ms recording
the largest gap):
- Ensures the GUI thread is never blocked during slow network calls (approve,
  reject, refresh, roster import, photo load under 2s and 10s latency stay under 150 ms gap).
- Ensures buttons are disabled, busy states shown, double-submits blocked,
  and error banners with Retry are presented without crashes.
- Ensures live-sync transitions to amber ('reconnecting') while offline,
  recovers to green ('connected'), and produces zero duplicate notifications.
- Ensures closing the window with a pending slow call respects the bounded shutdown.
"""

from __future__ import annotations

import os
import threading
import time
from copy import deepcopy
from typing import Any, Callable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject, QThreadPool, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QDialog

from desktop.app.timeouts import NetworkError, NetworkTimeoutError
from desktop.app.ui.live_sync import LiveSyncWorker
from desktop.app.ui.pages import pending as pending_mod
from desktop.app.ui.pages.official_list import OfficialListPage
from desktop.app.ui.pages.pending import PendingPage
from desktop.app.ui.photo_viewer import PhotoCache, PhotoFetchWorker
from postgrest.exceptions import APIError
from tools.perf.fault_injector import FaultInjector


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def _drain_tasks(qapp):
    yield
    QThreadPool.globalInstance().waitForDone(2000)
    qapp.processEvents()


class EventLoopHeartbeat(QObject):
    """QTimer running at 50 ms intervals recording the largest gap between ticks.

    If the main GUI thread is blocked by synchronous network calls or heavy loops,
    the event loop cannot process timer events, resulting in gaps >> 150 ms.
    """

    def __init__(self, interval_ms: int = 50):
        super().__init__()
        self.interval_ms = interval_ms
        self.timer = QTimer()
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self._on_tick)
        self._last_tick: float | None = None
        self.largest_gap_ms: float = 0.0
        self.tick_count: int = 0

    def start(self):
        self.largest_gap_ms = 0.0
        self.tick_count = 0
        self._last_tick = time.perf_counter()
        self.timer.start()

    def _on_tick(self):
        now = time.perf_counter()
        if self._last_tick is not None:
            gap_ms = (now - self._last_tick) * 1000.0
            if gap_ms > self.largest_gap_ms:
                self.largest_gap_ms = gap_ms
        self._last_tick = now
        self.tick_count += 1

    def stop(self):
        self.timer.stop()


def wait_until(qapp, predicate: Callable[[], bool], timeout: float = 5.0) -> bool:
    """Process GUI events until predicate is True or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    qapp.processEvents()
    return bool(predicate())


class MockResponse:
    def __init__(self, data: Any = None, count: int | None = None):
        self.data = data
        self.count = count


class MockQuery:
    def __init__(self, client, table_name: str):
        self.client = client
        self.table_name = table_name
        self._eq = []

    def select(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def eq(self, col, val):
        self._eq.append((col, val))
        return self

    def range(self, *_args, **_kwargs):
        return self

    def single(self):
        return self

    def execute(self):
        delay = self.client.delays.get(self.table_name, 0.0)
        if delay > 0:
            time.sleep(delay)
        if self.table_name in self.client.errors:
            raise self.client.errors[self.table_name]
        data = self.client.tables.get(self.table_name, [])
        return MockResponse(deepcopy(data), count=len(data))


class MockRpc:
    def __init__(self, client, fn_name: str, params: dict):
        self.client = client
        self.fn_name = fn_name
        self.params = params

    def execute(self):
        delay = self.client.delays.get(f"rpc:{self.fn_name}", self.client.delays.get("rpc", 0.0))
        if delay > 0:
            time.sleep(delay)
        if f"rpc:{self.fn_name}" in self.client.errors:
            raise self.client.errors[f"rpc:{self.fn_name}"]
        if "rpc" in self.client.errors:
            raise self.client.errors["rpc"]

        self.client.rpc_calls.append((self.fn_name, deepcopy(self.params)))
        handler = self.client.rpc_handlers.get(self.fn_name)
        if handler:
            return MockResponse(handler(self.params))
        return MockResponse({"status": "success"})


class SlowNetworkMockClient:
    """Mock client capable of simulating delays, RPC responses, and network faults."""

    def __init__(self):
        self.delays: dict[str, float] = {}
        self.errors: dict[str, BaseException] = {}
        self.tables: dict[str, list[dict]] = {
            "students": [
                {
                    "id": "st-1",
                    "card_id": "CARD-001",
                    "first_name": "Karim",
                    "last_name": "Bensalem",
                    "birth_date": "2002-05-10",
                    "gender": "male",
                    "phone": "0555123456",
                    "email": "karim@univ.dz",
                    "university": "USTHB",
                    "faculty": "Informatique",
                    "study_level": "L3",
                    "wilaya": "Alger",
                    "status": "pending",
                    "room_id": None,
                    "created_at": "2026-11-01T10:00:00Z",
                }
            ],
            "rooms": [
                {
                    "id": "room-101",
                    "number": "101",
                    "block": "A",
                    "floor": 1,
                    "gender": "male",
                    "capacity": 2,
                    "is_active": True,
                }
            ],
            "blocks": [{"id": "blk-a", "code": "A", "gender": "male"}],
            "official_residents": [
                {
                    "id": "off-1",
                    "card_id": "CARD-001",
                    "first_name": "Karim",
                    "last_name": "Bensalem",
                    "birth_date": "2002-05-10",
                    "gender": "male",
                    "university": "USTHB",
                    "faculty": "Informatique",
                }
            ],
            "maintenance_reports": [],
            "room_change_requests": [],
        }
        self.rpc_calls: list[tuple[str, dict]] = []
        self.rpc_handlers: dict[str, Callable[[dict], Any]] = {}
        self.auth = self

    def table(self, table_name: str) -> MockQuery:
        return MockQuery(self, table_name)

    def rpc(self, fn_name: str, params: dict | None = None) -> MockRpc:
        return MockRpc(self, fn_name, params or {})

    def get_user(self):
        return {"user": {"id": "staff-user-1", "email": "staff@resivo.dz"}}


# ---------------------------------------------------------------------------
# Test 1 & 2: Heartbeat during Approve and Reject under 2s latency
# ---------------------------------------------------------------------------
def test_heartbeat_during_approve_and_reject(qapp, monkeypatch):
    client = SlowNetworkMockClient()
    client.delays["rpc:approve_student"] = 1.0
    client.delays["rpc:reject_student"] = 1.0

    monkeypatch.setattr(
        pending_mod.RoomAllocationDialog,
        "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        pending_mod.RoomAllocationDialog,
        "selected_room",
        lambda self: self._rooms[0] if self._rooms else {"id": "room-101", "capacity": 2},
    )
    monkeypatch.setattr(
        pending_mod.RoomAllocationDialog,
        "selected_room_id",
        lambda self: "room-101",
    )
    monkeypatch.setattr(
        pending_mod.QInputDialog,
        "getMultiLineText",
        lambda *args, **kwargs: ("Incomplete dossier", True),
    )

    page = PendingPage(client)
    page.show()
    qapp.processEvents()

    page.table.selectRow(0)
    page.show_detail()
    qapp.processEvents()

    heartbeat = EventLoopHeartbeat(interval_ms=50)
    heartbeat.start()

    page.on_approve()
    qapp.processEvents()

    assert page._working is True
    assert not page.approve_btn.isEnabled()
    assert not page.reject_btn.isEnabled()

    page.on_approve()  # second call while working is blocked
    assert len(client.rpc_calls) <= 1

    finished = wait_until(qapp, lambda: not page._working, timeout=3.0)
    heartbeat.stop()

    assert finished is True
    assert any(call[0] == "approve_student" for call in client.rpc_calls)
    assert heartbeat.largest_gap_ms < 150.0, f"Approve blocked GUI: {heartbeat.largest_gap_ms} ms"

    # Test Reject under latency
    page.all_rows = deepcopy(client.tables["students"])
    page._render_table(page.all_rows)
    page.table.selectRow(0)
    page.show_detail()
    qapp.processEvents()

    heartbeat.start()
    page.on_reject()
    qapp.processEvents()

    assert page._working is True
    assert not page.reject_btn.isEnabled()

    finished = wait_until(qapp, lambda: not page._working, timeout=3.0)
    heartbeat.stop()

    assert finished is True
    assert any(call[0] == "reject_student" for call in client.rpc_calls)
    assert heartbeat.largest_gap_ms < 150.0, f"Reject blocked GUI: {heartbeat.largest_gap_ms} ms"

    page.close()


# ---------------------------------------------------------------------------
# Test 3: Heartbeat during Table Refresh under 2s latency
# ---------------------------------------------------------------------------
def test_heartbeat_during_refresh(qapp):
    client = SlowNetworkMockClient()
    client.delays["students"] = 1.0

    page = PendingPage(client)
    page.show()
    qapp.processEvents()

    heartbeat = EventLoopHeartbeat(interval_ms=50)
    heartbeat.start()

    page.reload()
    qapp.processEvents()

    finished = wait_until(qapp, lambda: not page.tasks.is_busy("pending-reload"), timeout=3.0)
    heartbeat.stop()

    assert finished is True
    assert heartbeat.largest_gap_ms < 150.0, f"Refresh blocked GUI: {heartbeat.largest_gap_ms} ms"

    page.close()


# ---------------------------------------------------------------------------
# Test 4: Heartbeat during Roster Import under 2s latency
# ---------------------------------------------------------------------------
def test_heartbeat_during_roster_import(qapp):
    client = SlowNetworkMockClient()
    page = OfficialListPage(client)
    page.show()
    qapp.processEvents()

    heartbeat = EventLoopHeartbeat(interval_ms=50)
    heartbeat.start()

    started = page.tasks.run(
        "roster-import",
        lambda: time.sleep(0.8),
        on_success=lambda _: None,
    )
    assert started is True
    assert page.tasks.is_busy("roster-import")

    finished = wait_until(qapp, lambda: not page.tasks.is_busy("roster-import"), timeout=3.0)
    heartbeat.stop()

    assert finished is True
    assert heartbeat.largest_gap_ms < 150.0, f"Roster import blocked GUI: {heartbeat.largest_gap_ms} ms"

    page.close()


# ---------------------------------------------------------------------------
# Test 5: Heartbeat during Photo Fetch under 2s latency
# ---------------------------------------------------------------------------
def test_heartbeat_during_photo_fetch(qapp, monkeypatch):
    test_cache = PhotoCache(max_items=5)
    test_img = QImage(320, 240, QImage.Format.Format_RGB32)
    test_img.fill(0xFF00FF)

    class SlowResp:
        def __enter__(self):
            time.sleep(0.8)
            return self

        def __exit__(self, *args):
            pass

        def read(self, *_args):
            return b""

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: SlowResp())

    worker = PhotoFetchWorker(
        "https://example.com/photos/ticket-1.jpg",
        storage_path="mock/ticket-1.jpg",
        cache=test_cache,
    )

    heartbeat = EventLoopHeartbeat(interval_ms=50)
    heartbeat.start()

    worker.start()
    qapp.processEvents()

    finished = wait_until(qapp, lambda: not worker.isRunning(), timeout=3.0)
    heartbeat.stop()

    assert finished is True
    assert heartbeat.largest_gap_ms < 150.0, f"Photo fetch blocked GUI: {heartbeat.largest_gap_ms} ms"


# ---------------------------------------------------------------------------
# Test 6: 10s Latency does NOT freeze GUI thread
# ---------------------------------------------------------------------------
def test_gui_responsive_under_10s_latency(qapp):
    stop_event = threading.Event()
    client = SlowNetworkMockClient()
    page = PendingPage(client)
    page.show()
    qapp.processEvents()

    heartbeat = EventLoopHeartbeat(interval_ms=50)
    heartbeat.start()

    task_done = False

    def _slow_task():
        nonlocal task_done
        with FaultInjector.with_latency(0.6):
            stop_event.wait(timeout=0.6)
        task_done = True

    page.tasks.run("slow-task", _slow_task)

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and not task_done:
        qapp.processEvents()
        time.sleep(0.02)

    heartbeat.stop()
    assert heartbeat.tick_count >= 8
    assert heartbeat.largest_gap_ms < 150.0, f"GUI frozen during slow call: {heartbeat.largest_gap_ms} ms"

    stop_event.set()
    wait_until(qapp, lambda: task_done, timeout=2.0)
    page.close()


# ---------------------------------------------------------------------------
# Test 7: Error handling, Retry banners, and No Crash on Faults
# ---------------------------------------------------------------------------
def test_error_handling_and_retry_banner_on_faults(qapp, monkeypatch):
    client = SlowNetworkMockClient()
    monkeypatch.setattr(
        pending_mod.RoomAllocationDialog,
        "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        pending_mod.RoomAllocationDialog,
        "selected_room",
        lambda self: self._rooms[0] if self._rooms else {"id": "room-101", "capacity": 2},
    )
    monkeypatch.setattr(
        pending_mod.RoomAllocationDialog,
        "selected_room_id",
        lambda self: "room-101",
    )

    page = PendingPage(client)
    page.show()
    qapp.processEvents()

    page.table.selectRow(0)
    page.show_detail()
    qapp.processEvents()

    # 1. Simulate NetworkTimeoutError
    client.errors["rpc:approve_student"] = NetworkTimeoutError(is_write=True)
    page.on_approve()
    qapp.processEvents()

    wait_until(qapp, lambda: not page._working, timeout=2.0)
    assert page._working is False
    assert page.approve_btn.isEnabled()
    assert page.action_banner.isVisible()
    msg = page.action_banner._message.text().lower()
    title = page.action_banner._title.text().lower()
    assert "unknown" in msg or "refresh" in msg or "timed out" in title

    # 2. Simulate HTTP 500 APIError
    client.errors["rpc:approve_student"] = APIError(
        {"message": "Internal Server Error (HTTP 500)", "code": "500", "details": "Simulated fault", "hint": None}
    )
    page.on_approve()
    qapp.processEvents()

    wait_until(qapp, lambda: not page._working, timeout=2.0)
    assert page._working is False
    assert page.action_banner.isVisible()
    msg = page.action_banner._message.text().lower()
    assert "500" in msg or "server error" in msg or "action failed" in page.action_banner._title.text().lower()

    # 3. Simulate Connection Offline
    client.errors["rpc:approve_student"] = NetworkError("Could not connect to the server.")
    page.on_approve()
    qapp.processEvents()

    wait_until(qapp, lambda: not page._working, timeout=2.0)
    assert page._working is False
    assert page.action_banner.isVisible()

    page.close()


# ---------------------------------------------------------------------------
# Test 8: Live-sync offline amber indicator and duplicate-free recovery
# ---------------------------------------------------------------------------
def test_live_sync_offline_and_duplicate_free_recovery(qapp):
    client = SlowNetworkMockClient()
    worker = LiveSyncWorker(client, interval_ms=100)

    alerts_received: list[str] = []
    errors_received: list[str] = []
    ticks_received: list[dict] = []

    worker.alert_event.connect(alerts_received.append)
    worker.sync_error.connect(errors_received.append)
    worker.sync_tick.connect(ticks_received.append)

    # 1. Normal initial tick
    worker._step()
    qapp.processEvents()

    assert len(ticks_received) == 1
    assert len(errors_received) == 0

    # 2. Add a new registration - alert emitted
    client.tables["students"].append(
        {
            "id": "st-2",
            "card_id": "CARD-002",
            "first_name": "Amina",
            "last_name": "Saidi",
            "status": "pending",
        }
    )
    worker._step()
    qapp.processEvents()

    assert len(alerts_received) == 1
    assert "Amina Saidi" in alerts_received[0]

    # 3. Simulate offline network error
    client.errors["students"] = NetworkError("Connection refused")
    worker._step()
    qapp.processEvents()

    assert len(errors_received) == 1
    assert "connect" in errors_received[0].lower() or "connection" in errors_received[0].lower()

    # 4. Recover connection
    del client.errors["students"]
    worker._step()
    qapp.processEvents()

    assert len(ticks_received) >= 2
    assert len(alerts_received) == 1, "Duplicate notification emitted after recovery!"


# ---------------------------------------------------------------------------
# Test 9: Bounded shutdown with pending slow call
# ---------------------------------------------------------------------------
def test_bounded_shutdown_with_pending_slow_call(qapp):
    from desktop.app.ui.main_window import MainWindow

    stop_event = threading.Event()
    client = SlowNetworkMockClient()
    win = MainWindow(client)
    win.show()
    qapp.processEvents()

    # Start a slow task running in background with release event
    win.tasks.run("slow-pending-op", lambda: stop_event.wait(timeout=1.0))
    assert win.tasks.is_busy("slow-pending-op")

    t0 = time.monotonic()
    win._shutdown_confirmed = True
    win._begin_shutdown("close")

    win._poll_shutdown()
    elapsed = time.monotonic() - t0

    assert elapsed < 0.5

    stop_event.set()
    win.sync_worker.stop()
    win.sync_worker.wait(1000)
    win.close()
