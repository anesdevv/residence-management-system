"""RÉSIVO — Room change requests (visual layer only, docs/DESIGN.md §6–§7).

Master-detail page: a ``PageHeader``, a ``SearchField``, the pending transfer
requests ``QTableWidget`` on the left and the 340/480 ``DetailPanel`` inspector
on the right — resident identity with the ``StatusPill``, the "current room ›
requested room" move visual (two room cards joined by the ``arrow-left-right``
icon, with a ``RoomOccupancyBar`` whenever the fetched room carries capacity
data), the stated reason as a quoted block, the submission facts, the guarded
approve / reject / delete actions and the plain-text record block.

The data layer is frozen: ``reload()`` keeps its ``room_change_requests`` select
(``*, students(first_name, last_name, gender, card_id)`` filtered on
``status = pending``), ``apply_live_data`` keeps the ``(id, status)`` diff and
the selection restore by id, ``show_detail`` keeps the single ``rooms`` lookup
(``block, number, floor`` through ``preferred_room_id``), ``on_approve`` keeps
the gender-filtered ``rooms`` query + ``room_occupancy`` + the ``[LOCKED]``
guard + the ``approve_room_change`` RPC, ``on_reject`` keeps
``reject_room_change`` and its reason validation, and ``on_delete`` keeps the
delete + reload.

Widget contracts kept for the tests
-----------------------------------
``table`` / ``rows`` / ``delete_btn`` / ``approve_btn`` / ``reject_btn`` /
``selected()`` / ``show_detail()`` / ``on_row_double_clicked()`` /
``on_approve()`` / ``on_reject()`` / ``on_delete()`` / ``filter_table()`` /
``apply_live_data()`` / ``reload()`` are unchanged; ``delete_btn`` is disabled
until a row is selected; ``detail_text`` is a direct child of the 340/480
``DetailPanel`` frame.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...client import official_lookup, room_occupancy
from .. import theme
from ..components import (
    Avatar,
    Button,
    ConfirmDialog,
    DetailPanel,
    EmptyState,
    IconButton,
    InlineBanner,
    KeyValueList,
    PageHeader,
    RoomOccupancyBar,
    SearchField,
    StatusPill,
    configure_table,
)
from ..icons import get_pixmap
from ..infocard import StudentInfoCardDialog
from ..theme import C, S

# Table language: overline headers are uppercased by configure_table().
_COLUMNS = ["Resident", "Status", "Reason", "Submitted"]

# request status -> (StatusPill kind, status word)
_STATUS_KINDS = {
    "pending": ("pending", "Pending"),
    "approved": ("ok", "Approved"),
    "rejected": ("danger", "Rejected"),
}
_DEFAULT_STATUS = ("pending", "Pending")


def _normalise_student(row: dict) -> dict:
    """``students`` embed of a request row as a plain dict (list/dict/None safe)."""
    st = row.get("students") or {}
    if isinstance(st, list) and st:
        st = st[0]
    elif not isinstance(st, dict):
        st = {}
    return st


def _status_meta(raw_status) -> tuple[str, str]:
    """``(StatusPill kind, status word)`` for any request status value."""
    return _STATUS_KINDS.get(str(raw_status), _DEFAULT_STATUS)


def _fmt_date(value) -> str:
    """Date-only value (raw data, never invented)."""
    text = str(value or "").strip()
    return text[:10] if text else "—"


def _fmt_stamp(value) -> str:
    """Readable timestamp for the record block (raw value, never invented)."""
    text = str(value or "").strip()
    if not text:
        return "—"
    return text.replace("T", " ").replace("Z", "").strip()


def _short_id(value) -> str:
    """First 8 characters of a UUID (raw reference, never invented)."""
    text = str(value or "").strip()
    return text[:8] if text else ""


def _cell_widget(widget: QWidget) -> QWidget:
    """Wrap a widget for a table cell so clicks still select the row.

    ``WA_TransparentForMouseEvents`` also disables delivery for the wrapper's
    children, so a pill never swallows the row selection. The wrapper keeps no
    margins of its own: the stylesheet's item padding already insets it.
    """
    holder = QWidget()
    holder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
    row.addStretch(1)
    return holder


def _pill_item(text: str, holder: QWidget) -> QTableWidgetItem:
    """Cell item behind a pill widget (readable text, painted transparently)."""
    item = QTableWidgetItem(text)
    item.setForeground(QBrush(QColor(0, 0, 0, 0)))
    hint = holder.sizeHint()
    item.setSizeHint(QSize(hint.width() + 2 * S("space-3"), hint.height()))
    return item


def _fit_columns(table: QTableWidget, modes: list) -> QHeaderView:
    """Apply per-column resize modes (last section keeps its own mode)."""
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    for column, mode in enumerate(modes):
        header.setSectionResizeMode(column, mode)
    return header


class _QuotedBlock(QFrame):
    """Tinted block: overline + quoted body (the stated transfer reason)."""

    def __init__(self, overline_text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("quotedBlock")
        column = QVBoxLayout(self)
        column.setContentsMargins(S("space-3"), S("space-3"), S("space-3"), S("space-3"))
        column.setSpacing(S("space-1"))
        self.overline = QLabel(str(overline_text).upper())
        theme.apply_role(self.overline, "overline")
        self.overline.setWordWrap(True)
        self.body = QLabel("")
        theme.apply_role(self.body, "body")
        self.body.setWordWrap(True)
        column.addWidget(self.overline)
        column.addWidget(self.body)
        self.setStyleSheet(
            f"QFrame#quotedBlock {{ background-color: {C('surface-subtle')};"
            f" border: 1px solid {C('border')}; border-radius: {C('radius-input')}; }}"
        )

    def set_text(self, text: str) -> None:
        """Set the quoted body text."""
        self.body.setText(str(text))


class RoomChangesPage(QWidget):
    """Room change requests: search, pending table and the transfer inspector."""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-8"), S("space-8"), S("space-8"), S("space-8"))
        layout.setSpacing(S("space-6"))

        self.header = PageHeader(
            "Room change requests",
            "Review resident transfer justifications and reallocate rooms.",
        )
        self.refresh_btn = IconButton("refresh", "Reload the transfer requests")
        self.refresh_btn.clicked.connect(self.reload)
        self.header.actions.addWidget(self.refresh_btn)
        layout.addWidget(self.header)

        self.search = SearchField("Filter requests by student name or reason…")
        self.search.changed.connect(self.filter_table)
        # Legacy alias: the search box used to be a bare QLineEdit.
        self.search_input = self.search.edit
        layout.addWidget(self.search)

        self.error_banner = InlineBanner(
            "error",
            title="Transfer requests could not be loaded",
            message="The table is showing the last data received. Use Refresh to try again.",
        )
        self.error_banner.setVisible(False)
        layout.addWidget(self.error_banner)

        # ---------------------------------------------------- master-detail
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        table_card = QFrame()
        table_card.setObjectName("cardFrame")
        table_card.setMinimumWidth(400)
        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.table = QTableWidget(0, len(_COLUMNS))
        configure_table(self.table, _COLUMNS)
        _fit_columns(
            self.table,
            [
                QHeaderView.ResizeMode.Stretch,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.Stretch,
                QHeaderView.ResizeMode.ResizeToContents,
            ],
        )
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        self.stack.addWidget(self.table)

        self.empty_state = EmptyState(
            "arrow-left-right",
            "No pending transfer requests",
            "New requests appear here automatically; adjust the search for a specific student.",
        )
        self.stack.addWidget(self.empty_state)
        card_layout.addWidget(self.stack)
        self.splitter.addWidget(table_card)

        # ------------------------------------------------------ inspector
        self.panel = DetailPanel(340, 480, title="Transfer inspector")
        self.empty_panel = EmptyState(
            "arrow-left-right",
            "No request selected",
            "Select a request to compare the rooms and record a decision.",
        )
        self.panel.add_widget(self.empty_panel)

        self.inspector_scroll = QScrollArea()
        self.inspector_scroll.setWidgetResizable(True)
        self.inspector_scroll.setFrameShape(QFrame.Shape.NoFrame)
        inspector_body = QWidget()
        inspector = QVBoxLayout(inspector_body)
        inspector.setContentsMargins(0, 0, 0, 0)
        inspector.setSpacing(S("space-3"))

        # Resident identity.
        self.identity = QWidget()
        identity = QHBoxLayout(self.identity)
        identity.setContentsMargins(0, 0, 0, 0)
        identity.setSpacing(S("space-3"))
        self.avatar = Avatar("?", size=S("space-12"))
        identity.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignTop)
        identity_column = QVBoxLayout()
        identity_column.setSpacing(2)
        self.name_label = QLabel("—")
        theme.apply_role(self.name_label, "h3")
        self.name_label.setWordWrap(True)
        self.meta_label = QLabel("—")
        theme.apply_role(self.meta_label, "small")
        theme.enable_tabular(self.meta_label)
        self.meta_label.setWordWrap(True)
        identity_column.addWidget(self.name_label)
        identity_column.addWidget(self.meta_label)
        self.status_pill = StatusPill("pending", "Pending")
        identity_column.addWidget(self.status_pill, 0, Qt.AlignmentFlag.AlignLeft)
        identity.addLayout(identity_column, 1)
        inspector.addWidget(self.identity)

        # Current room › requested room.
        self.move_section = QWidget()
        move_layout = QVBoxLayout(self.move_section)
        move_layout.setContentsMargins(0, 0, 0, 0)
        move_layout.setSpacing(S("space-2"))
        move_overline = QLabel("ROOM MOVE")
        theme.apply_role(move_overline, "overline")
        move_layout.addWidget(move_overline)
        cards_row = QHBoxLayout()
        cards_row.setSpacing(S("space-2"))
        self.current_card, self.current_value, self.current_meta = self._room_card("Current room")
        cards_row.addWidget(self.current_card, 1)
        arrow = QLabel()
        arrow.setPixmap(get_pixmap("arrow-left-right", S("size-icon"), C("text-muted")))
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setToolTip("From the current room to the requested room")
        cards_row.addWidget(arrow, 0)
        self.target_card, self.target_value, self.target_meta = self._room_card("Requested room")
        self.target_bar = RoomOccupancyBar(0, 1)
        self.target_bar.setVisible(False)
        self.target_card.layout().addWidget(self.target_bar)
        cards_row.addWidget(self.target_card, 1)
        move_layout.addLayout(cards_row)
        inspector.addWidget(self.move_section)

        # Stated reason (quoted block).
        self.motive_block = _QuotedBlock("Stated reason for transfer")
        inspector.addWidget(self.motive_block)

        # Key facts.
        self.facts = KeyValueList()
        inspector.addWidget(self.facts)

        # ------------------------------------------------------- actions
        self.actions_row = QWidget()
        actions = QVBoxLayout(self.actions_row)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(S("space-2"))
        self.approve_btn = Button.accent("Approve & reassign", icon="check")
        self.approve_btn.clicked.connect(self.on_approve)
        self.reject_btn = Button.danger("Reject request", icon="x")
        self.reject_btn.clicked.connect(self.on_reject)
        actions.addWidget(self.approve_btn)
        actions.addWidget(self.reject_btn)
        self.delete_btn = Button("Delete request", "ghost", icon="trash")
        self._style_flat_danger(self.delete_btn)
        self.delete_btn.clicked.connect(self.on_delete)
        actions.addWidget(self.delete_btn)
        inspector.addWidget(self.actions_row)

        inspector.addStretch(1)
        self.inspector_scroll.setWidget(inspector_body)
        self.panel.body.addWidget(self.inspector_scroll, 1)

        self.detail_text = QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMinimumHeight(S("space-12"))
        self.detail_text.setMaximumHeight(S("space-12") * 2 + S("space-6"))
        self.detail_text.setPlaceholderText("Select a transfer request to inspect the full record…")
        theme.enable_tabular(self.detail_text)
        self.panel.body.addWidget(self.detail_text, 0)

        # Widgets revealed only while a request is selected.
        self._selection_widgets = [self.inspector_scroll, self.detail_text]

        self.splitter.addWidget(self.panel)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        layout.addWidget(self.splitter, 1)

        self._clear_selection_state()
        self.reload()

    # --------------------------------------------------------------- styling
    @staticmethod
    def _room_card(overline_text: str):
        """Room card: overline, room line and meta line (``(frame, value, meta)``)."""
        frame = QFrame()
        frame.setObjectName("roomCard")
        frame.setStyleSheet(
            f"QFrame#roomCard {{ background-color: {C('surface-subtle')};"
            f" border: 1px solid {C('border')}; border-radius: {C('radius-input')}; }}"
        )
        column = QVBoxLayout(frame)
        column.setContentsMargins(S("space-2"), S("space-2"), S("space-2"), S("space-2"))
        column.setSpacing(S("space-1"))
        overline = QLabel(str(overline_text).upper())
        theme.apply_role(overline, "overline")
        overline.setWordWrap(True)
        value = QLabel("—")
        theme.apply_role(value, "h3")
        theme.enable_tabular(value)
        value.setWordWrap(True)
        meta = QLabel("")
        theme.apply_role(meta, "small")
        meta.setWordWrap(True)
        column.addWidget(overline)
        column.addWidget(value)
        column.addWidget(meta)
        return frame, value, meta

    @staticmethod
    def _style_flat_danger(button: Button) -> None:
        """Flat danger variant for destructive actions (tokens only)."""
        button.setProperty("variant", "ghost")
        button.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {C('status-danger-ink')};"
            f" border: 1px solid transparent; border-radius: {C('radius-input')};"
            f" padding: 8px 12px; font-size: {C('fs-body')}; font-weight: {C('fw-semibold')}; }}"
            f"QPushButton:hover {{ background-color: {C('status-danger-bg')};"
            f" border-color: {C('status-danger-border')}; }}"
            f"QPushButton:pressed {{ background-color: {C('status-danger-bg')}; }}"
            f"QPushButton:focus {{ border: 2px solid {C('status-danger-ink')}; padding: 7px 11px; }}"
            f"QPushButton:disabled {{ background-color: {C('surface-subtle')}; color: {C('text-muted')};"
            f" border: 1px solid {C('border')}; padding: 8px 12px; }}"
        )

    def _show_selection(self, has_selection: bool) -> None:
        """Toggle between the EmptyState and the selected-request widgets."""
        self.empty_panel.setVisible(not has_selection)
        for widget in self._selection_widgets:
            widget.setVisible(has_selection)

    def _clear_selection_state(self):
        """No selected request: clear the inspector and the action guards."""
        self.detail_text.clear()
        self.target_bar.setVisible(False)
        self.approve_btn.setEnabled(False)
        self.approve_btn.setToolTip("Select a request to approve.")
        self.reject_btn.setEnabled(False)
        self.reject_btn.setToolTip("Select a request to record a rejection reason.")
        self.delete_btn.setEnabled(False)
        self.delete_btn.setToolTip("Select a request to delete it.")
        self._show_selection(False)

    # ------------------------------------------------------------------ data
    def filter_table(self, *_args):
        needle = self.search.text().lower().strip()
        for r in range(self.table.rowCount()):
            row_data = self.rows[r] if r < len(self.rows) else {}
            st = _normalise_student(row_data)
            name = f"{st.get('first_name', '')} {st.get('last_name', '')}".lower()
            reason = str(row_data.get("reason", "")).lower()
            self.table.setRowHidden(r, needle not in f"{name} {reason}")
        self._update_view_state()

    def _update_view_state(self):
        """Table/empty-state swap (never rebuilds the table)."""
        visible = sum(1 for r in range(self.table.rowCount()) if not self.table.isRowHidden(r))
        self.stack.setCurrentIndex(0 if visible else 1)

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
            st = _normalise_student(r)
            status = str(r.get("status", "pending"))
            status_kind, status_text = _status_meta(status)

            name_item = QTableWidgetItem(f"{st.get('first_name', '')} {st.get('last_name', '')}".strip())
            status_holder = _cell_widget(StatusPill(status_kind, status_text))
            status_item = _pill_item(status_text, status_holder)
            reason = str(r.get("reason", ""))
            reason_disp = (reason[:42] + "...") if len(reason) > 45 else reason
            reason_item = QTableWidgetItem(reason_disp)
            date_item = QTableWidgetItem(_fmt_date(r.get("created_at")))

            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, status_item)
            self.table.setItem(i, 2, reason_item)
            self.table.setItem(i, 3, date_item)
            self.table.setCellWidget(i, 1, status_holder)

        if restore_row >= 0:
            self.table.selectRow(restore_row)
        else:
            self._clear_selection_state()

        self.filter_table()

    def reload(self):
        try:
            resp = self.client.table("room_change_requests") \
                .select("*, students(first_name, last_name, gender, card_id)") \
                .eq("status", "pending").order("created_at", desc=True).execute()
            self.error_banner.setVisible(False)
            self.apply_live_data(resp.data or [])
        except Exception:
            self.error_banner.setVisible(True)

    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None


    # -------------------------------------------------------------- inspector
    def show_detail(self):
        r = self.selected()
        if not r:
            self._clear_selection_state()
            return

        self.approve_btn.setEnabled(True)
        self.approve_btn.setToolTip("")
        self.reject_btn.setEnabled(True)
        self.reject_btn.setToolTip("")
        self.delete_btn.setEnabled(True)
        self.delete_btn.setToolTip("")

        status = str(r.get("status", "pending"))
        status_kind, status_text = _status_meta(status)
        st = _normalise_student(r)
        name = f"{st.get('first_name', '')} {st.get('last_name', '')}".strip() or "Unnamed resident"
        gender = str(st.get("gender") or "").strip()

        # Resident identity.
        self.avatar.set_name(name)
        self.name_label.setText(name)
        meta_parts = [f"Card ID {st.get('card_id') or '—'}"]
        if gender:
            meta_parts.append(gender.capitalize())
        self.meta_label.setText(" · ".join(meta_parts))
        self.status_pill.set_kind(status_kind, status_text)

        # Rooms: the requested room keeps the single existing lookup.
        pref_id = r.get("preferred_room_id")
        room_data = None
        pref_info = "No specific room requested"
        if pref_id:
            try:
                room_data = self.client.table("rooms").select("block, number, floor").eq("id", pref_id).single().execute().data
                if room_data:
                    pref_info = f"Block {room_data['block']} — Room {room_data['number']} (Floor {room_data['floor']})"
                else:
                    room_data = None
            except Exception:
                room_data = None
                pref_info = f"Room ID: {pref_id}"

        current_id = r.get("current_room_id")
        if current_id:
            self.current_value.setText(_short_id(current_id))
            self.current_value.setToolTip(str(current_id))
            self.current_meta.setText("Room reference recorded when the request was filed.")
        else:
            self.current_value.setText("Not recorded")
            self.current_value.setToolTip("")
            self.current_meta.setText("The request carries no current-room reference.")

        if room_data:
            floor = room_data.get("floor")
            self.target_value.setText(
                f"Block {room_data.get('block', '—')} — Room {room_data.get('number', '—')}"
            )
            self.target_meta.setText(f"Floor {floor}" if floor is not None and str(floor) != "" else "")
            capacity = room_data.get("capacity")
            if capacity:
                self.target_bar.set_values(int(room_data.get("occupied") or 0), int(capacity))
                self.target_bar.setVisible(True)
            else:
                self.target_bar.setVisible(False)
        else:
            self.target_value.setText(pref_info)
            self.target_meta.setText(
                "The resident did not name a room." if not pref_id else "Room details could not be retrieved."
            )
            self.target_bar.setVisible(False)

        # Stated reason (quoted block).
        reason = str(r.get("reason") or "").strip()
        self.motive_block.set_text(f"“{reason}”" if reason else "No reason recorded.")

        # Key facts (raw data only).
        self.facts.set_rows([
            ("Submitted", _fmt_date(r.get("created_at"))),
            ("Last update", _fmt_stamp(r.get("updated_at"))),
            ("Decision note", str(r.get("decision_note") or "").strip() or "Awaiting decision"),
        ])

        # Plain-text record block (the desk reference for inquiries).
        self.detail_text.setPlainText(
            f"RESIDENT: {name}\n"
            f"Card ID: {st.get('card_id', '—')} | Gender: {st.get('gender', '—')}\n"
            f"Status: {status_text}\n"
            f"Preferred Room: {pref_info}\n"
            f"Submitted: {_fmt_stamp(r.get('created_at'))}\n\n"
            f"----------------------------------------\n"
            f"STATED REASON FOR TRANSFER:\n{reason}\n\n"
            f"Decision Note: {r.get('decision_note') or 'None'}"
        )
        self._show_selection(True)

    def on_row_double_clicked(self, row: int, col: int):
        r = self.selected()
        if r and r.get("students"):
            st_raw = r.get("students")
            if isinstance(st_raw, list) and st_raw:
                st = dict(st_raw[0])
            elif isinstance(st_raw, dict):
                st = dict(st_raw)
            else:
                st = {}
            roster_map = {}
            try:
                roster_map = official_lookup(self.client)
            except Exception:
                pass
            roster_match = roster_map.get(st.get("card_id"))
            dlg = StudentInfoCardDialog(self, st, roster_match)
            dlg.exec()

    # ------------------------------------------------------------- decisions
    def on_approve(self):
        r = self.selected()
        if not r:
            QMessageBox.information(self, "Select request", "Please select a transfer request from the table first.")
            return
        st = _normalise_student(r)
        gender = st.get("gender", "male")
        try:
            rooms = self.client.table("rooms").select("id, block, number, floor, capacity, gender") \
                .eq("gender", gender).order("block").order("number").execute().data or []
            occ = room_occupancy(self.client)
        except Exception as exc:
            QMessageBox.critical(self, "Network Error", f"Failed to fetch room availability: {exc}")
            return

        options = []
        for room in rooms:
            free = room["capacity"] - occ.get(room["id"], 0)
            if free > 0:
                options.append(f"Block {room['block']} — Room {room['number']} ({free}/{room['capacity']} free) | id={room['id']}")
            else:
                options.append(f"Block {room['block']} — Room {room['number']} (FULL) [LOCKED] | id={room['id']}")
        if not options:
            QMessageBox.warning(self, "No rooms", "No rooms configured for this gender.")
            return
        choice, ok = QInputDialog.getItem(self, "Allocate New Room", "Select target room for transfer:", options, 0, False)
        if not ok:
            return
        if "[LOCKED]" in choice:
            QMessageBox.warning(self, "Room Full", "This room is at capacity. Please select an available room.")
            return
        if "id=" not in choice:
            return
        room_id = choice.split("id=")[1].strip()
        try:
            self.client.rpc("approve_room_change", {"p_request": r["id"], "p_room": room_id}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        QMessageBox.information(self, "Approved", "Room transfer request approved and student reassigned.")
        try:
            self.reload()
        except Exception:
            pass

    def on_reject(self):
        r = self.selected()
        if not r:
            QMessageBox.information(self, "Select request", "Please select a transfer request from the table first.")
            return
        reason, ok = QInputDialog.getMultiLineText(self, "Reject Transfer", "Reason for refusal:")
        if not ok or not reason.strip():
            return
        try:
            self.client.rpc("reject_room_change", {"p_request": r["id"], "p_reason": reason.strip()}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        QMessageBox.information(self, "Rejected", "Room transfer request rejected.")
        try:
            self.reload()
        except Exception:
            pass

    def on_delete(self):
        r = self.selected()
        if not r:
            return
        st = _normalise_student(r)
        name = f"{st.get('first_name', '')} {st.get('last_name', '')}".strip() or "this resident"
        confirmed = ConfirmDialog.ask(
            self,
            "Delete transfer request",
            f"Permanently delete the room change request from {name}?\n\n"
            "This removes the resident justification and its decision history.",
            confirm_text="Delete request",
        )
        if not confirmed:
            return
        try:
            self.client.table("room_change_requests").delete().eq("id", r["id"]).execute()
            QMessageBox.information(self, "Deleted", "Room change request deleted successfully.")
            self.reload()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Failed to delete request: {exc}")


