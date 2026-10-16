#!/usr/bin/env python3
"""End-to-end acceptance checks for the hosted RÉSIVO MCP worker.

Usage:
    python verify_remote.py <BASE_URL> [--token TOKEN] [--timeout SECONDS]

Examples:
    python verify_remote.py https://resivo-mcp.example.workers.dev
    python verify_remote.py http://localhost:8788 --token <token>

The consent token is read from the repository's ``mcp/.env`` (``MCP_AUTH_TOKEN``
line) or from ``--token``. The write-surface checks also read ``SUPABASE_URL``,
``SUPABASE_ANON_KEY``, ``ADMIN_EMAIL`` and ``ADMIN_PASSWORD`` from the same
file for direct PostgREST probes as the seeded admin (off-switch + audit
read-back). No value from ``mcp/.env`` is ever printed, logged, or written
anywhere.

Stdlib only: urllib, json, base64, hashlib, secrets, uuid, pathlib, html.parser.

Exit status: 0 when every check passed or was skipped; non-zero when any FAIL.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html.parser
import http.cookiejar
import json
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

USER_AGENT = "resivo-mcp-verify/1.0 (stdlib urllib acceptance script)"
DEFAULT_PROTOCOL_VERSION = "2025-06-18"
DEFAULT_TIMEOUT = 15.0
PROBE_TIMEOUT = 10.0
PROBE_REQUESTS = 65
REDIRECT_URI = "http://127.0.0.1:8976/oauth/callback"
EXPECTED_TOOLS = (
    # Reads (6) then writes (8), in worker registration order.
    "list_maintenance_tickets",
    "list_room_change_requests",
    "list_pending_registrations",
    "search_students",
    "list_rooms",
    "get_summary",
    "approve_registration",
    "reject_registration",
    "approve_room_change",
    "reject_room_change",
    "create_room",
    "update_room",
    "delete_room",
    "update_ticket",
)
READ_TOOLS = EXPECTED_TOOLS[:6]
# destructiveHint must be true exactly on these three write tools.
DESTRUCTIVE_TOOLS = ("reject_registration", "reject_room_change", "delete_room")
# Write tools whose ok:true audit rows the audit read-back expects.
ROUND_TRIP_TOOLS = ("create_room", "update_room", "delete_room")
SCRATCH_BLOCK = "ZZT"
WRITING_DISABLED_PREFIX = "Writing is currently disabled."
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
TOKEN_FIELD_CANDIDATES = ("access_token", "token", "password")
TOOL_CALLS = (
    ("list_maintenance_tickets", {"status": "pending", "limit": 5}),
    ("list_room_change_requests", {"status": "pending", "limit": 5}),
    ("list_pending_registrations", {"limit": 5}),
    ("search_students", {"query": "a", "limit": 3}),
    ("list_rooms", {}),
    ("get_summary", {}),
)
# Text prefixes that mean the tool did NOT return real data.
FAILURE_PREFIXES = (
    "Invalid request:",
    "Permission denied:",
    "The server could not authenticate with Supabase.",
    "Error talking to Supabase:",
)


# ---------------------------------------------------------------------------
# Small output / error helpers
# ---------------------------------------------------------------------------
def short_error(exc: BaseException) -> str:
    """Compact exception text; never includes secrets (token is never in a URL)."""
    return " ".join(f"{type(exc).__name__}: {exc}".split())[:160]


def path_only(url: str) -> str:
    try:
        return urllib.parse.urlsplit(url).path or "/"
    except ValueError:
        return "?"


class Report:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def add(self, status: str, name: str, detail: str = "") -> None:
        detail = " ".join(str(detail).split())[:200]
        line = f"{status} {name}"
        if detail:
            line += f": {detail}"
        print(line, flush=True)
        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1
        else:
            self.skipped += 1

    def summary(self) -> int:
        print(
            f"SUMMARY: {self.passed} passed, {self.failed} failed, {self.skipped} skipped",
            flush=True,
        )
        return 1 if self.failed else 0


# ---------------------------------------------------------------------------
# HTTP layer (urllib; redirects only followed when explicitly requested)
# ---------------------------------------------------------------------------
class Response:
    __slots__ = ("status", "headers", "body", "url")

    def __init__(self, status: int, headers, body: bytes, url: str) -> None:
        self.status = status
        self.headers = headers
        self.body = body
        self.url = url

    def header(self, name: str, default=None):
        if self.headers is None:
            return default
        try:
            value = self.headers.get(name)
        except AttributeError:
            return default
        return default if value is None else value

    def text(self, limit: int | None = None) -> str:
        text = self.body.decode("utf-8", "replace")
        return text if limit is None else text[:limit]

    def json(self):
        return json.loads(self.text())


def try_json(resp: Response):
    try:
        return resp.json()
    except Exception:
        return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Make 3xx responses surface as HTTPError so callers can read Location."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    """urllib wrapper: one cookie jar, with and without redirect following."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        jar = http.cookiejar.CookieJar()
        processor = urllib.request.HTTPCookieProcessor(jar)
        self._follow = urllib.request.build_opener(processor)
        self._nofollow = urllib.request.build_opener(processor, _NoRedirect())
        self.timeout = timeout

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict | None = None,
        body: bytes | None = None,
        timeout: float | None = None,
        follow: bool = False,
    ) -> Response:
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("User-Agent", USER_AGENT)
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        opener = self._follow if follow else self._nofollow
        try:
            with opener.open(req, timeout=self.timeout if timeout is None else timeout) as resp:
                return Response(resp.status, resp.headers, resp.read(), resp.geturl())
        except urllib.error.HTTPError as exc:
            try:
                data = exc.read()
            except Exception:
                data = b""
            return Response(exc.code, exc.headers, data, getattr(exc, "url", url))


# ---------------------------------------------------------------------------
# JSON-RPC / SSE parsing (MCP Streamable HTTP)
# ---------------------------------------------------------------------------
def parse_sse(body: bytes) -> list[str]:
    events: list[str] = []
    current: list[str] = []
    for raw in body.decode("utf-8", "replace").split("\n"):
        line = raw.rstrip("\r")
        if not line:
            if current:
                events.append("\n".join(current))
                current = []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            current.append(line[len("data:"):].lstrip(" "))
    if current:
        events.append("\n".join(current))
    return events


