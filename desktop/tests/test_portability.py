"""Portability, zero-prerequisite packaging helpers, TLS, and scaling tests."""

from __future__ import annotations

import logging
import os
import ssl
import sys
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import httpx
import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QWidget

from desktop import i18n
from desktop.app import config as config_mod
from desktop.app import logging_setup, timeouts, tls
from desktop.app.ui import resource
from desktop.app.ui.login_window import LoginWindow
from desktop.app.ui.main_window import MainWindow
from desktop.app.ui.tasks import human_error
from desktop.auth.session_store import SessionStore
from desktop.platform import win32_compat


_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


@pytest.fixture
def qapp():
    return _qapp


def test_unicode_and_spaces_profile_paths(tmp_path: Path, monkeypatch):
    profile = tmp_path / "Users" / "Aïcha Benali"
    roaming = profile / "AppData" / "Roaming"
    local = profile / "AppData" / "Local"
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.delenv("RESIVO_DATA_DIR", raising=False)
    monkeypatch.delenv("RESIVO_SESSION_DIR", raising=False)

    assert logging_setup.app_data_dir() == roaming / "RESIVO"
    log_dir = logging_setup.log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "test_unicode.log"
    log_file.write_text("éàç RÉSIVO\n", encoding="utf-8")
    assert "Aïcha Benali" not in log_file.read_text(encoding="utf-8")
    assert "éàç RÉSIVO" in log_file.read_text(encoding="utf-8")

    store = SessionStore()
    assert store.storage_dir == local / "RESIVO" / "session"
    saved = store.save(
        {
            "access_token": "tok_a",
            "refresh_token": "tok_r",
            "expires_at": 1893456000,
            "user_id": "uid_unicode",
        },
        remember=True,
    )
    assert saved is True
    assert store.session_file.is_file()
    payload, reason = store.load()
    assert reason is None
    assert payload is not None and payload["user_id"] == "uid_unicode"
    store.clear()


def test_cwd_independence_for_resources_and_i18n(tmp_path: Path, monkeypatch):
    unrelated = tmp_path / "arbitrary cwd folder"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)

    assert resource.get_asset_path("brand/resivo.ico").is_file()
    assert (resource.get_asset_path("fonts") / "Outfit-Bold.ttf").is_file()
    assert (resource.get_i18n_dir() / "en.json").is_file()
    assert (resource.get_i18n_dir() / "fr.json").is_file()

    i18n.init("fr")
    assert i18n.t("portability.config_error_title") == "RÉSIVO — Erreur de configuration"
    i18n.init("en")
    assert i18n.t("portability.config_error_title") == "RÉSIVO — Configuration error"


def test_frozen_meipass_resource_and_tls_lookup(tmp_path: Path, monkeypatch):
    exe_dir = tmp_path / "RÉSIVO Install"
    meipass = exe_dir / "_internal"
    (meipass / "assets" / "brand").mkdir(parents=True)
    (meipass / "assets" / "fonts").mkdir(parents=True)
    (meipass / "i18n").mkdir(parents=True)
    (meipass / "translations").mkdir(parents=True)
    (meipass / "certifi").mkdir(parents=True)

    (meipass / "assets" / "brand" / "resivo.ico").write_bytes(b"ico")
    (meipass / "assets" / "fonts" / "Outfit-Bold.ttf").write_bytes(b"ttf")
    (meipass / "i18n" / "en.json").write_text("{}", encoding="utf-8")
    (meipass / "i18n" / "fr.json").write_text("{}", encoding="utf-8")
    (meipass / "translations" / "qtbase_fr.qm").write_bytes(b"qm")
    (meipass / "certifi" / "cacert.pem").write_text("pem", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "RESIVO.exe"))
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

    assert resource.get_asset_path("brand/resivo.ico") == meipass / "assets" / "brand" / "resivo.ico"
    assert resource.get_asset_path("fonts") == meipass / "assets" / "fonts"
    assert resource.get_i18n_dir() == meipass / "i18n"
    assert resource.get_qt_translations_dir() == meipass / "translations"
    assert tls.ca_bundle_path() == meipass / "certifi" / "cacert.pem"


