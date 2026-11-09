"""RÉSIVO — Application close policy, confirmation dialog, and settings persistence."""

from __future__ import annotations

import os
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .components import Button, Card, InlineBanner
from .theme import C, DESKTOP_STYLESHEET, S

try:
    from i18n import t
except ImportError:
    from desktop.i18n import t


class ClosePolicy:
    """Pure logic deciding whether closing the application requires confirmation."""

    @staticmethod
    def should_confirm(
        confirm_setting: bool,
        is_busy: bool,
        is_session_ending: bool = False,
    ) -> bool:
        """Determine whether the app should prompt for confirmation before closing.

        Rules:
        - If the OS session is ending (logoff/reboot/shutdown), NEVER prompt (return False).
        - If background workers or mutating actions are active, ALWAYS prompt (return True),
          even if the user turned off the confirmation setting.
        - Otherwise, follow the user's confirm_setting preference.
        """
        if is_session_ending:
            return False
        if is_busy:
            return True
        return bool(confirm_setting)


def get_confirm_close_setting() -> bool:
    """Read the confirm-before-close setting from QSettings (default: True)."""
    settings = QSettings("RESIVO", "StaffConsole")
    val = settings.value("general/confirm_close", True)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() not in ("false", "0", "no")
    return bool(val)


def set_confirm_close_setting(enabled: bool) -> None:
    """Persist the confirm-before-close setting to QSettings."""
    settings = QSettings("RESIVO", "StaffConsole")
    settings.setValue("general/confirm_close", bool(enabled))


def get_minimize_to_tray_setting() -> bool:
    """Read the minimize-to-system-tray setting from QSettings (default: True)."""
    settings = QSettings("RESIVO", "StaffConsole")
    val = settings.value("general/minimize_to_tray", True)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() not in ("false", "0", "no")
    return bool(val)


def set_minimize_to_tray_setting(enabled: bool) -> None:
    """Persist the minimize-to-system-tray setting to QSettings."""
    settings = QSettings("RESIVO", "StaffConsole")
    settings.setValue("general/minimize_to_tray", bool(enabled))


class CloseConfirmDialog(QDialog):
    """Custom confirmation dialog displayed before closing the application."""

    def __init__(self, parent: QWidget | None = None, is_busy: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("close_dialog.title"))
        self.setMinimumWidth(440)
        self.setStyleSheet(DESKTOP_STYLESHEET)
        self.is_busy = is_busy

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        layout.setSpacing(S("space-4"))

        if is_busy:
            card = Card(
                t("close_dialog.busy_title"),
                t("close_dialog.busy_desc"),
                icon="alert-triangle",
            )
            banner = InlineBanner(
                "danger",
                title=t("close_dialog.warning"),
                message=t("close_dialog.busy_warning"),
            )
            card.add_widget(banner)
            self.dont_ask_checkbox = None
        else:
            card = Card(
                t("close_dialog.normal_title"),
                t("close_dialog.normal_desc"),
                icon="log-out",
            )
            msg = QLabel(t("close_dialog.normal_body"))
            msg.setWordWrap(True)
            msg.setStyleSheet(f"color: {C('text-secondary')}; font-size: {C('fs-body')};")
            card.add_widget(msg)

            self.dont_ask_checkbox = QCheckBox(t("close_dialog.dont_ask"))
            self.dont_ask_checkbox.setStyleSheet(
                f"QCheckBox {{ color: {C('text-secondary')}; font-size: {C('fs-small')}; margin-top: 8px; }}"
            )
            card.add_widget(self.dont_ask_checkbox)

        layout.addWidget(card)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(S("space-3"))
        btn_row.addStretch(1)

        self.was_minimized_to_tray = False

        # Cancel is secondary and default (Esc / Enter on Cancel safe)
        self.cancel_btn = Button.secondary(t("close_dialog.cancel"))
        self.cancel_btn.setDefault(True)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        if is_busy:
            self.minimize_btn = None
            self.confirm_btn = Button.danger(t("close_dialog.close_anyway"), icon="alert-triangle")
        else:
            self.minimize_btn = Button.secondary(t("close_dialog.minimize_to_tray"))
            self.minimize_btn.clicked.connect(self._on_minimize_clicked)
            btn_row.addWidget(self.minimize_btn)
            self.confirm_btn = Button.primary(t("close_dialog.close_app"))
        self.confirm_btn.clicked.connect(self._on_confirm_clicked)
        btn_row.addWidget(self.confirm_btn)

        layout.addLayout(btn_row)

    def _on_minimize_clicked(self) -> None:
        self.was_minimized_to_tray = True
        self.reject()

    def _on_confirm_clicked(self) -> None:
        if self.dont_ask_checkbox and self.dont_ask_checkbox.isChecked():
            set_confirm_close_setting(False)
        self.accept()

    def exec(self) -> int:
        if "PYTEST_CURRENT_TEST" in os.environ and not getattr(self, "_test_modal", False):
            return QDialog.DialogCode.Accepted
        return super().exec()
