"""Tests for --selftest CLI diagnostics and tools/preflight.ps1."""

from __future__ import annotations

from datetime import datetime, timezone
import email.utils
import logging
import os
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from desktop import i18n
from desktop.app import selftest


_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


def test_selftest_passes_offline_mocked_https(tmp_path: Path, monkeypatch, caplog):
    monkeypatch.setenv("RESIVO_DATA_DIR", str(tmp_path / "roaming" / "RESIVO"))
    monkeypatch.setenv("RESIVO_SESSION_DIR", str(tmp_path / "local" / "RESIVO" / "session"))
    monkeypatch.setenv("RESIVO_SELFTEST_QUIET", "1")
    monkeypatch.setattr("desktop.app.selftest.socket.getaddrinfo", lambda h, p: [(None, None, None, None, ("127.0.0.1", 443))])

    class FakeResp:
        status = 200
        headers = {"Date": email.utils.format_datetime(datetime.now(timezone.utc))}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("desktop.app.selftest.urlopen_with_tls", lambda req, timeout=5.0: FakeResp())

    i18n.init("en")
    with caplog.at_level(logging.INFO, logger="resivo.selftest"):
        checks = selftest.run_selftest(app=_qapp, timeout_s=2.0)

    assert len(checks) == 8
    assert all(c.passed for c in checks), [c for c in checks if not c.passed]
    report = selftest.format_selftest_report(checks)
    assert "[PASS]" in report
    assert "SUPA" not in caplog.text or "eyJ" not in caplog.text

    rc = selftest.execute_selftest_cli(_qapp)
    assert rc == 0


def test_selftest_flags_clock_skew_and_shows_localized_dialog(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RESIVO_DATA_DIR", str(tmp_path / "roaming" / "RESIVO"))
    monkeypatch.setenv("RESIVO_SESSION_DIR", str(tmp_path / "local" / "RESIVO" / "session"))
    monkeypatch.delenv("RESIVO_SELFTEST_QUIET", raising=False)
    monkeypatch.setattr("desktop.app.selftest.socket.getaddrinfo", lambda h, p: [(None, None, None, None, ("127.0.0.1", 443))])

    skewed = datetime(2020, 1, 1, tzinfo=timezone.utc)

    class FakeResp:
        status = 200
        headers = {"Date": email.utils.format_datetime(skewed)}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("desktop.app.selftest.urlopen_with_tls", lambda req, timeout=5.0: FakeResp())

    seen_boxes = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: seen_boxes.append((self.windowTitle(), self.text())) or 0)

    i18n.init("fr")
    rc = selftest.execute_selftest_cli(_qapp)
    i18n.init("en")

    assert rc == 1
    assert len(seen_boxes) == 1
    title, text = seen_boxes[0]
    assert "Autotest" in title
    assert "échoué" in text


def test_preflight_script_exists_and_uses_powershell_51_only():
    root = Path(__file__).resolve().parents[2]
    ps1 = root / "tools" / "preflight.ps1"
    assert ps1.is_file()
    content = ps1.read_text(encoding="utf-8")
    assert not content.startswith("\ufeff\ufeff")
    assert "Zone.Identifier" in content
    assert "Is64BitOperatingSystem" in content
    assert "SUPABASE_ANON_KEY" not in content
    assert "SERVICE_ROLE" not in content
