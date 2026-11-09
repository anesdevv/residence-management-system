"""Session persistence infrastructure for RÉSIVO desktop console.

Provides Windows DPAPI-encrypted credential storage tied to the Windows logon
session (or boot epoch fallback) with automatic token refresh synchronization
and secure wipe on revocation or reboot.
"""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import inspect
import json
import logging
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

try:
    from PySide6.QtCore import QCoreApplication, QObject, QSettings, QTimer, Signal, Slot
except ImportError:
    QCoreApplication = None  # type: ignore[assignment]
    QObject = None  # type: ignore[assignment,misc]
    QSettings = None  # type: ignore[assignment,misc]
    QTimer = None  # type: ignore[assignment]
    Signal = None  # type: ignore[assignment]
    Slot = None  # type: ignore[assignment]

from desktop.app.config import SESSION_ENTROPY, SESSION_MAX_AGE_SECONDS
from desktop.app.timeouts import (
    NetworkError,
    NetworkTimeoutError,
    is_connection_error,
    is_timeout_exception,
)

if sys.platform == "win32":
    from ctypes import wintypes

_log = logging.getLogger("resivo.auth")

# ---------------------------------------------------------------------------
# Windows API structures & functions (ctypes)
# ---------------------------------------------------------------------------
CRYPTPROTECT_UI_FORBIDDEN = 0x01
TOKEN_QUERY = 0x0008
TOKEN_STATISTICS_CLASS = 10

if sys.platform == "win32":

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]

    class LUID(ctypes.Structure):
        _fields_ = [
            ("LowPart", wintypes.DWORD),
            ("HighPart", wintypes.LONG),
        ]

    class TOKEN_STATISTICS(ctypes.Structure):
        _fields_ = [
            ("TokenId", LUID),
            ("AuthenticationId", LUID),
            ("ExpirationTime", ctypes.c_int64),
            ("TokenType", wintypes.DWORD),
            ("ImpersonationLevel", wintypes.DWORD),
            ("DynamicCharged", wintypes.DWORD),
            ("DynamicAvailable", wintypes.DWORD),
            ("GroupCount", wintypes.DWORD),
            ("PrivilegeCount", wintypes.DWORD),
            ("ModifiedId", LUID),
        ]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    advapi32 = ctypes.windll.advapi32

    # Set 64-bit safe function signatures
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetTickCount64.restype = ctypes.c_uint64
    kernel32.GetTickCount64.argtypes = []

    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL

    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL

    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL

    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
else:
    DATA_BLOB = None  # type: ignore[assignment,misc]
    LUID = None  # type: ignore[assignment,misc]
    TOKEN_STATISTICS = None  # type: ignore[assignment,misc]
    crypt32 = None  # type: ignore[assignment]
    kernel32 = None  # type: ignore[assignment]
    advapi32 = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Backend Implementations
