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
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
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
from ..theme import C, S

# Table language: overline headers are uppercased by ``configure_table``.
_COLUMNS = ["Card ID", "First Name", "Last Name", "Birth Date", "Gender", "University", "Faculty"]
# File types the import path accepts (button dialog and drag & drop alike).
_IMPORT_SUFFIXES = (".csv", ".xlsx", ".xls")


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
        self.role = current_role(client)

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
        if self.role != "admin":
            self.import_btn.setEnabled(False)
            self.import_btn.setToolTip("Administrator privileges required to import roster.")
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

    # --------------------------------------------------------------- data
    def reload(self):
        self._set_loading(True)
        try:
            resp = self.client.table("official_residents").select("*").order("card_id").execute()
            data = getattr(resp, "data", None)
            self.rows = [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []
        except Exception as exc:  # noqa: BLE001
            self.error_banner.set_message(
                f"The official roster could not be loaded ({exc}). "
                "Check the connection, then use Refresh to try again."
            )
            self.error_banner.setVisible(True)
            self._set_loading(False)
            return
        self.error_banner.setVisible(False)
        self.count_badge.setText(f"{len(self.rows)} Verified Records")
        self._render_rows()
        self._set_loading(False)

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
        """Swap the preview table for the Skeleton while ``reload()`` runs."""
        if loading:
            self.stack.setCurrentWidget(self.skeleton)
            self.skeleton.raise_()
            app = QApplication.instance()
            if app is not None and self.isVisible():
                # Let the placeholder paint before the (blocking) query runs.
                app.processEvents()
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
        passes the dropped file path. The admin check, ``read_official_file``
        and the ``import_official_residents`` upsert payload are unchanged.
        """
        from ...client import current_role
        if current_role(self.client) != "admin":
            QMessageBox.warning(self, "Permission Denied", "Importing the official residents list requires administrator privileges.")
            return
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Open Official Roster File", "", "Spreadsheets (*.xlsx *.csv)")
        if not path:
            return
        rows: list[dict] = []
        try:
            rows = read_official_file(path)
            resp = self.client.rpc("import_official_residents", {"p_rows": rows}).execute()
        except Exception as exc:  # noqa: BLE001
            self._show_import_result(False, imported=0, skipped=len(rows), errors=1, detail=str(exc))
            return
        reported = getattr(resp, "data", None)
        imported = reported if isinstance(reported, int) and not isinstance(reported, bool) else len(rows)
        skipped = max(0, len(rows) - imported)
        self._show_import_result(True, imported=imported, skipped=skipped, errors=0, detail=Path(path).name)
        self.reload()
