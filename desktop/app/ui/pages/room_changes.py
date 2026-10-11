from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox, QTextEdit, QFrame,
    QSplitter, QLineEdit,
)
from ...client import room_occupancy
from ..icons import get_icon, get_pixmap
from ..theme import apply_button_style


class RoomChangesPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Bar
        header_row = QHBoxLayout()
        header_vbox = QVBoxLayout()
        title_lbl = QLabel("Room Transfer Applications")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #0f172a;")
        sub_lbl = QLabel("Review resident room change justifications and reallocate rooms based on block availability.")
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

        # Search / Filter
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter transfer requests by student name or reason...")
        self.search_input.textChanged.connect(self.filter_table)
        layout.addWidget(self.search_input)

        # Splitter Layout
        splitter = QSplitter(Qt.Horizontal)

        table_card = QFrame()
        table_card.setObjectName("cardFrame")
        tc_layout = QVBoxLayout(table_card)
        tc_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Resident", "Status", "Reason Excerpt", "Date"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.table.horizontalHeader().setStretchLastSection(True)
        tc_layout.addWidget(self.table)
        splitter.addWidget(table_card)

        # Inspector Card
        detail_card = QFrame()
        detail_card.setObjectName("cardFrame")
        detail_card.setFixedWidth(400)
        dc_layout = QVBoxLayout(detail_card)
        dc_layout.setSpacing(12)
        dc_layout.setContentsMargins(16, 16, 16, 16)

        detail_title = QLabel("Transfer Request Inspector")
        detail_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0f172a;")
        dc_layout.addWidget(detail_title)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText("Select a transfer request to inspect...")
        dc_layout.addWidget(self.detail_text, 1)

        self.approve_btn = QPushButton("Approve Transfer & Reassign")
        self.approve_btn.setFixedHeight(40)
        self.approve_btn.setIcon(get_icon("check", size=16, color="#ffffff"))
        apply_button_style(self.approve_btn, "success")
        self.approve_btn.clicked.connect(self.on_approve)

        self.reject_btn = QPushButton("Reject Transfer Request")
        self.reject_btn.setFixedHeight(40)
        self.reject_btn.setIcon(get_icon("cross", size=16, color="#ffffff"))
        apply_button_style(self.reject_btn, "danger")
        self.reject_btn.clicked.connect(self.on_reject)

        dc_layout.addWidget(self.approve_btn)
        dc_layout.addWidget(self.reject_btn)

        splitter.addWidget(detail_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.reload()

    def filter_table(self):
        needle = self.search_input.text().lower().strip()
        for r in range(self.table.rowCount()):
            row_data = self.rows[r] if r < len(self.rows) else {}
            st = row_data.get("students") or {}
            name = f"{st.get('first_name', '')} {st.get('last_name', '')}".lower()
            reason = str(row_data.get("reason", "")).lower()
            self.table.setRowHidden(r, needle not in f"{name} {reason}")

    def apply_live_data(self, rows: list[dict]):
        old_keys = [(r.get("id"), r.get("status")) for r in self.rows]
        new_keys = [(r.get("id"), r.get("status")) for r in rows]
        if old_keys == new_keys and len(rows) == len(self.rows):
            return

        selected_id = self.selected().get("id") if self.selected() else None
        self.rows = rows
        self.table.setRowCount(len(self.rows))
        restore_row = -1

        for i, r in enumerate(self.rows):
            if r.get("id") == selected_id:
                restore_row = i
            st = r.get("students") or {}
            status = r.get("status", "pending")
            status_text = "Pending" if status == "pending" else "Approved" if status == "approved" else "Rejected"

            name_item = QTableWidgetItem(f"{st.get('first_name', '')} {st.get('last_name', '')}")
            status_item = QTableWidgetItem(status_text)
            reason_item = QTableWidgetItem(str(r.get("reason", ""))[:45] + "...")
            date_item = QTableWidgetItem(str(r.get("created_at", ""))[:10])

            if status == "approved":
                status_item.setForeground(Qt.darkGreen)
            elif status == "rejected":
                status_item.setForeground(Qt.darkRed)
            else:
                status_item.setForeground(Qt.darkYellow)

            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, status_item)
            self.table.setItem(i, 2, reason_item)
            self.table.setItem(i, 3, date_item)

        if restore_row >= 0:
            self.table.setCurrentRow(restore_row)
        else:
            self.detail_text.clear()

        self.filter_table()

    def reload(self):
        resp = self.client.table("room_change_requests") \
            .select("*, students(first_name, last_name, gender, card_id)") \
            .eq("status", "pending").order("created_at", desc=True).execute()
        self.apply_live_data(resp.data or [])

    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def show_detail(self):
        r = self.selected()
        if not r:
            self.detail_text.clear()
            return
        st = r.get("students") or {}
        pref_id = r.get("preferred_room_id")
        pref_info = "No specific room requested"
        if pref_id:
            try:
                room_data = self.client.table("rooms").select("block, number, floor").eq("id", pref_id).single().execute().data
                if room_data:
                    pref_info = f"Block {room_data['block']} — Room {room_data['number']} (Floor {room_data['floor']})"
            except Exception:
                pref_info = f"Room ID: {pref_id}"

        self.detail_text.setPlainText(
            f"RESIDENT: {st.get('first_name', '')} {st.get('last_name', '')}\n"
            f"Card ID: {st.get('card_id', '—')} | Gender: {st.get('gender', '—')}\n"
            f"Preferred Room: {pref_info}\n\n"
            f"----------------------------------------\n"
            f"STATED REASON FOR TRANSFER:\n{r.get('reason', '')}\n\n"
            f"Decision Note: {r.get('decision_note') or 'None'}"
        )

    def on_approve(self):
        r = self.selected()
        if not r:
            QMessageBox.information(self, "Select request", "Please select a transfer request from the table first.")
            return
        gender = (r.get("students") or {}).get("gender", "male")
        rooms = self.client.table("rooms").select("id, block, number, floor, capacity, gender") \
            .eq("gender", gender).order("block").order("number").execute().data or []
        occ = room_occupancy(self.client)
        options = []
        for room in rooms:
            free = room["capacity"] - occ.get(room["id"], 0)
            if free > 0:
                options.append(f"Block {room['block']} — Room {room['number']} ({free}/{room['capacity']} free) | id={room['id']}")
            else:
                options.append(f"Block {room['block']} — Room {room['number']} (FULL) [LOCKED] | id={room['id']}")
        if not options:
            QMessageBox.warning(self, "No rooms", "No rooms configured for this gender.")
            return
        choice, ok = QInputDialog.getItem(self, "Allocate New Room", "Select target room for transfer:", options, 0, False)
        if not ok:
            return
        if "[LOCKED]" in choice:
            QMessageBox.warning(self, "Room Full", "This room is at capacity. Please select an available room.")
            return
        room_id = choice.split("id=")[1].strip()
        try:
            self.client.rpc("approve_room_change", {"p_request": r["id"], "p_room": room_id}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        QMessageBox.information(self, "Approved", "Room transfer request approved and student reassigned.")
        self.reload()

    def on_reject(self):
        r = self.selected()
        if not r:
            QMessageBox.information(self, "Select request", "Please select a transfer request from the table first.")
            return
        reason, ok = QInputDialog.getMultiLineText(self, "Reject Transfer", "Reason for refusal:")
        if not ok or not reason.strip():
            return
        try:
            self.client.rpc("reject_room_change", {"p_request": r["id"], "p_reason": reason.strip()}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        QMessageBox.information(self, "Rejected", "Room transfer request rejected.")
        self.reload()
