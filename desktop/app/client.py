import json
import time
import logging
import re
import threading

from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from .config import SUPABASE_URL, SUPABASE_ANON_KEY
from .coalescer import install_query_coalescer
from .tls import configure_tls_environment
from .timeouts import (
    AUTH_TIMEOUT,
    CONNECT_TIMEOUT_S,
    EDGE_FUNCTION_TIMEOUT_S,
    FUNCTION_TIMEOUT,
    POSTGREST_TIMEOUT,
    READ_TIMEOUT_S,
    STORAGE_DOWNLOAD_TIMEOUT_S,
    STORAGE_TIMEOUT,
    STORAGE_UPLOAD_TIMEOUT_S,
    WRITE_TIMEOUT_S,
    NetworkError,
    NetworkTimeoutError,
    execute_network_call,
    is_timeout_exception,
)

# Supabase's synchronous client keeps lazily-created sub-clients and an auth
# session on one object.  The live-sync thread and action workers share it, so
# every background operation serializes its use through this re-entrant lock.
CLIENT_LOCK = threading.RLock()

_log = logging.getLogger("resivo.client")


class RoleLookupError(RuntimeError):
    """The signed-in user's role could not be verified.

    Raised instead of silently returning ``None`` so the login window and the
    main window can offer a retry instead of downgrading the session to staff.
    """


# Successful role lookups, keyed by ``id(client)``.  The client itself is kept
# in the entry so a later object cannot be mistaken for it after id reuse.
# Entries also remember the local session identity: signing out (or signing in
# as somebody else) invalidates the cached role without a network call.
_ROLE_CACHE: dict[int, tuple[object, str, str]] = {}
_ROLE_CACHE_LOCK = threading.RLock()

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_CREDENTIAL_RE = re.compile(
    r"(?i)(password|passwd|pwd|token|api[_-]?key|authorization)\s*[:=]\s*\S+"
)


def make_client() -> Client:
    configure_tls_environment()
    install_query_coalescer()
    opts = ClientOptions(
        postgrest_client_timeout=POSTGREST_TIMEOUT,
        storage_client_timeout=STORAGE_TIMEOUT,
        function_client_timeout=FUNCTION_TIMEOUT,
    )
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=opts)
    if hasattr(client, "auth") and hasattr(client.auth, "_http_client") and client.auth._http_client is not None:
        client.auth._http_client.timeout = AUTH_TIMEOUT
    return client


def sign_in(client: Client, email: str, password: str):
    return execute_network_call(
        lambda: client.auth.sign_in_with_password({"email": email, "password": password}),
        is_write=False,
    )


def clear_local_session(client: Client) -> None:
    """Drop the locally stored session when a server sign-out failed.

    ``gotrue`` keeps the refresh token in memory or in local storage until
    ``_remove_session()`` runs.  Calling it explicitly prevents a failed network
    request from leaving credentials behind for the next person at the console.
    """
    auth = getattr(client, "auth", None)
    remove_session = getattr(auth, "_remove_session", None)
    if callable(remove_session):
        remove_session()
        return
    if auth is None:
        raise RuntimeError("The authentication client is not available.")
    auth._in_memory_session = None


def _normalize_role(role) -> str:
    """Case/whitespace-insensitive role value (``" Admin "`` -> ``"admin"``)."""
    if role is None:
        return ""
    return str(role).strip().lower()


def redact_sensitive(text: str) -> str:
    """Remove tokens, keys and credential-looking values from log/UI text."""
    if not text:
        return ""
    if SUPABASE_ANON_KEY:
        text = text.replace(SUPABASE_ANON_KEY, "[redacted]")
    text = _JWT_RE.sub("[redacted]", text)
    return _CREDENTIAL_RE.sub(r"\1=[redacted]", text)


def _safe_reason(exc: BaseException) -> str:
    """Short failure reason with credentials/keys removed."""
    message = str(exc).strip().splitlines()[0].strip() if str(exc).strip() else ""
    message = redact_sensitive(message)[:300]
    return f"{exc.__class__.__name__}: {message}" if message else exc.__class__.__name__