def extract_jsonrpc(resp: Response, request_id):
    content_type = (resp.header("content-type") or "").lower()
    if "text/event-stream" in content_type:
        chunks = parse_sse(resp.body)
    else:
        chunks = [resp.text()]
    objects = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            value = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            objects.append(value)
    if not objects:
        return None, "no parseable JSON-RPC object in response"
    for obj in objects:
        if obj.get("id") == request_id and ("result" in obj or "error" in obj):
            return obj, None
    for obj in objects:
        if "result" in obj or "error" in obj:
            return obj, None
    return None, "response contained no JSON-RPC result/error"


def jsonrpc_error_text(obj: dict) -> str:
    err = obj.get("error")
    if not isinstance(err, dict):
        return "unknown error"
    message = str(err.get("message") or "unknown error")[:120]
    code = err.get("code")
    return f"[{code}] {message}" if code is not None else message


def result_text(result: dict) -> str:
    """Text payload of a tools/call result (content[] preferred, else structuredContent)."""
    content = result.get("content")
    if isinstance(content, list):
        parts = [
            str(item.get("text"))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text") is not None
        ]
        if parts:
            return "\n".join(parts)
    structured = result.get("structuredContent")
    if structured is not None:
        return json.dumps(structured, ensure_ascii=False)
    return ""


# ---------------------------------------------------------------------------
# Environment: mcp/.env parsing + token resolution (values never printed)
# ---------------------------------------------------------------------------
def load_env() -> dict:
    """Parse ``mcp/.env`` into a dict (tolerates ``export`` and quotes).

    Returns an empty dict when the file is missing. Values are secrets: never
    print or log them.
    """
    script_dir = Path(__file__).resolve().parent
    env_path = script_dir.parent.parent / "mcp" / ".env"
    values: dict = {}
    if not env_path.is_file():
        return values
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def resolve_token(cli_token: str | None):
    if cli_token:
        token = cli_token.strip()
        return (token, "--token") if token else (None, None)
    script_dir = Path(__file__).resolve().parent
    env_path = script_dir.parent.parent / "mcp" / ".env"
    if not env_path.is_file():
        return None, None
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() != "MCP_AUTH_TOKEN":
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        return (value or None), "mcp/.env (MCP_AUTH_TOKEN)"
    return None, None


