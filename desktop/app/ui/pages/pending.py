from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox, QTextEdit,
)
from ...client import room_occupancy, official_lookup


class PendingPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Card ID", "Name", "Gender", "Official list", "Requested"])
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)

        self.approve = QPushButton("Approve")
        self.approve.clicked.connect(self.on_approve)
        self.reject = QPushButton("Reject")
        self.reject.clicked.connect(self.on_reject)

        actions = QHBoxLayout()
        actions.addWidget(self.approve)
        actions.addWidget(self.reject)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Pending accounts</h2>", textFormat=Qt.TextFormat.RichText))
        layout.addWidget(self.table)
        layout.addWidget(self.detail)
        layout.addLayout(actions)

        self.reload()

    def reload(self):
        resp = self.client.table("students").select("*").eq("status", "pending").execute()
        self.rows = resp.data or []
        self.official = official_lookup(self.client)
        self.table.setRowCount(len(self.rows))
        for i, s in enumerate(self.rows):
            match = "match" if s["card_id"] in self.official else "no match"
            self.table.setItem(i, 0, QTableWidgetItem(s["card_id"]))
            self.table.setItem(i, 1, QTableWidgetItem(f"{s['first_name']} {s['last_name']}"))
            self.table.setItem(i, 2, QTableWidgetItem(s["gender"]))
            self.table.setItem(i, 3, QTableWidgetItem(match))
            self.table.setItem(i, 4, QTableWidgetItem(s["created_at"]))

    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def show_detail(self):
        s = self.selected()
        if not s:
            return
        o = self.official.get(s["card_id"])
        official = (
            f"MATCH with official record:\n  {o['first_name']} {o['last_name']}, "
            f"{o.get('birth_date') or '—'}, {o.get('gender') or '—'}"
            if o else "NO MATCH in official list."
        )
        self.detail.setPlainText(
            f"Card ID: {s['card_id']}\n"
            f"Name: {s['first_name']} {s['last_name']}\n"
            f"Birth date: {s['birth_date']}\n"
            f"Gender: {s['gender']}\n"
            f"Phone: {s['phone']}\n"
            f"Email: {s['email'] or '—'}\n"
            f"University: {s['university']} / {s['faculty']}\n"
            f"Study level: {s['study_level']} | Wilaya: {s['wilaya']}\n\n"
            f"{official}"
        )

    def on_approve(self):
        s = self.selected()
        if not s:
            return
        rooms = self.client.table("rooms").select("id, block, number, capacity, gender") \
            .eq("gender", s["gender"]).execute().data or []
        occ = room_occupancy(self.client)
        options = []
        for r in rooms:
            free = r["capacity"] - occ.get(r["id"], 0)
            options.append(f"Block {r['block']} — {r['number']} ({free} free) | id={r['id']}")
        if not options:
            QMessageBox.warning(self, "No rooms", "No rooms available for this gender.")
            return
        choice, ok = QInputDialog.getItem(self, "Assign room", "Room:", options, 0, False)
        if not ok:
            return
        room_id = choice.split("id=")[1].strip()
        try:
            self.client.rpc("approve_student", {"p_student": s["id"], "p_room": room_id}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        QMessageBox.information(self, "Approved", f"{s['first_name']} {s['last_name']} approved.")
        self.reload()

    def on_reject(self):
        s = self.selected()
        if not s:
            return
        reason, ok = QInputDialog.getMultiLineText(self, "Reject", "Reason for rejection:")
        if not ok or not reason.strip():
            return
        try:
            self.client.rpc("reject_student", {"p_student": s["id"], "p_reason": reason.strip()}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        self.reload()