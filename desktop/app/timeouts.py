"""Centralized timeout constants and network error handling for the desktop application.

Configures explicit timeouts for connect, read, write/RPC, storage, and edge functions.
Provides exception types and retry policies (automatic retry ONCE for idempotent reads;
NEVER retry mutating writes).
"""

from __future__ import annotations

import logging
import socket
import time
from typing import Any, Callable, TypeVar

import httpx

_log = logging.getLogger("resivo.timeouts")

# ---------------------------------------------------------------------------
# Central Timeout Values (in seconds)
# ---------------------------------------------------------------------------
CONNECT_TIMEOUT_S: float = 5.0
READ_TIMEOUT_S: float = 10.0
WRITE_TIMEOUT_S: float = 20.0
STORAGE_DOWNLOAD_TIMEOUT_S: float = 20.0
STORAGE_UPLOAD_TIMEOUT_S: float = 30.0
EDGE_FUNCTION_TIMEOUT_S: float = 30.0

# ---------------------------------------------------------------------------
# Pre-configured httpx.Timeout specifications
# ---------------------------------------------------------------------------
POSTGREST_TIMEOUT = httpx.Timeout(
    READ_TIMEOUT_S,
    connect=CONNECT_TIMEOUT_S,
    read=READ_TIMEOUT_S,
    write=WRITE_TIMEOUT_S,
)

STORAGE_TIMEOUT = httpx.Timeout(
    STORAGE_DOWNLOAD_TIMEOUT_S,
    connect=CONNECT_TIMEOUT_S,
    read=STORAGE_DOWNLOAD_TIMEOUT_S,
    write=STORAGE_UPLOAD_TIMEOUT_S,
)

FUNCTION_TIMEOUT = httpx.Timeout(
    EDGE_FUNCTION_TIMEOUT_S,
    connect=CONNECT_TIMEOUT_S,
    read=EDGE_FUNCTION_TIMEOUT_S,
    write=EDGE_FUNCTION_TIMEOUT_S,
)

AUTH_TIMEOUT = httpx.Timeout(
    READ_TIMEOUT_S,
    connect=CONNECT_TIMEOUT_S,
    read=READ_TIMEOUT_S,
    write=WRITE_TIMEOUT_S,
)


# ---------------------------------------------------------------------------
# Exception Hierarchy
# ---------------------------------------------------------------------------
class NetworkError(Exception):
    """Base exception for all transport and connection failures."""

    DEFAULT_MESSAGE = "Could not connect to the server. Check your connection and try again."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.DEFAULT_MESSAGE)


class NetworkTimeoutError(NetworkError):
    """Raised when an outbound request exceeds its configured deadline."""

    READ_MESSAGE = "The server is taking too long to respond. Check your connection and try again."
    WRITE_MESSAGE = "The result is unknown. Refresh to check before trying again."

    def __init__(self, message: str | None = None, *, is_write: bool = False):
        if message is None:
            message = self.WRITE_MESSAGE if is_write else self.READ_MESSAGE
        super().__init__(message)
        self.is_write = is_write


def is_timeout_exception(exc: BaseException) -> bool:
    """Determine whether an exception was caused by a socket/HTTP timeout."""
    if isinstance(exc, (NetworkTimeoutError, TimeoutError, socket.timeout, httpx.TimeoutException)):
        return True
    if hasattr(exc, "reason") and isinstance(getattr(exc, "reason"), (socket.timeout, TimeoutError)):
        return True
    # Check chained causes
    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    if cause is not None and is_timeout_exception(cause):
        return True
    # Check if exception class name explicitly indicates a timeout
    cls_name = type(exc).__name__
    if "Timeout" in cls_name:
        return True
    return False


def is_connection_error(exc: BaseException) -> bool:
    """Determine whether an exception was caused by a network connection failure."""
    if isinstance(exc, (NetworkError, httpx.ConnectError, httpx.NetworkError, ConnectionError)):
        return True
    msg = str(exc).lower()
    return "connection refused" in msg or "network is unreachable" in msg or "failed to establish a new connection" in msg


T = TypeVar("T")


def execute_network_call(
    fn: Callable[[], T],
    *,
    is_write: bool = False,
    max_retries: int = 1,
    backoff_s: float = 0.5,
) -> T:
    """Execute a network callable with unified timeout handling and retry policy.

    Rules:
    - Idempotent READS (is_write=False): automatically retry ONCE after short backoff.
    - Mutating WRITES (is_write=True): NEVER retry automatically. If a write times out,
      the outcome is ambiguous and we must alert the user to refresh.
    """
    retries_left = 0 if is_write else max(0, max_retries)

    while True:
        try:
            return fn()
        except BaseException as exc:
            if is_timeout_exception(exc):
                if retries_left > 0:
                    retries_left -= 1
                    _log.info(
                        "Idempotent read timed out; retrying in %.2fs (%d retries left)",
                        backoff_s,
                        retries_left,
                    )
                    time.sleep(backoff_s)
                    continue
                _log.warning("Network call timed out (is_write=%s): %s", is_write, exc)
                raise NetworkTimeoutError(is_write=is_write) from exc

            if is_connection_error(exc):
                if retries_left > 0:
                    retries_left -= 1
                    _log.info(
                        "Connection failed; retrying in %.2fs (%d retries left)",
                        backoff_s,
                        retries_left,
                    )
                    time.sleep(backoff_s)
                    continue
                _log.warning("Network connection failed (is_write=%s): %s", is_write, exc)
                raise NetworkError() from exc

            # Other business/validation/PostgREST exceptions propagate as-is
            raise
