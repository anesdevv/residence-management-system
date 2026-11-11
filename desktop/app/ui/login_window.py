"""RÉSIVO — staff login window (split gradient hero + form; visual layer only).

Behaviour: the seeded credentials, the ``attempt()`` flow, ``sign_in`` /
``resolve_role`` usage, the exact "Access denied" path, the window staying open
on wrong credentials and the lazy ``MainWindow`` import.

A role lookup that fails is *not* treated as a denied account: the window stays
open, explains that the role could not be verified, and the main button becomes
"Retry role check".  Only authentication failures show a login error.

Attributes kept for callers/tests: ``self.email``, ``self.password``,
``self.button``, ``self.status`` (the error banner's message label), the
``returnPressed`` connection on the password field and the 380x480 minimum.
"""

from __future__ import annotations

import hashlib
import importlib
import logging
import os
from pathlib import Path
import threading

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

try:
    from i18n import current_language, set_saved_language, t, tn
except ImportError:
    from desktop.i18n import current_language, set_saved_language, t, tn

from desktop.auth.session_store import (
    get_remember_session_setting,
    session_manager as default_session_manager,
    set_remember_session_setting,
)

from ..client import (
    RoleLookupError,
    forget_role,
    make_client,
    remember_role,
    resolve_role,
    sign_in,
    warm_connection,
)
from ..startup_debug import attach_first_paint_probe, mark, reset_timeline, startup_debug_enabled
from .components import BrandMark, Button, GradientHero, InlineBanner
from .icons import get_icon
from .resource import get_asset_path
from .tasks import human_error
from .theme import C, DESKTOP_STYLESHEET, S, apply_app_stylesheet, apply_role

# DESIGN.md §7 — hide the hero below this window width (form-only mode).
_LOGIN_HERO_BREAKPOINT = 760


def _dynamic_login_attr(name: str):
    """Look up module-level auth helpers dynamically so tests monkeypatching
    ``login_window.sign_in`` / ``resolve_role`` / ``remember_role`` work off-thread.
    """
    return globals()[name]


class _LoginTaskBridge(QObject):
    """Qt signal carrier delivering background login state onto the GUI thread."""

    phase_changed = Signal(int, str)
    auth_failed = Signal(int, str)
    role_error = Signal(int, object)
    access_denied = Signal(int)
    succeeded = Signal(int, str)


class _LoginWorker(QRunnable):
    """Runs sign-in, role verification, DPAPI persistence and module preload off GUI."""

    def __init__(
        self,
        bridge: _LoginTaskBridge,
        generation: int,
        *,
        client,
        email: str,
        password: str,
        credentials: tuple[str, str],
        retrying_role: bool,
        need_sign_out_old: bool,
        remember: bool,
        session_manager,
        package_name: str | None,
    ):
        super().__init__()
        self.bridge = bridge
        self.generation = generation
        self.client = client
        self.email = email
        self.password = password
        self.credentials = credentials
        self.retrying_role = retrying_role
        self.need_sign_out_old = need_sign_out_old
        self.remember = remember
        self.session_manager = session_manager
        self.package_name = package_name

    def run(self) -> None:
        log = logging.getLogger("resivo.login")
        sign_in_fn = _dynamic_login_attr("sign_in")
        resolve_role_fn = _dynamic_login_attr("resolve_role")
        remember_role_fn = _dynamic_login_attr("remember_role")
        forget_role_fn = _dynamic_login_attr("forget_role")

        try:
            if self.need_sign_out_old:
                try:
                    self.client.auth.sign_out()
                except Exception as exc:
                    log.warning("Could not sign out previous unverified session: %s", exc)
                forget_role_fn(self.client)

            if not self.retrying_role:
                mark("auth_start")
                try:
                    sign_in_fn(self.client, self.email, self.password)
                except Exception as exc:
                    mark("auth_end")
                    self.bridge.auth_failed.emit(self.generation, human_error(exc))
                    return
                mark("auth_end")
                self.bridge.phase_changed.emit(self.generation, "checking_role")

            mark("role_check_start")
            try:
                resolved = resolve_role_fn(self.client)
            except RoleLookupError as exc:
                mark("role_check_end")
                log.warning("Role verification failed during login: %s", exc)
                self.bridge.role_error.emit(self.generation, self.credentials)
                return
            except Exception as exc:
                mark("role_check_end")
                log.warning("Unexpected role lookup error during login: %s", exc)
                self.bridge.role_error.emit(self.generation, self.credentials)
                return
            mark("role_check_end")

            role = (resolved or "").strip().lower()
            if role not in ("staff", "admin"):
                try:
                    self.client.auth.sign_out()
                except Exception as exc:
                    log.warning("Could not sign out unauthorized account: %s", exc)
                forget_role_fn(self.client)
                if self.session_manager is not None:
                    try:
                        self.session_manager.clear()
                    except Exception:
                        pass
                self.bridge.access_denied.emit(self.generation)
                return

            remember_role_fn(self.client, role)
            if self.session_manager is not None:
                try:
                    self.session_manager.save_current_session(self.client, remember=self.remember)
                except Exception as exc:
                    log.warning("Failed to save session securely: %s", exc)
            mark("session_save_end")

            self.bridge.phase_changed.emit(self.generation, "opening_console")
            try:
                if self.package_name:
                    importlib.import_module(".main_window", package=self.package_name)
                else:
                    importlib.import_module("app.ui.main_window")
            except Exception as exc:
                log.debug("Background MainWindow preload skipped: %s", exc)
            self.bridge.succeeded.emit(self.generation, role)
        except Exception as exc:
            log.exception("Unhandled error in login worker")
            self.bridge.auth_failed.emit(self.generation, human_error(exc))
