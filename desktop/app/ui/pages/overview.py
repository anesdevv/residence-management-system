from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QFrame,
)
from ...client import room_occupancy
from ..icons import get_pixmap, get_icon
from ..theme import apply_button_style


class StatCard(QFrame):
    def __init__(self, title: str, subtitle: str, icon_name: str, accent_color: str, bg_tint: str):
        super().__init__()
        self.setObjectName("cardFrame")
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(18, 18, 18, 18)

        top_row = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_pixmap(icon_name, size=24, color=accent_color))
        icon_lbl.setStyleSheet(f"background-color: {bg_tint}; border-radius: 6px; padding: 6px;")

        top_row.addWidget(icon_lbl)
        top_row.addStretch(1)
        layout.addLayout(top_row)

        self.value_lbl = QLabel("0")
        self.value_lbl.setStyleSheet(f"font-size: 32px; font-weight: 800; color: {accent_color}; margin-top: 4px;")
        layout.addWidget(self.value_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #0f172a;")
        layout.addWidget(title_lbl)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet("font-size: 11px; color: #64748b;")
        sub_lbl.setWordWrap(True)
        layout.addWidget(sub_lbl)

    def set_value(self, val: int):
        self.value_lbl.setText(str(val))


class OverviewPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Header with Title and Refresh
        header_row = QHBoxLayout()
        header_vbox = QVBoxLayout()
        title_lbl = QLabel("Department Operations Dashboard")
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #0f172a;")
        sub_lbl = QLabel("Real-time dormitory metrics, intake triage, and occupancy monitoring.")
        sub_lbl.setStyleSheet("font-size: 12px; color: #64748b;")
        header_vbox.addWidget(title_lbl)
        header_vbox.addWidget(sub_lbl)
        header_row.addLayout(header_vbox)
        header_row.addStretch(1)

        refresh_btn = QPushButton("Refresh Metrics")
        refresh_btn.setIcon(get_icon("refresh", size=14, color="#334155"))
        apply_button_style(refresh_btn, "secondary")
        refresh_btn.clicked.connect(self.reload)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        # 4 KPI Stat Cards
        grid = QGridLayout()
        grid.setSpacing(16)

        self.pending_card = StatCard(
            title="Pending Registrations",
            subtitle="Student applications awaiting verification & room allocation",
            icon_name="pending",
            accent_color="#d97706",
            bg_tint="#fef3c7",
        )
        self.reports_card = StatCard(
            title="Open Maintenance Tickets",
            subtitle="Facility repairs requiring inspection & technician dispatch",
            icon_name="maintenance",
            accent_color="#2563eb",
            bg_tint="#dbeafe",
        )
        self.requests_card = StatCard(
            title="Room Transfer Requests",
            subtitle="Approved resident relocation and room swap applications",
            icon_name="room_changes",
            accent_color="#7c3aed",
            bg_tint="#ede9fe",
        )
        self.occupancy_card = StatCard(
            title="Active Housed Residents",
            subtitle="Current university students occupying designated rooms",
            icon_name="residents",
            accent_color="#059669",
            bg_tint="#d1fae5",
        )

        grid.addWidget(self.pending_card, 0, 0)
        grid.addWidget(self.reports_card, 0, 1)
        grid.addWidget(self.requests_card, 1, 0)
        grid.addWidget(self.occupancy_card, 1, 1)
        layout.addLayout(grid)

        # Operational Guidelines Card
        guideline_card = QFrame()
        guideline_card.setObjectName("cardFrame")
        g_layout = QVBoxLayout(guideline_card)
        g_layout.setSpacing(10)
        g_layout.setContentsMargins(18, 18, 18, 18)

        g_title = QLabel("Housing Administration Protocol")
        g_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #0f172a;")
        g_layout.addWidget(g_title)

        guidelines = [
            ("1. Intake Verification", "Cross-reference each student card ID with the official university roster before approving."),
            ("2. Gender Block Enforcement", "Male students must be assigned to male blocks; female students to female blocks."),
            ("3. Capacity Limits", "Do not exceed room bed capacity. The system enforces maximum bed limits per room."),
            ("4. Urgent Facility Triage", "Plumbing and electrical reports should be marked 'In Progress' and assigned promptly."),
        ]
        for step, desc in guidelines:
            row = QHBoxLayout()
            s_lbl = QLabel(step)
            s_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #1e293b; min-width: 170px;")
            d_lbl = QLabel(desc)
            d_lbl.setStyleSheet("font-size: 12px; color: #64748b;")
            row.addWidget(s_lbl)
            row.addWidget(d_lbl, 1)
            g_layout.addLayout(row)

        layout.addWidget(guideline_card)
        layout.addStretch(1)

        self.reload()

    def _count(self, table, **filters) -> int:
        q = self.client.table(table).select("id", count="exact")
        for col, val in filters.items():
            q = q.eq(col, val)
        return q.execute().count or 0

    def apply_live_data(self, pending: int, reports: int, requests: int, occupancy: int | None = None):
        self.pending_card.set_value(pending)
        self.reports_card.set_value(reports)
        self.requests_card.set_value(requests)
        if occupancy is not None:
            self.occupancy_card.set_value(occupancy)

    def reload(self):
        pending = self._count("students", status="pending")
        reports = self.client.table("maintenance_reports").select("id", count="exact").neq("status", "resolved").execute().count or 0
        requests = self._count("room_change_requests", status="pending")
        occupancy = sum(room_occupancy(self.client).values())
        self.apply_live_data(pending, reports, requests, occupancy)
