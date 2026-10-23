"""RÉSIVO — Desktop notifications manager, settings persistence, and grouping logic."""

from __future__ import annotations

from collections import deque
from datetime import datetime, time
import logging
import re
from typing import NamedTuple

from PySide6.QtCore import QObject, QSettings
from PySide6.QtWidgets import QSystemTrayIcon

_log = logging.getLogger("resivo.notifications")


class NotificationItem(NamedTuple):
    timestamp: float
    category: str
    title: str
    body: str


def is_in_quiet_hours(start_str: str, end_str: str, check_time: time | None = None) -> bool:
    """Check whether a time falls within the quiet hours window (supports midnight wrap)."""
    if check_time is None:
        check_time = datetime.now().time()
    try:
        sh, sm = (int(x) for x in start_str.strip().split(":"))
        eh, em = (int(x) for x in end_str.strip().split(":"))
        start = time(sh, sm)
        end = time(eh, em)
    except Exception:
        return False

    if start < end:
        return start <= check_time < end
    # Wraps midnight, e.g. 22:00 to 07:00
    return check_time >= start or check_time < end


class NotificationSettings:
    """Notification configuration persisted in QSettings("RESIVO", "StaffConsole")."""

    def __init__(self) -> None:
        self._s = QSettings("RESIVO", "StaffConsole")

    def _bool(self, key: str, default: bool) -> bool:
        val = self._s.value(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() not in ("false", "0", "no")
        return bool(val)

    @property
    def enabled(self) -> bool:
        return self._bool("notifications/enabled", True)

    @enabled.setter
    def enabled(self, val: bool) -> None:
        self._s.setValue("notifications/enabled", bool(val))

    @property
    def notify_maintenance(self) -> bool:
        return self._bool("notifications/maintenance", True)

    @notify_maintenance.setter
    def notify_maintenance(self, val: bool) -> None:
        self._s.setValue("notifications/maintenance", bool(val))

    @property
    def notify_room_changes(self) -> bool:
        return self._bool("notifications/room_changes", True)

    @notify_room_changes.setter
    def notify_room_changes(self, val: bool) -> None:
        self._s.setValue("notifications/room_changes", bool(val))

    @property
    def notify_registrations(self) -> bool:
        return self._bool("notifications/registrations", True)

    @notify_registrations.setter
    def notify_registrations(self, val: bool) -> None:
        self._s.setValue("notifications/registrations", bool(val))

    @property
    def show_student_names(self) -> bool:
        return self._bool("notifications/show_student_names", True)

    @show_student_names.setter
    def show_student_names(self, val: bool) -> None:
        self._s.setValue("notifications/show_student_names", bool(val))

    @property
    def only_unfocused(self) -> bool:
        return self._bool("notifications/only_unfocused", False)

    @only_unfocused.setter
    def only_unfocused(self, val: bool) -> None:
        self._s.setValue("notifications/only_unfocused", bool(val))

    @property
    def play_sound(self) -> bool:
        return self._bool("notifications/play_sound", True)

    @play_sound.setter
    def play_sound(self, val: bool) -> None:
        self._s.setValue("notifications/play_sound", bool(val))

    @property
    def quiet_hours_enabled(self) -> bool:
        return self._bool("notifications/quiet_hours_enabled", False)

    @quiet_hours_enabled.setter
    def quiet_hours_enabled(self, val: bool) -> None:
        self._s.setValue("notifications/quiet_hours_enabled", bool(val))

    @property
    def quiet_hours_start(self) -> str:
        return str(self._s.value("notifications/quiet_hours_start", "22:00"))

    @quiet_hours_start.setter
    def quiet_hours_start(self, val: str) -> None:
        self._s.setValue("notifications/quiet_hours_start", str(val))

    @property
    def quiet_hours_end(self) -> str:
        return str(self._s.value("notifications/quiet_hours_end", "07:00"))

    @quiet_hours_end.setter
    def quiet_hours_end(self, val: str) -> None:
        self._s.setValue("notifications/quiet_hours_end", str(val))


class NotificationManager(QObject):
    """Manages event classification, deduplication, burst grouping, and tray toasts."""

    def __init__(self, parent: QObject | None = None, tray_icon: QSystemTrayIcon | None = None) -> None:
        super().__init__(parent)
        self.tray_icon = tray_icon
        self.settings = NotificationSettings()
        self.recent_events: deque[NotificationItem] = deque()
        self._seen_messages: set[str] = set()

    def classify_event(self, msg: str) -> tuple[str, str, str] | None:
        """Classify a LiveSync alert message into (category, title, body).

        Respects the show_student_names privacy setting.
        """
        show_names = self.settings.show_student_names
        clean = msg.strip()

        # 1. Maintenance
        if clean.startswith("New maintenance report:"):
            category = "maintenance"
            title = "New Maintenance Report"
            if not show_names:
                # Remove student name in parentheses, e.g. "New maintenance report: Plumbing (Student)"
                body = re.sub(r"\s*\([^)]*\)", "", clean)
            else:
                body = clean
            return category, title, body

        # 2. Room changes
        if clean.startswith("New room-change request"):
            category = "room_changes"
            title = "New Room-Change Request"
            if not show_names:
                body = "New room-change request submitted"
            else:
                body = clean
            return category, title, body

        # 3. Registrations / Applications
        if clean.startswith("New registration:"):
            category = "registrations"
            title = "New Student Application"
            if not show_names:
                # Remove name, keeping card id if present
                card_match = re.search(r"\(Card: ([^)]+)\)", clean)
                card_suffix = f" (Card: {card_match.group(1)})" if card_match else ""
                body = f"New registration received{card_suffix}"
            else:
                body = clean
            return category, title, body

        return None

    def handle_alert_event(
        self,
        msg: str,
        now: float | None = None,
        is_window_active: bool = False,
        check_time: time | None = None,
    ) -> dict | None:
        """Evaluate an alert event against settings and burst grouping.

        Returns a dictionary with {"title": str, "body": str, "sound": bool} if a
        notification should be shown, or None if suppressed.
        """
        if not self.settings.enabled:
            return None

        # Quiet hours suppression
        if self.settings.quiet_hours_enabled:
            if is_in_quiet_hours(
                self.settings.quiet_hours_start,
                self.settings.quiet_hours_end,
                check_time=check_time,
            ):
                return None

        # Window focus filter
        if self.settings.only_unfocused and is_window_active:
            return None

        # Deduplication
        if msg in self._seen_messages:
            return None
        self._seen_messages.add(msg)
        if len(self._seen_messages) > 500:
            self._seen_messages.clear()

        classified = self.classify_event(msg)
        if not classified:
            return None

        category, title, body = classified

        # Per-event toggle check
        if category == "maintenance" and not self.settings.notify_maintenance:
            return None
        if category == "room_changes" and not self.settings.notify_room_changes:
            return None
        if category == "registrations" and not self.settings.notify_registrations:
            return None

        if now is None:
            now = datetime.now().timestamp()

        # Prune events older than 10 seconds
        cutoff = now - 10.0
        while self.recent_events and self.recent_events[0].timestamp < cutoff:
            self.recent_events.popleft()

        item = NotificationItem(now, category, title, body)
        self.recent_events.append(item)

        # Grouping: > 3 events within 10s -> single summary notification
        if len(self.recent_events) > 3:
            total = len(self.recent_events)
            m_count = sum(1 for e in self.recent_events if e.category == "maintenance")
            r_count = sum(1 for e in self.recent_events if e.category == "room_changes")
            s_count = sum(1 for e in self.recent_events if e.category == "registrations")

            parts = []
            if m_count:
                parts.append(f"{m_count} maintenance report{'s' if m_count > 1 else ''}")
            if r_count:
                parts.append(f"{r_count} room change{'s' if r_count > 1 else ''}")
            if s_count:
                parts.append(f"{s_count} application{'s' if s_count > 1 else ''}")

            summary_title = "RÉSIVO Updates"
            summary_body = f"{total} new residence updates: {', '.join(parts)}"
            return {
                "title": summary_title,
                "body": summary_body,
                "sound": self.settings.play_sound,
            }

        return {
            "title": title,
            "body": body,
            "sound": self.settings.play_sound,
        }

    def dispatch_notification(self, title: str, body: str, sound: bool = True) -> None:
        """Show notification via QSystemTrayIcon."""
        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                title,
                body,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )

    def process_alert(self, msg: str, window=None) -> dict | None:
        """Handle incoming LiveSync alert message and dispatch tray toast if applicable."""
        is_active = False
        if window is not None:
            try:
                is_active = window.isActiveWindow() and not window.isMinimized()
            except Exception:
                is_active = False

        res = self.handle_alert_event(msg, is_window_active=is_active)
        if res:
            self.dispatch_notification(res["title"], res["body"], sound=res.get("sound", True))
        return res

    def send_test_notification(self) -> dict:
        """Trigger a test notification for operator feedback."""
        res = {
            "title": "RÉSIVO Notifications",
            "body": "Desktop notifications are working correctly.",
            "sound": self.settings.play_sound,
        }
        self.dispatch_notification(res["title"], res["body"], sound=res["sound"])
        return res
