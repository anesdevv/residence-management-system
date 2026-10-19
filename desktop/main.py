import sys
from pathlib import Path

# Ensure desktop folder is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
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
    app = QApplication(sys.argv)
    app.setApplicationName("RÉSIVO")
    load_fonts()  # bundled Outfit/Inter; must run after the QApplication exists
    if _BRAND_ICON.is_file():
        app.setWindowIcon(QIcon(str(_BRAND_ICON)))
    window = LoginWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
