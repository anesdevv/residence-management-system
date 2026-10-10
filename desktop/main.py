import sys
from PySide6.QtWidgets import QApplication
from app.ui.login_window import LoginWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
