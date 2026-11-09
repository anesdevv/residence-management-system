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
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from i18n import t, tn
except ImportError:
    from desktop.i18n import t, tn

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
    from .theme import DESKTOP_STYLESHEET, S, apply_elevation
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
    from desktop.app.ui.theme import DESKTOP_STYLESHEET, S, apply_elevation


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


def kpi_block(label: str, value, accent: str = "teal", icon: str = "bed", parent=None) -> StatCard:
    """KPI block helper (kept importable): a ``StatCard`` with its value set."""
    card = StatCard(label, icon, accent, parent)
    card.set_value(value)
    return card


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

    ``StudentInfoCardDialog(parent, student_data, official_roster_data)`` — the
    dialog only renders the dicts it is given; the roster banner is green when
    ``official_roster_data`` is a non-empty row, amber-free red otherwise.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        student_data: dict[str, Any] | None = None,
        official_roster_data: dict[str, Any] | None = None,
    ):
        super().__init__(parent)
        self.student_data = student_data or {}
        self.official_roster_data = official_roster_data

        # ------------------------------------------------------- window setup
        first_name = str(self.student_data.get("first_name", "")).strip()
        last_name = str(self.student_data.get("last_name", "")).strip()
        full_name = f"{first_name} {last_name}".strip() or t("infocard.default_student_name")
        card_id = str(self.student_data.get("card_id", "—")).strip() or "—"
        self.setWindowTitle(t("infocard.student_title", name=full_name))
        self.setModal(True)
        self.setMinimumWidth(580)
        self.setStyleSheet(DESKTOP_STYLESHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        root.setSpacing(S("space-4"))

        is_verified = bool(self.official_roster_data)

        # ------------------------------------------------------ profile card
        profile_card = Card(
            t("infocard.student_card_title"),
            t("infocard.student_card_desc"),
            icon="id-card",
        )
        root.addWidget(profile_card)

        identity = QWidget()
        identity_row = QHBoxLayout(identity)
        identity_row.setContentsMargins(0, 0, 0, 0)
        identity_row.setSpacing(S("space-3"))
        identity_row.addWidget(Avatar(full_name, size=S("space-12")), 0, Qt.AlignmentFlag.AlignTop)

        identity_column = QVBoxLayout()
        identity_column.setSpacing(2)
        name_label = QLabel(full_name)
        theme.apply_role(name_label, "h2")
        name_label.setWordWrap(True)
        identity_column.addWidget(name_label)

        meta_parts = [t("infocard.card_id_prefix", card_id=card_id)]
        wilaya = self.student_data.get("wilaya")
        if wilaya:
            meta_parts.append(t("infocard.wilaya_prefix", wilaya=wilaya))
        study_level = self.student_data.get("study_level")
        if study_level:
            meta_parts.append(str(study_level))
        meta_label = QLabel(" · ".join(meta_parts))
        theme.apply_role(meta_label, "small")
        theme.enable_tabular(meta_label)
        meta_label.setWordWrap(True)
        identity_column.addWidget(meta_label)
        identity_row.addLayout(identity_column, 1)
        profile_card.add_widget(identity)

        status_raw = str(self.student_data.get("status", "active")).lower().strip()
        status_kind, status_label = _get_status_pill(
            status_raw, str(self.student_data.get("status", "Unknown"))
        )
        self.status_pill = StatusPill(status_kind, status_label)
        self.roster_badge = RosterMatchBadge(True if is_verified else False)
        self.roster_badge.setToolTip(t("infocard.roster_tooltip"))
        profile_card.add_widget(_row(self.status_pill, self.roster_badge))

        profile_card.add_widget(section_header(t("infocard.section_academic")))
        gender_str = str(self.student_data.get("gender", "—")).strip().capitalize()
        univ_str = str(self.student_data.get("university", "—")).strip()
        fac_str = str(self.student_data.get("faculty", "—")).strip()
        dob_val = "—"
        if isinstance(self.official_roster_data, dict) and self.official_roster_data.get("birth_date"):
            dob_val = str(self.official_roster_data["birth_date"])
        elif self.student_data.get("birth_date"):
            dob_val = str(self.student_data["birth_date"])
        phone_val = str(self.student_data.get("phone", "")).strip() or "—"

        self.facts = KeyValueList()
        self.facts.set_rows([
            (t("infocard.student_card_id"), card_id),
            (t("fields.gender"), gender_str),
            (t("fields.university"), univ_str),
            (t("fields.faculty"), fac_str),
            (t("infocard.birth_date"), dob_val),
            (t("infocard.contact_phone"), phone_val),
        ])
        profile_card.add_widget(self.facts)

        # ------------------------------------------------------ housing card
        housing_card = Card(
            t("infocard.housing_card_title"),
            t("infocard.housing_card_desc"),
            icon="building",
        )
        root.addWidget(housing_card)

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

        housing_facts = KeyValueList()
        housing_facts.add_row(t("infocard.assigned_room_label"), assigned_room_str)
        housing_card.add_widget(housing_facts)
        if not has_room:
            housing_card.add_widget(
                InlineBanner(
                    "info",
                    title=t("infocard.no_room_title"),
                    message=t("infocard.no_room_desc"),
                )
            )

        if is_verified:
            roster_banner = InlineBanner(
                "success",
                title=t("infocard.roster_match_title"),
                message=t("infocard.roster_match_desc"),
                icon="shield-check",
            )
        else:
            roster_banner = InlineBanner(
                "error",
                title=t("infocard.roster_mismatch_title"),
                message=t("infocard.roster_mismatch_desc"),
            )
        housing_card.add_widget(roster_banner)

        # ------------------------------------------------------------ footer
        footer = QHBoxLayout()
        footer.setSpacing(S("space-2"))
        footer.addStretch(1)
        close_btn = Button.secondary(t("common.close"))
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        root.addLayout(footer)

        apply_elevation(self, 2)


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
        gender = str(self.room_data.get("gender", "male")).strip().capitalize()
        capacity = int(self.room_data.get("capacity") or 1)

        self.setWindowTitle(t("infocard.room_title", block=block, number=number))
        self.setModal(True)
        self.setMinimumWidth(620)
        self.setStyleSheet(DESKTOP_STYLESHEET)

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
            t("infocard.capacity_card_desc", floor=floor, gender=gender),
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
        stats.addWidget(kpi_block(t("infocard.total_capacity"), capacity, "navy"), 1)
        stats.addWidget(kpi_block(t("infocard.occupied_beds"), occupied, "teal", icon="user-check"), 1)
        stats.addWidget(
            kpi_block(
                t("infocard.available_beds"),
                available,
                "green" if available > 0 else "danger",
                icon="bed",
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
            configure_table(
                table,
                [
                    t("infocard.table_col_name"),
                    t("infocard.table_col_card_id"),
                    t("infocard.table_col_faculty"),
                ],
            )
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
