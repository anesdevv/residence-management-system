"""RÉSIVO — Official university roster (visual layer only, docs/DESIGN.md §6–§7).

Drag-and-drop import card: a dashed ``border-strong`` drop zone with the upload
icon, the line "Drop a CSV or Excel file here, or choose a file" and the primary
"Import list" button. Dropped files (``.csv`` / ``.xlsx`` / ``.xls``) and the
button go through the *same* import method — no duplicated logic. Below it, the
roster preview table follows the DataTable language and the result summary
``InlineBanner`` reports real counts from the existing import result
(imported / skipped / errors).

Admins can also manually add, edit, delete selected, and clear all roster records.
Non-admin staff are restricted to read-only access.
All data mutations run off the GUI thread with double-click protection and busy states.
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...importers.official_list import read_official_file
from .. import theme
from ..components import (
    Button,
    Card,
    ConfirmDialog,
    EmptyState,
    IconButton,
    InlineBanner,
    PageHeader,
    SearchField,
    Skeleton,
    StatusPill,
    configure_table,
)
from ..icons import get_icon, get_pixmap
from ..infocard import StudentInfoCardDialog
from ..tasks import TaskRunner, human_error
from ..theme import C, DESKTOP_STYLESHEET, S

# Table language: overline headers are uppercased by ``configure_table``.
_COLUMNS = ["Card ID", "First Name", "Last Name", "Birth Date", "Gender", "University", "Faculty"]
# File types the import path accepts (button dialog and drag & drop alike).
_IMPORT_SUFFIXES = (".csv", ".xlsx", ".xls")

_IMPORT_TEXT = "Import list"
_WORKING_TEXT = "Working..."
_RELOAD_KEY = "official-reload"
_IMPORT_KEY = "official-import"
_ACTION_KEY = "official-action"

_ADMIN_MODIFY_TOOLTIP = "Only administrators can modify the official list"
_ADMIN_IMPORT_TOOLTIP = "Administrator privileges required to import roster."


def _normalize_role(role) -> str | None:
    """Case/whitespace-insensitive role value (``" Admin "`` -> ``"admin"``)."""
    if role is None:
        return None
    normalized = str(role).strip().lower()
    return normalized or None


def _fit_columns(table: QTableWidget, modes: list) -> QHeaderView:
    """Apply per-column resize modes (no column keeps a hard-coded width)."""
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    for column, mode in enumerate(modes):
        header.setSectionResizeMode(column, mode)
    return header


def _small_label(text: str) -> QLabel:
    """Secondary 12 px line (typography role ``small``)."""
    label = QLabel(text)
    theme.apply_role(label, "small")
    return label


class OfficialResidentDialog(QDialog):
    """Add or edit an official resident admissions record."""

    def __init__(self, parent=None, client=None, mode: str = "add", initial_data: dict | None = None):
        super().__init__(parent)
        self.client = client
        self.mode = mode
        self.initial_data = dict(initial_data or {})
        self.old_card_id = str(self.initial_data.get("card_id") or "").strip()
        self.tasks = TaskRunner(self)
        self._busy = False
        self._closing = False
        self.result_data = None

        self.setWindowTitle("Edit Official Resident" if mode == "edit" else "Add Official Resident")
        self.setMinimumWidth(440)
        self.setModal(True)
        self.setStyleSheet(DESKTOP_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        layout.setSpacing(S("space-4"))

        card = Card(
            "Official resident details" if mode == "edit" else "New official resident",
            "Update the verified admissions registry details." if mode == "edit" else "Enter verified student details into the official admissions roster.",
            icon="official_list",
        )

        form = QFormLayout()
        form.setSpacing(S("space-3"))
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.card_id_edit = QLineEdit()
        self.card_id_edit.setPlaceholderText("e.g. 202437010001")
        self.card_id_edit.setText(str(self.initial_data.get("card_id") or ""))

        self.first_name_edit = QLineEdit()
        self.first_name_edit.setPlaceholderText("First name")
        self.first_name_edit.setText(str(self.initial_data.get("first_name") or ""))

        self.last_name_edit = QLineEdit()
        self.last_name_edit.setPlaceholderText("Last name")
        self.last_name_edit.setText(str(self.initial_data.get("last_name") or ""))

        self.birth_date_edit = QLineEdit()
        self.birth_date_edit.setPlaceholderText("YYYY-MM-DD")
        self.birth_date_edit.setText(str(self.initial_data.get("birth_date") or ""))

        self.gender_combo = QComboBox()
        self.gender_combo.addItem("Select gender…", "")
        self.gender_combo.addItem("Male", "male")
        self.gender_combo.addItem("Female", "female")
        curr_gender = str(self.initial_data.get("gender") or "").lower()
        if curr_gender == "male":
            self.gender_combo.setCurrentIndex(1)
        elif curr_gender == "female":
            self.gender_combo.setCurrentIndex(2)
        else:
            self.gender_combo.setCurrentIndex(0)

        self.university_edit = QLineEdit()
        self.university_edit.setPlaceholderText("University name")
        self.university_edit.setText(str(self.initial_data.get("university") or ""))

        self.faculty_edit = QLineEdit()
        self.faculty_edit.setPlaceholderText("Faculty or department")
        self.faculty_edit.setText(str(self.initial_data.get("faculty") or ""))

        form.addRow("Card ID *:", self.card_id_edit)
        form.addRow("First Name *:", self.first_name_edit)
        form.addRow("Last Name *:", self.last_name_edit)
        form.addRow("Birth Date:", self.birth_date_edit)
        form.addRow("Gender:", self.gender_combo)
        form.addRow("University:", self.university_edit)
        form.addRow("Faculty:", self.faculty_edit)

        card.add_layout(form)

        self.error_banner = InlineBanner("error", title="Validation Error", message="")
        self.error_banner.setVisible(False)
        card.add_widget(self.error_banner)

        layout.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(S("space-2"))
        btn_row.addStretch(1)

        self.cancel_btn = Button.secondary("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        save_label = "Save changes" if mode == "edit" else "Add resident"
        self.save_btn = Button.primary(save_label)
        self.save_btn.clicked.connect(self.on_save)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.save_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(not busy)
        if busy:
            self.save_btn.setText(_WORKING_TEXT)
        else:
            self.save_btn.setText("Save changes" if self.mode == "edit" else "Add resident")

    def _show_error(self, message: str, title: str = "Validation Error") -> None:
        self.error_banner.set_kind("error")
        self.error_banner.set_title(title)
        self.error_banner.set_message(message)
        self.error_banner.setVisible(True)

    def on_save(self) -> None:
        if self._busy:
            return

        card_id = self.card_id_edit.text().strip()
        first_name = self.first_name_edit.text().strip()
        last_name = self.last_name_edit.text().strip()
        birth_date = self.birth_date_edit.text().strip() or None
        gender = self.gender_combo.currentData() or None
        university = self.university_edit.text().strip() or None
        faculty = self.faculty_edit.text().strip() or None

        if not card_id:
            self._show_error("Card ID is required.")
            self.card_id_edit.setFocus()
            return
        if not first_name:
            self._show_error("First name is required.")
            self.first_name_edit.setFocus()
            return
        if not last_name:
            self._show_error("Last name is required.")
            self.last_name_edit.setFocus()
            return

        if birth_date:
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", birth_date):
                self._show_error("Birth date must be in YYYY-MM-DD format.")
                self.birth_date_edit.setFocus()
                return

        if self.mode == "edit":
            rpc_name = "update_official_resident"
            params = {
                "p_old_card_id": self.old_card_id,
                "p_card_id": card_id,
                "p_first_name": first_name,
                "p_last_name": last_name,
                "p_birth_date": birth_date,
                "p_gender": gender,
                "p_university": university,
                "p_faculty": faculty,
            }
        else:
            rpc_name = "add_official_resident"
            params = {
                "p_card_id": card_id,
                "p_first_name": first_name,
                "p_last_name": last_name,
                "p_birth_date": birth_date,
                "p_gender": gender,
                "p_university": university,
                "p_faculty": faculty,
            }

        if not self.isVisible():
            if self.client:
                try:
                    resp = self.client.rpc(rpc_name, params).execute()
                    self.result_data = getattr(resp, "data", None)
                except Exception as exc:
                    self._on_save_failed(human_error(exc))
                    return
            self.accept()
            return

        self._set_busy(True)
        started = self.tasks.run(
            "official-save",
            lambda: self.client.rpc(rpc_name, params).execute() if self.client else None,
            on_success=self._on_save_success,
            on_failed=self._on_save_failed,
            on_finished=lambda: self._set_busy(False),
        )
        if not started:
            self._set_busy(False)

    def _on_save_success(self, resp) -> None:
        self.result_data = getattr(resp, "data", None)
        self.accept()

    def _on_save_failed(self, message: str) -> None:
        title = "Card ID Already Exists" if "already exists" in message.lower() else "Save Failed"
        self._show_error(message, title=title)


class ClearAllRosterDialog(QDialog):
    """Strong confirmation dialog requiring the user to type DELETE."""

    def __init__(self, parent=None, total_count: int = 0, matching_pending: int = 0):
        super().__init__(parent)
        self.confirmed = False
        self.setWindowTitle("Clear Official Admissions Roster")
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setStyleSheet(DESKTOP_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        layout.setSpacing(S("space-4"))

        head = QHBoxLayout()
        head.setSpacing(S("space-3"))
        icon = QLabel()
        icon.setPixmap(get_pixmap("alert-triangle", 24, C("status-danger-ink")))
        head.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        column = QVBoxLayout()
        column.setSpacing(S("space-1"))
        title_label = QLabel("Delete all official admissions records?")
        theme.apply_role(title_label, "h2")
        column.addWidget(title_label)

        warn_text = f"This action will permanently delete all {total_count} records from the official roster."
        if matching_pending > 0:
            warn_text += f"\n\nWarning: {matching_pending} pending student application(s) will lose their roster match."
        warn_text += "\n\nTo confirm, please type DELETE below:"

        msg_label = QLabel(warn_text)
        theme.apply_role(msg_label, "muted")
        msg_label.setWordWrap(True)
        column.addWidget(msg_label)
        head.addLayout(column, 1)
        layout.addLayout(head)

        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Type DELETE to confirm")
        self.confirm_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.confirm_input)

        buttons = QHBoxLayout()
        buttons.setSpacing(S("space-2"))
        buttons.addStretch(1)

        self.cancel_button = Button.secondary("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)

        self.delete_button = Button.danger("Delete all")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._on_confirm)
        buttons.addWidget(self.delete_button)

        layout.addLayout(buttons)

    def _on_text_changed(self, text: str) -> None:
        self.delete_button.setEnabled(text.strip() == "DELETE")

    def _on_confirm(self) -> None:
        if self.confirm_input.text().strip() == "DELETE":
            self.confirmed = True
            self.accept()


class _RosterDropZone(QFrame):
    """Dashed drop target for a roster file.

    The zone owns only the drag & drop plumbing: an accepted drop calls the
    page's existing import method with the dropped file path, so the button and
    the drop share one code path.
    """

    def __init__(self, import_handler, parent=None):
        super().__init__(parent)
        self._import_handler = import_handler
        self.setObjectName("rosterDropZone")
        self.setProperty("dragActive", False)
        self.setAcceptDrops(True)
        self._apply_style()

        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        self.body.setSpacing(S("space-2"))

    # -- drag & drop --------------------------------------------------------
    def dragEnterEvent(self, event):  # noqa: N802 - Qt API
        if self._dropped_path(event.mimeData()):
            self._set_drag_active(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):  # noqa: N802 - Qt API
        self._set_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):  # noqa: N802 - Qt API
        path = self._dropped_path(event.mimeData())
        self._set_drag_active(False)
        if not path:
            event.ignore()
            return
        event.acceptProposedAction()
        self._import_handler(path)

    @staticmethod
    def _dropped_path(mime) -> str:
        """First local file URL with an accepted roster suffix, else ``""``."""
        if mime is None or not mime.hasUrls():
            return ""
        for url in mime.urls():
            path = url.toLocalFile()
            if path and path.lower().endswith(_IMPORT_SUFFIXES):
                return path
        return ""

    # -- styling ------------------------------------------------------------
    def _style_qss(self) -> str:
        active = bool(self.property("dragActive"))
        border = C("teal-600") if active else C("border-strong")
        background = C("selection-tint") if active else C("surface-subtle")
        return (
            f"QFrame#rosterDropZone {{ background-color: {background};"
            f" border: 2px dashed {border}; border-radius: {C('radius-card')}; }}"
        )

    def _apply_style(self) -> None:
        self.setStyleSheet(self._style_qss())

    def _set_drag_active(self, active: bool) -> None:
        if self.property("dragActive") != active:
            self.setProperty("dragActive", active)
            self._apply_style()


class OfficialListPage(QWidget):
    """Official roster: import card, preview table, edit/delete/clear actions, and profile dialog."""

    roster_changed = Signal()

    def __init__(self, client, pending_page=None):
        super().__init__()
        self.client = client
        self.pending_page = pending_page
        self.rows: list[dict] = []

        # Background I/O: the constructor keeps one synchronous first load;
        # every later refresh, file parse, action and import RPC runs on the pool.
        self.tasks = TaskRunner(self)
        self._initializing = True
        self._reload_busy = False
        self._import_busy = False
        self._action_busy = False
        self._reload_pending = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-8"), S("space-8"), S("space-8"), S("space-8"))
        layout.setSpacing(S("space-6"))

        self.header = PageHeader(
            "Official university roster",
            "Master admissions database used to verify student housing applications.",
        )
        self.count_badge = StatusPill("neutral", "0 Verified Records")
        self.header.actions.addWidget(self.count_badge)
        layout.addWidget(self.header)

        from ...client import current_role
        self.role = _normalize_role(current_role(client))

        # ------------------------------------------------- import drop zone
        self.drop_zone = _RosterDropZone(self.on_import)
        drop_body = self.drop_zone.body
        drop_body.addStretch(1)

        upload_icon = QLabel()
        upload_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        upload_icon.setPixmap(get_pixmap("upload", 28, C("teal-600")))
        drop_body.addWidget(upload_icon, 0, Qt.AlignmentFlag.AlignHCenter)

        drop_title = QLabel("Import the official roster")
        theme.apply_role(drop_title, "h3")
        drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_body.addWidget(drop_title)

        drop_hint = _small_label("Drop a CSV or Excel file here, or choose a file")
        drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_body.addWidget(drop_hint)

        self.import_btn = Button.primary("Import list", icon="upload")
        self.import_btn.clicked.connect(lambda _checked=False: self.on_import())
        drop_body.addWidget(self.import_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        drop_body.addStretch(1)
        layout.addWidget(self.drop_zone)

        # -------------------------------------------------- result summary
        self.result_banner = InlineBanner(
            "success",
            title="Roster import",
            message="",
        )
        self.result_banner.setVisible(False)
        layout.addWidget(self.result_banner)

        self.error_banner = InlineBanner(
            "error",
            title="Roster could not be loaded",
            message="Check the connection, then use Refresh to try again.",
        )
        self.error_banner.setVisible(False)
        layout.addWidget(self.error_banner)

        # -------------------------------------------------------- toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(S("space-2"))

        self.search_field = SearchField(
            "Search official roster by card ID, student name, university, or faculty…"
        )
        self.search_field.changed.connect(self.filter_table)
        self.search_input = self.search_field.edit
        toolbar.addWidget(self.search_field, 1)

        self.add_btn = Button.primary("Add entry", icon="plus")
        self.add_btn.clicked.connect(lambda _checked=False: self.on_add())
        toolbar.addWidget(self.add_btn)

        self.edit_btn = Button.secondary("Edit", icon="edit")
        self.edit_btn.clicked.connect(lambda _checked=False: self.on_edit())
        toolbar.addWidget(self.edit_btn)

        self.delete_selected_btn = Button.danger("Delete selected", icon="trash")
        self.delete_selected_btn.clicked.connect(lambda _checked=False: self.on_delete_selected())
        toolbar.addWidget(self.delete_selected_btn)

        self.delete_all_btn = Button.danger("Delete all", icon="trash")
        self.delete_all_btn.clicked.connect(lambda _checked=False: self.on_delete_all())
        toolbar.addWidget(self.delete_all_btn)

        self.refresh_btn = IconButton("refresh", "Reload the official roster")
        self.refresh_btn.clicked.connect(self.reload)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        # ------------------------------------------------- preview table
        table_card = QFrame()
        table_card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.table = QTableWidget(0, len(_COLUMNS))
        configure_table(self.table, _COLUMNS)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._update_action_states)

        _fit_columns(
            self.table,
            [
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.Stretch,
                QHeaderView.ResizeMode.Stretch,
            ],
        )
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        self.stack.addWidget(self.table)

        self.empty_no_data = EmptyState(
            "file-spreadsheet",
            "No roster records yet",
            "Import a CSV or Excel list or add entries to seed the admissions database.",
        )
        self.empty_no_match = EmptyState(
            "search",
            "No roster record matches",
            "Clear the search field to see the full official list again.",
        )
        self.stack.addWidget(self.empty_no_data)
        self.stack.addWidget(self.empty_no_match)

        self.skeleton = Skeleton(rows=6)
        self.stack.addWidget(self.skeleton)

        card_layout.addWidget(self.stack)
        layout.addWidget(table_card, 1)

        tip = _small_label("Official admissions roster — select entries to edit or delete, or double-click to view profile.")
        layout.addWidget(tip)

        self._apply_import_gate()
        self._update_action_states()

        self.reload()
        self._initializing = False

    # --------------------------------------------------------------- role & gating
    def set_role(self, role) -> None:
        """Apply a late-verified role without rebuilding the page."""
        self.role = _normalize_role(role)
        self._apply_import_gate()
        self._update_action_states()

    def _is_busy(self) -> bool:
        return bool(self._action_busy or self._import_busy or self._reload_busy)

    def _apply_import_gate(self) -> None:
        """Import is admin-only and stays disabled while an import is running."""
        can_import = self.role == "admin" and not self._import_busy
        self.import_btn.setEnabled(can_import)
        self.import_btn.setToolTip("" if can_import else _ADMIN_IMPORT_TOOLTIP)
        self._update_action_states()

    def _selected_row_indices(self) -> list[int]:
        """Distinct row indices currently selected in the table."""
        if not self.table.selectionModel():
            return []
        selected_indexes = self.table.selectionModel().selectedRows()
        return sorted({index.row() for index in selected_indexes if 0 <= index.row() < len(self.rows)})

    def _update_action_states(self) -> None:
        """Update write action button enabled states and tooltips based on role and selection."""
        is_admin = self.role == "admin"
        busy = self._is_busy()
        sel = self._selected_row_indices()

        can_write = is_admin and not busy

        self.add_btn.setEnabled(can_write)
        self.edit_btn.setEnabled(can_write and len(sel) == 1)
        self.delete_selected_btn.setEnabled(can_write and len(sel) > 0)
        self.delete_all_btn.setEnabled(can_write and len(self.rows) > 0)

        if not is_admin:
            self.add_btn.setToolTip(_ADMIN_MODIFY_TOOLTIP)
            self.edit_btn.setToolTip(_ADMIN_MODIFY_TOOLTIP)
            self.delete_selected_btn.setToolTip(_ADMIN_MODIFY_TOOLTIP)
            self.delete_all_btn.setToolTip(_ADMIN_MODIFY_TOOLTIP)
        else:
            self.add_btn.setToolTip("Add a verified student record manually")
            self.edit_btn.setToolTip("Edit selected admissions record" if len(sel) == 1 else "Select exactly one entry to edit")
            self.delete_selected_btn.setToolTip("Delete selected admissions records" if len(sel) > 0 else "Select one or more entries to delete")
            self.delete_all_btn.setToolTip("Clear all records from admissions roster" if len(self.rows) > 0 else "Roster is empty")

    def _count_matching_pending(self, card_ids: set[str]) -> int:
        """Count pending applications matching any of the given card IDs."""
        if not card_ids:
            return 0
        if self.pending_page and hasattr(self.pending_page, "all_rows"):
            return sum(
                1 for s in self.pending_page.all_rows
                if str(s.get("status") or "").lower() == "pending"
                and str(s.get("card_id") or "") in card_ids
            )
        try:
            resp = self.client.table("students").select("card_id").eq("status", "pending").execute()
            data = getattr(resp, "data", []) or []
            return sum(1 for s in data if str(s.get("card_id") or "") in card_ids)
        except Exception:
            return 0

    def _notify_roster_changed(self) -> None:
        """Notify MainWindow and PendingPage that official admissions data has changed."""
        self.roster_changed.emit()
        if self.pending_page and hasattr(self.pending_page, "reload"):
            self.pending_page.reload()

    # --------------------------------------------------------------- data
    def reload(self):
        """Load the roster; the constructor keeps its synchronous first paint."""
        if self._initializing:
            self._load_sync()
            return
        self._reload_async()

    def _load_sync(self) -> None:
        """Initial load only (keeps the constructor contract synchronous)."""
        self._set_loading(True)
        try:
            rows = self._fetch_roster()
        except Exception as exc:  # noqa: BLE001 - reported inline
            self._on_reload_failed(human_error(exc))
        else:
            self._on_reload_success(rows)

    def _reload_async(self) -> None:
        if self._reload_busy:
            self._reload_pending = True
            return
        self._reload_busy = True
        self.refresh_btn.setEnabled(False)
        self._set_loading(True)
        started = self.tasks.run(
            _RELOAD_KEY,
            self._fetch_roster,
            on_success=self._on_reload_success,
            on_failed=self._on_reload_failed,
            on_finished=self._on_reload_finished,
        )
        if not started:
            self._reload_busy = False
            self.refresh_btn.setEnabled(True)
            self._set_loading(False)

    def _fetch_roster(self) -> list[dict]:
        """Network read of the official roster (never call from the GUI thread)."""
        resp = self.client.table("official_residents").select("*").order("card_id").execute()
        data = getattr(resp, "data", None)
        return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []

    def _on_reload_success(self, rows) -> None:
        self.error_banner.setVisible(False)
        self._apply_rows(rows)
        self._set_loading(False)

    def _on_reload_failed(self, message: str) -> None:
        self.error_banner.set_message(
            f"The official roster could not be loaded ({message}). "
            "Check the connection, then use Refresh to try again."
        )
        self.error_banner.setVisible(True)
        self._set_loading(False)

    def _on_reload_finished(self) -> None:
        self._reload_busy = False
        self.refresh_btn.setEnabled(not self._import_busy and not self._action_busy)
        self._apply_import_gate()
        self._update_action_states()
        if self._reload_pending:
            self._reload_pending = False
            self.reload()

    def _apply_rows(self, rows) -> None:
        """Render rows on the GUI thread, preserving search and card selection."""
        selected_card_ids = {
            self.rows[idx].get("card_id") for idx in self._selected_row_indices()
            if self.rows[idx].get("card_id")
        }
        self.rows = [row for row in (rows or []) if isinstance(row, dict)]
        self.count_badge.setText(f"{len(self.rows)} Verified Records")
        self._render_rows()

        # Restore multi-selection if cards still exist
        if selected_card_ids:
            for index, row in enumerate(self.rows):
                if row.get("card_id") in selected_card_ids:
                    self.table.selectRow(index)
        self._update_action_states()

    def _render_rows(self):
        self.table.setRowCount(len(self.rows))

        for i, r in enumerate(self.rows):
            card_item = QTableWidgetItem(str(r.get("card_id") or ""))
            card_item.setIcon(get_icon("official_list", 14, C("teal-600")))
            self.table.setItem(i, 0, card_item)
            self.table.setItem(i, 1, QTableWidgetItem(str(r.get("first_name") or "")))
            self.table.setItem(i, 2, QTableWidgetItem(str(r.get("last_name") or "")))
            self.table.setItem(i, 3, QTableWidgetItem(str(r.get("birth_date") or "")))
            self.table.setItem(i, 4, QTableWidgetItem(str(r.get("gender") or "").capitalize()))
            self.table.setItem(i, 5, QTableWidgetItem(str(r.get("university") or "")))
            self.table.setItem(i, 6, QTableWidgetItem(str(r.get("faculty") or "")))

        self.filter_table()

    def filter_table(self):
        needle = self.search_input.text().lower().strip()
        for r in range(self.table.rowCount()):
            row_data = self.rows[r] if r < len(self.rows) else {}
            haystack = f"{row_data.get('card_id', '')} {row_data.get('first_name', '')} {row_data.get('last_name', '')} {row_data.get('university', '')} {row_data.get('faculty', '')}".lower()
            self.table.setRowHidden(r, needle not in haystack)

        self._update_empty_state()
        self._update_action_states()

    # ------------------------------------------------------------ rendering
    def _set_loading(self, loading: bool) -> None:
        """Swap the preview table for the Skeleton while a load is in flight."""
        if loading:
            self.stack.setCurrentWidget(self.skeleton)
            self.skeleton.raise_()
        else:
            self._update_empty_state()

    def _update_empty_state(self) -> None:
        """Table / "no match" / "no records" — never a blank area."""
        if not self.rows:
            self.stack.setCurrentWidget(self.empty_no_data)
            return
        visible = sum(
            1 for row in range(self.table.rowCount()) if not self.table.isRowHidden(row)
        )
        self.stack.setCurrentWidget(self.table if visible else self.empty_no_match)

    def _show_import_result(self, ok: bool, imported: int, skipped: int, errors: int, detail: str = "") -> None:
        """Result summary banner with the real counts of the import that ran."""
        self.result_banner.set_kind("success" if ok else "error")
        self.result_banner.set_title("Roster import completed" if ok else "Roster import failed")
        message = f"Imported {imported} · Skipped {skipped} · Errors {errors}"
        if detail:
            message = f"{message} — {detail}"
        self.result_banner.set_message(message)
        self.result_banner.setVisible(True)

    # -------------------------------------------------------------- dialogs
    def on_row_double_clicked(self, row: int, col: int):
        if 0 <= row < len(self.rows):
            r = self.rows[row]
            st_data = {
                "card_id": r.get("card_id"),
                "first_name": r.get("first_name"),
                "last_name": r.get("last_name"),
                "birth_date": r.get("birth_date"),
                "gender": r.get("gender"),
                "university": r.get("university"),
                "faculty": r.get("faculty"),
                "status": "active",
            }
            dlg = StudentInfoCardDialog(self, st_data, r)
            dlg.exec()

    # --------------------------------------------------------------- edit/add/delete actions
    def on_add(self):
        if self._is_busy():
            return
        if self.role != "admin":
            QMessageBox.warning(self, "Permission Denied", _ADMIN_MODIFY_TOOLTIP)
            return
        dlg = OfficialResidentDialog(self, client=self.client, mode="add")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            card_id = dlg.card_id_edit.text().strip()
            self.result_banner.set_kind("success")
            self.result_banner.set_title("Roster entry added")
            self.result_banner.set_message(f"Added record for {dlg.first_name_edit.text().strip()} {dlg.last_name_edit.text().strip()} ({card_id}).")
            self.result_banner.setVisible(True)
            self.reload()
            self._notify_roster_changed()

    def on_edit(self, row_index: int | None = None):
        if self._is_busy():
            return
        if self.role != "admin":
            QMessageBox.warning(self, "Permission Denied", _ADMIN_MODIFY_TOOLTIP)
            return
        if row_index is None:
            sel = self._selected_row_indices()
            if len(sel) != 1:
                return
            row_index = sel[0]
        if not (0 <= row_index < len(self.rows)):
            return
        row_data = self.rows[row_index]
        dlg = OfficialResidentDialog(self, client=self.client, mode="edit", initial_data=row_data)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            card_id = dlg.card_id_edit.text().strip()
            self.result_banner.set_kind("success")
            self.result_banner.set_title("Roster entry updated")
            self.result_banner.set_message(f"Updated record for {dlg.first_name_edit.text().strip()} {dlg.last_name_edit.text().strip()} ({card_id}).")
            self.result_banner.setVisible(True)
            self.reload()
            self._notify_roster_changed()

    def on_delete_selected(self):
        if self._is_busy() or self.tasks.is_busy(_ACTION_KEY):
            return
        if self.role != "admin":
            QMessageBox.warning(self, "Permission Denied", _ADMIN_MODIFY_TOOLTIP)
            return
        sel = self._selected_row_indices()
        if not sel:
            return
        card_ids = [str(self.rows[i].get("card_id") or "") for i in sel if self.rows[i].get("card_id")]
        if not card_ids:
            return

        matching = self._count_matching_pending(set(card_ids))
        msg = f"Are you sure you want to delete {len(card_ids)} selected roster entry(ies)?"
        if matching > 0:
            msg += f"\n\nWarning: {matching} pending application(s) will lose their roster match."

        if not ConfirmDialog.ask(self, "Delete selected roster entries", msg, confirm_text="Delete", danger=True):
            return

        self._begin_action()
        started = self.tasks.run(
            _ACTION_KEY,
            lambda: self._delete_entries_worker(card_ids),
            on_success=lambda count: self._on_delete_selected_complete(len(card_ids), count),
            on_failed=self._on_action_failed,
            on_finished=self._on_action_finished,
        )
        if not started:
            self._on_action_finished()

    def _delete_entries_worker(self, card_ids: list[str]) -> int:
        resp = self.client.rpc("delete_official_residents", {"p_card_ids": card_ids}).execute()
        count = getattr(resp, "data", len(card_ids))
        return int(count) if isinstance(count, (int, float)) else len(card_ids)

    def _on_delete_selected_complete(self, requested_count: int, deleted_count: int) -> None:
        self.result_banner.set_kind("success")
        self.result_banner.set_title("Roster entries deleted")
        self.result_banner.set_message(f"Successfully deleted {deleted_count} roster record(s).")
        self.result_banner.setVisible(True)
        self.reload()
        self._notify_roster_changed()

    def on_delete_all(self):
        if self._is_busy() or self.tasks.is_busy(_ACTION_KEY):
            return
        if self.role != "admin":
            QMessageBox.warning(self, "Permission Denied", _ADMIN_MODIFY_TOOLTIP)
            return
        if not self.rows:
            return

        all_card_ids = {str(r.get("card_id") or "") for r in self.rows if r.get("card_id")}
        matching = self._count_matching_pending(all_card_ids)

        dlg = ClearAllRosterDialog(self, total_count=len(self.rows), matching_pending=matching)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.confirmed:
            return

        self._begin_action()
        started = self.tasks.run(
            _ACTION_KEY,
            self._clear_all_worker,
            on_success=self._on_clear_all_complete,
            on_failed=self._on_action_failed,
            on_finished=self._on_action_finished,
        )
        if not started:
            self._on_action_finished()

    def _clear_all_worker(self) -> int:
        resp = self.client.rpc("clear_official_residents", {}).execute()
        count = getattr(resp, "data", len(self.rows))
        return int(count) if isinstance(count, (int, float)) else len(self.rows)

    def _on_clear_all_complete(self, deleted_count: int) -> None:
        self.result_banner.set_kind("success")
        self.result_banner.set_title("Official roster cleared")
        self.result_banner.set_message(f"Successfully cleared admissions roster (deleted {deleted_count} records).")
        self.result_banner.setVisible(True)
        self.reload()
        self._notify_roster_changed()

    def _begin_action(self) -> None:
        self._action_busy = True
        self.refresh_btn.setEnabled(False)
        self.import_btn.setEnabled(False)
        self.add_btn.setEnabled(False)
        self.edit_btn.setEnabled(False)
        self.delete_selected_btn.setEnabled(False)
        self.delete_all_btn.setEnabled(False)
        self.table.setEnabled(False)

    def _on_action_failed(self, message: str) -> None:
        self.result_banner.set_kind("error")
        self.result_banner.set_title("Action failed")
        self.result_banner.set_message(message)
        self.result_banner.setVisible(True)

    def _on_action_finished(self) -> None:
        self._action_busy = False
        self.table.setEnabled(True)
        self.refresh_btn.setEnabled(not self._reload_busy and not self._import_busy)
        self._apply_import_gate()
        self._update_action_states()

    # --------------------------------------------------------------- import
    def on_import(self, path: str | None = None):
        """Import a roster file — the one path used by the button and by drops.

        ``path`` is ``None`` for the button (a file dialog opens); drag & drop
        passes the dropped file path. Role validation and the file dialog stay
        on the GUI thread; the file parse and the import RPC run on the pool.
        """
        if self._import_busy or self.tasks.is_busy(_IMPORT_KEY):
            return
        if self.role != "admin":
            QMessageBox.warning(self, "Permission Denied", "Importing the official residents list requires administrator privileges.")
            return
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Open Official Roster File", "", "Spreadsheets (*.xlsx *.csv)")
        if not path:
            return

        self._begin_import()
        started = self.tasks.run(
            _IMPORT_KEY,
            lambda: self._import_file(path),
            on_success=self._on_import_complete,
            on_failed=self._on_import_failed,
            on_finished=self._on_import_finished,
        )
        if not started:
            self._on_import_finished()

    def _begin_import(self) -> None:
        self._import_busy = True
        self.import_btn.setText(_WORKING_TEXT)
        self.import_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.drop_zone.setAcceptDrops(False)
        self._update_action_states()

    def _on_import_finished(self) -> None:
        self._import_busy = False
        self.import_btn.setText(_IMPORT_TEXT)
        self._apply_import_gate()
        self.refresh_btn.setEnabled(not self._reload_busy and not self._action_busy)
        self.drop_zone.setAcceptDrops(True)
        self._update_action_states()

    def _import_file(self, path: str) -> dict:
        """Parse the spreadsheet and run the import RPC (worker thread)."""
        try:
            rows = read_official_file(path)
        except Exception as exc:  # noqa: BLE001 - reported in the result banner
            return {"ok": False, "path": path, "rows": 0, "error": human_error(exc)}
        try:
            resp = self.client.rpc("import_official_residents", {"p_rows": rows}).execute()
        except Exception as exc:  # noqa: BLE001 - reported in the result banner
            return {"ok": False, "path": path, "rows": len(rows), "error": human_error(exc)}
        return {
            "ok": True,
            "path": path,
            "rows": len(rows),
            "reported": getattr(resp, "data", None),
        }

    def _on_import_complete(self, result: dict) -> None:
        if not result.get("ok"):
            self._show_import_result(
                False,
                imported=0,
                skipped=int(result.get("rows") or 0),
                errors=1,
                detail=str(result.get("error") or "Import failed"),
            )
            return
        rows_count = int(result.get("rows") or 0)
        reported = result.get("reported")
        imported = reported if isinstance(reported, int) and not isinstance(reported, bool) else rows_count
        skipped = max(0, rows_count - imported)
        self._show_import_result(
            True,
            imported=imported,
            skipped=skipped,
            errors=0,
            detail=Path(result.get("path") or "").name,
        )
        self.reload()
        self._notify_roster_changed()

    def _on_import_failed(self, message: str) -> None:
        self._show_import_result(False, imported=0, skipped=0, errors=1, detail=message)
