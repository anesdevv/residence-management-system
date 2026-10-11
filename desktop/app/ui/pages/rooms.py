from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox, QFrame, QLineEdit,
    QComboBox,
)
from ...client import room_occupancy
from ..icons import get_icon, get_pixmap
from ..theme import apply_button_style


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
        self.table.horizontalHeader().setStretchLastSection(True)
        tc_layout.addWidget(self.table)
        layout.addWidget(table_card, 1)

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
        self.rows = self.client.table("rooms").select("*").order("block").order("number").execute().data or []
        self.occupancy_map = room_occupancy(self.client)
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

    def _prompt(self, block="", floor="0", number="", capacity="1", gender="male"):
        block, ok = QInputDialog.getText(self, "Room Setup", "Block (e.g. A, B, C):", text=block)
        if not ok:
            return None
        floor_s, ok = QInputDialog.getText(self, "Room Setup", "Floor (0, 1, 2...):", text=floor)
        if not ok:
            return None
        number, ok = QInputDialog.getText(self, "Room Setup", "Room Number:", text=number)
        if not ok:
            return None
        cap_s, ok = QInputDialog.getText(self, "Room Setup", "Bed Capacity:", text=capacity)
        if not ok:
            return None
        try:
            floor_val = int(floor_s or 0)
            cap_val = int(cap_s or 1)
        except ValueError:
            QMessageBox.warning(self, "Invalid Entry", "Floor and capacity must be valid integers.")
            return None
        if not block.strip() or not number.strip():
            QMessageBox.warning(self, "Missing Data", "Block and Room Number cannot be empty.")
            return None
        if cap_val <= 0:
            QMessageBox.warning(self, "Invalid Capacity", "Capacity must be at least 1.")
            return None
        gender_idx = 0 if gender == "male" else 1
        gender, ok = QInputDialog.getItem(self, "Room Setup", "Designated Block Gender:", ["male", "female"], gender_idx, False)
        if not ok:
            return None
        return {
            "block": block.strip(),
            "floor": floor_val,
            "number": number.strip(),
            "capacity": cap_val,
            "gender": gender,
        }

    def on_add(self):
        data = self._prompt()
        if not data:
            return
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
        data = self._prompt(room["block"], str(room["floor"]), room["number"], str(room["capacity"]), room["gender"])
        if not data:
            return
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
