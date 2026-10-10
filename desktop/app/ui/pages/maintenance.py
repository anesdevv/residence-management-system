from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QTextEdit, QInputDialog, QMessageBox,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt


class MaintenancePage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Category", "Student", "Status", "Created"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self.show_detail)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.photo = QLabel()
        self.photo.setAlignment(Qt.AlignCenter)
        self.photo.setMinimumHeight(200)

        in_progress = QPushButton("Mark in progress")
        in_progress.clicked.connect(lambda: self.set_status("in_progress"))
        resolved = QPushButton("Mark resolved")
        resolved.clicked.connect(lambda: self.set_status("resolved"))
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)

        actions = QHBoxLayout()
        for b in (in_progress, resolved, refresh):
            actions.addWidget(b)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Maintenance reports</h2>", textFormat=Qt.TextFormat.RichText))
        layout.addWidget(self.table)
        layout.addWidget(self.detail)
        layout.addWidget(self.photo)
        layout.addLayout(actions)

        self.reload()

    def reload(self):
        self.rows = self.client.table("maintenance_reports") \
            .select("*, students(first_name, last_name, card_id)") \
            .order("created_at", desc=True).execute().data or []
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            st = r.get("students") or {}
            self.table.setItem(i, 0, QTableWidgetItem(r["category"]))
            self.table.setItem(i, 1, QTableWidgetItem(f"{st.get('first_name','')} {st.get('last_name','')}"))
            self.table.setItem(i, 2, QTableWidgetItem(r["status"]))
            self.table.setItem(i, 3, QTableWidgetItem(r["created_at"]))

    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def show_detail(self):
        r = self.selected()
        if not r:
            self.detail.clear()
            self.photo.clear()
            return
        self.detail.setPlainText(f"{r['description']}\n\nStaff note: {r.get('staff_note') or '—'}")
        self.photo.clear()
        if r.get("photo_path"):
            import urllib.request
            try:
                signed = self.client.storage.from_("maintenance-photos").create_signed_url(r["photo_path"], 300)
                url = (signed or {}).get("signedURL") or (signed or {}).get("signedUrl")
                if url:
                    data = urllib.request.urlopen(url, timeout=15).read()
                    pix = QPixmap()
                    pix.loadFromData(data)
                    self.photo.setPixmap(pix.scaledToWidth(400, Qt.SmoothTransformation))
            except Exception:  # noqa: BLE001
                self.photo.clear()

    def set_status(self, status: str):
        r = self.selected()
        if not r:
            return
        note, ok = QInputDialog.getMultiLineText(self, "Staff note", "Note (optional):")
        if not ok:
            return
        try:
            self.client.table("maintenance_reports") \
                .update({"status": status, "staff_note": note or None}) \
                .eq("id", r["id"]).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
        self.reload()
