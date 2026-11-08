"""Network resilience, timeout enforcement, and anti-hang guardrails tests.

Verifies:
1. Timeouts and error translation (NetworkTimeoutError / friendly messages).
2. Automatic single retry for idempotent reads.
3. Strict zero-retry policy for mutating writes.
4. "The result is unknown" message and record refresh on write timeouts.
5. GUI responsiveness (heartbeat QTimer gap < 150 ms during background network waits).
6. LiveSyncWorker survival on timeout and indicator state transitions (connected -> reconnecting -> connected).
"""

from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import httpx
import pytest
from PySide6.QtCore import QObject, QThread, QThreadPool, QTimer
from PySide6.QtWidgets import QApplication

from desktop.app.timeouts import (
    CONNECT_TIMEOUT_S,
    READ_TIMEOUT_S,
    WRITE_TIMEOUT_S,
    STORAGE_DOWNLOAD_TIMEOUT_S,
    STORAGE_UPLOAD_TIMEOUT_S,
    EDGE_FUNCTION_TIMEOUT_S,
    NetworkError,
    NetworkTimeoutError,
    execute_network_call,
    is_timeout_exception,
)
from desktop.app.ui.tasks import TaskRunner, human_error
from desktop.app.ui.live_sync import LiveSyncWorker
from desktop.app.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def drain_tasks(qapp):
    yield
    QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()


