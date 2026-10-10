from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QMessageBox,
)


class StaffAccountsPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Position", "ID"])

        self.email = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.full_name = QLineEdit()
        self.position = QLineEdit()

        form = QFormLayout()
        form.addRow("Email", self.email)
        form.addRow("Password", self.password)
        form.addRow("Full name", self.full_name)
        form.addRow("Position", self.position)

        create = QPushButton("Create staff account")
        create.clicked.connect(self.on_create)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)

        actions = QHBoxLayout()
        actions.addWidget(create)
        actions.addWidget(refresh)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Staff accounts</h2>", textFormat=Qt.TextFormat.RichText))
        layout.addWidget(self.table)
        layout.addLayout(form)
        layout.addLayout(actions)

        self.reload()

    def reload(self):
        try:
            resp = self.client.functions.invoke("admin-users", invoke_options={"body": {"action": "list_staff"}})
            rows = resp or []
        except Exception as exc:  # noqa: BLE001
            rows = []
            QMessageBox.warning(self, "Error", str(exc))
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(r.get("full_name", "")))
            self.table.setItem(i, 1, QTableWidgetItem(r.get("position") or ""))
            self.table.setItem(i, 2, QTableWidgetItem(r.get("id", "")))

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
            self.client.functions.invoke("admin-users", invoke_options={"body": body})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        QMessageBox.information(self, "Created", "Staff account created.")
        self.reload()
