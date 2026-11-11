"""Dialogs and formatting helpers for single-gender residence configuration."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
)

try:
    from i18n import format_number, t
except ImportError:
    from desktop.i18n import format_number, t

from ..client import fetch_residence_gender_impact, set_residence_gender
from . import theme
from .components import Button, InlineBanner, apply_elevation
from .icons import get_pixmap
from .tasks import TaskRunner
from .theme import C, DESKTOP_STYLESHEET, S, apply_app_stylesheet


def residence_gender_label(value: str | None) -> str:
    """Human-readable label for configured residence_gender."""
    normalized = str(value or "").strip().lower()
    if normalized == "male":
        return t("residence.male_residence")
    if normalized == "female":
        return t("residence.female_residence")
    return t("residence.not_set")


def gender_word_label(value: str | None) -> str:
    """Short gender word label (Male / Female)."""
    normalized = str(value or "").strip().lower()
    if normalized == "female":
        return t("gender.female").lower()
    if normalized == "male":
        return t("gender.male").lower()
    return "—"


class ResidenceSetupDialog(QDialog):
    """One-time administrator dialog shown on launch when residence_gender is unset."""

    def __init__(self, parent=None, client=None):
        super().__init__(parent)
        self.client = client
        self.saved_gender: str | None = None
        self.result_payload: dict | None = None
        self._busy = False
        self._closing = False
        self.tasks = TaskRunner(self)

        self.setWindowTitle(t("residence.setup_title"))
        self.setModal(True)
        self.setMinimumWidth(460)
        apply_app_stylesheet(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        root.setSpacing(S("space-4"))

        head = QHBoxLayout()
        head.setSpacing(S("space-3"))
        icon = QLabel()
        icon.setPixmap(get_pixmap("building", 24, C("teal-600")))
        head.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        header_col = QVBoxLayout()
        header_col.setSpacing(S("space-1"))
        title = QLabel(t("residence.setup_title"))
        theme.apply_role(title, "h2")
        desc = QLabel(t("residence.setup_body"))
        theme.apply_role(desc, "muted")
        desc.setWordWrap(True)
        header_col.addWidget(title)
        header_col.addWidget(desc)
        head.addLayout(header_col, 1)
        root.addLayout(head)

        self.radio_group = QButtonGroup(self)
        self.male_radio = QRadioButton(t("residence.male_residence"))
        self.female_radio = QRadioButton(t("residence.female_residence"))
        for rb in (self.male_radio, self.female_radio):
            theme.apply_role(rb, "body")
            rb.toggled.connect(self._sync_save_state)
            self.radio_group.addButton(rb)
            root.addWidget(rb)

        self.error_banner = InlineBanner(
            "error",
            title=t("settings.residence_error_title"),
            message="",
        )
        self.error_banner.setVisible(False)
        root.addWidget(self.error_banner)

        buttons = QHBoxLayout()
        buttons.setSpacing(S("space-2"))
        buttons.addStretch(1)
        self.later_btn = Button.secondary(t("residence.setup_later_btn"))
        self.later_btn.clicked.connect(self.reject)
        self.save_btn = Button.primary(t("residence.setup_save_btn"))
        self.save_btn.setEnabled(False)
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.on_save)
        buttons.addWidget(self.later_btn)
        buttons.addWidget(self.save_btn)
        root.addLayout(buttons)
        apply_elevation(self, 2)

    def selected_gender(self) -> str | None:
        if self.male_radio.isChecked():
            return "male"
        if self.female_radio.isChecked():
            return "female"
        return None

    def _sync_save_state(self) -> None:
        self.save_btn.setEnabled((not self._busy) and self.selected_gender() is not None)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.male_radio.setEnabled(not busy)
        self.female_radio.setEnabled(not busy)
        self.later_btn.setEnabled(not busy)
        self.save_btn.setText(t("settings.residence_saving") if busy else t("residence.setup_save_btn"))
        self._sync_save_state()

    def _on_saved(self, target_gender: str, payload: dict) -> None:
        if self._closing:
            return
        self.saved_gender = target_gender
        self.result_payload = dict(payload or {})
        self.accept()

    def _on_failed(self, message: str) -> None:
        if self._closing:
            return
        self.error_banner.set_message(message)
        self.error_banner.setVisible(True)

    def _on_finished(self) -> None:
        if not self._closing:
            self._set_busy(False)

    def closeEvent(self, event):  # noqa: N802 - Qt API
        self._closing = True
        super().closeEvent(event)

    def _on_impact_finished(self) -> None:
        if not self._closing and not self.tasks.is_busy("residence-initial-setup"):
            self._set_busy(False)

    def _submit_gender(self, target_gender: str, confirmation: str | None) -> None:
        self._set_busy(True)
        started = self.tasks.run(
            "residence-initial-setup",
            lambda: set_residence_gender(self.client, target_gender, confirmation=confirmation),
            on_success=lambda res: self._on_saved(target_gender, res),
            on_failed=self._on_failed,
            on_finished=self._on_finished,
        )
        if not started:
            self._set_busy(False)

    def _on_impact_ready(self, target_gender: str, impact: dict) -> None:
        if self._closing:
            return
        self._set_busy(False)
        if impact.get("needs_confirmation"):
            dlg = ResidenceGenderChangeDialog(self, impact, target_gender)
            if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.confirmed:
                return
            self._submit_gender(target_gender, "CHANGE")
        else:
            self._submit_gender(target_gender, None)

    def on_save(self) -> None:
        if self._busy:
            return
        chosen = self.selected_gender()
        if chosen is None:
            self.error_banner.set_message(t("residence.setup_select_required"))
            self.error_banner.setVisible(True)
            return

        self.error_banner.setVisible(False)
        self._set_busy(True)

        def check_then_prepare():
            try:
                return fetch_residence_gender_impact(self.client, chosen)
            except RuntimeError:
                return {"needs_confirmation": False}

        started = self.tasks.run(
            "residence-initial-impact",
            check_then_prepare,
            on_success=lambda impact: self._on_impact_ready(chosen, impact),
            on_failed=self._on_failed,
            on_finished=self._on_impact_finished,
        )
        if not started:
            self._set_busy(False)


class ResidenceGenderChangeDialog(QDialog):
    """Typed 'CHANGE' confirmation dialog showing exact residence impact counts."""

    def __init__(self, parent, impact: dict, new_gender: str):
        super().__init__(parent)
        self.confirmed = False
        self._impact = dict(impact or {})
        self._new_gender = str(new_gender).strip().lower()
        other_gender = "female" if self._new_gender == "male" else "male"

        self.setWindowTitle(t("settings.residence_change_title"))
        self.setModal(True)
        self.setMinimumWidth(480)
        apply_app_stylesheet(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        root.setSpacing(S("space-4"))

        head = QHBoxLayout()
        head.setSpacing(S("space-3"))
        icon = QLabel()
        icon.setPixmap(get_pixmap("alert-triangle", 22, C("status-danger-ink")))
        head.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(S("space-2"))
        title = QLabel(t("settings.residence_change_title"))
        theme.apply_role(title, "h2")
        col.addWidget(title)

        body_text = t(
            "settings.residence_change_body",
            total=format_number(int(self._impact.get("students_total") or 0)),
            pending=format_number(int(self._impact.get("students_pending") or 0)),
            active=format_number(int(self._impact.get("students_active") or 0)),
            rejected=format_number(int(self._impact.get("students_rejected") or 0)),
            assigned=format_number(int(self._impact.get("students_with_room") or 0)),
            other_students=format_number(int(self._impact.get("students_of_other_gender") or 0)),
            other_gender=gender_word_label(other_gender),
            new_gender=gender_word_label(self._new_gender),
        )
        self.body_label = QLabel(body_text)
        theme.apply_role(self.body_label, "body")
        self.body_label.setWordWrap(True)
        col.addWidget(self.body_label)
        head.addLayout(col, 1)
        root.addLayout(head)

        type_label = QLabel(t("settings.residence_change_type_label"))
        theme.apply_role(type_label, "small")
        root.addWidget(type_label)

        self.confirm_edit = QLineEdit()
        self.confirm_edit.setPlaceholderText(t("settings.residence_change_type_placeholder"))
        self.confirm_edit.textChanged.connect(self._on_text_changed)
        root.addWidget(self.confirm_edit)

        buttons = QHBoxLayout()
        buttons.setSpacing(S("space-2"))
        buttons.addStretch(1)

        self.cancel_btn = Button.secondary(t("common.cancel"))
        self.cancel_btn.setDefault(True)
        self.cancel_btn.setAutoDefault(True)
        self.cancel_btn.clicked.connect(self.reject)

        self.confirm_btn = Button.danger(t("settings.residence_change_confirm_btn"))
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setDefault(False)
        self.confirm_btn.setAutoDefault(False)
        self.confirm_btn.clicked.connect(self._on_confirm)

        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.confirm_btn)
        root.addLayout(buttons)
        apply_elevation(self, 2)

    def _on_text_changed(self, text: str) -> None:
        self.confirm_btn.setEnabled(text == "CHANGE")

    def _on_confirm(self) -> None:
        if self.confirm_edit.text() != "CHANGE":
            return
        self.confirmed = True
        self.accept()
