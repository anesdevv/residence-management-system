"""RÉSIVO — Overview dashboard (visual layer only, docs/DESIGN.md §6–§7).

Greeting, a KPI row built from the counters the page already fetches, an
occupancy card, a "needs attention" queue list and the latest live-sync
events. Every number comes from an existing call:

``_count()`` query chains, the ``maintenance_reports`` count, the
``room_occupancy`` map and the counts handed over by
``MainWindow.on_live_sync_tick`` through ``apply_live_data``. Nothing is
invented: a value that cannot be derived from those calls is shown as a muted
"not available" instead of a guess.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    from i18n import format_date, format_number, format_percent, t, tn
except ImportError:
    from desktop.i18n import format_date, format_number, format_percent, t, tn

from ...client import room_occupancy, stored_user_display_name
from .. import theme
from ..components import (
    Avatar,
    Card,
    EmptyState,
    IconButton,
    InlineBanner,
    PageHeader,
    Skeleton,
    StatCard,
    StatusPill,
)
from ..tasks import TaskRunner
from ..icons import get_pixmap
from ..theme import C, S

# Institutional caption used by the desktop shell (main_window sidebar).
_RESIDENCE_NAME = "Cité Universitaire · Tlemcen"

_METRIC_KINDS = {
    "pending": "pending",
    "reports": "progress",
    "requests": "review",
    "occupancy": "ok",
}
_MAX_EVENTS = 4


def _metric_label(key: str) -> str:
    labels = {
        "pending": t("overview.metric_pending"),
        "reports": t("overview.metric_reports"),
        "requests": t("overview.metric_requests"),
        "occupancy": t("overview.metric_occupancy"),
    }
    return labels.get(key, key.title())


def _clear_layout(layout) -> None:
    """Remove and delete every widget/layout currently in ``layout``."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
            continue
        child = item.layout()
        if child is not None:
            _clear_layout(child)


def _staff_display_name(client) -> str:
    """Signed-in staff name from the stored session (local read, no network call).

    Mirrors the shell's user card: session metadata first (``full_name`` /
    ``name``), then the email local part. Returns ``""`` when nothing usable is
    available so the greeting degrades to a name-free line.
    """
    return stored_user_display_name(client, "")


def _greeting_word() -> str:
    """Time-of-day greeting from the local clock."""
    hour = datetime.now().hour
    if hour < 12:
        return t("overview.greeting_morning")
    if hour < 18:
        return t("overview.greeting_afternoon")
    return t("overview.greeting_evening")


def _muted(text: str, word_wrap: bool = True) -> QLabel:
    """Secondary line used for "not available" and empty states inside cards."""
    label = QLabel(text)
    theme.apply_role(label, "small")
    label.setWordWrap(word_wrap)
    return label


def _muted_row(icon_name: str, text: str) -> QWidget:
    """Small icon + sentence row for unavailable / all-clear states."""
    row = QWidget()
    line = QHBoxLayout(row)
    line.setContentsMargins(0, 0, 0, 0)
    line.setSpacing(S("space-2"))
    icon = QLabel()
    icon.setPixmap(get_pixmap(icon_name, 16, C("text-muted")))
    icon.setFixedWidth(18)
    line.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
    line.addWidget(_muted(text), 1)
    return row


class _AttentionRow(QWidget):
    """One non-interactive queue row: status pill + explanation."""

    def __init__(self, kind: str, pill_label: str, detail: str, parent=None):
        super().__init__(parent)
        line = QHBoxLayout(self)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(S("space-3"))
        line.addWidget(StatusPill(kind, pill_label), 0, Qt.AlignmentFlag.AlignTop)
        line.addWidget(_muted(detail), 1)


class _EventRow(QWidget):
    """One live-sync event: status pill + sentence + receipt time."""

    def __init__(self, kind: str, pill_label: str, text: str, stamp: str, parent=None):
        super().__init__(parent)
        line = QHBoxLayout(self)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(S("space-3"))
        line.addWidget(StatusPill(kind, pill_label), 0, Qt.AlignmentFlag.AlignTop)
        line.addWidget(_muted(text), 1)
        time_label = QLabel(stamp)
        theme.apply_role(time_label, "small")
        theme.enable_tabular(time_label)
        time_label.setToolTip(t("overview.event_received_at", stamp=stamp))
        line.addWidget(time_label, 0, Qt.AlignmentFlag.AlignTop)


