from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QFrame,
)
from ..client import make_client, sign_in, current_role
from .icons import get_pixmap, get_icon
from .theme import DESKTOP_STYLESHEET, apply_button_style


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Staff Login — Cité Universitaire Tlemcen")
        self.resize(440, 520)
        self.setStyleSheet(DESKTOP_STYLESHEET)
        self.client = make_client()

        # Main Centered Container Frame
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(20)

        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        card_layout.setContentsMargins(28, 28, 28, 28)

        # Crest & Header
        crest_lbl = QLabel()
        crest_lbl.setPixmap(get_pixmap("crest", size=42, color="#38bdf8"))
        crest_lbl.setAlignment(Qt.AlignCenter)

        title_lbl = QLabel("Residence Tlemcen")
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #f8fafc; letter-spacing: 0.4px; margin-top: 6px;")
        title_lbl.setAlignment(Qt.AlignCenter)

        subtitle_lbl = QLabel("Staff & Housing Operations Console")
        subtitle_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #94a3b8; margin-bottom: 8px;")
        subtitle_lbl.setAlignment(Qt.AlignCenter)

        card_layout.addWidget(crest_lbl)
        card_layout.addWidget(title_lbl)
        card_layout.addWidget(subtitle_lbl)

        # Form Inputs
        self.email = QLineEdit()
        self.email.setPlaceholderText("staff@univ-tlemcen.dz")
        self.email.setText("staff@residence.test")  # seeded staff account

        self.password = QLineEdit()
        self.password.setPlaceholderText("••••••••")
        self.password.setText("Staff1234!")  # seeded password convenience
        self.password.setEchoMode(QLineEdit.Password)
        self.password.returnPressed.connect(self.attempt)

        form = QFormLayout()
        form.setSpacing(12)
        form.addRow("Staff Email:", self.email)
        form.addRow("Password:", self.password)
        card_layout.addLayout(form)

        # Status Error Banner
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #f87171; font-size: 12px; font-weight: 600; padding: 4px;")
        card_layout.addWidget(self.status)

        # Login Action Button
        self.button = QPushButton("Sign In to Console")
        self.button.setFixedHeight(42)
        self.button.setIcon(get_icon("staff_accounts", size=16, color="#ffffff"))
        apply_button_style(self.button, "primary")
        self.button.clicked.connect(self.attempt)
        card_layout.addWidget(self.button)

        main_layout.addWidget(card)

        # Security Footer
        security_lbl = QLabel("Direction des Œuvres Universitaires • Tlemcen")
        security_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        security_lbl.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(security_lbl)

    def attempt(self):
        email_txt = self.email.text().strip()
        pwd_txt = self.password.text()

        if not email_txt or not pwd_txt:
            self.status.setText("Please enter both email and password.")
            return

        self.button.setText("Signing in...")
        self.button.setEnabled(False)

        try:
            sign_in(self.client, email_txt, pwd_txt)
            role = current_role(self.client)
            if role not in ("staff", "admin"):
                self.client.auth.sign_out()
                self.status.setText("Access denied: Console restricted to staff and administrators.")
                self.button.setText("Sign In to Console")
                self.button.setEnabled(True)
                return
        except Exception as exc:  # noqa: BLE001
            self.status.setText(f"Login failed: {exc}")
            self.button.setText("Sign In to Console")
            self.button.setEnabled(True)
            return

        from .main_window import MainWindow
        self.window = MainWindow(self.client)
        self.window.show()
        self.close()
