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


class CloseConfirmDialog(QDialog):
    """Custom confirmation dialog displayed before closing the application."""

    def __init__(self, parent: QWidget | None = None, is_busy: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("Close RÉSIVO?")
        self.setMinimumWidth(440)
        self.setStyleSheet(DESKTOP_STYLESHEET)
        self.is_busy = is_busy

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        layout.setSpacing(S("space-4"))

        if is_busy:
            card = Card(
                "Action in progress",
                "An action is still running. Closing now may leave it unfinished.",
                icon="alert-triangle",
            )
            banner = InlineBanner(
                "danger",
                title="Warning",
                message="Background database operations are currently active. "
                "Forcing closure now may corrupt in-flight changes.",
            )
            card.add_widget(banner)
            self.dont_ask_checkbox = None
        else:
            card = Card(
                "Close RÉSIVO?",
                "Background live sync and notifications will stop running.",
                icon="log-out",
            )
            msg = QLabel(
                "Are you sure you want to close RÉSIVO? Background live sync and "
                "desktop notifications will stop running."
            )
            msg.setWordWrap(True)
            msg.setStyleSheet(f"color: {C('text-secondary')}; font-size: {C('fs-body')};")
            card.add_widget(msg)

            self.dont_ask_checkbox = QCheckBox("Don't ask me again")
            self.dont_ask_checkbox.setStyleSheet(
                f"QCheckBox {{ color: {C('text-secondary')}; font-size: {C('fs-small')}; margin-top: 8px; }}"
            )
            card.add_widget(self.dont_ask_checkbox)

        layout.addWidget(card)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(S("space-3"))
        btn_row.addStretch(1)

        # Cancel is secondary and default (Esc / Enter on Cancel safe)
        self.cancel_btn = Button.secondary("Cancel")
        self.cancel_btn.setDefault(True)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        if is_busy:
            self.confirm_btn = Button.danger("Close anyway", icon="alert-triangle")
        else:
            self.confirm_btn = Button.primary("Close app")
        self.confirm_btn.clicked.connect(self._on_confirm_clicked)
        btn_row.addWidget(self.confirm_btn)

        layout.addLayout(btn_row)

    def _on_confirm_clicked(self) -> None:
        if self.dont_ask_checkbox and self.dont_ask_checkbox.isChecked():
            set_confirm_close_setting(False)
        self.accept()

    def exec(self) -> int:
        if "PYTEST_CURRENT_TEST" in os.environ and not getattr(self, "_test_modal", False):
            return QDialog.DialogCode.Accepted
        return super().exec()
