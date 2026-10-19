"""RÉSIVO — Staff accounts (visual layer only, docs/DESIGN.md §6–§7).

Split view: the staff DataTable on the left (same table language as every other
page, an ``EmptyState`` when there is no data and a ``Skeleton`` while
``reload()`` is in flight) and the create form card on the right. That form card
is the ``QFrame`` clamped to 340/460 px that the layout tests walk up to from
``self.full_name``. Self-deletion protection keeps its exact tooltips and adds
an info ``InlineBanner`` while the signed-in admin's own row is selected.

The data layer is frozen: ``reload()`` keeps the ``admin-users`` /
``list_staff`` function invocation and its response parsing, ``on_delete()``
keeps the ``delete_staff`` invocation + ``delete_staff`` RPC fallback (with the
self-account guard), and ``on_create()`` keeps the ``create_staff`` invocation
and its required-field validation.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..components import (
    Button,
    Card,
    EmptyState,
    IconButton,
    InlineBanner,
    PageHeader,
    Skeleton,
    configure_table,
)
from ..icons import get_icon
from ..theme import C, S

# Table language: overline headers are uppercased by ``configure_table``.
_COLUMNS = ["Staff Member", "Position / Role", "System Account ID"]


def _fit_columns(table: QTableWidget, modes: list) -> QHeaderView:
    """Apply per-column resize modes (no column keeps a hard-coded width)."""
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    for column, mode in enumerate(modes):
        header.setSectionResizeMode(column, mode)
    return header


class StaffAccountsPage(QWidget):
    """Staff table + provisioning form (admin only)."""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-8"), S("space-8"), S("space-8"), S("space-8"))
        layout.setSpacing(S("space-6"))

        self.header = PageHeader(
            "Staff & administrative access",
            "Manage department officer credentials, assigned positions, and console privileges.",
        )
        self.refresh_btn = IconButton("refresh", "Reload the staff list")
        self.refresh_btn.clicked.connect(self.reload)
        self.header.actions.addWidget(self.refresh_btn)
        layout.addWidget(self.header)

        self.error_banner = InlineBanner(
            "error",
            title="Staff accounts could not be loaded",
            message="Use Refresh to try again.",
        )
        self.error_banner.setVisible(False)
        layout.addWidget(self.error_banner)

        # Splitter layout: staff table on the left, provisioning card right.
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        table_card = QFrame()
        table_card.setObjectName("cardFrame")
        table_card.setMinimumWidth(420)
        tc_layout = QVBoxLayout(table_card)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.table = QTableWidget(0, len(_COLUMNS))
        configure_table(self.table, _COLUMNS)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        _fit_columns(
            self.table,
            [
                QHeaderView.ResizeMode.Stretch,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.Stretch,
            ],
        )
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.stack.addWidget(self.table)

        self.empty_state = EmptyState(
            "shield-check",
            "No staff accounts",
            "Provision the first officer with the form on the right.",
        )
        self.stack.addWidget(self.empty_state)

        self.skeleton = Skeleton(rows=5)
        self.stack.addWidget(self.skeleton)

        tc_layout.addWidget(self.stack)

        # Self-deletion protection is explained while it applies.
        self.self_delete_banner = InlineBanner(
            "info",
            title="Self-deletion protection",
            message="You cannot delete the staff account you are signed in with — "
            "ask another administrator to revoke it if needed.",
        )
        self.self_delete_banner.setVisible(False)
        tc_layout.addWidget(self.self_delete_banner)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(S("space-3"), 0, S("space-3"), S("space-3"))
        btn_row.addStretch(1)

        self.delete_btn = Button.danger("Delete selected staff account", icon="trash")
        self.delete_btn.setFixedHeight(S("size-control"))
        self.delete_btn.setEnabled(False)
        self.delete_btn.setToolTip("")
        self.delete_btn.clicked.connect(self.on_delete)
        btn_row.addWidget(self.delete_btn)
        tc_layout.addLayout(btn_row)

        splitter.addWidget(table_card)

        # Creation form card — the 340/460 QFrame the layout tests assert.
        form_card = Card(
            "Provision staff account",
            "Create a console login for a new officer.",
            icon="shield-check",
        )
        form_card.setMinimumWidth(340)
        form_card.setMaximumWidth(460)

        form = QFormLayout()
        form.setSpacing(S("space-3"))
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.full_name = QLineEdit()
        self.full_name.setPlaceholderText("e.g. Fatima Zohra")

        self.position = QLineEdit()
        self.position.setPlaceholderText("e.g. Housing Officer, Reception…")

        self.email = QLineEdit()
        self.email.setPlaceholderText("officer@univ-tlemcen.dz")

        self.password = QLineEdit()
        self.password.setPlaceholderText("••••••••")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Full Name:", self.full_name)
        form.addRow("Position:", self.position)
        form.addRow("Email:", self.email)
        form.addRow("Password:", self.password)
        form_card.add_layout(form)

        self.create_btn = Button.primary("Create staff account", icon="plus")
        self.create_btn.clicked.connect(self.on_create)
        form_card.add_widget(self.create_btn)

        splitter.addWidget(form_card)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.reload()

    # ------------------------------------------------------------- selection
    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def on_selection_changed(self):
        staff = self.selected()
        if not staff:
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip("")
            self.self_delete_banner.setVisible(False)
            return

        current_uid = None
        user_resp = getattr(self.client.auth, "get_user", lambda: None)()
        if user_resp and hasattr(user_resp, "user") and user_resp.user:
            current_uid = user_resp.user.id

        if staff.get("id") == current_uid:
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip("You cannot delete your own staff account.")
            self.self_delete_banner.setVisible(True)
        else:
            self.delete_btn.setEnabled(True)
            self.delete_btn.setToolTip("")
            self.self_delete_banner.setVisible(False)

    # ------------------------------------------------------------------ data
    def reload(self):
        self._set_loading(True)
        rows = []
        error_text = None
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
                    error_text = str(resp["error"])
                    QMessageBox.warning(self, "Error", error_text)
                elif isinstance(resp.get("data"), list):
                    rows = [r for r in resp["data"] if isinstance(r, dict)]
            elif hasattr(resp, "data"):
                data = resp.data
                if isinstance(data, list):
                    rows = [r for r in data if isinstance(r, dict)]
        except Exception as exc:  # noqa: BLE001
            error_text = str(exc)
            QMessageBox.warning(self, "Error", error_text)

        if error_text is not None:
            self.error_banner.set_message(f"Staff accounts could not be loaded ({error_text}). Use Refresh to try again.")
            self.error_banner.setVisible(True)
        else:
            self.error_banner.setVisible(False)

        self.rows = rows
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            name_item = QTableWidgetItem(str(r.get("full_name", "")))
            name_item.setIcon(get_icon("staff_accounts", 14, C("teal-600")))
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, QTableWidgetItem(str(r.get("position") or "Officer")))
            self.table.setItem(i, 2, QTableWidgetItem(str(r.get("id", ""))))

        self.on_selection_changed()
        self._set_loading(False)

    def _set_loading(self, loading: bool) -> None:
        """Swap the table for the Skeleton while ``reload()`` is in flight."""
        if loading:
            self.stack.setCurrentWidget(self.skeleton)
            self.skeleton.raise_()
            app = QApplication.instance()
            if app is not None and self.isVisible():
                # Let the placeholder paint before the (blocking) call runs.
                app.processEvents()
        else:
            self.stack.setCurrentWidget(self.table if self.rows else self.empty_state)

    # ---------------------------------------------------------------- actions
    def on_delete(self):
        staff = self.selected()
        if not staff:
            return

        current_uid = None
        try:
            user_resp = getattr(self.client.auth, "get_user", lambda: None)()
            if user_resp and hasattr(user_resp, "user") and user_resp.user:
                current_uid = user_resp.user.id
        except Exception:
            current_uid = None

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
