from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox,
)
from ...client import room_occupancy


class RoomsPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Block", "Floor", "Number", "Capacity", "Gender", "Occupied"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        add = QPushButton("Add room")
        add.clicked.connect(self.on_add)
        edit = QPushButton("Edit room")
        edit.clicked.connect(self.on_edit)
        delete = QPushButton("Delete room")
        delete.clicked.connect(self.on_delete)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)

        actions = QHBoxLayout()
        for b in (add, edit, delete, refresh):
            actions.addWidget(b)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Rooms</h2>", textFormat=Qt.TextFormat.RichText))
        layout.addWidget(self.table)
        layout.addLayout(actions)

        self.reload()

    def reload(self):
        self.rows = self.client.table("rooms").select("*").order("block").order("number").execute().data or []
        occ = room_occupancy(self.client)
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            self.table.setItem(i, 0, QTableWidgetItem(r["block"]))
            self.table.setItem(i, 1, QTableWidgetItem(str(r["floor"])))
            self.table.setItem(i, 2, QTableWidgetItem(r["number"]))
            self.table.setItem(i, 3, QTableWidgetItem(str(r["capacity"])))
            self.table.setItem(i, 4, QTableWidgetItem(r["gender"]))
            self.table.setItem(i, 5, QTableWidgetItem(str(occ.get(r["id"], 0))))

    def _prompt(self, block="", floor="0", number="", capacity="1", gender="male"):
        block, ok = QInputDialog.getText(self, "Room", "Block:", text=block)
        if not ok:
            return None
        floor_s, ok = QInputDialog.getText(self, "Room", "Floor:", text=floor)
        if not ok:
            return None
        number, ok = QInputDialog.getText(self, "Room", "Number:", text=number)
        if not ok:
            return None
        cap_s, ok = QInputDialog.getText(self, "Room", "Capacity:", text=capacity)
        if not ok:
            return None
        try:
            floor_val = int(floor_s or 0)
            cap_val = int(cap_s or 1)
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Floor and capacity must be whole numbers.")
            return None
        gender_idx = 0 if gender == "male" else 1
        gender, ok = QInputDialog.getItem(self, "Room", "Gender:", ["male", "female"], gender_idx, False)
        if not ok:
            return None
        return {
            "block": block.strip(), "floor": floor_val, "number": number.strip(),
            "capacity": cap_val, "gender": gender,
        }

    def on_add(self):
        data = self._prompt()
        if not data:
            return
        try:
            self.client.table("rooms").insert(data).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
        self.reload()

    def on_edit(self):
        r = self.table.currentRow()
        if r < 0:
            return
        room = self.rows[r]
        data = self._prompt(room["block"], str(room["floor"]), room["number"], str(room["capacity"]), room["gender"])
        if not data:
            return
        try:
            self.client.table("rooms").update(data).eq("id", room["id"]).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
        self.reload()

    def on_delete(self):
        r = self.table.currentRow()
        if r < 0:
            return
        room = self.rows[r]
        if room_occupancy(self.client).get(room["id"], 0) > 0:
            QMessageBox.warning(self, "Room occupied", "Cannot delete a room that still has residents assigned.")
            return
        confirm = QMessageBox.question(self, "Delete", f"Delete room {room['block']}-{room['number']}?")
        if confirm != QMessageBox.Yes:
            return
        try:
            self.client.table("rooms").delete().eq("id", room["id"]).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
        self.reload()
