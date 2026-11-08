"""Data-layer request coalescer and short-TTL read cache.

Guarantees:
1. In-flight request coalescing: If an identical read is already in flight across
   any thread (e.g. LiveSyncWorker and a UI page simultaneously), subsequent callers
   wait for the existing in-flight result instead of dispatching duplicate HTTP requests.
2. Short-TTL caching: Bounded 1.5-second TTL cache for idempotent reads shared
   between LiveSyncWorker and foreground views.
3. Thread-safe: Protected by re-entrant locks.
4. Mutation invalidation: Any write (POST, PATCH, DELETE, or mutating RPC)
   immediately invalidates all cached entries for the affected tables.
5. Errors are NEVER cached. If a network call fails, the exception propagates to all
   coalesced callers, and the cache remains clean.
6. Writes are NEVER deduped or cached.
7. force=True (or bypass_cache() context manager) bypasses cache and fetches fresh.
8. Live-sync diff logic and notification baseline behavior remain strictly intact.
"""

from __future__ import annotations

from contextlib import contextmanager
import copy
from dataclasses import dataclass, field
import json
import logging
import threading
import time
from typing import Any, Callable, TypeVar

_log = logging.getLogger("resivo.coalescer")

DEFAULT_TTL_S: float = 1.5

T = TypeVar("T")


@dataclass
class _CacheEntry:
    result: Any
    expiry: float
    table: str


@dataclass
class _InFlightRequest:
    event: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    exception: BaseException | None = None
    waiters: int = 0


_LOCK = threading.RLock()
_CACHE: dict[tuple, _CacheEntry] = {}
_IN_FLIGHT: dict[tuple, _InFlightRequest] = {}
_STATS = {
    "hits": 0,
    "misses": 0,
    "coalesced": 0,
    "invalidations": 0,
    "writes_executed": 0,
}

_THREAD_LOCAL = threading.local()

READ_ONLY_RPCS = {
    "get_room_occupancy",
    "mcp_get_overview",
    "mcp_list_pending",
    "mcp_list_maintenance",
    "mcp_list_rooms",
    "mcp_list_residents",
    "mcp_list_tickets",
    "mcp_list_room_changes",
    "mcp_list_available_rooms",
    "mcp_list_audit",
    "mcp_get_settings",
}

RPC_INVALIDATION_MAP: dict[str, set[str]] = {
    "approve_student": {"students", "rooms"},
    "reject_student": {"students"},
    "approve_room_change": {"students", "rooms", "room_change_requests"},
    "reject_room_change": {"room_change_requests"},
    "delete_student": {"students", "rooms", "profiles", "maintenance_reports", "room_change_requests"},
    "delete_staff": {"staff", "profiles", "students", "maintenance_reports", "room_change_requests"},
    "add_official_resident": {"official_residents"},
    "update_official_resident": {"official_residents"},
    "delete_official_residents": {"official_residents"},
    "clear_official_residents": {"official_residents"},
    "import_official_residents": {"official_residents"},
    "allocate_room": {"students", "rooms"},
    "mcp_approve_application": {"students", "rooms"},
    "mcp_reject_application": {"students"},
    "mcp_update_room": {"rooms"},
    "mcp_delete_room": {"rooms"},
}


@contextmanager
def bypass_cache():
    """Context manager to force bypassing read cache for the current thread."""
    prev = getattr(_THREAD_LOCAL, "bypass", False)
    _THREAD_LOCAL.bypass = True
    try:
        yield
    finally:
        _THREAD_LOCAL.bypass = prev


def is_cache_bypassed() -> bool:
    return bool(getattr(_THREAD_LOCAL, "bypass", False))


def _extract_table_or_rpc(path: str) -> str:
    clean = str(path).strip().strip("/")
    if clean.startswith("rpc/"):
        parts = clean.split("/")
        return parts[1] if len(parts) > 1 else ""
    parts = clean.split("/")
    return parts[0] if parts else ""


def _make_key(http_method: str, path: str, params: Any, headers: Any, body: Any = None) -> tuple:
    method = str(http_method).upper()
    path_str = str(path).strip()
    params_str = str(params) if params is not None else ""
    range_header = ""
    if isinstance(headers, dict):
        range_header = str(headers.get("Range") or headers.get("range") or "")
    if isinstance(body, dict):
        try:
            body_str = json.dumps(body, sort_keys=True)
        except Exception:
            body_str = str(body)
    else:
        body_str = str(body or "")
    return (method, path_str, params_str, range_header, body_str)


