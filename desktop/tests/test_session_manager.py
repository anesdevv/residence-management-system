"""Tests for SessionManager coordinating client token persistence, auto-refresh, and restore."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import pytest

from desktop.app.timeouts import NetworkError, NetworkTimeoutError
from desktop.auth.session_store import (
    FakeBackend,
    SessionManager,
    SessionStore,
)


class MockAuth:
    def __init__(self):
        self._in_memory_session: SimpleNamespace | None = None
        self._on_change_callbacks: list[Callable] = []
        self.set_session_calls: list[tuple[str, str]] = []
        self.set_session_error: Exception | None = None

    def on_auth_state_change(self, callback: Callable):
        self._on_change_callbacks.append(callback)
        return SimpleNamespace(unsubscribe=lambda: None)

    def trigger_event(self, event: str, session: Any = None):
        for cb in self._on_change_callbacks:
            cb(event, session)

    def set_session(self, access_token: str, refresh_token: str):
        self.set_session_calls.append((access_token, refresh_token))
        if self.set_session_error:
            raise self.set_session_error
        self._in_memory_session = SimpleNamespace(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=1900000000,
            user=SimpleNamespace(id="usr_restored"),
        )
        return SimpleNamespace(session=self._in_memory_session)

    def get_session(self):
        return self._in_memory_session


class MockClient:
    def __init__(self):
        self.auth = MockAuth()


@pytest.fixture
def fake_backend():
    return FakeBackend(logon_session_id="0:5555", boot_epoch=1700000000)


@pytest.fixture
def session_manager(tmp_path: Path, fake_backend):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    return SessionManager(store=store)


def test_save_current_session(session_manager):
    client = MockClient()
    client.auth._in_memory_session = SimpleNamespace(
        access_token="tok_initial_access",
        refresh_token="tok_initial_refresh",
        expires_at=1800000000,
        user=SimpleNamespace(id="usr_current"),
    )

    # Save with remember=True
    saved = session_manager.save_current_session(client, remember=True)
    assert saved is True
    assert session_manager.store.session_file.exists()

    payload, reason = session_manager.store.load()
    assert reason is None
    assert payload is not None
    assert payload["access_token"] == "tok_initial_access"
    assert payload["refresh_token"] == "tok_initial_refresh"

    # Save with remember=False wipes store
    saved_off = session_manager.save_current_session(client, remember=False)
    assert saved_off is False
    assert not session_manager.store.session_file.exists()


def test_try_restore_success(session_manager):
    client = MockClient()
    # Save a valid session in store first
    session_manager.store.save(
        {
            "access_token": "tok_to_restore_acc",
            "refresh_token": "tok_to_restore_ref",
            "expires_at": 1800000000,
            "user_id": "usr_restore_1",
        },
        remember=True,
    )

    success, reason = session_manager.try_restore(client)
    assert success is True
    assert reason is None
    assert len(client.auth.set_session_calls) == 1
    assert client.auth.set_session_calls[0] == ("tok_to_restore_acc", "tok_to_restore_ref")


def test_try_restore_no_session(session_manager):
    client = MockClient()
    success, reason = session_manager.try_restore(client)
    assert success is False
    assert reason is None  # no file present


def test_try_restore_auth_error_clears_store(session_manager):
    client = MockClient()
    session_manager.store.save(
        {
            "access_token": "tok_bad_acc",
            "refresh_token": "tok_bad_ref",
            "expires_at": 1800000000,
            "user_id": "usr_bad",
        },
        remember=True,
    )

    # Auth error: invalid refresh token or account disabled
    client.auth.set_session_error = Exception("Invalid Refresh Token: Refresh Token Not Found")

    success, reason = session_manager.try_restore(client)
    assert success is False
    assert reason == "expired"
    # Store must be cleared!
    assert not session_manager.store.session_file.exists()


def test_try_restore_network_error_preserves_store(session_manager):
    client = MockClient()
    session_manager.store.save(
        {
            "access_token": "tok_net_acc",
            "refresh_token": "tok_net_ref",
            "expires_at": 1800000000,
            "user_id": "usr_net",
        },
        remember=True,
    )

    # Network / timeout error
    client.auth.set_session_error = NetworkTimeoutError("Connection timed out to Supabase auth")

    success, reason = session_manager.try_restore(client)
    assert success is False
    assert reason == "network"
    # Store must NOT be cleared on network failure!
    assert session_manager.store.session_file.exists()


def test_attach_client_updates_persisted_on_token_refreshed(session_manager):
    client = MockClient()
    session_manager.store.save(
        {
            "access_token": "tok_old_acc",
            "refresh_token": "tok_old_ref",
            "expires_at": 1800000000,
            "user_id": "usr_listen",
        },
        remember=True,
    )

    session_manager.attach_client(client)
    assert len(client.auth._on_change_callbacks) == 1

    # Simulate Supabase auth background token refresh
    new_session = SimpleNamespace(
        access_token="tok_refreshed_acc_NEW",
        refresh_token="tok_refreshed_ref_NEW",
        expires_at=1850000000,
        user=SimpleNamespace(id="usr_listen"),
    )
    client.auth.trigger_event("TOKEN_REFRESHED", new_session)

    # Persisted session file must immediately contain the newest tokens
    payload, reason = session_manager.store.load()
    assert reason is None
    assert payload is not None
    assert payload["access_token"] == "tok_refreshed_acc_NEW"
    assert payload["refresh_token"] == "tok_refreshed_ref_NEW"


def test_clear_wipes_store_and_client(session_manager):
    client = MockClient()
    session_manager.attach_client(client)
    session_manager.store.save(
        {
            "access_token": "tok_c_acc",
            "refresh_token": "tok_c_ref",
            "expires_at": 1800000000,
            "user_id": "usr_c",
        },
        remember=True,
    )

    session_manager.clear()
    assert not session_manager.store.session_file.exists()
    assert session_manager._client is None
