"""Authentication and session management for RÉSIVO desktop console."""

from .session_store import (
    FakeBackend,
    SessionManager,
    SessionStore,
    WindowsBackend,
    get_remember_session_setting,
    session_manager,
    set_remember_session_setting,
)

__all__ = [
    "FakeBackend",
    "SessionManager",
    "SessionStore",
    "WindowsBackend",
    "get_remember_session_setting",
    "session_manager",
    "set_remember_session_setting",
]
