import logging
import time
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from ..client import CLIENT_LOCK

_log = logging.getLogger(__name__)

# Keep a broken network from flooding the log at every tick.
_ERROR_LOG_INTERVAL_S = 60.0


class LiveSyncWorker(QThread):
    sync_tick = Signal(dict)
    alert_event = Signal(str)

    def __init__(self, client, interval_ms: int = 2500):
        super().__init__()
        self.client = client
        self.interval_ms = interval_ms
        self._running = True
        self._paused = False
        self._last_student_ids: set[str] | None = None
        self._last_report_ids: set[str] | None = None
        self._last_request_ids: set[str] | None = None
        self._last_error_logged_at = 0.0

    def stop(self):
        self._running = False

    def set_paused(self, paused: bool):
        self._paused = paused

    def is_paused(self) -> bool:
        return self._paused

    def run(self):
        while self._running:
            if not self._paused:
                try:
                    with CLIENT_LOCK:
                        # 1. Fetch pending students
                        s_resp = (
                            self.client.table("students")
                            .select("*")
                            .eq("status", "pending")
                            .order("created_at", desc=True)
                            .execute()
                        )
                        pending_students = s_resp.data or []

                        # 2. Fetch maintenance reports
                        m_resp = (
                            self.client.table("maintenance_reports")
                            .select("*, students(first_name, last_name, card_id)")
                            .order("created_at", desc=True)
                            .execute()
                        )
                        reports = m_resp.data or []
                        open_reports_count = sum(1 for r in reports if r.get("status") != "resolved")

                        # 3. Fetch ALL room change requests so processed rows stay
                        # visible in the status views; the badge stays pending-only.
                        r_resp = (
                            self.client.table("room_change_requests")
                            .select(
                                "*, students(first_name, last_name, gender, card_id),"
                                " staff(full_name)"
                            )
                            .order("created_at", desc=True)
                            .execute()
                        )
                        requests = r_resp.data or []

                        # 4. Fetch active residents count for live KPI updates
                        a_resp = (
                            self.client.table("students")
                            .select("id", count="exact")
                            .eq("status", "active")
                            .execute()
                        )
                        active_count = a_resp.count if a_resp.count is not None else 0

                    # Detect new arrivals for live notifications
                    cur_s_ids = {s["id"] for s in pending_students}
                    cur_m_ids = {m["id"] for m in reports}
                    cur_r_ids = {r["id"] for r in requests}

                    if self._last_student_ids is not None:
                        new_students = cur_s_ids - self._last_student_ids
                        for s in pending_students:
                            if s["id"] in new_students:
                                self.alert_event.emit(
                                    f"New registration: {s.get('first_name', '')} {s.get('last_name', '')} (Card: {s.get('card_id', '')})"
                                )

                    if self._last_report_ids is not None:
                        new_reports = cur_m_ids - self._last_report_ids
                        for r in reports:
                            if r["id"] in new_reports and r.get("status") == "pending":
                                st = r.get("students") or {}
                                if isinstance(st, list) and st:
                                    st = st[0]
                                elif not isinstance(st, dict):
                                    st = {}
                                name = f"{st.get('first_name','')} {st.get('last_name','')}".strip()
                                self.alert_event.emit(
                                    f"New maintenance report: {str(r.get('category','')).capitalize()} ({name or 'Student'})"
                                )

                    if self._last_request_ids is not None:
                        new_reqs = cur_r_ids - self._last_request_ids
                        for req in requests:
                            if req["id"] in new_reqs and req.get("status") == "pending":
                                st = req.get("students") or {}
                                if isinstance(st, list) and st:
                                    st = st[0]
                                elif not isinstance(st, dict):
                                    st = {}
                                name = f"{st.get('first_name','')} {st.get('last_name','')}".strip()
                                self.alert_event.emit(
                                    f"New room-change request from {name or 'Student'}"
                                )

                    self._last_student_ids = cur_s_ids
                    self._last_report_ids = cur_m_ids
                    self._last_request_ids = cur_r_ids

                    now_str = datetime.now().strftime("%H:%M:%S")

                    payload = {
                        "pending_students": pending_students,
                        "reports": reports,
                        "open_reports_count": open_reports_count,
                        # Legacy payload key kept for the shell; it now carries
                        # every status (pending / approved / rejected).
                        "pending_requests": requests,
                        "room_change_requests": requests,
                        "active_residents_count": active_count,
                        "timestamp": now_str,
                    }
                    self.sync_tick.emit(payload)
                except Exception:
                    # Keep the thread running through transient network
                    # timeouts, but record them at a bounded rate instead of
                    # swallowing every failure silently.
                    now = time.monotonic()
                    if now - self._last_error_logged_at >= _ERROR_LOG_INTERVAL_S:
                        self._last_error_logged_at = now
                        _log.warning("Live sync tick failed", exc_info=True)

            # Responsive sleep so thread exits cleanly without hanging
            sleep_elapsed = 0
            while self._running and sleep_elapsed < self.interval_ms:
                self.msleep(100)
                sleep_elapsed += 100
