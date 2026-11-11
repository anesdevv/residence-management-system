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
    from desktop.app.config import config_error, config_error_code
    from desktop.app.selftest import execute_selftest_cli
    from desktop.app.startup_debug import (
        attach_first_paint_probe,
        install_ghost_window_probe,
        mark,
        reset_timeline,
    )
    from desktop.app.tls import configure_tls_environment
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
    from desktop.app.ui.resource import get_asset_path
    from desktop.app.ui.theme import apply_app_stylesheet, load_fonts
except ImportError:
    from app.client import RoleLookupError, make_client, remember_role, resolve_role
    from app.config import config_error, config_error_code
    from app.selftest import execute_selftest_cli
    from app.startup_debug import (
        attach_first_paint_probe,
        install_ghost_window_probe,
        mark,
        reset_timeline,
    )
    from app.tls import configure_tls_environment
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
    from app.ui.resource import get_asset_path
    from app.ui.theme import apply_app_stylesheet, load_fonts
from desktop.auth.session_store import (
    default_session_dir,
    get_remember_session_setting,
    session_manager,
)

try:
    from i18n import t
except ImportError:
    from desktop.i18n import t

try:
    from desktop.platform import autostart, win32_compat
except ImportError:
    from platform import autostart, win32_compat


def _resolve_brand_icon() -> Path:
    return get_asset_path("brand/resivo.ico")


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
    configure_tls_environment()

    # Ensure per-user writable directories exist (handles spaces & non-ASCII profiles).
    for _dir_fn in (app_data_dir, default_session_dir):
        try:
            _dir_fn().mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logging.getLogger("resivo").warning("Could not create per-user dir: %s", exc)

    is_autostart = "--autostart" in sys.argv
    is_selftest = "--selftest" in sys.argv

    # Single-instance guard (QLockFile in per-user AppData location)
    lock_file = None
    if not is_selftest:
        lock_path = app_data_dir() / "resivo.lock"
        lock_file, exit_code = autostart.acquire_single_instance(
            lock_path, is_autostart=is_autostart
        )
        if exit_code is not None:
            return exit_code

    win32_compat.set_app_user_model_id("dz.dou.resivo.desktop")

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
    if _BRAND_ICON.is_file():
        app.setWindowIcon(QIcon(str(_BRAND_ICON)))

    if is_selftest:
        return execute_selftest_cli(app)

    # Validate before the login window: a broken deployment gets one clear
    # message in the active app language (no key material).
    err_code = config_error_code()
    if err_code:
        error_en = config_error() or err_code
        logging.getLogger("resivo").error("Configuration error: %s", error_en)
        localized_msg = t(f"portability.config_{err_code}")
        hint = t("portability.log_file_hint", path=str(log_path()))
        QMessageBox.critical(
            None,
            t("portability.config_error_title"),
            f"{localized_msg}\n\n{hint}",
        )
        return 1

    # Moved EXE: on every normal launch, if the Run value exists and its path differs
    # from current EXE path, rewrite it. If value does not exist, do nothing.
    autostart.repair()

    load_fonts()  # bundled Outfit/Inter; must run after the QApplication exists
    apply_app_stylesheet()

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
    install_ghost_window_probe(app)
    reset_timeline("launch")
    mark("launch_application_start")
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

        if success:
            role, role_exc = role_result if role_result else (None, None)
            normalized_role = str(role).strip().lower() if role is not None else ""

            if normalized_role in ("staff", "admin"):
                remember_role(client, normalized_role)
                mark("restore_role_end")
                main_win = MainWindow(client, role=normalized_role)
                app._main_window = main_win
                attach_first_paint_probe(main_win)
                if start_minimized:
                    main_win.showMinimized()
                else:
                    main_win.show()
                    main_win.raise_()
                    main_win.activateWindow()
                mark("main_window_shown")
                if restoring_window is not None:
                    restoring_window.close()
            elif role_exc is not None or (role is None and role_exc is None and normalized_role == ""):
                mark("restore_role_end")
                main_win = MainWindow(client, role=None)
                app._main_window = main_win
                attach_first_paint_probe(main_win)
                if start_minimized:
                    main_win.showMinimized()
                else:
                    main_win.show()
                    main_win.raise_()
                    main_win.activateWindow()
                mark("main_window_shown")
                if restoring_window is not None:
                    restoring_window.close()
            else:
                if restoring_window is not None:
                    restoring_window.close()
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

        auth_log = logging.getLogger("resivo.auth")
        if success:
            auth_log.info("session restored")
        elif reason == "network":
            auth_log.warning("network error during restore")
        elif reason in ("reboot", "rebooted"):
            auth_log.info("session discarded: reboot detected")
        elif reason == "logon_changed":
            auth_log.info("session discarded: logon session changed")
        elif reason == "expired":
            auth_log.info("session discarded: expired")

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
