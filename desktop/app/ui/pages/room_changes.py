"""RÉSIVO — Room change requests (visual layer only, docs/DESIGN.md §6–§7).

Master-detail page: a ``PageHeader``, the four-status ``SegmentedControl``
(Pending / Approved / Rejected / All with live counts), a ``SearchField``, the
transfer requests ``QTableWidget`` on the left and the 340/480 ``DetailPanel``
inspector on the right — resident identity with the ``StatusPill``, the
"current room › requested room" move visual (two room cards joined by the
``arrow-left-right`` icon, with a ``RoomOccupancyBar`` whenever the fetched room
carries capacity data), the stated reason as a quoted block, the rejection
record card (reason, decider, timestamp, rooms and original motive), the
submission facts, the guarded approve / reject / delete actions and the
plain-text record block.

The data layer keeps its view semantics: ``reload()`` fetches **all**
``room_change_requests`` (all statuses) with ``students(first_name, last_name,
gender, card_id)`` and the deciding staff member (``staff(full_name)`` through
``decided_by``), ``apply_live_data`` treats the complete all-status snapshot as
authoritative (deleted rows are removed, stale pending copies never undo a local
decision) and preserves the selected view, the search text and the selection by
id, ``show_detail`` keeps the single ``rooms`` lookup (``block, number, floor``
through ``preferred_room_id``) but serves it from a cache/background job instead
of blocking paint, ``on_approve`` keeps the gender-filtered ``rooms`` query +
``room_occupancy`` + the ``[LOCKED]`` guard + the ``approve_room_change`` RPC,
``on_reject`` keeps ``reject_room_change`` and its reason validation, and
``on_delete`` keeps the explicit delete (local removal, no refetch).

Network work for refresh and decisions runs through ``TaskRunner``; the
constructor performs one blocking first load so the initial paint is populated.
Approve/reject are guarded to pending rows; processed rows stay visible in their
status view (rejection never deletes the request).

Widget contracts kept for the tests
-----------------------------------
``table`` / ``rows`` / ``delete_btn`` / ``approve_btn`` / ``reject_btn`` /
``selected()`` / ``show_detail()`` / ``on_row_double_clicked()`` /
``on_approve()`` / ``on_reject()`` / ``on_delete()`` / ``filter_table()`` /
``apply_live_data()`` / ``reload()`` are unchanged; ``delete_btn`` is disabled
until a row is selected; ``detail_text`` is a direct child of the 340/480
``DetailPanel`` frame. Processed rows are hidden by the view/search filters
(``table.isRowHidden(row)``) rather than removed from ``all_rows``.
"""

from __future__ import annotations

import json

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
from ..tasks import TaskRunner, human_error
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
    SegmentedControl,
    StatusPill,
    configure_table,
)
from ..icons import get_pixmap
from ..infocard import StudentInfoCardDialog
from ..theme import C, S

# Table language: overline headers are uppercased by configure_table().
_COLUMNS = ["Resident", "Status", "Reason", "Submitted"]

# Live view keys -> segment labels (order = the four request views).
_VIEWS = [
    ("all", "All"),
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]
_VIEW_KEYS = {key for key, _label in _VIEWS}

# The exact rejection card title (the plain-text record keeps the uppercase
# desk-inquiry overline used by the applications page).
_REJECTION_TITLE = "Rejection reason (desk inquiry reference)"
_REJECTION_OVERLINE = "REJECTION REASON (Desk Inquiry Reference)"

# Empty-state copy per view (never reuse the pending copy under Rejected).
_EMPTY_COPY = {
    "pending": (
        "No pending transfer requests",
        "New requests appear here automatically; adjust the search for a specific student.",
    ),
    "approved": (
        "No approved transfer requests",
        "Approved requests stay here as the desk record for inquiries.",
    ),
    "rejected": (
        "No rejected transfer requests",
        "Rejected requests appear here with their recorded reason and decider.",
    ),
    "all": (
        "No transfer requests",
        "New requests appear here automatically; adjust the search for a specific student.",
    ),
}

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


def _normalise_staff(row: dict) -> dict:
    """``staff`` decider embed of a request row (list/dict/None safe)."""
    st = row.get("staff") or row.get("decided_by_staff") or {}
    if isinstance(st, list) and st:
        st = st[0]
    elif not isinstance(st, dict):
        st = {}
    return st


