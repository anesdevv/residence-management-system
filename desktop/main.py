import logging
import sys
from pathlib import Path

# Ensure desktop folder is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMessageBox
from app.config import config_error
from app.logging_setup import (
    SafeApplication,
    install_exception_hooks,
    log_path,
    setup_logging,
)
from app.ui.login_window import LoginWindow
from app.ui.theme import load_fonts

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
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("dz.dou.resivo.desktop")
        except Exception:  # pragma: no cover - non-fatal Windows shell API
            logging.getLogger("resivo").warning("Could not set process AppUserModelID")

    app = SafeApplication(sys.argv)
    install_exception_hooks()
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

    load_fonts()  # bundled Outfit/Inter; must run after the QApplication exists
    if _BRAND_ICON.is_file():
        app.setWindowIcon(QIcon(str(_BRAND_ICON)))
    window = LoginWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
