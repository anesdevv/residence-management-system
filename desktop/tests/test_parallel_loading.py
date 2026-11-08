"""Tests for concurrent / parallel data loading and request gather helpers.

Verifies:
1. Concurrency: With 300 ms mocked latency per call, concurrent load takes approximately
   the duration of the longest call (~300-450 ms), not the sum (~900 ms).
2. Partial failure: One failing call does not block or cancel other successful calls.
3. Stale discard: Stale results are discarded when the request_id / generation advances.
4. Equivalence: Overview counters returned by overview_stats RPC match legacy query numbers.
5. Mutual exclusion: Active gather key blocks duplicate submissions until complete.
6. Client isolation: clone_client creates an independent client sharing the auth session.
"""

from __future__ import annotations

import os
import threading
import time
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from desktop.app.client import clone_client
from desktop.app.ui.pages.overview import OverviewPage
from desktop.app.ui.tasks import GatherResult, TaskRunner


def _qapp():
    return QApplication.instance() or QApplication([])


def _wait_until(predicate, timeout=5.0):
    app = _qapp()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    app.processEvents()
    return bool(predicate())


def test_gather_executes_concurrently_wall_clock():
    """Three 300 ms calls complete in ~300-500 ms, far below sequential 900 ms."""
    _qapp()
    pool = QThreadPool()
    pool.setMaxThreadCount(4)
    runner = TaskRunner(pool=pool)

    received_result: list[GatherResult] = []
    finished_called: list[bool] = []

    def slow_call(name: str):
        time.sleep(0.300)
        return f"result_{name}"

    callables = {
        "call_1": lambda: slow_call("1"),
        "call_2": lambda: slow_call("2"),
        "call_3": lambda: slow_call("3"),
    }

    t0 = time.perf_counter()
    started = runner.gather(
        "concurrent_bench",
        callables,
        on_complete=received_result.append,
        on_finished=lambda: finished_called.append(True),
        request_id=42,
    )
    assert started is True

    # Wait for gather completion signal on GUI event loop
    assert _wait_until(lambda: bool(received_result and finished_called), timeout=3.0)
    elapsed = time.perf_counter() - t0

    res = received_result[0]
    assert res.all_succeeded is True
    assert res.has_errors is False
    assert res.request_id == 42
    assert res.get("call_1") == "result_1"
    assert res.get("call_2") == "result_2"
    assert res.get("call_3") == "result_3"

    # Wall-clock must be bounded near longest call (300 ms), NOT sequential sum (900 ms)
    # Generous ceiling of 650 ms accounts for thread startup and Windows timer resolution
    assert elapsed < 0.65, f"Expected concurrent elapsed < 0.65s, got {elapsed:.3f}s"
    assert elapsed >= 0.28, f"Expected at least 0.3s work, got {elapsed:.3f}s"


def test_gather_partial_failure_does_not_block_others():
    """One failed callable records its error while other callables succeed."""
    _qapp()
    pool = QThreadPool()
    runner = TaskRunner(pool=pool)

    received_result: list[GatherResult] = []

    def broken_call():
        raise RuntimeError("Synthetic network failure")

    callables = {
        "ok_first": lambda: "data_1",
        "broken": broken_call,
        "ok_second": lambda: "data_2",
    }

    assert runner.gather(
        "partial_fail_test",
        callables,
        on_complete=received_result.append,
        request_id=101,
    )

    assert _wait_until(lambda: bool(received_result), timeout=3.0)
    res = received_result[0]

    assert res.all_succeeded is False
    assert res.has_errors is True
    assert res.get("ok_first") == "data_1"
    assert res.get("ok_second") == "data_2"
    assert "broken" in res.errors
    assert "Synthetic network failure" in res.errors["broken"]


