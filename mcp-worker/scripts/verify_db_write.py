"""Live-DB probe for the MCP write surface (migration A3).

Stdlib only; reads SUPABASE_URL / SUPABASE_ANON_KEY / ADMIN_EMAIL /
ADMIN_PASSWORD from mcp/.env without ever printing secret values, then logs in
as the seeded admin (password grant) and probes the write RPCs over PostgREST:

  1.    mcp_get_settings reports writes_enabled true.
  2.    mcp_set_writes_enabled flips it off, then back on.
  3-6.  scratch-room lifecycle in block ZZT (create, duplicate, partial update,
        delete, delete again) -- the script's own data only; always cleaned up.
  7-8.  safe negative probes: unknown ticket id, blank rejection reason.
  9.    two-phase audit: mcp_log_audit -> mcp_complete_audit -> mcp_list_audit.

The probe flips the real writes off-switch and deliberately writes one
'verify_db_probe' audit row; the off-switch is always restored to enabled and
the scratch room is always deleted (best-effort, even after a failure).

Exit status: 0 when every check passed, non-zero when any FAIL.
"""

import json
import pathlib
import re
import secrets
import sys
import urllib.error
import urllib.request
import uuid

REPO = pathlib.Path(__file__).resolve().parents[2]

env = {}
for line in (REPO / "mcp" / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

url = env["SUPABASE_URL"].rstrip("/")
anon = env["SUPABASE_ANON_KEY"]

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

passed = 0
failed = 0


def report(ok, name, detail=""):
    global passed, failed
    line = f"{'PASS' if ok else 'FAIL'} {name}"
    if detail:
        line += f": {detail}"
    print(line, flush=True)
    if ok:
        passed += 1
    else:
        failed += 1


def compact(value):
    text = json.dumps(value, separators=(",", ":"), default=str)
    return text if len(text) <= 160 else text[:157] + "..."


def request(path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url + path,
        data=data,
        headers={"apikey": anon, "Content-Type": "application/json", **(headers or {})},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except Exception as exc:  # URLError / timeout -> reported as HTTP 0
        return 0, str(exc).encode()


# ---------------------------------------------------------------------------
# Login as the seeded admin (values never printed).
# ---------------------------------------------------------------------------
status, body = request(
    "/auth/v1/token?grant_type=password",
    {"email": env["ADMIN_EMAIL"], "password": env["ADMIN_PASSWORD"]},
)
try:
    token = json.loads(body)["access_token"]
except Exception:
    token = None
if status != 200 or not token:
    print(f"FAIL admin login: HTTP {status}")
    sys.exit(1)
auth = {"Authorization": "Bearer " + token}


def rpc(name, params):
    """POST one RPC. Returns (http_status, parsed_json_or_None, message)."""
    status, body = request("/rest/v1/rpc/" + name, params, headers=auth)
    data = None
    if body:
        try:
            data = json.loads(body)
        except ValueError:
            data = None
    message = data.get("message") if isinstance(data, dict) else None
    return status, data, message


# ---------------------------------------------------------------------------
# Probes.
# ---------------------------------------------------------------------------
room_id = None
room_deleted = False

try:
    # 1. Settings read: writes enabled.
    status, data, _ = rpc("mcp_get_settings", {})
    ok = status == 200 and isinstance(data, dict) and data.get("writes_enabled") is True
    report(ok, "mcp_get_settings -> writes_enabled true", f"HTTP {status} {compact(data)}")

    # 2. Off-switch: off, then back on.
    status, data, _ = rpc("mcp_set_writes_enabled", {"p_enabled": False})
    ok = status == 200 and isinstance(data, dict) and data.get("writes_enabled") is False
    report(ok, "mcp_set_writes_enabled(false) -> false", f"HTTP {status} {compact(data)}")

    status, data, _ = rpc("mcp_set_writes_enabled", {"p_enabled": True})
    ok = status == 200 and isinstance(data, dict) and data.get("writes_enabled") is True
    report(ok, "mcp_set_writes_enabled(true) -> true", f"HTTP {status} {compact(data)}")

    # 3. Scratch room create (block ZZT; the script's own data only).
    number = "DBTEST-" + secrets.token_hex(3).upper()
    create_args = {
        "p_block": "ZZT",
        "p_floor": 9,
        "p_number": number,
        "p_capacity": 2,
        "p_gender": "male",
    }
    status, data, _ = rpc("mcp_create_room", create_args)
    room_id = data.get("id") if isinstance(data, dict) else None
    ok = (
        status == 200
        and isinstance(data, dict)
        and isinstance(room_id, str)
        and UUID_RE.match(room_id) is not None
        and data.get("block") == "ZZT"
        and data.get("number") == number
    )
    report(ok, "mcp_create_room -> row with id", f"HTTP {status} {compact(data)}")

    # 4. Duplicate create is rejected.
    status, data, message = rpc("mcp_create_room", create_args)
    ok = status != 200 and isinstance(message, str) and "already exists" in message
    report(
        ok,
        "duplicate mcp_create_room -> already exists",
        f"HTTP {status} {compact(message if message else data)}",
    )

    # 5. Partial update: capacity only.
    status, data, _ = rpc("mcp_update_room", {"p_room": room_id, "p_capacity": 3})
    ok = status == 200 and isinstance(data, dict) and data.get("capacity") == 3
    report(ok, "mcp_update_room capacity -> 3", f"HTTP {status} {compact(data)}")

    # 6. Delete, then delete again.
    status, data, _ = rpc("mcp_delete_room", {"p_room": room_id})
    ok = status == 200 and isinstance(data, dict) and data.get("deleted") is True
    room_deleted = ok
    report(ok, "mcp_delete_room -> deleted true", f"HTTP {status} {compact(data)}")

    status, data, message = rpc("mcp_delete_room", {"p_room": room_id})
    ok = status != 200 and isinstance(message, str) and "room not found" in message
    report(
        ok,
        "second mcp_delete_room -> room not found",
        f"HTTP {status} {compact(message if message else data)}",
    )

    # 7. Unknown ticket id (never touches a real ticket).
    status, data, message = rpc(
        "mcp_update_ticket", {"p_ticket": str(uuid.uuid4()), "p_status": "in_progress"}
    )
    ok = status != 200 and isinstance(message, str) and "ticket not found" in message
    report(
        ok,
        "mcp_update_ticket unknown id -> ticket not found",
        f"HTTP {status} {compact(message if message else data)}",
    )

    # 8. Blank rejection reason on an unknown student (fails before any write).
    status, data, message = rpc(
        "reject_student", {"p_student": str(uuid.uuid4()), "p_reason": "   "}
    )
    ok = status != 200 and isinstance(message, str) and "reason required" in message
    report(
        ok,
        "reject_student blank reason -> reason required",
        f"HTTP {status} {compact(message if message else data)}",
    )

    # 9. Two-phase audit: attempt row -> outcome -> read back.
    status, data, _ = rpc("mcp_log_audit", {"p_tool": "verify_db_probe", "p_args": {}})
    audit_id = data if isinstance(data, int) and not isinstance(data, bool) else None
    report(
        status == 200 and audit_id is not None,
        "mcp_log_audit -> numeric id",
        f"HTTP {status} {compact(data)}",
    )

    if audit_id is not None:
        status, _ = request(
            "/rest/v1/rpc/mcp_complete_audit",
            {"p_id": audit_id, "p_ok": True, "p_detail": "probe"},
            headers=auth,
        )
        report(status == 204, "mcp_complete_audit -> 204", f"HTTP {status}")
    else:
        report(False, "mcp_complete_audit -> 204", "no audit id from mcp_log_audit")

    status, data, _ = rpc("mcp_list_audit", {"p_limit": 5})
    newest = data[0] if isinstance(data, list) and data else None
    ok = (
        isinstance(newest, dict)
        and newest.get("ok") is True
        and newest.get("detail") == "probe"
    )
    report(ok, "mcp_list_audit newest row ok=true detail=probe", compact(newest))

finally:
    # Best-effort: remove the scratch room if a step failed before the delete.
    if room_id is not None and not room_deleted:
        try:
            rpc("mcp_delete_room", {"p_room": room_id})
        except Exception:
            pass
    # Best-effort: never leave the writes off-switch disabled.
    try:
        rpc("mcp_set_writes_enabled", {"p_enabled": True})
    except Exception:
        pass

print(f"SUMMARY: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
