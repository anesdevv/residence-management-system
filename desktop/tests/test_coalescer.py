"""Tests for data-layer request coalescing and short-TTL read caching."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from desktop.app.coalescer import (
    DEFAULT_TTL_S,
    bypass_cache,
    get_coalescer_stats,
    install_query_coalescer,
    invalidate_all,
    invalidate_tables,
    reset_coalescer_stats,
)


@pytest.fixture(autouse=True)
def _setup_coalescer():
    install_query_coalescer()
    invalidate_all()
    reset_coalescer_stats()
    yield
    invalidate_all()
    reset_coalescer_stats()


def test_two_concurrent_identical_reads_produce_one_request():
    from desktop.app.client import make_client

    client = make_client()
    call_count = 0
    gate = threading.Event()

    # Create mock target that pauses to allow concurrent overlap
    class FakeBuilder:
        def __init__(self):
            self.http_method = "GET"
            self.path = "/students"
            self.params = "select=id&status=eq.pending"
            self.headers = {}
            self.json = None

    import postgrest._sync.request_builder as rb

    orig = rb.SyncQueryRequestBuilder.execute

    def slow_exec(self):
        nonlocal call_count
        if getattr(self, "path", "") == "/students_test_concurrent":
            call_count += 1
            gate.wait(timeout=2.0)
            mock_resp = MagicMock()
            mock_resp.data = [{"id": "s1", "name": "Alice"}]
            mock_resp.count = 1
            return mock_resp
        return orig(self)

    rb.SyncQueryRequestBuilder.execute = slow_exec
    try:
        results = [None, None]
        errors = [None, None]

        def worker(idx):
            builder = FakeBuilder()
            builder.path = "/students_test_concurrent"
            try:
                from desktop.app.coalescer import _execute_coalesced
                results[idx] = _execute_coalesced(builder, slow_exec)
            except Exception as exc:
                errors[idx] = exc

        t1 = threading.Thread(target=worker, args=(0,))
        t2 = threading.Thread(target=worker, args=(1,))

        t1.start()
        time.sleep(0.05)  # Let t1 start and enter in-flight
        t2.start()
        time.sleep(0.05)  # Let t2 join as a waiter

        gate.set()  # Release execution
        t1.join()
        t2.join()

        assert errors == [None, None]
        assert call_count == 1, f"Expected 1 network call, got {call_count}"
        assert results[0].data == [{"id": "s1", "name": "Alice"}]
        assert results[1].data == [{"id": "s1", "name": "Alice"}]

        stats = get_coalescer_stats()
        assert stats["coalesced"] >= 1
    finally:
        rb.SyncQueryRequestBuilder.execute = orig


def test_write_invalidates_cache():
    class FakeBuilder:
        def __init__(self, method="GET", path="/students", params="select=id"):
            self.http_method = method
            self.path = path
            self.params = params
            self.headers = {}
            self.json = None

    network_calls = 0

    def mock_exec(self):
        nonlocal network_calls
        network_calls += 1
        res = MagicMock()
        res.data = [{"id": f"row_{network_calls}"}]
        res.count = 1
        return res

    from desktop.app.coalescer import _execute_coalesced

    # 1. First read -> misses cache
    read1 = FakeBuilder("GET", "/students", "select=id")
    res1 = _execute_coalesced(read1, mock_exec)
    assert network_calls == 1
    assert res1.data == [{"id": "row_1"}]

    # 2. Second read within TTL -> hits cache (network_calls remains 1)
    res2 = _execute_coalesced(read1, mock_exec)
    assert network_calls == 1
    assert res2.data == [{"id": "row_1"}]

    # 3. Write operation on students -> invalidates students
    write_builder = FakeBuilder("POST", "/students", "")
    _execute_coalesced(write_builder, mock_exec)
    assert network_calls == 2

    # 4. Third read -> cache was invalidated, must hit network
    res3 = _execute_coalesced(read1, mock_exec)
    assert network_calls == 3
    assert res3.data == [{"id": "row_3"}]


def test_ttl_expiry():
    class FakeBuilder:
        def __init__(self):
            self.http_method = "GET"
            self.path = "/rooms"
            self.params = "select=id,number"
            self.headers = {}
            self.json = None

    network_calls = 0

    def mock_exec(self):
        nonlocal network_calls
        network_calls += 1
        res = MagicMock()
        res.data = [{"id": f"room_{network_calls}"}]
        res.count = 1
        return res

    from desktop.app.coalescer import _execute_coalesced

    builder = FakeBuilder()

    # Initial fetch
    _execute_coalesced(builder, mock_exec)
    assert network_calls == 1

    # Immediate refetch within 1.5s -> hits cache
    _execute_coalesced(builder, mock_exec)
    assert network_calls == 1

    # Wait past TTL (> 1.5s)
    time.sleep(1.6)

    # Subsequent fetch after TTL -> fresh network call
    _execute_coalesced(builder, mock_exec)
    assert network_calls == 2


def test_errors_not_cached():
    class FakeBuilder:
        def __init__(self):
            self.http_method = "GET"
            self.path = "/failing_table"
            self.params = ""
            self.headers = {}
            self.json = None

    attempts = 0

    def failing_exec(self):
        nonlocal attempts
        attempts += 1
        raise ConnectionError("Server unavailable")

    from desktop.app.coalescer import _execute_coalesced

    builder = FakeBuilder()

    with pytest.raises(ConnectionError):
        _execute_coalesced(builder, failing_exec)
    assert attempts == 1

    # Second attempt must NOT return a cached exception; it must try network again
    with pytest.raises(ConnectionError):
        _execute_coalesced(builder, failing_exec)
    assert attempts == 2


def test_different_filters_produce_different_keys():
    class FakeBuilder:
        def __init__(self, filter_param):
            self.http_method = "GET"
            self.path = "/students"
            self.params = f"select=id&status={filter_param}"
            self.headers = {}
            self.json = None

    queries = []

    def mock_exec(self):
        queries.append(self.params)
        res = MagicMock()
        res.data = [{"param": self.params}]
        res.count = 1
        return res

    from desktop.app.coalescer import _execute_coalesced

    pending_builder = FakeBuilder("eq.pending")
    active_builder = FakeBuilder("eq.active")

    res_p = _execute_coalesced(pending_builder, mock_exec)
    res_a = _execute_coalesced(active_builder, mock_exec)

    assert len(queries) == 2
    assert "status=eq.pending" in res_p.data[0]["param"]
    assert "status=eq.active" in res_a.data[0]["param"]


def test_writes_never_deduped_or_cached():
    class FakeBuilder:
        def __init__(self):
            self.http_method = "POST"
            self.path = "/rooms"
            self.params = ""
            self.headers = {}
            self.json = {"block": "A", "number": "101"}

    write_count = 0

    def mock_exec(self):
        nonlocal write_count
        write_count += 1
        res = MagicMock()
        res.data = [{"id": f"created_{write_count}"}]
        res.count = 1
        return res

    from desktop.app.coalescer import _execute_coalesced

    builder = FakeBuilder()
    _execute_coalesced(builder, mock_exec)
    _execute_coalesced(builder, mock_exec)

    # Must execute twice
    assert write_count == 2
    stats = get_coalescer_stats()
    assert stats["writes_executed"] == 2


def test_force_bypass_cache():
    class FakeBuilder:
        def __init__(self):
            self.http_method = "GET"
            self.path = "/blocks"
            self.params = "select=id,name"
            self.headers = {}
            self.json = None

    fetches = 0

    def mock_exec(self):
        nonlocal fetches
        fetches += 1
        res = MagicMock()
        res.data = [{"fetches": fetches}]
        res.count = 1
        return res

    from desktop.app.coalescer import _execute_coalesced

    builder = FakeBuilder()
    r1 = _execute_coalesced(builder, mock_exec)
    assert fetches == 1

    # Regular fetch within TTL -> hits cache
    r2 = _execute_coalesced(builder, mock_exec)
    assert fetches == 1

    # Fetch with bypass_cache() -> forces fresh network call
    with bypass_cache():
        r3 = _execute_coalesced(builder, mock_exec)
    assert fetches == 2
    assert r3.data == [{"fetches": 2}]


def test_live_sync_notifications_no_duplicates():
    """Verify live sync diffing logic continues to emit alerts only on new items without duplicates."""
    from desktop.app.ui.live_sync import LiveSyncWorker

    mock_client = MagicMock()
    worker = LiveSyncWorker(mock_client, interval_ms=1000)

    alerts = []
    worker.alert_event.connect(lambda msg: alerts.append(msg))

    # Mock response for step
    mock_resp = MagicMock()
    mock_resp.data = [
        {"id": "s1", "first_name": "Karim", "last_name": "B", "card_id": "C001"},
        {"id": "s2", "first_name": "Amina", "last_name": "D", "card_id": "C002"},
    ]
    mock_resp.count = 2

    mock_client.table().select().eq().order().execute.return_value = mock_resp
    mock_client.table().select().order().execute.return_value = mock_resp
    mock_client.table().select().execute.return_value = mock_resp

    # First step establishes baseline (no alerts emitted for initial baseline)
    worker._step()
    assert len(alerts) == 0

    # Second step with identical items -> 0 duplicate alerts
    worker._step()
    assert len(alerts) == 0

    # Third step with 1 newly added student
    new_resp = MagicMock()
    new_resp.data = [
        {"id": "s1", "first_name": "Karim", "last_name": "B", "card_id": "C001"},
        {"id": "s2", "first_name": "Amina", "last_name": "D", "card_id": "C002"},
        {"id": "s3", "first_name": "Yassine", "last_name": "M", "card_id": "C003"},
    ]
    new_resp.count = 3
    mock_client.table().select().eq().order().execute.return_value = new_resp

    worker._step()
    assert len(alerts) == 1
    assert "Yassine" in alerts[0]

    # Fourth step with same 3 items -> no new alert
    worker._step()
    assert len(alerts) == 1
