"""RÉSIVO — read-only info modals (student profile, room occupancy).

Visual layer only (docs/DESIGN.md §4/§6): both dialogs are ``surface`` cards
with ``e2`` elevation, built from the shared component library (``Card``,
``KeyValueList``, ``StatusPill``, ``RosterMatchBadge``, ``Avatar``,
``InlineBanner``, ``StatCard``, ``RoomOccupancyBar``, ``EmptyState``,
``Button``) and theme tokens — no inline hex, no px font sizes.

Frozen surface
--------------
``StudentInfoCardDialog(parent, student_data, official_roster_data)`` and
``RoomInfoCardDialog(parent, room_data, client)`` keep their positional
signature (six call sites pass ``(self, dict, item)`` / ``(self, room, client)``
positionally) and their attributes (``student_data``, ``official_roster_data``,
``room_data``, ``client``). The roster-match banner keeps its semantics: a
roster row present = ``ok`` "Matched", otherwise ``danger`` "Not in roster"
(no network call is made for it). The room dialog keeps every Supabase read it
performed (``students`` by ``room_id`` with the best-effort ``status`` filter,
then the ``occupants`` / ``residents`` fallback) and the occupancy maths.

Helpers ``section_header`` and ``kpi_block`` stay importable for other modules.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from i18n import format_date, format_datetime, t, tn
except ImportError:
    from desktop.i18n import format_date, format_datetime, t, tn

try:
    from ..client import (
        get_cached_residence_settings,
        get_student_profile,
        has_gender_mismatch,
    )
except ImportError:
    from desktop.app.client import (
        get_cached_residence_settings,
        get_student_profile,
        has_gender_mismatch,
    )

try:
    from ..tasks import TaskRunner, human_error
except ImportError:
    from desktop.app.ui.tasks import TaskRunner, human_error

try:
    from . import theme
    from .components import (
        Avatar,
        Button,
        Card,
        EmptyState,
        InlineBanner,
        KeyValueList,
        RoomOccupancyBar,
        RosterMatchBadge,
        StatCard,
        StatusPill,
        configure_table,
    )
    from .icons import get_icon
    from .theme import DESKTOP_STYLESHEET, S, apply_app_stylesheet, apply_elevation
except (ImportError, ValueError):  # pragma: no cover - direct module execution
    from desktop.app.ui import theme
    from desktop.app.ui.components import (
        Avatar,
        Button,
        Card,
        EmptyState,
        InlineBanner,
        KeyValueList,
        RoomOccupancyBar,
        RosterMatchBadge,
        StatCard,
        StatusPill,
        configure_table,
    )
    from desktop.app.ui.icons import get_icon
    from desktop.app.ui.theme import DESKTOP_STYLESHEET, S, apply_app_stylesheet, apply_elevation


# Student status -> (StatusPill kind, label) — the desk vocabulary stays the same.
_STATUS_PILLS = {
    "active": ("ok", "Active resident"),
    "approved": ("ok", "Active resident"),
    "resident": ("ok", "Active resident"),
    "pending": ("pending", "Pending verification"),
    "pending_verification": ("pending", "Pending verification"),
    "rejected": ("danger", "Rejected"),
    "cancelled": ("danger", "Cancelled"),
}


def _get_status_pill(status_raw: str, default_val: str) -> tuple[str, str]:
    mapping = {
        "active": ("ok", t("infocard.status_active_resident")),
        "approved": ("ok", t("infocard.status_active_resident")),
        "resident": ("ok", t("infocard.status_active_resident")),
        "pending": ("pending", t("infocard.status_pending_verification")),
        "pending_verification": ("pending", t("infocard.status_pending_verification")),
        "rejected": ("danger", t("status.rejected")),
        "cancelled": ("danger", t("infocard.status_cancelled")),
    }
    return mapping.get(status_raw, ("neutral", default_val.capitalize()))


def section_header(text: str) -> QLabel:
    """Small overline section header (kept importable for other modules)."""
    label = QLabel(str(text).upper())
    theme.apply_role(label, "overline")
    label.setWordWrap(True)
    return label


def kpi_block(
    label: str,
    value,
    accent: str = "teal",
    icon: str = "bed",
    parent=None,
    *,
    flat: bool = False,
) -> StatCard:
    """KPI block helper (kept importable): a ``StatCard`` (or flat borderless well inside cards)."""
    card = StatCard(label, icon, accent, parent)
    card.set_value(value)
    if flat:
        card.setProperty("cardFrame", False)
        card.setObjectName("statWell")
        card.setStyleSheet(
            f"QFrame#statWell {{ background-color: {theme.C('surface-subtle')};"
            f" border: none; border-radius: {theme.C('radius-input')}; }}"
        )
    return card


def _safe_date(val: Any) -> tuple[str, bool]:
    """Return (formatted_date_string, is_empty)."""
    if not val:
        return t("infocard.not_provided"), True
    try:
        return format_date(val), False
    except Exception:
        s = str(val).strip()
        if not s or s.lower() == "none" or s == "—":
            return t("infocard.not_provided"), True
        return s, False


def _safe_datetime(val: Any) -> tuple[str, bool]:
    """Return (formatted_datetime_string, is_empty)."""
    if not val:
        return t("infocard.not_provided"), True
    try:
        return format_datetime(val), False
    except Exception:
        s = str(val).strip()
        if not s or s.lower() == "none" or s == "—":
            return t("infocard.not_provided"), True
        return s, False


def _safe_str(val: Any, empty_msg: str | None = None) -> tuple[str, bool]:
    """Return (string_value, is_empty)."""
    fallback = empty_msg or t("infocard.not_provided")
    if val is None:
        return fallback, True
    s = str(val).strip()
    if not s or s.lower() == "none" or s == "—":
        return fallback, True
    return s, False


def _row(*widgets: QWidget) -> QWidget:
    """Plain horizontal row of widgets (no margins, spacing ``space-2``)."""
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(S("space-2"))
    for widget in widgets:
        layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
    layout.addStretch(1)
    return holder


class StudentInfoCardDialog(QDialog):
    """Read-only resident profile: identity, academic data and roster match.

    Enriches student profile from `get_student_profile` off-thread while
    displaying preliminary data immediately.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        student_data: dict[str, Any] | None = None,
        official_roster_data: dict[str, Any] | None = None,
        residence_gender: str | None = None,
        *,
        client: Any | None = None,
        student_id: str | None = None,
    ):
        super().__init__(parent)
        self._closing = False
        self._fetch_req_id = 0
        self.student_data = dict(student_data or {})
        self.official_roster_data = official_roster_data

        # Client resolution
        self.client = client or (getattr(parent, "client", None) if parent is not None else None)

        # Student ID resolution
        sid = student_id or self.student_data.get("id") or self.student_data.get("card_id")
        self.student_id = str(sid).strip() if sid else None

        # Residence gender resolution
        parent_client = self.client or (getattr(parent, "client", None) if parent is not None else None)
        cached_res = get_cached_residence_settings(parent_client) if parent_client else None
        self.residence_gender = (
            residence_gender
            or (getattr(parent, "residence_gender", None) if parent is not None else None)
            or (cached_res or {}).get("residence_gender")
        )

        self.tasks = TaskRunner(self)

        # ------------------------------------------------------- window setup
        first_name = str(self.student_data.get("first_name", "")).strip()
        last_name = str(self.student_data.get("last_name", "")).strip()
        full_name = f"{first_name} {last_name}".strip() or t("infocard.default_student_name")
        self.setWindowTitle(t("infocard.student_title", name=full_name))
        self.setModal(True)
        self.setMinimumWidth(620)
        self.setMinimumHeight(480)
        apply_app_stylesheet(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        root.setSpacing(S("space-4"))

        # Error banner (shown if asynchronous enrichment fails)
        self.error_banner = InlineBanner(
            "error",
            title=t("infocard.error_profile_title"),
            message="",
            icon="alert-circle",
        )
        self.retry_btn = Button.secondary(t("infocard.retry_btn"))
        self.retry_btn.clicked.connect(self._fetch_profile)
        self.error_banner.add_action(self.retry_btn)
        self.error_banner.setVisible(False)
        root.addWidget(self.error_banner)

        # Scroll area for dialog content
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(S("space-4"))
        scroll.setWidget(scroll_content)
        root.addWidget(scroll, 1)

        # ------------------------------------------------------ profile card
        self.profile_card = Card(
            t("infocard.student_card_title"),
            t("infocard.student_card_desc"),
            icon="id-card",
        )
        scroll_layout.addWidget(self.profile_card)

        identity = QWidget()
        identity_row = QHBoxLayout(identity)
        identity_row.setContentsMargins(0, 0, 0, 0)
        identity_row.setSpacing(S("space-3"))
        self.avatar = Avatar(full_name, size=S("space-12"))
        identity_row.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignTop)

        identity_column = QVBoxLayout()
        identity_column.setSpacing(2)
        self.name_label = QLabel(full_name)
        theme.apply_role(self.name_label, "h2")
        self.name_label.setWordWrap(True)
        identity_column.addWidget(self.name_label)

        self.meta_label = QLabel()
        theme.apply_role(self.meta_label, "small")
        theme.enable_tabular(self.meta_label)
        self.meta_label.setWordWrap(True)
        identity_column.addWidget(self.meta_label)
        identity_row.addLayout(identity_column, 1)
        self.profile_card.add_widget(identity)

        # Badges & pills row
        self.status_pill = StatusPill("neutral", "")
        self.roster_badge = RosterMatchBadge(False)
        self.roster_badge.setToolTip(t("infocard.roster_tooltip"))
        self.gender_warning_badge = StatusPill("warning", t("residence.gender_differs_badge"))
        self.gender_warning_badge.setToolTip(t("residence.gender_differs_tooltip"))
        self.active_no_room_pill = StatusPill("warning", t("infocard.active_no_room_warn"))
        self.pills_holder = _row(
            self.status_pill,
            self.roster_badge,
            self.gender_warning_badge,
            self.active_no_room_pill,
        )
        self.profile_card.add_widget(self.pills_holder)

        self.profile_card.add_widget(section_header(t("infocard.section_academic")))
        self.facts = KeyValueList()
        self.profile_card.add_widget(self.facts)

        # ------------------------------------------------------ housing card
        self.housing_card = Card(
            t("infocard.housing_card_title"),
            t("infocard.housing_card_desc"),
            icon="building",
        )
        scroll_layout.addWidget(self.housing_card)

        self.housing_facts = KeyValueList()
        self.housing_card.add_widget(self.housing_facts)

        self.no_room_banner = InlineBanner("info", title="", message="")
        self.housing_card.add_widget(self.no_room_banner)

        self.roster_banner = InlineBanner("info", title="", message="")
        self.housing_card.add_widget(self.roster_banner)

        # ------------------------------------------------------------ footer
        footer = QHBoxLayout()
        footer.setSpacing(S("space-2"))
        footer.addStretch(1)
        close_btn = Button.secondary(t("common.close"))
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        root.addLayout(footer)

        apply_elevation(self, 2)

        # Render preliminary UI immediately
        self._update_ui()

        # Initiate off-thread background enrichment if client and id are available
        self._fetch_profile()

    def _update_ui(self) -> None:
        first_name = str(self.student_data.get("first_name", "")).strip()
        last_name = str(self.student_data.get("last_name", "")).strip()
        full_name = f"{first_name} {last_name}".strip() or t("infocard.default_student_name")
        card_id = str(self.student_data.get("card_id", "")).strip()
        card_id_display = card_id or t("infocard.not_provided")

        self.setWindowTitle(t("infocard.student_title", name=full_name))
        self.avatar.set_name(full_name)
        self.name_label.setText(full_name)

        meta_parts = [t("infocard.card_id_prefix", card_id=card_id_display)]
        wilaya = self.student_data.get("wilaya")
        if wilaya:
            meta_parts.append(t("infocard.wilaya_prefix", wilaya=wilaya))
        study_level = self.student_data.get("study_level")
        if study_level:
            meta_parts.append(str(study_level))
        self.meta_label.setText(", ".join(meta_parts))

        status_raw = str(self.student_data.get("status", "active")).lower().strip()
        status_kind, status_label = _get_status_pill(
            status_raw, str(self.student_data.get("status", "Unknown"))
        )
        self.status_pill.set_kind(status_kind, status_label)

        is_verified = bool(self.official_roster_data)
        self.roster_badge.set_matched(True if is_verified else False)

        roster_gender = (
            self.official_roster_data.get("gender")
            if isinstance(self.official_roster_data, dict)
            else None
        )
        self.gender_warning_badge.setVisible(
            has_gender_mismatch(
                self.residence_gender,
                student_gender=self.student_data.get("gender"),
                roster_gender=roster_gender,
            )
        )

        # Room allocation
        room = self.student_data.get("rooms") or self.student_data.get("room") or {}
        if isinstance(room, list) and room:
            room = room[0]
        elif not isinstance(room, dict):
            room = {}

        block = room.get("block") or self.student_data.get("block")
        number = room.get("number") or self.student_data.get("room_number") or self.student_data.get("number")
        floor = room.get("floor") if room.get("floor") is not None else self.student_data.get("floor")

        has_room = False
        if block and number:
            floor_text = t("infocard.floor_suffix", floor=floor) if floor is not None and str(floor) != "" else ""
            assigned_room_str = t("infocard.assigned_room_format", block=block, number=number, floor_text=floor_text)
            has_room = True
        elif self.student_data.get("room_str"):
            assigned_room_str = str(self.student_data["room_str"])
            has_room = True
        else:
            assigned_room_str = t("infocard.no_room_assigned")

        is_active = status_raw in ("active", "approved", "resident")
        self.active_no_room_pill.setVisible(is_active and not has_room)

        # Build academic & identity facts rows
        cid_val, cid_empty = _safe_str(self.student_data.get("card_id"))
        fn_val, fn_empty = _safe_str(full_name)
        facts_rows = [
            (t("infocard.student_card_id"), cid_val, cid_empty),
            (t("infocard.full_name"), fn_val, fn_empty),
            (t("infocard.status_label"), status_label, False),
        ]

        if not self.residence_gender:
            g_raw = self.student_data.get("gender")
            if g_raw and str(g_raw).lower() in ("male", "female"):
                g_str = t(f"gender.{str(g_raw).lower()}")
                g_empty = False
            else:
                g_str, g_empty = _safe_str(g_raw)
            facts_rows.append((t("fields.gender"), g_str, g_empty))

        dob_val = self.student_data.get("birth_date")
        if not dob_val and isinstance(self.official_roster_data, dict):
            dob_val = self.official_roster_data.get("birth_date")
        dob_str, dob_empty = _safe_date(dob_val)
        facts_rows.append((t("infocard.birth_date"), dob_str, dob_empty))

        univ_str, univ_empty = _safe_str(self.student_data.get("university"))
        facts_rows.append((t("fields.university"), univ_str, univ_empty))

        fac_str, fac_empty = _safe_str(self.student_data.get("faculty"))
        facts_rows.append((t("fields.faculty"), fac_str, fac_empty))

        lvl_str, lvl_empty = _safe_str(self.student_data.get("study_level"))
        facts_rows.append((t("infocard.study_level"), lvl_str, lvl_empty))

        wil_str, wil_empty = _safe_str(self.student_data.get("wilaya"))
        facts_rows.append((t("infocard.wilaya"), wil_str, wil_empty))

        ph_str, ph_empty = _safe_str(self.student_data.get("phone"))
        facts_rows.append((t("infocard.contact_phone"), ph_str, ph_empty))

        em_str, em_empty = _safe_str(self.student_data.get("email"))
        facts_rows.append((t("infocard.contact_email"), em_str, em_empty))

        reg_str, reg_empty = _safe_datetime(self.student_data.get("created_at"))
        facts_rows.append((t("infocard.registered_on"), reg_str, reg_empty))

        # Reviewer info
        reviewed_at = self.student_data.get("reviewed_at")
        reviewer = self.student_data.get("staff")
        reviewer_name = None
        if isinstance(reviewer, dict):
            reviewer_name = reviewer.get("full_name")
        elif not reviewer_name and self.student_data.get("reviewed_by"):
            reviewer_name = str(self.student_data["reviewed_by"])

        if reviewed_at or reviewer_name:
            name_str = reviewer_name or "Staff"
            if reviewed_at:
                dt_str, _ = _safe_datetime(reviewed_at)
                rev_display = t("infocard.reviewed_by_on", name=name_str, date=dt_str)
            else:
                rev_display = name_str
            rev_empty = False
        else:
            rev_display = t("infocard.not_reviewed_yet")
            rev_empty = True
        facts_rows.append((t("infocard.reviewed_label"), rev_display, rev_empty))

        if status_raw == "rejected" and self.student_data.get("rejection_reason"):
            rej_str, rej_empty = _safe_str(self.student_data.get("rejection_reason"))
            facts_rows.append((t("fields.rejection_reason"), rej_str, rej_empty))

        self.facts.set_rows(facts_rows)

        # Housing facts
        self.housing_facts.set_rows([
            (t("infocard.assigned_room_label"), assigned_room_str, not has_room)
        ])

        # No room banner
        if has_room:
            self.no_room_banner.setVisible(False)
        else:
            self.no_room_banner.setVisible(True)
            if is_active:
                self.no_room_banner.set_kind("warning")
                self.no_room_banner.set_title(t("infocard.no_room_title"))
                self.no_room_banner.set_message(t("infocard.active_no_room_warn"))
            else:
                self.no_room_banner.set_kind("info")
                self.no_room_banner.set_title(t("infocard.no_room_title"))
                self.no_room_banner.set_message(t("infocard.no_room_desc"))

        # Roster banner
        if is_verified:
            differing_fields = self.student_data.get("roster_differing_fields")
            if differing_fields is None and isinstance(self.official_roster_data, dict):
                differing_fields = []
                for field in ("first_name", "last_name", "birth_date", "gender", "university", "faculty"):
                    s_v = str(self.student_data.get(field) or "").strip().lower()
                    o_v = str(self.official_roster_data.get(field) or "").strip().lower()
                    if s_v and o_v and s_v != o_v:
                        differing_fields.append(field)
            if differing_fields:
                field_labels = {
                    "first_name": t("infocard.full_name"),
                    "last_name": t("infocard.full_name"),
                    "birth_date": t("infocard.birth_date"),
                    "gender": t("fields.gender"),
                    "university": t("fields.university"),
                    "faculty": t("fields.faculty"),
                }
                diff_str = ", ".join(field_labels.get(f, f) for f in differing_fields)
                self.roster_banner.set_kind("warning")
                self.roster_banner.set_title(t("infocard.roster_match_title"))
                self.roster_banner.set_message(t("infocard.roster_differing_fields", fields=diff_str))
            else:
                self.roster_banner.set_kind("success")
                self.roster_banner.set_title(t("infocard.roster_match_title"))
                self.roster_banner.set_message(t("infocard.roster_match_desc"))
        else:
            if status_raw in ("pending", "pending_verification"):
                self.roster_banner.set_kind("error")
                self.roster_banner.set_title(t("infocard.roster_mismatch_title"))
                self.roster_banner.set_message(t("infocard.roster_mismatch_desc"))
            else:
                self.roster_banner.set_kind("info")
                self.roster_banner.set_title(t("infocard.approved_without_roster"))
                self.roster_banner.set_message(t("infocard.roster_mismatch_desc"))

    def _fetch_profile(self) -> None:
        if not self.client or not self.student_id or self._closing:
            return
        if not hasattr(self.client, "table"):
            return
        self._fetch_req_id += 1
        req_id = self._fetch_req_id
        self.error_banner.setVisible(False)
        key = f"profile_{self.student_id}_{req_id}"
        self.tasks.run(
            key,
            lambda: get_student_profile(self.client, self.student_id),
            on_success=lambda res: self._on_profile_loaded(res, req_id),
            on_failed=lambda err: self._on_profile_failed(err, req_id),
        )

    def _on_profile_loaded(self, res: dict | None, req_id: int) -> None:
        if self._closing or req_id != self._fetch_req_id:
            return
        if res:
            self.student_data.update(res)
            if res.get("official_roster"):
                self.official_roster_data = res["official_roster"]
            self._update_ui()

    def _on_profile_failed(self, err_msg: str, req_id: int) -> None:
        if self._closing or req_id != self._fetch_req_id:
            return
        self.error_banner.set_message(err_msg or t("infocard.could_not_load"))
        self.error_banner.setVisible(True)

    def closeEvent(self, event) -> None:
        self._closing = True
        super().closeEvent(event)

    def reject(self) -> None:
        self._closing = True
        super().reject()

    def accept(self) -> None:
        self._closing = True
        super().accept()


