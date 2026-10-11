from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QMessageBox, QFrame, QLineEdit,
    QComboBox, QSpinBox, QDialog, QFormLayout,
)
from ...client import room_occupancy
from ..icons import get_icon, get_pixmap
from ..theme import apply_button_style, DESKTOP_STYLESHEET
from ..infocard import RoomInfoCardDialog


class RoomSetupDialog(QDialog):
    def __init__(self, parent=None, room=None, current_occupancy=0):
        super().__init__(parent)
        self.setWindowTitle("Edit Room Configuration" if room else "Add Dormitory Room")
        self.setMinimumWidth(400)
        self.setStyleSheet(DESKTOP_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        card = QFrame()
        card.setObjectName("cardFrame")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 20, 20, 20)
        c_layout.setSpacing(14)

        header_lbl = QLabel("Edit Room Configuration" if room else "Configure New Dormitory Room")
        header_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #f8fafc;")
        c_layout.addWidget(header_lbl)

        form = QFormLayout()
        form.setSpacing(12)

        self.block_edit = QLineEdit(room.get("block", "A") if room else "A")
        self.block_edit.setPlaceholderText("e.g. A, B, C...")

        self.floor_spin = QSpinBox()
        self.floor_spin.setRange(0, 15)
        self.floor_spin.setValue(int(room.get("floor", 0)) if room else 0)

        self.num_edit = QLineEdit(str(room.get("number", "")) if room else "")
        self.num_edit.setPlaceholderText("e.g. 101, 204...")

        min_cap = max(1, current_occupancy)
        self.cap_spin = QSpinBox()
        self.cap_spin.setRange(min_cap, 8)
        self.cap_spin.setValue(int(room.get("capacity", 2)) if room else 2)

        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["Male", "Female"])
        current_gender = room.get("gender", "male") if room else "male"
        self.gender_combo.setCurrentText(current_gender.capitalize())

        form.addRow("Dormitory Block:", self.block_edit)
        form.addRow("Floor Level:", self.floor_spin)
        form.addRow("Room Number:", self.num_edit)
        form.addRow(f"Bed Capacity (Min {min_cap}):", self.cap_spin)
        form.addRow("Designated Gender:", self.gender_combo)

        c_layout.addLayout(form)

        if current_occupancy > 0:
            self.gender_combo.setEnabled(False)
            lock_note = QLabel(f"🔒 Gender locked: Room currently has {current_occupancy} active occupant(s).")
            lock_note.setStyleSheet("font-size: 11px; color: #fbbf24; padding-top: 4px;")
            c_layout.addWidget(lock_note)

        layout.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        cancel_btn = QPushButton("Cancel")
        apply_button_style(cancel_btn, "secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save Room" if room else "Create Room")
        apply_button_style(save_btn, "primary")
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
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []
        self.occupancy_map: dict[str, int] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Row
        header_row = QHBoxLayout()
        header_vbox = QVBoxLayout()
        title_lbl = QLabel("Dormitory Rooms & Capacity")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #f8fafc;")
        sub_lbl = QLabel("Manage dormitory residential blocks, room numbers, capacities, and live bed occupancy.")
        sub_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        header_vbox.addWidget(title_lbl)
        header_vbox.addWidget(sub_lbl)
        header_row.addLayout(header_vbox)
        header_row.addStretch(1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setIcon(get_icon("refresh", size=14, color="#cbd5e1"))
        apply_button_style(refresh_btn, "secondary")
        refresh_btn.clicked.connect(self.reload)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        # Filter & Action Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search room number or block...")
        self.search_input.textChanged.connect(self.filter_table)
        toolbar.addWidget(self.search_input, 1)

        self.gender_filter = QComboBox()
        self.gender_filter.addItems(["All Genders", "Male Blocks", "Female Blocks"])
        self.gender_filter.currentIndexChanged.connect(self.filter_table)
        toolbar.addWidget(self.gender_filter)

        add_btn = QPushButton("Add Room")
        add_btn.setIcon(get_icon("plus", size=14, color="#ffffff"))
        apply_button_style(add_btn, "primary")
        add_btn.clicked.connect(self.on_add)

        edit_btn = QPushButton("Edit")
        edit_btn.setIcon(get_icon("edit", size=14, color="#cbd5e1"))
        apply_button_style(edit_btn, "secondary")
        edit_btn.clicked.connect(self.on_edit)

        delete_btn = QPushButton("Delete")
        delete_btn.setIcon(get_icon("trash", size=14, color="#ffffff"))
        apply_button_style(delete_btn, "danger")
        delete_btn.clicked.connect(self.on_delete)

        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(delete_btn)

        layout.addLayout(toolbar)

        # Table Frame
        table_card = QFrame()
        table_card.setObjectName("cardFrame")
        tc_layout = QVBoxLayout(table_card)
        tc_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Block", "Floor", "Room No.", "Gender", "Total Beds", "Occupied", "Availability"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        self.table.horizontalHeader().setStretchLastSection(True)
        tc_layout.addWidget(self.table)
        layout.addWidget(table_card, 1)

        tip_lbl = QLabel("💡 Tip: Double-click any room to inspect active occupants and bed allocation.")
        tip_lbl.setStyleSheet("font-size: 11px; color: #64748b; padding-left: 2px;")
        layout.addWidget(tip_lbl)

        self.reload()

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

    def reload(self):
        try:
            self.rows = self.client.table("rooms").select("*").order("block").order("number").execute().data or []
            self.occupancy_map = room_occupancy(self.client)
        except Exception:
            return
        self.table.setRowCount(len(self.rows))

        for i, r in enumerate(self.rows):
            cap = r.get("capacity", 1)
            occ = self.occupancy_map.get(r["id"], 0)
            free = cap - occ
            avail_text = f"{free} bed(s) available" if free > 0 else "Full"

            block_item = QTableWidgetItem(f"Block {r['block']}")
            block_item.setIcon(get_icon("building", size=14, color="#38bdf8"))
            floor_item = QTableWidgetItem(f"Floor {r['floor']}")
            num_item = QTableWidgetItem(f"Room {r['number']}")
            gender_item = QTableWidgetItem(str(r["gender"]).capitalize())
            cap_item = QTableWidgetItem(str(cap))
            occ_item = QTableWidgetItem(str(occ))
            avail_item = QTableWidgetItem(avail_text)

            if free > 0:
                avail_item.setForeground(QColor("#34d399"))
            else:
                avail_item.setForeground(QColor("#94a3b8"))

            self.table.setItem(i, 0, block_item)
            self.table.setItem(i, 1, floor_item)
            self.table.setItem(i, 2, num_item)
            self.table.setItem(i, 3, gender_item)
            self.table.setItem(i, 4, cap_item)
            self.table.setItem(i, 5, occ_item)
            self.table.setItem(i, 6, avail_item)

        self.filter_table()

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
        if r < 0:
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
        if r < 0:
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
