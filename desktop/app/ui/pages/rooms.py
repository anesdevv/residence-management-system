"""RÉSIVO — Dormitory rooms & capacity (visual layer only, docs/DESIGN.md §6–§7).

The rooms table follows the shared DataTable language (overline header on
``surface-subtle``, 44 px rows, hairline row separators, no gridlines, hover and
selection tint, tabular numerics) with a ``PageHeader``, a ``SearchField``
toolbar, a count ``StatusPill``, two distinct ``EmptyState`` variants ("no
rooms" vs "no match"), a ``Skeleton`` while ``reload()`` is in flight and an
error ``InlineBanner`` when the fetch fails. The occupancy column renders a
``RoomOccupancyBar`` while the item text keeps the numeric count, because the
filter and any downstream sorting read the item text.

The data layer is frozen: ``reload()`` keeps its exact query chain (``rooms``
ordered by ``block`` then ``number``, plus ``room_occupancy``), ``filter_table()``
keeps the text + gender filter logic, ``on_add`` / ``on_edit`` / ``on_delete``
keep their inserts, updates, deletes and validations, ``on_row_double_clicked``
keeps calling ``RoomInfoCardDialog(self, room_copy, self.client)``, and
``RoomSetupDialog`` keeps its exact signature and ``on_save`` validation —
including the occupancy/capacity guard (the capacity spin can never drop below
the current occupancy) and its tooltip / warning behaviour.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...client import room_occupancy
from .. import theme
from ..components import (
    Button,
    Card,
    EmptyState,
    IconButton,
    InlineBanner,
    PageHeader,
    RoomOccupancyBar,
    SearchField,
    Skeleton,
    StatusPill,
    configure_table,
)
from ..icons import get_icon
from ..infocard import RoomInfoCardDialog
from ..theme import C, S, DESKTOP_STYLESHEET

# Table language: overline headers are uppercased by ``configure_table``.
_COLUMNS = ["Block", "Floor", "Room No.", "Gender", "Total Beds", "Occupied", "Availability"]
# The occupancy meter wants a wider cell than its size hint so the bar is readable.
_OCCUPANCY_CELL_WIDTH = S("space-12") * 3 + S("space-4")


def _cell_widget(widget: QWidget, stretch: int = 0) -> QWidget:
    """Wrap a widget for a table cell so clicks still select the row.

    ``WA_TransparentForMouseEvents`` also disables delivery for the wrapper's
    children, so the occupancy meter never swallows the row selection.
    """
    holder = QWidget()
    holder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    row.addWidget(widget, stretch, Qt.AlignmentFlag.AlignVCenter)
    if not stretch:
        row.addStretch(1)
    return holder


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


class RoomSetupDialog(QDialog):
    """Add / edit one room; signature and ``on_save`` validation frozen.

    The occupancy/capacity guard: ``cap_spin`` starts at ``current_occupancy``
    so a room can never be shrunk below its live occupants, with a tooltip that
    explains the limit. A room with active occupants also has its designated
    gender locked (warning banner + disabled combo).
    """

    def __init__(self, parent=None, room=None, current_occupancy=0):
        super().__init__(parent)
        self.setWindowTitle("Edit Room Configuration" if room else "Add Dormitory Room")
        self.setMinimumWidth(400)
        self.setStyleSheet(DESKTOP_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        layout.setSpacing(S("space-4"))

        card = Card(
            "Edit room configuration" if room else "Configure new dormitory room",
            "Block, floor, capacity and designated gender for this room.",
            icon="bed",
        )

        form = QFormLayout()
        form.setSpacing(S("space-3"))
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.block_edit = QLineEdit(room.get("block", "A") if room else "A")
        self.block_edit.setPlaceholderText("e.g. A, B, C…")

        self.floor_spin = QSpinBox()
        self.floor_spin.setRange(0, 15)
        self.floor_spin.setValue(int(room.get("floor", 0)) if room else 0)

        self.num_edit = QLineEdit(str(room.get("number", "")) if room else "")
        self.num_edit.setPlaceholderText("e.g. 101, 204…")

        min_cap = max(1, current_occupancy)
        self.cap_spin = QSpinBox()
        self.cap_spin.setRange(min_cap, 8)
        self.cap_spin.setValue(int(room.get("capacity", 2)) if room else 2)
        if current_occupancy > 0:
            self.cap_spin.setToolTip(
                f"{current_occupancy} bed(s) are occupied — the capacity cannot be lower "
                f"than {min_cap}."
            )
        else:
            self.cap_spin.setToolTip("Total beds in this room (1–8).")

        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["Male", "Female"])
        current_gender = room.get("gender", "male") if room else "male"
        self.gender_combo.setCurrentText(current_gender.capitalize())
        self.gender_combo.setToolTip("Designated gender of the residential block for this room")

        form.addRow("Dormitory Block:", self.block_edit)
        form.addRow("Floor Level:", self.floor_spin)
        form.addRow("Room Number:", self.num_edit)
        form.addRow(f"Bed Capacity (Min {min_cap}):", self.cap_spin)
        form.addRow("Designated Gender:", self.gender_combo)
        card.add_layout(form)

        if current_occupancy > 0:
            self.gender_combo.setEnabled(False)
            self.gender_combo.setToolTip(
                "The designated gender is locked while the room has active occupants."
            )
            card.add_widget(
                InlineBanner(
                    "warning",
                    title="Gender locked",
                    message=f"Room currently has {current_occupancy} active occupant(s).",
                )
            )

        layout.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(S("space-2"))
        btn_row.addStretch(1)

        cancel_btn = Button.secondary("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = Button.primary("Save room" if room else "Create room")
        save_btn.clicked.connect(self.on_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

        self.result_data = None

    def on_save(self):
        block = self.block_edit.text().strip().upper()
        num = self.num_edit.text().strip()
        if not block or not num:
            QMessageBox.warning(self, "Missing Data", "Block and Room Number cannot be empty.")
            return
        self.result_data = {
            "block": block,
            "floor": self.floor_spin.value(),
            "number": num,
            "capacity": self.cap_spin.value(),
            "gender": self.gender_combo.currentText().lower(),
        }
        self.accept()


class RoomsPage(QWidget):
    """Dormitory rooms: toolbar, DataTable and the room info card dialog."""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []
        self.occupancy_map: dict[str, int] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-8"), S("space-8"), S("space-8"), S("space-8"))
        layout.setSpacing(S("space-6"))

        self.header = PageHeader(
            "Dormitory rooms & capacity",
            "Manage residential blocks, room numbers, bed capacity and live occupancy.",
        )
        self.add_btn = Button.primary("Add room", icon="plus")
        self.add_btn.setToolTip("Configure a new dormitory room")
        self.add_btn.clicked.connect(self.on_add)
        self.header.actions.addWidget(self.add_btn)
        layout.addWidget(self.header)

        # ------------------------------------------------------------ toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(S("space-3"))

        self.search_field = SearchField("Search room number or block…")
        self.search_field.changed.connect(self.filter_table)
        # Legacy alias: the search box used to be a bare ``QLineEdit``.
        self.search_input = self.search_field.edit
        toolbar.addWidget(self.search_field, 1)

        self.gender_filter = QComboBox()
        self.gender_filter.addItems(["All Genders", "Male Blocks", "Female Blocks"])
        self.gender_filter.setToolTip("Show every block, or only male / female blocks")
        self.gender_filter.currentIndexChanged.connect(self.filter_table)
        toolbar.addWidget(self.gender_filter)

        self.count_badge = StatusPill("neutral", "0 rooms")
        toolbar.addWidget(self.count_badge)

        self.edit_btn = Button.secondary("Edit", icon="edit")
        self.edit_btn.setToolTip("Edit the selected room")
        self.edit_btn.clicked.connect(self.on_edit)
        toolbar.addWidget(self.edit_btn)

        self.delete_btn = Button.danger("Delete", icon="trash")
        self.delete_btn.setToolTip("Delete the selected room (only when no resident is assigned)")
        self.delete_btn.clicked.connect(self.on_delete)
        toolbar.addWidget(self.delete_btn)

        self.refresh_btn = IconButton("refresh", "Reload the room list")
        self.refresh_btn.clicked.connect(self.reload)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        self.error_banner = InlineBanner(
            "error",
            title="Rooms could not be loaded",
            message="Check the connection, then use Refresh to try again.",
        )
        self.error_banner.setVisible(False)
        layout.addWidget(self.error_banner)

        # -------------------------------------------------------------- table
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
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.Stretch,
            ],
        )
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        self.stack.addWidget(self.table)

        self.empty_no_data = EmptyState(
            "bed",
            "No rooms configured",
            "Add a room to start allocating beds to residents.",
        )
        self.empty_no_match = EmptyState(
            "search",
            "No room matches the filters",
            "Clear the search field or switch the gender filter to see every room again.",
        )
        self.stack.addWidget(self.empty_no_data)
        self.stack.addWidget(self.empty_no_match)

        self.skeleton = Skeleton(rows=6)
        self.stack.addWidget(self.skeleton)

        card_layout.addWidget(self.stack)
        layout.addWidget(table_card, 1)

        tip = _small_label("Double-click a room to inspect its occupants and bed allocation.")
        layout.addWidget(tip)

        self.reload()

    # --------------------------------------------------------------- data
    def reload(self):
        self._set_loading(True)
        try:
            resp = self.client.table("rooms").select("*").order("block").order("number").execute()
            data = getattr(resp, "data", None)
            self.rows = [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []
            self.occupancy_map = room_occupancy(self.client)
        except Exception as exc:  # noqa: BLE001
            self.error_banner.set_message(
                f"The room list could not be loaded ({exc}). "
                "Check the connection, then use Refresh to try again."
            )
            self.error_banner.setVisible(True)
            self._set_loading(False)
            return
        self.error_banner.setVisible(False)
        self.count_badge.setText(f"{len(self.rows)} rooms")
        self._render_rows()
        self._set_loading(False)

    def _render_rows(self):
        self.table.clearContents()
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            cap = r.get("capacity", 1)
            occ = self.occupancy_map.get(r["id"], 0)
            free = cap - occ
            avail_text = f"{free} bed(s) available" if free > 0 else "Full"

            block_item = QTableWidgetItem(f"Block {r['block']}")
            block_item.setIcon(get_icon("building", 14, C("teal-600")))
            floor_item = QTableWidgetItem(f"Floor {r['floor']}")
            num_item = QTableWidgetItem(f"Room {r['number']}")
            gender_item = QTableWidgetItem(str(r["gender"]).capitalize())
            cap_item = QTableWidgetItem(str(cap))
            # Numeric value kept in UserRole; DisplayRole stays empty so Qt's default
            # delegate does not render a duplicate number behind the RoomOccupancyBar.
            occ_item = QTableWidgetItem()
            occ_item.setData(Qt.ItemDataRole.UserRole, occ)
            avail_item = QTableWidgetItem(avail_text)
            if free > 0:
                avail_item.setForeground(QColor(C("status-ok-ink")))
            else:
                avail_item.setForeground(QColor(C("text-muted")))

            meter = RoomOccupancyBar(occ, cap)
            meter.setToolTip(f"{occ} of {cap} beds occupied — {avail_text}")
            holder = _cell_widget(meter, stretch=1)
            occ_item.setSizeHint(QSize(_OCCUPANCY_CELL_WIDTH, holder.sizeHint().height()))

            self.table.setItem(i, 0, block_item)
            self.table.setItem(i, 1, floor_item)
            self.table.setItem(i, 2, num_item)
            self.table.setItem(i, 3, gender_item)
            self.table.setItem(i, 4, cap_item)
            self.table.setItem(i, 5, occ_item)
            self.table.setItem(i, 6, avail_item)
            self.table.setCellWidget(i, 5, holder)

        self.filter_table()

    def filter_table(self):
        needle = self.search_input.text().lower().strip()
        gender_sel = self.gender_filter.currentText()
        gender_target = "male" if gender_sel == "Male Blocks" else "female" if gender_sel == "Female Blocks" else None

        for r in range(self.table.rowCount()):
            row_data = self.rows[r] if r < len(self.rows) else {}
            block = str(row_data.get("block", "")).lower()
            number = str(row_data.get("number", "")).lower()
            gender = str(row_data.get("gender", "")).lower()

            matches_text = needle in f"{block} {number}"
            matches_gender = gender_target is None or gender == gender_target
            self.table.setRowHidden(r, not (matches_text and matches_gender))

        self._update_empty_state()

    # ------------------------------------------------------------ rendering
    def _set_loading(self, loading: bool) -> None:
        """Swap the table for the Skeleton while ``reload()`` is in flight."""
        if loading:
            self.stack.setCurrentWidget(self.skeleton)
            self.skeleton.raise_()
            app = QApplication.instance()
            if app is not None and self.isVisible():
                # Let the placeholder paint before the (blocking) queries run.
                app.processEvents()
        else:
            self._update_empty_state()

    def _update_empty_state(self) -> None:
        """Table / "no match" / "no rooms" — never a blank area."""
        if not self.rows:
            self.stack.setCurrentWidget(self.empty_no_data)
            return
        visible = sum(
            1 for row in range(self.table.rowCount()) if not self.table.isRowHidden(row)
        )
        self.stack.setCurrentWidget(self.table if visible else self.empty_no_match)

    # -------------------------------------------------------------- dialogs
    def on_row_double_clicked(self, row: int, col: int):
        if 0 <= row < len(self.rows):
            room = self.rows[row]
            room_copy = dict(room)
            room_copy["occupied"] = self.occupancy_map.get(room["id"], 0)
            dlg = RoomInfoCardDialog(self, room_copy, self.client)
            dlg.exec()

    def on_add(self):
        dlg = RoomSetupDialog(self)
        if dlg.exec() and dlg.result_data:
            data = dlg.result_data
            try:
                self.client.table("rooms").insert(data).execute()
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Error", str(exc))
                return
            QMessageBox.information(self, "Room Created", f"Room {data['block']}-{data['number']} configured successfully.")
            self.reload()

    def on_edit(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self.rows):
            QMessageBox.information(self, "Select room", "Please select a room from the table to edit.")
            return
        room = self.rows[r]
        occ = self.occupancy_map.get(room["id"], 0)
        dlg = RoomSetupDialog(self, room=room, current_occupancy=occ)
        if dlg.exec() and dlg.result_data:
            data = dlg.result_data
            try:
                self.client.table("rooms").update(data).eq("id", room["id"]).execute()
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Error", str(exc))
                return
            QMessageBox.information(self, "Room Updated", f"Room {data['block']}-{data['number']} updated successfully.")
            self.reload()

    def on_delete(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self.rows):
            QMessageBox.information(self, "Select room", "Please select a room from the table to delete.")
            return
        room = self.rows[r]
        if self.occupancy_map.get(room["id"], 0) > 0:
            QMessageBox.warning(self, "Room Occupied", "Cannot delete a room that still has active residents assigned.")
            return
        confirm = QMessageBox.question(self, "Delete Room", f"Are you sure you want to delete room Block {room['block']} — {room['number']}?")
        if confirm != QMessageBox.StandardButton.Yes and confirm != QMessageBox.Yes:
            return
        try:
            self.client.table("rooms").delete().eq("id", room["id"]).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        QMessageBox.information(self, "Room Deleted", f"Room {room['block']}-{room['number']} has been removed.")
        self.reload()