class RoomInfoCardDialog(QDialog):
    """Read-only room inspection: capacity, occupancy, current occupants.

    ``RoomInfoCardDialog(parent, room_data, client)`` — the occupant read
    (``students`` by ``room_id``, best-effort ``status = active``) and the
    ``occupants`` / ``residents`` fallback are unchanged.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        room_data: dict[str, Any] | None = None,
        client: Any | None = None,
    ):
        super().__init__(parent)
        self.room_data = room_data or {}
        self.client = client

        # Room properties (same parsing as before).
        block = str(self.room_data.get("block", "—")).strip()
        number = str(self.room_data.get("number") or self.room_data.get("room_number") or "—").strip()
        floor = str(self.room_data.get("floor", "0") if self.room_data.get("floor") is not None else "0").strip()
        capacity = int(self.room_data.get("capacity") or 1)

        self.setWindowTitle(t("infocard.room_title", block=block, number=number))
        self.setModal(True)
        self.setMinimumWidth(620)
        apply_app_stylesheet(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        root.setSpacing(S("space-4"))

        # ------------------------------------------- occupants (unchanged read)
        occupants: list[dict[str, Any]] = []
        room_id = self.room_data.get("id")
        if self.client is not None and room_id:
            try:
                query = self.client.table("students").select("card_id, first_name, last_name, faculty").eq("room_id", room_id)
                if hasattr(query, "eq"):
                    # in case chaining .eq("status", "active")
                    try:
                        query = query.eq("status", "active")
                    except Exception:
                        pass
                resp = query.execute()
                if resp and hasattr(resp, "data") and isinstance(resp.data, list):
                    occupants = resp.data
            except Exception:
                pass

        if not occupants:
            raw_occ = self.room_data.get("occupants") or self.room_data.get("residents")
            if isinstance(raw_occ, list):
                occupants = raw_occ

        if not isinstance(occupants, list):
            occupants = []

        # Calculate Occupied & Available Beds (unchanged maths).
        if len(occupants) > 0:
            occupied = len(occupants)
        elif "occupied" in self.room_data and self.room_data["occupied"] is not None:
            try:
                occupied = int(self.room_data["occupied"])
            except (ValueError, TypeError):
                occupied = 0
        elif "occupied_beds" in self.room_data and self.room_data["occupied_beds"] is not None:
            try:
                occupied = int(self.room_data["occupied_beds"])
            except (ValueError, TypeError):
                occupied = 0
        else:
            occupied = 0

        available = max(0, capacity - occupied)

        # ------------------------------------------------------ capacity card
        capacity_card = Card(
            t("infocard.capacity_card_title", block=block, number=number),
            t("infocard.capacity_card_desc", floor=floor),
            icon="building",
        )
        root.addWidget(capacity_card)

        if available <= 0:
            self.capacity_pill = StatusPill("danger", t("infocard.room_full"))
            self.capacity_pill.setToolTip(t("infocard.room_full_tooltip"))
        else:
            beds_text = tn("infocard.bed_available", count=available)
            self.capacity_pill = StatusPill("ok", beds_text)
            self.capacity_pill.setToolTip(t("infocard.bed_available_tooltip"))
        capacity_card.add_widget(_row(self.capacity_pill))

        stats = QHBoxLayout()
        stats.setSpacing(S("space-3"))
        stats.addWidget(kpi_block(t("infocard.total_capacity"), capacity, "navy", flat=True), 1)
        stats.addWidget(kpi_block(t("infocard.occupied_beds"), occupied, "teal", icon="user-check", flat=True), 1)
        stats.addWidget(
            kpi_block(
                t("infocard.available_beds"),
                available,
                "green" if available > 0 else "danger",
                icon="bed",
                flat=True,
            ),
            1,
        )
        capacity_card.add_layout(stats)

        self.occupancy_bar = RoomOccupancyBar(occupied, capacity)
        capacity_card.add_widget(self.occupancy_bar)

        # ----------------------------------------------------- occupants card
        occupants_card = Card(
            t("infocard.occupants_card_title"),
            t("infocard.occupants_card_desc", occupied=occupied, capacity=capacity),
            icon="users",
        )
        root.addWidget(occupants_card)

        if occupants:
            table = QTableWidget(len(occupants), 3)
            table.setProperty("borderless", True)
            configure_table(
                table,
                [
                    t("infocard.table_col_name"),
                    t("infocard.table_col_card_id"),
                    t("infocard.table_col_faculty"),
                ],
            )
            header = table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            for index, occupant in enumerate(occupants):
                occupant_name = (
                    f"{str(occupant.get('first_name', '')).strip()} {str(occupant.get('last_name', '')).strip()}".strip()
                    or t("infocard.default_occupant_name")
                )
                name_item = QTableWidgetItem(occupant_name)
                name_item.setIcon(get_icon("user", 14, theme.C("text-muted")))
                card_item = QTableWidgetItem(str(occupant.get("card_id", "—")))
                card_item.setIcon(get_icon("id-card", 14, theme.C("teal-600")))
                faculty_item = QTableWidgetItem(str(occupant.get("faculty", "—")))
                table.setItem(index, 0, name_item)
                table.setItem(index, 1, card_item)
                table.setItem(index, 2, faculty_item)
            table.setFixedHeight(
                min(S("space-12") * 5, S("size-row") * (len(occupants) + 1) + S("space-2"))
            )
            occupants_card.add_widget(table)
        else:
            occupants_card.add_widget(
                EmptyState(
                    "bed",
                    t("infocard.no_residents_title"),
                    t("infocard.no_residents_desc"),
                )
            )

        # ------------------------------------------------------------ footer
        footer = QHBoxLayout()
        footer.setSpacing(S("space-2"))
        footer.addStretch(1)
        close_btn = Button.secondary(t("common.close"))
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        root.addLayout(footer)

        apply_elevation(self, 2)


__all__ = [
    "StudentInfoCardDialog",
    "RoomInfoCardDialog",
    "section_header",
    "kpi_block",
]
