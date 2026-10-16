"""RÉSIVO admin MCP server (read-only).

Exposes 6 read-only admin tools from the existing Supabase project over the
MCP streamable HTTP transport:

    1. list_maintenance_tickets      5. list_rooms
    2. list_room_change_requests     6. get_summary
    3. list_pending_registrations
    4. search_students

Safety model
------------
* The SQL functions are read-only by construction (security invoker + stable)
  and raise 'admin only' unless profiles.role is exactly 'admin'
  (see supabase/migrations/20261015120000_mcp_admin_readonly_functions.sql).
* This server uses the anon key plus a real admin login. The service role key
  is never used or referenced, so RLS always applies.
* Every request to /mcp must carry "Authorization: Bearer $MCP_AUTH_TOKEN"
  (compared with hmac.compare_digest). A simple per-IP rate limit (default
  60 requests/minute) returns 429.
* Every tool call appends one line (tool name, arguments, timestamp - never
  results) to mcp/audit.log.

Run:  python server.py   (from the mcp/ folder, with .env filled in)
"""

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from supabase import Client, create_client

from formatting import (
    ROOM_CHANGE_STATUSES,
    TICKET_STATUSES,
    RateLimiter,
    cap_limit,
    empty_message,
    to_compact_json,
    token_is_valid,
    truncate_records,
    validate_status,
)

BASE_DIR = Path(__file__).resolve().parent
AUDIT_LOG = BASE_DIR / "audit.log"
AUDIT_LOCK = threading.Lock()

# .env lives next to this file, so the server works from any working directory.
load_dotenv(BASE_DIR / ".env")

REQUIRED_ENV = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "MCP_AUTH_TOKEN",
)
MIN_TOKEN_LENGTH = 32
RATE_LIMIT_PER_MINUTE = 60
RELOGIN_AFTER_SECONDS = 45 * 60  # access tokens last 1h; re-login comfortably early


# ---------------------------------------------------------------------------
# Supabase session (anon key + real admin login)
# ---------------------------------------------------------------------------
class SupabaseAdminSession:
    """Supabase client signed in as the admin account, with automatic re-login."""

    def __init__(self, url: str, anon_key: str, email: str, password: str):
        self._url = url
        self._anon_key = anon_key
        self._email = email
        self._password = password
        self._client: Client | None = None
        self._signed_in_at = 0.0
        self._lock = threading.Lock()

    def login(self) -> None:
        """Create a fresh client and sign in (must be called while holding the lock)."""
        client = create_client(self._url, self._anon_key)
        client.auth.sign_in_with_password({"email": self._email, "password": self._password})
        self._client = client
        self._signed_in_at = time.monotonic()

    def rpc(self, function: str, params: dict):
        """Call a SQL function as the admin.

        Re-logs in once on auth errors and retries once on transient network /
        gateway errors. Retrying is safe because every exposed SQL function is
        read-only.
        """
        with self._lock:
            if self._client is None or (time.monotonic() - self._signed_in_at) > RELOGIN_AFTER_SECONDS:
                self.login()
            try:
                return self._client.rpc(function, params).execute().data
            except Exception as exc:
                if _looks_like_auth_error(exc):
                    self.login()
                    return self._client.rpc(function, params).execute().data
                if _looks_like_transient_error(exc):
                    time.sleep(0.5)
                    return self._client.rpc(function, params).execute().data
                raise


def _looks_like_auth_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = (
        "jwt expired",
        "jwt is expired",
        "invalid jwt",
        "token has expired",
        "invalid claim",
        "session not found",
        "refresh token",
        "401",
    )
    return any(marker in text for marker in markers)


def _looks_like_transient_error(exc: Exception) -> bool:
    """Flaky-network / gateway errors worth one retry (hosted Supabase, tunnels)."""
    text = str(exc).lower()
    markers = (
        "json could not be generated",
        "timeout",
        "timed out",
        "connection",
        "temporarily",
        "upstream",
        "bad gateway",
        "service unavailable",
        "502",
        "503",
        "504",
    )
    return any(marker in text for marker in markers)


SESSION = SupabaseAdminSession(
    url=os.environ.get("SUPABASE_URL", ""),
    anon_key=os.environ.get("SUPABASE_ANON_KEY", ""),
    email=os.environ.get("ADMIN_EMAIL", ""),
    password=os.environ.get("ADMIN_PASSWORD", ""),
)


