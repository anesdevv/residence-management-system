from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QFrame, QComboBox,
)
from ..icons import get_icon, get_pixmap
from ..theme import apply_button_style


class ResidentsPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Row
        header_row = QHBoxLayout()
        header_vbox = QVBoxLayout()
        title_lbl = QLabel("Resident Students Directory")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #0f172a;")
        sub_lbl = QLabel("Official record of all active students currently accommodated in Residence Tlemcen.")
        sub_lbl.setStyleSheet("font-size: 12px; color: #64748b;")
        header_vbox.addWidget(title_lbl)
        header_vbox.addWidget(sub_lbl)
        header_row.addLayout(header_vbox)
        header_row.addStretch(1)

        self.count_badge = QLabel("0 Residents")
        self.count_badge.setStyleSheet("""
            background-color: #d1fae5;
            color: #065f46;
            border: 1px solid #a7f3d0;
            border-radius: 12px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 700;
        """)
        header_row.addWidget(self.count_badge)

        refresh = QPushButton("Refresh")
        refresh.setIcon(get_icon("refresh", size=14, color="#334155"))
        apply_button_style(refresh, "secondary")
        refresh.clicked.connect(self.reload)
        header_row.addWidget(refresh)
        layout.addLayout(header_row)

        # Search & Filter Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search residents by card ID, name, assigned room, or university...")
        self.search.textChanged.connect(self.render)
        toolbar.addWidget(self.search, 1)

        self.gender_filter = QComboBox()
        self.gender_filter.addItems(["All Genders", "Male Residents", "Female Residents"])
        self.gender_filter.currentIndexChanged.connect(self.render)
        toolbar.addWidget(self.gender_filter)

        layout.addLayout(toolbar)

        # Table Container
        table_card = QFrame()
        table_card.setObjectName("cardFrame")
        tc_layout = QVBoxLayout(table_card)
        tc_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Student Card ID", "Full Name", "Gender", "Assigned Room", "Faculty / University", "Status"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        tc_layout.addWidget(self.table)
        layout.addWidget(table_card, 1)

        self.reload()

    def reload(self):
        resp = self.client.table("students") \
            .select("card_id, first_name, last_name, gender, status, university, faculty, rooms(block, number, floor)") \
            .eq("status", "active").order("last_name").execute()
        self.rows = resp.data or []
        self.count_badge.setText(f"{len(self.rows)} Active Residents")
        self.render()

    def render(self):
        needle = self.search.text().lower().strip()
        gender_sel = self.gender_filter.currentText()
        gender_target = "male" if gender_sel == "Male Residents" else "female" if gender_sel == "Female Residents" else None

        filtered = []
        for r in self.rows:
            room = r.get("rooms") or {}
            if isinstance(room, list) and room:
                room = room[0]
            elif not isinstance(room, dict):
                room = {}

            haystack = f"{r.get('first_name', '')} {r.get('last_name', '')} {r.get('card_id', '')} {room.get('block', '')} {room.get('number', '')} {r.get('university', '')} {r.get('faculty', '')}".lower()
            matches_text = needle in haystack
            matches_gender = gender_target is None or str(r.get("gender", "")).lower() == gender_target
            if matches_text and matches_gender:
                filtered.append((r, room))

        self.table.setRowCount(len(filtered))
        for i, (r, room) in enumerate(filtered):
            card_item = QTableWidgetItem(str(r.get("card_id", "")))
            card_item.setIcon(get_icon("user", size=14, color="#64748b"))
            name_item = QTableWidgetItem(f"{r.get('first_name', '')} {r.get('last_name', '')}")
            gender_item = QTableWidgetItem(str(r.get("gender", "")).capitalize())

            room_str = f"Block {room.get('block','—')} — Room {room.get('number','—')}"
            room_item = QTableWidgetItem(room_str)
            room_item.setIcon(get_icon("building", size=14, color="#2563eb"))

            univ_str = f"{r.get('faculty', '') or '—'}"
            univ_item = QTableWidgetItem(univ_str)

            status_item = QTableWidgetItem("Active Resident")
            status_item.setForeground(Qt.darkGreen)

            self.table.setItem(i, 0, card_item)
            self.table.setItem(i, 1, name_item)
            self.table.setItem(i, 2, gender_item)
            self.table.setItem(i, 3, room_item)
            self.table.setItem(i, 4, univ_item)
            self.table.setItem(i, 5, status_item)
