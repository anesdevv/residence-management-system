from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox, QTextEdit, QLineEdit,
    QFrame, QSplitter,
)
from ...client import room_occupancy, official_lookup
from ..icons import get_icon, get_pixmap
from ..theme import apply_button_style


class PendingPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []
        self.official = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Bar
        header_row = QHBoxLayout()
        header_vbox = QVBoxLayout()
        title_lbl = QLabel("Pending Student Applications")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #0f172a;")
        sub_lbl = QLabel("Verify student enrollment against official roster, approve and allocate rooms, or reject with reason.")
        sub_lbl.setStyleSheet("font-size: 12px; color: #64748b;")
        header_vbox.addWidget(title_lbl)
        header_vbox.addWidget(sub_lbl)
        header_row.addLayout(header_vbox)
        header_row.addStretch(1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(get_icon("refresh", size=14, color="#334155"))
        apply_button_style(self.refresh_btn, "secondary")
        self.refresh_btn.clicked.connect(self.reload)
        header_row.addWidget(self.refresh_btn)
        layout.addLayout(header_row)

        # Search Bar
        search_box = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter pending students by name, card ID, or university...")
        self.search_input.textChanged.connect(self.filter_table)
        search_box.addWidget(self.search_input)
        layout.addLayout(search_box)

        # Main Splitter (Table on Left, Inspector on Right)
        splitter = QSplitter(Qt.Horizontal)

        # Left Container: Table
        table_container = QFrame()
        table_container.setObjectName("cardFrame")
        tc_layout = QVBoxLayout(table_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Card ID", "Student Name", "Gender", "Roster Status", "Submitted"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.table.horizontalHeader().setStretchLastSection(True)
        tc_layout.addWidget(self.table)

        splitter.addWidget(table_container)

        # Right Container: Inspector & Actions
        detail_container = QFrame()
        detail_container.setObjectName("cardFrame")
        detail_container.setFixedWidth(380)
        dc_layout = QVBoxLayout(detail_container)
        dc_layout.setSpacing(12)
        dc_layout.setContentsMargins(16, 16, 16, 16)

        inspector_title = QLabel("Application Inspector")
        inspector_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0f172a;")
        dc_layout.addWidget(inspector_title)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText("Select an applicant from the table to inspect details...")
        dc_layout.addWidget(self.detail_text, 1)

        # Action Buttons
        self.approve_btn = QPushButton("Approve & Assign Room")
        self.approve_btn.setFixedHeight(40)
        self.approve_btn.setIcon(get_icon("check", size=16, color="#ffffff"))
        apply_button_style(self.approve_btn, "success")
        self.approve_btn.clicked.connect(self.on_approve)

        self.reject_btn = QPushButton("Reject Application")
        self.reject_btn.setFixedHeight(40)
        self.reject_btn.setIcon(get_icon("cross", size=16, color="#ffffff"))
        apply_button_style(self.reject_btn, "danger")
        self.reject_btn.clicked.connect(self.on_reject)

        dc_layout.addWidget(self.approve_btn)
        dc_layout.addWidget(self.reject_btn)

        splitter.addWidget(detail_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.reload()

    def filter_table(self):
        needle = self.search_input.text().lower().strip()
        for r in range(self.table.rowCount()):
            row_data = self.rows[r] if r < len(self.rows) else {}
            text = f"{row_data.get('card_id', '')} {row_data.get('first_name', '')} {row_data.get('last_name', '')} {row_data.get('university', '')}".lower()
            self.table.setRowHidden(r, needle not in text)

    def apply_live_data(self, rows: list[dict]):
        old_ids = [r.get("id") for r in self.rows]
        new_ids = [r.get("id") for r in rows]
        if old_ids == new_ids and len(rows) == len(self.rows):
            return

        selected_id = self.selected().get("id") if self.selected() else None
        self.rows = rows
        if not hasattr(self, "official") or not self.official:
            self.official = official_lookup(self.client)

        self.table.setRowCount(len(self.rows))
        restore_row = -1
        for i, s in enumerate(self.rows):
            if s.get("id") == selected_id:
                restore_row = i
            is_match = s.get("card_id") in self.official
            match_text = "✓ Matched" if is_match else "⚠ Not in Roster"

            card_item = QTableWidgetItem(str(s.get("card_id", "")))
            name_item = QTableWidgetItem(f"{s.get('first_name', '')} {s.get('last_name', '')}")
            gender_item = QTableWidgetItem(str(s.get("gender", "")).capitalize())
            match_item = QTableWidgetItem(match_text)
            date_item = QTableWidgetItem(str(s.get("created_at", ""))[:10])

            if is_match:
                match_item.setForeground(Qt.darkGreen)
            else:
                match_item.setForeground(Qt.darkRed)

            self.table.setItem(i, 0, card_item)
            self.table.setItem(i, 1, name_item)
            self.table.setItem(i, 2, gender_item)
            self.table.setItem(i, 3, match_item)
            self.table.setItem(i, 4, date_item)

        if restore_row >= 0:
            self.table.setCurrentRow(restore_row)
        else:
            self.detail_text.clear()

        self.filter_table()

    def reload(self):
        resp = self.client.table("students").select("*").eq("status", "pending").order("created_at", desc=True).execute()
        self.official = official_lookup(self.client)
        self.apply_live_data(resp.data or [])

    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def show_detail(self):
        s = self.selected()
        if not s:
            return
        o = self.official.get(s["card_id"])
        official_str = (
            f"✅ OFFICIAL ROSTER MATCH:\n"
            f"  Name: {o.get('first_name')} {o.get('last_name')}\n"
            f"  Birth Date: {o.get('birth_date') or '—'}\n"
            f"  Gender: {o.get('gender') or '—'}\n"
            f"  Faculty: {o.get('faculty') or '—'}"
            if o else "⚠️ NO MATCH IN OFFICIAL UNIVERSITY ROSTER\nPlease verify physical enrollment certificate before approval."
        )
        self.detail_text.setPlainText(
            f"STUDENT CARD ID: {s['card_id']}\n"
            f"Name: {s['first_name']} {s['last_name']}\n"
            f"Gender: {s['gender']} | Birth: {s['birth_date']}\n"
            f"Phone: {s['phone']}\n"
            f"Email: {s['email'] or '—'}\n"
            f"University: {s['university']}\n"
            f"Faculty: {s['faculty']}\n"
            f"Study Level: {s['study_level']} | Wilaya: {s['wilaya']}\n\n"
            f"----------------------------------------\n"
            f"{official_str}"
        )

    def on_approve(self):
        s = self.selected()
        if not s:
            QMessageBox.information(self, "Select applicant", "Please select a student applicant from the table first.")
            return
        rooms = self.client.table("rooms").select("id, block, number, floor, capacity, gender") \
            .eq("gender", s["gender"]).order("block").order("number").execute().data or []
        occ = room_occupancy(self.client)
        options = []
        for r in rooms:
            occupied = occ.get(r["id"], 0)
            free = r["capacity"] - occupied
            if free > 0:
                options.append(f"Block {r['block']} — Room {r['number']} (Floor {r['floor']}, {free}/{r['capacity']} beds free) | id={r['id']}")
            else:
                options.append(f"Block {r['block']} — Room {r['number']} (FULL: {occupied}/{r['capacity']}) [LOCKED] | id={r['id']}")
        if not options:
            QMessageBox.warning(self, "No rooms", f"No rooms configured for {s['gender']} residential blocks.")
            return
        choice, ok = QInputDialog.getItem(self, "Assign Room", f"Allocate room for {s['first_name']} {s['last_name']} ({s['gender']}):", options, 0, False)
        if not ok:
            return
        if "[LOCKED]" in choice:
            QMessageBox.warning(self, "Room Full", "This room is at maximum bed capacity. Please select an available room.")
            return
        room_id = choice.split("id=")[1].strip()
        try:
            self.client.rpc("approve_student", {"p_student": s["id"], "p_room": room_id}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Approval Error", str(exc))
            return
        QMessageBox.information(self, "Approved & Housed", f"Student {s['first_name']} {s['last_name']} has been approved and allocated to the room.")
        self.reload()

    def on_reject(self):
        s = self.selected()
        if not s:
            QMessageBox.information(self, "Select applicant", "Please select a student applicant from the table first.")
            return
        reason, ok = QInputDialog.getMultiLineText(self, "Reject Application", f"Enter official rejection reason for {s['first_name']} {s['last_name']}:")
        if not ok or not reason.strip():
            return
        try:
            self.client.rpc("reject_student", {"p_student": s["id"], "p_reason": reason.strip()}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Rejection Error", str(exc))
            return
        QMessageBox.information(self, "Application Rejected", f"Application for {s['first_name']} {s['last_name']} has been rejected.")
        self.reload()