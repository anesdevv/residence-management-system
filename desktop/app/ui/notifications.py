"""RÉSIVO — Desktop notifications manager, settings persistence, and grouping logic."""

from __future__ import annotations

from collections import deque
from datetime import datetime, time
import logging
import re
from typing import NamedTuple

from PySide6.QtCore import QObject, QSettings
from PySide6.QtWidgets import QSystemTrayIcon

try:
    from i18n import current_language, t, tn
except ImportError:
    from desktop.i18n import current_language, t, tn

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

    def classify_event(self, msg: str | dict) -> tuple[str, str, str] | None:
        """Classify an alert event into (category, title, body).

        Supports both structured event dictionaries and unstructured message strings
        across multiple languages (language-agnostic classification).
        Respects the show_student_names privacy setting.
        """
        show_names = self.settings.show_student_names

        # Structured dictionary event input
        if isinstance(msg, dict):
            event_type = str(msg.get("type") or msg.get("event") or msg.get("category") or "").lower().strip()
            if event_type in ("maintenance", "maint", "repair"):
                category = "maintenance"
                title = t("notifications.maintenance_title")
                raw_cat = str(msg.get("maintenance_category") or msg.get("category") or "others")
                norm_cat = raw_cat.lower().strip()
                if norm_cat in ("plumbing", "plomberie"):
                    cat_display = t("category.plumbing")
                elif norm_cat in ("electricity", "electrical", "électricité"):
                    cat_display = t("category.electricity")
                elif norm_cat in ("carpentry", "furniture", "menuiserie"):
                    cat_display = t("category.carpentry")
                elif norm_cat in ("others", "other", "heating", "general", "autres"):
                    cat_display = t("category.others")
                else:
                    cat_display = raw_cat.capitalize()

                student_name = (msg.get("student_name") or msg.get("name") or "").strip()
                if show_names and student_name:
                    body = t("notifications.maintenance_report_name", category=cat_display, name=student_name)
                else:
                    body = t("notifications.maintenance_report", category=cat_display)
                return category, title, body

            if event_type in ("room_changes", "room_change", "transfer"):
                category = "room_changes"
                title = t("notifications.room_change_title")
                student_name = (msg.get("student_name") or msg.get("name") or "").strip()
                if show_names and student_name:
                    body = t("notifications.room_change_from", name=student_name)
                else:
                    body = t("notifications.room_change_submitted")
                return category, title, body

            if event_type in ("registrations", "registration", "applications", "application"):
                category = "registrations"
                title = t("notifications.registration_title")
                student_name = (msg.get("student_name") or msg.get("name") or "").strip()
                card_id = str(msg.get("card_id") or "").strip()
                if show_names and student_name:
                    body = t("notifications.registration_from", name=student_name, card_id=card_id or "—")
                else:
                    if card_id:
                        body = t("notifications.registration_received_card", card_id=card_id)
                    else:
                        body = t("notifications.registration_received")
                return category, title, body

        # String message event input
        clean = str(msg).strip()

        # 1. Maintenance
        # Matches English: "New maintenance report: Category (Name)"
        # French: "Nouveau signalement de maintenance : Catégorie (Nom)"
        # Or structured prefixes: "[maintenance]", "maintenance:"
        maint_match = re.match(
            r"^(?:\[maintenance\]|maintenance:|New maintenance report:|Nouveau signalement de maintenance\s*[:\u00A0])\s*([^(]+?)(?:\s*\(([^)]+)\))?$",
            clean,
            re.IGNORECASE,
        )
        if maint_match:
            category = "maintenance"
            title = t("notifications.maintenance_title")
            raw_cat = maint_match.group(1).strip()
            student_name = (maint_match.group(2) or "").strip()

            norm_cat = raw_cat.lower()
            if norm_cat in ("plumbing", "plomberie"):
                cat_display = t("category.plumbing")
            elif norm_cat in ("electricity", "electrical", "électricité"):
                cat_display = t("category.electricity")
            elif norm_cat in ("carpentry", "furniture", "menuiserie"):
                cat_display = t("category.carpentry")
            elif norm_cat in ("others", "other", "heating", "general", "autres"):
                cat_display = t("category.others")
            else:
                cat_display = raw_cat

            if show_names and student_name:
                body = t("notifications.maintenance_report_name", category=cat_display, name=student_name)
            else:
                body = t("notifications.maintenance_report", category=cat_display)
            return category, title, body

        # 2. Room changes
        # Matches English: "New room-change request from Alice"
        # French: "Nouvelle demande de changement de chambre de Alice"
        # Prefixes: "[room_change]", "room_change:"
        rc_match = re.match(
            r"^(?:\[room_changes?\]|room_changes?:|New room-change request(?:\s+from\s+|\s+submitted|\s*:)?|Nouvelle demande de changement de chambre(?:\s+de\s+|\s+soumise|\s*[:\u00A0])?)\s*(.*)$",
            clean,
            re.IGNORECASE,
        )
        if rc_match:
            category = "room_changes"
            title = t("notifications.room_change_title")
            remainder = rc_match.group(1).strip()
            student_name = remainder if remainder and remainder.lower() not in ("submitted", "soumise") else ""
            if show_names and student_name:
                body = t("notifications.room_change_from", name=student_name)
            else:
                body = t("notifications.room_change_submitted")
            return category, title, body

        # 3. Registrations / Applications
        # Matches English: "New registration: Jane Smith (Card: C123)"
        # French: "Nouvelle inscription : Jane Smith (N° de carte : C123)"
        # Prefixes: "[registration]", "registration:", "application:"
        reg_match = re.match(
            r"^(?:\[registrations?\]|registrations?:|applications?:|New registration:|Nouvelle inscription\s*[:\u00A0]|Nouvelle demande d[’']hébergement\s*[:\u00A0])\s*(.*)$",
            clean,
            re.IGNORECASE,
        )
        if reg_match:
            category = "registrations"
            title = t("notifications.registration_title")
            content = reg_match.group(1).strip()
            card_match = re.search(r"\((?:Card|Carte|N° de carte)\s*:\s*([^)]+)\)", content, re.IGNORECASE)
            card_id = card_match.group(1).strip() if card_match else ""
            name_part = re.sub(r"\s*\([^)]*\)", "", content).strip()
            student_name = name_part if name_part else ""

            if show_names and student_name:
                body = t("notifications.registration_from", name=student_name, card_id=card_id or "—")
            else:
                if card_id:
                    body = t("notifications.registration_received_card", card_id=card_id)
                else:
                    body = t("notifications.registration_received")
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
                parts.append(tn("notifications.count_maintenance", count=m_count))
            if r_count:
                parts.append(tn("notifications.count_room_change", count=r_count))
            if s_count:
                parts.append(tn("notifications.count_application", count=s_count))

            summary_title = t("notifications.burst_title")
            summary_body = tn("notifications.burst_summary", count=total, details=", ".join(parts))
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
            "title": t("notifications.test_title"),
            "body": t("notifications.test_body"),
            "sound": self.settings.play_sound,
        }
        self.dispatch_notification(res["title"], res["body"], sound=res["sound"])
        return res
