"""RÉSIVO — Dormitory rooms & capacity (visual layer only, docs/DESIGN.md §6–§7).

The rooms table follows the shared DataTable language (overline header on
``surface-subtle``, 44 px rows, hairline row separators, no gridlines, hover and
selection tint, tabular numerics) with a ``PageHeader``, a ``SearchField``
toolbar, a count ``StatusPill``, two distinct ``EmptyState`` variants ("no
rooms" vs "no match"), a ``Skeleton`` while ``reload()`` is in flight and an
error ``InlineBanner`` when the fetch fails. The occupancy column renders a
``RoomOccupancyBar`` while the item text keeps the numeric count, because the
filter and any downstream sorting read the item text.

The query chains are unchanged (``rooms`` ordered by ``block`` then ``number``,
plus ``room_occupancy`` and the ``blocks`` lookup), ``filter_table()`` keeps the
text + gender filter logic, and ``on_add`` / ``on_edit`` / ``on_delete`` keep
their inserts, updates, deletes and validations.  Those writes and the
post-action ``reload()`` run through ``TaskRunner``; dialogs reuse the
already-loaded block list, and ``on_row_double_clicked`` loads occupants in the
background before showing ``RoomInfoCardDialog``.  ``RoomSetupDialog`` keeps its
exact signature and ``on_save`` validation — including the occupancy/capacity
guard (the capacity spin can never drop below the current occupancy) and its
tooltip / warning behaviour.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
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
    NumberStepper,
    PageHeader,
    RoomOccupancyBar,
    SearchField,
    Skeleton,
    StatusPill,
    configure_table,
)
from ..icons import get_icon
from ..infocard import RoomInfoCardDialog
from ..tasks import TaskRunner, human_error
from ..theme import C, S, DESKTOP_STYLESHEET

# Table language: overline headers are uppercased by ``configure_table``.
_COLUMNS = ["Block", "Floor", "Room No.", "Gender", "Total Beds", "Occupied", "Availability"]
# The occupancy meter wants a wider cell than its size hint so the bar is readable.
_OCCUPANCY_CELL_WIDTH = S("space-12") * 3 + S("space-4")

# Background task keys. Writes share one key on purpose: add/edit/delete and a
# refresh must never race each other through the GUI state.
_ACTION_KEY = "rooms-action"
_RELOAD_KEY = "rooms-reload"
_INFO_KEY = "rooms-info"
_WORKING_TEXT = "Working..."


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
        self.tasks = TaskRunner(self)
        self._busy = False
        self._closing = False

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

        self.error_banner = InlineBanner(
            "error",
            title="Block could not be created",
            message="",
        )
        self.error_banner.setVisible(False)
        card.add_widget(self.error_banner)

        layout.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(S("space-2"))
        btn_row.addStretch(1)

        self.cancel_btn = Button.secondary("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        self.save_btn = Button.primary("Create block")
        self.save_btn.clicked.connect(self.on_save)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)
        self.result_data = None

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.save_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(not busy)
        if busy:
            self.save_btn.setText(_WORKING_TEXT)
            self.error_banner.set_kind("info")
            self.error_banner.set_title(_WORKING_TEXT)
            self.error_banner.set_message("Creating the residential block…")
            self.error_banner.setVisible(True)
        else:
            self.save_btn.setText("Create block")

    def _apply_created_block(self, payload: dict) -> None:
        if self._closing:
            return
        self.result_data = payload
        self.accept()

    def _on_create_failed(self, message: str) -> None:
        self.error_banner.set_kind("error")
        self.error_banner.set_title("Block could not be created")
        self.error_banner.set_message(message)
        self.error_banner.setVisible(True)

    def _on_create_finished(self) -> None:
        if not self._closing:
            self._set_busy(False)

    def closeEvent(self, event):  # noqa: N802 - Qt API
        self._closing = True
        super().closeEvent(event)

    def on_save(self):
        name = self.name_edit.text().strip().upper()
        if not name:
            QMessageBox.warning(self, "Missing Identifier", "Block identifier cannot be empty.")
            return
        if name in self.existing_names:
            QMessageBox.warning(self, "Block Exists", f"A block named '{name}' already exists.")
            return

        gender = self.gender_combo.currentText().lower()
        payload = {"name": name, "gender": gender}

        # Programmatic (never-shown) invocations keep the historical synchronous
        # behaviour used by callers/tests.  Every dialog the user actually sees
        # performs its insert through TaskRunner, off the GUI thread.
        if not self.isVisible():
            if self.client:
                try:
                    self.client.table("blocks").insert(payload).execute()
                except Exception as exc:  # noqa: BLE001
                    QMessageBox.critical(self, "Error Creating Block", human_error(exc))
                    return
            self.result_data = payload
            self.accept()
            return

        if self._busy:
            return
        self._set_busy(True)

        def work():
            if self.client:
                self.client.table("blocks").insert(payload).execute()
            return payload

        started = self.tasks.run(
            "block-create",
            work,
            on_success=self._apply_created_block,
            on_failed=self._on_create_failed,
            on_finished=self._on_create_finished,
        )
        if not started:
            self._set_busy(False)


class ManageBlocksDialog(QDialog):
    """View and manage residential blocks and their gender designations."""

    def __init__(self, parent=None, client=None, rooms=None, occupancy=None, blocks=None):
        super().__init__(parent)
        self.setWindowTitle("Residential Blocks")
        self.setMinimumSize(660, 440)
        self.setStyleSheet(DESKTOP_STYLESHEET)
        self.client = client
        self.rooms = list(rooms or [])
        self.occupancy = dict(occupancy or {})
        self.blocks: list[dict] = []
        self.tasks = TaskRunner(self)
        self._loaded_once = False
        self._busy = False
        self._closing = False
        self._deleting_block_name = "?"
        self._seed_blocks = (
            [dict(b) for b in blocks if isinstance(b, dict)] if blocks is not None else None
        )

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

        self.error_banner = InlineBanner(
            "error",
            title="Blocks could not be loaded",
            message="",
        )
        self.error_banner.setVisible(False)
        card.add_widget(self.error_banner)

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

    def _show_banner(self, kind: str, title: str, message: str) -> None:
        self.error_banner.set_kind(kind)
        self.error_banner.set_title(title)
        self.error_banner.set_message(message)
        self.error_banner.setVisible(True)

    def _set_busy(self, busy: bool, message: str = "Please wait…") -> None:
        """Disable dialog controls while a block write/refresh is in flight."""
        self._busy = busy
        self.add_block_btn.setEnabled(not busy)
        self.refresh_btn.setEnabled(not busy)
        self.table.setEnabled(not busy)
        if busy:
            self._show_banner("info", _WORKING_TEXT, message)

    def _fetch_blocks(self) -> list[dict]:
        resp = self.client.table("blocks").select("*").order("name").execute()
        data = getattr(resp, "data", None)
        return [b for b in data if isinstance(b, dict)] if isinstance(data, list) else []

    def _derive_blocks_from_rooms(self) -> None:
        if self.blocks or not self.rooms:
            return
        seen = {}
        for r in self.rooms:
            b_name = str(r.get("block", "")).strip().upper()
            if b_name and b_name not in seen:
                seen[b_name] = {"name": b_name, "gender": str(r.get("gender", "male")).lower()}
        self.blocks = list(seen.values())

    def _load_sync(self) -> None:
        if self.client:
            try:
                self.blocks = self._fetch_blocks()
            except Exception:  # noqa: BLE001 - fall back to room-derived blocks
                self.blocks = []
        self._derive_blocks_from_rooms()
        self._render()

    def _on_reload_success(self, blocks) -> None:
        if self._closing:
            return
        self.blocks = blocks
        self._derive_blocks_from_rooms()
        self._render()
        self.error_banner.setVisible(False)

    def _on_reload_failed(self, message: str) -> None:
        self._show_banner(
            "error",
            "Blocks could not be loaded",
            f"The list is showing the last data received ({message}).",
        )

    def _on_reload_finished(self) -> None:
        if not self._closing:
            self._set_busy(False)

    def _reload_async(self) -> None:
        if self.tasks.is_busy(_RELOAD_KEY) or self._busy:
            return
        self._set_busy(True, "Refreshing residential blocks…")
        started = self.tasks.run(
            _RELOAD_KEY,
            self._fetch_blocks,
            on_success=self._on_reload_success,
            on_failed=self._on_reload_failed,
            on_finished=self._on_reload_finished,
        )
        if not started:
            self._set_busy(False)

    def reload(self):
        """Load blocks; the first (constructor) call reuses the seed or is sync."""
        if not self._loaded_once:
            self._loaded_once = True
            if self._seed_blocks is not None:
                self.blocks = [dict(b) for b in self._seed_blocks]
                self._derive_blocks_from_rooms()
                self._render()
            else:
                self._load_sync()
            return
        self._reload_async()

    def _render(self) -> None:
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
        if self._busy:
            return
        names = [b["name"] for b in self.blocks]
        dlg = BlockSetupDialog(self, client=self.client, existing_names=names)
        if dlg.exec() and dlg.result_data:
            new_block = dict(dlg.result_data)
            self.blocks.append(new_block)
            self._render()
            self.reload()

    def _on_delete_block_success(self, blocks) -> None:
        self.blocks = blocks
        self._derive_blocks_from_rooms()
        self._render()
        self.error_banner.setVisible(False)

    def _on_delete_block_failed(self, message: str) -> None:
        self._show_banner(
            "error",
            "Block could not be deleted",
            f"Block {self._deleting_block_name} was not removed. {message}",
        )

    def _on_delete_block_finished(self) -> None:
        if not self._closing:
            self._set_busy(False)

    def on_delete_block(self, block: dict):
        if self._busy:
            return
        block_name = block.get("name", "?")
        confirm = QMessageBox.question(
            self,
            "Delete Block",
            f"Are you sure you want to delete residential Block {block_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes and confirm != QMessageBox.Yes:
            return

        if self.client and "id" in block:
            block_id = block["id"]
            self._deleting_block_name = block_name

            def work():
                self.client.table("blocks").delete().eq("id", block_id).execute()
                return self._fetch_blocks()

            self._set_busy(True, f"Deleting Block {block_name}…")
            started = self.tasks.run(
                _ACTION_KEY,
                work,
                on_success=self._on_delete_block_success,
                on_failed=self._on_delete_block_failed,
                on_finished=self._on_delete_block_finished,
            )
            if not started:
                self._set_busy(False)
            return

        self.reload()

    def closeEvent(self, event):  # noqa: N802 - Qt API
        self._closing = True
        super().closeEvent(event)


class RoomSetupDialog(QDialog):
    """Add / edit one room with automatic block gender inheritance.

    The occupancy/capacity guard: ``cap_spin`` starts at ``current_occupancy``
    so a room can never be shrunk below its live occupants, with a tooltip that
    explains the limit. A room with active occupants also has its designated
    gender and block locked (warning banner + disabled combo).
    """

    def __init__(self, parent=None, room=None, current_occupancy=0, client=None, blocks=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Dormitory Room" if room else "Add Dormitory Room")
        self.setMinimumWidth(480)
        self.setStyleSheet(DESKTOP_STYLESHEET)
        self.client = client or getattr(parent, "client", None)
        self.room = room
        self.current_occupancy = current_occupancy
        self._busy = False
        self._num_touched = bool(room and str(room.get("number", "")).strip())

        # Reuse the already-loaded blocks supplied by the page/dialog.  No
        # network query is made here: the caller loads them off the GUI thread.
        self.blocks: list[dict] = list(blocks or getattr(parent, "blocks", []) or [])
        if room:
            r_block = str(room.get("block", "")).strip().upper()
            if r_block and not any(b["name"].upper() == r_block for b in self.blocks):
                self.blocks.append({"name": r_block, "gender": str(room.get("gender", "male")).lower()})

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        layout.setSpacing(S("space-4"))

        card = Card(
            "Edit Dormitory Room" if room else "Add Dormitory Room",
            "Select residential block, floor, capacity. Room gender is automatically inherited from the block.",
            icon="bed",
        )

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(S("space-4"))  # 16px gap
        grid.setVerticalSpacing(S("space-4"))    # 16px gap
        grid.setColumnMinimumWidth(0, 160)

        # Row 0: Block
        lbl_block = QLabel("Dormitory Block:")
        lbl_block.setFixedWidth(160)
        theme.apply_role(lbl_block, "body")

        block_row = QHBoxLayout()
        block_row.setSpacing(S("space-2"))

        self.block_combo = QComboBox()
        self.block_combo.setFixedHeight(40)
        self.block_combo.setToolTip("Select the residential block for this room.")
        block_row.addWidget(self.block_combo, 1)

        self.new_block_btn = Button.secondary("Add block", icon="plus")
        self.new_block_btn.setFixedHeight(40)
        self.new_block_btn.setToolTip("Create a new residential block designating Female or Male.")
        self.new_block_btn.clicked.connect(self._on_quick_create_block)
        block_row.addWidget(self.new_block_btn)

        grid.addWidget(lbl_block, 0, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        grid.addLayout(block_row, 0, 1)

        # Backwards compatibility: keep self.block_edit synced
        self.block_edit = QLineEdit(room.get("block", "A") if room else "A")
        self.block_edit.setVisible(False)

        # Row 1: Floor
        lbl_floor = QLabel("Floor Level:")
        lbl_floor.setFixedWidth(160)
        theme.apply_role(lbl_floor, "body")

        self.floor_spin = NumberStepper(self)
        self.floor_spin.setRange(0, 15)
        self.floor_spin.setValue(int(room.get("floor", 0)) if room else 0)

        grid.addWidget(lbl_floor, 1, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(self.floor_spin, 1, 1)

        # Row 2: Room Number
        lbl_num = QLabel("Room Number:")
        lbl_num.setFixedWidth(160)
        theme.apply_role(lbl_num, "body")

        num_container = QVBoxLayout()
        num_container.setSpacing(2)
        num_container.setContentsMargins(0, 0, 0, 0)

        self.num_edit = QLineEdit(str(room.get("number", "")) if room else "")
        self.num_edit.setFixedHeight(40)
        self.num_edit.setPlaceholderText("e.g. 101, 204…")
        self.num_edit.textChanged.connect(self._on_num_changed)
        num_container.addWidget(self.num_edit)

        self.num_error_label = QLabel("")
        self.num_error_label.setStyleSheet(f"color: {C('status-danger-ink')}; font-size: 12px; padding-left: 2px;")
        self.num_error_label.setVisible(False)
        num_container.addWidget(self.num_error_label)

        grid.addWidget(lbl_num, 2, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        grid.addLayout(num_container, 2, 1)

        # Row 3: Bed Capacity
        min_cap = max(1, current_occupancy)
        lbl_cap = QLabel(f"Bed Capacity (Min {min_cap}):")
        lbl_cap.setFixedWidth(160)
        theme.apply_role(lbl_cap, "body")

        self.cap_spin = NumberStepper(self)
        self.cap_spin.setRange(min_cap, 8)
        self.cap_spin.setValue(int(room.get("capacity", 2)) if room else 2)
        if current_occupancy > 0:
            self.cap_spin.setToolTip(
                f"{current_occupancy} bed(s) are occupied — the capacity cannot be lower "
                f"than {min_cap}."
            )
        else:
            self.cap_spin.setToolTip("Total beds in this room (1–8).")
        self.cap_spin.valueChanged.connect(self._validate_inputs)

        grid.addWidget(lbl_cap, 3, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(self.cap_spin, 3, 1)

        # Row 4: Designated Gender
        lbl_gender = QLabel("Designated Gender:")
        lbl_gender.setFixedWidth(160)
        theme.apply_role(lbl_gender, "body")

        gender_layout = QVBoxLayout()
        gender_layout.setSpacing(2)
        gender_layout.setContentsMargins(0, 0, 0, 0)

        self.gender_combo = QComboBox()
        self.gender_combo.setFixedHeight(40)
        self.gender_combo.addItems(["Male", "Female"])
        self.gender_combo.setEnabled(False)
        # Higher contrast for disabled state: text #5B6B82 on #EDF2F7
        self.gender_combo.setStyleSheet(
            f"QComboBox:disabled {{ color: #5B6B82; background-color: #EDF2F7; border: 1px solid #DCE4EE; }}"
        )
        self.gender_combo.setToolTip("Designated gender is inherited automatically from the selected block.")
        gender_layout.addWidget(self.gender_combo)

        self.gender_note = QLabel()
        theme.apply_role(self.gender_note, "small")
        self.gender_note.setStyleSheet(f"color: {C('text-muted')}; font-style: italic; margin-top: 2px;")
        gender_layout.addWidget(self.gender_note)

        grid.addWidget(lbl_gender, 4, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        grid.addLayout(gender_layout, 4, 1)

        card.add_layout(grid)

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

        # Right-aligned QDialogButtonBox: Cancel (secondary) then Create/Save (primary default)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.button_box = QDialogButtonBox(Qt.Orientation.Horizontal, self)
        self.cancel_btn = Button.secondary("Cancel")
        self.cancel_btn.setFixedHeight(40)
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = Button.primary("Save changes" if room else "Create room")
        self.save_btn.setFixedHeight(40)
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.on_save)

        self.button_box.addButton(self.cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        self.button_box.addButton(self.save_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        btn_row.addWidget(self.button_box)

        layout.addLayout(btn_row)

        self.result_data = None

        self._populate_block_combo(initial_block=room.get("block") if room else None)
        self.block_combo.currentIndexChanged.connect(self._on_block_changed)
        self._on_block_changed()
        self._validate_inputs()

    def _on_num_changed(self, _text: str) -> None:
        self._num_touched = True
        self._validate_inputs()

    def _validate_inputs(self, *_args) -> bool:
        num = self.num_edit.text().strip()
        cap = self.cap_spin.value()
        has_block = self._get_selected_block() is not None

        is_valid = True
        if not num:
            is_valid = False
            self.num_error_label.setText("Room number is required.")
            self.num_error_label.setVisible(self._num_touched)
        else:
            self.num_error_label.setText("")
            self.num_error_label.setVisible(False)

        if cap < 1:
            is_valid = False

        if not has_block:
            is_valid = False

        self.save_btn.setEnabled(is_valid and not self._busy)
        return is_valid

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
        else:
            self.block_combo.addItem("No blocks available", userData=None)
            self.gender_note.setText("Click 'Add block' to create a residential block first.")

        self.block_combo.blockSignals(False)
        self._validate_inputs()

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
        else:
            self.gender_note.setText("Please create or select a residential block.")

        self._validate_inputs()

    def _on_quick_create_block(self):
        names = [b["name"] for b in self.blocks]
        dlg = BlockSetupDialog(self, client=self.client, existing_names=names)
        if dlg.exec() and dlg.result_data:
            new_block = dlg.result_data
            self.blocks.append(new_block)
            self._populate_block_combo(initial_block=new_block["name"])
            self._on_block_changed()

    def on_save(self):
        self._num_touched = True
        if not self._validate_inputs():
            return

        block_data = self._get_selected_block()
        if not block_data:
            QMessageBox.warning(self, "No Block", "Please create or select a residential block first.")
            return

        block_name = str(block_data["name"]).strip().upper()
        block_gender = str(block_data["gender"]).strip().lower()

        num = self.num_edit.text().strip()
        if not num:
            self.num_error_label.setText("Room number is required.")
            self.num_error_label.setVisible(True)
            return

        self._busy = True
        self.save_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

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

        # Background action plumbing: every room/block write and every read
        # used to build a dialog runs on the task pool, never on the GUI thread.
        self.tasks = TaskRunner(self)
        self._actions_busy: bool = False
        self._info_busy: bool = False
        self._loaded_once: bool = False
        self._closing: bool = False
        self._data_generation: int = 0
        self._action_texts: dict[Button, str] = {}
        self._reload_after_action: bool = False
        self._last_deleted_row: int = -1

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

        self.add_btn = Button.primary("Add room", icon="plus")
        self.add_btn.setFixedHeight(36)
        self.add_btn.setToolTip("Configure a new dormitory room")
        self.add_btn.clicked.connect(self.on_add)
        toolbar.addWidget(self.add_btn)

        self.edit_btn = Button.secondary("Edit", icon="edit")
        self.edit_btn.setFixedHeight(36)
        self.edit_btn.setEnabled(False)
        self.edit_btn.setToolTip("Select a room from the table to edit")
        self.edit_btn.clicked.connect(self.on_edit)
        toolbar.addWidget(self.edit_btn)

        self.delete_btn = Button.danger("Delete", icon="trash")
        self.delete_btn.setFixedHeight(36)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setToolTip("Select a room from the table to delete")
        self.delete_btn.clicked.connect(self.on_delete)
        toolbar.addWidget(self.delete_btn)

        self.refresh_btn = IconButton("refresh", "Reload the room list")
        self.refresh_btn.setFixedHeight(36)
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
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
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

    # --------------------------------------------------- background plumbing
    def _show_banner(self, kind: str, title: str, message: str) -> None:
        self.error_banner.set_kind(kind)
        self.error_banner.set_title(title)
        self.error_banner.set_message(message)
        self.error_banner.setVisible(True)

    def _set_actions_busy(self, busy: bool, active_button: Button | None = None) -> None:
        """Disable/restore room controls while a write or refresh runs."""
        self._actions_busy = busy
        if busy:
            for button in (self.add_btn, self.edit_btn, self.delete_btn, self.blocks_btn):
                self._action_texts.setdefault(button, button.text())
                button.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            if active_button is not None:
                active_button.setText(_WORKING_TEXT)
            return

        for button, text in self._action_texts.items():
            try:
                button.setText(text)
            except RuntimeError:  # widget already destroyed (window closing)
                pass
        self._action_texts.clear()
        self.add_btn.setEnabled(True)
        self.blocks_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        """Update edit/delete button state and tooltips based on current selection."""
        if self._actions_busy:
            return
        row = self.table.currentRow()
        has_sel = (
            0 <= row < len(self.rows)
            and bool(self.table.selectionModel() and self.table.selectionModel().hasSelection())
            and not self.table.isRowHidden(row)
        )
        self.edit_btn.setEnabled(has_sel)
        self.delete_btn.setEnabled(has_sel)
        if has_sel:
            self.edit_btn.setToolTip("Edit the selected room")
            self.delete_btn.setToolTip("Delete the selected room (only when no resident is assigned)")
        else:
            self.edit_btn.setToolTip("Select a room from the table to edit")
            self.delete_btn.setToolTip("Select a room from the table to delete")

    def _current_room_id(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.rows):
            return self.rows[row].get("id")
        return None

    def _fetch_snapshot(self) -> dict:
        """Worker read: rooms + occupancy + blocks, all under CLIENT_LOCK."""
        resp = self.client.table("rooms").select("*").order("block").order("number").execute()
        data = getattr(resp, "data", None)
        rows = [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []
        occupancy = room_occupancy(self.client)
        if not isinstance(occupancy, dict):
            occupancy = {}

        try:
            resp_b = self.client.table("blocks").select("*").order("name").execute()
            data_b = getattr(resp_b, "data", None)
            blocks = [b for b in data_b if isinstance(b, dict)] if isinstance(data_b, list) else []
        except Exception:  # noqa: BLE001 - blocks are a best-effort addition
            blocks = []

        if not blocks and rows:
            seen = {}
            for r in rows:
                b_name = str(r.get("block", "")).strip().upper()
                if b_name and b_name not in seen:
                    seen[b_name] = {"name": b_name, "gender": str(r.get("gender", "male")).lower()}
            blocks = list(seen.values())

        return {"rows": rows, "occupancy": occupancy, "blocks": blocks}

    def _apply_snapshot(self, snapshot: dict, select_id=None) -> None:
        if select_id is None:
            select_id = self._current_room_id()
        self.rows = list(snapshot.get("rows") or [])
        self.occupancy_map = dict(snapshot.get("occupancy") or {})
        self.blocks = list(snapshot.get("blocks") or [])
        self.count_badge.setText(f"{len(self.rows)} rooms")
        self._render_rows(select_id=select_id)
        self._set_loading(False)

    def _load_sync(self) -> None:
        """Initial page load only; keeps the constructor contract synchronous."""
        self._set_loading(True)
        try:
            snapshot = self._fetch_snapshot()
        except Exception as exc:  # noqa: BLE001 - reported inline
            self._show_banner(
                "error",
                "Rooms could not be loaded",
                f"The room list could not be loaded ({human_error(exc)}). "
                "Check the connection, then use Refresh to try again.",
            )
            self._set_loading(False)
            return
        self.error_banner.setVisible(False)
        self._apply_snapshot(snapshot, select_id=None)

    def _on_reload_success(self, snapshot, generation: int) -> None:
        if generation != self._data_generation or self._closing:
            return
        self.error_banner.setVisible(False)
        self._apply_snapshot(snapshot)

    def _on_reload_failed(self, message: str) -> None:
        self._show_banner(
            "error",
            "Rooms could not be loaded",
            f"The room list could not be reloaded ({message}). "
            "Check the connection, then use Refresh to try again.",
        )
        self._set_loading(False)

    def _on_reload_finished(self) -> None:
        if self._closing:
            self._actions_busy = False
            return
        self._set_loading(False)
        self._set_actions_busy(False)

    def _reload_async(self) -> None:
        if self.tasks.is_busy(_RELOAD_KEY) or self._actions_busy:
            return
        generation = self._data_generation
        self._set_actions_busy(True)
        self._show_banner("info", _WORKING_TEXT, "Refreshing the room list…")
        self._set_loading(True)
        started = self.tasks.run(
            _RELOAD_KEY,
            self._fetch_snapshot,
            on_success=lambda snapshot: self._on_reload_success(snapshot, generation),
            on_failed=self._on_reload_failed,
            on_finished=self._on_reload_finished,
        )
        if not started:
            self._set_actions_busy(False)
            self._set_loading(False)

    def reload(self):
        """Refresh rooms; the first (constructor) call stays synchronous."""
        if not self._loaded_once:
            self._loaded_once = True
            self._load_sync()
            return
        self._reload_async()

    def _render_rows(self, select_id=None):
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
        if select_id is not None:
            for index, row in enumerate(self.rows):
                if row.get("id") == select_id:
                    self.table.selectRow(index)
                    break
        self._update_action_buttons()

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
        self._update_action_buttons()

    # ------------------------------------------------------------ rendering
    def _set_loading(self, loading: bool) -> None:
        """Swap the table for the Skeleton while ``reload()`` is in flight."""
        if loading:
            self.stack.setCurrentWidget(self.skeleton)
            self.skeleton.raise_()
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
    def _fetch_occupants(self, room_id) -> list[dict]:
        """Worker read for the room info card (no GUI objects touched)."""
        query = self.client.table("students").select(
            "card_id, first_name, last_name, faculty"
        ).eq("room_id", room_id)
        try:
            query = query.eq("status", "active")
        except Exception:  # noqa: BLE001 - best-effort status filter, as before
            pass
        resp = query.execute()
        data = getattr(resp, "data", None)
        return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []

    def _show_room_info(self, room_copy: dict, occupants) -> None:
        if self._closing:
            return
        room_data = dict(room_copy)
        room_data["occupants"] = list(occupants or [])
        # The dialog gets its data pre-loaded, so passing ``None`` as the client
        # prevents its constructor from issuing a blocking occupant query.
        dlg = RoomInfoCardDialog(self, room_data, None)
        try:
            dlg.exec()
        finally:
            dlg.deleteLater()

    def _on_info_failed(self, message: str) -> None:
        self._show_banner(
            "error",
            "Room details could not be loaded",
            f"The occupant lookup failed ({message}). The room list is unchanged.",
        )

    def _on_info_finished(self) -> None:
        self._info_busy = False

    def on_row_double_clicked(self, row: int, col: int):
        if self._actions_busy or self._info_busy or self.tasks.is_busy(_INFO_KEY):
            return
        if not (0 <= row < len(self.rows)):
            return

        room = self.rows[row]
        room_copy = dict(room)
        room_copy["occupied"] = self.occupancy_map.get(room.get("id"), 0)
        self._info_busy = True
        started = self.tasks.run(
            _INFO_KEY,
            lambda: self._fetch_occupants(room.get("id")),
            on_success=lambda occupants: self._show_room_info(room_copy, occupants),
            on_failed=self._on_info_failed,
            on_finished=self._on_info_finished,
        )
        if not started:
            self._info_busy = False

    def on_manage_blocks(self):
        if self._actions_busy or self._info_busy:
            return
        dlg = ManageBlocksDialog(
            self,
            client=self.client,
            rooms=self.rows,
            occupancy=self.occupancy_map,
            blocks=self.blocks,
        )
        dlg.exec()
        if dlg.blocks:
            self.blocks = [dict(b) for b in dlg.blocks]
        if not self._closing:
            self.reload()

    # --------------------------------------------------------- room actions
    def _start_action(
        self,
        key: str,
        fn,
        *,
        button: Button,
        working_message: str,
        on_success,
        on_failed,
    ) -> bool:
        if self._actions_busy or self.tasks.is_busy(_ACTION_KEY):
            return False
        self._set_actions_busy(True, button)
        self._show_banner("info", _WORKING_TEXT, working_message)
        started = self.tasks.run(
            key,
            fn,
            on_success=on_success,
            on_failed=on_failed,
            on_finished=self._on_action_finished,
        )
        if not started:
            self._set_actions_busy(False)
        return started

    def _on_action_finished(self) -> None:
        if self._closing:
            self._actions_busy = False
            return
        self._set_actions_busy(False)
        if self._reload_after_action:
            self._reload_after_action = False
            # The write already succeeded; the authoritative rows are fetched
            # in the background so a refresh failure cannot undo it.
            self.reload()

    def _on_created(self, created, message: str) -> None:
        self._data_generation += 1
        self._show_banner("success", "Room created", message)
        self._reload_after_action = True

    def _on_create_failed(self, message: str) -> None:
        self._show_banner(
            "error",
            "Room could not be created",
            f"The room was not created. {message}",
        )

    def _on_updated(self, data, room_id, message: str) -> None:
        self._data_generation += 1
        for row in self.rows:
            if row.get("id") == room_id:
                row.update(data)
                break
        self._render_rows(select_id=room_id)
        self._show_banner("success", "Room updated", message)
        self._reload_after_action = True

    def _on_update_failed(self, message: str) -> None:
        self._show_banner(
            "error",
            "Room could not be updated",
            f"The room was not updated. {message}",
        )

    def _on_deleted(self, room_id, message: str) -> None:
        self._data_generation += 1
        self.rows = [row for row in self.rows if row.get("id") != room_id]
        select_id = None
        if self.rows and getattr(self, "_last_deleted_row", -1) >= 0:
            target_idx = min(self._last_deleted_row, len(self.rows) - 1)
            select_id = self.rows[target_idx].get("id")
        self._render_rows(select_id=select_id)
        self._show_banner("success", "Room deleted", message)
        self._reload_after_action = True

    def _on_delete_failed(self, message: str) -> None:
        self._show_banner(
            "error",
            "Room could not be deleted",
            f"The room was not removed. {message}",
        )

    def on_add(self):
        if self._actions_busy or self._info_busy or self.tasks.is_busy(_ACTION_KEY):
            return

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
                    new_block = dict(b_dlg.result_data)
                    if not any(
                        str(b.get("name", "")).upper() == str(new_block["name"]).upper()
                        for b in self.blocks
                    ):
                        self.blocks.append(new_block)
                else:
                    return
            else:
                return

        dlg = RoomSetupDialog(self, client=self.client, blocks=self.blocks)
        if not dlg.exec() or not dlg.result_data:
            return

        data = dict(dlg.result_data)
        message = (
            f"Room {data['block']}-{data['number']} "
            f"({data['gender'].capitalize()}) configured successfully."
        )

        def work():
            self.client.table("rooms").insert(data).execute()
            return data

        self._start_action(
            _ACTION_KEY,
            work,
            button=self.add_btn,
            working_message=f"Creating room {data['block']}-{data['number']}…",
            on_success=lambda created: self._on_created(created, message),
            on_failed=self._on_create_failed,
        )

    def on_edit(self):
        if self._actions_busy or self._info_busy or self.tasks.is_busy(_ACTION_KEY):
            return
        r = self.table.currentRow()
        if r < 0 or r >= len(self.rows):
            QMessageBox.information(self, "Select room", "Please select a room from the table to edit.")
            return
        room = self.rows[r]
        room_id = room.get("id")
        if room_id is None:
            return
        occ = self.occupancy_map.get(room_id, 0)
        dlg = RoomSetupDialog(self, room=room, current_occupancy=occ, client=self.client, blocks=self.blocks)
        if not dlg.exec() or not dlg.result_data:
            return

        data = dict(dlg.result_data)
        message = (
            f"Room {data['block']}-{data['number']} "
            f"({data['gender'].capitalize()}) updated successfully."
        )

        def work():
            self.client.table("rooms").update(data).eq("id", room_id).execute()
            return data

        self._start_action(
            _ACTION_KEY,
            work,
            button=self.edit_btn,
            working_message=f"Updating room {data['block']}-{data['number']}…",
            on_success=lambda updated: self._on_updated(updated, room_id, message),
            on_failed=self._on_update_failed,
        )

    def on_delete(self):
        if self._actions_busy or self._info_busy or self.tasks.is_busy(_ACTION_KEY):
            return
        r = self.table.currentRow()
        if r < 0 or r >= len(self.rows):
            QMessageBox.information(self, "Select room", "Please select a room from the table to delete.")
            return
        self._last_deleted_row = r
        room = self.rows[r]
        room_id = room.get("id")
        if room_id is None:
            return
        if self.occupancy_map.get(room_id, 0) > 0:
            QMessageBox.warning(self, "Room Occupied", "Cannot delete a room that still has active residents assigned.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete Room",
            f"Are you sure you want to delete room Block {room['block']} — {room['number']}?",
        )
        if confirm != QMessageBox.StandardButton.Yes and confirm != QMessageBox.Yes:
            return

        message = f"Room {room['block']}-{room['number']} has been removed."

        def work():
            self.client.table("rooms").delete().eq("id", room_id).execute()
            return room_id

        self._start_action(
            _ACTION_KEY,
            work,
            button=self.delete_btn,
            working_message=f"Deleting room {room['block']}-{room['number']}…",
            on_success=lambda deleted_id: self._on_deleted(deleted_id, message),
            on_failed=self._on_delete_failed,
        )

    def closeEvent(self, event):  # noqa: N802 - Qt API
        self._closing = True
        super().closeEvent(event)
