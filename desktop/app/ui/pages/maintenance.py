from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QTextEdit, QInputDialog, QMessageBox, QFrame,
    QSplitter, QLineEdit,
)
from ...client import official_lookup
from ..icons import get_icon, get_pixmap
from ..theme import apply_button_style
from ..infocard import StudentInfoCardDialog
from ..photo_viewer import ClickablePhotoLabel, PhotoViewerDialog, PhotoFetchWorker


class MaintenancePage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []
        self.filter_mode = "all"
        self._thumb_worker: PhotoFetchWorker | None = None
        self._photo_req_id: int = 0
        self._current_photo_url: str | None = None
        self._current_pixmap: QPixmap | None = None
        self._photo_fetch_failed: bool = False
        self._photo_loading: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Bar
        header_row = QHBoxLayout()
        header_vbox = QVBoxLayout()
        title_lbl = QLabel("Facility Maintenance & Repairs")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #f8fafc;")
        sub_lbl = QLabel("Triage plumbing, electrical, furniture, and heating repair tickets filed by residents.")
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

        # Filter & Search Row
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.btn_all = QPushButton("All Tickets")
        self.btn_pending = QPushButton("Pending Triage")
        self.btn_in_progress = QPushButton("In Progress")
        self.btn_resolved = QPushButton("Resolved")

        for b in (self.btn_all, self.btn_pending, self.btn_in_progress, self.btn_resolved):
            b.setCheckable(True)
            apply_button_style(b, "filter")
            toolbar.addWidget(b)

        self.btn_all.setChecked(True)
        self.btn_all.clicked.connect(lambda: self.set_filter("all"))
        self.btn_pending.clicked.connect(lambda: self.set_filter("pending"))
        self.btn_in_progress.clicked.connect(lambda: self.set_filter("in_progress"))
        self.btn_resolved.clicked.connect(lambda: self.set_filter("resolved"))

        toolbar.addSpacing(12)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search tickets by description, student, or category...")
        self.search_input.textChanged.connect(self.apply_filter)
        toolbar.addWidget(self.search_input, 1)

        layout.addLayout(toolbar)

        # Splitter Layout (Left: Table, Right: Inspector)
        splitter = QSplitter(Qt.Horizontal)

        table_card = QFrame()
        table_card.setObjectName("cardFrame")
        tc_layout = QVBoxLayout(table_card)
        tc_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Category", "Resident", "Status", "Reported"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        self.table.horizontalHeader().setStretchLastSection(True)
        tc_layout.addWidget(self.table)
        splitter.addWidget(table_card)

        # Inspector Card
        detail_card = QFrame()
        detail_card.setObjectName("cardFrame")
        detail_card.setMinimumWidth(360)
        detail_card.setMaximumWidth(520)
        dc_layout = QVBoxLayout(detail_card)
        dc_layout.setSpacing(12)
        dc_layout.setContentsMargins(16, 16, 16, 16)

        detail_title = QLabel("Ticket Inspector")
        detail_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #f8fafc;")
        dc_layout.addWidget(detail_title)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setFixedHeight(140)
        self.detail_text.setPlaceholderText("Select a ticket from the table...")
        dc_layout.addWidget(self.detail_text)

        # Photo Inspector
        self.photo_label = ClickablePhotoLabel("No fault photo attached")
        self.photo_label.setObjectName("maintenancePhotoLabel")
        self.photo_label.setAlignment(Qt.AlignCenter)
        self.photo_label.setStyleSheet("""
            QLabel#maintenancePhotoLabel {
                background-color: #0b0d14;
                border: 1px dashed #22293b;
                border-radius: 8px;
                color: #64748b;
                font-size: 12px;
            }
            QLabel#maintenancePhotoLabel:hover {
                border-color: #38bdf8;
            }
        """)
        self.photo_label.setFixedHeight(180)
        self.photo_label.clicked.connect(self.on_photo_clicked)
        dc_layout.addWidget(self.photo_label)

        # Status Update Actions
        actions_box = QVBoxLayout()
        actions_box.setSpacing(8)

        self.in_progress_btn = QPushButton("Mark In Progress (Technician Dispatched)")
        self.in_progress_btn.setFixedHeight(40)
        self.in_progress_btn.setIcon(get_icon("maintenance", size=16, color="#ffffff"))
        apply_button_style(self.in_progress_btn, "in_progress")
        self.in_progress_btn.clicked.connect(lambda: self.set_status("in_progress"))

        self.resolved_btn = QPushButton("Mark Resolved & Close Ticket")
        self.resolved_btn.setFixedHeight(40)
        self.resolved_btn.setIcon(get_icon("check", size=16, color="#ffffff"))
        apply_button_style(self.resolved_btn, "success")
        self.resolved_btn.clicked.connect(lambda: self.set_status("resolved"))

        self.delete_btn = QPushButton("Delete Maintenance Ticket")
        self.delete_btn.setFixedHeight(40)
        self.delete_btn.setIcon(get_icon("trash", size=16, color="#ffffff"))
        apply_button_style(self.delete_btn, "danger")
        self.delete_btn.clicked.connect(self.on_delete)
        self.delete_btn.setEnabled(False)

        actions_box.addWidget(self.in_progress_btn)
        actions_box.addWidget(self.resolved_btn)
        actions_box.addWidget(self.delete_btn)
        dc_layout.addLayout(actions_box)

        splitter.addWidget(detail_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.reload()

    def set_filter(self, mode: str):
        self.filter_mode = mode
        self.btn_all.setChecked(mode == "all")
        self.btn_pending.setChecked(mode == "pending")
        self.btn_in_progress.setChecked(mode == "in_progress")
        self.btn_resolved.setChecked(mode == "resolved")
        self.apply_filter()

    def apply_filter(self):
        needle = self.search_input.text().lower().strip()
        for r in range(self.table.rowCount()):
            row_data = self.rows[r] if r < len(self.rows) else {}
            st = row_data.get("students") or {}
            status = row_data.get("status", "")
            cat = str(row_data.get("category", "")).lower()
            desc = str(row_data.get("description", "")).lower()
            name = f"{st.get('first_name','')} {st.get('last_name','')}".lower()

            status_matches = (
                self.filter_mode == "all"
                or (self.filter_mode == "pending" and status == "pending")
                or (self.filter_mode == "in_progress" and status == "in_progress")
                or (self.filter_mode == "resolved" and status == "resolved")
            )
            text_matches = needle in f"{cat} {desc} {name}"
            self.table.setRowHidden(r, not (status_matches and text_matches))

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
            status_text = "Pending" if status == "pending" else "In Progress" if status == "in_progress" else "Resolved"

            cat_item = QTableWidgetItem(str(r.get("category", "")).capitalize())
            cat_item.setIcon(get_icon("maintenance", size=14, color="#2563eb"))
            student_item = QTableWidgetItem(f"{st.get('first_name', '')} {st.get('last_name', '')}")
            status_item = QTableWidgetItem(status_text)
            date_item = QTableWidgetItem(str(r.get("created_at", ""))[:10])

            if status == "resolved":
                status_item.setForeground(QColor("#34d399"))
            elif status == "in_progress":
                status_item.setForeground(QColor("#38bdf8"))
            else:
                status_item.setForeground(QColor("#fbbf24"))

            self.table.setItem(i, 0, cat_item)
            self.table.setItem(i, 1, student_item)
            self.table.setItem(i, 2, status_item)
            self.table.setItem(i, 3, date_item)

        if restore_row >= 0:
            self.table.selectRow(restore_row)
        else:
            self._cleanup_thumb_worker()
            self._current_pixmap = None
            self._current_photo_url = None
            self._photo_fetch_failed = False
            self._photo_loading = False
            self.detail_text.clear()
            self.photo_label.clear()
            self.photo_label.setText("No fault photo attached")
            self.photo_label.setCursor(Qt.ArrowCursor)
            self.photo_label.setToolTip("")
            self.delete_btn.setEnabled(False)

        self.apply_filter()

    def _cleanup_thumb_worker(self):
        if self._thumb_worker is not None:
            try:
                self._thumb_worker.loaded.disconnect()
                self._thumb_worker.failed.disconnect()
            except RuntimeError:
                pass
            self._thumb_worker.stop()
            self._thumb_worker = None

    def reload(self):
        try:
            resp = self.client.table("maintenance_reports") \
                .select("*, students(first_name, last_name, card_id)") \
                .order("created_at", desc=True).execute()
            self.apply_live_data(resp.data or [])
        except Exception:
            pass

    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def show_detail(self):
        self._cleanup_thumb_worker()
        self._photo_req_id += 1
        current_req = self._photo_req_id
        self._current_pixmap = None
        self._current_photo_url = None
        self._photo_fetch_failed = False
        self._photo_loading = False

        r = self.selected()
        if not r:
            self.detail_text.clear()
            self.photo_label.clear()
            self.photo_label.setText("No fault photo attached")
            self.photo_label.setCursor(Qt.ArrowCursor)
            self.photo_label.setToolTip("")
            self.delete_btn.setEnabled(False)
            return

        self.delete_btn.setEnabled(True)
        st = r.get("students") or {}
        staff_note = r.get("staff_note") or "No technician notes recorded."
        self.detail_text.setPlainText(
            f"CATEGORY: {r.get('category', '').upper()}\n"
            f"Resident: {st.get('first_name', '')} {st.get('last_name', '')} (Card ID: {st.get('card_id', '—')})\n"
            f"Status: {r.get('status', '').upper()}\n\n"
            f"DESCRIPTION:\n{r.get('description', '')}\n\n"
            f"STAFF / DISPATCH NOTE:\n{staff_note}"
        )

        self.photo_label.clear()
        if not r.get("photo_path"):
            self.photo_label.setText("No photo attached by resident")
            self.photo_label.setCursor(Qt.PointingHandCursor)
            self.photo_label.setToolTip("Click to view fault details")
            return

        self.photo_label.setText("Loading photo...")
        self.photo_label.setCursor(Qt.PointingHandCursor)
        self.photo_label.setToolTip("Loading photo preview…")
        self._photo_loading = True

        url = None
        try:
            signed = self.client.storage.from_("maintenance-photos").create_signed_url(r["photo_path"], 300)
            url = (signed or {}).get("signedURL") or (signed or {}).get("signedUrl")
        except Exception:
            url = None

        if not url:
            self._photo_loading = False
            self._photo_fetch_failed = True
            self.photo_label.setText("Photo unavailable")
            self.photo_label.setToolTip("Failed to retrieve signed URL")
            return

        self._current_photo_url = url

        def on_loaded(data: bytes, req=current_req, img_url=url):
            if self._photo_req_id != req:
                return
            self._photo_loading = False
            pix = QPixmap()
            if pix.loadFromData(data) and not pix.isNull() and pix.width() > 0 and pix.height() > 0:
                self._current_pixmap = pix
                self._current_photo_url = img_url
                scaled = pix.scaled(380, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.photo_label.setPixmap(scaled)
                self.photo_label.setCursor(Qt.PointingHandCursor)
                self.photo_label.setToolTip("Click to open full-size photo viewer")
            else:
                self._photo_fetch_failed = True
                self.photo_label.setText("Photo preview unavailable")

        def on_failed(err_msg: str, req=current_req):
            if self._photo_req_id != req:
                return
            self._photo_loading = False
            self._photo_fetch_failed = True
            self.photo_label.setText("Failed to load photo")

        worker = PhotoFetchWorker(url, parent=None)
        worker.finished.connect(worker.deleteLater)
        self._thumb_worker = worker
        worker.loaded.connect(on_loaded)
        worker.failed.connect(on_failed)
        worker.start()

    def on_photo_clicked(self):
        r = self.selected()
        if not r:
            return

        if not r.get("photo_path"):
            QMessageBox.information(
                self,
                "Fault Photo",
                "No photo was attached to this maintenance ticket by the resident.",
            )
            return

        if self._photo_fetch_failed and not self._current_pixmap:
            QMessageBox.information(
                self,
                "Fault Photo",
                "Fault photo could not be loaded from storage. Please check the network connection.",
            )
            return

        dlg = PhotoViewerDialog(
            parent=self,
            initial_pixmap=self._current_pixmap,
            image_url=self._current_photo_url,
        )
        try:
            dlg.exec()
        finally:
            dlg.deleteLater()

    def closeEvent(self, event):
        worker = self._thumb_worker
        self._cleanup_thumb_worker()
        if worker is not None and worker.isRunning():
            worker.wait(2000)
        super().closeEvent(event)

    def on_row_double_clicked(self, row: int, col: int):
        r = self.selected()
        if r and r.get("students"):
            st = dict(r.get("students"))
            roster_map = {}
            try:
                roster_map = official_lookup(self.client)
            except Exception:
                pass
            roster_match = roster_map.get(st.get("card_id"))
            dlg = StudentInfoCardDialog(self, st, roster_match)
            dlg.exec()

    def set_status(self, status: str):
        r = self.selected()
        if not r:
            QMessageBox.information(self, "Select ticket", "Please select a maintenance ticket from the table first.")
            return

        default_note = r.get("staff_note") or ""
        note, ok = QInputDialog.getMultiLineText(
            self,
            "Staff Dispatch Note",
            f"Add note for technician / resolution ({status.replace('_', ' ')}):",
            text=default_note,
        )
        if not ok:
            return

        note_val = note.strip() or default_note or None
        user = None
        try:
            user = getattr(self.client.auth.get_user(), "user", None)
        except Exception:
            pass

        update_data = {"status": status, "staff_note": note_val}
        if user:
            update_data["handled_by"] = user.id

        try:
            self.client.table("maintenance_reports").update(update_data).eq("id", r["id"]).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Update Error", f"Network error updating ticket: {exc}")
            return

        QMessageBox.information(self, "Status Updated", f"Maintenance ticket updated to '{status.replace('_', ' ')}'.")
        try:
            self.reload()
        except Exception:
            pass

    def on_delete(self):
        t = self.selected()
        if not t:
            return

        ticket_id = str(t.get("id", ""))[:8]
        ans = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to permanently delete maintenance ticket #{ticket_id}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ans != QMessageBox.Yes:
            return

        try:
            self.client.table("maintenance_reports").delete().eq("id", t["id"]).execute()
            QMessageBox.information(self, "Deleted", "Maintenance ticket deleted successfully.")
            self.reload()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Failed to delete ticket: {exc}")

