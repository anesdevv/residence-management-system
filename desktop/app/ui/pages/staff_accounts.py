import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QMessageBox,
    QFrame, QSplitter,
)
from ..icons import get_icon, get_pixmap
from ..theme import apply_button_style


class StaffAccountsPage(QWidget):
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
        title_lbl = QLabel("Staff & Administrative Access")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #f8fafc;")
        sub_lbl = QLabel("Manage department officer credentials, assigned positions, and console privileges.")
        sub_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        header_vbox.addWidget(title_lbl)
        header_vbox.addWidget(sub_lbl)
        header_row.addLayout(header_vbox)
        header_row.addStretch(1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setIcon(get_icon("refresh", size=14, color="#cbd5e1"))
        apply_button_style(refresh_btn, "secondary")
        refresh_btn.clicked.connect(self.reload)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        # Splitter Layout (Left: Staff Table, Right: Provision Form Card)
        splitter = QSplitter(Qt.Horizontal)

        table_card = QFrame()
        table_card.setObjectName("cardFrame")
        tc_layout = QVBoxLayout(table_card)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.setSpacing(10)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Staff Member", "Position / Role", "System Account ID"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        tc_layout.addWidget(self.table)

        # Bottom action row for table
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(12, 0, 12, 12)
        btn_row.addStretch(1)
        self.delete_btn = QPushButton("Delete Selected Staff Account")
        self.delete_btn.setFixedHeight(36)
        self.delete_btn.setIcon(get_icon("trash", size=14, color="#ffffff"))
        apply_button_style(self.delete_btn, "danger")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self.on_delete)
        btn_row.addWidget(self.delete_btn)
        tc_layout.addLayout(btn_row)

        splitter.addWidget(table_card)

        # Creation Form Card
        form_card = QFrame()
        form_card.setObjectName("cardFrame")
        form_card.setMinimumWidth(340)
        form_card.setMaximumWidth(460)
        fc_layout = QVBoxLayout(form_card)
        fc_layout.setSpacing(14)
        fc_layout.setContentsMargins(16, 16, 16, 16)

        form_title = QLabel("Provision Staff Account")
        form_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #f8fafc;")
        fc_layout.addWidget(form_title)

        form = QFormLayout()
        form.setSpacing(10)

        self.full_name = QLineEdit()
        self.full_name.setPlaceholderText("e.g. Fatima Zohra")

        self.position = QLineEdit()
        self.position.setPlaceholderText("e.g. Housing Officer, Reception...")

        self.email = QLineEdit()
        self.email.setPlaceholderText("officer@univ-tlemcen.dz")

        self.password = QLineEdit()
        self.password.setPlaceholderText("••••••••")
        self.password.setEchoMode(QLineEdit.Password)

        form.addRow("Full Name:", self.full_name)
        form.addRow("Position:", self.position)
        form.addRow("Email:", self.email)
        form.addRow("Password:", self.password)

        fc_layout.addLayout(form)

        create_btn = QPushButton("Create Staff Account")
        create_btn.setFixedHeight(40)
        create_btn.setIcon(get_icon("plus", size=14, color="#ffffff"))
        apply_button_style(create_btn, "primary")
        create_btn.clicked.connect(self.on_create)
        fc_layout.addWidget(create_btn)

        fc_layout.addStretch(1)
        splitter.addWidget(form_card)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.reload()

    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def on_selection_changed(self):
        staff = self.selected()
        if not staff:
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip("")
            return

        current_uid = None
        user_resp = getattr(self.client.auth, "get_user", lambda: None)()
        if user_resp and hasattr(user_resp, "user") and user_resp.user:
            current_uid = user_resp.user.id

        if staff.get("id") == current_uid:
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip("You cannot delete your own staff account.")
        else:
            self.delete_btn.setEnabled(True)
            self.delete_btn.setToolTip("")

    def reload(self):
        rows = []
        try:
            resp = self.client.functions.invoke(
                "admin-users",
                invoke_options={"body": {"action": "list_staff"}, "responseType": "json"},
            )
            if isinstance(resp, (bytes, bytearray)):
                try:
                    resp = json.loads(resp.decode("utf-8"))
                except Exception:
                    pass
            elif isinstance(resp, str):
                try:
                    resp = json.loads(resp)
                except Exception:
                    pass

            if isinstance(resp, list):
                rows = [r for r in resp if isinstance(r, dict)]
            elif isinstance(resp, dict):
                if "error" in resp:
                    QMessageBox.warning(self, "Error", str(resp["error"]))
                elif isinstance(resp.get("data"), list):
                    rows = [r for r in resp["data"] if isinstance(r, dict)]
            elif hasattr(resp, "data"):
                data = resp.data
                if isinstance(data, list):
                    rows = [r for r in data if isinstance(r, dict)]
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Error", str(exc))

        self.rows = rows
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            name_item = QTableWidgetItem(str(r.get("full_name", "")))
            name_item.setIcon(get_icon("staff_accounts", size=14, color="#818cf8"))
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, QTableWidgetItem(str(r.get("position") or "Officer")))
            self.table.setItem(i, 2, QTableWidgetItem(str(r.get("id", ""))))

        self.on_selection_changed()

    def on_delete(self):
        staff = self.selected()
        if not staff:
            return

        current_uid = None
        user_resp = getattr(self.client.auth, "get_user", lambda: None)()
        if user_resp and hasattr(user_resp, "user") and user_resp.user:
            current_uid = user_resp.user.id

        if staff.get("id") == current_uid:
            QMessageBox.warning(self, "Cannot Delete", "You cannot delete your own staff account.")
            return

        name = staff.get("full_name") or "this staff member"
        ans = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete staff account '{name}'?\n\nThis will permanently revoke their access.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ans != QMessageBox.Yes:
            return

        deleted = False
        last_error = None
        # Try calling admin-users function first
        try:
            resp = self.client.functions.invoke(
                "admin-users",
                invoke_options={"body": {"action": "delete_staff", "id": staff["id"]}, "responseType": "json"},
            )
            if isinstance(resp, (bytes, bytearray)):
                try:
                    resp = json.loads(resp.decode("utf-8"))
                except Exception:
                    pass
            elif isinstance(resp, str):
                try:
                    resp = json.loads(resp)
                except Exception:
                    pass
            if isinstance(resp, dict) and "error" in resp:
                last_error = resp["error"]
            else:
                deleted = True
        except Exception as exc:
            last_error = exc

        # If edge function failed or had error, try rpc fallback
        if not deleted:
            try:
                self.client.rpc("delete_staff", {"p_staff": staff["id"]}).execute()
                deleted = True
            except Exception as rpc_exc:
                last_error = rpc_exc

        if not deleted:
            QMessageBox.critical(self, "Error Deleting Staff", f"Failed to delete staff account: {last_error}")
            return

        QMessageBox.information(self, "Staff Account Deleted", "Staff account deleted successfully.")
        self.reload()

    def on_create(self):
        body = {
            "action": "create_staff",
            "email": self.email.text().strip(),
            "password": self.password.text(),
            "full_name": self.full_name.text().strip(),
            "position": self.position.text().strip(),
        }
        if not (body["email"] and body["password"] and body["full_name"]):
            QMessageBox.warning(self, "Missing data", "Email, password and full name are required.")
            return
        try:
            resp = self.client.functions.invoke(
                "admin-users",
                invoke_options={"body": body, "responseType": "json"},
            )
            if isinstance(resp, (bytes, bytearray)):
                try:
                    resp = json.loads(resp.decode("utf-8"))
                except Exception:
                    pass
            elif isinstance(resp, str):
                try:
                    resp = json.loads(resp)
                except Exception:
                    pass
            if isinstance(resp, dict) and "error" in resp:
                QMessageBox.critical(self, "Error", str(resp["error"]))
                return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        QMessageBox.information(self, "Staff Account Created", f"Account for {body['full_name']} created successfully.")
        self.email.clear()
        self.password.clear()
        self.full_name.clear()
        self.position.clear()
        self.reload()
