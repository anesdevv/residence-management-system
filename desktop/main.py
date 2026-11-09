import logging
from pathlib import Path
import sys

# Ensure desktop folder and repository root are on sys.path
_desktop_dir = Path(__file__).resolve().parent
if str(_desktop_dir) not in sys.path:
    sys.path.insert(0, str(_desktop_dir))
if str(_desktop_dir.parent) not in sys.path:
    sys.path.insert(0, str(_desktop_dir.parent))

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMessageBox
from app.config import config_error
from app.logging_setup import (
    SafeApplication,
    app_data_dir,
    install_exception_hooks,
    log_path,
    setup_logging,
)
from app.ui.login_window import LoginWindow
from app.ui.theme import load_fonts

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

    start_minimized = is_autostart and autostart.get_start_minimized_setting()
    window = LoginWindow(start_minimized=start_minimized)
    if start_minimized:
        window.showMinimized()
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
