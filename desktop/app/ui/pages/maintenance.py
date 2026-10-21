"""RÉSIVO — Facility maintenance & repairs (visual layer only, docs/DESIGN.md §6–§7).

Master-detail page: a ``PageHeader``, the four lifecycle stages as a
``SegmentedControl`` (Pending › Under review › In progress › Resolved) with live
counts, a ``SearchField``, the maintenance ``QTableWidget`` on the left and the
360/520 ``DetailPanel`` inspector on the right — stage ``Stepper``, category +
status header, resident identity, key facts, the fault-photo card with its
hover zoom cue, the staff-note block, the guarded status actions, the flat
delete row and the plain-text record block.

The data layer keeps its exact queries: ``reload()`` selects
``maintenance_reports`` (``*, students(first_name, last_name, card_id)``) and
``apply_live_data`` keeps the ``(id, status)`` diff plus the selection restore
by id.  ``set_status`` keeps the ``QInputDialog`` note flow, ``on_delete`` keeps
its confirmation text, and both run ``auth.get_user()`` / update / delete /
refresh through ``TaskRunner`` (off the GUI thread).  ``official_lookup`` is
also loaded in the background before the double-click ``StudentInfoCardDialog``
is shown, and the signed-URL + ``PhotoFetchWorker`` photo flow keeps its
``_photo_req_id`` stale-response guard.

Widget contracts kept for the tests
-----------------------------------
``rows`` / ``table`` / ``selected()`` / ``show_detail()`` /
``on_photo_clicked()`` / ``on_row_double_clicked()`` / ``set_status()`` /
``set_filter()`` / ``apply_filter()`` / ``apply_live_data(reports)`` /
``reload()`` / ``closeEvent()`` / ``_cleanup_thumb_worker()`` / ``delete_btn``
are unchanged; ``photo_label`` is a ``QLabel`` whose ``text()`` is exactly
``No photo attached by resident`` for a ticket without a photo;
``_current_pixmap`` / ``_current_photo_url`` / ``_photo_fetch_failed`` keep
their meaning; ``PhotoViewerDialog`` and ``QMessageBox`` stay module-level so
the tests can patch them; ``detail_text`` is a direct child of the 360/520
``DetailPanel`` frame.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QPixmap
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

from ...client import official_lookup
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
    SearchField,
    SegmentedControl,
    Skeleton,
    StatusPill,
    Stepper,
    configure_table,
)
from ..icons import get_icon, get_pixmap
from ..infocard import StudentInfoCardDialog
from ..photo_viewer import ClickablePhotoLabel, PhotoFetchWorker, PhotoViewerDialog
from ..tasks import TaskRunner, human_error
from ..theme import C, S

# Lifecycle stages (UI): the segmented filter and the inspector Stepper share
# this order. "Under review" is a UI-only stage — no ``maintenance_reports``
# row carries it yet, so its count is always 0 and the empty state explains it.
_STAGES = [
    ("pending", "Pending"),
    ("under_review", "Under review"),
    ("in_progress", "In progress"),
    ("resolved", "Resolved"),
]
_STAGE_LABELS = [label for _key, label in _STAGES]

# Table language: overline headers are uppercased by configure_table().
_COLUMNS = ["Category", "Resident", "Status", "Reported"]

# report status -> (StatusPill kind, status word)
_STATUS_KINDS = {
    "pending": ("pending", "Pending"),
    "under_review": ("review", "Under review"),
    "in_progress": ("progress", "In progress"),
    "resolved": ("ok", "Resolved"),
}
_DEFAULT_STATUS = ("pending", "Pending")

# maintenance_category -> icon name (table cell and inspector header)
_CATEGORY_ICONS = {
    "plumbing": "droplet",
    "electrical": "zap",
    "furniture": "hammer",
    "internet": "wifi",
    "other": "wrench",
}
_CATEGORY_FALLBACK = "wrench"

# The exact string asserted by the no-photo contract test.
_NO_PHOTO_TEXT = "No photo attached by resident"

# Task keys: writes share one key so status changes and deletes can never
# overlap; reads use their own keys so a refresh cannot masquerade as a write.
_ACTION_KEY = "maintenance-action"
_RELOAD_KEY = "maintenance-reload"
_INFO_KEY = "maintenance-info"
_WORKING_TEXT = "Working..."


def _normalise_student(row: dict) -> dict:
    """``students`` embed of a report row as a plain dict (list/dict/None safe)."""
    st = row.get("students") or {}
    if isinstance(st, list) and st:
        st = st[0]
    elif not isinstance(st, dict):
        st = {}
    return st


def _status_meta(raw_status) -> tuple[str, str]:
    """``(StatusPill kind, status word)`` for any report status value."""
    return _STATUS_KINDS.get(str(raw_status), _DEFAULT_STATUS)


def _category_icon(category) -> str:
    """Icon name for a maintenance category (unknown categories -> wrench)."""
    return _CATEGORY_ICONS.get(str(category or "").lower(), _CATEGORY_FALLBACK)


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


def _room_text(row: dict, student: dict) -> str:
    """Best-effort room label from whatever room data the payload carries."""
    room = row.get("rooms") or row.get("room")
    if room is None and isinstance(student, dict):
        room = student.get("rooms") or student.get("room")
    if isinstance(room, list) and room:
        room = room[0]
    if isinstance(room, dict) and (room.get("number") or room.get("block")):
        floor = room.get("floor")
        floor_text = f" (Floor {floor})" if floor is not None and str(floor) != "" else ""
        return f"Block {room.get('block', '—')} — Room {room.get('number', '—')}{floor_text}"
    room_id = row.get("room_id") or (student.get("room_id") if isinstance(student, dict) else None)
    return str(room_id)[:8] if room_id else "—"


def _stage_index(status) -> int:
    """Stepper index for a report status (unknown -> Pending)."""
    for index, (key, _label) in enumerate(_STAGES):
        if key == str(status):
            return index
    return 0


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
    """Tinted block: overline + quoted body (fault description, staff note)."""

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


class MaintenancePage(QWidget):
    """Facility maintenance & repairs: stage filters, tickets table, inspector."""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []
        self.filter_mode = "pending"
        self._thumb_worker: PhotoFetchWorker | None = None
        self._photo_req_id: int = 0
        self._current_photo_url: str | None = None
        self._current_pixmap: QPixmap | None = None
        self._photo_fetch_failed: bool = False
        self._photo_loading: bool = False

        # Background action plumbing. Every network call started by a status
        # change, a delete, a refresh or the roster lookup runs through this
        # runner; the GUI thread only renders results.
        self.tasks = TaskRunner(self)
        self._actions_busy: bool = False
        self._info_busy: bool = False
        self._closing: bool = False
        self._loaded_once: bool = False
        self._data_generation: int = 0
        self._banner_mode: str | None = None
        self._action_texts: dict[Button, str] = {}
        self._reload_after_action: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S("space-8"), S("space-8"), S("space-8"), S("space-8"))
        layout.setSpacing(S("space-6"))

        self.header = PageHeader(
            "Facility maintenance & repairs",
            "Triage resident repair tickets filed from every residential block.",
        )
        self.refresh_btn = IconButton("refresh", "Reload the maintenance queue")
        self.refresh_btn.clicked.connect(self.reload)
        self.header.actions.addWidget(self.refresh_btn)
        layout.addWidget(self.header)

        # ------------------------------------------------------------ toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(S("space-3"))

        self.segments = SegmentedControl(_STAGES)
        self.btn_pending = self.segments.buttons["pending"]
        self.btn_under_review = self.segments.buttons["under_review"]
        self.btn_in_progress = self.segments.buttons["in_progress"]
        self.btn_resolved = self.segments.buttons["resolved"]
        self.segments.changed.connect(self.set_filter)
        toolbar.addWidget(self.segments)

        self.search = SearchField("Search by description, resident or category…")
        self.search.changed.connect(self.apply_filter)
        # Legacy alias: the search box used to be a bare QLineEdit.
        self.search_input = self.search.edit
        toolbar.addWidget(self.search, 1)
        layout.addLayout(toolbar)

        self.error_banner = InlineBanner(
            "error",
            title="Maintenance queue could not be loaded",
            message="The table is showing the last data received. Use Refresh to try again.",
        )
        self.error_banner.setVisible(False)
        layout.addWidget(self.error_banner)

        # ---------------------------------------------------- master-detail
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        table_card = QFrame()
        table_card.setObjectName("cardFrame")
        table_card.setMinimumWidth(420)
        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.table = QTableWidget(0, len(_COLUMNS))
        configure_table(self.table, _COLUMNS)
        _fit_columns(
            self.table,
            [
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.Stretch,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
            ],
        )
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        self.stack.addWidget(self.table)

        self.empty_state = EmptyState(
            "wrench",
            "No tickets in this view",
            "Switch the stage filter, adjust the search, or refresh.",
        )
        self.stack.addWidget(self.empty_state)
        card_layout.addWidget(self.stack)
        self.splitter.addWidget(table_card)

        # ------------------------------------------------------ inspector
        self.panel = DetailPanel(360, 520, title="Ticket inspector")
        self.empty_panel = EmptyState(
            "wrench",
            "No ticket selected",
            "Select a ticket to inspect the fault, the resident and the repair stage.",
        )
        self.panel.add_widget(self.empty_panel)

        self.inspector_scroll = QScrollArea()
        self.inspector_scroll.setWidgetResizable(True)
        self.inspector_scroll.setFrameShape(QFrame.Shape.NoFrame)
        inspector_body = QWidget()
        inspector = QVBoxLayout(inspector_body)
        inspector.setContentsMargins(0, 0, 0, 0)
        inspector.setSpacing(S("space-3"))

        self.stepper = Stepper(_STAGE_LABELS)
        inspector.addWidget(self.stepper)

        # Category + status header.
        self.category_row = QWidget()
        category_layout = QHBoxLayout(self.category_row)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_layout.setSpacing(S("space-3"))
        self.category_icon = QLabel()
        self.category_icon.setFixedSize(S("size-control"), S("size-control"))
        self.category_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.category_icon.setStyleSheet(
            f"background-color: {C('selection-tint')}; border-radius: {C('radius-input')};"
        )
        self.category_label = QLabel("—")
        theme.apply_role(self.category_label, "h3")
        self.status_pill = StatusPill("pending", "Pending")
        category_layout.addWidget(self.category_icon, 0)
        category_layout.addWidget(self.category_label, 1)
        category_layout.addWidget(self.status_pill, 0, Qt.AlignmentFlag.AlignVCenter)
        inspector.addWidget(self.category_row)

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
        self.card_label = QLabel("—")
        theme.apply_role(self.card_label, "small")
        theme.enable_tabular(self.card_label)
        self.card_label.setWordWrap(True)
        identity_column.addWidget(self.name_label)
        identity_column.addWidget(self.card_label)
        identity.addLayout(identity_column, 1)
        inspector.addWidget(self.identity)

        # Key facts.
        self.facts = KeyValueList()
        inspector.addWidget(self.facts)

        # ------------------------------------------------------ photo card
        self.photo_section = QWidget()
        photo_layout = QVBoxLayout(self.photo_section)
        photo_layout.setContentsMargins(0, 0, 0, 0)
        photo_layout.setSpacing(S("space-2"))
        photo_overline = QLabel("FAULT PHOTO")
        theme.apply_role(photo_overline, "overline")
        photo_layout.addWidget(photo_overline)

        self.photo_label = ClickablePhotoLabel("No ticket selected")
        self.photo_label.setObjectName("maintenancePhotoLabel")
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setWordWrap(True)
        self.photo_label.setFixedHeight(S("space-12") * 3)
        self.photo_label.setStyleSheet(
            f"QLabel#maintenancePhotoLabel {{ background-color: {C('surface-subtle')};"
            f" border: 1px dashed {C('border-strong')}; border-radius: {C('radius-input')};"
            f" color: {C('text-muted')}; font-size: {C('fs-small')}; }}"
            f"QLabel#maintenancePhotoLabel:hover {{ border-color: {C('teal-600')}; }}"
        )
        self.photo_label.clicked.connect(self.on_photo_clicked)
        self.photo_label.installEventFilter(self)

        # Hover zoom cue (overlay inside the thumbnail; clicks fall through).
        self.zoom_cue = QWidget(self.photo_label)
        self.zoom_cue.setObjectName("zoomCue")
        self.zoom_cue.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.zoom_cue.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.zoom_cue.setStyleSheet(
            f"QWidget#zoomCue {{ background-color: {C('surface')};"
            f" border: 1px solid {C('border')}; border-radius: {C('radius-input')}; }}"
            f"QWidget#zoomCue QLabel {{ background: transparent; border: none; }}"
        )
        cue_row = QHBoxLayout(self.zoom_cue)
        cue_row.setContentsMargins(S("space-2"), S("space-1"), S("space-2"), S("space-1"))
        cue_row.setSpacing(S("space-1"))
        cue_icon = QLabel()
        cue_icon.setPixmap(get_pixmap("zoom-in", 14, C("navy-800")))
        cue_text = QLabel("Open full view")
        theme.apply_role(cue_text, "small")
        cue_row.addWidget(cue_icon, 0)
        cue_row.addWidget(cue_text, 0)
        cue_holder = QVBoxLayout(self.photo_label)
        cue_holder.setContentsMargins(S("space-2"), S("space-2"), S("space-2"), S("space-2"))
        cue_holder.addWidget(self.zoom_cue, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        cue_holder.addStretch(1)
        self.zoom_cue.setVisible(False)

        photo_layout.addWidget(self.photo_label)
        self.photo_skeleton = Skeleton(2)
        self.photo_skeleton.setVisible(False)
        photo_layout.addWidget(self.photo_skeleton)
        inspector.addWidget(self.photo_section)

        # Staff / dispatch note (read-only display; set_status records it).
        self.note_block = _QuotedBlock("Staff / dispatch note")
        inspector.addWidget(self.note_block)

        # ------------------------------------------------------- actions
        self.actions_row = QWidget()
        actions = QVBoxLayout(self.actions_row)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(S("space-2"))
        self.in_progress_btn = Button("Mark in progress", "secondary", icon="wrench")
        self.in_progress_btn.clicked.connect(lambda: self.set_status("in_progress"))
        self.resolved_btn = Button.accent("Mark resolved", icon="check")
        self.resolved_btn.clicked.connect(lambda: self.set_status("resolved"))
        actions.addWidget(self.in_progress_btn)
        actions.addWidget(self.resolved_btn)
        self.delete_btn = Button("Delete ticket", "ghost", icon="trash")
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
        self.detail_text.setPlaceholderText("Select a ticket from the table to inspect the full record…")
        theme.enable_tabular(self.detail_text)
        self.panel.body.addWidget(self.detail_text, 0)

        # Widgets revealed only while a ticket is selected.
        self._selection_widgets = [self.inspector_scroll, self.detail_text]

        self.splitter.addWidget(self.panel)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        layout.addWidget(self.splitter, 1)

        self._clear_selection_state()
        self.reload()

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
        """Switch the stage filter (legacy ``"all"`` still shows every ticket)."""
        self.filter_mode = mode
        self.segments.set_current(mode)
        self.apply_filter()

    def apply_filter(self):
        needle = self.search.text().lower().strip()
        for r in range(self.table.rowCount()):
            row_data = self.rows[r] if r < len(self.rows) else {}
            st = _normalise_student(row_data)
            status = row_data.get("status", "")
            cat = str(row_data.get("category", "")).lower()
            desc = str(row_data.get("description", "")).lower()
            name = f"{st.get('first_name', '')} {st.get('last_name', '')}".lower()

            status_matches = self.filter_mode == "all" or status == self.filter_mode
            text_matches = needle in f"{cat} {desc} {name}"
            self.table.setRowHidden(r, not (status_matches and text_matches))
        self._update_view_state()

    def _update_view_state(self):
        """Table/empty-state swap + segment counts (never rebuilds the table)."""
        visible = sum(1 for r in range(self.table.rowCount()) if not self.table.isRowHidden(r))
        self.stack.setCurrentIndex(0 if visible else 1)
        self._update_segment_counts()

    def _update_segment_counts(self):
        counts = {key: 0 for key, _label in _STAGES}
        for r in self.rows:
            status = str(r.get("status", ""))
            if status in counts:
                counts[status] += 1
        for key, value in counts.items():
            self.segments.set_count(key, value)

    def _show_selection(self, has_selection: bool) -> None:
        """Toggle between the EmptyState and the selected-ticket widgets."""
        self.empty_panel.setVisible(not has_selection)
        for widget in self._selection_widgets:
            widget.setVisible(has_selection)

    # --------------------------------------------------- background plumbing
    def _show_banner(self, kind: str, title: str, message: str, mode: str = "action") -> None:
        """Show the page's inline banner with a human-readable message."""
        self._banner_mode = mode
        self.error_banner.set_kind(kind)
        self.error_banner.set_title(title)
        self.error_banner.set_message(message)
        self.error_banner.setVisible(True)

    def _hide_banner(self, mode: str | None = None) -> None:
        """Hide the banner, optionally only when it belongs to ``mode``."""
        if mode is None or self._banner_mode == mode:
            self._banner_mode = None
            self.error_banner.setVisible(False)

    def _set_actions_busy(self, busy: bool, active_button: Button | None = None) -> None:
        """Disable/restore the action controls while a background write runs."""
        self._actions_busy = busy
        if busy:
            for button in (self.in_progress_btn, self.resolved_btn, self.delete_btn):
                self._action_texts.setdefault(button, button.text())
                button.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            if active_button is not None:
                active_button.setText(_WORKING_TEXT)
            return

        for button, text in self._action_texts.items():
            try:
                button.setText(text)
            except RuntimeError:  # widget already destroyed (window closing)
                pass
        self._action_texts.clear()
        self.refresh_btn.setEnabled(True)
        self._apply_action_buttons(self.selected())

    def _apply_action_buttons(self, row: dict | None) -> None:
        """Enable status/delete controls for the selected ticket (or clear them)."""
        if row is None:
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip("Select a ticket to delete it.")
            self.in_progress_btn.setEnabled(False)
            self.in_progress_btn.setToolTip("Select a ticket to dispatch a technician.")
            self.resolved_btn.setEnabled(False)
            self.resolved_btn.setToolTip("Select a ticket to close it as resolved.")
            return

        if self._actions_busy:
            for button in (self.in_progress_btn, self.resolved_btn, self.delete_btn):
                button.setEnabled(False)
                button.setToolTip("An action is already in progress for this queue.")
            return

        status = str(row.get("status", "pending"))
        if status == "resolved":
            self.in_progress_btn.setEnabled(False)
            self.in_progress_btn.setToolTip("This ticket is already resolved.")
            self.resolved_btn.setEnabled(False)
            self.resolved_btn.setToolTip("This ticket is already resolved.")
        elif status == "in_progress":
            self.in_progress_btn.setEnabled(False)
            self.in_progress_btn.setToolTip("A technician is already dispatched for this ticket.")
            self.resolved_btn.setEnabled(True)
            self.resolved_btn.setToolTip("")
        else:
            self.in_progress_btn.setEnabled(True)
            self.in_progress_btn.setToolTip("")
            self.resolved_btn.setEnabled(True)
            self.resolved_btn.setToolTip("")

        self.delete_btn.setEnabled(True)
        self.delete_btn.setToolTip("")

    def _start_action(
        self,
        key: str,
        fn,
        *,
        button: Button | None,
        working_message: str,
        on_success,
        on_failed,
    ) -> bool:
        """Run a write in the background; return False if one is already running."""
        if self._actions_busy or self.tasks.is_busy(_ACTION_KEY):
            return False

        self._set_actions_busy(True, button)
        self._show_banner("info", _WORKING_TEXT, working_message, mode="action")
        started = self.tasks.run(
            key,
            fn,
            on_success=on_success,
            on_failed=on_failed,
            on_finished=self._on_action_finished,
        )
        if not started:
            self._set_actions_busy(False)
        return started

    def _on_action_finished(self) -> None:
        if self._closing:
            self._actions_busy = False
            return
        self._set_actions_busy(False)
        if self._reload_after_action:
            self._reload_after_action = False
            # The authoritative rows are fetched in the background; the write
            # itself already succeeded, so a refresh failure cannot roll it back.
            self.reload()

    # -------------------------------------------------------- live sync data
    def apply_live_data(self, rows: list[dict], force: bool = False):
        old_keys = [(r.get("id"), r.get("status")) for r in self.rows]
        new_keys = [(r.get("id"), r.get("status")) for r in rows]
        if not force and old_keys == new_keys and len(rows) == len(self.rows):
            return

        selected_id = self.selected().get("id") if self.selected() else None
        self.rows = rows
        self.table.setRowCount(len(self.rows))
        restore_row = -1

        for i, r in enumerate(self.rows):
            if r.get("id") == selected_id:
                restore_row = i
            st = _normalise_student(r)
            status = r.get("status", "pending")
            status_kind, status_text = _status_meta(status)
            category = str(r.get("category") or "other")

            cat_item = QTableWidgetItem(category.capitalize())
            cat_item.setIcon(get_icon(_category_icon(category), 14, C("text-secondary")))
            student_item = QTableWidgetItem(f"{st.get('first_name', '')} {st.get('last_name', '')}".strip())
            status_holder = _cell_widget(StatusPill(status_kind, status_text))
            status_item = _pill_item(status_text, status_holder)
            date_item = QTableWidgetItem(_fmt_date(r.get("created_at")))

            self.table.setItem(i, 0, cat_item)
            self.table.setItem(i, 1, student_item)
            self.table.setItem(i, 2, status_item)
            self.table.setItem(i, 3, date_item)
            self.table.setCellWidget(i, 2, status_holder)

        if restore_row >= 0:
            self.table.selectRow(restore_row)
        else:
            self._clear_selection_state()

        self.apply_filter()

    def _clear_selection_state(self):
        """No selected ticket: clear the inspector, the photo and the actions."""
        self._cleanup_thumb_worker()
        self._current_pixmap = None
        self._current_photo_url = None
        self._photo_fetch_failed = False
        self._photo_loading = False
        self.photo_skeleton.setVisible(False)
        self.zoom_cue.setVisible(False)
        self.detail_text.clear()
        self.photo_label.clear()
        self.photo_label.setText("No ticket selected")
        self.photo_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.photo_label.setToolTip("")
        self.delete_btn.setEnabled(False)
        self.delete_btn.setToolTip("Select a ticket to delete it.")
        self.in_progress_btn.setEnabled(False)
        self.in_progress_btn.setToolTip("Select a ticket to dispatch a technician.")
        self.resolved_btn.setEnabled(False)
        self.resolved_btn.setToolTip("Select a ticket to close it as resolved.")
        self._show_selection(False)

    def _fetch_rows(self) -> list[dict]:
        """Network read: the maintenance queue (call from a worker thread)."""
        resp = self.client.table("maintenance_reports") \
            .select("*, students(first_name, last_name, card_id)") \
            .order("created_at", desc=True).execute()
        data = getattr(resp, "data", None)
        return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []

    def _load_sync(self) -> None:
        """Initial page load only; keeps the constructor contract synchronous."""
        try:
            rows = self._fetch_rows()
        except Exception as exc:  # noqa: BLE001 - reported inline
            self._show_banner(
                "error",
                "Maintenance queue could not be loaded",
                f"The table is showing the last data received ({human_error(exc)}). "
                "Use Refresh to try again.",
                mode="load",
            )
            return
        self._hide_banner("load")
        self.apply_live_data(rows)

    def _on_reload_success(self, rows, generation: int) -> None:
        if generation != self._data_generation or self._closing:
            return
        self._hide_banner("reload")
        self.apply_live_data(rows)

    def _on_reload_failed(self, message: str) -> None:
        self._show_banner(
            "error",
            "Maintenance queue could not be loaded",
            f"The table is showing the last data received ({message}). "
            "Use Refresh to try again.",
            mode="reload",
        )

    def _on_reload_finished(self) -> None:
        if not self._actions_busy:
            self.refresh_btn.setEnabled(True)

    def _reload_async(self) -> None:
        if self.tasks.is_busy(_RELOAD_KEY) or self._actions_busy:
            return
        generation = self._data_generation
        started = self.tasks.run(
            _RELOAD_KEY,
            self._fetch_rows,
            on_success=lambda rows: self._on_reload_success(rows, generation),
            on_failed=self._on_reload_failed,
            on_finished=self._on_reload_finished,
        )
        if not started:
            return
        self.refresh_btn.setEnabled(False)
        self._show_banner("info", _WORKING_TEXT, "Refreshing the maintenance queue…", mode="reload")

    def reload(self):
        """Refresh the queue; the first (constructor) call stays synchronous."""
        if not self._loaded_once:
            self._loaded_once = True
            self._load_sync()
            return
        self._reload_async()

    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None


    # -------------------------------------------------------------- inspector
    def show_detail(self):
        self._cleanup_thumb_worker()
        self._photo_req_id += 1
        current_req = self._photo_req_id
        self._current_pixmap = None
        self._current_photo_url = None
        self._photo_fetch_failed = False
        self._photo_loading = False
        self.photo_skeleton.setVisible(False)
        self.zoom_cue.setVisible(False)

        r = self.selected()
        if not r:
            self._clear_selection_state()
            return

        status = str(r.get("status", "pending"))
        status_kind, status_text = _status_meta(status)
        stage = _stage_index(status)
        category = str(r.get("category") or "other")
        st = _normalise_student(r)
        name = f"{st.get('first_name', '')} {st.get('last_name', '')}".strip() or "Unnamed resident"

        # Lifecycle stepper: the current stage is marked, earlier stages done.
        self.stepper.set_current(stage)
        self.stepper.set_states([index < stage for index in range(len(_STAGES))])

        # Category + status header.
        self.category_icon.setPixmap(get_pixmap(_category_icon(category), S("size-icon"), C("navy-800")))
        self.category_label.setText(category.capitalize())
        self.status_pill.set_kind(status_kind, status_text)

        # Resident identity.
        self.avatar.set_name(name)
        self.name_label.setText(name)
        self.card_label.setText(f"Card ID {st.get('card_id') or '—'}")

        # Key facts (raw data only).
        self.facts.set_rows([
            ("Room", _room_text(r, st)),
            ("Submitted", _fmt_date(r.get("created_at"))),
            ("Resolved", _fmt_date(r.get("updated_at")) if status == "resolved" else "—"),
        ])

        # Status actions: disabled with the reason in the tooltip.
        self._apply_action_buttons(r)

        # Staff / dispatch note.
        note = str(r.get("staff_note") or "").strip()
        self.note_block.set_text(f"“{note}”" if note else "No technician notes recorded yet.")

        # Plain-text record block (the desk reference for inquiries).
        self.detail_text.setPlainText(
            f"CATEGORY: {category.upper()}\n"
            f"Resident: {name} (Card ID: {st.get('card_id', '—')})\n"
            f"Status: {status_text.upper()}\n"
            f"Submitted: {_fmt_stamp(r.get('created_at'))}\n"
            f"Last update: {_fmt_stamp(r.get('updated_at'))}\n"
            f"\n"
            f"DESCRIPTION:\n{r.get('description', '')}\n"
            f"\n"
            f"STAFF / DISPATCH NOTE:\n{r.get('staff_note') or 'No technician notes recorded.'}"
        )

        self._show_selection(True)

        # Fault photo (signed URL + background fetch, stale responses dropped).
        self.photo_label.clear()
        self.photo_label.setCursor(Qt.CursorShape.PointingHandCursor)
        if not r.get("photo_path"):
            self.photo_label.setText(_NO_PHOTO_TEXT)
            self.photo_label.setToolTip("Click to view fault details")
            return

        self.photo_label.setText("Loading photo…")
        self.photo_label.setToolTip("Loading photo preview…")
        self._photo_loading = True
        self.photo_skeleton.setVisible(True)

        url = None
        try:
            signed = self.client.storage.from_("maintenance-photos").create_signed_url(r["photo_path"], 300)
            url = (signed or {}).get("signedURL") or (signed or {}).get("signedUrl")
        except Exception:
            url = None

        if not url:
            self._photo_loading = False
            self.photo_skeleton.setVisible(False)
            self._photo_fetch_failed = True
            self.photo_label.setText("Photo unavailable")
            self.photo_label.setToolTip("Failed to retrieve signed URL")
            return

        self._current_photo_url = url

        def on_loaded(data: bytes, req=current_req, img_url=url):
            if self._photo_req_id != req:
                return
            self._photo_loading = False
            self.photo_skeleton.setVisible(False)
            pix = QPixmap()
            if pix.loadFromData(data) and not pix.isNull() and pix.width() > 0 and pix.height() > 0:
                self._current_pixmap = pix
                self._current_photo_url = img_url
                scaled = pix.scaled(
                    S("space-12") * 8, S("space-12") * 3,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.photo_label.setPixmap(scaled)
                self.photo_label.setCursor(Qt.CursorShape.PointingHandCursor)
                self.photo_label.setToolTip("Click to open full-size photo viewer")
            else:
                self._photo_fetch_failed = True
                self.photo_label.setText("Photo preview unavailable")

        def on_failed(err_msg: str, req=current_req):
            if self._photo_req_id != req:
                return
            self._photo_loading = False
            self.photo_skeleton.setVisible(False)
            self._photo_fetch_failed = True
            self.photo_label.setText("Failed to load photo")

        worker = PhotoFetchWorker(url, parent=None)
        worker.finished.connect(worker.deleteLater)
        self._thumb_worker = worker
        worker.loaded.connect(on_loaded)
        worker.failed.connect(on_failed)
        worker.start()

    def eventFilter(self, obj, event):  # noqa: N802 - Qt API
        """Hover zoom cue over the thumbnail (only while a photo is loaded)."""
        if obj is self.photo_label:
            if event.type() == QEvent.Type.Enter:
                self.zoom_cue.setVisible(self._current_pixmap is not None)
            elif event.type() == QEvent.Type.Leave:
                self.zoom_cue.setVisible(False)
        return super().eventFilter(obj, event)

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

    def closeEvent(self, event):  # noqa: N802 - Qt API
        self._closing = True
        worker = self._thumb_worker
        self._cleanup_thumb_worker()
        if worker is not None and worker.isRunning():
            worker.wait(2000)
        super().closeEvent(event)

    def _cleanup_thumb_worker(self):
        if self._thumb_worker is not None:
            try:
                self._thumb_worker.loaded.disconnect()
                self._thumb_worker.failed.disconnect()
            except RuntimeError:
                pass
            self._thumb_worker.stop()
            self._thumb_worker = None

    def on_row_double_clicked(self, row: int, col: int):
        r = self.selected()
        if not r or not r.get("students"):
            return
        if self._actions_busy or self._info_busy or self.tasks.is_busy(_INFO_KEY):
            return

        st = dict(_normalise_student(r))
        self._info_busy = True
        started = self.tasks.run(
            _INFO_KEY,
            lambda: official_lookup(self.client),
            on_success=lambda roster: self._show_student_card(st, roster),
            on_failed=self._on_info_failed,
            on_finished=self._on_info_finished,
        )
        if not started:
            self._info_busy = False

    def _show_student_card(self, student: dict, roster_map) -> None:
        if self._closing:
            return
        roster_match = (roster_map or {}).get(student.get("card_id"))
        dlg = StudentInfoCardDialog(self, student, roster_match)
        try:
            dlg.exec()
        finally:
            dlg.deleteLater()

    def _on_info_failed(self, message: str) -> None:
        self._show_banner(
            "error",
            "Resident record could not be loaded",
            f"The roster lookup failed ({message}). The maintenance queue is unchanged.",
            mode="info",
        )

    def _on_info_finished(self) -> None:
        self._info_busy = False

    # ------------------------------------------------------------- decisions
    def _update_status_worker(self, ticket_id, status: str, note_val):
        """Worker: resolve the signed-in staff member, then update the ticket."""
        update_data = {"status": status, "staff_note": note_val}
        try:
            user = getattr(self.client.auth.get_user(), "user", None)
        except Exception:  # noqa: BLE001 - auth is best-effort, update still runs
            user = None
        if user:
            update_data["handled_by"] = user.id
        try:
            self.client.table("maintenance_reports").update(update_data) \
                .eq("id", ticket_id).execute()
        except Exception as exc:  # noqa: BLE001 - re-raised with context
            raise RuntimeError(f"Network error updating ticket: {exc}") from exc
        return update_data

    def _delete_ticket_worker(self, ticket_id):
        """Worker: delete the ticket."""
        try:
            self.client.table("maintenance_reports").delete() \
                .eq("id", ticket_id).execute()
        except Exception as exc:  # noqa: BLE001 - re-raised with context
            raise RuntimeError(f"Failed to delete ticket: {exc}") from exc
        return True

    def _on_status_success(self, update_data, ticket_id, status: str) -> None:
        self._data_generation += 1
        for row in self.rows:
            if row.get("id") == ticket_id:
                row.update(update_data)
                break
        self.apply_live_data(self.rows, force=True)
        label = status.replace("_", " ")
        self._show_banner(
            "success",
            "Status updated",
            f"Maintenance ticket updated to '{label}'.",
            mode="action",
        )
        self._reload_after_action = True

    def _on_status_failed(self, message: str) -> None:
        self._show_banner(
            "error",
            "Ticket could not be updated",
            f"The maintenance ticket was not changed. {message}",
            mode="action",
        )

    def _on_delete_success(self, deleted, ticket_id) -> None:
        self._data_generation += 1
        self.rows = [row for row in self.rows if row.get("id") != ticket_id]
        self.apply_live_data(self.rows, force=True)
        self._show_banner(
            "success",
            "Ticket deleted",
            "Maintenance ticket deleted successfully.",
            mode="action",
        )
        self._reload_after_action = True

    def _on_delete_failed(self, message: str) -> None:
        self._show_banner(
            "error",
            "Ticket could not be deleted",
            f"The maintenance ticket was not removed. {message}",
            mode="action",
        )

    def set_status(self, status: str):
        if self._actions_busy or self._info_busy or self.tasks.is_busy(_ACTION_KEY):
            return

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

        ticket_id = r.get("id")
        if ticket_id is None:
            return

        note_val = note.strip() or default_note or None
        button = self.resolved_btn if status == "resolved" else self.in_progress_btn
        started = self._start_action(
            _ACTION_KEY,
            lambda: self._update_status_worker(ticket_id, status, note_val),
            button=button,
            working_message=f"Updating maintenance ticket to '{status.replace('_', ' ')}'…",
            on_success=lambda update_data: self._on_status_success(
                update_data, ticket_id, status
            ),
            on_failed=self._on_status_failed,
        )
        if not started:
            return

    def on_delete(self):
        if self._actions_busy or self._info_busy or self.tasks.is_busy(_ACTION_KEY):
            return

        t = self.selected()
        if not t:
            return

        ticket_id = str(t.get("id", ""))[:8]
        category = str(t.get("category") or "—").capitalize()
        status_text = _status_meta(t.get("status", "pending"))[1]
        confirmed = ConfirmDialog.ask(
            self,
            "Delete maintenance ticket",
            f"Permanently delete maintenance ticket #{ticket_id}?\n\n"
            f"Category: {category}\nStatus: {status_text}\n"
            "This removes the resident report and its fault photo.",
            confirm_text="Delete ticket",
        )
        if not confirmed:
            return

        raw_id = t.get("id")
        if raw_id is None:
            return
        self._start_action(
            _ACTION_KEY,
            lambda: self._delete_ticket_worker(raw_id),
            button=self.delete_btn,
            working_message="Deleting the maintenance ticket…",
            on_success=lambda deleted: self._on_delete_success(deleted, raw_id),
            on_failed=self._on_delete_failed,
        )


