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

Every network call after the first paint runs on the shared :class:`TaskRunner`
thread pool; the GUI thread only renders results. The signed-in user's id is
cached once at page load so selecting rows never performs an auth lookup.

``defer_initial_load=True`` is the late-promotion path: it skips the
constructor's synchronous identity/list round-trip (the shell's first-paint
contract is unchanged for the normal constructor) and starts the existing
asynchronous ``reload()`` instead.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from ...client import stored_user_id
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
from ..tasks import TaskRunner, human_error
from ..theme import C, S

# Table language: overline headers are uppercased by ``configure_table``.
_COLUMNS = ["Staff Member", "Position / Role", "System Account ID"]

_CREATE_TEXT = "Create staff account"
_DELETE_TEXT = "Delete selected staff account"
_WORKING_TEXT = "Working..."
_RELOAD_KEY = "staff-reload"
_ACTION_KEY = "staff-action"


def _fit_columns(table: QTableWidget, modes: list) -> QHeaderView:
    """Apply per-column resize modes (no column keeps a hard-coded width)."""
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    for column, mode in enumerate(modes):
        header.setSectionResizeMode(column, mode)
    return header


class StaffAccountsPage(QWidget):
    """Staff table + provisioning form (admin only)."""

    def __init__(self, client, defer_initial_load=False, current_uid=None):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []
        self._defer_initial_load = bool(defer_initial_load)

        # Background I/O. The constructor keeps one synchronous first load so
        # the initial paint has data (the project-wide page contract); every
        # later refresh, create and delete runs on the thread pool.
        self.tasks = TaskRunner(self)
        self._initializing = True
        self._current_uid: str | None = None
        if current_uid is not None:
            uid = str(current_uid).strip()
            self._current_uid = uid or None
        self._action_busy = False
        self._list_busy = False
        self._reload_pending = False
        self._active_button = None
        self._active_button_text = ""

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

        if self._defer_initial_load:
            # Late promotion: no synchronous auth/list call on the GUI thread.
            # A cheap local session read fills in the id when MainWindow could
            # not provide one; then the existing async reload takes over.
            if self._current_uid is None:
                self._current_uid = self._local_session_user_id()
            self._initializing = False
            self.reload()
            return

        # Cache the signed-in id once; selection changes only compare against
        # this value and never touch the auth API again.
        self._current_uid = self._fetch_current_user_id()
        self.reload()
        self._initializing = False

    # ------------------------------------------------------------- identity
    def _local_session_user_id(self) -> str | None:
        """Signed-in id from the stored session only (never a network call)."""
        return stored_user_id(self.client)

    def _fetch_current_user_id(self) -> str | None:
        """Signed-in user id (initial load only)."""
        try:
            user_resp = getattr(self.client.auth, "get_user", lambda: None)()
            user = getattr(user_resp, "user", None)
            return getattr(user, "id", None) if user else None
        except Exception:  # noqa: BLE001 - missing session just disables deletion
            return None

    # ------------------------------------------------------------- selection
    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def on_selection_changed(self):
        """Apply the delete guards using the cached signed-in id only."""
        staff = self.selected()
        if not staff:
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip("")
            self.self_delete_banner.setVisible(False)
            return

        if self._action_busy:
            # A create/delete is in flight: never start a second write.
            self.delete_btn.setEnabled(False)
            self.self_delete_banner.setVisible(False)
            return

        if not self._current_uid:
            # Missing session: fail safe instead of guessing who is signed in.
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip(
                "Your signed-in account could not be verified, so deletion is disabled."
            )
            self.self_delete_banner.setVisible(False)
            return

        if staff.get("id") == self._current_uid:
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip("You cannot delete your own staff account.")
            self.self_delete_banner.setVisible(True)
        else:
            self.delete_btn.setEnabled(True)
            self.delete_btn.setToolTip("")
            self.self_delete_banner.setVisible(False)

    # ------------------------------------------------------------------ data
    def reload(self):
        """Load the staff list; the constructor keeps its synchronous first paint."""
        if self._initializing:
            self._load_sync()
            return
        self._reload_async()

    def _load_sync(self) -> None:
        """Initial load only (keeps the constructor contract synchronous)."""
        self._set_loading(True)
        try:
            rows = self._fetch_staff_rows()
        except Exception as exc:  # noqa: BLE001 - reported inline
            self._on_reload_failed(human_error(exc))
        else:
            self._on_reload_success(rows)

    def _reload_async(self) -> None:
        if self._list_busy:
            # A create/delete may finish during this refresh: coalesce the
            # follow-up into one more load instead of dropping it.
            self._reload_pending = True
            return
        self._list_busy = True
        self._sync_controls()
        self._set_loading(True)
        started = self.tasks.run(
            _RELOAD_KEY,
            self._fetch_staff_rows,
            on_success=self._on_reload_success,
            on_failed=self._on_reload_failed,
            on_finished=self._on_reload_finished,
        )
        if not started:
            self._list_busy = False
            self._sync_controls()
            self._set_loading(False)

    def _on_reload_success(self, rows) -> None:
        self.error_banner.setVisible(False)
        self._apply_rows(rows)
        self._set_loading(False)

    def _on_reload_failed(self, message: str) -> None:
        self.error_banner.set_message(
            f"Staff accounts could not be loaded ({message}). Use Refresh to try again."
        )
        self.error_banner.setVisible(True)
        self._set_loading(False)

    def _on_reload_finished(self) -> None:
        self._list_busy = False
        self._sync_controls()
        if self._reload_pending:
            self._reload_pending = False
            self.reload()

    def _apply_rows(self, rows) -> None:
        """Render rows on the GUI thread, preserving the selected staff id."""
        selected = self.selected()
        selected_id = selected.get("id") if selected else None
        self.rows = [r for r in (rows or []) if isinstance(r, dict)]

        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.rows))
            restore_row = -1
            for i, r in enumerate(self.rows):
                name_item = QTableWidgetItem(str(r.get("full_name", "")))
                name_item.setIcon(get_icon("staff_accounts", 14, C("teal-600")))
                self.table.setItem(i, 0, name_item)
                self.table.setItem(i, 1, QTableWidgetItem(str(r.get("position") or "Officer")))
                self.table.setItem(i, 2, QTableWidgetItem(str(r.get("id", ""))))
                if selected_id is not None and r.get("id") == selected_id:
                    restore_row = i
            if restore_row >= 0:
                self.table.selectRow(restore_row)
            else:
                self.table.clearSelection()
                self.table.setCurrentCell(-1, -1)
        finally:
            self.table.blockSignals(False)
        self.on_selection_changed()

    @staticmethod
    def _decode_payload(resp):
        """bytes/str JSON payloads from the Edge Function, other values as-is."""
        if isinstance(resp, (bytes, bytearray)):
            try:
                return json.loads(resp.decode("utf-8"))
            except Exception:  # noqa: BLE001 - keep the original payload
                return resp
        if isinstance(resp, str):
            try:
                return json.loads(resp)
            except Exception:  # noqa: BLE001 - keep the original payload
                return resp
        return resp

    def _invoke_admin_users(self, body: dict):
        """Call the admin-users Edge Function (worker thread in async paths)."""
        resp = self.client.functions.invoke(
            "admin-users",
            invoke_options={"body": body, "responseType": "json"},
        )
        return self._decode_payload(resp)

    def _fetch_staff_rows(self) -> list[dict]:
        """Network read of the staff list (never call from the GUI thread)."""
        resp = self._invoke_admin_users({"action": "list_staff"})
        if isinstance(resp, list):
            return [r for r in resp if isinstance(r, dict)]
        if isinstance(resp, dict):
            if "error" in resp:
                raise RuntimeError(str(resp["error"]))
            if isinstance(resp.get("data"), list):
                return [r for r in resp["data"] if isinstance(r, dict)]
            return []
        data = getattr(resp, "data", None)
        return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []

    def _set_loading(self, loading: bool) -> None:
        """Swap the table for the Skeleton while a load is in flight."""
        if loading:
            self.stack.setCurrentWidget(self.skeleton)
            self.skeleton.raise_()
        else:
            self.stack.setCurrentWidget(self.table if self.rows else self.empty_state)

    def _sync_controls(self) -> None:
        self.refresh_btn.setEnabled(not self._list_busy and not self._action_busy)
        self.create_btn.setEnabled(not self._action_busy)
        if self._action_busy:
            self.delete_btn.setEnabled(False)
        else:
            self.on_selection_changed()

    # ---------------------------------------------------------------- actions
    def _begin_action(self, button, normal_text: str) -> None:
        """Disable every write control and show progress on the acting button."""
        self._action_busy = True
        self._active_button = button
        self._active_button_text = normal_text
        self.create_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        button.setText(_WORKING_TEXT)
        button.setEnabled(False)

    def _end_action(self) -> None:
        self._action_busy = False
        if self._active_button is not None:
            self._active_button.setText(self._active_button_text)
            self._active_button = None
        self.create_btn.setEnabled(True)
        self._sync_controls()

    def _on_action_failed(self, message: str, title: str) -> None:
        QMessageBox.critical(self, title, f"The request could not be completed: {message}")

    def on_delete(self):
        staff = self.selected()
        if not staff:
            return
        if self._action_busy or self.tasks.is_busy(_ACTION_KEY):
            return

        if not self._current_uid:
            QMessageBox.warning(
                self,
                "Cannot Delete",
                "Your signed-in account could not be verified, so deletion is disabled.",
            )
            return

        if staff.get("id") == self._current_uid:
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

        staff_id = staff["id"]
        self._begin_action(self.delete_btn, _DELETE_TEXT)
        started = self.tasks.run(
            _ACTION_KEY,
            lambda: self._delete_staff(staff_id),
            on_success=lambda _result: self._on_delete_success(),
            on_failed=lambda message: self._on_action_failed(message, "Error Deleting Staff"),
            on_finished=self._end_action,
        )
        if not started:
            self._end_action()

    def _delete_staff(self, staff_id):
        """Edge Function delete with the historical RPC fallback (worker thread)."""
        last_error = None
        try:
            resp = self._invoke_admin_users({"action": "delete_staff", "id": staff_id})
        except Exception as exc:  # noqa: BLE001 - fallback below
            last_error = exc
        else:
            if isinstance(resp, dict) and resp.get("success") is True:
                return True
            # An empty/ambiguous reply is not proof of deletion: try the RPC
            # instead of showing a success dialog for a no-op.
            last_error = (
                resp.get("error") if isinstance(resp, dict) else "unexpected reply"
            )

        try:
            self.client.rpc("delete_staff", {"p_staff": staff_id}).execute()
        except Exception as rpc_exc:  # noqa: BLE001 - reported to the page
            raise RuntimeError(str(last_error or rpc_exc)) from rpc_exc
        return True

    def _on_delete_success(self) -> None:
        QMessageBox.information(self, "Staff Account Deleted", "Staff account deleted successfully.")
        self.reload()

    def on_create(self):
        if self._action_busy or self.tasks.is_busy(_ACTION_KEY):
            return
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

        self._begin_action(self.create_btn, _CREATE_TEXT)
        started = self.tasks.run(
            _ACTION_KEY,
            lambda: self._create_staff(body),
            on_success=lambda _result: self._on_create_success(body),
            on_failed=lambda message: self._on_action_failed(message, "Error Creating Staff"),
            on_finished=self._end_action,
        )
        if not started:
            self._end_action()

    def _create_staff(self, body: dict):
        """Create the staff account on the Edge Function (worker thread)."""
        resp = self._invoke_admin_users(body)
        if isinstance(resp, dict) and "error" in resp:
            raise RuntimeError(str(resp["error"]))
        return resp

    def _on_create_success(self, body: dict) -> None:
        self.email.clear()
        self.password.clear()
        self.full_name.clear()
        self.position.clear()
        self.reload()
        QMessageBox.information(
            self,
            "Staff Account Created",
            f"Account for {body['full_name']} created successfully.",
        )