# ---------------------------------------------------------------------------
# Audit log (tool name + arguments + timestamp; never results, never tokens)
# ---------------------------------------------------------------------------
def audit_tool_call(tool: str, arguments: dict) -> None:
    """Append one JSON line per tool call to mcp/audit.log."""
    line = json.dumps(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "arguments": arguments,
        },
        ensure_ascii=False,
    )
    try:
        with AUDIT_LOCK:
            with AUDIT_LOG.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except OSError:
        pass  # never fail a tool call because audit logging failed


# ---------------------------------------------------------------------------
# Error handling and the shared RPC call helper
# ---------------------------------------------------------------------------
def friendly_error(exc: Exception) -> str:
    """Short, safe error text: no traceback, no secrets."""
    message = str(exc)
    as_json = getattr(exc, "json", None)
    if callable(as_json):
        try:
            data = as_json()
            if isinstance(data, dict):
                message = str(data.get("message") or message)
        except Exception:
            pass
    message = " ".join(message.split())[:300]
    lowered = message.lower()
    if "admin only" in lowered or "permission denied" in lowered:
        return (
            "Permission denied: this tool requires an administrator account "
            "(profiles.role = 'admin')."
        )
    if "invalid status" in lowered or "query required" in lowered:
        return f"Invalid request: {message}"
    if any(marker in lowered for marker in ("jwt", "token", "session", "auth")):
        return (
            "The server could not authenticate with Supabase. "
            "Check ADMIN_EMAIL / ADMIN_PASSWORD in mcp/.env."
        )
    return f"Error talking to Supabase: {message}"


def call_admin_rpc(function: str, params: dict, empty_entity=None, status=None, block=None) -> str:
    """Run the SQL function and render the result for the model."""
    try:
        data = SESSION.rpc(function, params)
    except Exception as exc:
        return friendly_error(exc)
    if data is None or (isinstance(data, list) and not data):
        if empty_entity:
            return empty_message(empty_entity, status=status, block=block)
        return "No data returned."
    return to_compact_json(truncate_records(data))


# ---------------------------------------------------------------------------
# MCP server and tools
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "RÉSIVO Admin",
    instructions=(
        "Read-only administrator tools for RÉSIVO, the university residence "
        "management system. (maintenance tickets, room change requests, pending "
        "registrations, student lookup, rooms and an overall summary). "
        "All data comes from the live Supabase project. The tools never "
        "modify anything."
    ),
    stateless_http=True,
    # Tunnel hostnames (cloudflared / ngrok / trycloudflare) are random, so the
    # SDK's DNS-rebinding Host allowlist can never match them and every tunneled
    # request would fail with 421 "Invalid Host header". Disable that check:
    # McpSecurityMiddleware already rejects any /mcp request without the bearer
    # token *before* the transport layer runs, and all tools are read-only.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
def list_maintenance_tickets(status: str | None = None, limit: int = 20) -> str:
    """List maintenance tickets with student and room details. Use for questions about open, pending, in-progress or resolved maintenance problems. Status can be pending, in_progress or resolved (omit for all)."""
    audit_tool_call("list_maintenance_tickets", {"status": status, "limit": limit})
    try:
        normalized = validate_status(status, TICKET_STATUSES, label="status")
        capped = cap_limit(limit, default=20)
    except ValueError as exc:
        return f"Invalid request: {exc}"
    return call_admin_rpc(
        "mcp_list_tickets",
        {"p_status": normalized, "p_limit": capped},
        empty_entity="tickets",
        status=normalized,
    )


@mcp.tool()
def list_room_change_requests(status: str | None = None, limit: int = 20) -> str:
    """List room change requests with student, current room and preferred room. Status can be pending, approved or rejected (omit for all)."""
    audit_tool_call("list_room_change_requests", {"status": status, "limit": limit})
    try:
        normalized = validate_status(status, ROOM_CHANGE_STATUSES, label="status")
        capped = cap_limit(limit, default=20)
    except ValueError as exc:
        return f"Invalid request: {exc}"
    return call_admin_rpc(
        "mcp_list_room_changes",
        {"p_status": normalized, "p_limit": capped},
        empty_entity="room_changes",
        status=normalized,
    )


@mcp.tool()
def list_pending_registrations(limit: int = 20) -> str:
    """List students waiting for account approval, with their submitted data and whether they match the official residents list."""
    audit_tool_call("list_pending_registrations", {"limit": limit})
    try:
        capped = cap_limit(limit, default=20)
    except ValueError as exc:
        return f"Invalid request: {exc}"
    return call_admin_rpc(
        "mcp_list_pending_registrations",
        {"p_limit": capped},
        empty_entity="registrations",
    )


