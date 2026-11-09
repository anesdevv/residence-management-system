from __future__ import annotations

import logging
from pathlib import Path
import sys
import threading
from typing import Any

# Ensure desktop folder and repository root are on sys.path
_desktop_dir = Path(__file__).resolve().parent
if str(_desktop_dir) not in sys.path:
    sys.path.insert(0, str(_desktop_dir))
if str(_desktop_dir.parent) not in sys.path:
    sys.path.insert(0, str(_desktop_dir.parent))

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMessageBox
try:
    from desktop.app.client import RoleLookupError, make_client, remember_role, resolve_role
    from desktop.app.config import config_error
    from desktop.app.logging_setup import (
        SafeApplication,
        app_data_dir,
        install_exception_hooks,
        log_path,
        setup_logging,
    )
    from desktop.app.timeouts import (
        NetworkError,
        NetworkTimeoutError,
        is_connection_error,
        is_timeout_exception,
    )
    from desktop.app.ui.login_window import LoginWindow
    from desktop.app.ui.main_window import MainWindow
    from desktop.app.ui.theme import load_fonts
except ImportError:
    from app.client import RoleLookupError, make_client, remember_role, resolve_role
    from app.config import config_error
    from app.logging_setup import (
        SafeApplication,
        app_data_dir,
        install_exception_hooks,
        log_path,
        setup_logging,
    )
    from app.timeouts import (
        NetworkError,
        NetworkTimeoutError,
        is_connection_error,
        is_timeout_exception,
    )
    from app.ui.login_window import LoginWindow
    from app.ui.main_window import MainWindow
    from app.ui.theme import load_fonts
from desktop.auth.session_store import (
    get_remember_session_setting,
    session_manager,
)

try:
    from i18n import t
except ImportError:
    from desktop.i18n import t

try:
    from desktop.platform import autostart
except ImportError:
    from platform import autostart


def _resolve_brand_icon() -> Path:
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "assets" / "brand" / "resivo.ico")
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "assets" / "brand" / "resivo.ico")
            candidates.append(Path(meipass) / "desktop" / "assets" / "brand" / "resivo.ico")
    candidates.append(Path(__file__).resolve().parent / "assets" / "brand" / "resivo.ico")
    for c in candidates:
        if c.is_file():
            return c
    return candidates[-1]


class _StartupBridge(QObject):
    restore_done = Signal(bool, str, object)

    def __init__(self, callback):
        super().__init__()
        self.restore_done.connect(callback)


_BRAND_ICON = _resolve_brand_icon()


def main() -> int:
    # Configure the file log before creating any widget: --noconsole builds
    # have no stderr, and startup failures must still be diagnosable.
    setup_logging()

    is_autostart = "--autostart" in sys.argv

    # Single-instance guard (QLockFile in per-user AppData location)
    lock_path = app_data_dir() / "resivo.lock"
    lock_file, exit_code = autostart.acquire_single_instance(
        lock_path, is_autostart=is_autostart
    )
    if exit_code is not None:
        return exit_code

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("dz.dou.resivo.desktop")
        except Exception:  # pragma: no cover - non-fatal Windows shell API
            logging.getLogger("resivo").warning("Could not set process AppUserModelID")

    app = SafeApplication(sys.argv)
    # Store lock_file on app instance so it remains locked until process termination
    app._instance_lock = lock_file
    install_exception_hooks()

    # Initialize localization (QSettings -> system locale -> English default)
    try:
        from i18n import init as init_i18n
        init_i18n(app=app)
    except Exception as e:
        logging.getLogger("resivo").warning("Could not initialize i18n: %s", e)

    app.setApplicationName("RÉSIVO")
    app.setApplicationDisplayName("RÉSIVO")
    app.setDesktopFileName("dz.dou.resivo.desktop")

    # Validate before the login window: a broken deployment gets one clear
    # message (no key material) instead of a misleading auth failure.
    error = config_error()
    if error:
        logging.getLogger("resivo").error("Configuration error: %s", error)
        QMessageBox.critical(
            None,
            "RÉSIVO — Configuration error",
            f"{error}\n\nLog file: {log_path()}",
        )
        return 1

    # Moved EXE: on every normal launch, if the Run value exists and its path differs
    # from current EXE path, rewrite it. If value does not exist, do nothing.
    autostart.repair()

    load_fonts()  # bundled Outfit/Inter; must run after the QApplication exists
    if _BRAND_ICON.is_file():
        app.setWindowIcon(QIcon(str(_BRAND_ICON)))

    return launch_application(
        app=app,
        is_autostart=is_autostart,
    )


