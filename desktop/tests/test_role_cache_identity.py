"""Role-cache identity must come from the stored session, never get_session()."""

import json
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop.app.client import (
    forget_role,
    resolve_role,
    stored_user,
    stored_user_display_name,
    stored_user_email,
    stored_user_id,
)
from desktop.app.ui.diagnostics import _session_email as diagnostics_email
from desktop.app.ui.main_window import (
    _session_display_name,
    _session_email,
)
from desktop.app.ui.pages.overview import _staff_display_name


class _Query:
    def __init__(self, client):
        self.client = client

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, _column, _value):
        return self

    def single(self):
        return self

    def execute(self):
        self.client.profile_calls += 1
        return SimpleNamespace(data={"role": self.client.role})


class _Auth:
    """Real gotrue exposes _in_memory_session; get_session() must not run."""

    def __init__(self, user_id="user-1"):
        self._in_memory_session = SimpleNamespace(
            user=SimpleNamespace(id=user_id, email="staff@test.local")
        )
        self._persist_session = False
        self.get_session_calls = 0
        self.get_user_calls = 0

    def get_session(self):
        self.get_session_calls += 1
        raise AssertionError("get_session() performs a refresh and must not be called")

    def get_user(self):
        self.get_user_calls += 1
        return SimpleNamespace(user=self._in_memory_session.user)


class _Client:
    def __init__(self, role="admin", user_id="user-1"):
        self.role = role
        self.profile_calls = 0
        self.auth = _Auth(user_id)

    def table(self, name):
        assert name == "profiles"
        return _Query(self)


class _Storage(_Auth):
    def __init__(self, session):
        _Auth.__init__(self)
        self._in_memory_session = None
        self._persist_session = True
        self._storage_key = "sb-session"
        self._storage = _DictStorage(
            {
                "sb-session": json.dumps(
                    {"user": {"id": session[0], "email": session[1]}}
                )
            }
        )


class _DictStorage:
    def __init__(self, values):
        self.values = values

    def get_item(self, key):
        return self.values.get(key)


class _StorageClient:
    def __init__(self, session):
        self.auth = _Storage(session)
        self.profile_calls = 0
        self.role = "staff"

    def table(self, name):
        assert name == "profiles"
        return _Query(self)


def test_role_cache_reads_stored_session_without_token_refresh():
    client = _Client()
    try:
        assert resolve_role(client) == "admin"
        assert resolve_role(client) == "admin"
        assert client.auth.get_user_calls == 1
        assert client.profile_calls == 1
        assert client.auth.get_session_calls == 0
        assert stored_user_id(client) == "user-1"
    finally:
        forget_role(client)


def test_stored_session_identity_change_invalidates_role_cache():
    client = _Client()
    try:
        assert resolve_role(client) == "admin"
        client.auth._in_memory_session.user.id = "user-2"
        assert resolve_role(client) == "admin"
        assert client.auth.get_user_calls == 2
        assert client.auth.get_session_calls == 0
    finally:
        forget_role(client)


def test_stored_user_id_reads_persisted_json_without_refresh():
    client = _StorageClient(("user-9", "officer@test.local"))
    assert stored_user_id(client) == "user-9"
    assert client.auth.get_session_calls == 0


class _ProfileUser:
    def __init__(self):
        self.id = "user-7"
        self.email = "nadia.haddad@test.local"
        self.user_metadata = {"full_name": "Nadia Haddad"}


class _ProfileAuth(_Auth):
    def __init__(self):
        _Auth.__init__(self, "user-7")
        self._in_memory_session = SimpleNamespace(user=_ProfileUser())


class _ProfileClient:
    def __init__(self):
        self.auth = _ProfileAuth()

    def table(self, name):
        raise AssertionError("session reads must not query the database")


def test_stored_session_details_never_refresh_or_query():
    client = _ProfileClient()

    assert stored_user(client) is client.auth._in_memory_session.user
    assert stored_user_id(client) == "user-7"
    assert stored_user_email(client) == "nadia.haddad@test.local"
    assert stored_user_display_name(client) == "Nadia Haddad"
    assert stored_user_display_name(client, "Housing staff") == "Nadia Haddad"
    assert client.auth.get_session_calls == 0


def test_ui_session_labels_read_only_the_stored_session():
    """Shell, Overview and Diagnostics must not call get_session()."""
    client = _ProfileClient()

    assert _session_email(client) == "nadia.haddad@test.local"
    assert _session_display_name(client) == "Nadia Haddad"
    assert _staff_display_name(client) == "Nadia Haddad"
    assert diagnostics_email(client) == "nadia.haddad@test.local"
    assert client.auth.get_session_calls == 0


def test_stored_session_details_fall_back_without_a_session():
    client = _StorageClient(("user-9", "officer@test.local"))
    client.auth._storage.values["sb-session"] = None

    assert stored_user(client) is None
    assert stored_user_email(client) == ""
    assert stored_user_display_name(client, "Housing staff") == "Housing staff"
    assert client.auth.get_session_calls == 0


class _GetSessionOnlyAuth:
    """A non-gotrue adapter must not drag the app onto the refreshing path."""

    def __init__(self):
        self.get_session_calls = 0

    def get_session(self):
        self.get_session_calls += 1
        raise AssertionError("get_session() must never be used as a fallback")


class _GetSessionOnlyClient:
    def __init__(self):
        self.auth = _GetSessionOnlyAuth()

    def table(self, _name):
        raise AssertionError("session reads must not query the database")


def test_stored_session_does_not_fall_back_to_get_session():
    client = _GetSessionOnlyClient()

    assert stored_user(client) is None
    assert stored_user_id(client) is None
    assert stored_user_email(client) == ""
    assert stored_user_display_name(client, "Housing staff") == "Housing staff"
    assert client.auth.get_session_calls == 0