# ---------------------------------------------------------------------------
# Direct PostgREST as the seeded admin (off-switch + audit read-back)
# ---------------------------------------------------------------------------
def admin_token(env: dict):
    """Password-grant login as the seeded admin; returns (token, detail).

    Uses the shared Client; neither the token nor the credentials are ever
    printed. ``env`` is the ``load_env()`` dict.
    """
    url = str(env.get("SUPABASE_URL") or "").rstrip("/")
    anon = str(env.get("SUPABASE_ANON_KEY") or "")
    email = str(env.get("ADMIN_EMAIL") or "")
    password = str(env.get("ADMIN_PASSWORD") or "")
    missing = [
        key
        for key, value in (
            ("SUPABASE_URL", url),
            ("SUPABASE_ANON_KEY", anon),
            ("ADMIN_EMAIL", email),
            ("ADMIN_PASSWORD", password),
        )
        if not value
    ]
    if missing:
        return None, "mcp/.env is missing " + ", ".join(missing)
    payload = {"email": email, "password": password}
    try:
        resp = Client().request(
            "POST",
            url + "/auth/v1/token?grant_type=password",
            headers={
                "apikey": anon,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body=json.dumps(payload).encode("utf-8"),
        )
    except Exception as exc:
        return None, f"admin login request error: {short_error(exc)}"
    if resp.status != 200:
        return None, f"admin login returned HTTP {resp.status}"
    data = try_json(resp)
    token = data.get("access_token") if isinstance(data, dict) else None
    if not token:
        return None, "admin login response has no access_token"
    return str(token), "ok"


def admin_rpc(env: dict, fn: str, params: dict, token: str | None = None):
    """POST one PostgREST rpc as the admin; returns (parsed_json, detail).

    Logs in first when no token is given. Only status codes and short SQL
    messages are reported - never a value from ``mcp/.env``.
    """
    if token is None:
        token, error = admin_token(env)
        if token is None:
            return None, error
    url = str(env.get("SUPABASE_URL") or "").rstrip("/")
    anon = str(env.get("SUPABASE_ANON_KEY") or "")
    if not url or not anon:
        return None, "mcp/.env is missing SUPABASE_URL or SUPABASE_ANON_KEY"
    try:
        resp = Client().request(
            "POST",
            f"{url}/rest/v1/rpc/{fn}",
            headers={
                "apikey": anon,
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body=json.dumps(params).encode("utf-8"),
        )
    except Exception as exc:
        return None, f"{fn} request error: {short_error(exc)}"
    if resp.status != 200:
        message = ""
        data = try_json(resp)
        if isinstance(data, dict) and isinstance(data.get("message"), str):
            message = f" ({data['message'][:80]})"
        return None, f"{fn} returned HTTP {resp.status}{message}"
    return try_json(resp), "ok"


# ---------------------------------------------------------------------------
# Check 1 + 2: health, unauthenticated 401
# ---------------------------------------------------------------------------
def check_health(client: Client, base: str, report: Report) -> None:
    try:
        resp = client.request("GET", base + "/health", headers={"Accept": "application/json"}, follow=True)
    except Exception as exc:
        report.add("FAIL", "health", f"request error: {short_error(exc)}")
        return
    if resp.status != 200:
        report.add("FAIL", "health", f"HTTP {resp.status}")
        return
    data = try_json(resp)
    if not isinstance(data, dict) or data.get("status") != "ok":
        report.add("FAIL", "health", f'expected {{"status":"ok"}}, got {resp.text(120)!r}')
        return
    report.add("PASS", "health", 'HTTP 200 {"status":"ok"}')


def check_unauth(client: Client, base: str, report: Report):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": DEFAULT_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "verify_remote.py", "version": "1.0"},
        },
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    try:
        resp = client.request(
            "POST", base + "/mcp", headers=headers, body=json.dumps(payload).encode("utf-8")
        )
    except Exception as exc:
        report.add("FAIL", "unauthorized /mcp", f"request error: {short_error(exc)}")
        return None
    challenge = resp.header("www-authenticate")
    if resp.status != 401:
        report.add("FAIL", "unauthorized /mcp", f"expected HTTP 401, got {resp.status}")
        return challenge
    detail = f"HTTP 401 (WWW-Authenticate: {challenge})" if challenge else "HTTP 401"
    report.add("PASS", "unauthorized /mcp", detail)
    return challenge


# ---------------------------------------------------------------------------
# Check 3: discovery-driven OAuth (no hardcoded endpoint paths)
# ---------------------------------------------------------------------------
def fetch_resource_metadata(client: Client, base: str, www_auth):
    candidates: list[str] = []
    if www_auth:
        match = re.search(r'resource_metadata\s*=\s*"([^"]+)"', www_auth, re.IGNORECASE)
        if not match:
            match = re.search(r"resource_metadata=([^,\s]+)", www_auth, re.IGNORECASE)
        if match:
            candidates.append(match.group(1).strip())
    candidates.append(base + "/.well-known/oauth-protected-resource")
    candidates.append(base + "/.well-known/oauth-protected-resource/mcp")
    last_error = "no resource metadata document found"
    seen = set()
    for url in candidates:
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            resp = client.request("GET", url, headers={"Accept": "application/json"}, follow=True)
        except Exception as exc:
            last_error = short_error(exc)
            continue
        if resp.status != 200:
            last_error = f"HTTP {resp.status} at {path_only(url)}"
            continue
        data = try_json(resp)
        if not isinstance(data, dict):
            last_error = f"non-JSON body at {path_only(url)}"
            continue
        return data, path_only(url)
    return None, last_error


def fetch_as_metadata(client: Client, resource_meta: dict):
    # Some servers inline the authorization-server endpoints in resource metadata.
    if resource_meta.get("authorization_endpoint") and resource_meta.get("token_endpoint"):
        return resource_meta, "inline in resource metadata"
    servers = resource_meta.get("authorization_servers")
    if not isinstance(servers, list) or not servers:
        return None, "resource metadata has no authorization_servers entry"
    as_url = str(servers[0]).rstrip("/")
    parts = urllib.parse.urlsplit(as_url)
    candidates = [as_url + "/.well-known/oauth-authorization-server"]
    if parts.path not in ("", "/"):
        candidates.append(
            f"{parts.scheme}://{parts.netloc}/.well-known/oauth-authorization-server{parts.path}"
        )
    candidates.append(as_url + "/.well-known/openid-configuration")
    last_error = "no authorization-server metadata document found"
    for url in candidates:
        try:
            resp = client.request("GET", url, headers={"Accept": "application/json"}, follow=True)
        except Exception as exc:
            last_error = short_error(exc)
            continue
        if resp.status != 200:
            last_error = f"HTTP {resp.status} at {path_only(url)}"
            continue
        data = try_json(resp)
        if not isinstance(data, dict):
            last_error = f"non-JSON body at {path_only(url)}"
            continue
        if not (data.get("authorization_endpoint") and data.get("token_endpoint")):
            last_error = f"metadata at {path_only(url)} lacks authorization/token endpoints"
            continue
        return data, path_only(url)
    return None, last_error


def register_client(client: Client, as_meta: dict):
    endpoint = as_meta.get("registration_endpoint")
    if not endpoint:
        return None, (
            "no registration_endpoint advertised (DCR unsupported); this script cannot "
            "host a client_id metadata document, so the CIMD flow is unavailable"
        )
    payload = {
        "client_name": "resivo-mcp verify_remote.py",
        "redirect_uris": [REDIRECT_URI],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    try:
        resp = client.request(
            "POST",
            endpoint,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            body=json.dumps(payload).encode("utf-8"),
        )
    except Exception as exc:
        return None, f"registration request error: {short_error(exc)}"
    if resp.status not in (200, 201):
        return None, f"registration returned HTTP {resp.status}"
    data = try_json(resp)
    if not isinstance(data, dict) or not data.get("client_id"):
        return None, "registration response has no client_id"
    client_secret = data.get("client_secret")
    auth_method = str(data.get("token_endpoint_auth_method") or "").strip().lower()
    if auth_method not in ("none", "client_secret_post", "client_secret_basic"):
        auth_method = "client_secret_post" if client_secret else "none"
    if auth_method != "none" and not client_secret:
        return None, f"server requested {auth_method} without issuing a client_secret"
    info = {
        "client_id": str(data["client_id"]),
        "client_secret": str(client_secret) if client_secret else None,
        "auth_method": auth_method,
    }
    return info, f"DCR at {path_only(endpoint)} (token_endpoint_auth_method: {auth_method})"


class _FormParser(html.parser.HTMLParser):
    """Collect <form> elements with their action, method and input fields."""

    _SKIP_TYPES = {"submit", "button", "reset", "image", "file"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[dict] = []
        self._current: dict | None = None

    def handle_starttag(self, tag, attrs):
        attrs = {name.lower(): (value or "") for name, value in attrs}
        if tag == "form":
            self._current = {
                "action": attrs.get("action", ""),
                "method": (attrs.get("method") or "get").strip().lower(),
                "fields": [],
            }
            self.forms.append(self._current)
            return
        if self._current is None:
            return
        if tag == "input":
            name = attrs.get("name")
            if not name:
                return
            input_type = (attrs.get("type") or "text").strip().lower()
            if input_type in self._SKIP_TYPES:
                return
            if input_type in ("checkbox", "radio") and "checked" not in attrs:
                return
            self._current["fields"].append((name, attrs.get("value", "")))
        elif tag == "textarea":
            name = attrs.get("name")
            if name:
                self._current["fields"].append((name, ""))

    def handle_endtag(self, tag):
        if tag == "form":
            self._current = None


def pick_form(forms: list[dict]):
    for form in forms:
        if form["method"] == "post":
            return form
    return forms[0] if forms else None


def submit_form(client: Client, form: dict, action: str, fields: list):
    try:
        if form["method"] == "get":
            url = action + ("&" if "?" in action else "?") + urllib.parse.urlencode(fields)
            return client.request("GET", url, headers={"Accept": "text/html"})
        body = urllib.parse.urlencode(fields).encode("utf-8")
        return client.request(
            "POST",
            action,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html",
            },
            body=body,
        )
    except Exception:
        return None


def do_consent(client: Client, as_meta: dict, client_info: dict, token: str, base: str):
    authorize_endpoint = as_meta["authorization_endpoint"]
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    state = secrets.token_urlsafe(16)
    params = [
        ("response_type", "code"),
        ("client_id", client_info["client_id"]),
        ("redirect_uri", REDIRECT_URI),
        ("state", state),
        ("code_challenge", challenge),
        ("code_challenge_method", "S256"),
        ("resource", base + "/mcp"),
    ]
    scopes = as_meta.get("scopes_supported")
    if isinstance(scopes, list) and scopes:
        params.append(("scope", " ".join(str(s) for s in scopes)))
    url = authorize_endpoint + ("&" if "?" in authorize_endpoint else "?") + urllib.parse.urlencode(params)
    try:
        resp = client.request("GET", url, headers={"Accept": "text/html"})
    except Exception as exc:
        return None, f"GET authorize error: {short_error(exc)}"
    if resp.status != 200:
        return None, f"GET authorize returned HTTP {resp.status}"
    parser = _FormParser()
    try:
        parser.feed(resp.text())
    except Exception as exc:
        return None, f"consent page parse error: {short_error(exc)}"
    form = pick_form(parser.forms)
    if form is None:
        return None, "consent page contains no <form>"
    action = urllib.parse.urljoin(resp.url, form["action"] or authorize_endpoint)
    fields = list(form["fields"])
    lower_names = {name.lower() for name, _ in fields}
    matched = next((c for c in TOKEN_FIELD_CANDIDATES if c in lower_names), None)
    attempts: list[list] = []
    if matched:
        attempts.append([(n, token if n.lower() == matched else v) for n, v in fields])
    for candidate in TOKEN_FIELD_CANDIDATES:
        if candidate == matched:
            continue
        attempts.append(fields + [(candidate, token)])
    attempts = attempts[:3]
    last = "consent form submission failed"
    for attempt in attempts:
        submitted = submit_form(client, form, action, attempt)
        if submitted is None:
            last = "consent form submit error"
            continue
        status = submitted.status
        if status in (301, 302, 303, 307, 308):
            target = urllib.parse.urljoin(action, submitted.header("location") or "")
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(target).query)
            error = (query.get("error") or [None])[0]
            if error:
                return None, f"authorization error: {str(error)[:60]}"
            code = (query.get("code") or [None])[0]
            if not code:
                last = "redirect without a code parameter"
                continue
            returned_state = (query.get("state") or [None])[0]
            if returned_state and returned_state != state:
                return None, "state mismatch in authorization redirect"
            return {"code": code, "verifier": verifier}, "consent accepted, authorization code received"
        last = f"consent form submit returned HTTP {status}"
    return None, last


def do_token_exchange(client: Client, as_meta: dict, client_info: dict, consent: dict, base: str):
    fields = [
        ("grant_type", "authorization_code"),
        ("code", consent["code"]),
        ("redirect_uri", REDIRECT_URI),
        ("client_id", client_info["client_id"]),
        ("code_verifier", consent["verifier"]),
        ("resource", base + "/mcp"),
    ]
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    if client_info["auth_method"] == "client_secret_post" and client_info["client_secret"]:
        fields.append(("client_secret", client_info["client_secret"]))
    if client_info["auth_method"] == "client_secret_basic" and client_info["client_secret"]:
        raw = f"{client_info['client_id']}:{client_info['client_secret']}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
    try:
        resp = client.request(
            "POST",
            as_meta["token_endpoint"],
            headers=headers,
            body=urllib.parse.urlencode(fields).encode("utf-8"),
        )
    except Exception as exc:
        return None, f"token request error: {short_error(exc)}"
    if resp.status != 200:
        return None, f"token endpoint returned HTTP {resp.status}"
    data = try_json(resp)
    if not isinstance(data, dict) or not data.get("access_token"):
        detail = "token response has no access_token"
        if isinstance(data, dict) and data.get("error"):
            detail += f" (error: {str(data.get('error'))[:60]})"
        return None, detail
    tokens = {
        "access_token": str(data["access_token"]),
        "refresh_token": str(data["refresh_token"]) if data.get("refresh_token") else None,
    }
    return tokens, "ok"


def run_oauth(client: Client, base: str, token: str, www_auth, report: Report):
    remaining = ["oauth client registration", "oauth consent", "oauth token exchange"]

    resource_meta, resource_path = fetch_resource_metadata(client, base, www_auth)
    if resource_meta is None:
        report.add("FAIL", "oauth discovery", resource_path)
        for name in remaining:
            report.add("FAIL", name, "not reached (oauth discovery failed)")
        return None
    as_meta, as_path = fetch_as_metadata(client, resource_meta)
    if as_meta is None:
        report.add("FAIL", "oauth discovery", f"resource metadata {resource_path}; {as_path}")
        for name in remaining:
            report.add("FAIL", name, "not reached (oauth discovery failed)")
        return None
    report.add("PASS", "oauth discovery", f"resource {resource_path}; AS metadata {as_path}")

    client_info, reg_detail = register_client(client, as_meta)
    if client_info is None:
        report.add("FAIL", "oauth client registration", reg_detail)
        report.add("FAIL", "oauth consent", "not reached (client registration failed)")
        report.add("FAIL", "oauth token exchange", "not reached (client registration failed)")
        return None
    report.add("PASS", "oauth client registration", reg_detail)

    consent, consent_detail = do_consent(client, as_meta, client_info, token, base)
    if consent is None:
        report.add("FAIL", "oauth consent", consent_detail)
        report.add("FAIL", "oauth token exchange", "not reached (oauth consent failed)")
        return None
    report.add("PASS", "oauth consent", consent_detail)

    tokens, exchange_detail = do_token_exchange(client, as_meta, client_info, consent, base)
    if tokens is None:
        report.add("FAIL", "oauth token exchange", exchange_detail)
        return None
    tokens["as"] = as_meta
    tokens["client"] = client_info
    tokens["resource_meta"] = resource_meta
    report.add(
        "PASS",
        "oauth token exchange",
        f"access_token issued (refresh_token: {'yes' if tokens.get('refresh_token') else 'no'})",
    )
    return tokens


# ---------------------------------------------------------------------------
# Check 4: MCP initialize + tools
# ---------------------------------------------------------------------------
def protocol_version_hint(resource_meta: dict | None) -> str:
    if isinstance(resource_meta, dict):
        for key in ("protocolVersion", "protocol_version", "mcp_protocol_version"):
            value = resource_meta.get(key)
            if isinstance(value, str) and value:
                return value
    return DEFAULT_PROTOCOL_VERSION


def mcp_post(
    client: Client,
    base: str,
    payload: dict,
    *,
    token: str | None = None,
    session_id: str | None = None,
    protocol_version: str | None = None,
    timeout: float | None = None,
) -> Response:
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    if protocol_version:
        headers["MCP-Protocol-Version"] = protocol_version
    return client.request(
        "POST", base + "/mcp", headers=headers, body=json.dumps(payload).encode("utf-8"), timeout=timeout
    )


def do_initialize(client: Client, base: str, token: str, protocol_version: str):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": protocol_version,
            "capabilities": {},
            "clientInfo": {"name": "verify_remote.py", "version": "1.0"},
        },
    }
    try:
        resp = mcp_post(client, base, payload, token=token)
    except Exception as exc:
        return None, f"request error: {short_error(exc)}"
    if resp.status != 200:
        return None, f"HTTP {resp.status}"
    obj, error = extract_jsonrpc(resp, 1)
    if obj is None:
        return None, error
    if "error" in obj:
        return None, f"JSON-RPC error {jsonrpc_error_text(obj)}"
    result = obj.get("result")
    if not isinstance(result, dict):
        return None, "initialize result is not an object"
    server_info = result.get("serverInfo") if isinstance(result.get("serverInfo"), dict) else {}
    return {
        "session_id": resp.header("mcp-session-id") or None,
        "protocol_version": str(result.get("protocolVersion") or protocol_version),
        "server_name": str(server_info.get("name") or ""),
    }, None


