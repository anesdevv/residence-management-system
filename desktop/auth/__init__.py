"""Authentication and session management for RÉSIVO desktop console."""

from .session_store import (
    FakeBackend,
    SessionManager,
    SessionStore,
    WindowsBackend,
)

__all__ = [
    "FakeBackend",
    "SessionManager",
    "SessionStore",
    "WindowsBackend",
]