def _staff_name(row: dict) -> str:
    """Deciding staff member's full name, falling back to the raw id."""
    name = str(_normalise_staff(row).get("full_name") or "").strip()
    if name:
        return name
    decided_by = str(row.get("decided_by") or "").strip()
    return f"Unknown ({_short_id(decided_by)})" if decided_by else "Unknown"


def _row_signature(row: dict) -> str:
    """Stable signature of every field of one request row."""
    return json.dumps(row, sort_keys=True, default=str)


def _rpc_row(response) -> dict:
    """The single request row returned by a decision RPC.

    PostgREST may hand the composite row back as a dict or as a one-element
    list; any other shape is a broken response, not something to paper over.
    """
    data = getattr(response, "data", None)
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        raise RuntimeError("The server did not return the updated transfer request.")
    return dict(data)


def _fill_embeds(row: dict, fallback: dict | None) -> dict:
    """Keep joined embeds the RPC's bare table row does not carry."""
    if fallback:
        for key in ("students", "staff", "decided_by_staff"):
            if not row.get(key) and fallback.get(key):
                row[key] = fallback[key]
    return row


def _merge_decision_row(rows, decision_row: dict, fallback: dict | None = None):
    """Overlay the RPC-returned decision row on a snapshot by id.

    The RPC returns a bare ``room_change_requests`` row (no joins). The
    snapshot usually carries the ``students`` / ``staff`` embeds, so those are
    kept; when the snapshot lacks them, the locally held request supplies them.
    """
    target = str(decision_row.get("id"))
    overlay = dict(decision_row)
    for key in ("students", "staff", "decided_by_staff"):
        if not overlay.get(key):
            overlay.pop(key, None)

    merged: list[dict] = []
    found = False
    for raw in rows or []:
        row = dict(raw)
        if str(row.get("id")) == target:
            found = True
            row = _fill_embeds(row, fallback)
            row.update(overlay)
        merged.append(row)
    if not found:
        row = _fill_embeds(dict(fallback or {}), None)
        row.update(overlay)
        merged.append(row)
    return merged