_FORM_MAX_WIDTH = 420
_SIGN_IN_TEXT = "Sign in"
_ROLE_ERROR_TEXT = "Could not verify your role. Check your connection or configuration."

_log = logging.getLogger("resivo.ui.login")


def _credential_key(email: str, password: str) -> tuple[str, str]:
    """Comparison key for the fields used by the last sign-in.

    Only the password digest is retained, never a second plaintext copy.
    """
    return email.strip().lower(), hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


class PasswordField(QLineEdit):
    """Password input with trailing eye toggle, Tab accessibility and echo mode switching."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(t("login.password_placeholder"))
        self.setMinimumHeight(S("size-control"))
        self.setStyleSheet("QLineEdit { padding-right: 34px; }")

        self.toggle_btn = QToolButton(self)
        self.toggle_btn.setObjectName("togglePasswordButton")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toggle_btn.setFixedSize(26, 26)
        self.toggle_btn.setStyleSheet(
            "QToolButton { background: transparent; border: none; padding: 2px; margin: 0; border-radius: 4px; }"
            f"QToolButton:hover {{ background-color: {C('surface-subtle')}; }}"
            f"QToolButton:focus {{ border: 2px solid {C('teal-600')}; }}"
        )
        self.toggle_btn.clicked.connect(self.toggle_visibility)
        self.set_visible(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        btn_w, btn_h = self.toggle_btn.width(), self.toggle_btn.height()
        x = self.width() - btn_w - 6
        y = (self.height() - btn_h) // 2
        self.toggle_btn.move(x, y)

    def set_visible(self, visible: bool):
        self._is_visible = bool(visible)
        if self._is_visible:
            self.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_btn.setIcon(get_icon("eye-off", 16, C("text-muted")))
            self.toggle_btn.setToolTip(t("login.hide_password"))
            self.toggle_btn.setAccessibleName(t("login.hide_password"))
        else:
            self.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_btn.setIcon(get_icon("eye", 16, C("text-muted")))
            self.toggle_btn.setToolTip(t("login.show_password"))
            self.toggle_btn.setAccessibleName(t("login.show_password"))

    def toggle_visibility(self):
        self.set_visible(not getattr(self, "_is_visible", False))

    def retranslate_ui(self):
        self.setPlaceholderText(t("login.password_placeholder"))
        self.set_visible(getattr(self, "_is_visible", False))


class LoginWindow(QWidget):
    def __init__(
        self,
        client=None,
        start_minimized: bool = False,
        session_manager: Any = None,
        banner_message: str | None = None,
        reason: str | None = None,
    ):
        super().__init__()
        self.setWindowTitle(t("login.title"))
        self.setMinimumSize(380, 480)
        self.resize(940, 580)
        apply_app_stylesheet(self)
        self.client = client if client is not None else make_client()
        self._busy = False
        self._busy_phase = "sign_in"
        self._auth_generation = 0
        self._auth_bridge = _LoginTaskBridge(self)
        self._auth_bridge.phase_changed.connect(self._on_worker_phase)
        self._auth_bridge.auth_failed.connect(self._on_worker_auth_failed)
        self._auth_bridge.role_error.connect(self._on_worker_role_error)
        self._auth_bridge.access_denied.connect(self._on_worker_access_denied)
        self._auth_bridge.succeeded.connect(self._on_worker_succeeded)
        self._warmup_cancel = threading.Event()
        self._warmup_started = False
        self._warmup_thread: threading.Thread | None = None
        self.session_manager = session_manager or default_session_manager
        self._start_minimized = bool(start_minimized)
        self._role_retry_pending = False
        # (email, password digest) for the signed-in session, so an edited
        # credential is treated as a fresh sign-in, not another role retry.
        self._pending_credentials: tuple[str, str] | None = None
        icon_path = get_asset_path("brand/resivo.ico")
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.hero = self._build_hero()
        self.form_host, self.form_column = self._build_form()
        root.addWidget(self.hero, 1)
        root.addWidget(self.form_host, 1)

        if banner_message:
            self._show_error(banner_message)
        elif reason in ("reboot", "logon_changed", "rebooted"):
            self.error_banner.set_kind("info")
            self._show_error(t("login.session_rebooted"))
        elif reason == "expired":
            self.error_banner.set_kind("warning")
            self._show_error(t("login.session_expired"))
        elif reason:
            self._show_error(reason)

        self._retranslate_ui()
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

        self.hero_headline = QLabel(t("login.hero_title"))
        apply_role(self.hero_headline, "display")
        self.hero_headline.setStyleSheet(f"color: {C('surface')};")
        self.hero_headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.body.addWidget(self.hero_headline)

        self.hero_value_line = QLabel(t("login.hero_desc"))
        apply_role(self.hero_value_line, "body")
        self.hero_value_line.setStyleSheet(f"color: {C('text-on-dark')};")
        self.hero_value_line.setWordWrap(True)
        self.hero_value_line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.body.addWidget(self.hero_value_line)

        hero.body.addStretch(1)

        self.hero_caption = QLabel(t("login.hero_caption"))
        apply_role(self.hero_caption, "small")
        self.hero_caption.setStyleSheet(f"color: {C('text-on-dark-muted')};")
        self.hero_caption.setWordWrap(True)
        self.hero_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.body.addWidget(self.hero_caption)
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
        self.subtitle_label = QLabel(t("login.subtitle"))
        apply_role(self.subtitle_label, "muted")
        col.addWidget(title)
        col.addWidget(self.subtitle_label)
        col.addSpacing(S("space-4"))

        self.email_label = QLabel(t("login.email_label"))
        apply_role(self.email_label, "small")
        self.email = QLineEdit()
        self.email.setPlaceholderText(t("login.email_placeholder"))
        self.email.setMinimumHeight(S("size-control"))
        self.email.returnPressed.connect(self._on_email_return_pressed)
        col.addWidget(self.email_label)
        col.addWidget(self.email)

        self.password_label = QLabel(t("login.password_label"))
        apply_role(self.password_label, "small")
        self.password = PasswordField()
        self.toggle_password_btn = self.password.toggle_btn
        self.password.returnPressed.connect(self.attempt)
        col.addWidget(self.password_label)
        col.addWidget(self.password)

        self.remember_checkbox = QCheckBox(t("login.remember_session"))
        self.remember_checkbox.setObjectName("rememberSessionCheckbox")
        self.remember_checkbox.setChecked(get_remember_session_setting())
        self.remember_checkbox.toggled.connect(set_remember_session_setting)
        self.remember_checkbox.setStyleSheet(
            f"QCheckBox {{ color: {C('text-primary')}; font-size: {C('fs-small')}; margin-top: 4px; margin-bottom: 4px; }}"
        )
        col.addWidget(self.remember_checkbox)

        # Failure banner — hidden until needed; ``self.status`` is its message
        # label so legacy ``self.status.setText(...)`` code keeps working.
        self.error_banner = InlineBanner(kind="error", message="")
        self.error_banner.setVisible(False)
        self.status = self.error_banner._message
        col.addWidget(self.error_banner)

        self.button = Button.primary(t("login.sign_in"), "log-in")
        self.button.setMinimumHeight(S("size-control"))
        self.button.clicked.connect(self.attempt)
        col.addWidget(self.button)

        self.busy_bar = QProgressBar(self)
        self.busy_bar.setObjectName("loginBusyBar")
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setFixedHeight(4)
        self.busy_bar.setVisible(False)
        col.addWidget(self.busy_bar)

        # Only offered when the role check failed (the session exists but its
        # role could not be verified): sign out and enter another account.
        self.switch_account_btn = Button.secondary(t("login.switch_account"))
        self.switch_account_btn.setObjectName("switchAccountButton")
        self.switch_account_btn.setVisible(False)
        self.switch_account_btn.clicked.connect(self.switch_account)
        col.addWidget(self.switch_account_btn)

        # Discreet language switch below the form
        self.lang_btn = QPushButton("Français | English")
        self.lang_btn.setObjectName("languageToggle")
        self.lang_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lang_btn.setFlat(True)
        self.lang_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {C('text-muted')}; "
            f"font-size: {C('fs-small')}; font-weight: {C('fw-medium')}; padding: 4px 8px; border-radius: 4px; }} "
            f"QPushButton:hover {{ color: {C('teal-600')}; background-color: {C('surface-subtle')}; }}"
        )
        self.lang_btn.setToolTip(t("terms.language"))
        self.lang_btn.clicked.connect(self._toggle_language)
        col.addSpacing(S("space-2"))
        col.addWidget(self.lang_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        host_layout.addWidget(column, 0, Qt.AlignmentFlag.AlignHCenter)
        host_layout.addStretch(1)
        return host, column

    def _toggle_language(self):
        new_lang = "fr" if current_language() == "en" else "en"
        set_saved_language(new_lang)
        self._retranslate_ui()

    def _retranslate_ui(self):
        self.setWindowTitle(t("login.title"))
        if hasattr(self, "hero_headline"):
            self.hero_headline.setText(t("login.hero_title"))
        if hasattr(self, "hero_value_line"):
            self.hero_value_line.setText(t("login.hero_desc"))
        if hasattr(self, "hero_caption"):
            self.hero_caption.setText(t("login.hero_caption"))
        if hasattr(self, "subtitle_label"):
            self.subtitle_label.setText(t("login.subtitle"))
        if hasattr(self, "email_label"):
            self.email_label.setText(t("login.email_label"))
        if hasattr(self, "email"):
            self.email.setPlaceholderText(t("login.email_placeholder"))
        if hasattr(self, "password_label"):
            self.password_label.setText(t("login.password_label"))
        if hasattr(self, "password"):
            self.password.setPlaceholderText(t("login.password_placeholder"))
            if hasattr(self.password, "retranslate_ui"):
                self.password.retranslate_ui()
        if hasattr(self, "remember_checkbox"):
            self.remember_checkbox.setText(t("login.remember_session"))
        if hasattr(self, "button"):
            if self._busy:
                phase_keys = {
                    "signing_in": "login.signing_in",
                    "checking_role": "login.checking_role",
                    "opening_console": "login.opening_console",
                }
                self.button.setText(t(phase_keys.get(self._busy_phase, "login.signing_in")))
            elif self._role_retry_pending:
                self.button.setText(t("login.retry_role_check"))
            elif not self.button.isEnabled():
                self.button.setText(t("login.checking_role"))
            else:
                self.button.setText(t("login.sign_in"))
        if hasattr(self, "switch_account_btn"):
            self.switch_account_btn.setText(t("login.switch_account"))
        if hasattr(self, "lang_btn"):
            self.lang_btn.setToolTip(t("terms.language"))

    # --------------------------------------------------------------- responsive
    def _apply_responsive_layout(self) -> None:
        """Hero hidden below 760 px (DESIGN.md §7); form centred, max ~420 px."""
        hero_visible = self.width() >= _LOGIN_HERO_BREAKPOINT
        self.hero.setVisible(hero_visible)
        available = self.width() if not hero_visible else self.width() // 2
        width = max(280, min(_FORM_MAX_WIDTH, available - 2 * S("space-8")))
        self.form_column.setFixedWidth(width)

    def showEvent(self, event):  # noqa: N802 - Qt API
        super().showEvent(event)
        if hasattr(self, "password") and hasattr(self.password, "set_visible"):
            self.password.set_visible(False)
        self._schedule_idle_warmup()

    def _on_email_return_pressed(self):
        if self._busy:
            return
        if self.password.text():
            self.attempt()
        else:
            self.password.setFocus()

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if hasattr(self, "hero"):
            self._apply_responsive_layout()

    # ------------------------------------------------------------------- flow
    def _show_error(self, message: str) -> None:
        self.error_banner.set_message(message)
        self.error_banner.setVisible(True)

    def show_error(self, message: str) -> None:
        """Display a caller-supplied, already-human-readable failure."""
        self._show_error(message)

    def attempt(self):
        if self._busy:
            return

        email_txt = self.email.text().strip()
        pwd_txt = self.password.text()
        credentials = _credential_key(email_txt, pwd_txt)

        retrying_role = False
        need_sign_out_old = False
        if self._role_retry_pending:
            if not pwd_txt and self._pending_credentials and email_txt.lower() == self._pending_credentials[0]:
                retrying_role = True
                credentials = self._pending_credentials
            elif credentials == self._pending_credentials:
                retrying_role = True
            else:
                # The credentials were edited after the role check failed: this is
                # a new sign-in for another account, not a retry of the old session.
                need_sign_out_old = True
                self._role_retry_pending = False
                self._pending_credentials = None

        if not retrying_role and (not email_txt or not pwd_txt):
            self._show_error(t("login.missing_credentials"))
            return

        self._warmup_cancel.set()
        self.switch_account_btn.setVisible(False)
        self.error_banner.setVisible(False)

        reset_timeline("sign_in")
        mark("sign_in_click")

        initial_phase = "checking_role" if retrying_role else "signing_in"
        initial_text = t("login.checking_role") if retrying_role else t("login.signing_in")
        self._set_busy(True, phase=initial_phase, button_text=initial_text)
        mark("busy_ui_set")
        if startup_debug_enabled():
            QTimer.singleShot(0, lambda: mark("busy_ui_event_loop_tick"))

        remember = self.remember_checkbox.isChecked() if hasattr(self, "remember_checkbox") else True
        self._auth_generation += 1
        worker = _LoginWorker(
            self._auth_bridge,
            self._auth_generation,
            client=self.client,
            email=email_txt,
            password=pwd_txt,
            credentials=credentials,
            retrying_role=retrying_role,
            need_sign_out_old=need_sign_out_old,
            remember=remember,
            session_manager=self.session_manager,
            package_name=__package__,
        )
        QThreadPool.globalInstance().start(worker)

    def _leave_failed_session(self):
        """Drop the unverified session before signing in with new credentials."""
        forget_role(self.client)
        try:
            self.client.auth.sign_out()
        except Exception as exc:  # noqa: BLE001 - cleanup only, sign-in follows
            _log.warning(
                "Sign-out before re-authentication failed: %s", human_error(exc)
            )
        self._role_retry_pending = False
        self._pending_credentials = None
        self.switch_account_btn.setVisible(False)

    def switch_account(self):
        """Sign out the unverified session and return to the credential form."""
        forget_role(self.client)
        try:
            self.client.auth.sign_out()
        except Exception as exc:  # noqa: BLE001 - reported, form stays usable
            _log.warning("Sign-out for account switch failed: %s", human_error(exc))
            self._show_error(t("login.sign_out_error", reason=human_error(exc)))
            return

        self._role_retry_pending = False
        self._pending_credentials = None
        self.password.clear()
        self.error_banner.setVisible(False)
        self.button.setText(t("login.sign_in"))
        self.button.setEnabled(True)
        self.switch_account_btn.setVisible(False)
        self.email.setFocus()
        self.email.selectAll()

    def _verify_role(self):
        """Trigger async role verification on the current session (compat helper)."""
        if self._busy:
            return
        self._set_busy(True, phase="checking_role", button_text=t("login.checking_role"))
        remember = self.remember_checkbox.isChecked() if hasattr(self, "remember_checkbox") else True
        creds = self._pending_credentials or _credential_key(self.email.text().strip(), "")
        self._auth_generation += 1
        worker = _LoginWorker(
            self._auth_bridge,
            self._auth_generation,
            client=self.client,
            email=self.email.text().strip(),
            password="",
            credentials=creds,
            retrying_role=True,
            need_sign_out_old=False,
            remember=remember,
            session_manager=self.session_manager,
            package_name=__package__,
        )
        QThreadPool.globalInstance().start(worker)

    def _on_worker_phase(self, generation: int, phase: str) -> None:
        if generation != self._auth_generation:
            return
        self._busy_phase = phase
        key_map = {
            "signing_in": "login.signing_in",
            "checking_role": "login.checking_role",
            "opening_console": "login.opening_console",
        }
        self.button.setText(t(key_map.get(phase, "login.signing_in")))

    def _on_worker_auth_failed(self, generation: int, message: str) -> None:
        if generation != self._auth_generation:
            return
        self._set_busy(False)
        self.password.clear()
        self._show_error(f"{t('login.login_failed')}: {message}")
        self.button.setText(t("login.sign_in"))

    def _on_worker_role_error(self, generation: int, credentials) -> None:
        if generation != self._auth_generation:
            return
        self._pending_credentials = credentials
        self._set_busy(False)
        self.password.clear()
        self._show_role_error()

    def _on_worker_access_denied(self, generation: int) -> None:
        if generation != self._auth_generation:
            return
        self._role_retry_pending = False
        self._pending_credentials = None
        self._set_busy(False)
        self._show_error(t("login.access_denied"))
        self.button.setText(t("login.sign_in"))
        self.password.clear()

    def _on_worker_succeeded(self, generation: int, role: str) -> None:
        if generation != self._auth_generation:
            return
        self._role_retry_pending = False
        self._pending_credentials = None
        self.switch_account_btn.setVisible(False)
        if hasattr(self, "password") and hasattr(self.password, "set_visible"):
            self.password.set_visible(False)
        self.password.clear()
        self._open_main_window(role)

    def _open_main_window(self, role: str) -> None:
        mark("main_window_init_start")
        try:
            from .main_window import MainWindow

            win = MainWindow(self.client, role=role)
        except Exception as exc:
            self._set_busy(False)
            self._show_error(human_error(exc))
            return
        self.window = win
        attach_first_paint_probe(self.window)
        if getattr(self, "_start_minimized", False):
            self.window.showMinimized()
        else:
            self.window.show()
            if hasattr(self.window, "raise_"):
                self.window.raise_()
            if hasattr(self.window, "activateWindow"):
                self.window.activateWindow()
        mark("main_window_shown")
        self._warmup_cancel.set()
        self._auth_generation += 1
        self._busy = False
        self.close()

    def _set_busy(self, busy: bool, *, phase: str | None = None, button_text: str | None = None) -> None:
        self._busy = busy
        if phase is not None:
            self._busy_phase = phase
        self.email.setEnabled(not busy)
        self.password.setEnabled(not busy)
        if hasattr(self, "toggle_password_btn"):
            self.toggle_password_btn.setEnabled(not busy)
        if hasattr(self, "remember_checkbox"):
            self.remember_checkbox.setEnabled(not busy)
        if hasattr(self, "lang_btn"):
            self.lang_btn.setEnabled(not busy)
        self.button.setEnabled(not busy)
        if hasattr(self, "busy_bar"):
            self.busy_bar.setVisible(busy)
        if button_text is not None:
            self.button.setText(button_text)

    def _schedule_idle_warmup(self) -> None:
        if not self._warmup_started and not self._warmup_cancel.is_set():
            QTimer.singleShot(150, self._start_idle_warmup)

    def _start_idle_warmup(self) -> None:
        if self._warmup_started or self._warmup_cancel.is_set() or self._busy:
            return
        self._warmup_started = True
        cancel = self._warmup_cancel
        client = self.client
        pkg = __package__
        warm_net = (
            os.environ.get("QT_QPA_PLATFORM", "") != "offscreen"
            and "PYTEST_CURRENT_TEST" not in os.environ
            and os.environ.get("RESIVO_SKIP_NETWORK_WARMUP", "") != "1"
        )

        def _worker():
            try:
                if cancel.is_set():
                    return
                if pkg:
                    importlib.import_module(".main_window", package=pkg)
                    if cancel.is_set():
                        return
                    importlib.import_module(".pages.overview", package=pkg)
                if warm_net and not cancel.is_set():
                    warm_connection(client, cancel_event=cancel)
            except Exception:
                pass

        t_worker = threading.Thread(target=_worker, name="resivo-login-warmup", daemon=True)
        self._warmup_thread = t_worker
        t_worker.start()

    def closeEvent(self, event):  # noqa: N802 - Qt API
        self._warmup_cancel.set()
        self._auth_generation += 1
        self._busy = False
        super().closeEvent(event)

    def _show_role_error(self):
        # Keep the window open and let the same button retry the check.  The
        # session is deliberately not signed out: this is a transient failure,
        # not an access-denied decision.  "Use another account" remains
        # available for an operator who signed in with the wrong address.
        self._role_retry_pending = True
        self._show_error(t("login.role_error"))
        self.button.setText(t("login.retry_role_check"))
        self.button.setEnabled(True)
        self.switch_account_btn.setVisible(True)
