"""Settings → Updates section.

Reuses the shell components (Card, Button, InlineBanner, ConfirmDialog) and
binds to :class:`desktop.updater.service.UpdateService`.  The widget never
performs I/O itself: pressing a button asks the service, which runs the work
on the existing TaskRunner.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Callable

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop.version import __version__

try:
    from i18n import format_date, format_datetime, format_number, format_time, t
except ImportError:
    from desktop.i18n import format_date, format_datetime, format_number, format_time, t

from ...updater import prefs
from ...updater.state import UpdateState
from . import theme
from .components import Button, Card, ConfirmDialog, InlineBanner
from .theme import C, S

__all__ = ["UpdatesSection", "markdown_to_plain"]

_MAX_NOTES_CHARS = 6000
_TAG_RE = re.compile(r"<[^>]+>")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD_RE = re.compile(r"(\*\*|__)(.+?)\1")
_CODE_RE = re.compile(r"`([^`]+)`")


def markdown_to_plain(text: str, max_chars: int = _MAX_NOTES_CHARS) -> str:
    """Render release-note markdown as safe plain text.

    Headings become uppercase lines, links become ``label (url)``, bullets use
    a plain dash, and every HTML tag is stripped.  The result is only ever fed
    to a plain-text widget, so nothing is rendered or opened automatically.
    """
    if not text:
        return ""
    value = str(text).replace("\r\n", "\n").replace("\r", "\n")
    value = _TAG_RE.sub("", value)
    value = _LINK_RE.sub(lambda m: f"{m.group(1)} ({m.group(2)})", value)
    value = _BOLD_RE.sub(lambda m: m.group(2), value)
    value = _CODE_RE.sub(lambda m: m.group(1), value)

    lines: list[str] = []
    for raw in value.split("\n"):
        line = raw.rstrip()
        heading = re.match(r"^\s{0,3}#{1,6}\s*(.+)$", line)
        if heading:
            lines.append(heading.group(1).upper())
            continue
        bullet = re.match(r"^\s*[-*+]\s+(.*)$", line)
        if bullet:
            lines.append(f"- {bullet.group(1)}")
            continue
        lines.append(line)
    cleaned = "\n".join(lines).strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[: max_chars - 1].rstrip() + "…"
    return cleaned


def format_size_mb(value: int) -> str:
    """Localized one-decimal megabyte string."""
    return f"{format_number(max(0, int(value)) / (1024 * 1024), decimals=1)} MB"


class UpdatesSection(QWidget):
    """The Updates card with version, check button, notes and progress."""

    install_requested = Signal(object)  # Path to the verified installer
    availability_changed = Signal(bool)

    def __init__(self, service, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._busy_checker: Callable[[], bool] = lambda: False
        self._last_action = "check"
        self._last_kind = ""
        self._retry_at: float | None = None
        self._build()
        self._connect_service()
        self._render(self.service.state)
        self._refresh_last_checked()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S("space-2"))

        self.card = Card(
            t("updates.title"),
            t("updates.subtitle"),
            icon="download",
        )
        self.card.setObjectName("updatesSection")

        row = QHBoxLayout()
        row.setSpacing(S("space-4"))
        self.current_version_label = QLabel(
            t("updates.current_version", version=__version__)
        )
        self.current_version_label.setObjectName("updatesCurrentVersion")
        theme.apply_role(self.current_version_label, "h3")
        row.addWidget(self.current_version_label)
        row.addStretch(1)
        self.check_button = Button.primary(t("updates.check_button"), icon="refresh")
        self.check_button.setObjectName("updatesCheckButton")
        self.check_button.clicked.connect(self._on_check_clicked)
        row.addWidget(self.check_button)
        self.card.add_layout(row)

        self.last_checked_label = QLabel()
        self.last_checked_label.setObjectName("updatesLastChecked")
        _small(self.last_checked_label)
        self.card.add_widget(self.last_checked_label)

        self.auto_check = QCheckBox(t("updates.auto_check_label"))
        self.auto_check.setObjectName("updatesAutoCheck")
        self.auto_check.setChecked(prefs.get_auto_check())
        self.auto_check.toggled.connect(prefs.set_auto_check)
        self.card.add_widget(self.auto_check)

        self.auto_check_note = QLabel(t("updates.auto_check_note"))
        self.auto_check_note.setObjectName("updatesAutoCheckNote")
        _small(self.auto_check_note)
        self.card.add_widget(self.auto_check_note)

        self.status_label = QLabel("")
        self.status_label.setObjectName("updatesStatus")
        self.status_label.setWordWrap(True)
        theme.apply_role(self.status_label, "body")
        self.status_label.setVisible(False)
        self.card.add_widget(self.status_label)

        self.notes_label = QLabel(t("updates.release_notes"))
        self.notes_label.setObjectName("updatesNotesLabel")
        theme.apply_role(self.notes_label, "h3")
        self.notes_label.setVisible(False)
        self.card.add_widget(self.notes_label)

        self.notes_box = QTextEdit()
        self.notes_box.setObjectName("updatesNotes")
        self.notes_box.setReadOnly(True)
        self.notes_box.setAcceptRichText(False)
        self.notes_box.setPlainText("")
        self.notes_box.setMinimumHeight(110)
        self.notes_box.setMaximumHeight(190)
        self.notes_box.setStyleSheet(
            f"QTextEdit {{ background-color: {C('surface-subtle')};"
            f" border: 1px solid {C('border')}; border-radius: {C('radius-input')};"
            f" color: {C('text-primary')}; font-size: {C('fs-small')};"
            f" padding: {C('space-2')}; }}"
        )
        self.notes_box.setVisible(False)
        self.card.add_widget(self.notes_box)

        actions = QHBoxLayout()
        actions.setSpacing(S("space-2"))
        self.update_button = Button.primary(t("updates.update_now"), icon="download")
        self.update_button.setObjectName("updatesUpdateNow")
        self.update_button.clicked.connect(self._on_update_now)
        self.skip_button = Button.secondary(t("updates.skip_version"))
        self.skip_button.setObjectName("updatesSkipVersion")
        self.skip_button.clicked.connect(self._on_skip)
        self.later_button = Button.secondary(t("updates.later"))
        self.later_button.setObjectName("updatesLater")
        self.later_button.clicked.connect(self._on_later)
        for button in (self.update_button, self.skip_button, self.later_button):
            button.setVisible(False)
            actions.addWidget(button)
        actions.addStretch(1)
        self.card.add_layout(actions)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(S("space-3"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("updatesProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        progress_row.addWidget(self.progress_bar, 1)
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("updatesProgressLabel")
        _small(self.progress_label, wrap=False)
        self.progress_label.setVisible(False)
        progress_row.addWidget(self.progress_label)
        self.cancel_button = Button.secondary(t("updates.cancel_download"))
        self.cancel_button.setObjectName("updatesCancelDownload")
        self.cancel_button.clicked.connect(self.service.cancel_download)
        self.cancel_button.setVisible(False)
        progress_row.addWidget(self.cancel_button)
        self.card.add_layout(progress_row)

        self.error_banner = InlineBanner("error", title=t("updates.error_title"), message="")
        self.error_banner.setObjectName("updatesErrorBanner")
        self.retry_button = Button.secondary(t("updates.error_retry"), icon="refresh")
        self.retry_button.setObjectName("updatesRetryButton")
        self.retry_button.clicked.connect(self._on_retry)
        self.error_banner.add_action(self.retry_button)
        self.error_banner.setVisible(False)
        self.card.add_widget(self.error_banner)

        layout.addWidget(self.card)

    def _connect_service(self) -> None:
        self.service.state_changed.connect(self._on_state_changed)
        self.service.check_finished.connect(self._on_check_finished)
        self.service.progress_changed.connect(self._on_progress)
        self.service.download_cancelled.connect(self._on_cancelled)
        self.service.error_occurred.connect(self._on_error)
        self.service.available_changed.connect(self.availability_changed.emit)

    # ----------------------------------------------------------------- public
    def set_busy_checker(self, checker: Callable[[], bool]) -> None:
        self._busy_checker = checker

    def on_shown(self) -> None:
        """Refresh when the Settings page becomes visible."""
        self._refresh_last_checked()
        self._render(self.service.state)

    # ------------------------------------------------------------------ state
    def _percent(self) -> int:
        value = self.progress_bar.value()
        return max(0, min(100, int(value)))

    def _show_progress(self, visible: bool) -> None:
        self.progress_bar.setVisible(visible)
        self.progress_label.setVisible(visible)

    def _render(self, state: UpdateState) -> None:
        release = self.service.release
        checking = state is UpdateState.CHECKING
        downloading = state is UpdateState.DOWNLOADING
        verifying = state is UpdateState.VERIFYING
        available = state is UpdateState.AVAILABLE
        ready = state is UpdateState.READY

        self.check_button.setEnabled(not (checking or downloading or verifying))
        self.check_button.setText(
            t("updates.checking") if checking else t("updates.check_button")
        )
        self.auto_check.setEnabled(not (downloading or verifying))

        show_release = bool(release) and state in (
            UpdateState.AVAILABLE,
            UpdateState.DOWNLOADING,
            UpdateState.VERIFYING,
            UpdateState.READY,
        )
        self.notes_label.setVisible(show_release)
        self.notes_box.setVisible(show_release)
        self.notes_box.setPlainText(
            markdown_to_plain(release.notes if release is not None else "")
        )

        self.update_button.setVisible(available or ready)
        self.skip_button.setVisible(available)
        self.later_button.setVisible(available)
        self.update_button.setEnabled(available or ready)
        self.update_button.setText(
            t("updates.install_confirm_button") if ready else t("updates.update_now")
        )

        self._show_progress(downloading or verifying)
        self.cancel_button.setVisible(downloading)
        if not (downloading or verifying):
            self.progress_bar.setValue(0)
            self.progress_label.setText("")

        status = ""
        if checking:
            status = t("updates.checking")
        elif state is UpdateState.UP_TO_DATE:
            status = (
                t("updates.error_no_releases")
                if self._last_kind == "no_releases"
                else t("updates.up_to_date")
            )
        elif available and release is not None:
            status = t("updates.available_title", version=release.version_str)
            if release.published_dt is not None:
                status += " · " + t(
                    "updates.published_on",
                    date=format_date(release.published_dt.date()),
                )
        elif downloading:
            status = t("updates.downloading", percent=self._percent())
        elif verifying:
            status = t("updates.verifying")
        elif ready:
            status = f"{t('updates.ready_title')} — {t('updates.ready_message')}"
        elif state is UpdateState.ERROR:
            status = self.status_label.text()
        elif state is UpdateState.INSTALLING:
            status = t("updates.installing")
        self.status_label.setText(status)
        self.status_label.setVisible(bool(status) and state is not UpdateState.ERROR)

        if state is not UpdateState.ERROR:
            self.error_banner.setVisible(False)

        if release is not None and available:
            if self.service.is_skipped(release.version_str):
                self.update_button.setVisible(False)
                self.skip_button.setVisible(False)

    def _on_state_changed(self, value: str, _release) -> None:
        try:
            state = UpdateState(value)
        except ValueError:
            state = UpdateState.IDLE
        self._render(state)

    def _on_check_finished(self, result) -> None:
        self._last_kind = str(getattr(result, "kind", "") or "")
        self._retry_at = getattr(result, "retry_at", None)
        if self._last_kind == "no_releases":
            self.status_label.setText(t("updates.error_no_releases"))
            self.status_label.setVisible(True)
        self._refresh_last_checked()

    def _on_progress(self, done: int, total: int) -> None:
        percent = 0 if total <= 0 else min(100, int(done * 100 / total))
        self.progress_bar.setValue(percent)
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_label.setText(
            t(
                "updates.downloaded_size",
                done=format_size_mb(done),
                total=format_size_mb(total),
            )
        )
        if self.service.state is UpdateState.DOWNLOADING:
            self.status_label.setText(t("updates.downloading", percent=percent))

    def _on_cancelled(self) -> None:
        self._show_progress(False)
        self.status_label.setText("")
        self.status_label.setVisible(False)
        self._render(UpdateState.IDLE)

    def _on_error(self, code: str, fallback: str) -> None:
        # An automatic check stays quiet: the user did not ask for it.
        if self._last_action == "check" and getattr(self.service, "silent", False):
            return
        message = self._error_text(code, fallback)
        self.error_banner.set_title(
            t("updates.error_download_title")
            if self._last_action == "download"
            else t("updates.error_title")
        )
        self.error_banner.set_message(message)
        self.error_banner.setVisible(True)
        self.error_banner.set_kind("error")

    def _error_text(self, code: str, fallback: str) -> str:
        mapping = {
            "offline": "updates.error_offline",
            "rate_limited": "updates.error_rate_limited",
            "no_releases": "updates.error_no_releases",
            "missing_assets": "updates.error_missing_assets",
            "checksum_mismatch": "updates.error_checksum",
            "size_mismatch": "updates.error_size",
            "oversize": "updates.error_size",
            "bad_pe": "updates.error_pe",
            "bad_host": "updates.error_host",
            "bad_asset_name": "updates.error_name",
            "missing_checksum": "updates.error_missing_assets",
            "error_busy": "updates.error_busy",
        }
        key = mapping.get(code)
        if code == "rate_limited" and self._retry_at:
            try:
                retry_text = format_time(datetime.fromtimestamp(self._retry_at))
                return t(
                    "updates.error_rate_limited",
                    time=format_date(datetime.fromtimestamp(self._retry_at)) + " " + retry_text,
                )
            except (OSError, ValueError, OverflowError):
                pass
        if key:
            return t(key)
        return fallback or t("updates.error_generic")

    # ----------------------------------------------------------------- events
    def _on_check_clicked(self) -> None:
        self._last_action = "check"
        self._last_kind = ""
        self._retry_at = None
        self.error_banner.setVisible(False)
        self.service.check(silent=False)

    def _on_retry(self) -> None:
        if self._last_action == "download" and self.service.release is not None:
            self.service.start_download()
        else:
            self._on_check_clicked()

    def _on_update_now(self) -> None:
        if self._busy_checker():
            self._last_action = "install"
            self._on_error("error_busy", t("updates.error_busy"))
            return
        if self.service.installer_path is None:
            self._last_action = "download"
            self.service.start_download()
            return
        accepted = ConfirmDialog.ask(
            self,
            t("updates.install_confirm_title"),
            t("updates.install_confirm_message"),
            confirm_text=t("updates.install_confirm_button"),
            danger=False,
        )
        if not accepted:
            return
        self.install_requested.emit(self.service.installer_path)

    def _on_skip(self) -> None:
        self.service.skip_current()
        self.availability_changed.emit(False)
        self.status_label.setText(t("updates.skipped"))
        self.status_label.setVisible(True)
        self._render(UpdateState.IDLE)

    def _on_later(self) -> None:
        self.service.reset()
        self.status_label.setVisible(False)

    # --------------------------------------------------------------- last check
    def _refresh_last_checked(self) -> None:
        value = prefs.get_last_check()
        if value <= 0:
            text = t("updates.never_checked")
        else:
            try:
                text = t(
                    "updates.last_checked",
                    date=format_datetime(datetime.fromtimestamp(value)),
                )
            except (OSError, ValueError, OverflowError):
                text = t("updates.never_checked")
        self.last_checked_label.setText(text)

    # Retry-at plumbing used by the error text.
    def remember_retry_at(self, when: float | None) -> None:
        self._retry_at = when


def _small(label: QLabel, wrap: bool = True) -> QLabel:
    theme.apply_role(label, "small")
    label.setWordWrap(wrap)
    return label