def invalidate_tables(tables: set[str] | list[str] | str) -> None:
    """Invalidate all cached entries for the specified table(s)."""
    if isinstance(tables, str):
        target_tables = {tables}
    else:
        target_tables = set(tables)

    with _LOCK:
        _STATS["invalidations"] += 1
        keys_to_del = [k for k, entry in _CACHE.items() if entry.table in target_tables]
        for k in keys_to_del:
            _CACHE.pop(k, None)


def invalidate_all() -> None:
    """Invalidate entire query cache."""
    with _LOCK:
        _STATS["invalidations"] += 1
        _CACHE.clear()


def get_coalescer_stats() -> dict[str, int]:
    with _LOCK:
        return dict(_STATS)


def reset_coalescer_stats() -> None:
    with _LOCK:
        for k in _STATS:
            _STATS[k] = 0


def _execute_coalesced(self, original_execute: Callable[..., Any]) -> Any:
    """Wrapped execute logic handling table queries and RPCs."""
    raw_method = getattr(self, "http_method", "GET")
    method = str(getattr(raw_method, "value", raw_method)).upper()
    path = str(getattr(self, "path", ""))
    is_rpc = path.strip().startswith("/rpc/") or "/rpc/" in path
    target = _extract_table_or_rpc(path)

    if is_rpc:
        is_read = target in READ_ONLY_RPCS
    elif method in ("GET", "HEAD"):
        is_read = True
    else:
        is_read = False

    bypass = is_cache_bypassed()

    # 1. Mutating operations: NEVER deduped or cached
    if not is_read:
        with _LOCK:
            _STATS["writes_executed"] += 1
        res = original_execute(self)
        if is_rpc:
            affected = RPC_INVALIDATION_MAP.get(target)
            if affected:
                invalidate_tables(affected)
            else:
                invalidate_all()
        else:
            invalidate_tables(target)
            # Table updates to students may affect room occupancy
            if target == "students":
                invalidate_tables("rooms")
        return res

    # 2. Idempotent read handling
    params = getattr(self, "params", None)
    headers = getattr(self, "headers", None)
    body = getattr(self, "json", None)
    key = _make_key(method, path, params, headers, body)
    now = time.monotonic()

    # Check TTL cache
    if not bypass:
        with _LOCK:
            entry = _CACHE.get(key)
            if entry is not None and now < entry.expiry:
                _STATS["hits"] += 1
                return copy.deepcopy(entry.result)

    # Check in-flight coalescer
    with _LOCK:
        in_flight = _IN_FLIGHT.get(key)
        if in_flight is not None and not bypass:
            in_flight.waiters += 1
            _STATS["coalesced"] += 1
            should_wait = True
        else:
            in_flight = _InFlightRequest()
            _IN_FLIGHT[key] = in_flight
            should_wait = False

    if should_wait:
        in_flight.event.wait(timeout=30.0)
        if in_flight.exception is not None:
            raise in_flight.exception
        return copy.deepcopy(in_flight.result)

    # Primary network execution
    with _LOCK:
        _STATS["misses"] += 1

    try:
        result = original_execute(self)
        in_flight.result = result
        with _LOCK:
            _CACHE[key] = _CacheEntry(
                result=result,
                expiry=time.monotonic() + DEFAULT_TTL_S,
                table=target,
            )
        return copy.deepcopy(result)
    except BaseException as exc:
        in_flight.exception = exc
        # ERRORS ARE NEVER CACHED
        raise
    finally:
        with _LOCK:
            _IN_FLIGHT.pop(key, None)
        in_flight.event.set()


_INSTALLED = False
_INSTALL_LOCK = threading.RLock()


def install_query_coalescer() -> None:
    """Idempotently install the request coalescer into PostgREST sync builders."""
    global _INSTALLED
    with _INSTALL_LOCK:
        if _INSTALLED:
            return

        import postgrest._sync.request_builder as rb

        orig_query_exec = rb.SyncQueryRequestBuilder.execute

        def hooked_query_exec(self):
            return _execute_coalesced(self, orig_query_exec)

        rb.SyncQueryRequestBuilder.execute = hooked_query_exec

        orig_single_exec = rb.SyncSingleRequestBuilder.execute

        def hooked_single_exec(self):
            return _execute_coalesced(self, orig_single_exec)

        rb.SyncSingleRequestBuilder.execute = hooked_single_exec

        _INSTALLED = True
        _log.info("Installed PostgREST data-layer request coalescer and read cache")
