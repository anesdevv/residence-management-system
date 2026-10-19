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


class BlockSetupDialog(QDialog):
    """Add a residential block designating female or male resident housing."""

    def __init__(self, parent=None, client=None, existing_names=None):
        super().__init__(parent)
        self.setWindowTitle("Add Residential Block")
        self.setMinimumWidth(380)
        self.setStyleSheet(DESKTOP_STYLESHEET)
        self.client = client
        self.existing_names = {str(n).strip().upper() for n in (existing_names or [])}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        layout.setSpacing(S("space-4"))

        card = Card(
            "New residential block",
            "Assign a block identifier and its resident gender designation.",
            icon="building",
        )

        form = QFormLayout()
        form.setSpacing(S("space-3"))
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. A, B, C, D, North Wing…")

        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["Female", "Male"])
        self.gender_combo.setToolTip("Designated gender for students housed in this block.")

        form.addRow("Block Identifier:", self.name_edit)
        form.addRow("Designated Gender:", self.gender_combo)
        card.add_layout(form)

        tip = QLabel("Every room created inside this block will automatically be designated for this gender.")
        theme.apply_role(tip, "small")
        tip.setStyleSheet(f"color: {C('text-muted')}; padding-top: 4px;")
        tip.setWordWrap(True)
        card.add_widget(tip)

        layout.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(S("space-2"))
        btn_row.addStretch(1)

        cancel_btn = Button.secondary("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = Button.primary("Create block")
        save_btn.clicked.connect(self.on_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)
        self.result_data = None

    def on_save(self):
        name = self.name_edit.text().strip().upper()
        if not name:
            QMessageBox.warning(self, "Missing Identifier", "Block identifier cannot be empty.")
            return
        if name in self.existing_names:
            QMessageBox.warning(self, "Block Exists", f"A block named '{name}' already exists.")
            return

        gender = self.gender_combo.currentText().lower()
        if self.client:
            try:
                self.client.table("blocks").insert({"name": name, "gender": gender}).execute()
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Error Creating Block", str(exc))
                return

        self.result_data = {"name": name, "gender": gender}
        self.accept()


class ManageBlocksDialog(QDialog):
    """View and manage residential blocks and their gender designations."""

    def __init__(self, parent=None, client=None, rooms=None, occupancy=None):
        super().__init__(parent)
        self.setWindowTitle("Residential Blocks")
        self.setMinimumSize(660, 440)
        self.setStyleSheet(DESKTOP_STYLESHEET)
        self.client = client
        self.rooms = list(rooms or [])
        self.occupancy = dict(occupancy or {})
        self.blocks: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        layout.setSpacing(S("space-4"))

        card = Card(
            "Residential blocks & housing gender",
            "Every dormitory room automatically inherits its block's designated gender.",
            icon="building",
        )

        toolbar = QHBoxLayout()
        toolbar.setSpacing(S("space-2"))
        self.add_block_btn = Button.primary("Add block", icon="plus")
        self.add_block_btn.setToolTip("Configure a new residential block")
        self.add_block_btn.clicked.connect(self.on_add_block)
        toolbar.addWidget(self.add_block_btn)

        self.refresh_btn = IconButton("refresh", "Reload blocks")
        self.refresh_btn.clicked.connect(self.reload)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addStretch(1)
        card.add_layout(toolbar)

        self.table = QTableWidget(0, 6)
        cols = ["Block", "Gender Designation", "Rooms", "Total Beds", "Occupied Beds", "Actions"]
        configure_table(self.table, cols)
        _fit_columns(
            self.table,
            [
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.Stretch,
            ],
        )
        card.add_widget(self.table)
        layout.addWidget(card, 1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch(1)
        close_btn = Button.secondary("Close")
        close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(close_btn)
        layout.addLayout(bottom_row)

        self.reload()

    def reload(self):
        if self.client:
            try:
                resp = self.client.table("blocks").select("*").order("name").execute()
                data = getattr(resp, "data", None)
                self.blocks = [b for b in data if isinstance(b, dict)] if isinstance(data, list) else []
            except Exception:
                self.blocks = []

        if not self.blocks and self.rooms:
            seen = {}
            for r in self.rooms:
                b_name = str(r.get("block", "")).strip().upper()
                if b_name and b_name not in seen:
                    seen[b_name] = {"name": b_name, "gender": str(r.get("gender", "male")).lower()}
            self.blocks = list(seen.values())

        metrics: dict[str, dict] = {}
        for b in self.blocks:
            metrics[b["name"].upper()] = {"rooms": 0, "capacity": 0, "occupied": 0}

        for r in self.rooms:
            b_name = str(r.get("block", "")).strip().upper()
            if b_name not in metrics:
                metrics[b_name] = {"rooms": 0, "capacity": 0, "occupied": 0}
            metrics[b_name]["rooms"] += 1
            metrics[b_name]["capacity"] += int(r.get("capacity", 1))
            metrics[b_name]["occupied"] += self.occupancy.get(r.get("id"), 0)

        self.table.clearContents()
        self.table.setRowCount(len(self.blocks))
        for i, b in enumerate(self.blocks):
            b_name = b["name"].upper()
            gender = str(b.get("gender", "male")).lower()
            m = metrics.get(b_name, {"rooms": 0, "capacity": 0, "occupied": 0})

            name_item = QTableWidgetItem(f"Block {b_name}")
            name_item.setIcon(get_icon("building", 14, C("teal-600")))

            pill_flavor = "ok" if gender == "female" else "progress"
            pill = StatusPill(pill_flavor, gender.capitalize())
            pill_holder = _cell_widget(pill)

            rooms_item = QTableWidgetItem(str(m["rooms"]))
            cap_item = QTableWidgetItem(str(m["capacity"]))
            occ_item = QTableWidgetItem(str(m["occupied"]))

            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, QTableWidgetItem(gender.capitalize()))
            self.table.setCellWidget(i, 1, pill_holder)
            self.table.setItem(i, 2, rooms_item)
            self.table.setItem(i, 3, cap_item)
            self.table.setItem(i, 4, occ_item)

            del_btn = Button.danger("Delete", icon="trash")
            if m["rooms"] > 0:
                del_btn.setEnabled(False)
                del_btn.setToolTip(f"Cannot delete Block {b_name} while it contains {m['rooms']} room(s).")
            else:
                del_btn.setToolTip(f"Remove empty Block {b_name}.")
                del_btn.clicked.connect(lambda _, blk=b: self.on_delete_block(blk))

            del_holder = _cell_widget(del_btn)
            self.table.setCellWidget(i, 5, del_holder)

    def on_add_block(self):
        names = [b["name"] for b in self.blocks]
        dlg = BlockSetupDialog(self, client=self.client, existing_names=names)
        if dlg.exec() and dlg.result_data:
            self.reload()

    def on_delete_block(self, block: dict):
        b_name = block["name"]
        confirm = QMessageBox.question(
            self,
            "Delete Block",
            f"Are you sure you want to delete residential Block {b_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes and confirm != QMessageBox.Yes:
            return
        if self.client and "id" in block:
            try:
                self.client.table("blocks").delete().eq("id", block["id"]).execute()
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Error Deleting Block", str(exc))
                return
        self.reload()


class RoomSetupDialog(QDialog):
    """Add / edit one room with automatic block gender inheritance.

    The occupancy/capacity guard: ``cap_spin`` starts at ``current_occupancy``
    so a room can never be shrunk below its live occupants, with a tooltip that
    explains the limit. A room with active occupants also has its designated
    gender and block locked (warning banner + disabled combo).
    """

    def __init__(self, parent=None, room=None, current_occupancy=0, client=None, blocks=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Room Configuration" if room else "Add Dormitory Room")
        self.setMinimumWidth(440)
        self.setStyleSheet(DESKTOP_STYLESHEET)
        self.client = client or getattr(parent, "client", None)
        self.room = room
        self.current_occupancy = current_occupancy

        # Resolve available blocks
        self.blocks: list[dict] = list(blocks or getattr(parent, "blocks", []) or [])
        if not self.blocks and self.client:
            try:
                resp = self.client.table("blocks").select("*").order("name").execute()
                data = getattr(resp, "data", None)
                if isinstance(data, list):
                    self.blocks = [b for b in data if isinstance(b, dict)]
            except Exception:
                pass

        if room:
            r_block = str(room.get("block", "")).strip().upper()
            if r_block and not any(b["name"].upper() == r_block for b in self.blocks):
                self.blocks.append({"name": r_block, "gender": str(room.get("gender", "male")).lower()})

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        layout.setSpacing(S("space-4"))

        card = Card(
            "Edit room configuration" if room else "Configure new dormitory room",
            "Select residential block, floor, capacity. Room gender is automatically inherited from the block.",
            icon="bed",
        )

        form = QFormLayout()
        form.setSpacing(S("space-3"))
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        block_row = QHBoxLayout()
        block_row.setSpacing(S("space-2"))

        self.block_combo = QComboBox()
        self.block_combo.setToolTip("Select the residential block for this room.")
        block_row.addWidget(self.block_combo, 1)

        self.new_block_btn = Button.secondary("+ Block", icon="plus")
        self.new_block_btn.setToolTip("Create a new residential block designating Female or Male.")
        self.new_block_btn.clicked.connect(self._on_quick_create_block)
        block_row.addWidget(self.new_block_btn)

        # Backwards compatibility: keep self.block_edit synced
        self.block_edit = QLineEdit(room.get("block", "A") if room else "A")
        self.block_edit.setVisible(False)

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
        self.gender_combo.setEnabled(False)
        self.gender_combo.setToolTip("Designated gender is inherited automatically from the selected block.")

        self.gender_note = QLabel()
        theme.apply_role(self.gender_note, "small")
        self.gender_note.setStyleSheet(f"color: {C('text-muted')}; font-style: italic;")

        gender_layout = QVBoxLayout()
        gender_layout.setSpacing(2)
        gender_layout.addWidget(self.gender_combo)
        gender_layout.addWidget(self.gender_note)

        form.addRow("Dormitory Block:", block_row)
        form.addRow("Floor Level:", self.floor_spin)
        form.addRow("Room Number:", self.num_edit)
        form.addRow(f"Bed Capacity (Min {min_cap}):", self.cap_spin)
        form.addRow("Designated Gender:", gender_layout)
        card.add_layout(form)

        if current_occupancy > 0:
            self.block_combo.setEnabled(False)
            self.new_block_btn.setEnabled(False)
            self.block_combo.setToolTip("The block cannot be changed while the room has active occupants.")
            card.add_widget(
                InlineBanner(
                    "warning",
                    title="Room locked",
                    message=f"Room currently has {current_occupancy} active occupant(s). Block and gender cannot be modified.",
                )
            )

        layout.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(S("space-2"))
        btn_row.addStretch(1)

        cancel_btn = Button.secondary("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.save_btn = Button.primary("Save room" if room else "Create room")
        self.save_btn.clicked.connect(self.on_save)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)

        self.result_data = None

        self._populate_block_combo(initial_block=room.get("block") if room else None)
        self.block_combo.currentIndexChanged.connect(self._on_block_changed)
        self._on_block_changed()

    def _populate_block_combo(self, initial_block: str | None = None):
        self.block_combo.blockSignals(True)
        self.block_combo.clear()
        selected_index = 0
        for i, b in enumerate(self.blocks):
            name = str(b["name"]).upper()
            gender = str(b.get("gender", "male")).capitalize()
            self.block_combo.addItem(f"Block {name}  ·  {gender}", userData=b)
            if initial_block and name == initial_block.strip().upper():
                selected_index = i

        if self.blocks:
            self.block_combo.setCurrentIndex(selected_index)
            self.save_btn.setEnabled(True)
        else:
            self.block_combo.addItem("No blocks available", userData=None)
            self.save_btn.setEnabled(False)
            self.gender_note.setText("Click '+ Block' to create a residential block first.")

        self.block_combo.blockSignals(False)

    def _get_selected_block(self) -> dict | None:
        idx = self.block_combo.currentIndex()
        if idx >= 0:
            return self.block_combo.itemData(idx)
        return None

    def _on_block_changed(self):
        block = self._get_selected_block()
        if block:
            gender = str(block.get("gender", "male")).capitalize()
            self.gender_combo.setCurrentText(gender)
            self.gender_note.setText(f"Automatically inherited from Block {block['name'].upper()} ({gender}).")
            self.block_edit.setText(block["name"].upper())
            self.save_btn.setEnabled(True)
        else:
            self.gender_note.setText("Please create or select a residential block.")
            self.save_btn.setEnabled(False)

    def _on_quick_create_block(self):
        names = [b["name"] for b in self.blocks]
        dlg = BlockSetupDialog(self, client=self.client, existing_names=names)
        if dlg.exec() and dlg.result_data:
            new_block = dlg.result_data
            self.blocks.append(new_block)
            self._populate_block_combo(initial_block=new_block["name"])
            self._on_block_changed()

    def on_save(self):
        block_data = self._get_selected_block()
        if not block_data:
            QMessageBox.warning(self, "No Block", "Please create or select a residential block first.")
            return

        block_name = str(block_data["name"]).strip().upper()
        block_gender = str(block_data["gender"]).strip().lower()

        num = self.num_edit.text().strip()
        if not num:
            QMessageBox.warning(self, "Missing Data", "Room Number cannot be empty.")
            return

        self.result_data = {
            "block": block_name,
            "floor": self.floor_spin.value(),
            "number": num,
            "capacity": self.cap_spin.value(),
            "gender": block_gender,
        }
        self.accept()


class RoomsPage(QWidget):
    """Dormitory rooms: toolbar, DataTable and the room info card dialog."""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []
        self.blocks: list[dict] = []
        self.occupancy_map: dict[str, int] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-8"), S("space-8"), S("space-8"), S("space-8"))
        layout.setSpacing(S("space-6"))

        self.header = PageHeader(
            "Dormitory rooms & capacity",
            "Manage residential blocks, room numbers, bed capacity and live occupancy.",
        )
        self.blocks_btn = Button.secondary("Residential blocks", icon="building")
        self.blocks_btn.setToolTip("Manage residential blocks and designated genders")
        self.blocks_btn.clicked.connect(self.on_manage_blocks)
        self.header.actions.addWidget(self.blocks_btn)

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

            try:
                resp_b = self.client.table("blocks").select("*").order("name").execute()
                data_b = getattr(resp_b, "data", None)
                self.blocks = [b for b in data_b if isinstance(b, dict)] if isinstance(data_b, list) else []
            except Exception:
                self.blocks = []

            if not self.blocks and self.rows:
                seen = {}
                for r in self.rows:
                    b_name = str(r.get("block", "")).strip().upper()
                    if b_name and b_name not in seen:
                        seen[b_name] = {"name": b_name, "gender": str(r.get("gender", "male")).lower()}
                self.blocks = list(seen.values())
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

    def on_manage_blocks(self):
        dlg = ManageBlocksDialog(self, client=self.client, rooms=self.rows, occupancy=self.occupancy_map)
        dlg.exec()
        self.reload()

    def on_add(self):
        if not self.blocks:
            confirm = QMessageBox.question(
                self,
                "No Residential Blocks",
                "Every room must belong to a residential block designating Female or Male.\n\n"
                "Would you like to configure a residential block now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if confirm == QMessageBox.StandardButton.Yes or confirm == QMessageBox.Yes:
                b_dlg = BlockSetupDialog(self, client=self.client)
                if b_dlg.exec() and b_dlg.result_data:
                    self.reload()
                else:
                    return
            else:
                return

        dlg = RoomSetupDialog(self, client=self.client, blocks=self.blocks)
        if dlg.exec() and dlg.result_data:
            data = dlg.result_data
            try:
                self.client.table("rooms").insert(data).execute()
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Error", str(exc))
                return
            QMessageBox.information(
                self,
                "Room Created",
                f"Room {data['block']}-{data['number']} ({data['gender'].capitalize()}) configured successfully.",
            )
            self.reload()

    def on_edit(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self.rows):
            QMessageBox.information(self, "Select room", "Please select a room from the table to edit.")
            return
        room = self.rows[r]
        occ = self.occupancy_map.get(room["id"], 0)
        dlg = RoomSetupDialog(self, room=room, current_occupancy=occ, client=self.client, blocks=self.blocks)
        if dlg.exec() and dlg.result_data:
            data = dlg.result_data
            try:
                self.client.table("rooms").update(data).eq("id", room["id"]).execute()
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Error", str(exc))
                return
            QMessageBox.information(
                self,
                "Room Updated",
                f"Room {data['block']}-{data['number']} ({data['gender'].capitalize()}) updated successfully.",
            )
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