def test_gather_stale_results_discarded_via_request_id():
    """Older in-flight gathers are discarded when request_id advances."""
    _qapp()
    pool = QThreadPool()
    runner = TaskRunner(pool=pool)

    applied_snapshots: list[tuple[int, dict]] = []
    current_request_id = 1

    def on_complete(result: GatherResult):
        # Mirroring the page guard: discard if request_id != current_request_id
        if result.request_id != current_request_id:
            return
        applied_snapshots.append((result.request_id, result.results))

    # Trigger slow request 1
    runner.gather(
        "req_1",
        {"data": lambda: (time.sleep(0.200), "stale_payload")[1]},
        on_complete=on_complete,
        request_id=1,
    )

    # Immediately advance request_id to 2 (simulating fast user navigation or refresh)
    current_request_id = 2

    # Trigger fast request 2
    runner.gather(
        "req_2",
        {"data": lambda: "fresh_payload"},
        on_complete=on_complete,
        request_id=2,
    )

    # Wait for all background threads to drain
    pool.waitForDone(3000)
    _qapp().processEvents()

    # Verify only request 2 was applied; request 1 was discarded
    assert len(applied_snapshots) == 1
    req_id, data = applied_snapshots[0]
    assert req_id == 2
    assert data["data"] == "fresh_payload"


def test_overview_stats_rpc_numbers_identical_to_legacy_queries():
    """overview_stats RPC returns identical numbers to individual count queries."""
    _qapp()

    mock_client = MagicMock()

    # Configure RPC response
    mock_rpc_resp = MagicMock()
    mock_rpc_resp.data = {
        "pending": 12,
        "reports": 5,
        "requests": 3,
        "occupancy": 84,
    }
    mock_client.rpc.return_value.execute.return_value = mock_rpc_resp

    # Configure fallback query chains to produce identical numbers
    def fake_table(name: str):
        table_mock = MagicMock()
        if name == "students":
            # pending count
            table_mock.select.return_value.eq.return_value.execute.return_value.count = 12
        elif name == "maintenance_reports":
            # open reports count
            table_mock.select.return_value.neq.return_value.execute.return_value.count = 5
        elif name == "room_change_requests":
            # pending requests count
            table_mock.select.return_value.eq.return_value.execute.return_value.count = 3
        return table_mock

    mock_client.table.side_effect = fake_table

    page = OverviewPage(mock_client)

    # 1. Fetch via RPC
    rpc_snapshot = page._fetch_snapshot()
    assert rpc_snapshot == (12, 5, 3, 84)

    # 2. Simulate RPC failing (e.g. unmigrated database) -> triggers fallback queries
    mock_client.rpc.side_effect = RuntimeError("RPC overview_stats() does not exist")
    # Mock room_occupancy for fallback path
    import desktop.app.ui.pages.overview as ov_mod
    orig_occupancy = ov_mod.room_occupancy
    ov_mod.room_occupancy = lambda client, strict=True: {"r1": 50, "r2": 34}
    try:
        fallback_snapshot = page._fetch_snapshot()
        assert fallback_snapshot == (12, 5, 3, 84)
    finally:
        ov_mod.room_occupancy = orig_occupancy

    # Both paths produce strictly identical numbers!
    assert rpc_snapshot == fallback_snapshot


def test_gather_key_mutual_exclusion():
    """Same action key cannot be re-submitted while gather is running."""
    _qapp()
    pool = QThreadPool()
    runner = TaskRunner(pool=pool)
    release = threading.Event()

    def blocking_callable():
        release.wait(3.0)
        return "done"

    started = runner.gather("test_key", {"sub": blocking_callable}, on_complete=lambda _: None)
    assert started is True
    assert runner.is_busy("test_key") is True

    # Duplicate submission under same key must be rejected
    rejected = runner.gather("test_key", {"sub": lambda: "other"}, on_complete=lambda _: None)
    assert rejected is False

    # Also normal run under same key must be rejected
    run_rejected = runner.run("test_key", lambda: "other")
    assert run_rejected is False

    release.set()
    assert _wait_until(lambda: not runner.is_busy("test_key"), timeout=3.0)


def test_gather_empty_callables():
    """Empty gather completes immediately without errors or hanging."""
    _qapp()
    runner = TaskRunner()
    results: list[GatherResult] = []

    started = runner.gather("empty_key", {}, on_complete=results.append, request_id=7)
    assert started is True
    assert len(results) == 1
    assert results[0].results == {}
    assert results[0].errors == {}
    assert results[0].request_id == 7
    assert results[0].all_succeeded is True


def test_clone_client_shares_auth_session_independently():
    """clone_client creates a new client sharing session without racing connections."""
    client = MagicMock()
    mock_session = {"access_token": "test-jwt-token", "user": {"id": "uid-1"}}
    client.auth = MagicMock()
    client.auth._in_memory_session = mock_session

    cloned = clone_client(client)
    assert cloned is not client
    assert cloned.auth._in_memory_session == mock_session
