"""Non-interactive readiness self-test runner (``RESIVO.exe --selftest``)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import email.utils
import logging
import os
from pathlib import Path
import socket
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request
import uuid

from PySide6.QtCore import QLibraryInfo
from PySide6.QtWidgets import QMessageBox

try:
    from desktop.app import config as config_mod
    from desktop.app.logging_setup import app_data_dir, log_dir, log_path
    from desktop.app.tls import ca_bundle_path, classify_tls_error, create_ssl_context, urlopen_with_tls
    from desktop.app.ui.resource import get_i18n_dir, get_qt_translations_dir
    from desktop.app.ui.theme import load_fonts
    from desktop.auth.session_store import default_session_dir
    from desktop.platform import win32_compat
except ImportError:  # pragma: no cover - direct package import fallback
    from app import config as config_mod
    from app.logging_setup import app_data_dir, log_dir, log_path
    from app.tls import ca_bundle_path, classify_tls_error, create_ssl_context, urlopen_with_tls
    from app.ui.resource import get_i18n_dir, get_qt_translations_dir
    from app.ui.theme import load_fonts
    from auth.session_store import default_session_dir
    from platform import win32_compat

try:
    from i18n import current_language, t
except ImportError:
    from desktop.i18n import current_language, t

_log = logging.getLogger("resivo.selftest")


@dataclass(frozen=True)
class SelfTestCheck:
    key: str
    label: str
    passed: bool
    detail: str


def _probe_writable_dir(target: Path) -> tuple[bool, str]:
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / f".resivo_probe_{uuid.uuid4().hex}.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True, str(target)
    except OSError as exc:
        return False, f"{target}: {exc.__class__.__name__}"


def _locate_qt_plugins_root() -> Path | None:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "_internal" / "PySide6" / "plugins")
        candidates.append(exe_dir / "PySide6" / "plugins")
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "PySide6" / "plugins")
    try:
        qlib_plugins = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
        if qlib_plugins:
            candidates.append(Path(qlib_plugins))
    except Exception:
        pass
    for c in candidates:
        if c.is_dir() and (c / "platforms").is_dir():
            return c
    return None


def _check_network_and_clock(supabase_url: str, timeout_s: float = 5.0) -> tuple[SelfTestCheck, SelfTestCheck]:
    parsed = urllib.parse.urlparse((supabase_url or "").strip())
    host = parsed.hostname or ""
    if not host:
        return (
            SelfTestCheck("network", t("portability.selftest_check_network"), False, "No Supabase hostname configured"),
            SelfTestCheck("clock", t("portability.selftest_check_clock"), False, "Skipped (missing hostname)"),
        )

    dns_ok = False
    try:
        socket.getaddrinfo(host, parsed.port or 443)
        dns_ok = True
    except OSError as exc:
        return (
            SelfTestCheck("network", t("portability.selftest_check_network"), False, f"DNS failed for {host}: {exc}"),
            _check_local_clock_fallback(None),
        )

    endpoint = f"{parsed.scheme}://{parsed.netloc}/rest/v1/"
    server_dt: datetime | None = None
    try:
        req = urllib.request.Request(endpoint, method="HEAD", headers={"User-Agent": "RESIVO-Selftest/1.0"})
        with urlopen_with_tls(req, timeout=timeout_s) as resp:
            date_hdr = resp.headers.get("Date") if hasattr(resp, "headers") else None
            if date_hdr:
                server_dt = email.utils.parsedate_to_datetime(date_hdr)
            net_check = SelfTestCheck(
                "network",
                t("portability.selftest_check_network"),
                True,
                f"DNS OK & HTTPS HTTP {getattr(resp, 'status', 200)} ({host})",
            )
    except urllib.error.HTTPError as http_err:
        # 401 Unauthorized from PostgREST without apikey confirms TLS + Supabase reachability!
        if hasattr(http_err, "headers") and http_err.headers:
            date_hdr = http_err.headers.get("Date")
            if date_hdr:
                try:
                    server_dt = email.utils.parsedate_to_datetime(date_hdr)
                except Exception:
                    server_dt = None
        reachable = 200 <= int(getattr(http_err, "code", 0)) < 500
        net_check = SelfTestCheck(
            "network",
            t("portability.selftest_check_network"),
            reachable,
            f"DNS OK & HTTPS HTTP {http_err.code} ({host})",
        )
    except Exception as exc:  # noqa: BLE001
        is_tls, clock_skew = classify_tls_error(exc)
        reason = (
            "TLS certificate/clock validation error"
            if is_tls and clock_skew
            else f"TLS error: {exc.__class__.__name__}"
            if is_tls
            else f"Unreachable ({exc.__class__.__name__})"
        )
        net_check = SelfTestCheck(
            "network",
            t("portability.selftest_check_network"),
            False,
            f"DNS={'OK' if dns_ok else 'FAIL'}, HTTPS failed: {reason}",
        )

    clock_check = _check_local_clock_fallback(server_dt)
    return net_check, clock_check


def _check_local_clock_fallback(server_dt: datetime | None) -> SelfTestCheck:
    now_utc = datetime.now(timezone.utc)
    if server_dt is not None:
        if server_dt.tzinfo is None:
            server_dt = server_dt.replace(tzinfo=timezone.utc)
        drift_s = abs((now_utc - server_dt.astimezone(timezone.utc)).total_seconds())
        passed = drift_s <= 300.0
        return SelfTestCheck(
            "clock",
            t("portability.selftest_check_clock"),
            passed,
            f"Local UTC={now_utc:%Y-%m-%d %H:%M:%S}, server drift={drift_s:.0f}s (limit 300s)",
        )
    # Fallback when offline: ensure clock is not stuck near epoch / pre-2025
    sane = now_utc.year >= 2025
    return SelfTestCheck(
        "clock",
        t("portability.selftest_check_clock"),
        sane,
        f"Local UTC={now_utc:%Y-%m-%d %H:%M:%S} (offline sanity check)",
    )


def run_selftest(app: Any = None, *, timeout_s: float = 5.0) -> list[SelfTestCheck]:
    """Execute all zero-prerequisite readiness checks without logging secrets or PII."""
    checks: list[SelfTestCheck] = []

    # 1. Config check
    cfg_code = config_mod.config_error_code()
    cfg_host = urllib.parse.urlparse(config_mod.SUPABASE_URL or "").netloc or "(none)"
    checks.append(
        SelfTestCheck(
            "config",
            t("portability.selftest_check_config"),
            cfg_code is None,
            f"source={config_mod.config_source()}, host={cfg_host}" if cfg_code is None else f"error={cfg_code}",
        )
    )

    # 2. Writable per-user directories
    ok_logs, log_detail = _probe_writable_dir(log_dir())
    ok_sess, sess_detail = _probe_writable_dir(default_session_dir())
    checks.append(
        SelfTestCheck(
            "writable",
            t("portability.selftest_check_writable"),
            ok_logs and ok_sess,
            f"logs={log_detail}; session={sess_detail}",
        )
    )

    # 3. Fonts + translations
    families = load_fonts()
    fonts_ok = all(f in families for f in ("Outfit", "Inter"))
    i18n_dir = get_i18n_dir()
    i18n_ok = (i18n_dir / "en.json").is_file() and (i18n_dir / "fr.json").is_file()
    qt_trans_dir = get_qt_translations_dir(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    qm_ok = qt_trans_dir is not None and (qt_trans_dir / "qtbase_fr.qm").is_file()
    checks.append(
        SelfTestCheck(
            "fonts_i18n",
            t("portability.selftest_check_fonts_i18n"),
            fonts_ok and i18n_ok and qm_ok,
            f"fonts={families}, lang={current_language()}, qtbase_fr={qm_ok}",
        )
    )

    # 4. Qt plugins check
    plugins_root = _locate_qt_plugins_root()
    missing_plugins: list[str] = []
    if plugins_root is None:
        missing_plugins.append("plugins root missing")
    else:
        for req_plugin in (
            Path("platforms") / "qwindows.dll",
            Path("styles") / "qmodernwindowsstyle.dll",
            Path("imageformats") / "qico.dll",
            Path("iconengines") / "qsvgicon.dll",
            Path("tls") / "qschannelbackend.dll",
        ):
            if sys.platform == "win32" and not (plugins_root / req_plugin).is_file():
                missing_plugins.append(str(req_plugin))
    platform_name = app.platformName() if app is not None and hasattr(app, "platformName") else "unknown"
    checks.append(
        SelfTestCheck(
            "qt_plugins",
            t("portability.selftest_check_qt_plugins"),
            not missing_plugins,
            f"platform={platform_name}, missing={missing_plugins or 'none'}",
        )
    )

    # 5. Certifi CA bundle
    bundle = ca_bundle_path()
    ca_ok = False
    if bundle is not None and bundle.is_file():
        try:
            create_ssl_context()
            ca_ok = True
        except Exception:
            ca_ok = False
    checks.append(
        SelfTestCheck(
            "ca_bundle",
            t("portability.selftest_check_ca_bundle"),
            ca_ok,
            str(bundle) if bundle is not None else "missing cacert.pem",
        )
    )

    # 6 & 7. Network reachability + clock skew
    net_check, clock_check = _check_network_and_clock(config_mod.SUPABASE_URL, timeout_s=timeout_s)
    checks.append(net_check)
    checks.append(clock_check)

    # 8. DPI & 64-bit runtime check
    dpi_info = win32_compat.get_dpi_info(app)
    is_64 = win32_compat.is_64bit_process()
    checks.append(
        SelfTestCheck(
            "dpi",
            t("portability.selftest_check_dpi"),
            is_64,
            f"64bit={is_64}, awareness={dpi_info.get('awareness')}, scale={dpi_info.get('scale_percent')}%",
        )
    )

    for item in checks:
        tag = "PASS" if item.passed else "FAIL"
        _log.info("[SELFTEST] [%s] %s — %s", tag, item.key, item.detail)

    return checks


def format_selftest_report(checks: list[SelfTestCheck]) -> str:
    """Format a safe PASS/FAIL summary for logs and message boxes."""
    lines: list[str] = []
    for item in checks:
        tag = "PASS" if item.passed else "FAIL"
        lines.append(f"[{tag}] {item.label}: {item.detail}")
    return "\n".join(lines)


def execute_selftest_cli(app: Any) -> int:
    """Run checks, write results to app.log, display UI box unless quiet, and return exit code."""
    checks = run_selftest(app=app)
    total = len(checks)
    failed = sum(1 for c in checks if not c.passed)
    passed = total - failed

    summary = (
        t("portability.selftest_passed_summary", passed=passed)
        if failed == 0
        else t("portability.selftest_failed_summary", failed=failed, total=total)
    )
    report = format_selftest_report(checks)
    hint = t("portability.log_file_hint", path=str(log_path()))
    full_text = f"{summary}\n\n{report}\n\n{hint}"

    _log.info("[SELFTEST] Summary: %d/%d passed (%d failed)", passed, total, failed)
    if os.environ.get("RESIVO_SELFTEST_QUIET", "").strip() not in ("1", "true", "yes"):
        box = QMessageBox()
        box.setWindowTitle(t("portability.selftest_title"))
        box.setIcon(QMessageBox.Icon.Information if failed == 0 else QMessageBox.Icon.Warning)
        box.setText(summary)
        box.setInformativeText(f"{report}\n\n{hint}")
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    return 0 if failed == 0 else 1