def do_tools_list(client: Client, base: str, token: str, session, protocol_version: str):
    payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    try:
        resp = mcp_post(
            client, base, payload, token=token,
            session_id=session.get("session_id"), protocol_version=protocol_version,
        )
    except Exception as exc:
        return None, f"request error: {short_error(exc)}"
    if resp.status != 200:
        return None, f"HTTP {resp.status}"
    obj, error = extract_jsonrpc(resp, 2)
    if obj is None:
        return None, error
    if "error" in obj:
        return None, f"JSON-RPC error {jsonrpc_error_text(obj)}"
    result = obj.get("result")
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list):
        return None, "tools/list result has no tools array"
    return [t for t in tools if isinstance(t, dict)], None


def call_tool(client: Client, base: str, token: str, session, protocol_version: str, req_id: int, name: str, args: dict):
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": args},
    }
    try:
        resp = mcp_post(
            client, base, payload, token=token,
            session_id=session.get("session_id"), protocol_version=protocol_version,
        )
    except Exception as exc:
        return None, f"request error: {short_error(exc)}"
    if resp.status == 429:
        return None, "HTTP 429 (rate limited - wait a minute and rerun)"
    if resp.status != 200:
        return None, f"HTTP {resp.status}"
    obj, error = extract_jsonrpc(resp, req_id)
    if obj is None:
        return None, error
    if "error" in obj:
        return None, f"JSON-RPC error {jsonrpc_error_text(obj)}"
    result = obj.get("result")
    if not isinstance(result, dict):
        return None, "tools/call result is not an object"
    return result, None