def _guard_decision_regression(row: dict, previous: dict | None) -> dict:
    """Never let a stale ``pending`` snapshot overwrite a local decision."""
    if not previous:
        return row
    old_status = str(previous.get("status") or "")
    new_status = str(row.get("status") or "pending")
    if old_status in ("approved", "rejected") and new_status == "pending":
        row = dict(row)
        for field in ("status", "decision_note", "decided_by", "decided_at",
                      "updated_at", "staff"):
            if field in previous:
                row[field] = previous[field]
    return row


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
    """Room change requests: status views, search and the transfer inspector."""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.all_rows: list[dict] = []
        self.rows: list[dict] = []
        self.filter_mode = "pending"
        # Differential-redraw index: request id -> field signature of the rows
        # currently held (decision_note / decided_at / decided_by included).
        self._row_index: dict[str, str] = {}
        # Background I/O for refresh/decisions and the lazy room-detail lookup.
        self._initializing = True
        self._working = False
        self._room_cache: dict[str, dict | None] = {}
        # Successfully deleted request ids: a permanently deleted row must
        # never come back from a stale in-flight or replicated snapshot.
        self._deleted_ids: set[str] = set()
        self.tasks = TaskRunner(self)

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

        # ------------------------------------------------------------ toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(S("space-3"))

        self.segments = SegmentedControl(_VIEWS)
        self.btn_all = self.segments.buttons["all"]
        self.btn_pending = self.segments.buttons["pending"]
        self.btn_approved = self.segments.buttons["approved"]
        self.btn_rejected = self.segments.buttons["rejected"]
        self.segments.set_current("pending")
        self.segments.changed.connect(self.set_filter)
        toolbar.addWidget(self.segments)

        self.search = SearchField(
            "Filter requests by student, card ID, reason or decision note…"
        )
        self.search.changed.connect(self.filter_table)
        # Legacy alias: the search box used to be a bare QLineEdit.
        self.search_input = self.search.edit
        toolbar.addWidget(self.search, 1)
        layout.addLayout(toolbar)

        self.error_banner = InlineBanner(
            "error",
            title="Transfer requests could not be loaded",
            message="The table is showing the last data received. Use Refresh to try again.",
        )
        self.error_banner.setVisible(False)
        layout.addWidget(self.error_banner)

        # Inline busy/result state: no modal progress dialog, no traceback.
        self.busy_banner = InlineBanner("info", title="Working…", message="")
        self.busy_banner.setVisible(False)
        layout.addWidget(self.busy_banner)

        self.action_banner = InlineBanner("info", title="", message="")
        self.action_banner.setVisible(False)
        layout.addWidget(self.action_banner)

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
            _EMPTY_COPY["pending"][0],
            _EMPTY_COPY["pending"][1],
        )
        # EmptyState doesn't expose its label widgets; keep references so the
        # copy can follow the active status view without rebuilding the page.
        empty_labels = self.empty_state.findChildren(QLabel)
        self.empty_title_label = next(
            (label for label in empty_labels if label.text() == _EMPTY_COPY["pending"][0]),
            None,
        )
        self.empty_message_label = next(
            (label for label in empty_labels if label.text() == _EMPTY_COPY["pending"][1]),
            None,
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

        # Rejection record: same tinted card style as the applications page.
        self.rejection_card = QFrame()
        self.rejection_card.setObjectName("recordBlock")
        rejection = QVBoxLayout(self.rejection_card)
        rejection.setContentsMargins(S("space-3"), S("space-3"), S("space-3"), S("space-3"))
        rejection.setSpacing(S("space-2"))
        rejection_head = QHBoxLayout()
        rejection_head.setSpacing(S("space-2"))
        self.rejection_overline = QLabel(_REJECTION_TITLE)
        theme.apply_role(self.rejection_overline, "overline")
        self.rejection_overline.setWordWrap(True)
        self.rejection_pill = StatusPill("danger", "Rejected")
        rejection_head.addWidget(self.rejection_overline, 1)
        rejection_head.addWidget(self.rejection_pill, 0, Qt.AlignmentFlag.AlignTop)
        self.rejection_body = QLabel("")
        theme.apply_role(self.rejection_body, "body")
        self.rejection_body.setWordWrap(True)
        self.rejection_meta = QLabel("")
        theme.apply_role(self.rejection_meta, "small")
        self.rejection_meta.setWordWrap(True)
        self.rejection_student_label = QLabel("")
        theme.apply_role(self.rejection_student_label, "small")
        self.rejection_student_label.setWordWrap(True)
        self.rejection_rooms_label = QLabel("")
        theme.apply_role(self.rejection_rooms_label, "small")
        self.rejection_rooms_label.setWordWrap(True)
        self.rejection_motive_label = QLabel("")
        theme.apply_role(self.rejection_motive_label, "small")
        self.rejection_motive_label.setWordWrap(True)
        rejection.addLayout(rejection_head)
        rejection.addWidget(self.rejection_body)
        rejection.addWidget(self.rejection_meta)
        rejection.addWidget(self.rejection_student_label)
        rejection.addWidget(self.rejection_rooms_label)
        rejection.addWidget(self.rejection_motive_label)
        rejection_tokens = theme.status_tokens("danger")
        self.rejection_card.setStyleSheet(
            f"QFrame#recordBlock {{ background-color: {rejection_tokens['bg']};"
            f" border: 1px solid {rejection_tokens['border']};"
            f" border-radius: {C('radius-input')}; }}"
        )
        self.rejection_card.setVisible(False)
        inspector.addWidget(self.rejection_card)

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
        self._initializing = False

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
        self.rejection_card.setVisible(False)
        self.approve_btn.setEnabled(False)
        self.approve_btn.setToolTip("Select a request to approve.")
        self.reject_btn.setEnabled(False)
        self.reject_btn.setToolTip("Select a request to record a rejection reason.")
        self.delete_btn.setEnabled(False)
        self.delete_btn.setToolTip("Select a request to delete it.")
        self._show_selection(False)

    # ------------------------------------------------------------------ data
    def set_filter(self, mode: str):
        """Switch the status view (Pending / Approved / Rejected / All)."""
        self.filter_mode = mode if mode in _VIEW_KEYS else "pending"
        self.segments.set_current(self.filter_mode)
        self.filter_table()

    def filter_table(self, *_args):
        """Apply the status view + search filter, preserving the selection by id.

        Processed rows are hidden, never removed from ``rows`` / ``all_rows``:
        a rejected request remains in the local data and is listed again as soon
        as the Rejected or All view is selected.
        """
        needle = self.search.text().lower().strip()
        selected_row = self.table.currentRow()
        selected_visible = False
        for r in range(self.table.rowCount()):
            row_data = self.rows[r] if r < len(self.rows) else {}
            status = str(row_data.get("status") or "pending")
            in_view = (
                self.filter_mode == "all"
                or status == self.filter_mode
            )
            st = _normalise_student(row_data)
            name = f"{st.get('first_name', '')} {st.get('last_name', '')}".lower()
            card_id = str(st.get("card_id") or "").lower()
            reason = str(row_data.get("reason") or "").lower()
            decision_note = str(row_data.get("decision_note") or "").lower()
            haystack = f"{name} {card_id} {reason} {decision_note}"
            matches = not needle or needle in haystack
            visible = in_view and matches
            self.table.setRowHidden(r, not visible)
            if r == selected_row and visible:
                selected_visible = True

        if selected_row >= 0 and not selected_visible:
            # The selected request is not part of this view/search: clear the
            # stale current index so the inspector never shows a hidden row.
            self.table.clearSelection()
            self.table.setCurrentCell(-1, -1)
            self._clear_selection_state()

        self._update_view_state()

    def visible_rows(self) -> list[dict]:
        """Rows currently listed by the selected view + search (read-only)."""
        return [
            row for index, row in enumerate(self.rows)
            if index < self.table.rowCount() and not self.table.isRowHidden(index)
        ]

    def _update_view_state(self):
        """Table/empty-state swap + per-view copy and counts (never rebuilds)."""
        visible = sum(1 for r in range(self.table.rowCount()) if not self.table.isRowHidden(r))
        self.stack.setCurrentIndex(0 if visible else 1)
        title, message = _EMPTY_COPY.get(self.filter_mode, _EMPTY_COPY["pending"])
        if self.empty_title_label is not None:
            self.empty_title_label.setText(title)
        if self.empty_message_label is not None:
            self.empty_message_label.setText(message)
        self._update_segment_counts()

    def _update_segment_counts(self):
        counts = {key: 0 for key, _label in _VIEWS}
        for row in self.all_rows:
            status = str(row.get("status") or "")
            counts["all"] += 1
            if status in ("pending", "approved", "rejected"):
                counts[status] += 1
        for key, value in counts.items():
            self.segments.set_count(key, value)

    @staticmethod
    def _index(rows) -> dict[str, str]:
        """``{request id: field signature}`` for the differential redraw."""
        return {str(row.get("id")): _row_signature(row) for row in rows}

    def _without_deleted(self, rows) -> list[dict]:
        """Drop rows deleted in this session, even from a stale snapshot."""
        if not self._deleted_ids:
            return list(rows or [])
        return [
            row for row in (rows or [])
            if str(row.get("id")) not in self._deleted_ids
        ]

    def apply_live_data(self, rows: list[dict]):
        """Apply the complete all-status live snapshot, preserving the view.

        The snapshot is authoritative for membership: a local row absent from
        it was deleted elsewhere and is removed (never left as a ghost). A
        stale ``pending`` copy of a locally approved/rejected request keeps the
        local decision. The view key, the search text and the selected request
        id are all preserved.
        """
        current_by_id = {str(row.get("id")): row for row in self.all_rows}
        incoming = [
            _guard_decision_regression(
                dict(row), current_by_id.get(str(row.get("id")))
            )
            for row in self._without_deleted(rows)
        ]

        index = self._index(incoming)
        if index == self._row_index and len(incoming) == len(self.rows):
            return

        selected = self.selected()
        selected_id = selected.get("id") if selected else None
        self._row_index = index
        self.all_rows = incoming
        self.rows = incoming
        self._render_table(selected_id)
        self.filter_table()

    def _render_table(self, selected_id=None):
        """Rebuild the table from ``rows`` and restore the selection by id."""
        self.table.setRowCount(len(self.rows))
        restore_row = -1

        for i, r in enumerate(self.rows):
            if selected_id is not None and str(r.get("id")) == str(selected_id):
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
            # The selected request vanished: clear the stale current index too,
            # otherwise selected() would resolve to whatever row took its place.
            self.table.clearSelection()
            self.table.setCurrentCell(-1, -1)
            self._clear_selection_state()

    # ------------------------------------------------------- background data
    def _fetch_requests(self):
        """Network-only all-status request snapshot (worker thread)."""
        resp = self.client.table("room_change_requests") \
            .select(
                "*, students(first_name, last_name, gender, card_id),"
                " staff(full_name)"
            ) \
            .order("created_at", desc=True).execute()
        return list(resp.data or [])

    def _apply_snapshot(self, rows):
        """Apply fetched rows on the GUI thread, preserving search/selection.

        A stale read that still reports ``pending`` for a request decided in
        this session never rolls the local status back.
        """
        selected = self.selected()
        selected_id = selected.get("id") if selected else None
        current_by_id = {str(row.get("id")): row for row in self.all_rows}
        self.error_banner.setVisible(False)
        self.all_rows = [
            _guard_decision_regression(
                dict(row), current_by_id.get(str(row.get("id")))
            )
            for row in self._without_deleted(rows)
        ]
        self.rows = self.all_rows
        self._row_index = self._index(self.all_rows)
        self._render_table(selected_id)
        self.filter_table()

    def _reload_blocking(self):
        """Initial load only: the constructor keeps its synchronous first data."""
        try:
            self._apply_snapshot(self._fetch_requests())
        except Exception:
            self.error_banner.setVisible(True)

    def reload(self):
        """Reload transfer requests.

        The constructor takes the blocking path so the first paint is populated;
        every later call (Refresh button, tests, live code) fetches on the thread
        pool and applies the snapshot on the GUI thread.
        """
        if self._initializing:
            self._reload_blocking()
        else:
            self._reload_async()

    def _reload_async(self):
        if self._working:
            return
        self._begin_working("Refreshing transfer requests…")
        started = self.tasks.run(
            "reload",
            self._fetch_requests,
            on_success=self._on_reload_success,
            on_failed=self._on_reload_failed,
            on_finished=self._end_working,
        )
        if not started:
            self._end_working()

    def _on_reload_success(self, rows):
        self._apply_snapshot(rows)

    def _on_reload_failed(self, message: str):
        self.error_banner.set_title("Transfer requests could not be refreshed")
        self.error_banner.set_message(
            f"{message} The table is showing the last data received."
        )
        self.error_banner.setVisible(True)

    # ---------------------------------------------------------- busy state
    def _begin_working(self, message: str):
        self._working = True
        self.busy_banner.set_kind("info")
        self.busy_banner.set_title("Working…")
        self.busy_banner.set_message(message)
        self.busy_banner.setVisible(True)
        self.action_banner.setVisible(False)
        self._set_action_controls_enabled(False)

    def _end_working(self):
        if not self._working:
            return
        self._working = False
        self.busy_banner.setVisible(False)
        self._set_action_controls_enabled(True)

    def _set_action_controls_enabled(self, enabled: bool):
        if enabled:
            self.refresh_btn.setEnabled(True)
            if self.selected():
                self.show_detail()
            else:
                self._clear_selection_state()
        else:
            self.approve_btn.setEnabled(False)
            self.reject_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)

    def _show_action_success(self, message: str):
        self.action_banner.set_kind("success")
        self.action_banner.set_title("Done")
        self.action_banner.set_message(message)
        self.action_banner.setVisible(True)

    def _show_action_warning(self, message: str):
        self.action_banner.set_kind("warning")
        self.action_banner.set_title("Action unavailable")
        self.action_banner.set_message(message)
        self.action_banner.setVisible(True)

    def _on_action_failed(self, message: str):
        self.action_banner.set_kind("error")
        self.action_banner.set_title("Action failed")
        self.action_banner.set_message(f"The request could not be completed: {message}")
        self.action_banner.setVisible(True)
        self._end_working()

    # ------------------------------------------------------- worker payloads
    def _load_rooms(self, gender):
        rooms = self.client.table("rooms").select(
            "id, block, number, floor, capacity, gender"
        ).eq("gender", gender).order("block").order("number").execute().data or []
        return list(rooms), room_occupancy(self.client)

    def _fetch_after_decision(self):
        """Best-effort follow-up snapshot for a committed decision.

        The decision RPC has already succeeded, so a read failure is reported
        alongside the returned row instead of making the whole action look
        failed (which would also throw the authoritative RPC row away).
        """
        try:
            return self._fetch_requests(), None
        except Exception as exc:  # noqa: BLE001 - the decision is already saved
            return None, human_error(exc)

    def _approve_rpc(self, request_id, room_id):
        """Run the approval RPC; return its row plus the follow-up snapshot."""
        response = self.client.rpc(
            "approve_room_change", {"p_request": request_id, "p_room": room_id}
        ).execute()
        decision_row = _rpc_row(response)
        rows, refresh_error = self._fetch_after_decision()
        return decision_row, rows, refresh_error

    def _reject_rpc(self, request_id, reason):
        """Run the rejection RPC; return its row plus the follow-up snapshot."""
        response = self.client.rpc(
            "reject_room_change", {"p_request": request_id, "p_reason": reason}
        ).execute()
        decision_row = _rpc_row(response)
        rows, refresh_error = self._fetch_after_decision()
        return decision_row, rows, refresh_error

    def _delete_rpc(self, request_id):
        """Delete the request; the local row is removed without a refetch.

        PostgREST represents deletes, so ``data == []`` means no row matched:
        the request was already deleted elsewhere and this is not a success.
        """
        response = (
            self.client.table("room_change_requests")
            .delete()
            .eq("id", request_id)
            .execute()
        )
        data = getattr(response, "data", None)
        if data is None:
            # No representation means the server did not confirm which row was
            # removed.  Reporting success here would hide a no-op delete.
            raise RuntimeError(
                "The server did not confirm the deletion. Refresh and try again."
            )
        return request_id, list(data)

    def _fetch_room(self, room_id):
        """Optional preferred-room details; failure falls back to the room id."""
        try:
            return self.client.table("rooms").select("block, number, floor") \
                .eq("id", room_id).single().execute().data
        except Exception:
            return None

    def _request_room_details(self, room_id: str):
        key = f"room:{room_id}"
        if self.tasks.is_busy(key):
            return
        self.tasks.run(
            key,
            lambda: self._fetch_room(room_id),
            on_success=lambda data, rid=room_id: self._on_room_details(rid, data),
            on_failed=lambda _message, rid=room_id: self._on_room_details(rid, None),
        )

    def _on_room_details(self, room_id, room_data):
        self._room_cache[room_id] = room_data
        current = self.selected()
        if current and str(current.get("preferred_room_id")) == str(room_id):
            # Repaint only if the same request is still selected.
            self.show_detail()

    def _show_info_card(self, student: dict, roster: dict):
        roster_match = (roster or {}).get(student.get("card_id"))
        dlg = StudentInfoCardDialog(self, student, roster_match)
        dlg.exec()

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
        if status != "pending":
            # Processed requests stay inspectable but cannot be decided again.
            self.approve_btn.setEnabled(False)
            self.approve_btn.setToolTip("Only pending requests can be approved.")
            self.reject_btn.setEnabled(False)
            self.reject_btn.setToolTip("Only pending requests can be rejected.")
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

        # Rooms: requested-room details come from the cache; a miss schedules a
        # background lookup so selecting a row never blocks on the network.
        pref_id = r.get("preferred_room_id")
        room_data = None
        pref_info = "No specific room requested"
        if pref_id:
            pref_key = str(pref_id)
            if pref_key in self._room_cache:
                room_data = self._room_cache[pref_key]
                if room_data:
                    pref_info = f"Block {room_data['block']} — Room {room_data['number']} (Floor {room_data['floor']})"
                else:
                    # Cached lookup failed: keep the raw room reference.
                    pref_info = f"Room ID: {pref_id}"
            else:
                pref_info = f"Room ID: {pref_id}"
                self._request_room_details(pref_key)

        current_id = r.get("current_room_id")
        current_info = f"Room ID: {current_id}" if current_id else "Not recorded"
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

        # Rejection record (desk inquiry reference) — rejected rows only.
        decider_name = _staff_name(r)
        decided_at = _fmt_stamp(r.get("decided_at"))
        decision_note = str(r.get("decision_note") or "").strip()
        is_rejected = status == "rejected"
        self.rejection_card.setVisible(is_rejected)
        if is_rejected:
            self.rejection_body.setText(f"“{decision_note or 'No reason recorded'}”")
            self.rejection_meta.setText(f"Decided by {decider_name} · {decided_at}")
            self.rejection_student_label.setText(
                f"Student: {name} — Card ID {st.get('card_id') or '—'}"
            )
            self.rejection_rooms_label.setText(
                f"Current room: {current_info} → Requested room: {pref_info}"
            )
            self.rejection_motive_label.setText(
                f"Student's original motive: “{reason or 'No reason recorded'}”"
            )

        # Key facts (raw data only).
        facts = [
            ("Submitted", _fmt_date(r.get("created_at"))),
            ("Last update", _fmt_stamp(r.get("updated_at"))),
        ]
        if status == "pending":
            facts.append(("Decision note", decision_note or "Awaiting decision"))
        else:
            facts.append(("Decision note", decision_note or "—"))
            facts.append(("Decided by", decider_name))
            facts.append(("Decided", decided_at))
        self.facts.set_rows(facts)

        # Plain-text record block (the desk reference for inquiries).
        notes = (
            f"RESIDENT: {name}\n"
            f"Card ID: {st.get('card_id', '—')} | Gender: {st.get('gender', '—')}\n"
            f"Status: {status_text}\n"
            f"Preferred Room: {pref_info}\n"
            f"Submitted: {_fmt_stamp(r.get('created_at'))}\n\n"
            f"----------------------------------------\n"
            f"STATED REASON FOR TRANSFER:\n{reason}\n\n"
            f"Decision Note: {r.get('decision_note') or 'None'}\n"
            f"Decided By: {decider_name}\n"
            f"Decided At: {decided_at}"
        )
        if is_rejected:
            notes += (
                f"\n\n{_REJECTION_OVERLINE}\n"
                f"Reason: {decision_note or 'No reason recorded'}\n"
                f"Decided by: {decider_name}\n"
                f"Decided at: {decided_at}\n"
                f"Student: {name} | Card ID: {st.get('card_id') or '—'}\n"
                f"Current room: {current_info} | Requested room: {pref_info}\n"
                f"Student's original motive: {reason or 'No reason recorded'}"
            )
        self.detail_text.setPlainText(notes)
        if self._working:
            # Never re-enable action controls mid-flight (selection changes and
            # live-sync repaints both call this method).
            self.approve_btn.setEnabled(False)
            self.reject_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
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
            # The roster lookup is optional data too: fetch it off-thread and
            # only then open the (unchanged) info card on the GUI thread.
            student = dict(st)
            key = f"roster:{student.get('card_id') or id(student)}"
            if self.tasks.is_busy(key):
                return
            self.tasks.run(
                key,
                lambda: official_lookup(self.client),
                on_success=lambda roster, s=student: self._show_info_card(s, roster),
                on_failed=lambda _message, s=student: self._show_info_card(s, {}),
            )

    # ------------------------------------------------------------- decisions
    def _require_pending(self, request: dict) -> bool:
        """Approve/reject only apply to pending requests (status views are read-only)."""
        if str(request.get("status", "pending")) == "pending":
            return True
        self._show_action_warning(
            "Only pending transfer requests can be approved or rejected."
        )
        return False

    def _find_row(self, request_id) -> dict | None:
        """Locally held request by id (never limited to the visible view)."""
        target = str(request_id)
        return next(
            (row for row in self.all_rows if str(row.get("id")) == target),
            None,
        )

    def _select_by_id(self, request_id) -> bool:
        """Select a request by id in the current view, if it is listed."""
        target = str(request_id)
        for index, row in enumerate(self.rows):
            if str(row.get("id")) == target:
                self.table.setCurrentCell(index, 0)
                self.table.selectRow(index)
                self.show_detail()
                return True
        return False

    def on_approve(self):
        if self._working:
            return
        r = self.selected()
        if not r:
            QMessageBox.information(self, "Select request", "Please select a transfer request from the table first.")
            return
        if not self._require_pending(r):
            return
        request = dict(r)
        gender = _normalise_student(request).get("gender", "male")
        self._begin_working("Loading available rooms…")
        started = self.tasks.run(
            "approve-rooms",
            lambda: self._load_rooms(gender),
            on_success=lambda result: self._on_approve_rooms_loaded(result, request),
            on_failed=self._on_action_failed,
            on_finished=self._finish_approve_rooms_stage,
        )
        if not started:
            self._end_working()

    def _finish_approve_rooms_stage(self):
        """Restore controls only if the approval RPC stage did not start."""
        if not self.tasks.is_busy("approve"):
            self._end_working()

    def _on_approve_rooms_loaded(self, result, request):
        rooms, occ = result
        options = []
        for room in rooms:
            free = room["capacity"] - occ.get(room["id"], 0)
            if free > 0:
                options.append(f"Block {room['block']} — Room {room['number']} ({free}/{room['capacity']} free) | id={room['id']}")
            else:
                options.append(f"Block {room['block']} — Room {room['number']} (FULL) [LOCKED] | id={room['id']}")
        if not options:
            QMessageBox.warning(self, "No rooms", "No rooms configured for this gender.")
            self._end_working()
            return
        choice, ok = QInputDialog.getItem(self, "Allocate New Room", "Select target room for transfer:", options, 0, False)
        if not ok:
            self._end_working()
            return
        if "[LOCKED]" in choice:
            QMessageBox.warning(self, "Room Full", "This room is at capacity. Please select an available room.")
            self._end_working()
            return
        if "id=" not in choice:
            self._end_working()
            return
        room_id = choice.split("id=")[1].strip()

        self._begin_working("Approving transfer…")
        request_id = request["id"]
        started = self.tasks.run(
            "approve",
            lambda: self._approve_rpc(request_id, room_id),
            on_success=lambda result: self._on_approve_success(result, request),
            on_failed=self._on_action_failed,
            on_finished=self._end_working,
        )
        if not started:
            self._end_working()

    def _apply_decision_result(self, result, request=None):
        """Apply the RPC row as the source of truth over the follow-up snapshot.

        Returns the follow-up read error, if any: the RPC row is still applied
        locally so a committed decision is never presented as a failure.
        """
        decision_row, rows, refresh_error = result
        fallback = self._find_row(decision_row.get("id")) or request
        if rows is None:
            rows = self.all_rows
        self._apply_snapshot(_merge_decision_row(rows, decision_row, fallback))
        return refresh_error

    def _show_decision_refresh_warning(self, refresh_error):
        """The decision is saved; only its list refresh failed."""
        self.error_banner.set_title("Decision saved; list not refreshed")
        self.error_banner.set_message(
            f"The decision was saved, but the request list could not be "
            f"refreshed: {refresh_error}. The next live sync will try again."
        )
        self.error_banner.setVisible(True)

    def _on_approve_success(self, result, request=None):
        refresh_error = self._apply_decision_result(result, request)
        if request is not None:
            request_id = request.get("id")
            found = self._find_row(request_id)
            if found is not None and str(found.get("status")) == "approved":
                # Show the processed request in its status view; it is never
                # removed from the local data.
                self.set_filter("approved")
                self._select_by_id(request_id)
        self._show_action_success("Room transfer request approved and student reassigned.")
        if refresh_error:
            self._show_decision_refresh_warning(refresh_error)

    def on_reject(self):
        if self._working:
            return
        r = self.selected()
        if not r:
            QMessageBox.information(self, "Select request", "Please select a transfer request from the table first.")
            return
        if not self._require_pending(r):
            return
        reason, ok = QInputDialog.getMultiLineText(self, "Reject Transfer", "Reason for refusal:")
        if not ok:
            return
        if not reason.strip():
            self._show_action_warning(
                "A rejection reason is required before the request can be rejected."
            )
            return

        request = dict(r)
        reason = reason.strip()
        self._begin_working("Saving rejection…")
        started = self.tasks.run(
            "reject",
            lambda: self._reject_rpc(request["id"], reason),
            on_success=lambda result: self._on_reject_success(result, request),
            on_failed=self._on_action_failed,
            on_finished=self._end_working,
        )
        if not started:
            self._end_working()

    def _on_reject_success(self, result, request=None):
        refresh_error = self._apply_decision_result(result, request)
        request_id = request.get("id") if request else None
        found = self._find_row(request_id) if request_id is not None else None
        if found is not None and str(found.get("status")) == "rejected":
            # The row stays in all_rows (never deleted); show it immediately in
            # the Rejected view with its recorded reason.
            self.set_filter("rejected")
            self._select_by_id(request_id)
            self._show_action_success(
                "Request rejected. View it in the Rejected tab."
            )
        else:
            # A stale read replica still reports the pre-decision state: keep
            # the current view/selection and let the next refresh update it.
            if request_id is not None:
                self._select_by_id(request_id)
            self._show_action_success("Room transfer request rejected.")
        if refresh_error:
            self._show_decision_refresh_warning(refresh_error)

    def on_delete(self):
        if self._working:
            return
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

        request = dict(r)
        self._begin_working("Deleting request…")
        started = self.tasks.run(
            "delete",
            lambda: self._delete_rpc(request["id"]),
            on_success=self._on_delete_success,
            on_failed=self._on_action_failed,
            on_finished=self._end_working,
        )
        if not started:
            self._end_working()

    def _on_delete_success(self, result):
        request_id, removed = result
        deleted_id = str(request_id)
        # Tombstone first: an in-flight or replicated snapshot may still carry
        # the row, and it must not resurrect after this successful delete.
        self._deleted_ids.add(deleted_id)
        # No refetch: a stale read could re-seed the row that was just deleted.
        self._apply_snapshot([
            row for row in self.all_rows
            if str(row.get("id")) != deleted_id
        ])
        if removed == []:
            # The server matched no row: it was already deleted elsewhere.
            self.action_banner.set_kind("warning")
            self.action_banner.set_title("Already removed")
            self.action_banner.set_message(
                "This transfer request no longer exists on the server. "
                "The table has been updated."
            )
            self.action_banner.setVisible(True)
            return
        self._show_action_success("Room change request deleted successfully.")


