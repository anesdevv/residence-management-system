"""Debug-only startup timeline and ghost-window instrumentation.

Controlled exclusively by environment variables so production runs pay zero cost:
- ``RESIVO_DEBUG_STARTUP=1``: enables timeline marks, 50 ms GUI heartbeat gap
  tracking, and the ghost-window event filter.
- ``RESIVO_DEBUG_WINDOWS=1``: enables only the ghost-window event filter (used
  during automated regression checks and manual debugging).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
import time
import traceback
from typing import Iterable

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication, QWidget

_log = logging.getLogger("resivo.startup")

_EVENT_NAMES = {
    QEvent.Type.Show: "Show",
    QEvent.Type.ShowToParent: "ShowToParent",
    QEvent.Type.WinIdChange: "WinIdChange",
}

DEFAULT_WINDOW_WHITELIST: frozenset[str] = frozenset({"LoginWindow", "MainWindow"})


def startup_debug_enabled() -> bool:
    return os.environ.get("RESIVO_DEBUG_STARTUP", "").strip() == "1"


def ghost_probe_enabled() -> bool:
    return startup_debug_enabled() or os.environ.get("RESIVO_DEBUG_WINDOWS", "").strip() == "1"


@dataclass(frozen=True)
class TimelineEntry:
    name: str
    ts: float
    from_start_ms: float
    delta_ms: float


class StartupTimeline(QObject):
    """Records perf_counter startup markers and measures 50 ms GUI heartbeat gaps."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.reset("init", start_heartbeat=False)

    def reset(self, reason: str = "startup", *, start_heartbeat: bool = True) -> None:
        now = time.perf_counter()
        self.reason = reason
        self._start_ts = now
        self._last_ts = now
        self.entries: list[TimelineEntry] = []
        self._summary_logged = False
        self.heartbeat_gaps_ms: list[float] = []
        self.max_heartbeat_gap_ms: float = 0.0
        self._hb_last_ts = now
        self._stop_heartbeat_timer()
        if start_heartbeat and startup_debug_enabled():
            self._start_heartbeat_timer()

    def _start_heartbeat_timer(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        timer = QTimer(self)
        timer.setInterval(50)
        self._hb_last_ts = time.perf_counter()
        timer.timeout.connect(self._on_heartbeat_tick)
        timer.start()
        self._hb_timer = timer

    def _stop_heartbeat_timer(self) -> None:
        timer = getattr(self, "_hb_timer", None)
        if timer is not None:
            try:
                timer.stop()
                timer.deleteLater()
            except RuntimeError:
                pass
            self._hb_timer = None

    def _on_heartbeat_tick(self) -> None:
        now = time.perf_counter()
        gap_ms = (now - self._hb_last_ts) * 1000.0
        self._hb_last_ts = now
        self.heartbeat_gaps_ms.append(gap_ms)
        if gap_ms > self.max_heartbeat_gap_ms:
            self.max_heartbeat_gap_ms = gap_ms

    def mark(self, name: str, *, force: bool = False) -> TimelineEntry | None:
        if not force and not startup_debug_enabled():
            return None
        now = time.perf_counter()
        from_start_ms = (now - self._start_ts) * 1000.0
        delta_ms = (now - self._last_ts) * 1000.0
        self._last_ts = now
        # Check heartbeat synchronously around markers too so a synchronous block
        # shows up immediately if the event loop never ran between marks.
        if getattr(self, "_hb_timer", None) is not None:
            gap_ms = (now - self._hb_last_ts) * 1000.0
            if gap_ms > self.max_heartbeat_gap_ms:
                self.max_heartbeat_gap_ms = gap_ms
        entry = TimelineEntry(
            name=name,
            ts=now,
            from_start_ms=from_start_ms,
            delta_ms=delta_ms,
        )
        self.entries.append(entry)
        _log.info(
            "[STARTUP] %-28s t=%8.1f ms  (+%7.1f ms)",
            name,
            from_start_ms,
            delta_ms,
        )
        return entry

    def stop_heartbeat(self) -> float:
        if getattr(self, "_hb_timer", None) is not None:
            self._on_heartbeat_tick()
        self._stop_heartbeat_timer()
        return self.max_heartbeat_gap_ms

    def format_summary(self) -> str:
        lines = [
            f"=== STARTUP TIMELINE ({self.reason}) ===",
            f"Max 50 ms GUI heartbeat gap: {self.max_heartbeat_gap_ms:.1f} ms",
            "| Marker | Elapsed (ms) | Step Delta (ms) |",
            "|---|---:|---:|",
        ]
        for item in self.entries:
            lines.append(
                f"| `{item.name}` | {item.from_start_ms:.1f} | {item.delta_ms:.1f} |"
            )
        return "\n".join(lines)

    def dump_summary(self, *, force: bool = False) -> str:
        if not force and not startup_debug_enabled():
            return ""
        self.stop_heartbeat()
        summary = self.format_summary()
        if not self._summary_logged:
            self._summary_logged = True
            _log.info("\n%s", summary)
        return summary


_timeline_singleton: StartupTimeline | None = None


def timeline() -> StartupTimeline:
    global _timeline_singleton
    if _timeline_singleton is None:
        _timeline_singleton = StartupTimeline()
    return _timeline_singleton


def mark(name: str) -> TimelineEntry | None:
    if not startup_debug_enabled():
        return None
    return timeline().mark(name)


def reset_timeline(reason: str = "startup") -> StartupTimeline | None:
    if not startup_debug_enabled():
        return None
    tl = timeline()
    tl.reset(reason, start_heartbeat=True)
    return tl


class _FirstPaintObserver(QObject):
    """Records the first Paint event on a window and removes itself."""

    def __init__(self, target: QWidget, mark_name: str = "first_paint"):
        super().__init__(target)
        self._target = target
        self._mark_name = mark_name
        self._fired = False

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if not self._fired and obj is self._target and event.type() == QEvent.Type.Paint:
            self._fired = True
            timeline().mark(self._mark_name)
            try:
                self._target.removeEventFilter(self)
            except RuntimeError:
                pass
            self.deleteLater()
        return False


def attach_first_paint_probe(window: QWidget, mark_name: str = "first_paint") -> None:
    if not startup_debug_enabled() or window is None:
        return
    observer = _FirstPaintObserver(window, mark_name=mark_name)
    window.installEventFilter(observer)
    QTimer.singleShot(0, lambda: mark("post_show_event_loop_tick"))


@dataclass
class GhostWindowEvent:
    event_type: str
    class_name: str
    object_name: str
    window_title: str
    parent_repr: str | None
    size: tuple[int, int]
    flags_hex: str
    stack: str
    whitelisted: bool


class GhostWindowProbe(QObject):
    """Application-wide filter logging top-level Show/ShowToParent/WinIdChange events."""

    def __init__(
        self,
        whitelist: Iterable[str] | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.whitelist: set[str] = set(
            DEFAULT_WINDOW_WHITELIST if whitelist is None else whitelist
        )
        self.events: list[GhostWindowEvent] = []
        self.unexpected_events: list[GhostWindowEvent] = []

    def clear(self) -> None:
        self.events.clear()
        self.unexpected_events.clear()

    def _is_whitelisted(self, widget: QWidget) -> bool:
        cls_name = type(widget).__name__
        if cls_name in self.whitelist:
            return True
        if bool(widget.property("_resivo_allowed_window")):
            return True
        return False

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        etype = event.type()
        if etype not in _EVENT_NAMES:
            return False
        if not isinstance(obj, QWidget):
            return False
        try:
            is_win = obj.isWindow()
        except RuntimeError:
            return False
        if not is_win:
            return False

        parent_obj = obj.parent()
        parent_repr = (
            f"{type(parent_obj).__name__}(objectName={parent_obj.objectName()!r})"
            if parent_obj is not None
            else None
        )
        cls_name = type(obj).__name__
        obj_name = obj.objectName()
        title = obj.windowTitle()
        size = (obj.width(), obj.height())
        flags_hex = hex(int(obj.windowFlags().value))
        stack = "".join(traceback.format_stack()[:-1])
        allowed = self._is_whitelisted(obj)

        record = GhostWindowEvent(
            event_type=_EVENT_NAMES[etype],
            class_name=cls_name,
            object_name=obj_name,
            window_title=title,
            parent_repr=parent_repr,
            size=size,
            flags_hex=flags_hex,
            stack=stack,
            whitelisted=allowed,
        )
        self.events.append(record)
        if not allowed:
            self.unexpected_events.append(record)
            _log.warning(
                "[GHOST WINDOW] event=%s class=%s objectName=%r title=%r parent=%s size=%s flags=%s\n%s",
                record.event_type,
                record.class_name,
                record.object_name,
                record.window_title,
                record.parent_repr,
                record.size,
                record.flags_hex,
                record.stack,
            )
        else:
            _log.info(
                "[WINDOW] event=%s class=%s objectName=%r title=%r size=%s",
                record.event_type,
                record.class_name,
                record.object_name,
                record.window_title,
                record.size,
            )
        return False


def install_ghost_window_probe(
    app: QApplication | None = None,
    *,
    whitelist: Iterable[str] | None = None,
    force: bool = False,
) -> GhostWindowProbe | None:
    if not force and not ghost_probe_enabled():
        return None
    target_app = app or QApplication.instance()
    if target_app is None:
        return None
    existing = getattr(target_app, "_ghost_window_probe", None)
    if existing is not None:
        if whitelist is not None:
            existing.whitelist = set(whitelist)
        return existing
    probe = GhostWindowProbe(whitelist=whitelist, parent=target_app)
    target_app.installEventFilter(probe)
    target_app._ghost_window_probe = probe
    return probe


def uninstall_ghost_window_probe(app: QApplication | None = None) -> None:
    target_app = app or QApplication.instance()
    if target_app is None:
        return
    probe = getattr(target_app, "_ghost_window_probe", None)
    if probe is not None:
        try:
            target_app.removeEventFilter(probe)
        except RuntimeError:
            pass
        try:
            probe.deleteLater()
        except RuntimeError:
            pass
        delattr(target_app, "_ghost_window_probe")
