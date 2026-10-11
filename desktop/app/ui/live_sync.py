from datetime import datetime
from PySide6.QtCore import QThread, Signal


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

                    # 3. Fetch pending room change requests
                    r_resp = (
                        self.client.table("room_change_requests")
                        .select("*, students(first_name, last_name, gender)")
                        .eq("status", "pending")
                        .order("created_at", desc=True)
                        .execute()
                    )
                    pending_requests = r_resp.data or []

                    # Detect new arrivals for live notifications
                    cur_s_ids = {s["id"] for s in pending_students}
                    cur_m_ids = {m["id"] for m in reports}
                    cur_r_ids = {r["id"] for r in pending_requests}

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
                                name = f"{st.get('first_name','')} {st.get('last_name','')}".strip()
                                self.alert_event.emit(
                                    f"New maintenance report: {str(r.get('category','')).capitalize()} ({name or 'Student'})"
                                )

                    if self._last_request_ids is not None:
                        new_reqs = cur_r_ids - self._last_request_ids
                        for req in pending_requests:
                            if req["id"] in new_reqs:
                                st = req.get("students") or {}
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
                        "pending_requests": pending_requests,
                        "timestamp": now_str,
                    }
                    self.sync_tick.emit(payload)
                except Exception:
                    # Ignore transient network timeouts to keep the thread running smoothly
                    pass

            self.msleep(self.interval_ms)