def run_mcp(client: Client, base: str, oauth, protocol_hint: str, report: Report) -> None:
    if not oauth or not oauth.get("access_token"):
        report.add("FAIL", "mcp initialize", "no access token (OAuth step failed)")
        for name in ["mcp tools/list"] + [f"tool {t[0]}" for t in TOOL_CALLS] + [
            "tool invalid status", "tool blank query",
        ]:
            report.add("FAIL", name, "not reached (no access token)")
        return
    token = oauth["access_token"]

    session, init_error = do_initialize(client, base, token, protocol_hint)
    if session is None:
        report.add("FAIL", "mcp initialize", init_error)
        for name in ["mcp tools/list"] + [f"tool {t[0]}" for t in TOOL_CALLS] + [
            "tool invalid status", "tool blank query",
        ]:
            report.add("FAIL", name, "not reached (mcp initialize failed)")
        return
    report.add(
        "PASS",
        "mcp initialize",
        f"protocolVersion {session['protocol_version']}"
        + (f", server {session['server_name']!r}" if session["server_name"] else "")
        + (", session id kept" if session["session_id"] else ""),
    )
    protocol_version = session["protocol_version"]

    # Best-effort initialised notification (spec-shaped clients send it).
    try:
        mcp_post(
            client,
            base,
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            token=token,
            session_id=session["session_id"],
            protocol_version=protocol_version,
        )
    except Exception:
        pass

    steps = [f"tool {t[0]}" for t in TOOL_CALLS] + ["tool invalid status", "tool blank query"]

    tools, tools_error = do_tools_list(client, base, token, session, protocol_version)
    if tools is None:
        report.add("FAIL", "mcp tools/list", tools_error)
        for name in steps:
            report.add("FAIL", name, "not reached (mcp tools/list failed)")
        return
    names = [str(t.get("name")) for t in tools]
    expected = set(EXPECTED_TOOLS)
    if len(names) == len(EXPECTED_TOOLS) and set(names) == expected:
        report.add("PASS", "mcp tools/list", f"exactly {len(EXPECTED_TOOLS)} tools as expected")
    else:
        missing = sorted(expected - set(names))
        extra = sorted(set(names) - expected)
        detail = f"{len(names)} tools"
        if missing:
            detail += f"; missing: {', '.join(missing)}"
        if extra:
            detail += f"; unexpected: {', '.join(extra)}"
        report.add("FAIL", "mcp tools/list", detail)

    req_id = 10
    for name, args in TOOL_CALLS:
        req_id += 1
        result, error = call_tool(client, base, token, session, protocol_version, req_id, name, args)
        if result is None:
            report.add("FAIL", f"tool {name}", error)
            continue
        text = result_text(result)
        if not text.strip():
            report.add("FAIL", f"tool {name}", "empty result content")
            continue
        if result.get("isError") or text.lstrip().startswith(FAILURE_PREFIXES):
            report.add("FAIL", f"tool {name}", f"tool error: {text[:120]}")
            continue
        if name == "get_summary":
            try:
                summary = json.loads(text)
            except json.JSONDecodeError:
                report.add("FAIL", f"tool {name}", f"not JSON ({len(text)} chars): {text[:80]}")
                continue
            if not isinstance(summary, dict):
                report.add("FAIL", f"tool {name}", f"expected a JSON object ({len(text)} chars)")
                continue
            report.add("PASS", f"tool {name}", f"JSON summary ({len(text)} chars)")
        else:
            report.add("PASS", f"tool {name}", f"{len(text)} chars")

    req_id += 1
    result, error = call_tool(
        client, base, token, session, protocol_version, req_id, "list_maintenance_tickets", {"status": "bogus"}
    )
    text = result_text(result) if result else ""
    if result is not None and text.lstrip().startswith("Invalid request:"):
        report.add("PASS", "tool invalid status", "rejected with 'Invalid request: ...'")
    else:
        report.add("FAIL", "tool invalid status", error or f"unexpected result text: {text[:120]!r}")

    req_id += 1
    result, error = call_tool(
        client, base, token, session, protocol_version, req_id, "search_students", {"query": ""}
    )
    text = result_text(result) if result else ""
    if result is not None and text.lstrip().startswith("Invalid request: query is required ("):
        report.add("PASS", "tool blank query", "rejected with 'Invalid request: query is required (...)'")
    else:
        report.add("FAIL", "tool blank query", error or f"unexpected result text: {text[:120]!r}")


