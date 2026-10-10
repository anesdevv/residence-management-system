from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from ...client import room_occupancy


class OverviewPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.labels: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Overview</h2>", textFormat=Qt.TextFormat.RichText))
        for key, title in [
            ("pending", "Pending accounts"),
            ("reports", "Open maintenance reports"),
            ("requests", "Pending room-change requests"),
            ("occupancy", "Total residents (active)"),
        ]:
            row = QLabel(f"{title}: —")
            self.labels[key] = row
            layout.addWidget(row)

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)
        layout.addWidget(refresh)
        layout.addStretch(1)

    def _count(self, table, **filters) -> int:
        q = self.client.table(table).select("id", count="exact")
        for col, val in filters.items():
            q = q.eq(col, val)
        return q.execute().count or 0

    def reload(self):
        pending = self._count("students", status="pending")
        reports = self._count("maintenance_reports", status="pending")
        requests = self._count("room_change_requests", status="pending")
        occupancy = sum(room_occupancy(self.client).values())
        self.labels["pending"].setText(f"Pending accounts: {pending}")
        self.labels["reports"].setText(f"Open maintenance reports: {reports}")
        self.labels["requests"].setText(f"Pending room-change requests: {requests}")
        self.labels["occupancy"].setText(f"Total residents (active): {occupancy}")