# ---------------------------------------------------------------------------
class WindowsBackend:
    """Windows DPAPI backend leveraging CryptProtectData and LUID logon sessions."""

    def is_supported(self) -> bool:
        return sys.platform == "win32"

    def protect(self, data: bytes, entropy: bytes = b"") -> bytes:
        if not self.is_supported():
            raise RuntimeError("Windows DPAPI is only supported on win32.")
        if not data:
            return b""

        in_buf = (ctypes.c_byte * len(data)).from_buffer_copy(data)
        in_blob = DATA_BLOB(len(data), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_byte)))

        if entropy:
            ent_buf = (ctypes.c_byte * len(entropy)).from_buffer_copy(entropy)
            ent_blob = DATA_BLOB(len(entropy), ctypes.cast(ent_buf, ctypes.POINTER(ctypes.c_byte)))
            p_ent = ctypes.byref(ent_blob)
        else:
            p_ent = None

        out_blob = DATA_BLOB()
        res = crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            None,
            p_ent,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        )
        if not res:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)

    def unprotect(self, cipher: bytes, entropy: bytes = b"") -> bytes:
        if not self.is_supported():
            raise RuntimeError("Windows DPAPI is only supported on win32.")
        if not cipher:
            raise ValueError("Ciphertext is empty")

        in_buf = (ctypes.c_byte * len(cipher)).from_buffer_copy(cipher)
        in_blob = DATA_BLOB(len(cipher), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_byte)))

        if entropy:
            ent_buf = (ctypes.c_byte * len(entropy)).from_buffer_copy(entropy)
            ent_blob = DATA_BLOB(len(entropy), ctypes.cast(ent_buf, ctypes.POINTER(ctypes.c_byte)))
            p_ent = ctypes.byref(ent_blob)
        else:
            p_ent = None

        out_blob = DATA_BLOB()
        res = crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            p_ent,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        )
        if not res:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)

    def get_logon_session_id(self) -> str | None:
        if not self.is_supported():
            return None
        try:
            h_process = kernel32.GetCurrentProcess()
            h_token = wintypes.HANDLE()
            if not advapi32.OpenProcessToken(h_process, TOKEN_QUERY, ctypes.byref(h_token)):
                return None
            try:
                stats = TOKEN_STATISTICS()
                ret_len = wintypes.DWORD()
                if not advapi32.GetTokenInformation(
                    h_token,
                    TOKEN_STATISTICS_CLASS,
                    ctypes.byref(stats),
                    ctypes.sizeof(stats),
                    ctypes.byref(ret_len),
                ):
                    return None
                return f"{stats.AuthenticationId.HighPart:x}:{stats.AuthenticationId.LowPart:x}"
            finally:
                kernel32.CloseHandle(h_token)
        except Exception:
            return None

    def get_boot_epoch(self) -> int | None:
        if not self.is_supported():
            return None
        try:
            uptime_ms = kernel32.GetTickCount64()
            return int(time.time() - (uptime_ms / 1000.0))
        except Exception:
            return None


