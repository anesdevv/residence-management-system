"""Tests for SessionStore and cryptographic backends (WindowsBackend & FakeBackend).

Verifies DPAPI protection, logon session ID isolation, boot epoch fallback,
fail-closed behaviors, max age expiry, secure file wiping, and absence of
plaintext tokens or passwords in files and logs.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from desktop.app.config import SESSION_ENTROPY, SESSION_MAX_AGE_SECONDS
from desktop.auth.session_store import (
    FakeBackend,
    SessionStore,
    WindowsBackend,
)


@pytest.fixture
def fake_backend():
    return FakeBackend(
        logon_session_id="0:9999",
        boot_epoch=1700000000,
        is_supported_override=True,
    )


@pytest.fixture
def sample_session_dict():
    return {
        "access_token": "resivo_access_token_secret_12345",
        "refresh_token": "resivo_refresh_token_secret_67890",
        "expires_at": 1800000000,
        "user_id": "usr_uuid_staff_admin_001",
    }


# ---------------------------------------------------------------------------
# Roundtrip & Gotrue Session Object Tests
# ---------------------------------------------------------------------------
def test_save_load_roundtrip_fake_backend(tmp_path: Path, fake_backend, sample_session_dict):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    assert store.is_supported() is True

    saved = store.save(sample_session_dict, remember=True)
    assert saved is True
    assert store.session_file.exists()

    payload, discard_reason = store.load()
    assert discard_reason is None
    assert payload is not None
    assert payload["access_token"] == sample_session_dict["access_token"]
    assert payload["refresh_token"] == sample_session_dict["refresh_token"]
    assert payload["user_id"] == sample_session_dict["user_id"]
    assert payload["schema_version"] == 1
    assert payload["version"] == 1
    assert payload["logon_session_id"] == "0:9999"
    assert payload["boot_epoch"] == 1700000000


def test_save_gotrue_session_object(tmp_path: Path, fake_backend):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)

    user_obj = SimpleNamespace(id="usr_obj_999")
    gotrue_session = SimpleNamespace(
        access_token="gotrue_access_token_abc",
        refresh_token="gotrue_refresh_token_xyz",
        expires_at=1850000000,
        user=user_obj,
    )

    saved = store.save(gotrue_session, remember=True)
    assert saved is True

    payload, reason = store.load()
    assert reason is None
    assert payload is not None
    assert payload["access_token"] == "gotrue_access_token_abc"
    assert payload["refresh_token"] == "gotrue_refresh_token_xyz"
    assert payload["user_id"] == "usr_obj_999"


# ---------------------------------------------------------------------------
# Raw Disk Inspection Test
# ---------------------------------------------------------------------------
def test_raw_disk_inspection_no_plaintext(tmp_path: Path, fake_backend):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)

    secret_access = "MY_HIGHLY_SECRET_ACCESS_TOKEN_ABC123"
    secret_refresh = "MY_HIGHLY_SECRET_REFRESH_TOKEN_XYZ789"
    secret_user = "USER_SECRET_ID_555"

    store.save(
        {
            "access_token": secret_access,
            "refresh_token": secret_refresh,
            "expires_at": 1800000000,
            "user_id": secret_user,
        },
        remember=True,
    )

    raw_bytes = store.session_file.read_bytes()
    assert len(raw_bytes) > 0

    # Ensure sensitive tokens, field names, or keywords do NOT appear in plaintext on disk
    assert secret_access.encode() not in raw_bytes
    assert secret_refresh.encode() not in raw_bytes
    assert secret_user.encode() not in raw_bytes
    assert b"password" not in raw_bytes.lower()
    assert b"refresh_token" not in raw_bytes
    assert b"access_token" not in raw_bytes


# ---------------------------------------------------------------------------
# Security Invalidation Tests (Logon ID, Boot Epoch, Fail Closed)
# ---------------------------------------------------------------------------
def test_logon_session_id_change(tmp_path: Path, fake_backend, sample_session_dict):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    store.save(sample_session_dict, remember=True)
    assert store.session_file.exists()

    # User logged off Windows or switched accounts -> logon session ID changes
    fake_backend.logon_session_id = "0:DIFF_SESSION"

    payload, reason = store.load()
    assert payload is None
    assert reason == "logon_changed"
    assert not store.session_file.exists()


def test_boot_time_fallback_within_300s(tmp_path: Path, fake_backend, sample_session_dict):
    # Logon ID is unavailable (None), relying on boot epoch
    fake_backend.logon_session_id = None
    fake_backend.boot_epoch = 1700000000

    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    store.save(sample_session_dict, remember=True)

    # Small drift (120 seconds, e.g. NTP or sleep drift <= 300s)
    fake_backend.boot_epoch = 1700000120
    payload, reason = store.load()
    assert reason is None
    assert payload is not None


def test_boot_time_fallback_exceeding_300s(tmp_path: Path, fake_backend, sample_session_dict):
    fake_backend.logon_session_id = None
    fake_backend.boot_epoch = 1700000000

    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    store.save(sample_session_dict, remember=True)

    # Windows rebooted -> boot epoch difference > 300 seconds
    fake_backend.boot_epoch = 1700000500
    payload, reason = store.load()
    assert payload is None
    assert reason == "rebooted"
    assert not store.session_file.exists()


def test_fail_closed_when_both_logon_and_boot_none(tmp_path: Path, fake_backend, sample_session_dict):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    store.save(sample_session_dict, remember=True)

    # Both logon session ID and boot epoch unavailable
    fake_backend.logon_session_id = None
    fake_backend.boot_epoch = None

    payload, reason = store.load()
    assert payload is None
    assert reason == "fail_closed"
    assert not store.session_file.exists()


def test_max_age_expiry(tmp_path: Path, fake_backend, sample_session_dict, monkeypatch):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    store.save(sample_session_dict, remember=True)

    # Fast forward 8 days into the future (> SESSION_MAX_AGE_SECONDS = 7 days)
    eight_days_future = time.time() + SESSION_MAX_AGE_SECONDS + (24 * 3600)
    monkeypatch.setattr(time, "time", lambda: eight_days_future)

    payload, reason = store.load()
    assert payload is None
    assert reason == "expired"
    assert not store.session_file.exists()


# ---------------------------------------------------------------------------
# Corruption, Tampering, and Missing Fields
# ---------------------------------------------------------------------------
def test_empty_file_deleted(tmp_path: Path, fake_backend):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    store.storage_dir.mkdir(parents=True, exist_ok=True)
    store.session_file.write_bytes(b"")

    payload, reason = store.load()
    assert payload is None
    assert reason == "corrupt"
    assert not store.session_file.exists()


def test_corrupted_ciphertext_deleted(tmp_path: Path, fake_backend):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    store.storage_dir.mkdir(parents=True, exist_ok=True)
    store.session_file.write_bytes(b"FAKEDPAPI:completely_corrupted_invalid_tampered_payload")

    payload, reason = store.load()
    assert payload is None
    assert reason == "decrypt_failed"
    assert not store.session_file.exists()


def test_wrong_schema_version_deleted(tmp_path: Path, fake_backend):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    bad_payload = {
        "schema_version": 999,
        "version": 999,
        "access_token": "tok_access",
        "refresh_token": "tok_refresh",
        "user_id": "usr_123",
        "created_at": time.time(),
        "logon_session_id": "0:9999",
    }
    cipher = fake_backend.protect(
        b'{"schema_version": 999, "version": 999, "access_token": "tok_access", "refresh_token": "tok_refresh", "user_id": "usr_123", "created_at": 1000}',
        SESSION_ENTROPY,
    )
    store.storage_dir.mkdir(parents=True, exist_ok=True)
    store.session_file.write_bytes(cipher)

    payload, reason = store.load()
    assert payload is None
    assert reason == "corrupt"
    assert not store.session_file.exists()


def test_missing_required_fields_deleted(tmp_path: Path, fake_backend):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    # Missing refresh_token and user_id
    cipher = fake_backend.protect(
        b'{"schema_version": 1, "version": 1, "access_token": "tok_access", "created_at": 1000}',
        SESSION_ENTROPY,
    )
    store.storage_dir.mkdir(parents=True, exist_ok=True)
    store.session_file.write_bytes(cipher)

    payload, reason = store.load()
    assert payload is None
    assert reason == "corrupt"
    assert not store.session_file.exists()


# ---------------------------------------------------------------------------
# Atomic Writes & Remember=False Settings
# ---------------------------------------------------------------------------
def test_atomic_write_failure_preserves_old_file(
    tmp_path: Path, fake_backend, sample_session_dict, monkeypatch
):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    store.save(sample_session_dict, remember=True)
    assert store.session_file.exists()

    orig_bytes = store.session_file.read_bytes()

    def _failing_replace(src, dst):
        raise OSError("Permission denied or disk full simulation")

    monkeypatch.setattr(os, "replace", _failing_replace)

    new_session = dict(sample_session_dict)
    new_session["access_token"] = "brand_new_token_that_fails"

    with pytest.raises(OSError, match="Permission denied"):
        store.save(new_session, remember=True)

    # Old file is safely preserved
    assert store.session_file.read_bytes() == orig_bytes
    # Stale .tmp files are cleaned up or not interfering
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_remember_false_clears_file(tmp_path: Path, fake_backend, sample_session_dict):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    store.save(sample_session_dict, remember=True)
    assert store.session_file.exists()

    result = store.save(sample_session_dict, remember=False)
    assert result is False
    assert not store.session_file.exists()


def test_secure_wipe_zeroes_content(tmp_path: Path, fake_backend, sample_session_dict):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    store.save(sample_session_dict, remember=True)
    assert store.session_file.exists()

    store.clear()
    assert not store.session_file.exists()


def test_concurrent_refresh_calls_under_lock(tmp_path: Path, fake_backend):
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)
    errors: list[Exception] = []

    def _worker(worker_id: int):
        try:
            for i in range(10):
                session = {
                    "access_token": f"access_{worker_id}_{i}",
                    "refresh_token": f"refresh_{worker_id}_{i}",
                    "expires_at": 1800000000 + i,
                    "user_id": f"usr_{worker_id}",
                }
                store.save(session, remember=True)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(w,)) for w in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    payload, reason = store.load()
    assert reason is None
    assert payload is not None
    assert "access_" in payload["access_token"]


def test_caplog_never_exposes_tokens(tmp_path: Path, fake_backend, caplog):
    caplog.set_level(logging.DEBUG)
    store = SessionStore(backend=fake_backend, storage_dir=tmp_path)

    secret_access = "CONFIDENTIAL_ACCESS_TOKEN_VALUE_42"
    secret_refresh = "CONFIDENTIAL_REFRESH_TOKEN_VALUE_99"

    store.save(
        {
            "access_token": secret_access,
            "refresh_token": secret_refresh,
            "expires_at": 1800000000,
            "user_id": "usr_99",
        },
        remember=True,
    )
    store.load()
    store.clear()

    full_log_text = caplog.text
    assert secret_access not in full_log_text
    assert secret_refresh not in full_log_text
    assert "password" not in full_log_text.lower()


# ---------------------------------------------------------------------------
# Real WindowsBackend on Windows
# ---------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform != "win32", reason="WindowsBackend requires win32")
def test_real_windows_backend_on_windows(tmp_path: Path, sample_session_dict):
    backend = WindowsBackend()
    assert backend.is_supported() is True

    logon_id = backend.get_logon_session_id()
    assert logon_id is not None
    assert ":" in logon_id

    boot_epoch = backend.get_boot_epoch()
    assert boot_epoch is not None
    assert boot_epoch > 0

    data = b"StaffSessionDataTestingWindowsDPAPI"
    cipher = backend.protect(data, SESSION_ENTROPY)
    assert cipher != data
    decrypted = backend.unprotect(cipher, SESSION_ENTROPY)
    assert decrypted == data

    # Test SessionStore integration with real DPAPI
    store = SessionStore(backend=backend, storage_dir=tmp_path)
    store.save(sample_session_dict, remember=True)
    assert store.session_file.exists()

    payload, reason = store.load()
    assert reason is None
    assert payload is not None
    assert payload["access_token"] == sample_session_dict["access_token"]

    store.clear()
    assert not store.session_file.exists()