# ---------------------------------------------------------------------------
# Check 5: refresh-token grant
# ---------------------------------------------------------------------------
def check_refresh(client: Client, base: str, oauth, protocol_hint: str, report: Report) -> None:
    if not oauth or not oauth.get("access_token"):
        report.add("FAIL", "refresh-token grant", "no access token (OAuth step failed)")
        return
    refresh_token = oauth.get("refresh_token")
    if not refresh_token:
        report.add("SKIP", "refresh-token grant", "server did not issue a refresh_token")
        return
    as_meta = oauth["as"]
    client_info = oauth["client"]
    fields = [
        ("grant_type", "refresh_token"),
        ("refresh_token", refresh_token),
        ("client_id", client_info["client_id"]),
        ("resource", base + "/mcp"),
    ]
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    if client_info["auth_method"] == "client_secret_post" and client_info["client_secret"]:
        fields.append(("client_secret", client_info["client_secret"]))
    if client_info["auth_method"] == "client_secret_basic" and client_info["client_secret"]:
        raw = f"{client_info['client_id']}:{client_info['client_secret']}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
    try:
        resp = client.request(
            "POST",
            as_meta["token_endpoint"],
            headers=headers,
            body=urllib.parse.urlencode(fields).encode("utf-8"),
        )
    except Exception as exc:
        report.add("FAIL", "refresh-token grant", f"request error: {short_error(exc)}")
        return
    if resp.status != 200:
        report.add("FAIL", "refresh-token grant", f"token endpoint returned HTTP {resp.status}")
        return
    data = try_json(resp)
    if not isinstance(data, dict) or not data.get("access_token"):
        report.add("FAIL", "refresh-token grant", "refresh response has no access_token")
        return
    session, error = do_initialize(client, base, str(data["access_token"]), protocol_hint)
    if session is None:
        report.add("FAIL", "refresh-token grant", f"new access token failed initialize: {error}")
        return
    report.add("PASS", "refresh-token grant", "new access token works for initialize")


