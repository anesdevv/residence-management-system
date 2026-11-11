"""RÉSIVO — Applications & housing (visual layer only, docs/DESIGN.md §6–§7).

Master-detail page: a ``SegmentedControl`` over the four application views with
live counts, a ``SearchField``, the applications ``QTableWidget`` on the left and
a ``DetailPanel`` inspector on the right (identity, roster badge, submitted data,
decisions, the rejection / desk-inquiry record block and the plain-text notes).

The data layer keeps its view semantics: the four views keep their exact
meanings (pending = ``pending``, approved = ``active``, rejected = ``rejected``,
all = everything), ``reload()`` keeps its query chain, ``on_approve`` keeps the
gender-filtered ``rooms`` query + ``room_occupancy`` + ``approve_student`` RPC,
``on_reject`` keeps ``reject_student`` and its reason validation, ``on_delete``
uses ``delete_student`` (the authenticated RPC, never a raw table delete), and
``official_lookup`` stays the module-level patch point
(``desktop.app.ui.pages.pending.official_lookup``).

Network work does not run on the GUI thread: every refresh/decision handler
starts a ``TaskRunner`` job and applies its snapshot in the queued success
callback.  The constructor performs one blocking first load so the initial paint
is populated; all later ``reload()`` calls are asynchronous.

Widget contracts kept for the tests
-----------------------------------
``btn_pending`` / ``btn_approved`` / ``btn_rejected`` / ``btn_all`` are the
``SegmentedControl`` segments (checkable ``QPushButton``s wired to
``set_filter``); ``table`` has column 0 = card ID and column 3 contains
``Pending`` / ``Approved`` / ``Rejected``; ``delete_btn`` is disabled with the
"Pending applications cannot be deleted" tooltip for pending applications and
enabled with an empty tooltip otherwise; ``approve_btn`` is disabled with an
"already approved" tooltip for approved students; ``reject_btn.text()`` is
``"Edit Rejection Reason"`` for rejected students; ``detail_text`` (read-only
``QPlainTextEdit``) is a direct child of the 340/460 ``DetailPanel`` frame and
its text still contains ``REJECTION REASON (Desk Inquiry Reference)`` plus the
reason and the review timestamp. ``apply_live_data`` never touches the filter,
the search field or the selection: it diffs the incoming pending slice by id and
only repaints the views whose data actually changed.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QDialog,
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

from ...client import (
    get_cached_residence_settings,
    has_gender_mismatch,
    official_lookup,
    room_occupancy,
)
from ...timeouts import execute_network_call

try:
    from i18n import format_date, format_number, format_percent, t, tn
except ImportError:
    from desktop.i18n import format_date, format_number, format_percent, t, tn

from .. import theme
from ..tasks import GatherResult, TaskRunner, human_error
from ..components import (
    StatusPillDelegate,
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
    RosterMatchBadge,
    SearchField,
    SegmentedControl,
    StatusPill,
    configure_table,
)
from ..infocard import StudentInfoCardDialog
from ..icons import get_pixmap
from ..theme import C, S

# Live view keys -> segment labels (order = the four application views).
def _views() -> list[tuple[str, str]]:
    return [
        ("all", t("pending.tab_all")),
        ("pending", t("pending.tab_pending")),
        ("approved", t("pending.tab_approved")),
        ("rejected", t("pending.tab_rejected")),
    ]

_VIEWS = _views()

# Table language: overline headers are uppercased by configure_table().
def _columns() -> list[str]:
    return [
        t("pending.col_card_id"),
        t("pending.col_student"),
        t("pending.col_university"),
        t("pending.col_status"),
        t("pending.col_roster"),
    ]

_COLUMNS = _columns()

def _status_meta(raw_status: str) -> tuple[str, str]:
    """``(status kind, status word)`` for any student status value."""
    kinds = {
        "active": ("ok", t("status.approved")),
        "rejected": ("danger", t("status.rejected")),
        "pending": ("pending", t("status.pending")),
    }
    return kinds.get(raw_status, ("pending", t("status.pending")))

# The exact rejection overline asserted by the tests: it must stay inside
# detail_text together with the reason and the review timestamp.
def _rejection_overline() -> str:
    return t("pending.rejection_overline")

_REJECTION_OVERLINE = "REJECTION REASON (Desk Inquiry Reference)"


def _rpc_row(response) -> dict:
    """The single student row returned by an approve/reject RPC.

    PostgREST may hand the composite row back as a dict or a one-element list;
    any other shape is a broken response, not something to paper over.
    """
    data = getattr(response, "data", None)
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        raise RuntimeError("The server did not return the updated student record.")
    return dict(data)


def _guard_decision_regression(row: dict, previous: dict | None) -> dict:
    """Never let a stale ``pending`` row overwrite a local decision.

    LiveSync can deliver a tick that was read before the approve/reject RPC
    committed.  The RPC result is authoritative, so a pending copy for a student
    this session already decided keeps the local status and decision fields.
    """
    if not previous:
        return row
    old_status = str(previous.get("status") or "")
    new_status = str(row.get("status") or "pending")
    if old_status in ("active", "rejected") and new_status == "pending":
        row = dict(row)
        for field in ("status", "rejection_reason", "room_id", "reviewed_by",
                      "reviewed_at", "updated_at"):
            if field in previous:
                row[field] = previous[field]
    return row


def _fmt_stamp(value) -> str:
    """Readable timestamp for the notes blocks (raw value, never invented)."""
    text = str(value or "").strip()
    if not text:
        return "—"
    return text.replace("T", " ").replace("Z", "").strip()


def _fmt_date(value) -> str:
    """Date-only value (``created_at`` shown in the notes)."""
    text = str(value or "").strip()
    return text[:10] if text else "—"


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
    """Cell item behind a pill widget.

    The status word stays readable through ``item(...).text()`` (the tests and
    the desk workflow rely on it) but is not painted, so nothing shows through
    behind the pill drawn on top of the cell. The table's item padding
    (``space-3`` on each side) insets the cell widget, so it is added to the
    column width the item asks for (``ResizeToContents``).
    """
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


class RoomAllocationDialog(QDialog):
    """Room picker used when approving an application (visual layer only).

    The caller keeps the room query, the occupancy maths and the
    ``approve_student`` RPC exactly as they were; this dialog only renders the
    already-filtered room list and returns the chosen room.
    """

    def __init__(self, parent, student: dict, rooms: list[dict], occupancy: dict[str, int]):
        super().__init__(parent)
        self._student = student
        self._rooms = list(rooms or [])
        self._occupancy = dict(occupancy or {})
        self._selected: dict | None = None
        name = f"{student.get('first_name', '')} {student.get('last_name', '')}".strip() or "applicant"
        self.setWindowTitle(t("pending.allocation_title"))
        self.setModal(True)
        self.setMinimumWidth(440)

        root = QVBoxLayout(self)
        root.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        root.setSpacing(S("space-4"))

        title = QLabel(t("pending.allocation_heading", name=name))
        theme.apply_role(title, "h2")
        root.addWidget(title)

        subtitle = QLabel(
            tn(
                "pending.allocation_subtitle",
                count=len(self._rooms),
                card_id=student.get("card_id") or "—",
            )
        )
        theme.apply_role(subtitle, "small")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        holder = QWidget()
        holder.setProperty("background", "canvas")
        self.room_rows = QVBoxLayout(holder)
        self.room_rows.setContentsMargins(0, 0, 0, 0)
        self.room_rows.setSpacing(S("space-2"))
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

        for room in self._rooms:
            self.room_rows.addWidget(self._build_room_row(room))
        self.room_rows.addStretch(1)

        footer = QHBoxLayout()
        footer.setSpacing(S("space-2"))
        footer.addStretch(1)
        cancel = Button(t("common.cancel"), "secondary")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        root.addLayout(footer)

    # ------------------------------------------------------------- helpers
    def _build_room_row(self, room: dict) -> QWidget:
        """One room: label, occupancy meter and an allocate button (or the reason)."""
        room_id = room.get("id")
        occupied = int(self._occupancy.get(room_id, 0) or 0)
        capacity = int(room.get("capacity") or 0)
        free = max(0, capacity - occupied)
        full = capacity > 0 and free <= 0

        row = QFrame()
        row.setObjectName("cardFrame")
        line = QHBoxLayout(row)
        line.setContentsMargins(S("space-3"), S("space-3"), S("space-3"), S("space-3"))
        line.setSpacing(S("space-3"))

        column = QVBoxLayout()
        column.setSpacing(2)
        room_label = QLabel(
            t(
                "pending.room_row_title",
                block=room.get("block", "—"),
                number=room.get("number", "—"),
            )
        )
        theme.apply_role(room_label, "h3")
        theme.enable_tabular(room_label)
        meta = QLabel(
            t(
                "pending.room_row_meta",
                floor=room.get("floor", "—"),
                free=format_number(free),
                capacity=format_number(capacity),
            )
        )
        theme.apply_role(meta, "small")
        column.addWidget(room_label)
        column.addWidget(meta)
        line.addLayout(column, 1)

        bar = RoomOccupancyBar(occupied, capacity or 1)
        bar.setFixedWidth(132)
        line.addWidget(bar, 0, Qt.AlignmentFlag.AlignVCenter)

        button = Button.accent(t("pending.allocate_btn"), icon="check")
        if full:
            button.setEnabled(False)
            button.setText(t("status.full"))
            button.setToolTip(
                t(
                    "pending.full_tooltip",
                    occupied=format_number(occupied),
                    capacity=format_number(capacity),
                )
            )
        else:
            button.setToolTip(
                t(
                    "pending.allocate_tooltip",
                    free=format_number(free),
                    capacity=format_number(capacity),
                )
            )
            button.clicked.connect(lambda _checked=False, chosen=room: self._choose(chosen))
        line.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    def _choose(self, room: dict) -> None:
        self._selected = room
        self.accept()

    # --------------------------------------------------------------- result
    def selected_room(self) -> dict | None:
        """The chosen room, or ``None`` when the dialog was cancelled."""
        return self._selected

    def selected_room_id(self):
        """``id`` of the chosen room, or ``None``."""
        return (self._selected or {}).get("id")


class PendingPage(QWidget):
    """Applications & housing: filters, applications table and inspector."""

    def __init__(self, client, *, defer_initial_load: bool = False):
        super().__init__()
        self.client = client
        self.all_rows: list[dict] = []
        self.rows: list[dict] = []
        self.official = {}
        self.filter_mode = "pending"
        # Differential-redraw index: student id -> field signature of the
        # pending slice currently held in ``all_rows``.
        self._pending_index: dict[str, str] = {}
        # Rows deleted in this session.  A stale snapshot or live tick must not
        # resurrect them (the delete RPC is authoritative).
        self._deleted_ids: set[str] = set()
        # Background I/O for every refresh / decision action.  The constructor
        # still loads synchronously once so the first paint has data; all later
        # entry points (Refresh, approve, reject, delete) use this runner.
        self._initializing = True
        self._working = False
        self._request_id = 0
        self._approve_student: dict | None = None
        self.residence_gender: str | None = (get_cached_residence_settings(client) or {}).get("residence_gender")
        self.tasks = TaskRunner(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-8"), S("space-8"), S("space-8"), S("space-8"))
        layout.setSpacing(S("space-6"))

        self.header = PageHeader(
            t("pending.title"),
            t("pending.subtitle"),
        )
        self.refresh_btn = IconButton("refresh", t("pending.refresh_tooltip"))
        self.refresh_btn.clicked.connect(self.reload)
        self.header.actions.addWidget(self.refresh_btn)
        layout.addWidget(self.header)

        # ------------------------------------------------------------ toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(S("space-3"))

        self.segments = SegmentedControl(_views())
        self.btn_all = self.segments.buttons["all"]
        self.btn_pending = self.segments.buttons["pending"]
        self.btn_approved = self.segments.buttons["approved"]
        self.btn_rejected = self.segments.buttons["rejected"]
        self.segments.set_current("pending")
        self.segments.changed.connect(self.set_filter)
        toolbar.addWidget(self.segments)

        self.search = SearchField(t("pending.search_placeholder"))
        self.search.changed.connect(self.apply_filter)
        # Legacy alias: the search box used to be a bare QLineEdit.
        self.search_input = self.search.edit
        toolbar.addWidget(self.search, 1)
        layout.addLayout(toolbar)

        self.error_banner = InlineBanner(
            "error",
            title=t("pending.error_title"),
            message=t("pending.error_msg"),
        )
        self.error_banner.setVisible(False)
        layout.addWidget(self.error_banner)

        # Busy state for in-flight background work and the result of the last
        # decision action.  Both stay inline so a slow network never blocks the
        # window with a modal dialog or a traceback.
        self.busy_banner = InlineBanner("info", title=t("pending.working_title"), message="")
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
        table_card.setMinimumWidth(420)
        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(0, 0, 0, 0)

        cols = _columns()
        self.stack = QStackedWidget()
        self.table = QTableWidget(0, len(cols))
        configure_table(self.table, cols)
        self.table.setItemDelegateForColumn(3, StatusPillDelegate(self.table))
        self.table.setItemDelegateForColumn(4, StatusPillDelegate(self.table))
        _fit_columns(
            self.table,
            [
                QHeaderView.ResizeMode.Interactive,
                QHeaderView.ResizeMode.Stretch,
                QHeaderView.ResizeMode.Stretch,
                QHeaderView.ResizeMode.Interactive,
                QHeaderView.ResizeMode.Interactive,
            ],
        )
        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 140)
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        self.stack.addWidget(self.table)

        self.empty_state = EmptyState(
            "clock",
            t("pending.empty_title"),
            t("pending.empty_desc"),
        )
        self.stack.addWidget(self.empty_state)
        card_layout.addWidget(self.stack)
        self.splitter.addWidget(table_card)

        # ------------------------------------------------------ inspector
        self.panel = DetailPanel(340, 460, title=t("pending.inspector_title"))
        self.empty_panel = EmptyState(
            "user-check",
            t("pending.empty_inspector_title"),
            t("pending.empty_inspector_desc"),
        )
        self.panel.add_widget(self.empty_panel)

        self.identity = QWidget()
        identity = QHBoxLayout(self.identity)
        identity.setContentsMargins(0, 0, 0, 0)
        identity.setSpacing(S("space-3"))
        self.avatar = Avatar("?", size=S("size-control"))
        identity.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignTop)
        identity_column = QVBoxLayout()
        identity_column.setSpacing(2)
        self.name_label = QLabel("—")
        theme.apply_role(self.name_label, "h3")
        self.name_label.setWordWrap(True)
        self.card_label = QLabel("—")
        theme.apply_role(self.card_label, "small")
        theme.enable_tabular(self.card_label)
        identity_column.addWidget(self.name_label)
        identity_column.addWidget(self.card_label)
        self.roster_badge = RosterMatchBadge(None)
        self.roster_badge.setToolTip(t("pending.roster_tooltip"))
        identity_column.addWidget(self.roster_badge, 0, Qt.AlignmentFlag.AlignLeft)
        self.gender_warning_badge = StatusPill("warning", t("residence.gender_differs_badge"))
        self.gender_warning_badge.setToolTip(t("residence.gender_differs_tooltip"))
        self.gender_warning_badge.setVisible(False)
        identity_column.addWidget(self.gender_warning_badge, 0, Qt.AlignmentFlag.AlignLeft)
        identity.addLayout(identity_column, 1)
        self.panel.add_widget(self.identity)

        self.facts = KeyValueList()
        self.panel.add_widget(self.facts)

        self.actions_row = QWidget()
        actions = QVBoxLayout(self.actions_row)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(S("space-2"))
        self.approve_btn = Button.accent(t("pending.approve_btn"), icon="check")
        self.approve_btn.clicked.connect(self.on_approve)
        actions.addWidget(self.approve_btn)
        reject_row = QHBoxLayout()
        reject_row.setSpacing(S("space-2"))
        self.reject_btn = Button.danger(t("pending.reject_btn"), icon="x")
        self.reject_btn.clicked.connect(self.on_reject)
        self.delete_btn = Button(t("common.delete"), "ghost", icon="trash")
        self.delete_btn.setToolTip(t("pending.delete_tooltip"))
        self.delete_btn.clicked.connect(self.on_delete)
        self._style_flat_danger(self.delete_btn)
        reject_row.addWidget(self.reject_btn, 1)
        reject_row.addWidget(self.delete_btn, 0)
        actions.addLayout(reject_row)
        self.panel.add_widget(self.actions_row)

        self.delete_hint = QWidget()
        hint_row = QHBoxLayout(self.delete_hint)
        hint_row.setContentsMargins(0, 0, 0, 0)
        hint_row.setSpacing(S("space-2"))
        hint_icon = QLabel()
        hint_icon.setPixmap(get_pixmap("info", 16, theme.status_tokens("progress")["ink"]))
        hint_icon.setFixedWidth(16)
        hint_icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        hint_text = QLabel(t("pending.delete_hint_text"))
        theme.apply_role(hint_text, "small")
        hint_text.setWordWrap(True)
        hint_row.addWidget(hint_icon, 0, Qt.AlignmentFlag.AlignTop)
        hint_row.addWidget(hint_text, 1)
        self.delete_hint.setVisible(False)
        self.panel.add_widget(self.delete_hint)

        self.record_block = QFrame()
        self.record_block.setObjectName("recordBlock")
        record = QVBoxLayout(self.record_block)
        record.setContentsMargins(S("space-3"), S("space-3"), S("space-3"), S("space-3"))
        record.setSpacing(S("space-2"))
        record_head = QHBoxLayout()
        record_head.setSpacing(S("space-2"))
        self.record_overline = QLabel("")
        theme.apply_role(self.record_overline, "overline")
        self.record_overline.setWordWrap(True)
        self.record_pill = StatusPill("pending", t("status.pending"))
        record_head.addWidget(self.record_overline, 1)
        record_head.addWidget(self.record_pill, 0, Qt.AlignmentFlag.AlignTop)
        record_body = QLabel("")
        theme.apply_role(record_body, "body")
        record_body.setWordWrap(True)
        self.record_body = record_body
        self.record_meta = QLabel("")
        theme.apply_role(self.record_meta, "small")
        self.record_meta.setWordWrap(True)
        record.addLayout(record_head)
        record.addWidget(record_body)
        record.addWidget(self.record_meta)
        self.panel.add_widget(self.record_block)

        self.detail_text = QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMinimumHeight(S("space-8"))
        self.detail_text.setPlaceholderText(t("pending.detail_placeholder"))
        theme.enable_tabular(self.detail_text)
        self.panel.add_widget(self.detail_text)

        # Widgets revealed only while a student is selected (``delete_hint`` is
        # toggled by the status rules in show_detail, not by selection alone).
        self._selection_widgets = [
            self.identity,
            self.roster_badge,
            self.facts,
            self.actions_row,
            self.record_block,
            self.detail_text,
        ]

        self.splitter.addWidget(self.panel)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        layout.addWidget(self.splitter, 1)

        self._show_selection(False)
        if not defer_initial_load:
            self.reload()
        self._initializing = False

    # --------------------------------------------------------------- styling
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

    # ----------------------------------------------------------------- views
    def set_filter(self, mode: str):
        self.filter_mode = mode
        self.btn_pending.setChecked(mode == "pending")
        self.btn_approved.setChecked(mode == "approved")
        self.btn_rejected.setChecked(mode == "rejected")
        self.btn_all.setChecked(mode == "all")
        self.apply_filter()

    def apply_filter(self):
        needle = self.search.text().lower().strip()
        filtered = []
        for r in getattr(self, "all_rows", []):
            status = r.get("status", "")
            if self.filter_mode == "pending" and status != "pending":
                continue
            elif self.filter_mode == "approved" and status != "active":
                continue
            elif self.filter_mode == "rejected" and status != "rejected":
                continue

            text = f"{r.get('card_id', '')} {r.get('first_name', '')} {r.get('last_name', '')} {r.get('university', '')}".lower()
            if needle and needle not in text:
                continue
            filtered.append(r)
        self._render_table(filtered)

    # -------------------------------------------------------- live sync data
    @staticmethod
    def _row_signature(row: dict):
        """Stable signature of every field of one row (order independent, fast tuple)."""
        return tuple(sorted((k, str(v)) for k, v in row.items()))

    def _index(self, rows) -> dict[str, str]:
        """``{student id: field signature}`` for the given rows."""
        return {str(row.get("id")): self._row_signature(row) for row in rows}

    def apply_live_data(self, pending_students: list[dict]):
        """Merge a live pending slice without touching filter, search or selection.

        Differential redraw: the incoming slice is compared (by id **and** field
        values) with the pending slice already held; when nothing changed the
        page does not repaint at all, and when only the pending slice changed the
        approved / rejected views keep their table, selection and scroll state.
        A stale pending tick never re-adds a row deleted here, duplicates an id,
        or rolls back a decision already recorded by this session.
        """
        current_by_id = {
            str(row.get("id")): row for row in getattr(self, "all_rows", [])
        }
        incoming: list[dict] = []
        seen: set[str] = set()
        for raw in pending_students or []:
            row = dict(raw)
            student_id = str(row.get("id"))
            if student_id in self._deleted_ids or student_id in seen:
                continue
            row = _guard_decision_regression(row, current_by_id.get(student_id))
            # A guarded row is no longer part of the pending slice; the local
            # approved/rejected copy stays in ``all_rows`` below.
            if str(row.get("status") or "pending") != "pending":
                continue
            seen.add(student_id)
            incoming.append(row)

        incoming_index = self._index(incoming)
        if incoming_index == self._pending_index:
            return

        self._pending_index = incoming_index
        self.all_rows = incoming + [
            r for r in getattr(self, "all_rows", [])
            if r.get("status") != "pending" and str(r.get("id")) not in seen
        ]

        if self.filter_mode in ("pending", "all"):
            # The visible slice is the one that changed: repaint it (the search
            # needle and the filter are reused, the selection is restored by id).
            self.apply_filter()
        else:
            # Approved / rejected views are unaffected by a pending change:
            # keep the table, the selected row and the search exactly as they are.
            self._update_segment_counts()

    # ------------------------------------------------------------ rendering
    def _render_table(self, rows: list[dict]):
        selected_id = self.selected().get("id") if self.selected() else None
        self.rows = rows
        # ``official`` is filled by the background snapshot loader.  Painting
        # never performs its own roster query: filters and post-action redraws
        # must stay on the GUI thread without network I/O.

        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.rows))
            restore_row = -1
            for i, s in enumerate(self.rows):
                if s.get("id") == selected_id:
                    restore_row = i
                card_id = str(s.get("card_id", ""))
                is_match = card_id in self.official
                raw_status = s.get("status", "pending")
                status_kind, status_text = _status_meta(raw_status)
                matched = True if is_match else (False if self.official else None)

                card_item = QTableWidgetItem(card_id)
                name_item = QTableWidgetItem(f"{s.get('first_name', '')} {s.get('last_name', '')}".strip())
                univ_item = QTableWidgetItem(str(s.get("university") or "—"))
                status_item = QTableWidgetItem(status_text)
                status_item.setData(Qt.ItemDataRole.UserRole, (status_kind, None, status_text))
                roster_text = (
                    t("pending.roster_matched")
                    if matched is True
                    else (t("pending.roster_not_in_roster") if matched is False else t("pending.roster_not_checked"))
                )
                roster_kind = "ok" if matched is True else "danger" if matched is False else "neutral"
                roster_icon = "check-circle" if matched is True else "x-circle" if matched is False else "info"
                roster_item = QTableWidgetItem(roster_text)
                roster_item.setData(Qt.ItemDataRole.UserRole, (roster_kind, roster_icon, roster_text))

                self.table.setItem(i, 0, card_item)
                self.table.setItem(i, 1, name_item)
                self.table.setItem(i, 2, univ_item)
                self.table.setItem(i, 3, status_item)
                self.table.setItem(i, 4, roster_item)
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)

        if restore_row >= 0:
            self.table.selectRow(restore_row)
        else:
            # The selected student vanished from the refreshed/filtered view:
            # clear both the selection and the current index so no stale row is
            # inspected by accident.
            self.table.clearSelection()
            self.table.setCurrentCell(-1, -1)
            self.show_detail()
        self._update_view_state()

    def _update_view_state(self):
        """Segment counts + table/empty-state swap (never rebuilds the table)."""
        self.stack.setCurrentIndex(1 if not self.rows else 0)
        self._update_segment_counts()

    def _update_segment_counts(self):
        counts = {key: 0 for key, _label in _views()}
        for r in getattr(self, "all_rows", []):
            status = r.get("status", "")
            counts["all"] += 1
            if status == "pending":
                counts["pending"] += 1
            elif status == "active":
                counts["approved"] += 1
            elif status == "rejected":
                counts["rejected"] += 1
        for key, value in counts.items():
            self.segments.set_count(key, value)

    # ------------------------------------------------------- background data
    def _fetch_students(self):
        resp = self.client.table("students").select(
            "id, card_id, first_name, last_name, birth_date, gender, phone, email, "
            "university, faculty, study_level, wilaya, status, rejection_reason, "
            "room_id, reviewed_by, reviewed_at, created_at"
        ).order("created_at", desc=True).execute()
        return list(resp.data or [])

    def _fetch_official(self):
        return official_lookup(self.client)

    def set_residence_gender(self, gender: str | None) -> None:
        self.residence_gender = gender
        self.show_detail()

    def _fetch_snapshot(self):
        """Network-only snapshot (students + official roster), for a worker."""
        resp = self.client.table("students").select(
            "id, card_id, first_name, last_name, birth_date, gender, phone, email, "
            "university, faculty, study_level, wilaya, status, rejection_reason, "
            "room_id, reviewed_by, reviewed_at, created_at"
        ).order("created_at", desc=True).execute()
        return list(resp.data or []), official_lookup(self.client)

    def _apply_snapshot(self, snapshot):
        """Apply a fetched snapshot on the GUI thread, preserving view state.

        Rows deleted in this session stay deleted, and a stale read that still
        reports ``pending`` cannot roll back a decision recorded locally.
        """
        rows, official = snapshot
        cached_res = get_cached_residence_settings(self.client)
        if cached_res:
            self.residence_gender = cached_res.get("residence_gender")
        current_by_id = {
            str(row.get("id")): row for row in getattr(self, "all_rows", [])
        }
        merged: list[dict] = []
        seen: set[str] = set()
        for raw in rows or []:
            row = dict(raw)
            student_id = str(row.get("id"))
            if student_id in self._deleted_ids or student_id in seen:
                continue
            seen.add(student_id)
            merged.append(_guard_decision_regression(row, current_by_id.get(student_id)))
        self.official = official or {}
        self.all_rows = merged
        self._pending_index = self._index(
            [r for r in self.all_rows if r.get("status") == "pending"]
        )
        self.error_banner.setVisible(False)
        self.apply_filter()

    def _merge_decision_row(self, decision_row: dict):
        """Overlay the authoritative RPC row on the locally held snapshot."""
        target = str(decision_row.get("id"))
        merged: list[dict] = []
        found = False
        for raw in getattr(self, "all_rows", []):
            row = dict(raw)
            if str(row.get("id")) == target:
                row.update(decision_row)
                found = True
            merged.append(row)
        if not found:
            merged.insert(0, dict(decision_row))
        self.all_rows = merged
        self._pending_index = self._index(
            [r for r in merged if r.get("status") == "pending"]
        )
        self.apply_filter()

    def _reload_blocking(self):
        """Initial load only: the constructor keeps its synchronous first data."""
        try:
            self._apply_snapshot(self._fetch_snapshot())
        except Exception:
            self.error_banner.setVisible(True)

    def reload(self):
        """Reload the applications queue.

        The constructor takes the blocking path so the first paint is populated;
        every later call (Refresh button, live code, tests) runs the network work
        on the thread pool and applies the snapshot on the GUI thread.
        """
        if self._initializing:
            self._reload_blocking()
        else:
            self._reload_async()

    def _reload_async(self):
        if self._working:
            return
        self._request_id += 1
        req_id = self._request_id
        self._begin_working(t("pending.refreshing_msg"))
        callables = {
            "students": self._fetch_students,
            "official": self._fetch_official,
        }
        started = self.tasks.gather(
            "reload",
            callables,
            on_complete=self._on_gather_success,
            on_finished=self._end_working,
            request_id=req_id,
        )
        if not started:
            self._end_working()

    def _on_gather_success(self, result: GatherResult) -> None:
        if result.request_id != self._request_id or getattr(self, "_closing", False):
            return  # Discard stale result

        if "students" in result.errors:
            self._on_reload_failed(result.errors["students"])
            return

        students = result.get("students", [])
        official = result.get("official")
        if official is None and "official" in result.errors:
            _log.warning("Official roster lookup failed during reload: %s", result.errors["official"])
            official = getattr(self, "official", {})

        self._apply_snapshot((students, official))

    def _on_reload_success(self, snapshot):
        self._apply_snapshot(snapshot)

    def _on_reload_failed(self, message: str):
        self.error_banner.set_title(t("pending.refresh_failed_title"))
        self.error_banner.set_message(
            t("pending.refresh_failed_msg", message=message)
        )
        self.error_banner.setVisible(True)

    # ---------------------------------------------------------- busy state
    def _begin_working(self, message: str):
        """Disable every action control and show the inline Working… banner."""
        self._working = True
        self.busy_banner.set_kind("info")
        self.busy_banner.set_title(t("pending.working_title"))
        self.busy_banner.set_message(message)
        self.busy_banner.setVisible(True)
        self.action_banner.setVisible(False)
        self._set_action_controls_enabled(False)

    def _end_working(self):
        """Restore the status-driven action guards after success or failure."""
        if not self._working:
            return
        self._working = False
        self.busy_banner.setVisible(False)
        self._set_action_controls_enabled(True)

    def _set_action_controls_enabled(self, enabled: bool):
        if enabled:
            self.refresh_btn.setEnabled(True)
            # show_detail reapplies the status rules (pending cannot be deleted,
            # approved cannot be approved again, no selection disables all).
            self.show_detail()
        else:
            self.approve_btn.setEnabled(False)
            self.reject_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)

    def _show_action_success(self, message: str):
        self.action_banner.set_kind("success")
        self.action_banner.set_title(t("pending.done_title"))
        self.action_banner.set_message(message)
        self.action_banner.setVisible(True)

    def _show_action_warning(self, message: str):
        self.action_banner.set_kind("warning")
        self.action_banner.set_title(t("pending.warning_title"))
        self.action_banner.set_message(message)
        self.action_banner.setVisible(True)

    def _on_action_failed(self, message: str):
        self.action_banner.set_kind("error")
        if "result is unknown" in message.lower():
            self.action_banner.set_title(t("pending.timeout_title"))
            self.action_banner.set_message(message)
            self.reload()
        else:
            self.action_banner.set_title(t("pending.failed_title"))
            self.action_banner.set_message(t("pending.action_failed_msg", message=message))
        self.action_banner.setVisible(True)
        self._end_working()

    # ------------------------------------------------------- worker payloads
    def _load_rooms(self, *_args):
        """Load dormitory rooms + occupancy (network-only, worker thread)."""
        rooms = self.client.table("rooms").select(
            "id, block, number, floor, capacity"
        ).order("block").order("number").execute().data or []
        return list(rooms), room_occupancy(self.client)

    def _fetch_after_decision(self):
        """Best-effort follow-up snapshot for a committed decision.

        The decision RPC has already succeeded, so a read failure is reported
        alongside the returned row instead of making the whole action look
        failed (which would also throw the authoritative RPC row away).
        """
        try:
            return self._fetch_snapshot(), None
        except Exception as exc:  # noqa: BLE001 - the decision is already saved
            return None, human_error(exc)

    def _approve_rpc(self, student_id, room_id):
        """Run the approval RPC; return its row plus the follow-up snapshot."""
        response = execute_network_call(
            lambda: self.client.rpc(
                "approve_student", {"p_student": student_id, "p_room": room_id}
            ).execute(),
            is_write=True,
        )
        decision_row = _rpc_row(response)
        snapshot, refresh_error = self._fetch_after_decision()
        return decision_row, snapshot, refresh_error

    def _reject_rpc(self, student_id, reason):
        """Run the rejection RPC; return its row plus the follow-up snapshot."""
        response = execute_network_call(
            lambda: self.client.rpc(
                "reject_student", {"p_student": student_id, "p_reason": reason}
            ).execute(),
            is_write=True,
        )
        decision_row = _rpc_row(response)
        snapshot, refresh_error = self._fetch_after_decision()
        return decision_row, snapshot, refresh_error

    def _delete_rpc(self, student_id):
        """Delete through the authenticated RPC; never fall back to the table.

        ``delete_student`` enforces staff authorisation, the pending-application
        guard and the staff/profile/auth cleanup.  A raw table delete would
        bypass those rules and silently report success when nothing matched.
        """
        execute_network_call(
            lambda: self.client.rpc("delete_student", {"p_student": student_id}).execute(),
            is_write=True,
        )
        return student_id

    @staticmethod
    def _student_name(student: dict) -> str:
        return f"{student.get('first_name', '')} {student.get('last_name', '')}".strip()

    # ------------------------------------------------------ action handlers
    def _on_approve_rooms_loaded(self, result):
        student = self._approve_student
        if student is None:
            self._end_working()
            return
        rooms, occ = result
        if not rooms:
            QMessageBox.warning(
                self,
                t("pending.no_rooms_title"),
                t("pending.no_rooms_message"),
            )
            self._end_working()
            return

        dlg = RoomAllocationDialog(self, student, rooms, occ)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self._end_working()
            return
        room = dlg.selected_room()
        room_id = dlg.selected_room_id()
        if not room_id or room is None:
            self._end_working()
            return

        # Same guard the old "[LOCKED]" option carried: a full room is refused.
        occupied = int(occ.get(room_id, 0) or 0)
        if occupied >= int(room.get("capacity") or 0):
            QMessageBox.warning(
                self,
                t("pending.room_full_title"),
                t("pending.room_full_message"),
            )
            self._end_working()
            return

        self._begin_working(t("pending.approving_msg"))
        student_id = student["id"]
        started = self.tasks.run(
            "approve",
            lambda: self._approve_rpc(student_id, room_id),
            on_success=lambda snapshot: self._on_approve_success(snapshot, student),
            on_failed=self._on_action_failed,
            on_finished=self._end_working,
        )
        if not started:
            self._end_working()

    def _apply_decision_result(self, result, student, message: str):
        """Apply the RPC row even when the follow-up snapshot failed."""
        decision_row, snapshot, refresh_error = result
        if snapshot is not None:
            self._apply_snapshot(snapshot)
        # The RPC row is authoritative: merge it after the snapshot so even a
        # stale follow-up read cannot leave the row pending or omit it.
        self._merge_decision_row(decision_row)
        if refresh_error:
            self._show_action_warning(
                t(
                    "pending.decision_warning_refresh",
                    message=message,
                    error=refresh_error,
                )
            )
            return
        self._show_action_success(message)

    def _on_approve_success(self, result, student):
        name = self._student_name(student) or "The student"
        self._apply_decision_result(
            result,
            student,
            t("pending.approved_success_msg", name=name),
        )

    def _on_decision_success(self, result, student):
        name = self._student_name(student) or "The applicant"
        self._apply_decision_result(
            result,
            student,
            t("pending.decision_success_msg", name=name),
        )

    def _on_delete_success(self, student_id, student):
        deleted_id = str(student_id)
        # Tombstone first: an in-flight snapshot or live tick may still carry
        # the row, and it must not resurrect after this successful delete.
        self._deleted_ids.add(deleted_id)
        self.all_rows = [
            row for row in getattr(self, "all_rows", [])
            if str(row.get("id")) != deleted_id
        ]
        self._pending_index = self._index(
            [r for r in self.all_rows if r.get("status") == "pending"]
        )
        self.apply_filter()
        name = self._student_name(student) or "The resident"
        self._show_action_success(t("pending.delete_success_msg", name=name))

    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def _show_selection(self, has_selection: bool) -> None:
        """Toggle between the EmptyState and the selected-applicant widgets."""
        self.empty_panel.setVisible(not has_selection)
        for widget in self._selection_widgets:
            widget.setVisible(has_selection)
        if not has_selection:
            self.delete_hint.setVisible(False)

    # -------------------------------------------------------------- inspector
    def show_detail(self):
        s = self.selected()
        if not s:
            self.detail_text.clear()
            self.approve_btn.setEnabled(False)
            self.approve_btn.setToolTip(t("pending.select_applicant_to_approve"))
            self.reject_btn.setEnabled(False)
            self.reject_btn.setText(t("pending.reject_btn"))
            self.reject_btn.setToolTip(t("pending.select_applicant_to_decide"))
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip(t("pending.select_applicant_to_delete"))
            self.delete_hint.setVisible(False)
            self.gender_warning_badge.setVisible(False)
            self._show_selection(False)
            return

        status = s.get("status", "pending")
        status_kind, status_text = _status_meta(status)
        name = f"{s.get('first_name', '')} {s.get('last_name', '')}".strip() or "Unnamed applicant"

        # Identity + roster match + non-blocking residence gender warning.
        self.avatar.set_name(name)
        self.name_label.setText(name)
        self.card_label.setText(t("pending.card_id_label", card_id=s.get('card_id') or '—'))
        official_row = self.official.get(s.get("card_id"))
        self.roster_badge.set_matched(True if official_row else (False if self.official else None))
        cached_res = get_cached_residence_settings(self.client)
        res_gender = (cached_res or {}).get("residence_gender") if cached_res else getattr(self, "residence_gender", None)
        self.residence_gender = res_gender
        self.gender_warning_badge.setVisible(
            has_gender_mismatch(
                res_gender,
                student_gender=s.get("gender"),
                roster_gender=(official_row or {}).get("gender"),
            )
        )

        # Submitted data.
        self.facts.set_rows([
            (t("pending.fact_university"), s.get("university") or "—"),
            (t("pending.fact_faculty"), s.get("faculty") or "—"),
            (t("pending.fact_study_level"), s.get("study_level") or "—"),
            (t("pending.fact_wilaya"), s.get("wilaya") or "—"),
            (t("pending.fact_birth_date"), s.get("birth_date") or "—"),
            (t("pending.fact_contact"), f"{s.get('phone') or '—'} · {s.get('email') or '—'}"),
        ])

        # Action buttons.
        if status == "active":
            self.approve_btn.setEnabled(False)
            self.approve_btn.setToolTip(t("pending.already_approved_tooltip"))
        else:
            self.approve_btn.setEnabled(True)
            self.approve_btn.setToolTip("")

        self.reject_btn.setEnabled(True)
        if status == "rejected":
            self.reject_btn.setText(t("pending.edit_rejection_btn"))
            self.reject_btn.setToolTip(t("pending.edit_rejection_tooltip"))
        else:
            self.reject_btn.setText(t("pending.reject_btn"))
            self.reject_btn.setToolTip(t("pending.reject_tooltip"))

        if status == "pending":
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip(t("pending.delete_pending_disabled_tooltip"))
            self.delete_hint.setVisible(True)
        else:
            self.delete_btn.setEnabled(True)
            self.delete_btn.setToolTip("")
            self.delete_hint.setVisible(False)

        self._render_record_block(status, status_kind, status_text, s)
        self.detail_text.setPlainText(self._detail_notes(status, status_text, s, official_row))
        if self._working:
            # A live-sync tick or a selection change during an action must not
            # re-enable the controls behind the Working… state.
            self.approve_btn.setEnabled(False)
            self.reject_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
        self._show_selection(True)

    def _render_record_block(self, status: str, status_kind: str, status_text: str, student: dict):
        """Tinted record block: rejection reason, housing status or pending state."""
        if status == "rejected":
            overline = _rejection_overline()
            body = f"“{student.get('rejection_reason') or t('pending.no_reason_recorded')}”"
            meta = t("pending.reviewed_stamp", stamp=_fmt_stamp(student.get("reviewed_at")))
        elif status == "active":
            overline = t("pending.housing_status_overline")
            body = t("pending.housing_status_active_body")
            meta = t("pending.reviewed_stamp", stamp=_fmt_stamp(student.get("reviewed_at")))
        else:
            overline = t("pending.application_status_overline")
            body = t("pending.housing_status_pending_body")
            meta = ""
        self.record_overline.setText(overline.upper())
        self.record_body.setText(body)
        self.record_meta.setText(meta)
        self.record_meta.setVisible(bool(meta))
        self.record_pill.set_kind(status_kind, status_text)
        self.record_overline.setText(overline.upper())
        self.record_body.setText(body)
        self.record_meta.setText(meta)
        self.record_meta.setVisible(bool(meta))
        self.record_pill.set_kind(status_kind, status_text)
        tokens = theme.status_tokens(status_kind)
        self.record_block.setStyleSheet(
            f"QFrame#recordBlock {{ background-color: {tokens['bg']};"
            f" border: 1px solid {tokens['border']}; border-radius: {C('radius-input')}; }}"
        )

    def _detail_notes(self, status: str, status_text: str, student: dict, official_row) -> str:
        """Plain-text record block (the desk reference for inquiries)."""
        name = f"{student.get('first_name', '')} {student.get('last_name', '')}".strip() or "—"
        if official_row:
            roster_lines = (
                "Matched in the official university roster.\n"
                f"  Name: {official_row.get('first_name', '')} {official_row.get('last_name', '')}\n"
                f"  Birth date: {official_row.get('birth_date') or '—'}\n"
                f"  Gender: {official_row.get('gender') or '—'}\n"
                f"  Faculty: {official_row.get('faculty') or '—'}"
            )
        else:
            roster_lines = (
                "No match in the official university roster.\n"
                "Verify the physical enrolment certificate before approval."
            )

        if status == "rejected":
            status_overline = _rejection_overline()
            status_body = f"“{student.get('rejection_reason') or t('pending.no_reason_recorded')}”"
            status_meta = t("pending.reviewed_stamp", stamp=_fmt_stamp(student.get("reviewed_at")))
        elif status == "active":
            status_overline = t("pending.housing_status_overline")
            status_body = t("pending.housing_status_active_body")
            status_meta = t("pending.reviewed_stamp", stamp=_fmt_stamp(student.get("reviewed_at")))
        else:
            status_overline = t("pending.application_status_overline")
            status_body = t("pending.housing_status_pending_body")
            status_meta = ""

        return (
            f"STUDENT CARD ID: {student.get('card_id') or '—'}\n"
            f"Name: {name}\n"
            f"Gender: {student.get('gender') or '—'}  |  Birth date: {student.get('birth_date') or '—'}\n"
            f"Phone: {student.get('phone') or '—'}\n"
            f"Email: {student.get('email') or '—'}\n"
            f"University: {student.get('university') or '—'}\n"
            f"Faculty: {student.get('faculty') or '—'}\n"
            f"Study level: {student.get('study_level') or '—'}  |  Wilaya: {student.get('wilaya') or '—'}\n"
            f"Submitted: {_fmt_date(student.get('created_at'))}\n"
            f"\n"
            f"ROSTER VERIFICATION\n"
            f"{roster_lines}\n"
            f"\n"
            f"{status_overline}\n"
            f"Status: {status_text}\n"
            f"{status_body}\n"
            f"{status_meta}"
        )

    # ----------------------------------------------------------------- events
    def on_row_double_clicked(self, row: int, col: int):
        s = self.selected()
        if s:
            o = self.official.get(s.get("card_id"))
            cached_res = get_cached_residence_settings(self.client)
            res_gender = (cached_res or {}).get("residence_gender") if cached_res else getattr(self, "residence_gender", None)
            dlg = StudentInfoCardDialog(self, s, o, residence_gender=res_gender)
            dlg.exec()

    def on_approve(self):
        if self._working:
            return
        s = self.selected()
        if not s:
            QMessageBox.information(
                self,
                t("pending.select_applicant_title"),
                t("pending.select_applicant_message"),
            )
            return

        # Room list + occupancy are optional data: fetch them on the worker,
        # then open the allocation dialog on the GUI thread.
        self._approve_student = dict(s)
        self._begin_working(t("pending.loading_rooms_msg"))
        started = self.tasks.run(
            "approve-rooms",
            lambda: self._load_rooms(),
            on_success=self._on_approve_rooms_loaded,
            on_failed=self._on_action_failed,
            on_finished=self._finish_approve_rooms_stage,
        )
        if not started:
            self._end_working()

    def _finish_approve_rooms_stage(self):
        """Restore controls only if the approval RPC stage did not start."""
        if not self.tasks.is_busy("approve"):
            self._end_working()

    def on_reject(self):
        if self._working:
            return
        s = self.selected()
        if not s:
            QMessageBox.information(
                self,
                t("pending.select_applicant_title"),
                t("pending.select_applicant_message"),
            )
            return
        default_reason = s.get("rejection_reason") or ""
        reason, ok = QInputDialog.getMultiLineText(
            self,
            t("pending.reject_dialog_title"),
            t(
                "pending.reject_dialog_prompt",
                name=f"{s.get('first_name', '')} {s.get('last_name', '')}".strip(),
            ),
            text=default_reason,
        )
        if not ok:
            return
        if not reason.strip():
            QMessageBox.warning(
                self,
                t("pending.reason_required_title"),
                t("pending.reason_required_message"),
            )
            return

        student = dict(s)
        reason = reason.strip()
        self._begin_working(t("pending.saving_rejection_msg"))
        started = self.tasks.run(
            "reject",
            lambda: self._reject_rpc(student["id"], reason),
            on_success=lambda snapshot: self._on_decision_success(snapshot, student),
            on_failed=self._on_action_failed,
            on_finished=self._end_working,
        )
        if not started:
            self._end_working()

    def on_delete(self):
        if self._working:
            return
        s = self.selected()
        if not s:
            QMessageBox.information(
                self,
                t("pending.select_student_title"),
                t("pending.select_student_message"),
            )
            return
        if s.get("status") == "pending":
            QMessageBox.warning(
                self,
                t("pending.cannot_delete_title"),
                t("pending.cannot_delete_message"),
            )
            return

        name = f"{s.get('first_name', '')} {s.get('last_name', '')}".strip()
        card_id = s.get("card_id", "—")
        status = s.get("status", "—")

        confirmed = ConfirmDialog.ask(
            self,
            t("pending.confirm_delete_title"),
            t(
                "pending.confirm_delete_message",
                name=name,
                card_id=card_id,
                status=status,
            ),
            confirm_text=t("pending.confirm_delete_btn"),
        )
        if not confirmed:
            return

        student = dict(s)
        self._begin_working(t("pending.deleting_msg"))
        started = self.tasks.run(
            "delete",
            lambda: self._delete_rpc(student["id"]),
            on_success=lambda student_id: self._on_delete_success(student_id, student),
            on_failed=self._on_action_failed,
            on_finished=self._end_working,
        )
        if not started:
            self._end_working()
