from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QFileDialog, QMessageBox, QFrame, QLineEdit,
)
from ...importers.official_list import read_official_file
from ..icons import get_icon, get_pixmap
from ..theme import apply_button_style
from ..infocard import StudentInfoCardDialog


class OfficialListPage(QWidget):
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
        title_lbl = QLabel("Official University Roster")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #f8fafc;")
        sub_lbl = QLabel("Master admissions database used to automatically verify student housing applications.")
        sub_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        header_vbox.addWidget(title_lbl)
        header_vbox.addWidget(sub_lbl)
        header_row.addLayout(header_vbox)
        header_row.addStretch(1)

        self.count_badge = QLabel("0 Records")
        self.count_badge.setStyleSheet("""
            background-color: #0c4a6e;
            color: #38bdf8;
            border: 1px solid #0284c7;
            border-radius: 12px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 700;
        """)
        header_row.addWidget(self.count_badge)

        from ...client import current_role
        self.role = current_role(client)

        import_btn = QPushButton("Import Excel / CSV Roster…")
        import_btn.setIcon(get_icon("upload", size=14, color="#ffffff"))
        apply_button_style(import_btn, "primary")
        if self.role != "admin":
            import_btn.setEnabled(False)
            import_btn.setToolTip("Administrator privileges required to import roster.")
        import_btn.clicked.connect(self.on_import)
        header_row.addWidget(import_btn)

        refresh = QPushButton("Refresh")
        refresh.setIcon(get_icon("refresh", size=14, color="#cbd5e1"))
        apply_button_style(refresh, "secondary")
        refresh.clicked.connect(self.reload)
        header_row.addWidget(refresh)

        layout.addLayout(header_row)

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search official roster by card ID, student name, university, or faculty...")
        self.search_input.textChanged.connect(self.filter_table)
        layout.addWidget(self.search_input)

        # Table Container
        table_card = QFrame()
        table_card.setObjectName("cardFrame")
        tc_layout = QVBoxLayout(table_card)
        tc_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Card ID", "First Name", "Last Name", "Birth Date", "Gender", "University", "Faculty",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        self.table.horizontalHeader().setStretchLastSection(True)
        tc_layout.addWidget(self.table)
        layout.addWidget(table_card, 1)

        tip_lbl = QLabel("💡 Tip: Double-click any official record to view their profile card.")
        tip_lbl.setStyleSheet("font-size: 11px; color: #64748b; padding-left: 2px;")
        layout.addWidget(tip_lbl)

        self.reload()

    def filter_table(self):
        needle = self.search_input.text().lower().strip()
        for r in range(self.table.rowCount()):
            row_data = self.rows[r] if r < len(self.rows) else {}
            haystack = f"{row_data.get('card_id', '')} {row_data.get('first_name', '')} {row_data.get('last_name', '')} {row_data.get('university', '')} {row_data.get('faculty', '')}".lower()
            self.table.setRowHidden(r, needle not in haystack)

    def reload(self):
        self.rows = self.client.table("official_residents").select("*").order("card_id").execute().data or []
        self.count_badge.setText(f"{len(self.rows)} Verified Records")
        self.table.setRowCount(len(self.rows))

        for i, r in enumerate(self.rows):
            card_item = QTableWidgetItem(str(r.get("card_id") or ""))
            card_item.setIcon(get_icon("official_list", size=14, color="#38bdf8"))
            self.table.setItem(i, 0, card_item)
            self.table.setItem(i, 1, QTableWidgetItem(str(r.get("first_name") or "")))
            self.table.setItem(i, 2, QTableWidgetItem(str(r.get("last_name") or "")))
            self.table.setItem(i, 3, QTableWidgetItem(str(r.get("birth_date") or "")))
            self.table.setItem(i, 4, QTableWidgetItem(str(r.get("gender") or "").capitalize()))
            self.table.setItem(i, 5, QTableWidgetItem(str(r.get("university") or "")))
            self.table.setItem(i, 6, QTableWidgetItem(str(r.get("faculty") or "")))

        self.filter_table()

    def on_row_double_clicked(self, row: int, col: int):
        if 0 <= row < len(self.rows):
            r = self.rows[row]
            st_data = {
                "card_id": r.get("card_id"),
                "first_name": r.get("first_name"),
                "last_name": r.get("last_name"),
                "birth_date": r.get("birth_date"),
                "gender": r.get("gender"),
                "university": r.get("university"),
                "faculty": r.get("faculty"),
                "status": "active",
            }
            dlg = StudentInfoCardDialog(self, st_data, r)
            dlg.exec()

    def on_import(self):
        from ...client import current_role
        if current_role(self.client) != "admin":
            QMessageBox.warning(self, "Permission Denied", "Importing the official residents list requires administrator privileges.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open Official Roster File", "", "Spreadsheets (*.xlsx *.csv)")
        if not path:
            return
        try:
            rows = read_official_file(path)
            self.client.rpc("import_official_residents", {"p_rows": rows}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Import Error", str(exc))
            return
        QMessageBox.information(self, "Roster Imported", f"Successfully imported {len(rows)} official student records.")
        self.reload()
