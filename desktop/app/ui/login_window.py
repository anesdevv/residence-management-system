"""RÉSIVO — staff login window (split gradient hero + form; visual layer only).

Behaviour is frozen: the prefilled seeded staff credentials, the ``attempt()``
flow, ``sign_in`` / ``current_role`` usage, the exact "Access denied" path, the
window staying open on wrong credentials and the lazy ``MainWindow`` import.

Attributes kept for callers/tests: ``self.email``, ``self.password``,
``self.button``, ``self.status`` (the error banner's message label), the
``returnPressed`` connection on the password field and the 380x480 minimum.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from ..client import make_client, sign_in, current_role
from .components import BrandMark, Button, GradientHero, InlineBanner
from .theme import C, DESKTOP_STYLESHEET, S, apply_role

# DESIGN.md §7 — hide the hero below this window width (form-only mode).
_LOGIN_HERO_BREAKPOINT = 760
_FORM_MAX_WIDTH = 420
_BRAND_DIR = Path(__file__).resolve().parents[2] / "assets" / "brand"
_SIGN_IN_TEXT = "Sign in"


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Staff Login — RÉSIVO")
        self.setMinimumSize(380, 480)
        self.resize(940, 580)
        self.setStyleSheet(DESKTOP_STYLESHEET)
        self.client = make_client()
        icon_path = _BRAND_DIR / "resivo.ico"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.hero = self._build_hero()
        self.form_host, self.form_column = self._build_form()
        root.addWidget(self.hero, 1)
        root.addWidget(self.form_host, 1)

        self._apply_responsive_layout()

    # ---------------------------------------------------------------- building
    def _build_hero(self) -> GradientHero:
        """Left half: brand-gradient hero with the white logo and value line."""
        hero = GradientHero()
        hero.body.setContentsMargins(S("space-12"), S("space-12"), S("space-12"), S("space-8"))
        hero.body.setSpacing(S("space-4"))
        hero.body.addStretch(1)

        logo = BrandMark(variant="logo", color="white", size=96)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.body.addWidget(logo)

        headline = QLabel("Staff Console")
        apply_role(headline, "display")
        headline.setStyleSheet(f"color: {C('surface')};")
        headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.body.addWidget(headline)

        value_line = QLabel("Applications, rooms and repairs in one live console.")
        apply_role(value_line, "body")
        value_line.setStyleSheet(f"color: {C('text-on-dark')};")
        value_line.setWordWrap(True)
        value_line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.body.addWidget(value_line)

        hero.body.addStretch(1)

        caption = QLabel("Direction des Œuvres Universitaires · Cité Universitaire · Tlemcen")
        apply_role(caption, "small")
        caption.setStyleSheet(f"color: {C('text-on-dark-muted')};")
        caption.setWordWrap(True)
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.body.addWidget(caption)
        return hero

    def _build_form(self) -> tuple[QWidget, QWidget]:
        """Right half: clean form on ``surface`` (labels, fields, banner, CTA)."""
        host = QWidget()
        host.setProperty("background", "surface")
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(S("space-8"), S("space-8"), S("space-8"), S("space-8"))
        host_layout.setSpacing(0)
        host_layout.addStretch(1)

        column = QWidget()
        col = QVBoxLayout(column)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(S("space-3"))

        title = QLabel("RÉSIVO")
        apply_role(title, "h1")
        subtitle = QLabel("Staff & Housing Operations Console")
        apply_role(subtitle, "muted")
        col.addWidget(title)
        col.addWidget(subtitle)
        col.addSpacing(S("space-4"))

        email_label = QLabel("Staff email")
        apply_role(email_label, "small")
        self.email = QLineEdit()
        self.email.setPlaceholderText("staff@univ-tlemcen.dz")
        self.email.setMinimumHeight(S("size-control"))
        col.addWidget(email_label)
        col.addWidget(self.email)

        password_label = QLabel("Password")
        apply_role(password_label, "small")
        self.password = QLineEdit()
        self.password.setPlaceholderText("••••••••")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setMinimumHeight(S("size-control"))
        self.password.returnPressed.connect(self.attempt)
        col.addWidget(password_label)
        col.addWidget(self.password)

        # Failure banner — hidden until needed; ``self.status`` is its message
        # label so legacy ``self.status.setText(...)`` code keeps working.
        self.error_banner = InlineBanner(kind="error", message="")
        self.error_banner.setVisible(False)
        self.status = self.error_banner._message
        col.addWidget(self.error_banner)

        self.button = Button.primary(_SIGN_IN_TEXT, "log-in")
        self.button.setMinimumHeight(S("size-control"))
        self.button.clicked.connect(self.attempt)
        col.addWidget(self.button)

        host_layout.addWidget(column, 0, Qt.AlignmentFlag.AlignHCenter)
        host_layout.addStretch(1)
        return host, column

    # --------------------------------------------------------------- responsive
    def _apply_responsive_layout(self) -> None:
        """Hero hidden below 760 px (DESIGN.md §7); form centred, max ~420 px."""
        hero_visible = self.width() >= _LOGIN_HERO_BREAKPOINT
        self.hero.setVisible(hero_visible)
        available = self.width() if not hero_visible else self.width() // 2
        width = max(280, min(_FORM_MAX_WIDTH, available - 2 * S("space-8")))
        self.form_column.setFixedWidth(width)

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if hasattr(self, "hero"):
            self._apply_responsive_layout()

    # ------------------------------------------------------------------- flow
    def _show_error(self, message: str) -> None:
        self.error_banner.set_message(message)
        self.error_banner.setVisible(True)

    def attempt(self):
        email_txt = self.email.text().strip()
        pwd_txt = self.password.text()

        if not email_txt or not pwd_txt:
            self._show_error("Please enter both email and password.")
            return

        self.button.setText("Signing in...")
        self.button.setEnabled(False)

        try:
            sign_in(self.client, email_txt, pwd_txt)
            role = current_role(self.client)
            if role not in ("staff", "admin"):
                self.client.auth.sign_out()
                self._show_error("Access denied: Console restricted to staff and administrators.")
                self.button.setText(_SIGN_IN_TEXT)
                self.button.setEnabled(True)
                return
        except Exception as exc:  # noqa: BLE001
            self._show_error(f"Login failed: {exc}")
            self.button.setText(_SIGN_IN_TEXT)
            self.button.setEnabled(True)
            return

        from .main_window import MainWindow
        self.window = MainWindow(self.client)
        self.window.show()
        self.close()