class FakeBackend:
    """Pure Python reversible obfuscation for non-Windows platforms and unit testing.

    Completely scrambles plaintext so tokens, passwords, and sensitive strings
    never appear in raw disk storage.
    """

    def __init__(
        self,
        logon_session_id: str | None = "0:12345",
        boot_epoch: int | None = 1700000000,
        is_supported_override: bool = True,
    ):
        self.logon_session_id = logon_session_id
        self.boot_epoch = boot_epoch
        self.is_supported_override = is_supported_override

    def is_supported(self) -> bool:
        return self.is_supported_override

    @staticmethod
    def _keystream(entropy: bytes, length: int) -> bytes:
        blocks: list[bytes] = []
        counter = 0
        while sum(len(b) for b in blocks) < length:
            blocks.append(hashlib.sha256(entropy + counter.to_bytes(4, "big")).digest())
            counter += 1
        return b"".join(blocks)[:length]

    def protect(self, data: bytes, entropy: bytes = b"") -> bytes:
        if not data:
            return b""
        ks = self._keystream(entropy, len(data))
        cipher = bytes(b ^ k for b, k in zip(data, ks))
        tag = hmac.new(entropy, cipher, hashlib.sha256).digest()
        return b"FAKEDPAPI:" + tag + cipher

    def unprotect(self, cipher: bytes, entropy: bytes = b"") -> bytes:
        if not cipher or not cipher.startswith(b"FAKEDPAPI:") or len(cipher) < 42:
            raise ValueError("Invalid or corrupted ciphertext")
        tag = cipher[10:42]
        body = cipher[42:]
        expected_tag = hmac.new(entropy, body, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError("Decryption failed: integrity check failed")
        ks = self._keystream(entropy, len(body))
        return bytes(b ^ k for b, k in zip(body, ks))

    def get_logon_session_id(self) -> str | None:
        return self.logon_session_id

    def get_boot_epoch(self) -> int | None:
        return self.boot_epoch


# ---------------------------------------------------------------------------
# QSettings Helpers for Session Persistence
# ---------------------------------------------------------------------------
_MEMORY_SETTINGS: dict[str, Any] = {}


def get_remember_session_setting() -> bool:
    """Read the remember-session setting from QSettings (default: True)."""
    if QSettings is None:
        return _MEMORY_SETTINGS.get("security/remember_session", True)
    settings = QSettings("RESIVO", "StaffConsole")
    val = settings.value("security/remember_session", True, type=bool)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() not in ("false", "0", "no")
    return bool(val)


def set_remember_session_setting(enabled: bool) -> None:
    """Write the remember-session setting to QSettings."""
    val = bool(enabled)
    if QSettings is None:
        _MEMORY_SETTINGS["security/remember_session"] = val
        return
    settings = QSettings("RESIVO", "StaffConsole")
    settings.setValue("security/remember_session", val)


def _invoke_on_main_thread(fn: Callable) -> None:
    try:
        if QCoreApplication is not None and QTimer is not None:
            app = QCoreApplication.instance()
            if app is not None and threading.current_thread() is not threading.main_thread():
                QTimer.singleShot(0, fn)
                return
    except Exception:
        pass
    fn()


def _dispatch_on_done(callback: Callable, success: bool, reason: str) -> None:
    try:
        sig = inspect.signature(callback)
        params = [
            p
            for p in sig.parameters.values()
            if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values())
        if has_varargs or len(params) >= 2:
            callback(success, reason)
        elif len(params) == 1:
            callback(reason if not success else "success")
        else:
            callback()
    except Exception:
        try:
            callback(success, reason)
        except TypeError:
            callback(reason if not success else "success")


if QObject is not None and Signal is not None:

    class _RestoreBridge(QObject):
        done = Signal(bool, str)

        def __init__(self, callback: Callable):
            super().__init__()
            self._callback = callback
            self.done.connect(self._handle_done)

        @Slot(bool, str)
        def _handle_done(self, success: bool, reason: str):
            _dispatch_on_done(self._callback, success, reason)

else:

    class _RestoreBridge:  # type: ignore[no-redef]
        def __init__(self, callback: Callable):
            self._callback = callback

        def emit(self, success: bool, reason: str):
            _dispatch_on_done(self._callback, success, reason)


# ---------------------------------------------------------------------------
# Default Storage Directory Helper
# ---------------------------------------------------------------------------
def default_session_dir() -> Path:
    override = os.environ.get("RESIVO_SESSION_DIR")
    if override:
        return Path(override)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "RESIVO" / "session"
    app_data = os.environ.get("APPDATA")
    if app_data:
        return Path(app_data) / "RESIVO" / "session"
    return Path.home() / "AppData" / "Local" / "RESIVO" / "session"


# ---------------------------------------------------------------------------
# SessionStore Implementation
# ---------------------------------------------------------------------------
class SessionStore:
    """Thread-safe persistent store for encrypted staff authentication tokens."""

    def __init__(
        self,
        backend: Any = None,
        storage_dir: str | Path | None = None,
    ):
        if backend is not None:
            self.backend = backend
        elif sys.platform == "win32":
            self.backend = WindowsBackend()
        else:
            self.backend = FakeBackend()

        if storage_dir is not None:
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = default_session_dir()

        self.session_file = self.storage_dir / "session.bin"
        self._lock = threading.RLock()

    def is_supported(self) -> bool:
        return bool(self.backend.is_supported())

    def _cleanup_tmp(self) -> None:
        """Clean up stale temporary files left by interrupted atomic writes."""
        if not self.storage_dir.exists():
            return
        try:
            for tmp_file in self.storage_dir.glob("*.tmp"):
                try:
                    tmp_file.unlink(missing_ok=True)
                except OSError:
                    pass
        except OSError:
            pass

    def save(self, session_data: dict | Any, remember: bool = True) -> bool:
        """Atomically persist an encrypted session payload.

        If ``remember`` is False, any existing persisted session is wiped and
        cleared immediately.
        """
        with self._lock:
            if not remember:
                self.clear()
                return False

            if isinstance(session_data, dict):
                access_token = session_data.get("access_token")
                refresh_token = session_data.get("refresh_token")
                expires_at = session_data.get("expires_at")
                user = session_data.get("user")
                if isinstance(user, dict):
                    user_id = user.get("id")
                elif hasattr(user, "id"):
                    user_id = getattr(user, "id")
                else:
                    user_id = session_data.get("user_id")
            else:
                access_token = getattr(session_data, "access_token", None)
                refresh_token = getattr(session_data, "refresh_token", None)
                expires_at = getattr(session_data, "expires_at", None)
                user = getattr(session_data, "user", None)
                if isinstance(user, dict):
                    user_id = user.get("id")
                elif hasattr(user, "id"):
                    user_id = getattr(user, "id")
                else:
                    user_id = getattr(session_data, "user_id", None)

            if not access_token or not refresh_token:
                return False

            now = time.time()
            payload = {
                "schema_version": 1,
                "version": 1,
                "access_token": str(access_token),
                "refresh_token": str(refresh_token),
                "expires_at": int(expires_at) if expires_at is not None else None,
                "user_id": str(user_id) if user_id else None,
                "created_at": now,
                "last_refreshed_at": now,
                "logon_session_id": self.backend.get_logon_session_id(),
                "boot_epoch": self.backend.get_boot_epoch(),
            }

            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            cipher = self.backend.protect(data, SESSION_ENTROPY)

            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self._cleanup_tmp()

            tmp_path = self.storage_dir / f"session_{uuid.uuid4().hex}.tmp"
            try:
                with open(tmp_path, "wb") as f:
                    f.write(cipher)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.session_file)
            except Exception:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise

            _log.info("Persisted session securely (schema_version=%d).", payload["schema_version"])
            return True

    def load(self) -> tuple[dict | None, str | None]:
        """Load and validate the persisted session payload.

        Returns ``(payload, None)`` on valid session, or ``(None, discard_reason)``
        with the underlying file wiped and cleared on discard or absence.
        """
        with self._lock:
            if not self.session_file.exists():
                return None, None

            try:
                raw = self.session_file.read_bytes()
            except OSError:
                return None, None

            if not raw:
                self.clear()
                return None, "corrupt"

            try:
                unprotected = self.backend.unprotect(raw, SESSION_ENTROPY)
            except Exception:
                self.clear()
                return None, "decrypt_failed"

            try:
                payload = json.loads(unprotected.decode("utf-8"))
            except Exception:
                self.clear()
                return None, "corrupt"

            if not isinstance(payload, dict):
                self.clear()
                return None, "corrupt"

            if payload.get("schema_version") != 1 or payload.get("version") != 1:
                self.clear()
                return None, "corrupt"

            for field in ("access_token", "refresh_token", "user_id", "created_at"):
                val = payload.get(field)
                if val is None or val == "":
                    self.clear()
                    return None, "corrupt"

            # ---------------------------------------------------------------
            # Logon session ID & boot epoch validation
            # ---------------------------------------------------------------
            current_logon = self.backend.get_logon_session_id()
            if current_logon is not None:
                stored_logon = payload.get("logon_session_id")
                if stored_logon != current_logon:
                    self.clear()
                    return None, "logon_changed"
            else:
                current_boot = self.backend.get_boot_epoch()
                stored_boot = payload.get("boot_epoch")
                if current_boot is not None and stored_boot is not None:
                    try:
                        diff = abs(int(current_boot) - int(stored_boot))
                    except (ValueError, TypeError):
                        self.clear()
                        return None, "corrupt"
                    if diff > 300:
                        self.clear()
                        return None, "rebooted"
                else:
                    # FAIL CLOSED: cannot verify logon continuity
                    self.clear()
                    return None, "fail_closed"

            # ---------------------------------------------------------------
            # Max age expiration
            # ---------------------------------------------------------------
            created_at = payload.get("created_at")
            try:
                age = time.time() - float(created_at)
            except (ValueError, TypeError):
                self.clear()
                return None, "corrupt"

            if age > SESSION_MAX_AGE_SECONDS:
                self.clear()
                return None, "expired"

            return payload, None

    def clear(self) -> None:
        """Securely wipe the session file and remove any temporary write files."""
        with self._lock:
            if self.session_file.exists():
                try:
                    size = self.session_file.stat().st_size
                    if size > 0:
                        with open(self.session_file, "r+b") as f:
                            f.write(b"\x00" * size)
                            f.flush()
                            os.fsync(f.fileno())
                except OSError:
                    pass
                finally:
                    try:
                        self.session_file.unlink(missing_ok=True)
                    except OSError:
                        pass
            self._cleanup_tmp()


