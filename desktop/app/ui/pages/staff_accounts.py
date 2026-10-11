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

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Staff Member", "Position / Role", "System Account ID"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        tc_layout.addWidget(self.table)
        splitter.addWidget(table_card)

        # Creation Form Card
        form_card = QFrame()
        form_card.setObjectName("cardFrame")
        form_card.setFixedWidth(380)
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

        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            name_item = QTableWidgetItem(str(r.get("full_name", "")))
            name_item.setIcon(get_icon("staff_accounts", size=14, color="#818cf8"))
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, QTableWidgetItem(str(r.get("position") or "Officer")))
            self.table.setItem(i, 2, QTableWidgetItem(str(r.get("id", ""))))

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
