from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QPushButton, QLabel, QVBoxLayout, QMessageBox,
)
from ..client import make_client, sign_in


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Staff Login — Residence Tlemcen")
        self.client = make_client()

        self.email = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)

        form = QFormLayout()
        form.addRow("Email", self.email)
        form.addRow("Password", self.password)

        self.button = QPushButton("Log in")
        self.button.clicked.connect(self.attempt)

        self.status = QLabel("")
        self.status.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.button)
        layout.addWidget(self.status)
        self.resize(380, 200)

    def attempt(self):
        try:
            sign_in(self.client, self.email.text().strip(), self.password.text())
        except Exception as exc:  # noqa: BLE001
            self.status.setText(f"Login failed: {exc}")
            return
        from .main_window import MainWindow
        self.window = MainWindow(self.client)
        self.window.show()
        self.close()
