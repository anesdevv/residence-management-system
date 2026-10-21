"""RÉSIVO — Official university roster (visual layer only, docs/DESIGN.md §6–§7).

Drag-and-drop import card: a dashed ``border-strong`` drop zone with the upload
icon, the line "Drop a CSV or Excel file here, or choose a file" and the primary
"Import list" button. Dropped files (``.csv`` / ``.xlsx`` / ``.xls``) and the
button go through the *same* import method — no duplicated logic. Below it, the
roster preview table follows the DataTable language and the result summary
``InlineBanner`` reports real counts from the existing import result
(imported / skipped / errors).

The data layer is frozen: ``reload()`` keeps its query chain
(``official_residents`` ordered by ``card_id``), ``on_import()`` keeps the admin
role check, the file dialog, ``read_official_file(path)`` and the
``import_official_residents`` upsert payload (``{"p_rows": rows}``), and
``on_row_double_clicked`` keeps calling
``StudentInfoCardDialog(self, st_data, r)``.

After the constructor's first paint every roster read, file parse and import
RPC runs on the shared :class:`TaskRunner`; the file dialog stays on the GUI
thread.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
from ..theme import C, S

# Table language: overline headers are uppercased by ``configure_table``.
_COLUMNS = ["Card ID", "First Name", "Last Name", "Birth Date", "Gender", "University", "Faculty"]
# File types the import path accepts (button dialog and drag & drop alike).
_IMPORT_SUFFIXES = (".csv", ".xlsx", ".xls")

_IMPORT_TEXT = "Import list"
_WORKING_TEXT = "Working..."
_RELOAD_KEY = "official-reload"
_IMPORT_KEY = "official-import"
_ADMIN_ONLY_TOOLTIP = "Administrator privileges required to import roster."


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
        # Same import method as the button — no duplicated logic.
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
    """Official roster: import card, preview table and profile card dialog."""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        # Background I/O: the constructor keeps one synchronous first load;
        # every later refresh, file parse and import RPC runs on the pool.
        self.tasks = TaskRunner(self)
        self._initializing = True
        self._reload_busy = False
        self._import_busy = False
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
        self._apply_import_gate()
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
        toolbar.setSpacing(S("space-3"))

        self.search_field = SearchField(
            "Search official roster by card ID, student name, university, or faculty…"
        )
        self.search_field.changed.connect(self.filter_table)
        # Legacy alias: the search box used to be a bare ``QLineEdit``.
        self.search_input = self.search_field.edit
        toolbar.addWidget(self.search_field, 1)

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
            "Import a CSV or Excel list to seed the admissions database.",
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

        tip = _small_label("Preview of the official roster — double-click a record to open its profile card.")
        layout.addWidget(tip)

        self.reload()
        self._initializing = False

    # --------------------------------------------------------------- role
    def set_role(self, role) -> None:
        """Apply a late-verified role without rebuilding the page.

        MainWindow calls this after its background retry succeeds; the page
        only flips the import gate, while ``on_import()`` keeps its own check.
        """
        self.role = _normalize_role(role)
        self._apply_import_gate()

    def _apply_import_gate(self) -> None:
        """Import is admin-only and stays disabled while an import is running."""
        can_import = self.role == "admin" and not self._import_busy
        self.import_btn.setEnabled(can_import)
        self.import_btn.setToolTip("" if can_import else _ADMIN_ONLY_TOOLTIP)

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
        self.refresh_btn.setEnabled(not self._import_busy)
        if self._reload_pending:
            self._reload_pending = False
            self.reload()

    def _apply_rows(self, rows) -> None:
        """Render rows on the GUI thread, preserving search and card selection."""
        selected = self.rows[self.table.currentRow()] if 0 <= self.table.currentRow() < len(self.rows) else None
        selected_card = selected.get("card_id") if selected else None
        self.rows = [row for row in (rows or []) if isinstance(row, dict)]
        self.count_badge.setText(f"{len(self.rows)} Verified Records")
        self._render_rows()
        if selected_card is not None:
            for index, row in enumerate(self.rows):
                if row.get("card_id") == selected_card:
                    self.table.selectRow(index)
                    break
            else:
                self.table.clearSelection()
                self.table.setCurrentCell(-1, -1)

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

    def _on_import_finished(self) -> None:
        self._import_busy = False
        self.import_btn.setText(_IMPORT_TEXT)
        self._apply_import_gate()
        self.refresh_btn.setEnabled(not self._reload_busy)
        self.drop_zone.setAcceptDrops(True)

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

    def _on_import_failed(self, message: str) -> None:
        self._show_import_result(False, imported=0, skipped=0, errors=1, detail=message)
