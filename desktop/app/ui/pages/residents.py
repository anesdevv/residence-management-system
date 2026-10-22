"""RÉSIVO — Residents directory (visual layer only, docs/DESIGN.md §6–§7).

Layout and styling follow the DataTable language (overline header on
``surface-subtle``, 44 px rows, no gridlines, hover + selection tint, tabular
numerics) with a ``PageHeader``, a ``SearchField`` toolbar, status pills,
roster badges, an ``EmptyState`` and an error ``InlineBanner``.

The data layer is frozen: ``reload()`` keeps its exact query chain
(``students`` + ``rooms(block, number, floor)``, ``status=active`` ordered by
``last_name``), ``render()`` keeps its filter logic (search haystack + gender
selector) and ``on_row_double_clicked`` keeps calling ``official_lookup`` and
``StudentInfoCardDialog(self, st_data, roster_item)`` unchanged.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...client import CLIENT_LOCK, official_lookup
from .. import theme
from ..components import (
    EmptyState,
    IconButton,
    InlineBanner,
    PageHeader,
    RosterMatchBadge,
    SearchField,
    StatusPill,
    configure_table,
)
from ..infocard import StudentInfoCardDialog
from ..tasks import TaskRunner, human_error
from ..theme import S

# Table language: overline headers are uppercased by configure_table().
_COLUMNS = ["Card ID", "Resident", "Room", "Faculty / University", "Registered", "Status", "Roster"]
_ACTIVE_STATUS_KIND = "ok"


def _cell_widget(widget: QWidget) -> QWidget:
    """Wrap a widget for a table cell so clicks still select the row.

    ``WA_TransparentForMouseEvents`` also disables delivery for the wrapper's
    children, so a pill never swallows the row selection. The wrapper keeps no
    margins of its own: the stylesheet's item padding already insets it.
    """
    holder = QWidget()
    holder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
    row.addStretch(1)
    return holder


def _pill_item(text: str, holder: QWidget) -> QTableWidgetItem:
    """Cell item behind a pill widget.

    The status word stays readable through ``item(...).text()`` but is not
    painted, so nothing shows through behind the pill drawn on top of the cell.
    The table's item padding (``space-3`` on each side) insets the cell widget,
    so it is added to the column width the item asks for (``ResizeToContents``).
    """
    item = QTableWidgetItem(text)
    item.setForeground(QBrush(QColor(0, 0, 0, 0)))
    hint = holder.sizeHint()
    item.setSizeHint(QSize(hint.width() + 2 * S("space-3"), hint.height()))
    return item


def _fit_columns(table: QTableWidget, modes: list) -> QHeaderView:
    """Apply per-column resize modes (last section keeps its own mode)."""
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


class ResidentsPage(QWidget):
    """Active residents: toolbar, DataTable and the profile card dialog."""

    def __init__(self, client, *, defer_initial_load: bool = False):
        super().__init__()
        self.client = client
        self.tasks = TaskRunner(self)
        self.rows: list[dict] = []
        self.filtered_rows: list[tuple[dict, dict]] = []
        # Official roster cache: filled by the lookup in
        # ``on_row_double_clicked`` (no extra query is issued by this page).
        self.roster: dict[str, dict] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-8"), S("space-8"), S("space-8"), S("space-8"))
        layout.setSpacing(S("space-6"))

        self.header = PageHeader(
            "Residents",
            "Students currently accommodated in the Cité Universitaire.",
        )
        layout.addWidget(self.header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(S("space-3"))

        self.search = SearchField("Search by card ID, name, room, faculty or university…")
        self.search.changed.connect(self.render)
        toolbar.addWidget(self.search, 1)

        self.gender_filter = QComboBox()
        self.gender_filter.addItems(["All Genders", "Male Residents", "Female Residents"])
        self.gender_filter.setToolTip("Show every resident, or only male / female residents")
        self.gender_filter.currentIndexChanged.connect(self.render)
        toolbar.addWidget(self.gender_filter)

        self.count_badge = StatusPill("neutral", "0 active residents")
        toolbar.addWidget(self.count_badge)

        self.refresh_btn = IconButton("refresh", "Reload the residents list")
        self.refresh_btn.clicked.connect(self.reload)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        self.error_banner = InlineBanner(
            "error",
            title="Residents could not be loaded",
            message="Use Refresh to try again.",
        )
        self.error_banner.setVisible(False)
        layout.addWidget(self.error_banner)

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
                QHeaderView.ResizeMode.Stretch,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.Stretch,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
            ],
        )
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        self.stack.addWidget(self.table)

        self.empty_no_data = EmptyState(
            "users",
            "No residents yet",
            "Approved students appear here as soon as a room has been allocated.",
        )
        self.empty_no_match = EmptyState(
            "search",
            "No resident matches",
            "Clear the search field or switch the gender filter to see everyone again.",
        )
        self.stack.addWidget(self.empty_no_data)
        self.stack.addWidget(self.empty_no_match)
        card_layout.addWidget(self.stack)
        layout.addWidget(table_card, 1)

        tip = _small_label("Double-click a resident to open the complete profile card.")
        layout.addWidget(tip)

        if not defer_initial_load:
            self.reload()

    # ------------------------------------------------------------------ data
    def reload(self):
        if self.tasks.is_busy("residents-reload"):
            return
        self.refresh_btn.setEnabled(False)
        self.tasks.run(
            "residents-reload",
            self._fetch_residents,
            on_success=self._on_reload_success,
            on_failed=self._on_reload_failed,
        )

    def _fetch_residents(self) -> list[dict]:
        with CLIENT_LOCK:
            resp = (
                self.client.table("students")
                .select("*, rooms(block, number, floor)")
                .eq("status", "active")
                .order("last_name")
                .execute()
            )
            return resp.data or []

    def _on_reload_success(self, rows: list[dict]):
        self.refresh_btn.setEnabled(True)
        self.rows = rows
        self.error_banner.setVisible(False)
        self.count_badge.setText(f"{len(self.rows)} active residents")
        self.render()

    def _on_reload_failed(self, error: str):
        self.refresh_btn.setEnabled(True)
        self.error_banner.set_message(
            f"The residents list could not be loaded ({human_error(error)}). Use Refresh to try again."
        )
        self.error_banner.setVisible(True)
        self.render()

    def render(self):
        needle = self.search.text().lower().strip()
        gender_sel = self.gender_filter.currentText()
        gender_target = "male" if gender_sel == "Male Residents" else "female" if gender_sel == "Female Residents" else None

        filtered = []
        for r in self.rows:
            room = r.get("rooms") or {}
            if isinstance(room, list) and room:
                room = room[0]
            elif not isinstance(room, dict):
                room = {}

            haystack = f"{r.get('first_name', '')} {r.get('last_name', '')} {r.get('card_id', '')} {room.get('block', '')} {room.get('number', '')} {r.get('university', '')} {r.get('faculty', '')}".lower()
            matches_text = needle in haystack
            matches_gender = gender_target is None or str(r.get("gender", "")).lower() == gender_target
            if matches_text and matches_gender:
                filtered.append((r, room))

        self.filtered_rows = filtered
        self.table.setRowCount(len(filtered))
        for i, (r, room) in enumerate(filtered):
            card_id = str(r.get("card_id", ""))
            name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or "—"
            room_item = (
                QTableWidgetItem(f"Block {room.get('block', '—')} — Room {room.get('number', '—')}")
                if room else QTableWidgetItem("Not assigned")
            )
            faculty_item = QTableWidgetItem(str(r.get("faculty") or "—"))
            date_item = QTableWidgetItem(str(r.get("created_at", ""))[:10])

            card_item = QTableWidgetItem(card_id)
            name_item = QTableWidgetItem(name)
            status_holder = _cell_widget(StatusPill(_ACTIVE_STATUS_KIND, "Active"))
            status_item = _pill_item("Active", status_holder)

            matched = None
            if self.roster:
                matched = card_id in self.roster
            roster_text = "Matched" if matched is True else "Not in roster" if matched is False else "Not checked"
            roster_holder = _cell_widget(RosterMatchBadge(matched))
            roster_item = _pill_item(roster_text, roster_holder)

            self.table.setItem(i, 0, card_item)
            self.table.setItem(i, 1, name_item)
            self.table.setItem(i, 2, room_item)
            self.table.setItem(i, 3, faculty_item)
            self.table.setItem(i, 4, date_item)
            self.table.setItem(i, 5, status_item)
            self.table.setItem(i, 6, roster_item)

            self.table.setCellWidget(i, 5, status_holder)
            self.table.setCellWidget(i, 6, roster_holder)

        self._update_empty_state()

    def _update_empty_state(self):
        """Swap between the table and the two empty states (no blank areas)."""
        if self.filtered_rows:
            self.stack.setCurrentIndex(0)
        elif self.rows:
            self.stack.setCurrentIndex(2)
        else:
            self.stack.setCurrentIndex(1)

    # -------------------------------------------------------------- dialogs
    def on_row_double_clicked(self, row: int, col: int):
        if 0 <= row < len(self.filtered_rows):
            student, room = self.filtered_rows[row]
            st_data = dict(student)
            st_data["rooms"] = room
            if self.roster:
                self._open_student_card(st_data, self.roster)
                return
            if self.tasks.is_busy("residents-roster"):
                return
            self.tasks.run(
                "residents-roster",
                lambda: official_lookup(self.client),
                on_success=lambda roster_map: self._on_roster_loaded(st_data, roster_map),
                on_failed=lambda _: self._open_student_card(st_data, {}),
            )

    def _on_roster_loaded(self, st_data: dict, roster_map: dict[str, dict]):
        if roster_map:
            self.roster = roster_map
            self.render()
        self._open_student_card(st_data, roster_map or {})

    def _open_student_card(self, st_data: dict, roster_map: dict[str, dict]):
        roster_item = roster_map.get(st_data.get("card_id"))
        dlg = StudentInfoCardDialog(self, st_data, roster_item)
        dlg.exec()