class OverviewPage(QWidget):
    """Operations overview: KPIs, occupancy, queues and live-sync events."""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self._metrics: dict[str, int | None] | None = None
        self._events: list[tuple[str, str, str, str]] = []
        self._last_tick: str | None = None
        self._loading = False
        # Monotonic revision of data delivered by live sync.  A reload snapshot
        # that started before a tick is older than that tick and must not
        # overwrite it when it lands.
        self._live_revision = 0
        self._reload_revision = 0
        self.tasks = TaskRunner(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer.addWidget(scroll)

        holder = QWidget()
        holder.setProperty("background", "canvas")
        scroll.setWidget(holder)

        layout = QVBoxLayout(holder)
        layout.setContentsMargins(S("space-8"), S("space-8"), S("space-8"), S("space-8"))
        layout.setSpacing(S("space-6"))

        self.header = PageHeader(
            t("overview.title"),
            t("overview.subtitle", residence=_RESIDENCE_NAME),
        )
        self.refresh_btn = IconButton("refresh", t("overview.refresh_tooltip"))
        self.refresh_btn.clicked.connect(self.reload)
        self.header.actions.addWidget(self.refresh_btn)
        layout.addWidget(self.header)

        self.error_banner = InlineBanner(
            "error",
            title=t("overview.error_title"),
            message=t("overview.error_desc"),
        )
        self.error_banner.setVisible(False)
        layout.addWidget(self.error_banner)

        # --- greeting line ------------------------------------------------
        greeting_row = QHBoxLayout()
        greeting_row.setSpacing(S("space-3"))
        staff_name = _staff_display_name(client)
        self.avatar = Avatar(staff_name or t("overview.default_staff"), size=S("size-control"))
        greeting_row.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignVCenter)
        greeting_column = QVBoxLayout()
        greeting_column.setSpacing(2)
        greeting_text = (
            t("overview.greeting_with_name", greeting=_greeting_word(), name=staff_name)
            if staff_name
            else _greeting_word()
        )
        self.greeting_label = QLabel(greeting_text)
        theme.apply_role(self.greeting_label, "h2")
        greeting_column.addWidget(self.greeting_label)
        self.tick_label = QLabel(t("overview.tick_waiting"))
        theme.apply_role(self.tick_label, "small")
        greeting_column.addWidget(self.tick_label)
        greeting_row.addLayout(greeting_column, 1)
        layout.addLayout(greeting_row)

        # --- loading skeleton (shown while reload() is in flight) ---------
        self.skeleton = Skeleton(rows=6)
        self.skeleton.setVisible(False)
        layout.addWidget(self.skeleton)

        # --- content ------------------------------------------------------
        self.content = QWidget()
        content = QVBoxLayout(self.content)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(S("space-6"))

        grid = QGridLayout()
        grid.setSpacing(S("space-4"))
        self.pending_card = StatCard(t("overview.kpi_pending_title"), "clock", accent="gold")
        self.pending_card.set_hint(t("overview.kpi_pending_hint"))
        self.reports_card = StatCard(t("overview.kpi_reports_title"), "wrench", accent="teal")
        self.reports_card.set_hint(t("overview.kpi_reports_hint"))
        self.requests_card = StatCard(t("overview.kpi_requests_title"), "arrow-left-right", accent="review")
        self.requests_card.set_hint(t("overview.kpi_requests_hint"))
        self.occupancy_card = StatCard(t("overview.kpi_occupancy_title"), "bed", accent="green")
        self.occupancy_card.set_hint(t("overview.kpi_occupancy_hint"))
        grid.addWidget(self.pending_card, 0, 0)
        grid.addWidget(self.reports_card, 0, 1)
        grid.addWidget(self.requests_card, 1, 0)
        grid.addWidget(self.occupancy_card, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        content.addLayout(grid)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(S("space-4"))

        self.occupancy_block_card = Card(
            t("overview.occupancy_card_title"),
            t("overview.occupancy_card_desc"),
            icon="building",
        )
        self.occupancy_rows = self.occupancy_block_card.body
        cards_row.addWidget(self.occupancy_block_card, 1)

        self.attention_card = Card(
            t("overview.attention_card_title"),
            t("overview.attention_card_desc"),
            icon="alert-triangle",
        )
        self.attention_rows = self.attention_card.body
        cards_row.addWidget(self.attention_card, 1)
        content.addLayout(cards_row)

        self.events_card = Card(
            t("overview.events_card_title"),
            t("overview.events_card_desc"),
            icon="bell",
        )
        self.events_rows = self.events_card.body
        content.addWidget(self.events_card)

        layout.addWidget(self.content)
        layout.addStretch(0)

        self._render_occupancy()
        self._render_attention()
        self._render_events()
        self.reload()

    # ------------------------------------------------------------------ data
    def _count(self, table, **filters) -> int:
        """Count rows; failures propagate to the refresh task, not to a fake 0."""
        q = self.client.table(table).select("id", count="exact")
        for col, val in filters.items():
            q = q.eq(col, val)
        return q.execute().count or 0

    def _fetch_snapshot(self):
        """Fetch dashboard counters via overview_stats RPC, with query fallback."""
        try:
            resp = self.client.rpc("overview_stats", {}).execute()
            data = getattr(resp, "data", None)
            if isinstance(data, dict):
                return (
                    int(data.get("pending", 0)),
                    int(data.get("reports", 0)),
                    int(data.get("requests", 0)),
                    int(data.get("occupancy", 0)),
                )
        except Exception:  # noqa: BLE001 - fallback to individual queries if unmigrated
            pass

        pending = self._count("students", status="pending")
        reports = (
            self.client.table("maintenance_reports")
            .select("id", count="exact")
            .neq("status", "resolved")
            .execute()
            .count
            or 0
        )
        requests = self._count("room_change_requests", status="pending")
        occupancy = sum(room_occupancy(self.client, strict=True).values())
        return pending, reports, requests, occupancy

    def apply_live_data(
        self,
        pending: int,
        reports: int,
        requests: int,
        occupancy: int | None = None,
        live: bool = True,
    ):
        if live:
            self._live_revision += 1
        self.pending_card.set_value(pending)
        self.reports_card.set_value(reports)
        self.requests_card.set_value(requests)
        if occupancy is not None:
            self.occupancy_card.set_value(occupancy)

        incoming: dict[str, int | None] = {
            "pending": int(pending or 0),
            "reports": int(reports or 0),
            "requests": int(requests or 0),
            "occupancy": occupancy,
        }
        previous = self._metrics
        changed: list[str] = []
        if previous is None:
            # First snapshot: prime the diff without logging an event.
            self._metrics = dict(incoming)
            changed = list(incoming)
        else:
            for key, value in incoming.items():
                if key == "occupancy" and value is None:
                    continue
                if value != previous.get(key):
                    self._append_event(key, previous.get(key), value)
                    changed.append(key)
            for key, value in incoming.items():
                if key == "occupancy" and value is None:
                    continue
                self._metrics[key] = value

        if live:
            self._last_tick = datetime.now().strftime("%H:%M:%S")
            self._update_tick_label()
        if changed:
            self._render_occupancy()
            self._render_attention()
            self._render_events()

    def reload(self):
        """Refresh on the thread pool; the greeting/first paint never blocks."""
        if self._loading:
            return
        self._loading = True
        self._reload_revision = self._live_revision
        self.error_banner.setVisible(False)
        self.refresh_btn.setEnabled(False)
        self._set_loading(True)
        started = self.tasks.run(
            "overview-reload",
            self._fetch_snapshot,
            on_success=self._on_reload_success,
            on_failed=self._on_reload_failed,
            on_finished=self._on_reload_finished,
        )
        if not started:
            self._on_reload_finished()

    def _on_reload_success(self, snapshot):
        if self._live_revision != self._reload_revision:
            # A live-sync tick arrived while this snapshot was in flight.  Keep
            # the newer live counts but merge in any field the tick omitted
            # (notably occupancy), rather than discarding the whole snapshot.
            latest = self._metrics or {}
            snapshot = (
                latest.get("pending", snapshot[0]),
                latest.get("reports", snapshot[1]),
                latest.get("requests", snapshot[2]),
                latest.get("occupancy")
                if latest.get("occupancy") is not None
                else snapshot[3],
            )
        self.apply_live_data(*snapshot, live=False)

    def _on_reload_failed(self, message: str):
        self.error_banner.set_message(
            t("overview.reload_failed_msg", message=message)
        )
        self.error_banner.setVisible(True)

    def _on_reload_finished(self):
        self._loading = False
        self.refresh_btn.setEnabled(True)
        self._set_loading(False)

    # ------------------------------------------------------------ rendering
    def _set_loading(self, loading: bool) -> None:
        """Swap the content for the Skeleton while the worker fetches counters."""
        self.skeleton.setVisible(loading)
        self.content.setVisible(not loading)

    def _update_tick_label(self) -> None:
        if self._last_tick:
            self.tick_label.setText(t("overview.tick_updated", time=self._last_tick))
        else:
            self.tick_label.setText(t("overview.tick_waiting"))

    def _append_event(self, key: str, old, new) -> None:
        label = _metric_label(key)
        new_fmt = format_number(new) if isinstance(new, (int, float)) else str(new)
        old_fmt = format_number(old) if isinstance(old, (int, float)) else (str(old) if old is not None else "—")
        pill = t("overview.event_pill", label=label, value=new_fmt)
        text = t("overview.event_text", label=label, old=old_fmt, new=new_fmt)
        self._events.insert(0, (_METRIC_KINDS.get(key, "neutral"), pill, text, self._stamp()))
        del self._events[_MAX_EVENTS:]

    @staticmethod
    def _stamp() -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _render_occupancy(self) -> None:
        """Beds occupied per block from the calls this page already makes.

        ``room_occupancy()`` returns ``room_id -> occupied beds`` and the page
        holds no block/capacity data, so the per-block breakdown is reported as
        unavailable rather than guessed.
        """
        _clear_layout(self.occupancy_rows)
        occupied = (self._metrics or {}).get("occupancy")
        if occupied is None:
            self.occupancy_rows.addWidget(
                _muted_row("info", t("overview.occupancy_not_fetched"))
            )
            return
        self.occupancy_rows.addWidget(
            _muted_row(
                "bed",
                tn("overview.occupancy_beds_count", count=occupied, count_fmt=format_number(occupied)),
            )
        )
        self.occupancy_rows.addWidget(
            _muted_row("info", t("overview.occupancy_block_unavailable"))
        )

    def _render_attention(self) -> None:
        """Non-interactive queue list fed by the live counters (no row detail)."""
        _clear_layout(self.attention_rows)
        metrics = self._metrics or {}
        queues = [
            ("pending", "pending", "pending", t("overview.attention_pending_detail")),
            ("reports", "progress", "open", t("overview.attention_reports_detail")),
            ("requests", "review", "waiting", t("overview.attention_requests_detail")),
        ]
        visible = []
        for key, kind, word, detail in queues:
            cnt = int(metrics.get(key) or 0)
            if cnt > 0:
                if word == "pending":
                    pill_label = tn("overview.attention_pending_pill", count=cnt, count_fmt=format_number(cnt))
                elif word == "open":
                    pill_label = tn("overview.attention_reports_pill", count=cnt, count_fmt=format_number(cnt))
                else:
                    pill_label = tn("overview.attention_requests_pill", count=cnt, count_fmt=format_number(cnt))
                visible.append((kind, pill_label, detail))

        if not visible:
            self.attention_rows.addWidget(_muted_row("check-circle", t("overview.attention_all_clear")))
            return
        for kind, pill_label, detail in visible:
            self.attention_rows.addWidget(_AttentionRow(kind, pill_label, detail))
        self.attention_rows.addWidget(
            _muted(t("overview.attention_footer_note"))
        )

    def _render_events(self) -> None:
        """Newest-first snapshot of live-sync changes (counts + receipt time)."""
        _clear_layout(self.events_rows)
        if not self._events:
            self.events_rows.addWidget(
                EmptyState(
                    "bell",
                    t("overview.events_empty_title"),
                    t("overview.events_empty_desc"),
                )
            )
            return
        for kind, pill_label, text, stamp in self._events:
            self.events_rows.addWidget(_EventRow(kind, pill_label, text, stamp))