def launch_application(
    app: SafeApplication,
    client: Any = None,
    session_manager_instance: Any = None,
    is_autostart: bool = False,
    exec_loop: bool = True,
) -> int:
    start_minimized = is_autostart and autostart.get_start_minimized_setting()
    if client is None:
        client = make_client()
    if session_manager_instance is None:
        session_manager_instance = session_manager

    remember = get_remember_session_setting()
    if not remember:
        session_manager_instance.clear()

    has_stored_session = session_manager_instance.store.session_file.exists()

    if not remember or not has_stored_session:
        window = LoginWindow(
            client=client,
            start_minimized=start_minimized,
            session_manager=session_manager_instance,
        )
        app._main_window = window
        if start_minimized:
            window.showMinimized()
        else:
            window.show()
        if exec_loop:
            return app.exec()
        return 0

    # Stored session exists and remember setting is True:
    # Run restore off-thread (keeping GUI event loop responsive).
    restoring_window: LoginWindow | None = None
    outcome_processed = False

    def _show_restoring_ui():
        nonlocal restoring_window
        if not outcome_processed:
            restoring_window = LoginWindow(
                client=client,
                start_minimized=start_minimized,
                session_manager=session_manager_instance,
            )
            restoring_window.button.setEnabled(False)
            restoring_window.button.setText(t("login.restoring_session"))
            restoring_window.email.setEnabled(False)
            restoring_window.password.setEnabled(False)
            if hasattr(restoring_window, "remember_checkbox"):
                restoring_window.remember_checkbox.setEnabled(False)
            if start_minimized:
                restoring_window.showMinimized()
            else:
                restoring_window.show()

    restore_timer = QTimer()
    restore_timer.setSingleShot(True)
    restore_timer.timeout.connect(_show_restoring_ui)
    restore_timer.start(400)

    def _on_restore_done(
        success: bool,
        reason: str,
        role_result: tuple[str | None, Exception | None] | None = None,
    ):
        nonlocal outcome_processed
        if outcome_processed:
            return
        outcome_processed = True
        restore_timer.stop()

        if restoring_window is not None:
            restoring_window.close()

        if success:
            role, role_exc = role_result if role_result else (None, None)
            normalized_role = str(role).strip().lower() if role is not None else ""

            if normalized_role in ("staff", "admin"):
                remember_role(client, normalized_role)
                main_win = MainWindow(client, role=normalized_role)
                app._main_window = main_win
                if start_minimized:
                    main_win.showMinimized()
                else:
                    main_win.show()
            elif role_exc is not None or (role is None and role_exc is None and normalized_role == ""):
                main_win = MainWindow(client, role=None)
                app._main_window = main_win
                if start_minimized:
                    main_win.showMinimized()
                else:
                    main_win.show()
            else:
                session_manager_instance.clear()
                login_win = LoginWindow(
                    client=client,
                    start_minimized=start_minimized,
                    session_manager=session_manager_instance,
                )
                login_win.show_error(t("login.access_denied"))
                app._main_window = login_win
                if start_minimized:
                    login_win.showMinimized()
                else:
                    login_win.show()
        else:
            if reason == "network":
                main_win = MainWindow(client, role=None)
                app._main_window = main_win
                if start_minimized:
                    main_win.showMinimized()
                else:
                    main_win.show()
            elif reason == "expired":
                session_manager_instance.clear()
                login_win = LoginWindow(
                    client=client,
                    start_minimized=start_minimized,
                    session_manager=session_manager_instance,
                    reason="expired",
                )
                app._main_window = login_win
                if start_minimized:
                    login_win.showMinimized()
                else:
                    login_win.show()
            elif reason in ("reboot", "logon_changed", "rebooted"):
                session_manager_instance.clear()
                login_win = LoginWindow(
                    client=client,
                    start_minimized=start_minimized,
                    session_manager=session_manager_instance,
                    reason="reboot",
                )
                app._main_window = login_win
                if start_minimized:
                    login_win.showMinimized()
                else:
                    login_win.show()
            else:
                session_manager_instance.clear()
                login_win = LoginWindow(
                    client=client,
                    start_minimized=start_minimized,
                    session_manager=session_manager_instance,
                )
                app._main_window = login_win
                if start_minimized:
                    login_win.showMinimized()
                else:
                    login_win.show()

    def _worker():
        try:
            success, reason = session_manager_instance.try_restore(client)
        except Exception as exc:
            if is_timeout_exception(exc) or is_connection_error(exc) or isinstance(exc, (NetworkError, NetworkTimeoutError, OSError)):
                success, reason = False, "network"
            else:
                session_manager_instance.clear()
                success, reason = False, "expired"

        role_result = None
        if success:
            try:
                resolved = resolve_role(client)
                role_result = (resolved, None)
            except RoleLookupError as exc:
                role_result = (None, exc)
            except Exception as exc:
                if is_timeout_exception(exc) or is_connection_error(exc) or isinstance(exc, (NetworkError, NetworkTimeoutError, OSError)):
                    role_result = (None, exc)
                else:
                    role_result = ("", None)

        bridge.restore_done.emit(success, reason, role_result)

    bridge = _StartupBridge(_on_restore_done)
    app._startup_bridge = bridge
    app._restore_timer = restore_timer
    worker_thread = threading.Thread(target=_worker, name="StartupRestoreWorker", daemon=True)
    worker_thread.start()
    app._startup_worker = worker_thread

    if exec_loop:
        return app.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