@mcp.tool()
def search_students(query: str, limit: int = 10) -> str:
    """Find a student by name or card ID and return their details, room and status. Also accepts a room label like 'B-101' to see which student lives there."""
    audit_tool_call("search_students", {"query": query, "limit": limit})
    if not query or not str(query).strip():
        return "Invalid request: query is required (a name, card ID or room label such as 'B-101')."
    try:
        capped = cap_limit(limit, default=10)
    except ValueError as exc:
        return f"Invalid request: {exc}"
    return call_admin_rpc(
        "mcp_search_students",
        {"p_query": str(query).strip(), "p_limit": capped},
        empty_entity="students",
    )


@mcp.tool()
def list_rooms(block: str | None = None, only_available: bool = False) -> str:
    """List rooms with capacity, occupancy and free places. Use only_available to find rooms with space."""
    audit_tool_call("list_rooms", {"block": block, "only_available": only_available})
    block_filter = str(block).strip() if block else None
    return call_admin_rpc(
        "mcp_list_rooms",
        {"p_block": block_filter, "p_only_available": bool(only_available)},
        empty_entity="rooms",
        block=block_filter,
    )


@mcp.tool()
def get_summary() -> str:
    """Overview: registrations, tickets, room changes and occupancy, in total and per block."""
    audit_tool_call("get_summary", {})
    return call_admin_rpc("mcp_summary", {})


# ---------------------------------------------------------------------------
# HTTP transport: /mcp (streamable HTTP) + /health, with bearer auth + rate limit
# ---------------------------------------------------------------------------
class McpSecurityMiddleware:
    """Pure ASGI middleware: bearer-token auth and a per-IP rate limit on /mcp.

    /health and any other path are left untouched. Compared with
    hmac.compare_digest inside formatting.token_is_valid.
    """

    def __init__(self, app, token: str, limiter: RateLimiter):
        self.app = app
        self.token = token
        self.limiter = limiter

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path", "").startswith("/mcp"):
            headers = {
                key.decode("latin-1").lower(): value.decode("latin-1")
                for key, value in scope.get("headers", [])
            }
            if not token_is_valid(headers.get("authorization"), self.token):
                await self._json_response(send, 401, {"error": "unauthorized"})
                return
            client = scope.get("client")
            client_key = client[0] if client else "unknown"
            if not self.limiter.allow(client_key):
                await self._json_response(send, 429, {"error": "rate limit exceeded"})
                return
        await self.app(scope, receive, send)

    @staticmethod
    async def _json_response(send, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})


def create_app(auth_token: str):
    """Build the ASGI app: MCP streamable HTTP at /mcp + health at /health."""
    app = mcp.streamable_http_app()

    async def health(_request):
        # No auth, no data - just a liveness probe for tunnels/uptime checks.
        return JSONResponse({"status": "ok"})

    app.add_route("/health", health, methods=["GET"])

    limiter = RateLimiter(limit=RATE_LIMIT_PER_MINUTE, window_seconds=60.0)
    return McpSecurityMiddleware(app, token=auth_token, limiter=limiter)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def load_config() -> dict:
    config = {name: (os.environ.get(name) or "").strip() for name in REQUIRED_ENV}
    missing = sorted(name for name, value in config.items() if not value)
    if missing:
        raise SystemExit(
            "Missing required environment variables: "
            + ", ".join(missing)
            + " (copy mcp/.env.example to mcp/.env and fill it in)"
        )
    if len(config["MCP_AUTH_TOKEN"]) < MIN_TOKEN_LENGTH:
        raise SystemExit(
            f"MCP_AUTH_TOKEN must be at least {MIN_TOKEN_LENGTH} characters. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    config["PORT"] = int(os.environ.get("PORT") or "8000")
    return config


def main() -> None:
    config = load_config()

    try:
        SESSION.login()
        print(f"Signed in to Supabase as {config['ADMIN_EMAIL']}")
    except Exception as exc:  # start anyway; tools will retry and report cleanly
        print(f"WARNING: startup login failed, tools will retry on each call. {friendly_error(exc)}")

    app = create_app(config["MCP_AUTH_TOKEN"])
    print(f"MCP endpoint: http://0.0.0.0:{config['PORT']}/mcp   (Bearer token required)")
    print(f"Health check:  http://0.0.0.0:{config['PORT']}/health (no auth)")
    uvicorn.run(app, host="0.0.0.0", port=config["PORT"], log_level="info")


if __name__ == "__main__":
    main()
