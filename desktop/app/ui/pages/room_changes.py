from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox,
)
from ...client import room_occupancy


class RoomChangesPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Student", "Status", "Reason"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        approve = QPushButton("Approve")
        approve.clicked.connect(self.on_approve)
        reject = QPushButton("Reject")
        reject.clicked.connect(self.on_reject)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)

        actions = QHBoxLayout()
        for b in (approve, reject, refresh):
            actions.addWidget(b)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Room-change requests</h2>", textFormat=Qt.TextFormat.RichText))
        layout.addWidget(self.table)
        layout.addLayout(actions)

        self.reload()

    def reload(self):
        self.rows = self.client.table("room_change_requests") \
            .select("*, students(first_name, last_name, gender)") \
            .eq("status", "pending").order("created_at", desc=True).execute().data or []
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            st = r.get("students") or {}
            self.table.setItem(i, 0, QTableWidgetItem(f"{st.get('first_name','')} {st.get('last_name','')}"))
            self.table.setItem(i, 1, QTableWidgetItem(r["status"]))
            self.table.setItem(i, 2, QTableWidgetItem(r["reason"]))

    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def on_approve(self):
        r = self.selected()
        if not r:
            return
        gender = (r.get("students") or {}).get("gender", "male")
        rooms = self.client.table("rooms").select("id, block, number, capacity, gender") \
            .eq("gender", gender).execute().data or []
        occ = room_occupancy(self.client)
        options = [
            f"Block {room['block']} — {room['number']} "
            f"({room['capacity'] - occ.get(room['id'], 0)} free) | id={room['id']}"
            for room in rooms
        ]
        if not options:
            QMessageBox.warning(self, "No rooms", "No rooms available for this gender.")
            return
        choice, ok = QInputDialog.getItem(self, "Assign room", "New room:", options, 0, False)
        if not ok:
            return
        room_id = choice.split("id=")[1].strip()
        try:
            self.client.rpc("approve_room_change", {"p_request": r["id"], "p_room": room_id}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
        self.reload()

    def on_reject(self):
        r = self.selected()
        if not r:
            return
        reason, ok = QInputDialog.getMultiLineText(self, "Reject", "Reason:")
        if not ok or not reason.strip():
            return
        try:
            self.client.rpc("reject_room_change", {"p_request": r["id"], "p_reason": reason.strip()}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
        self.reload()
