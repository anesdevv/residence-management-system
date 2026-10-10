from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem, QLabel,
)


class ResidentsPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name or card ID…")
        self.search.textChanged.connect(self.render)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Card ID", "Name", "Gender", "Room", "Status"])

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Residents</h2>", textFormat=Qt.TextFormat.RichText))
        layout.addWidget(self.search)
        layout.addWidget(self.table)

        self.reload()

    def reload(self):
        resp = self.client.table("students") \
            .select("card_id, first_name, last_name, gender, status, rooms(block, number)") \
            .eq("status", "active").execute()
        self.rows = resp.data or []
        self.render()

    def render(self):
        needle = self.search.text().lower().strip()
        filtered = [
            r for r in self.rows
            if needle in f"{r['first_name']} {r['last_name']} {r['card_id']}".lower()
        ]
        self.table.setRowCount(len(filtered))
        for i, r in enumerate(filtered):
            room = r.get("rooms") or {}
            self.table.setItem(i, 0, QTableWidgetItem(r["card_id"]))
            self.table.setItem(i, 1, QTableWidgetItem(f"{r['first_name']} {r['last_name']}"))
            self.table.setItem(i, 2, QTableWidgetItem(r["gender"]))
            self.table.setItem(i, 3, QTableWidgetItem(f"{room.get('block','—')} / {room.get('number','—')}"))
            self.table.setItem(i, 4, QTableWidgetItem(r["status"]))
