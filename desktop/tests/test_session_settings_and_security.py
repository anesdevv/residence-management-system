"""Unit and integration tests for Phase 3: Security, Settings hygiene, and Documentation.

Covers:
1. SettingsPage Security & Sign-in card (remember checkbox, clear on off, save on on,
   account label with email & role, sign-out button signal).
2. MainWindow connection to SettingsPage.sign_out_requested.
3. LoginWindow session discard banners (reboot, logon_changed, expired, normal launch).
4. Clean diagnostic logging (zero tokens, zero passwords, zero emails).
5. i18n catalog parity for session & security keys.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from desktop.app.config import SESSION_ENTROPY
from desktop.app.ui.login_window import LoginWindow
from desktop.app.ui.main_window import MainWindow
from desktop.app.ui.pages.settings import SettingsPage, _role_label
from desktop.auth.session_store import (
    FakeBackend,
    SessionManager,
    SessionStore,
    get_remember_session_setting,
    set_remember_session_setting,
)
from desktop.i18n import t

_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


@pytest.fixture
def qapp():
    return _qapp


@pytest.fixture(autouse=True)
def reset_remember_setting():
    orig = get_remember_session_setting()
    yield
    set_remember_session_setting(orig)


# ---------------------------------------------------------------------------
# Mocks
# ---------------------------------------------------------------------------
class MockAuth:
    def __init__(self, email="staff@univ-tlemcen.dz", user_id="usr_123"):
        self.user = SimpleNamespace(id=user_id, email=email)
        self._in_memory_session = SimpleNamespace(
            access_token="secret_access_jwt_value_12345",
            refresh_token="secret_refresh_token_value_67890",
            expires_at=int(time.time() + 3600),
            user=self.user,
        )
        self._callbacks: list[Callable] = []

    def on_auth_state_change(self, callback: Callable):
        self._callbacks.append(callback)
        return SimpleNamespace(unsubscribe=lambda: None)

    def get_session(self):
        return self._in_memory_session

    def get_user(self):
        return SimpleNamespace(user=self.user)

    def set_session(self, access_token: str, refresh_token: str):
        self._in_memory_session = SimpleNamespace(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=int(time.time() + 3600),
            user=self.user,
        )
        return SimpleNamespace(session=self._in_memory_session)

    def sign_out(self):
        self._in_memory_session = None


class MockClient:
    def __init__(self, email="staff@univ-tlemcen.dz", role="admin"):
        self.auth = MockAuth(email=email)
        self.role_value = role

    def rpc(self, name: str, params: dict | None = None):
        return SimpleNamespace(execute=lambda: SimpleNamespace(data={}))

    def table(self, name: str):
        mock_builder = MagicMock()
        mock_builder.select.return_value = mock_builder
        mock_builder.eq.return_value = mock_builder
        mock_builder.order.return_value = mock_builder
        mock_builder.limit.return_value = mock_builder
        mock_builder.single.return_value = mock_builder
        if name == "profiles":
            mock_builder.execute.return_value = SimpleNamespace(data=[{"role": self.role_value}])
        else:
            mock_builder.execute.return_value = SimpleNamespace(data=[])
        return mock_builder


# ---------------------------------------------------------------------------
# Tests: SettingsPage Security & Sign-in Card
# ---------------------------------------------------------------------------
def test_settings_security_card_controls_and_binding(qapp, tmp_path, monkeypatch):
    backend = FakeBackend()
    store = SessionStore(backend=backend, storage_dir=tmp_path)
    mgr = SessionManager(store=store)

    # Patch global session_manager in settings
    import desktop.app.ui.pages.settings as settings_mod
    monkeypatch.setattr(settings_mod, "session_manager", mgr)

    set_remember_session_setting(True)
    client = MockClient(email="admin@univ-tlemcen.dz", role="admin")

    page = SettingsPage(client)
    assert hasattr(page, "security_card"), "SettingsPage must have a security_card"
    assert hasattr(page, "remember_session_checkbox")
    assert hasattr(page, "remember_session_helper")
    assert hasattr(page, "signed_in_label")
    assert hasattr(page, "security_sign_out_btn")

    # Checkbox reflects current setting
    assert page.remember_session_checkbox.isChecked() is True

    # Account label contains email and role
    label_text = page.signed_in_label.text()
    assert "admin@univ-tlemcen.dz" in label_text
    assert t("roles.admin") in label_text or "Admin" in label_text

    # Helper copy is exact
    expected_helper = t("settings.remember_session_helper")
    assert page.remember_session_helper.text() == expected_helper

    # Test toggling switch OFF -> clears session immediately
    mgr.save_current_session(client, remember=True)
    assert store.session_file.exists()

    page.remember_session_checkbox.setChecked(False)
    assert get_remember_session_setting() is False
    assert not store.session_file.exists()

    # Test toggling switch ON -> saves current session immediately
    page.remember_session_checkbox.setChecked(True)
    assert get_remember_session_setting() is True
    assert store.session_file.exists()


def test_settings_page_sign_out_signal(qapp):
    client = MockClient(email="staff@univ-tlemcen.dz", role="staff")
    page = SettingsPage(client)

    received_signal = []
    page.sign_out_requested.connect(lambda: received_signal.append(True))

    page.security_sign_out_btn.click()
    assert len(received_signal) == 1


def test_settings_page_role_update_updates_label(qapp):
    client = MockClient(email="staff@univ-tlemcen.dz", role="staff")
    page = SettingsPage(client)

    assert "staff@univ-tlemcen.dz" in page.signed_in_label.text()
    assert _role_label("staff") in page.signed_in_label.text()

    # Change role to admin
    page.set_role("admin")
    assert _role_label("admin") in page.signed_in_label.text()


def test_main_window_connects_settings_sign_out(qapp, monkeypatch):
    client = MockClient(email="admin@univ-tlemcen.dz", role="admin")

    window = MainWindow(client, role="admin")
    assert hasattr(window, "settings_page")

    # Verify that sign_out_requested is connected by triggering it and checking shutdown sequence
    sign_out_called = []
    monkeypatch.setattr(window, "on_sign_out_clicked", lambda: sign_out_called.append(True))

    window.settings_page.sign_out_requested.emit()
    assert len(sign_out_called) == 1
    window.close()


# ---------------------------------------------------------------------------
# Tests: LoginWindow Session Discard Banners
# ---------------------------------------------------------------------------
def test_login_window_banner_reboot_reason(qapp):
    window = LoginWindow(reason="reboot")
    window.show()
    assert window.error_banner.isVisible() is True
    assert window.error_banner._kind == "info"
    assert window.error_banner._message.text() == t("login.session_rebooted")
    window.close()


def test_login_window_banner_logon_changed_reason(qapp):
    window = LoginWindow(reason="logon_changed")
    window.show()
    assert window.error_banner.isVisible() is True
    assert window.error_banner._kind == "info"
    assert window.error_banner._message.text() == t("login.session_rebooted")
    window.close()


def test_login_window_banner_expired_reason(qapp):
    window = LoginWindow(reason="expired")
    window.show()
    assert window.error_banner.isVisible() is True
    assert window.error_banner._kind == "warning"
    assert window.error_banner._message.text() == t("login.session_expired")
    window.close()


def test_login_window_banner_normal_launch_no_banner(qapp):
    window = LoginWindow(reason=None)
    window.show()
    assert window.error_banner.isVisible() is False
    window.close()


# ---------------------------------------------------------------------------
# Tests: Clean Diagnostic Logging (Zero Passwords, Zero Tokens, Zero Emails)
# ---------------------------------------------------------------------------
def test_diagnostic_logging_clean_and_token_free(caplog, tmp_path):
    backend = FakeBackend(logon_session_id="0:5555", boot_epoch=1700000000)
    store = SessionStore(backend=backend, storage_dir=tmp_path)
    mgr = SessionManager(store=store)

    secret_access = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sensitive_payload"
    secret_refresh = "refresh_token_very_sensitive_99999"
    secret_email = "sensitive_staff@univ-tlemcen.dz"

    client = MockClient(email=secret_email, role="staff")
    client.auth._in_memory_session.access_token = secret_access
    client.auth._in_memory_session.refresh_token = secret_refresh

    # 1. Save session
    mgr.save_current_session(client, remember=True)

    # 2. Test session restored
    with caplog.at_level(logging.INFO, logger="resivo.auth"):
        caplog.clear()
        success, reason = mgr.try_restore(client)
        assert success is True
        messages = [r.getMessage() for r in caplog.records]
        assert any("session restored" in m for m in messages)

        # Verify privacy: zero secrets
        for r in caplog.records:
            msg = r.getMessage()
            assert secret_access not in msg
            assert secret_refresh not in msg
            assert secret_email not in msg

    # 3. Test logon changed
    backend.logon_session_id = "0:9999"
    with caplog.at_level(logging.INFO, logger="resivo.auth"):
        caplog.clear()
        payload, reason = store.load()
        assert reason == "logon_changed"
        messages = [r.getMessage() for r in caplog.records]
        assert any("session discarded: logon session changed" in m for m in messages)

    # Resave for reboot check
    mgr.save_current_session(client, remember=True)
    backend.logon_session_id = None
    backend.boot_epoch = 1700500000  # >300s drift
    with caplog.at_level(logging.INFO, logger="resivo.auth"):
        caplog.clear()
        payload, reason = store.load()
        assert reason == "rebooted"
        messages = [r.getMessage() for r in caplog.records]
        assert any("session discarded: reboot detected" in m for m in messages)

    # 4. Test expired check
    backend.boot_epoch = 1700000000
    mgr.save_current_session(client, remember=True)
    # Tamper created_at to 10 days ago
    unprot = backend.unprotect(store.session_file.read_bytes(), SESSION_ENTROPY)
    data = json.loads(unprot.decode("utf-8"))
    data["created_at"] = time.time() - (86400 * 10)
    store.session_file.write_bytes(backend.protect(json.dumps(data).encode("utf-8"), SESSION_ENTROPY))

    with caplog.at_level(logging.INFO, logger="resivo.auth"):
        caplog.clear()
        payload, reason = store.load()
        assert reason == "expired"
        messages = [r.getMessage() for r in caplog.records]
        assert any("session discarded: expired" in m for m in messages)

    # 5. Test refresh rejected
    backend.logon_session_id = "0:5555"
    backend.boot_epoch = 1700000000
    mgr.save_current_session(client, remember=True)

    def reject_auth(*args, **kwargs):
        raise RuntimeError("Invalid Refresh Token: Token revoked")

    client.auth.set_session = reject_auth
    with caplog.at_level(logging.INFO, logger="resivo.auth"):
        caplog.clear()
        success, reason = mgr.try_restore(client)
        assert success is False
        assert reason == "expired"
        messages = [r.getMessage() for r in caplog.records]
        assert any("session discarded: refresh rejected" in m for m in messages)

    # 6. Test network error during restore
    mgr.save_current_session(client, remember=True)

    def network_fail(*args, **kwargs):
        raise OSError("Connection timed out")

    client.auth.set_session = network_fail
    with caplog.at_level(logging.WARNING, logger="resivo.auth"):
        caplog.clear()
        success, reason = mgr.try_restore(client)
        assert success is False
        assert reason == "network"
        messages = [r.getMessage() for r in caplog.records]
        assert any("network error during restore" in m for m in messages)


# ---------------------------------------------------------------------------
# Tests: i18n Catalogs Parity for Session & Security Keys
# ---------------------------------------------------------------------------
def test_i18n_session_and_security_keys_parity():
    i18n_dir = Path(__file__).resolve().parents[1] / "i18n"
    with open(i18n_dir / "en.json", "r", encoding="utf-8") as f:
        en = json.load(f)
    with open(i18n_dir / "fr.json", "r", encoding="utf-8") as f:
        fr = json.load(f)

    required_settings_keys = [
        "security_title",
        "security_subtitle",
        "remember_session_label",
        "remember_session_helper",
        "signed_in_as",
        "security_sign_out",
    ]

    for k in required_settings_keys:
        assert k in en.get("settings", {}), f"Missing key in en.json settings: {k}"
        assert k in fr.get("settings", {}), f"Missing key in fr.json settings: {k}"
        assert en["settings"][k], f"Empty key in en.json settings: {k}"
        assert fr["settings"][k], f"Empty key in fr.json settings: {k}"

    required_login_keys = [
        "remember_session",
        "restoring_session",
        "session_rebooted",
        "session_expired",
    ]

    for k in required_login_keys:
        assert k in en.get("login", {}), f"Missing key in en.json login: {k}"
        assert k in fr.get("login", {}), f"Missing key in fr.json login: {k}"
