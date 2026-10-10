from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QFileDialog, QMessageBox,
)
from ...importers.official_list import read_official_file


class OfficialListPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Card ID", "First", "Last", "Birth date", "Gender", "University", "Faculty"]
        )

        import_btn = QPushButton("Import Excel/CSV…")
        import_btn.clicked.connect(self.on_import)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)

        actions = QHBoxLayout()
        actions.addWidget(import_btn)
        actions.addWidget(refresh)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Official residents list</h2>", textFormat=Qt.TextFormat.RichText))
        layout.addWidget(self.table)
        layout.addLayout(actions)

        self.reload()

    def reload(self):
        rows = self.client.table("official_residents").select("*").order("card_id").execute().data or []
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for c, key in enumerate(["card_id", "first_name", "last_name", "birth_date", "gender", "university", "faculty"]):
                self.table.setItem(i, c, QTableWidgetItem(str(r.get(key) or "")))

    def on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open official list", "", "Spreadsheets (*.xlsx *.csv)")
        if not path:
            return
        try:
            rows = read_official_file(path)
            self.client.rpc("import_official_residents", {"p_rows": rows}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Import error", str(exc))
            return
        QMessageBox.information(self, "Imported", f"Imported {len(rows)} rows.")
        self.reload()
