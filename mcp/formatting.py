"""Pure helpers for the RÉSIVO admin MCP server.

Everything in this module is dependency-free and network-free so it can be
unit-tested with plain pytest (see tests/test_formatting.py).
"""

from __future__ import annotations

import hmac
import json
import time
from collections import deque

# Free text longer than this is truncated in tool results (spec: 500 chars).
MAX_FREE_TEXT = 500

# Free-text fields present in the jsonb rows returned by the mcp_* SQL functions.
FREE_TEXT_FIELDS = ("description", "staff_note", "reason", "decision_note", "rejection_reason")

DEFAULT_LIMIT = 20
MAX_LIMIT = 100

TICKET_STATUSES = ("pending", "in_progress", "resolved")
ROOM_CHANGE_STATUSES = ("pending", "approved", "rejected")

_EMPTY_LABELS = {
    "tickets": "maintenance tickets",
    "room_changes": "room change requests",
    "registrations": "pending registrations",
    "students": "students matching your search",
    "rooms": "rooms",
}


def truncate_text(value, limit: int = MAX_FREE_TEXT):
    """Truncate free text to at most ``limit`` characters (adding '...' when cut).

    ``None`` passes through unchanged. The result never exceeds ``limit``.
    """
    if value is None:
        return None
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)].rstrip() + "..."


def truncate_records(records, fields=FREE_TEXT_FIELDS, limit: int = MAX_FREE_TEXT):
    """Recursively truncate the given free-text fields in dicts/lists of dicts."""
    if isinstance(records, list):
        return [truncate_records(item, fields, limit) for item in records]
    if isinstance(records, dict):
        out = {}
        for key, value in records.items():
            if key in fields and isinstance(value, str):
                out[key] = truncate_text(value, limit)
            elif isinstance(value, (dict, list)):
                out[key] = truncate_records(value, fields, limit)
            else:
                out[key] = value
        return out
    return records


def cap_limit(limit, default: int = DEFAULT_LIMIT, maximum: int = MAX_LIMIT) -> int:
    """Coerce a user-supplied limit into ``[1, maximum]``; ``None`` becomes default.

    Raises ValueError for non-numeric input.
    """
    if limit is None:
        return default
    if isinstance(limit, bool) or not isinstance(limit, (int, float, str)):
        raise ValueError("limit must be a number")
    try:
        number = int(limit)
    except (TypeError, ValueError):
        raise ValueError("limit must be a number") from None
    return max(1, min(number, maximum))


def validate_status(value, allowed=TICKET_STATUSES, label: str = "status"):
    """Normalize and validate a status filter; ``None`` passes through.

    Accepts e.g. 'Pending', 'in progress', 'in-progress' for 'in_progress'.
    Raises ValueError listing the allowed values for anything else.
    """
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if normalized not in allowed:
        raise ValueError(
            f"invalid {label} {value!r}: expected one of {', '.join(allowed)}"
        )
    return normalized


def token_is_valid(authorization_header, expected_token: str) -> bool:
    """Constant-time check of an ``Authorization: Bearer <token>`` header."""
    if not authorization_header or not expected_token:
        return False
    scheme, _, provided = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not provided.strip():
        return False
    return hmac.compare_digest(provided.strip(), expected_token)


def empty_message(entity: str, status: str | None = None, block: str | None = None) -> str:
    """Friendly message used when a query returns no rows."""
    if entity == "students":
        return "No students matched your search."
    if entity == "registrations":
        return "No pending registrations found."
    if entity == "rooms":
        if block:
            return f"No rooms found in block {block}."
        return "No rooms found."
    label = _EMPTY_LABELS[entity]
    if status:
        return f"No {status.replace('_', '-')} {label} found."
    return f"No {label} found."


def to_compact_json(payload) -> str:
    """Compact, non-ASCII-safe-stripped JSON string, ready for a tool result."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class RateLimiter:
    """Sliding-window rate limiter, keyed by client (e.g. IP address).

    Pure and deterministic when ``now`` is passed in tests.
    """

    def __init__(self, limit: int = 60, window_seconds: float = 60.0):
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")
        self.limit = int(limit)
        self.window_seconds = float(window_seconds)
        self._hits: dict[str, deque] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        """Record one hit for ``key``; return False while over the limit."""
        moment = time.monotonic() if now is None else now
        hits = self._hits.setdefault(key, deque())
        cutoff = moment - self.window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(moment)
        return True