# ---------------------------------------------------------------------------
# Write surface: annotations, room ids, round-trip, probes, gate, audit
# ---------------------------------------------------------------------------
def try_json_text(text: str):
    """Parse a tool result that should be compact JSON; None when it is not."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def parse_room_list(text: str):
    """Parse a list_rooms result; returns (rooms, error).

    The worker renders an empty list as a sentence ("No rooms found..."), so
    that maps to an empty list here; anything else must be a JSON array.
    """
    stripped = text.strip()
    if stripped.startswith("No rooms"):
        return [], None
    data = try_json_text(stripped)
    if data is None:
        return None, f"not JSON: {stripped[:80]!r}"
    if not isinstance(data, list):
        return None, f"expected a JSON array, got {type(data).__name__}"
    return [item for item in data if isinstance(item, dict)], None


def check_tool_annotations(tools: list, report: Report) -> None:
    by_name = {str(tool.get("name")): tool for tool in tools}
    problems: list[str] = []
    for name in EXPECTED_TOOLS:
        tool = by_name.get(name)
        if tool is None:
            problems.append(f"{name}: missing")
            continue
        annotations = tool.get("annotations")
        if not isinstance(annotations, dict):
            problems.append(f"{name}: no annotations")
            continue
        expect_read_only = name in READ_TOOLS
        if annotations.get("readOnlyHint") is not expect_read_only:
            problems.append(f"{name}: readOnlyHint={annotations.get('readOnlyHint')!r}")
        if (annotations.get("destructiveHint") is True) != (name in DESTRUCTIVE_TOOLS):
            problems.append(f"{name}: destructiveHint={annotations.get('destructiveHint')!r}")
    if problems:
        detail = "; ".join(problems[:4])
        if len(problems) > 4:
            detail += f" (+{len(problems) - 4} more)"
        report.add("FAIL", "tool annotations", detail)
        return
    report.add(
        "PASS",
        "tool annotations",
        "reads readOnlyHint true; writes false; destructiveHint only on "
        + ", ".join(DESTRUCTIVE_TOOLS),
    )


def check_room_ids(client: Client, base: str, token: str, session: dict, protocol_version: str, report: Report) -> None:
    result, error = call_tool(client, base, token, session, protocol_version, 100, "list_rooms", {})
    if result is None:
        report.add("FAIL", "room ids in list_rooms", error or "no result")
        return
    rooms, parse_error = parse_room_list(result_text(result))
    if rooms is None:
        report.add("FAIL", "room ids in list_rooms", parse_error)
        return
    if not rooms:
        report.add("SKIP", "room ids in list_rooms", "no rooms to check")
        return
    missing = [room for room in rooms if not UUID_RE.match(str(room.get("id") or ""))]
    if missing:
        first = missing[0]
        report.add(
            "FAIL",
            "room ids in list_rooms",
            f"{len(missing)}/{len(rooms)} items without a uuid id (first: {str(first.get('label') or '?')[:40]})",
        )
        return
    report.add("PASS", "room ids in list_rooms", f"all {len(rooms)} items carry a uuid id")


def check_write_round_trip(
    client: Client, base: str, token: str, session: dict, protocol_version: str, report: Report, cleanup_ids: list
) -> None:
    number = "MCP-" + secrets.token_hex(4)
    args = {"block": SCRATCH_BLOCK, "floor": 9, "number": number, "capacity": 2, "gender": "male"}

    result, error = call_tool(client, base, token, session, protocol_version, 110, "create_room", args)
    room_id = None
    if result is None:
        report.add("FAIL", "write round-trip create", error or "no result")
    else:
        data = try_json_text(result_text(result))
        candidate = data.get("id") if isinstance(data, dict) else None
        if isinstance(candidate, str) and UUID_RE.match(candidate):
            room_id = candidate
            cleanup_ids.append(room_id)
            report.add("PASS", "write round-trip create", f"{SCRATCH_BLOCK}/{number} id {room_id[:8]}...")
        else:
            report.add("FAIL", "write round-trip create", f"result has no uuid id: {result_text(result)[:100]!r}")

    if room_id is None:
        report.add("FAIL", "write round-trip duplicate", "not reached (create gave no room id)")
    else:
        result, error = call_tool(client, base, token, session, protocol_version, 111, "create_room", args)
        if result is None:
            report.add("FAIL", "write round-trip duplicate", error or "no result")
        else:
            text = result_text(result)
            if "already exists" in text:
                report.add("PASS", "write round-trip duplicate", "duplicate create rejected with 'already exists'")
            else:
                report.add("FAIL", "write round-trip duplicate", f"expected 'already exists', got: {text[:100]!r}")

    if room_id is None:
        report.add("FAIL", "write round-trip update", "not reached (create gave no room id)")
    else:
        result, error = call_tool(
            client, base, token, session, protocol_version, 112, "update_room", {"room_id": room_id, "capacity": 3}
        )
        if result is None:
            report.add("FAIL", "write round-trip update", error or "no result")
        else:
            data = try_json_text(result_text(result))
            if isinstance(data, dict) and data.get("capacity") == 3:
                report.add("PASS", "write round-trip update", "capacity now 3")
            else:
                report.add(
                    "FAIL", "write round-trip update", f"expected capacity 3, got: {result_text(result)[:100]!r}"
                )

    if room_id is None:
        report.add("FAIL", "write round-trip list", "not reached (create gave no room id)")
    else:
        result, error = call_tool(
            client, base, token, session, protocol_version, 113, "list_rooms", {"block": SCRATCH_BLOCK}
        )
        if result is None:
            report.add("FAIL", "write round-trip list", error or "no result")
        else:
            rooms, parse_error = parse_room_list(result_text(result))
            if rooms is None:
                report.add("FAIL", "write round-trip list", parse_error)
            else:
                found = next((room for room in rooms if str(room.get("number")) == number), None)
                if found is not None and str(found.get("id")) == room_id:
                    report.add("PASS", "write round-trip list", f"{SCRATCH_BLOCK} list shows {number} with the same id")
                else:
                    report.add("FAIL", "write round-trip list", f"{number} not listed with the created id")

    if room_id is None:
        report.add("FAIL", "write round-trip delete", "not reached (create gave no room id)")
    else:
        result, error = call_tool(
            client, base, token, session, protocol_version, 114, "delete_room", {"room_id": room_id}
        )
        if result is None:
            report.add("FAIL", "write round-trip delete", error or "no result")
        else:
            data = try_json_text(result_text(result))
            if isinstance(data, dict) and data.get("deleted") is True:
                cleanup_ids.remove(room_id)
                report.add("PASS", "write round-trip delete", "deleted true")
            else:
                report.add(
                    "FAIL", "write round-trip delete", f"expected deleted true, got: {result_text(result)[:100]!r}"
                )

    if room_id is None:
        report.add("FAIL", "write round-trip absent", "not reached (create gave no room id)")
    else:
        result, error = call_tool(
            client, base, token, session, protocol_version, 115, "list_rooms", {"block": SCRATCH_BLOCK}
        )
        if result is None:
            report.add("FAIL", "write round-trip absent", error or "no result")
        else:
            rooms, parse_error = parse_room_list(result_text(result))
            if rooms is None:
                report.add("FAIL", "write round-trip absent", parse_error)
            elif any(str(room.get("number")) == number for room in rooms):
                report.add("FAIL", "write round-trip absent", f"{number} still listed after delete")
            else:
                report.add("PASS", "write round-trip absent", f"{number} gone from the {SCRATCH_BLOCK} list")


def check_write_negative_probes(
    client: Client, base: str, token: str, session: dict, protocol_version: str, report: Report
) -> None:
    result, error = call_tool(
        client,
        base,
        token,
        session,
        protocol_version,
        120,
        "reject_registration",
        {"student_id": str(uuid.uuid4()), "reason": "   "},
    )
    text = result_text(result) if result is not None else ""
    if result is not None and text.lstrip().startswith("Invalid request:"):
        report.add(
            "PASS", "write negative probe reject_registration", "blank reason rejected with 'Invalid request: ...'"
        )
    else:
        report.add(
            "FAIL", "write negative probe reject_registration", error or f"unexpected result text: {text[:100]!r}"
        )

    result, error = call_tool(
        client, base, token, session, protocol_version, 121, "delete_room", {"room_id": str(uuid.uuid4())}
    )
    text = result_text(result) if result is not None else ""
    if result is not None and "Room not found" in text:
        report.add("PASS", "write negative probe delete_room", "unknown uuid -> 'Room not found'")
    else:
        report.add("FAIL", "write negative probe delete_room", error or f"unexpected result text: {text[:100]!r}")


def check_write_gate(
    client: Client,
    base: str,
    token: str,
    session: dict,
    protocol_version: str,
    env: dict,
    report: Report,
    cleanup_ids: list,
) -> None:
    admin, login_error = admin_token(env)
    if admin is None:
        report.add("FAIL", "write gate refusal", f"admin login failed: {login_error}")
        report.add("FAIL", "write gate re-enable", "not reached (admin login failed)")
        return
    gate_number = "MCP-" + secrets.token_hex(4)
    try:
        data, error = admin_rpc(env, "mcp_set_writes_enabled", {"p_enabled": False}, token=admin)
        if not isinstance(data, dict) or data.get("writes_enabled") is not False:
            report.add("FAIL", "write gate refusal", f"could not disable writes: {error or data}")
        else:
            result, call_error = call_tool(
                client,
                base,
                token,
                session,
                protocol_version,
                130,
                "create_room",
                {"block": SCRATCH_BLOCK, "floor": 9, "number": gate_number, "capacity": 2, "gender": "male"},
            )
            text = result_text(result) if result is not None else ""
            if result is None:
                report.add("FAIL", "write gate refusal", call_error or "no result")
            elif text.lstrip().startswith(WRITING_DISABLED_PREFIX):
                report.add("PASS", "write gate refusal", "create_room refused with the disabled message")
            else:
                report.add("FAIL", "write gate refusal", f"expected the disabled message, got: {text[:100]!r}")
                # Gate broken: the room may have been created - clean it up.
                data = try_json_text(text)
                candidate = data.get("id") if isinstance(data, dict) else None
                if isinstance(candidate, str) and UUID_RE.match(candidate):
                    cleanup_ids.append(candidate)
    finally:
        # Always re-enable, even when a probe above failed.
        data, error = admin_rpc(env, "mcp_set_writes_enabled", {"p_enabled": True}, token=admin)
        if not isinstance(data, dict) or data.get("writes_enabled") is not True:
            report.add("FAIL", "write gate re-enable", f"could not re-enable writes: {error or data}")
        else:
            settings, error = admin_rpc(env, "mcp_get_settings", {}, token=admin)
            if not isinstance(settings, dict) or settings.get("writes_enabled") is not True:
                report.add("FAIL", "write gate re-enable", f"read-back failed: {error or settings}")
            else:
                report.add("PASS", "write gate re-enable", "writes re-enabled and read back true")


def check_audit_outcomes(env: dict, report: Report) -> None:
    admin, login_error = admin_token(env)
    if admin is None:
        report.add("FAIL", "audit outcomes", f"admin login failed: {login_error}")
        return
    rows, error = admin_rpc(env, "mcp_list_audit", {"p_limit": 20}, token=admin)
    if not isinstance(rows, list):
        report.add("FAIL", "audit outcomes", f"mcp_list_audit failed: {error or 'non-array result'}")
        return
    rows = [row for row in rows if isinstance(row, dict)]
    ok_tools = {str(row.get("tool")) for row in rows if row.get("ok") is True}
    missing = [tool for tool in ROUND_TRIP_TOOLS if tool not in ok_tools]
    gate_refused = any(
        row.get("ok") is False and WRITING_DISABLED_PREFIX.rstrip(".") in str(row.get("detail") or "")
        for row in rows
    )
    problems = []
    if missing:
        problems.append("no ok:true rows for: " + ", ".join(missing))
    if not gate_refused:
        problems.append("no ok:false gate-refusal row")
    if problems:
        report.add("FAIL", "audit outcomes", "; ".join(problems))
        return
    report.add("PASS", "audit outcomes", f"{len(rows)} rows: round-trip ok:true and the gate refusal ok:false")


def run_write_checks(client: Client, base: str, oauth, protocol_hint: str, report: Report) -> None:
    steps = [
        "tool annotations",
        "room ids in list_rooms",
        "write round-trip create",
        "write round-trip duplicate",
        "write round-trip update",
        "write round-trip list",
        "write round-trip delete",
        "write round-trip absent",
        "write negative probe reject_registration",
        "write negative probe delete_room",
        "write gate refusal",
        "write gate re-enable",
        "audit outcomes",
    ]
    if not oauth or not oauth.get("access_token"):
        for name in steps:
            report.add("FAIL", name, "not reached (no access token)")
        return
    token = oauth["access_token"]

    session, init_error = do_initialize(client, base, token, protocol_hint)
    if session is None:
        for name in steps:
            report.add("FAIL", name, "not reached (mcp initialize failed)")
        return
    protocol_version = session["protocol_version"]

    # Best-effort initialised notification (spec-shaped clients send it).
    try:
        mcp_post(
            client,
            base,
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            token=token,
            session_id=session["session_id"],
            protocol_version=protocol_version,
        )
    except Exception:
        pass

    cleanup_ids: list[str] = []
    try:
        tools, tools_error = do_tools_list(client, base, token, session, protocol_version)
        if tools is None:
            report.add("FAIL", "tool annotations", f"tools/list failed: {tools_error}")
        else:
            check_tool_annotations(tools, report)
        check_room_ids(client, base, token, session, protocol_version, report)
        check_write_round_trip(client, base, token, session, protocol_version, report, cleanup_ids)
        check_write_negative_probes(client, base, token, session, protocol_version, report)
        env = load_env()
        check_write_gate(client, base, token, session, protocol_version, env, report, cleanup_ids)
        check_audit_outcomes(env, report)
    finally:
        # Best-effort: delete any scratch room the round-trip could not remove.
        for offset, room_id in enumerate(cleanup_ids):
            try:
                call_tool(
                    client, base, token, session, protocol_version, 900 + offset, "delete_room", {"room_id": room_id}
                )
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Check 6: rate-limit probe (65 rapid unauthenticated POST /mcp calls)
# ---------------------------------------------------------------------------
def check_rate_limit(client: Client, base: str, report: Report) -> None:
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": DEFAULT_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "verify_remote.py", "version": "1.0"},
            },
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    seen_429 = False
    errors: list[str] = []
    last_status = None
    attempts = 0
    for attempt in range(1, PROBE_REQUESTS + 1):
        attempts = attempt
        try:
            resp = client.request(
                "POST", base + "/mcp", headers=headers, body=payload, timeout=PROBE_TIMEOUT
            )
        except Exception as exc:
            errors.append(short_error(exc))
            if len(errors) > 5:
                break
            continue
        last_status = resp.status
        if resp.status == 429:
            seen_429 = True
            break
    if seen_429:
        report.add("PASS", "rate limit", f"HTTP 429 after {attempts} rapid requests")
    elif errors:
        report.add("FAIL", "rate limit", f"probe aborted: {len(errors)} request errors (last: {errors[-1]})")
    else:
        report.add(
            "SKIP",
            "rate limit",
            f"no 429 among {PROBE_REQUESTS} requests (last HTTP {last_status}) - rate limit not enabled",
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def normalize_base(raw: str) -> str:
    base = raw.strip().rstrip("/")
    if "://" not in base:
        host = base.split("/", 1)[0].split(":", 1)[0].lower()
        scheme = "http" if host in ("localhost", "127.0.0.1", "[::1]", "::1") else "https"
        base = f"{scheme}://{base}"
    return base


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verify_remote.py",
        description="Acceptance checks for the hosted RÉSIVO MCP worker (stdlib only).",
    )
    parser.add_argument("base_url", help="Base URL, e.g. https://resivo-mcp.example.workers.dev or http://localhost:8788")
    parser.add_argument("--token", help="Consent token (default: MCP_AUTH_TOKEN from mcp/.env). Never printed.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Per-request timeout in seconds (default: 15)")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    try:
        args = parse_args(argv)
    except SystemExit as exc:  # argparse: --help exits 0, usage errors exit 2
        code = exc.code
        return 2 if code is None else int(code)
    base = normalize_base(args.base_url)
    timeout = max(1.0, float(args.timeout))
    print(f"verify_remote.py -> {base}", flush=True)

    token, token_source = resolve_token(args.token)
    if not token:
        print(
            "FAIL token: not found - pass --token or add MCP_AUTH_TOKEN=... to mcp/.env",
            flush=True,
        )
        return 2
    print(f"token: {token_source} (value hidden)", flush=True)

    client = Client(timeout=timeout)
    report = Report()

    check_health(client, base, report)
    www_auth = check_unauth(client, base, report)
    oauth = run_oauth(client, base, token, www_auth, report)
    hint = protocol_version_hint(oauth.get("resource_meta") if oauth else None)
    run_mcp(client, base, oauth, hint, report)
    check_refresh(client, base, oauth, hint, report)
    run_write_checks(client, base, oauth, hint, report)
    check_rate_limit(client, base, report)

    return report.summary()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
