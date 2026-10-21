import json
import logging
import re
import threading

from supabase import create_client, Client
from .config import SUPABASE_URL, SUPABASE_ANON_KEY

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
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def sign_in(client: Client, email: str, password: str):
    return client.auth.sign_in_with_password({"email": email, "password": password})


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
            response = client.auth.get_user()
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
            profile = (
                client.table("profiles")
                .select("role")
                .eq("id", user_id)
                .single()
                .execute()
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


def room_occupancy(client: Client, *, strict: bool = False) -> dict[str, int]:
    """Count occupied beds per room.

    The legacy pages treat a read failure as "no occupancy data" so their
    tables still render.  Callers that must not turn a failure into a fake zero
    pass ``strict=True`` to receive the exception instead.
    """
    with CLIENT_LOCK:
        try:
            resp = client.table("students").select("room_id").eq("status", "active").execute()
            counts: dict[str, int] = {}
            for row in resp.data or []:
                rid = row.get("room_id")
                if rid:
                    counts[rid] = counts.get(rid, 0) + 1
            return counts
        except Exception:
            if strict:
                raise
            return {}


def official_lookup(client: Client) -> dict[str, dict]:
    with CLIENT_LOCK:
        try:
            resp = client.table("official_residents").select("*").execute()
            return {r["card_id"]: r for r in (resp.data or []) if "card_id" in r}
        except Exception:
            return {}
