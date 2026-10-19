import sys
from pathlib import Path

# Ensure desktop folder is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from app.ui.login_window import LoginWindow
from app.ui.theme import load_fonts

_BRAND_ICON = Path(__file__).resolve().parent / "assets" / "brand" / "resivo.ico"


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