def _stored_session(client: Client):
    """The session already held locally, without a token refresh round trip.

    ``gotrue.get_session()`` refreshes an expiring token over HTTP.  Role
    checks run from GUI slots, so reading the in-memory/storage session avoids
    freezing the window and racing another worker holding ``CLIENT_LOCK``.
    """
    auth = getattr(client, "auth", None)
    if auth is None:
        return None

    # Installed gotrue keeps one of these two copies.  ``get_session()`` is
    # deliberately never called here: it refreshes an expiring token over HTTP
    # and role/session labels run from GUI slots.
    if not hasattr(auth, "_in_memory_session"):
        return None
    session = getattr(auth, "_in_memory_session", None)
    if session is not None:
        return session
    if getattr(auth, "_persist_session", False):
        storage = getattr(auth, "_storage", None)
        storage_key = getattr(auth, "_storage_key", None)
        if storage is None or not storage_key:
            return None
        try:
            raw = storage.get_item(storage_key)
        except Exception:  # noqa: BLE001 - absent/unreadable session
            return None
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError):
                return None
        return raw
    return None


def clone_client(client: Client) -> Client:
    """Create an independent client instance sharing the current auth session.

    Safe for concurrent workers running on separate threads without sharing
    sub-client HTTP sessions or racing on the main client's auth state.
    """
    new_client = make_client()
    session = _stored_session(client)
    if session is not None:
        if hasattr(new_client, "auth"):
            new_client.auth._in_memory_session = session
        token = getattr(session, "access_token", None) or (
            session.get("access_token") if isinstance(session, dict) else None
        )
        if token and hasattr(new_client, "postgrest") and hasattr(new_client.postgrest, "auth"):
            new_client.postgrest.auth(token)
    return new_client


def stored_user(client: Client):
    """The signed-in user from the local session (never a network call).

    ``gotrue`` stores the signed-in user as an object or, when persistence is
    enabled, as JSON in local storage.  Both shapes are returned unchanged so
    callers can read identity fields without triggering a token refresh.
    """
    session = _stored_session(client)
    if session is None:
        return None
    return (
        session.get("user")
        if isinstance(session, dict)
        else getattr(session, "user", None)
    )


def _user_value(user, field: str):
    """Read a field from a session user dict or object."""
    if isinstance(user, dict):
        return user.get(field)
    return getattr(user, field, None)


def stored_user_id(client: Client) -> str | None:
    """Signed-in user id from the local session (never a network call)."""
    user_id = _user_value(stored_user(client), "id")
    if isinstance(user_id, str) and user_id.strip():
        return user_id.strip()
    return None


def stored_user_email(client: Client) -> str:
    """Signed-in email from the local session (never a network call)."""
    email = _user_value(stored_user(client), "email")
    if isinstance(email, str) and email.strip():
        return email.strip()
    return ""


