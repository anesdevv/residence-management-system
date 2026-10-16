from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox, QTextEdit, QLineEdit,
    QFrame, QSplitter,
)
from ...client import room_occupancy, official_lookup
from ..icons import get_icon, get_pixmap
from ..theme import apply_button_style
from ..infocard import StudentInfoCardDialog


class PendingPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.all_rows: list[dict] = []
        self.rows: list[dict] = []
        self.official = {}
        self.filter_mode = "pending"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Bar
        header_row = QHBoxLayout()
        header_vbox = QVBoxLayout()
        title_lbl = QLabel("Student Applications & Housing")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #f8fafc;")
        sub_lbl = QLabel("Verify student enrollment against official roster, review applications, and allocate rooms.")
        sub_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        header_vbox.addWidget(title_lbl)
        header_vbox.addWidget(sub_lbl)
        header_row.addLayout(header_vbox)
        header_row.addStretch(1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(get_icon("refresh", size=14, color="#cbd5e1"))
        apply_button_style(self.refresh_btn, "secondary")
        self.refresh_btn.clicked.connect(self.reload)
        header_row.addWidget(self.refresh_btn)
        layout.addLayout(header_row)

        # Filter Toolbar & Search Bar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.btn_pending = QPushButton("Pending Applications")
        self.btn_approved = QPushButton("Approved Residents")
        self.btn_rejected = QPushButton("Rejected Applications")
        self.btn_all = QPushButton("All Applications")

        for b in (self.btn_pending, self.btn_approved, self.btn_rejected, self.btn_all):
            b.setCheckable(True)
            apply_button_style(b, "filter")
            toolbar.addWidget(b)

        self.btn_pending.setChecked(True)
        self.btn_pending.clicked.connect(lambda: self.set_filter("pending"))
        self.btn_approved.clicked.connect(lambda: self.set_filter("approved"))
        self.btn_rejected.clicked.connect(lambda: self.set_filter("rejected"))
        self.btn_all.clicked.connect(lambda: self.set_filter("all"))

        toolbar.addSpacing(12)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter students by name, card ID, or university...")
        self.search_input.textChanged.connect(self.apply_filter)
        toolbar.addWidget(self.search_input, 1)

        layout.addLayout(toolbar)

        # Main Splitter (Table on Left, Inspector on Right)
        splitter = QSplitter(Qt.Horizontal)

        # Left Container: Table
        table_container = QFrame()
        table_container.setObjectName("cardFrame")
        tc_layout = QVBoxLayout(table_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Card ID", "Student Name", "Gender", "Status", "Roster Match", "Submitted"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        self.table.horizontalHeader().setStretchLastSection(True)
        tc_layout.addWidget(self.table)

        splitter.addWidget(table_container)

        # Right Container: Inspector & Actions
        detail_container = QFrame()
        detail_container.setObjectName("cardFrame")
        detail_container.setMinimumWidth(340)
        detail_container.setMaximumWidth(460)
        dc_layout = QVBoxLayout(detail_container)
        dc_layout.setSpacing(12)
        dc_layout.setContentsMargins(16, 16, 16, 16)

        inspector_title = QLabel("Application Inspector")
        inspector_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #f8fafc;")
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

        self.delete_btn = QPushButton("Delete Student Record")
        self.delete_btn.setFixedHeight(40)
        self.delete_btn.setIcon(get_icon("trash", size=16, color="#ffffff"))
        apply_button_style(self.delete_btn, "danger")
        self.delete_btn.clicked.connect(self.on_delete)

        dc_layout.addWidget(self.approve_btn)
        dc_layout.addWidget(self.reject_btn)
        dc_layout.addWidget(self.delete_btn)

        splitter.addWidget(detail_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.reload()

    def set_filter(self, mode: str):
        self.filter_mode = mode
        self.btn_pending.setChecked(mode == "pending")
        self.btn_approved.setChecked(mode == "approved")
        self.btn_rejected.setChecked(mode == "rejected")
        self.btn_all.setChecked(mode == "all")
        self.apply_filter()

    def apply_filter(self):
        needle = self.search_input.text().lower().strip()
        filtered = []
        for r in getattr(self, "all_rows", []):
            status = r.get("status", "")
            if self.filter_mode == "pending" and status != "pending":
                continue
            elif self.filter_mode == "approved" and status != "active":
                continue
            elif self.filter_mode == "rejected" and status != "rejected":
                continue

            text = f"{r.get('card_id', '')} {r.get('first_name', '')} {r.get('last_name', '')} {r.get('university', '')}".lower()
            if needle and needle not in text:
                continue
            filtered.append(r)
        self._render_table(filtered)

    def apply_live_data(self, pending_students: list[dict]):
        # Compare pending keys to avoid unnecessary re-renders
        cur_pending = [r for r in getattr(self, "all_rows", []) if r.get("status") == "pending"]
        old_keys = [(r.get("id"), r.get("status")) for r in cur_pending]
        new_keys = [(r.get("id"), r.get("status")) for r in pending_students]
        if old_keys == new_keys and len(cur_pending) == len(pending_students):
            return

        # Preserve active and rejected rows while refreshing pending applications from live tick
        non_pending = [r for r in getattr(self, "all_rows", []) if r.get("status") != "pending"]
        self.all_rows = pending_students + non_pending
        self.apply_filter()

    def _render_table(self, rows: list[dict]):
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

            raw_status = s.get("status", "pending")
            if raw_status == "active":
                status_text = "✓ Approved"
                status_color = "#34d399"
            elif raw_status == "rejected":
                status_text = "✕ Rejected"
                status_color = "#f87171"
            else:
                status_text = "⏳ Pending"
                status_color = "#fbbf24"

            card_item = QTableWidgetItem(str(s.get("card_id", "")))
            name_item = QTableWidgetItem(f"{s.get('first_name', '')} {s.get('last_name', '')}")
            gender_item = QTableWidgetItem(str(s.get("gender", "")).capitalize())
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(status_color))
            match_item = QTableWidgetItem(match_text)
            match_item.setForeground(QColor("#34d399" if is_match else "#f87171"))
            date_item = QTableWidgetItem(str(s.get("created_at", ""))[:10])

            self.table.setItem(i, 0, card_item)
            self.table.setItem(i, 1, name_item)
            self.table.setItem(i, 2, gender_item)
            self.table.setItem(i, 3, status_item)
            self.table.setItem(i, 4, match_item)
            self.table.setItem(i, 5, date_item)

        if restore_row >= 0:
            self.table.selectRow(restore_row)
        else:
            self.show_detail()

    def reload(self):
        try:
            resp = self.client.table("students").select("*").order("created_at", desc=True).execute()
            self.official = official_lookup(self.client)
            self.all_rows = resp.data or []
            self.apply_filter()
        except Exception:
            pass

    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def show_detail(self):
        s = self.selected()
        if not s:
            self.detail_text.clear()
            self.approve_btn.setEnabled(False)
            self.approve_btn.setToolTip("")
            self.reject_btn.setEnabled(False)
            self.reject_btn.setText("Reject Application")
            self.reject_btn.setToolTip("")
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip("")
            return

        status = s.get("status", "pending")

        # Action Buttons configuration
        if status == "active":
            self.approve_btn.setEnabled(False)
            self.approve_btn.setToolTip("Student already approved.")
        else:
            self.approve_btn.setEnabled(True)
            self.approve_btn.setToolTip("")

        self.reject_btn.setEnabled(True)
        if status == "rejected":
            self.reject_btn.setText("Edit Rejection Reason")
        else:
            self.reject_btn.setText("Reject Application")

        if status == "pending":
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip("Pending applications cannot be deleted. Please approve or reject first.")
        else:
            self.delete_btn.setEnabled(True)
            self.delete_btn.setToolTip("")

        o = self.official.get(s.get("card_id"))
        official_str = (
            f"✅ OFFICIAL ROSTER MATCH:\n"
            f"  Name: {o.get('first_name')} {o.get('last_name')}\n"
            f"  Birth Date: {o.get('birth_date') or '—'}\n"
            f"  Gender: {o.get('gender') or '—'}\n"
            f"  Faculty: {o.get('faculty') or '—'}"
            if o else "⚠️ NO MATCH IN OFFICIAL UNIVERSITY ROSTER\nPlease verify physical enrollment certificate before approval."
        )

        if status == "rejected":
            status_section = (
                f"⚠️ REJECTION REASON (Desk Inquiry Reference):\n"
                f"\"{s.get('rejection_reason') or 'No reason recorded'}\"\n"
                f"Reviewed: {s.get('reviewed_at') or '—'}"
            )
        elif status == "active":
            status_section = (
                f"✅ HOUSING STATUS:\n"
                f"Student is Approved & Assigned to Room.\n"
                f"Reviewed: {s.get('reviewed_at') or '—'}"
            )
        else:
            status_section = (
                f"⏳ APPLICATION STATUS:\n"
                f"Awaiting Administrative Review & Room Allocation."
            )

        self.detail_text.setPlainText(
            f"STUDENT CARD ID: {s.get('card_id', '—')}\n"
            f"Name: {s.get('first_name', '')} {s.get('last_name', '')}\n"
            f"Gender: {s.get('gender', '—')} | Birth: {s.get('birth_date', '—')}\n"
            f"Phone: {s.get('phone', '—')}\n"
            f"Email: {s.get('email') or '—'}\n"
            f"University: {s.get('university', '—')}\n"
            f"Faculty: {s.get('faculty', '—')}\n"
            f"Study Level: {s.get('study_level', '—')} | Wilaya: {s.get('wilaya', '—')}\n\n"
            f"----------------------------------------\n"
            f"{official_str}\n\n"
            f"----------------------------------------\n"
            f"{status_section}"
        )

    def on_row_double_clicked(self, row: int, col: int):
        s = self.selected()
        if s:
            o = self.official.get(s.get("card_id"))
            dlg = StudentInfoCardDialog(self, s, o)
            dlg.exec()

    def on_approve(self):
        s = self.selected()
        if not s:
            QMessageBox.information(self, "Select applicant", "Please select a student applicant from the table first.")
            return

        try:
            rooms = self.client.table("rooms").select("id, block, number, floor, capacity, gender") \
                .eq("gender", s["gender"]).order("block").order("number").execute().data or []
            occ = room_occupancy(self.client)
        except Exception as exc:
            QMessageBox.critical(self, "Network Error", f"Failed to fetch room vacancy data: {exc}")
            return

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
        try:
            self.reload()
        except Exception:
            pass

    def on_reject(self):
        s = self.selected()
        if not s:
            QMessageBox.information(self, "Select applicant", "Please select a student applicant from the table first.")
            return
        default_reason = s.get("rejection_reason") or ""
        reason, ok = QInputDialog.getMultiLineText(
            self,
            "Reject Application",
            f"Enter official rejection reason for {s.get('first_name', '')} {s.get('last_name', '')}:",
            text=default_reason,
        )
        if not ok:
            return
        if not reason.strip():
            QMessageBox.warning(
                self,
                "Reason Required",
                "Rejection reason is required so administrative desk staff can answer student inquiries.",
            )
            return
        try:
            self.client.rpc("reject_student", {"p_student": s["id"], "p_reason": reason.strip()}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Rejection Error", str(exc))
            return
        QMessageBox.information(
            self,
            "Application Decision Saved",
            f"Official decision for {s.get('first_name', '')} {s.get('last_name', '')} has been recorded.",
        )
        try:
            self.reload()
        except Exception:
            pass

    def on_delete(self):
        s = self.selected()
        if not s:
            QMessageBox.information(self, "Select Student", "Please select a student from the table first.")
            return
        if s.get("status") == "pending":
            QMessageBox.warning(self, "Cannot Delete", "Pending applications cannot be deleted. Please approve or reject first.")
            return

        name = f"{s.get('first_name', '')} {s.get('last_name', '')}".strip()
        card_id = s.get("card_id", "—")
        status = s.get("status", "—")

        ans = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to permanently delete resident {name} ({card_id})?\n\nStatus: {status}\nThis will remove the student record and unassign any room.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ans != QMessageBox.Yes:
            return

        try:
            try:
                self.client.rpc("delete_student", {"p_student": s["id"]}).execute()
            except Exception:
                self.client.table("students").delete().eq("id", s["id"]).execute()
            QMessageBox.information(self, "Deleted", f"Resident record {name} deleted successfully.")
            self.reload()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Deletion Error", f"Failed to delete resident record: {exc}")