def test_tls_bundle_proxy_and_clock_skew_classification(monkeypatch):
    bundle = tls.ca_bundle_path()
    assert bundle is not None and bundle.is_file()

    ctx = tls.create_ssl_context()
    assert isinstance(ctx, ssl.SSLContext)

    # Ensure proxy password redaction in summary
    monkeypatch.setattr(
        "desktop.app.tls.urllib.request.getproxies",
        lambda: {"https": "http://user:secretpass@proxy.univ-tlemcen.dz:8080"},
    )
    proxies = tls.system_proxy_summary()
    assert proxies["https"] == "http://proxy.univ-tlemcen.dz:8080"
    assert "secretpass" not in str(proxies)

    # Clock skew SSL verification error produces clear guidance
    clock_err = httpx.ConnectError(
        "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate is not yet valid"
    )
    is_tls, clock_likely = tls.classify_tls_error(clock_err)
    assert is_tls is True
    assert clock_likely is True

    with pytest.raises(timeouts.TlsCertificateError) as exc_info:
        timeouts.execute_network_call(lambda: (_ for _ in ()).throw(clock_err), is_write=False)
    assert "system date" in human_error(exc_info.value).lower()


def test_config_error_codes_and_localized_messages(monkeypatch):
    monkeypatch.setattr(config_mod, "SUPABASE_URL", "")
    monkeypatch.setattr(config_mod, "SUPABASE_ANON_KEY", "secret-val")
    assert config_mod.config_error_code() == "missing_url"
    i18n.init("fr")
    assert "URL Supabase" in i18n.t("portability.config_missing_url")

    monkeypatch.setattr(config_mod, "SUPABASE_URL", "invalid-url")
    assert config_mod.config_error_code() == "invalid_url"
    assert "SUPABASE_URL" in i18n.t("portability.config_invalid_url")
    i18n.init("en")


def test_win32_compat_and_64bit_checks(qapp):
    assert win32_compat.is_64bit_process() is True
    assert win32_compat.is_64bit_os() is True
    ver = win32_compat.get_windows_version_info()
    assert ver["is_64bit_process"] is True
    dpi = win32_compat.get_dpi_info(qapp)
    assert "awareness" in dpi
    # Must never crash even if given an arbitrary AppUserModelID or fallback env
    assert isinstance(win32_compat.set_app_user_model_id("dz.dou.resivo.desktop"), bool)


def test_layout_does_not_clip_at_minimum_size(qapp, monkeypatch):
    monkeypatch.setattr("desktop.app.ui.main_window.current_role", lambda c: "staff")
    monkeypatch.setattr("desktop.app.ui.main_window.LiveSyncWorker.start", lambda self: None)
    monkeypatch.setattr("desktop.app.ui.pages.settings.McpHealthWorker.start", lambda self: None)
    for page_cls in (
        "OverviewPage", "PendingPage", "ResidentsPage", "RoomsPage",
        "MaintenancePage", "RoomChangesPage", "OfficialListPage", "SettingsPage",
    ):
        monkeypatch.setattr(f"desktop.app.ui.main_window.{page_cls}", lambda c: QWidget())

    mw = MainWindow(object())
    mw.resize(QSize(980, 640))
    mw.show()
    qapp.processEvents()
    assert mw.width() >= 980
    assert mw.height() >= 640
    assert mw.minimumSizeHint().width() <= 980
    assert mw.minimumSizeHint().height() <= 640
    assert mw.sidebar_widget.x() >= 0
    assert mw.sidebar_widget.x() + mw.sidebar_widget.width() <= mw.width()
    mw.close()

    lw = LoginWindow()
    lw.resize(QSize(380, 480))
    lw.show()
    qapp.processEvents()
    assert lw.minimumSizeHint().width() <= 380
    assert lw.minimumSizeHint().height() <= 480
    assert lw.button.x() + lw.button.width() <= lw.width()
    lw.resize(QSize(940, 580))
    qapp.processEvents()
    assert lw.hero.isVisible() is True
    lw.close()
    qapp.processEvents()