def stored_user_display_name(client: Client, fallback: str = "") -> str:
    """Session metadata name, then the email local part, else ``fallback``.

    Reads only the locally stored session; a mock or signed-out client falls
    through to the caller's neutral label.
    """
    user = stored_user(client)
    metadata = _user_value(user, "user_metadata") or {}
    if isinstance(metadata, dict):
        for key in ("full_name", "name"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    email = _user_value(user, "email")
    if isinstance(email, str) and email.strip():
        local = email.split("@")[0].replace(".", " ").replace("_", " ").strip()
        if local:
            return local.title()
    return fallback


def _session_key(client: Client) -> str:
    """Identity from the stored session only (never a network call)."""
    user_id = stored_user_id(client)
    if user_id:
        return f"id:{user_id}"
    email = stored_user_email(client)
    if email:
        return f"email:{email.lower()}"
    return ""


def _cached_role(client: Client) -> str | None:
    with _ROLE_CACHE_LOCK:
        entry = _ROLE_CACHE.get(id(client))
    if entry is None or entry[0] is not client:
        return None
    cached_session, role = entry[1], entry[2]
    current_session = _session_key(client)
    # A cached role belongs to one signed-in session.  An unknown identity is a
    # cache miss; once the local session changes the lookup must run again.
    if not cached_session or current_session != cached_session:
        return None
    return role


def remember_role(client: Client, role, *, session_key: str | None = None) -> str:
    """Cache the role already verified by the caller (e.g. right after sign-in)."""
    normalized = _normalize_role(role)
    if not normalized:
        return ""
    key = session_key if session_key is not None else _session_key(client)
    if not key:
        # Never attach a role to an unknown session: that is how a later sign-in
        # would inherit the previous account's admin rights.
        return normalized
    with _ROLE_CACHE_LOCK:
        _ROLE_CACHE[id(client)] = (client, key, normalized)
    return normalized


def forget_role(client: Client) -> None:
    """Drop the cached role for ``client`` (sign-out/denied access)."""
    with _ROLE_CACHE_LOCK:
        _ROLE_CACHE.pop(id(client), None)


def resolve_role(client: Client) -> str:
    """Return the normalized role for the signed-in user or raise.

    Network, auth and profile failures become :class:`RoleLookupError` with a
    safe reason.  Successful results are cached per client/session so a role
    verified at login is not queried again by the main window or Settings.
    """
    cached = _cached_role(client)
    if cached is not None:
        return cached

    with CLIENT_LOCK:
        cached = _cached_role(client)
        if cached is not None:
            return cached
        try:
            response = execute_network_call(lambda: client.auth.get_user(), is_write=False)
            user = (
                response.get("user")
                if isinstance(response, dict)
                else getattr(response, "user", None)
            )
            if not user:
                raise RoleLookupError("No signed-in user session was found.")

            user_id = user.get("id") if isinstance(user, dict) else user.id
            if not isinstance(user_id, str) or not user_id.strip():
                raise RoleLookupError("The signed-in account has no user id.")
            profile = execute_network_call(
                lambda: (
                    client.table("profiles")
                    .select("role")
                    .eq("id", user_id)
                    .single()
                    .execute()
                ),
                is_write=False,
            )
            data = (
                profile.get("data")
                if isinstance(profile, dict)
                else getattr(profile, "data", None)
            )
            if isinstance(data, list):
                data = data[0] if data else None
            role = data.get("role") if isinstance(data, dict) else None
            normalized = _normalize_role(role)
            if not normalized:
                raise RoleLookupError("The signed-in account has no role assigned.")
        except RoleLookupError as exc:
            _log.warning("Role lookup failed: %s", exc)
            raise
        except Exception as exc:  # noqa: BLE001 - translated to a safe error
            if isinstance(exc, NetworkTimeoutError):
                reason = str(exc)
            else:
                reason = _safe_reason(exc)
            _log.warning("Role lookup failed: %s", reason)
            raise RoleLookupError(reason) from exc

    remember_role(client, normalized, session_key=f"id:{user_id}")
    return normalized


def current_role(client: Client) -> str | None:
    """Backwards-compatible non-throwing role lookup.

    Returns the normalized role, or ``None`` when it cannot be verified.  New
    UI code that needs to distinguish "failed" from "not staff" should call
    :func:`resolve_role` instead.
    """
    try:
        return resolve_role(client)
    except RoleLookupError:
        return None
    except Exception as exc:  # noqa: BLE001 - legacy callers expect a value
        _log.warning("Role lookup failed: %s", _safe_reason(exc))
        return None


PAGE_SIZE = 1000


def _fetch_all_rows(query) -> list[dict]:
    """Fetch all rows from a PostgREST query, paginating if supported."""
    if not hasattr(query, "range") or not callable(getattr(query, "range", None)):
        resp = execute_network_call(lambda: query.execute(), is_write=False)
        return list(resp.data or [])

    all_rows: list[dict] = []
    offset = 0
    while True:
        resp = execute_network_call(
            lambda: query.range(offset, offset + PAGE_SIZE - 1).execute(),
            is_write=False,
        )
        rows = list(resp.data or [])
        all_rows.extend(rows)
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return all_rows


def room_occupancy(client: Client, *, strict: bool = False) -> dict[str, int]:
    """Count occupied beds per room.

    Attempts server-side aggregation via RPC ``get_room_occupancy`` first.
    Falls back to client-side counting if the RPC is unavailable or in mock test
    environments.

    The legacy pages treat a read failure as "no occupancy data" so their
    tables still render.  Callers that must not turn a failure into a fake zero
    pass ``strict=True`` to receive the exception instead.
    """
    with CLIENT_LOCK:
        try:
            # 1. Fast path: server-side Postgres aggregation via RPC
            if hasattr(client, "rpc") and callable(getattr(client, "rpc", None)):
                try:
                    rpc_resp = execute_network_call(
                        lambda: client.rpc("get_room_occupancy", {}).execute(),
                        is_write=False,
                    )
                    data = getattr(rpc_resp, "data", None)
                    if isinstance(data, list):
                        return {
                            str(r["room_id"]): int(r.get("occupied", 0) or 0)
                            for r in data
                            if isinstance(r, dict) and r.get("room_id")
                        }
                except Exception:
                    pass

            # 2. Fallback path: client-side aggregation
            query = client.table("students").select("room_id").eq("status", "active")
            counts: dict[str, int] = {}
            for row in _fetch_all_rows(query):
                rid = row.get("room_id")
                if rid:
                    counts[str(rid)] = counts.get(str(rid), 0) + 1
            return counts
        except Exception:
            if strict:
                raise
            return {}


_OFFICIAL_CACHE: dict[int, tuple[float, dict[str, dict]]] = {}
_OFFICIAL_CACHE_LOCK = threading.RLock()
_OFFICIAL_CACHE_TTL = 30.0  # seconds


def invalidate_official_lookup_cache(client: Client | None = None) -> None:
    """Invalidate cached official admissions roster records."""
    with _OFFICIAL_CACHE_LOCK:
        if client is not None:
            _OFFICIAL_CACHE.pop(id(client), None)
        else:
            _OFFICIAL_CACHE.clear()


def official_lookup(client: Client, *, force: bool = False) -> dict[str, dict]:
    """Look up official roster entries keyed by card_id.

    Results are cached in memory for up to 30 seconds per client object, or until
    explicitly invalidated by ``invalidate_official_lookup_cache()`` (e.g. after
    roster import or edits). This eliminates redundant full table downloads during
    application reloads and resident inspections.
    """
    now = time.monotonic()
    if not force:
        with _OFFICIAL_CACHE_LOCK:
            entry = _OFFICIAL_CACHE.get(id(client))
            if entry is not None and (now - entry[0]) < _OFFICIAL_CACHE_TTL:
                return dict(entry[1])

    with CLIENT_LOCK:
        if not force:
            with _OFFICIAL_CACHE_LOCK:
                entry = _OFFICIAL_CACHE.get(id(client))
                if entry is not None and (now - entry[0]) < _OFFICIAL_CACHE_TTL:
                    return dict(entry[1])
        try:
            query = client.table("official_residents").select(
                "card_id, first_name, last_name, birth_date, gender, university, faculty"
            )
            result = {r["card_id"]: r for r in _fetch_all_rows(query) if "card_id" in r}
            with _OFFICIAL_CACHE_LOCK:
                _OFFICIAL_CACHE[id(client)] = (time.monotonic(), result)
            return dict(result)
        except Exception:
            return {}


DEFAULT_RESIDENCE_NAME = "Cité Universitaire · Tlemcen"
_RESIDENCE_CACHE: dict[int, tuple[float, dict]] = {}
_RESIDENCE_CACHE_LOCK = threading.RLock()
_RESIDENCE_CACHE_TTL = 30.0


def _normalize_residence_gender(value) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized if normalized in ("male", "female") else None


def _extract_dict_payload(resp) -> dict | None:
    data = resp.get("data") if isinstance(resp, dict) else getattr(resp, "data", None)
    if isinstance(data, list) and data:
        data = data[0]
    return data if isinstance(data, dict) else None


def invalidate_residence_settings_cache(client: Client | None = None) -> None:
    """Clear cached single-gender residence settings."""
    with _RESIDENCE_CACHE_LOCK:
        if client is not None:
            _RESIDENCE_CACHE.pop(id(client), None)
        else:
            _RESIDENCE_CACHE.clear()


def get_cached_residence_settings(client: Client | None) -> dict | None:
    """Return cached residence settings without issuing any network call."""
    if client is None:
        return None
    now = time.monotonic()
    with _RESIDENCE_CACHE_LOCK:
        entry = _RESIDENCE_CACHE.get(id(client))
        if entry is not None and (now - entry[0]) < _RESIDENCE_CACHE_TTL:
            return dict(entry[1])
    return None


def _store_residence_cache(client: Client | None, payload: dict) -> None:
    if client is None or not payload.get("loaded"):
        return
    with _RESIDENCE_CACHE_LOCK:
        _RESIDENCE_CACHE[id(client)] = (time.monotonic(), dict(payload))


def fetch_residence_public(client: Client, *, force: bool = False) -> dict:
    """Read singleton residence name and gender via ``get_residence_public()``."""
    fallback = {
        "residence_name": DEFAULT_RESIDENCE_NAME,
        "residence_gender": None,
        "loaded": False,
    }
    if client is None:
        return fallback

    if not force:
        cached = get_cached_residence_settings(client)
        if cached is not None:
            return cached

    with CLIENT_LOCK:
        if not force:
            cached = get_cached_residence_settings(client)
            if cached is not None:
                return cached

        payload_dict = None
        if hasattr(client, "rpc") and callable(getattr(client, "rpc", None)):
            try:
                resp = execute_network_call(
                    lambda: client.rpc("get_residence_public", {}).execute(),
                    is_write=False,
                )
                cand = _extract_dict_payload(resp)
                if cand is not None and "residence_gender" in cand:
                    payload_dict = cand
            except Exception as exc:  # noqa: BLE001 - fallback below
                _log.debug("get_residence_public fallback needed: %s", exc)

        if payload_dict is None and hasattr(client, "table") and callable(getattr(client, "table", None)):
            try:
                resp = execute_network_call(
                    lambda: (
                        client.table("residence_settings")
                        .select("residence_name, residence_gender")
                        .eq("id", 1)
                        .execute()
                    ),
                    is_write=False,
                )
                cand = _extract_dict_payload(resp)
                if cand is not None and "residence_gender" in cand:
                    payload_dict = cand
            except Exception:  # noqa: BLE001
                payload_dict = None

        if payload_dict is None:
            return fallback

        result = {
            "residence_name": str(payload_dict.get("residence_name") or DEFAULT_RESIDENCE_NAME).strip()
            or DEFAULT_RESIDENCE_NAME,
            "residence_gender": _normalize_residence_gender(payload_dict.get("residence_gender")),
            "loaded": True,
        }
        _store_residence_cache(client, result)
        return dict(result)


def fetch_residence_settings_admin(client: Client) -> dict:
    """Read residence settings and last audit metadata for administrators."""
    with CLIENT_LOCK:
        resp = execute_network_call(
            lambda: client.rpc("get_residence_settings_admin", {}).execute(),
            is_write=False,
        )
        data = _extract_dict_payload(resp)
        if not isinstance(data, dict) or "residence_gender" not in data:
            pub = fetch_residence_public(client, force=True)
            return {
                "residence_name": pub["residence_name"],
                "residence_gender": pub["residence_gender"],
                "last_changed_at": None,
                "last_changed_by": None,
                "last_changed_by_name": None,
                "loaded": pub["loaded"],
            }
        normalized = {
            "residence_name": str(data.get("residence_name") or DEFAULT_RESIDENCE_NAME).strip()
            or DEFAULT_RESIDENCE_NAME,
            "residence_gender": _normalize_residence_gender(data.get("residence_gender")),
            "updated_at": data.get("updated_at"),
            "updated_by": data.get("updated_by"),
            "last_changed_at": data.get("last_changed_at"),
            "last_changed_by": data.get("last_changed_by"),
            "last_changed_by_name": data.get("last_changed_by_name"),
            "last_old_gender": _normalize_residence_gender(data.get("last_old_gender")),
            "last_new_gender": _normalize_residence_gender(data.get("last_new_gender")),
            "loaded": True,
        }
        _store_residence_cache(client, normalized)
        return dict(normalized)


def fetch_residence_gender_impact(client: Client, new_gender: str) -> dict:
    """Preview impact counts before switching ``residence_gender`` (admin only)."""
    with CLIENT_LOCK:
        resp = execute_network_call(
            lambda: client.rpc(
                "get_residence_gender_change_impact",
                {"p_new_gender": new_gender},
            ).execute(),
            is_write=False,
        )
        data = _extract_dict_payload(resp)
        if not isinstance(data, dict):
            raise RuntimeError("Could not read residence impact summary.")
        return dict(data)


def set_residence_gender(
    client: Client,
    new_gender: str,
    *,
    confirmation: str | None = None,
) -> dict:
    """Set or change residence_gender via ``set_residence_gender`` RPC."""
    with CLIENT_LOCK:
        resp = execute_network_call(
            lambda: client.rpc(
                "set_residence_gender",
                {"p_gender": new_gender, "p_confirmation": confirmation},
            ).execute(),
            is_write=True,
        )
        invalidate_residence_settings_cache(client)
        data = _extract_dict_payload(resp)
        if isinstance(data, dict):
            _store_residence_cache(
                client,
                {
                    "residence_name": str(data.get("residence_name") or DEFAULT_RESIDENCE_NAME).strip()
                    or DEFAULT_RESIDENCE_NAME,
                    "residence_gender": _normalize_residence_gender(data.get("residence_gender")),
                    "loaded": True,
                },
            )
            return dict(data)
        return {
            "residence_name": DEFAULT_RESIDENCE_NAME,
            "residence_gender": _normalize_residence_gender(new_gender),
        }


def set_residence_name(client: Client, residence_name: str) -> dict:
    """Update residence_name via ``set_residence_name`` RPC."""
    with CLIENT_LOCK:
        resp = execute_network_call(
            lambda: client.rpc(
                "set_residence_name",
                {"p_name": residence_name},
            ).execute(),
            is_write=True,
        )
        invalidate_residence_settings_cache(client)
        data = _extract_dict_payload(resp)
        if isinstance(data, dict):
            _store_residence_cache(
                client,
                {
                    "residence_name": str(data.get("residence_name") or residence_name).strip()
                    or DEFAULT_RESIDENCE_NAME,
                    "residence_gender": _normalize_residence_gender(data.get("residence_gender")),
                    "loaded": True,
                },
            )
            return dict(data)
        return {"residence_name": str(residence_name).strip()}


def has_gender_mismatch(
    residence_gender: str | None,
    *,
    student_gender: str | None = None,
    roster_gender: str | None = None,
) -> bool:
    """True when configured residence_gender differs from student or roster gender."""
    res_g = _normalize_residence_gender(residence_gender)
    if res_g is None:
        return False
    stu_g = _normalize_residence_gender(student_gender)
    if stu_g is not None and stu_g != res_g:
        return True
    ros_g = _normalize_residence_gender(roster_gender)
    if ros_g is not None and ros_g != res_g:
        return True
    return False