def wait_until(predicate, qapp, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return False


# ---------------------------------------------------------------------------
# 1. Central Timeouts Constants & Exception Hierarchy
# ---------------------------------------------------------------------------
def test_timeout_constants():
    assert CONNECT_TIMEOUT_S == 5.0
    assert READ_TIMEOUT_S == 10.0
    assert WRITE_TIMEOUT_S == 20.0
    assert STORAGE_DOWNLOAD_TIMEOUT_S == 20.0
    assert STORAGE_UPLOAD_TIMEOUT_S == 30.0
    assert EDGE_FUNCTION_TIMEOUT_S == 30.0


def test_exception_messages():
    read_err = NetworkTimeoutError(is_write=False)
    assert "The server is taking too long to respond. Check your connection and try again." in str(read_err)

    write_err = NetworkTimeoutError(is_write=True)
    assert "The result is unknown. Refresh to check before trying again." in str(write_err)


def test_human_error_formatting():
    read_to = httpx.ReadTimeout("timed out")
    assert "The server is taking too long to respond" in human_error(read_to)

    connect_to = httpx.ConnectTimeout("connection timed out")
    assert "The server is taking too long to respond" in human_error(connect_to)

    write_err = NetworkTimeoutError(is_write=True)
    assert "The result is unknown. Refresh to check before trying again." in human_error(write_err)


# ---------------------------------------------------------------------------
# 2. Idempotent Read Retries (Retry ONCE on timeout)
# ---------------------------------------------------------------------------
def test_read_retried_once_on_timeout():
    attempts = 0

    def mock_read():
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("read timeout")

    with pytest.raises(NetworkTimeoutError) as exc_info:
        execute_network_call(mock_read, is_write=False, max_retries=1, backoff_s=0.01)

    assert attempts == 2, "Read should have been retried exactly once (total 2 attempts)"
    assert "The server is taking too long to respond" in str(exc_info.value)


def test_read_retry_recovers_on_second_attempt():
    attempts = 0

    def mock_read():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectTimeout("connect timeout")
        return {"data": [1, 2, 3]}

    result = execute_network_call(mock_read, is_write=False, max_retries=1, backoff_s=0.01)
    assert attempts == 2
    assert result == {"data": [1, 2, 3]}


# ---------------------------------------------------------------------------
# 3. Mutating Writes (NEVER retried)
# ---------------------------------------------------------------------------
def test_write_never_retried_on_timeout():
    attempts = 0

    def mock_write():
        nonlocal attempts
        attempts += 1
        raise httpx.WriteTimeout("write timed out")

    with pytest.raises(NetworkTimeoutError) as exc_info:
        execute_network_call(mock_write, is_write=True, max_retries=1, backoff_s=0.01)

    assert attempts == 1, "Mutating write must NEVER be retried automatically"
    assert "The result is unknown. Refresh to check before trying again." in str(exc_info.value)


def test_write_never_retried_on_connection_error():
    attempts = 0

    def mock_write():
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("connection dropped")

    with pytest.raises(NetworkError) as exc_info:
        execute_network_call(mock_write, is_write=True, max_retries=1, backoff_s=0.01)

    assert attempts == 1, "Mutating write must NEVER be retried on connection error"


# ---------------------------------------------------------------------------
# 4. GUI Event Loop Responsiveness (< 150 ms gap during slow calls)
# ---------------------------------------------------------------------------
def test_gui_event_loop_stays_responsive_during_network_wait(qapp):
    runner = TaskRunner()
    gaps = []
    last_tick = time.monotonic()

    heartbeat = QTimer()
    heartbeat.setInterval(20)  # 20ms ticks

    def on_tick():
        nonlocal last_tick
        now = time.monotonic()
        gaps.append(now - last_tick)
        last_tick = now

    heartbeat.timeout.connect(on_tick)
    heartbeat.start()

    # Simulate a slow network call running off the GUI thread
    completed = False

    def slow_network_call():
        time.sleep(0.3)
        return "ok"

    def on_success(res):
        nonlocal completed
        completed = True

    runner.run("slow-call", slow_network_call, on_success=on_success)

    ok = wait_until(lambda: completed, qapp, timeout=3.0)
    heartbeat.stop()

    assert ok, "Slow network task should have completed"
    assert len(gaps) >= 5, "Heartbeat timer should have ticked several times"
    max_gap = max(gaps)
    # Heartbeat gap must remain well under 150 ms
    assert max_gap < 0.150, f"GUI event loop lagged: max gap was {max_gap * 1000:.1f} ms (> 150 ms)"


# ---------------------------------------------------------------------------
# 5. LiveSyncWorker Resilience and Reconnect State
# ---------------------------------------------------------------------------
def test_live_sync_worker_survives_timeout_and_retries(qapp):
    mock_client = MagicMock()
    # First call simulates a timeout
    mock_client.table().select().eq().order().execute.side_effect = httpx.ReadTimeout("sync timeout")

    worker = LiveSyncWorker(mock_client)
    errors = []
    worker.sync_error.connect(lambda msg: errors.append(msg))

    # Trigger step directly
    worker._step()
    qapp.processEvents()

    assert len(errors) == 1
    assert "The server is taking too long to respond" in errors[0]

    # Worker can still step on next tick when network recovers
    mock_client.table().select().eq().order().execute.side_effect = None
    mock_client.table().select().eq().order().execute.return_value.data = [{"id": "1", "status": "pending"}]
    mock_client.table().select().order().execute.return_value.data = []
    mock_client.table().select().eq().execute.return_value.count = 5

    ticks = []
    worker.sync_tick.connect(lambda payload: ticks.append(payload))

    worker._step()
    qapp.processEvents()

    assert len(ticks) == 1
    assert len(ticks[0]["pending_students"]) == 1, "Live sync successfully recovered on the next tick"


def test_main_window_indicator_transitions_on_sync_error(qapp):
    mock_client = MagicMock()
    mock_client.auth.get_user.return_value.user.email = "admin@university.edu"
    mock_client.auth.get_user.return_value.user.id = "admin-1"
    mock_client.table().select().execute.return_value.data = [{"role": "admin"}]

    with patch("desktop.app.ui.main_window.resolve_role", return_value="admin"):
        win = MainWindow(mock_client)

    try:
        # Initially set to connected
        win._set_live_state("connected")
        assert win.live_dot.property("state") == "connected"

        # On sync error -> reconnecting (amber)
        win.on_live_sync_error("The server is taking too long to respond.")
        assert win.live_dot.property("state") == "reconnecting"
        assert "reconnecting" in win.live_label.text().lower()

        # On successful tick -> recovers to connected (green)
        win.on_live_sync_tick({
            "pending_students": [],
            "reports": [],
            "open_reports_count": 0,
            "pending_requests": [],
            "active_residents_count": 0,
        })
        assert win.live_dot.property("state") == "connected"
        assert "connected" in win.live_label.text().lower()
    finally:
        win.close()