# ---------------------------------------------------------------------------
# SessionManager Implementation
# ---------------------------------------------------------------------------
class SessionManager:
    """Coordinates client session persistence, token refresh listening, and restore."""

    def __init__(self, store: SessionStore | None = None):
        self.store = store or SessionStore()
        self._client: Any = None
        self._auth_subscription: Any = None
        self._remember: bool = True

    def attach_client(self, client: Any) -> None:
        """Register listener on client auth state changes to synchronize token refresh."""
        self._client = client
        auth = getattr(client, "auth", None)
        if auth is not None and hasattr(auth, "on_auth_state_change"):
            try:
                self._auth_subscription = auth.on_auth_state_change(self._on_auth_state_change)
            except Exception as exc:
                _log.warning("Could not register on_auth_state_change: %s", exc)

    def _on_auth_state_change(self, event: Any, session: Any) -> None:
        """Update persisted session on token refresh events under lock."""
        event_str = str(event)
        if "TOKEN_REFRESHED" in event_str:
            with self.store._lock:
                if not (self._remember or self.store.session_file.exists()):
                    return
                target_session = session
                if target_session is None and self._client is not None:
                    auth = getattr(self._client, "auth", None)
                    target_session = getattr(auth, "_in_memory_session", None)
                if target_session is not None:
                    self.store.save(target_session, remember=True)

    def save_current_session(self, client: Any, remember: bool) -> bool:
        """Persist or wipe the current client session."""
        self._remember = remember
        if not remember:
            self.store.clear()
            return False

        auth = getattr(client, "auth", None)
        session = None
        if auth is not None:
            session = getattr(auth, "_in_memory_session", None)
            if session is None and hasattr(auth, "get_session"):
                try:
                    session = auth.get_session()
                except Exception:
                    session = None

        if session is None:
            return False
        return self.store.save(session, remember=remember)

    def try_restore(self, client: Any) -> tuple[bool, str | None]:
        """Attempt to restore the persisted session into the Supabase client.

        Returns ``(True, None)`` on success, ``(False, "network")`` on transient
        network error (preserving store), or ``(False, discard_reason)`` on
        terminal auth failure or reboot (clearing store).
        """
        payload, discard_reason = self.store.load()
        if not payload:
            if discard_reason in ("logon_changed", "rebooted"):
                discard_reason = "reboot"
            return False, discard_reason

        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")

        try:
            client.auth.set_session(access_token, refresh_token)
            self.attach_client(client)
            _log.info("Staff session restored successfully.")
            return True, None
        except Exception as exc:
            if is_timeout_exception(exc) or is_connection_error(exc) or isinstance(exc, (NetworkError, NetworkTimeoutError, OSError)):
                _log.warning("Session restoration paused due to network transport error: %s", exc.__class__.__name__)
                return False, "network"

            _log.info("Session restoration rejected by authentication server: %s", exc.__class__.__name__)
            self.store.clear()
            return False, "expired"

    def restore_session_async(
        self,
        client: Any,
        on_done: Callable,
        timeout_s: float = 10.0,
    ) -> threading.Thread:
        """Restore session off the Qt GUI thread without freezing the Qt event loop.

        Distinguishes reasons:
        - "success": restored and client attached
        - "reboot": Windows restarted or logon changed (store cleared)
        - "expired": Auth error (store cleared)
        - "network": Connection or timeout error (store preserved)
        - discard_reason or "no_session": any other case
        """
        completed = threading.Event()
        bridge = _RestoreBridge(on_done)

        def _worker():
            try:
                success, reason = self.try_restore(client)
            except Exception as exc:
                if is_timeout_exception(exc) or is_connection_error(exc) or isinstance(exc, (NetworkError, NetworkTimeoutError, OSError)):
                    success, reason = False, "network"
                else:
                    self.store.clear()
                    success, reason = False, "expired"

            if completed.is_set():
                return
            completed.set()

            final_reason = "success" if success else (reason or "no_session")
            if hasattr(bridge, "done"):
                bridge.done.emit(success, final_reason)
            else:
                bridge.emit(success, final_reason)

        def _watchdog():
            if not completed.wait(timeout=timeout_s):
                if not completed.is_set():
                    completed.set()
                    if hasattr(bridge, "done"):
                        bridge.done.emit(False, "network")
                    else:
                        bridge.emit(False, "network")

        worker_thread = threading.Thread(target=_worker, name="SessionRestoreWorker", daemon=True)
        watchdog_thread = threading.Thread(target=_watchdog, name="SessionRestoreWatchdog", daemon=True)
        worker_thread.start()
        watchdog_thread.start()
        return worker_thread

    def clear(self) -> None:
        """Wipe store and drop client references."""
        self._remember = False
        self.store.clear()
        self._client = None


# Module-level default SessionManager instance
session_manager = SessionManager()
