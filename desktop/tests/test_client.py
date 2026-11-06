import os
import pytest
from unittest.mock import MagicMock
from app.client import make_client, sign_in, current_role, room_occupancy


@pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_TESTS"),
    reason="Requires live test Supabase environment (set RUN_LIVE_TESTS=1)",
)
def test_staff_sign_in_and_role():
    client = make_client()
    sign_in(client, "staff@residence.test", "Staff1234!")
    assert current_role(client) == "staff"


def test_current_role_handles_exception_safely():
    class BrokenClient:
        @property
        def auth(self):
            raise RuntimeError("Network offline")

    assert current_role(BrokenClient()) is None


def test_room_occupancy_rpc_fast_path():
    client = MagicMock()
    rpc_mock = MagicMock()
    rpc_mock.execute.return_value = MagicMock(
        data=[
            {"room_id": "r-1", "occupied": 2},
            {"room_id": "r-2", "occupied": 1},
        ]
    )
    client.rpc.return_value = rpc_mock

    result = room_occupancy(client)
    assert result == {"r-1": 2, "r-2": 1}
    client.rpc.assert_called_once_with("get_room_occupancy", {})
    client.table.assert_not_called()


def test_room_occupancy_rpc_fallback_to_table():
    client = MagicMock()
    client.rpc.side_effect = RuntimeError("RPC not found")
    table_mock = MagicMock()
    client.table.return_value = table_mock
    select_mock = MagicMock()
    table_mock.select.return_value = select_mock
    eq_mock = MagicMock()
    select_mock.eq.return_value = eq_mock
    mock_data = [{"room_id": "r-1"}, {"room_id": "r-1"}, {"room_id": "r-3"}]
    eq_mock.range.return_value.execute.return_value = MagicMock(data=mock_data)
    eq_mock.execute.return_value = MagicMock(data=mock_data)

    result = room_occupancy(client)
    assert result == {"r-1": 2, "r-3": 1}
    client.table.assert_called_once_with("students")


def test_room_occupancy_strict_mode_propagates_on_error():
    client = MagicMock()
    client.rpc.side_effect = RuntimeError("RPC error")
    table_mock = MagicMock()
    client.table.return_value = table_mock
    select_mock = MagicMock()
    table_mock.select.return_value = select_mock
    select_mock.eq.side_effect = RuntimeError("Database down")

    with pytest.raises(RuntimeError, match="Database down"):
        room_occupancy(client, strict=True)



def test_official_lookup_caches_results_and_invalidates():
    from app.client import official_lookup, invalidate_official_lookup_cache

    client = MagicMock()
    table_mock = MagicMock()
    client.table.return_value = table_mock
    select_mock = MagicMock()
    table_mock.select.return_value = select_mock

    roster_data = [
        {"card_id": "20240001", "first_name": "Karim", "last_name": "Zitouni"},
        {"card_id": "20240002", "first_name": "Sara", "last_name": "Megherbi"},
    ]
    select_mock.range.return_value.execute.return_value = MagicMock(data=roster_data)
    select_mock.execute.return_value = MagicMock(data=roster_data)

    # Clear cache before starting test
    invalidate_official_lookup_cache(client)

    # Call 1: cache miss, triggers table query
    res1 = official_lookup(client)
    assert "20240001" in res1
    assert client.table.call_count == 1

    # Call 2: cache hit within TTL, no network call
    res2 = official_lookup(client)
    assert res2 == res1
    assert client.table.call_count == 1

    # Call 3: force=True bypasses cache
    res3 = official_lookup(client, force=True)
    assert res3 == res1
    assert client.table.call_count == 2

    # Call 4: explicit invalidation forces reload on next normal call
    invalidate_official_lookup_cache(client)
    res4 = official_lookup(client)
    assert res4 == res1
    assert client.table.call_count == 3
