"""
Residence Tlemcen — Modern Obsidian InfoCard Dialogs
High-contrast modal dialogs for Student Resident profiles and Room Occupancy inspection.
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
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from .icons import get_icon, get_pixmap
    from .theme import apply_button_style, get_badge_qss
except (ImportError, ValueError):
    try:
        from ..icons import get_icon, get_pixmap
        from ..theme import apply_button_style, get_badge_qss
    except (ImportError, ValueError):
        from desktop.app.ui.icons import get_icon, get_pixmap
        from desktop.app.ui.theme import apply_button_style, get_badge_qss


MODAL_BASE_QSS = """
QDialog {
    background-color: #0c0e15;
    color: #f8fafc;
}
QFrame#cardFrame {
    background-color: #121520;
    border: 1px solid #1c2234;
    border-radius: 12px;
}
QLabel {
    color: #f8fafc;
}
QTableWidget {
    background-color: #0b0d14;
    border: 1px solid #1c2234;
    border-radius: 8px;
    gridline-color: #181d2c;
    selection-background-color: #222a42;
    selection-color: #ffffff;
    alternate-background-color: #0e111a;
    outline: none;
}
QTableWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid #181d2c;
    color: #e2e8f0;
}
QTableWidget::item:selected {
    background-color: #222a42;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #080a0f;
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 8px 12px;
    border: none;
    border-bottom: 2px solid #1c2234;
    border-right: 1px solid #181d2c;
}
QScrollBar:vertical {
    border: none;
    background: #090a0f;
    width: 6px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #252c40;
    min-height: 20px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #3b4666;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


def _make_info_tile(label: str, value: str, subvalue: str | None = None, icon_name: str | None = None) -> QFrame:
    """Creates a high-contrast obsidian key-value information card tile."""
    tile = QFrame()
    tile.setStyleSheet("""
        QFrame {
            background-color: #0d1017;
            border: 1px solid #1a2032;
            border-radius: 8px;
        }
    """)
    layout = QVBoxLayout(tile)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(4)

    top_row = QHBoxLayout()
    top_row.setSpacing(6)
    if icon_name:
        icn_lbl = QLabel()
        icn_lbl.setPixmap(get_pixmap(icon_name, size=13, color="#64748b"))
        top_row.addWidget(icn_lbl)

    lbl = QLabel(label.upper())
    lbl.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
    top_row.addWidget(lbl)
    top_row.addStretch(1)
    layout.addLayout(top_row)

    val = QLabel(value if value else "—")
    val.setWordWrap(True)
    val.setStyleSheet("color: #f8fafc; font-size: 13px; font-weight: 600;")
    layout.addWidget(val)

    if subvalue:
        sub = QLabel(subvalue)
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 500;")
        layout.addWidget(sub)

    return tile


def _make_stat_card(label: str, value: str, color: str = "#f8fafc", bg_color: str = "#0d1017", border_color: str = "#1a2032") -> QFrame:
    """Creates a numerical metric card for room occupancy overview."""
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background-color: {bg_color};
            border: 1px solid {border_color};
            border-radius: 8px;
        }}
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(4)
    layout.setAlignment(Qt.AlignCenter)

    lbl = QLabel(label.upper())
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 0.6px;")
    layout.addWidget(lbl)

    val = QLabel(str(value))
    val.setAlignment(Qt.AlignCenter)
    val.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 800;")
    layout.addWidget(val)

    return card


class StudentInfoCardDialog(QDialog):
    """
    Sleek Obsidian Modal Dialog displaying comprehensive student resident profile information,
    academic credentials, assigned dormitory accommodation, and official admissions roster status.
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

        # Window Configuration
        first_name = str(self.student_data.get("first_name", "")).strip()
        last_name = str(self.student_data.get("last_name", "")).strip()
        full_name = f"{first_name} {last_name}".strip() or "Student Resident"
        self.setWindowTitle(f"Student Profile — {full_name}")
        self.setModal(True)
        self.setMinimumWidth(580)
        self.setStyleSheet(MODAL_BASE_QSS)

        # Dialog Root Layout
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(0)

        # Outer Obsidian Card Container
        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 22, 22, 22)
        card_layout.setSpacing(18)
        root_layout.addWidget(card)

        # -------------------------------------------------------------
        # 1. Header Banner
        # -------------------------------------------------------------
        header_row = QHBoxLayout()
        header_row.setSpacing(14)

        # University shield crest icon or user icon
        is_verified = bool(self.official_roster_data)
        avatar_box = QLabel()
        avatar_box.setFixedSize(52, 52)
        avatar_box.setAlignment(Qt.AlignCenter)

        if is_verified:
            avatar_box.setPixmap(get_pixmap("crest", size=28, color="#38bdf8"))
            avatar_box.setStyleSheet("""
                background-color: #082f49;
                border: 1px solid #0284c7;
                border-radius: 12px;
            """)
        else:
            avatar_box.setPixmap(get_pixmap("user", size=26, color="#818cf8"))
            avatar_box.setStyleSheet("""
                background-color: #1e1b4b;
                border: 1px solid #4338ca;
                border-radius: 12px;
            """)
        header_row.addWidget(avatar_box)

        # Name & Subtitle
        header_text_vbox = QVBoxLayout()
        header_text_vbox.setSpacing(3)

        name_lbl = QLabel(full_name)
        name_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        header_text_vbox.addWidget(name_lbl)

        card_id = str(self.student_data.get("card_id", "—")).strip()
        sub_text = f"Student Card ID: {card_id}"
        wilaya = self.student_data.get("wilaya")
        if wilaya:
            sub_text += f" • Wilaya {wilaya}"
        sub_lbl = QLabel(sub_text)
        sub_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        header_text_vbox.addWidget(sub_lbl)

        header_row.addLayout(header_text_vbox, 1)

        # Status Badge
        status_raw = str(self.student_data.get("status", "active")).lower().strip()
        status_lbl = QLabel()
        if status_raw in ("active", "approved", "resident"):
            status_lbl.setText("Active Resident")
            status_lbl.setStyleSheet(get_badge_qss("active"))
        elif status_raw in ("pending", "pending_verification"):
            status_lbl.setText("Pending Verification")
            status_lbl.setStyleSheet(get_badge_qss("pending"))
        elif status_raw in ("rejected", "cancelled"):
            status_lbl.setText("Rejected")
            status_lbl.setStyleSheet(get_badge_qss("rejected"))
        else:
            status_lbl.setText(status_raw.capitalize())
            status_lbl.setStyleSheet(get_badge_qss("info"))

        header_row.addWidget(status_lbl, 0, Qt.AlignVCenter)
        card_layout.addLayout(header_row)

        # Divider
        divider1 = QFrame()
        divider1.setFixedHeight(1)
        divider1.setStyleSheet("background-color: #1c2234;")
        card_layout.addWidget(divider1)

        # -------------------------------------------------------------
        # 2. Academic & Personal Details (2-Column Grid)
        # -------------------------------------------------------------
        section_lbl1 = QLabel("STUDENT ACADEMIC & IDENTITY PROFILE")
        section_lbl1.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 800; letter-spacing: 0.6px;")
        card_layout.addWidget(section_lbl1)

        gender_str = str(self.student_data.get("gender", "—")).strip().capitalize()
        univ_str = str(self.student_data.get("university", "—")).strip()
        fac_str = str(self.student_data.get("faculty", "—")).strip()

        # Date of birth: from roster if available, else from student_data
        dob_val = "—"
        if isinstance(self.official_roster_data, dict) and self.official_roster_data.get("birth_date"):
            dob_val = str(self.official_roster_data["birth_date"])
        elif self.student_data.get("birth_date"):
            dob_val = str(self.student_data["birth_date"])

        phone_val = str(self.student_data.get("phone", "")).strip()
        level_val = str(self.student_data.get("study_level", "")).strip()
        phone_sub = f"Level: {level_val}" if level_val else None

        grid = QHBoxLayout()
        grid.setSpacing(12)

        # Col 1
        col1 = QVBoxLayout()
        col1.setSpacing(10)
        col1.addWidget(_make_info_tile("Student Card ID", card_id, icon_name="user"))
        col1.addWidget(_make_info_tile("University", univ_str, icon_name="crest"))
        col1.addWidget(_make_info_tile("Date of Birth", dob_val))
        grid.addLayout(col1, 1)

        # Col 2
        col2 = QVBoxLayout()
        col2.setSpacing(10)
        col2.addWidget(_make_info_tile("Gender", gender_str))
        col2.addWidget(_make_info_tile("Faculty", fac_str))
        col2.addWidget(_make_info_tile("Contact Phone", phone_val or "—", subvalue=phone_sub, icon_name="phone"))
        grid.addLayout(col2, 1)

        card_layout.addLayout(grid)

        # -------------------------------------------------------------
        # 3. Accommodation & Official Verification Section
        # -------------------------------------------------------------
        section_lbl2 = QLabel("HOUSING & ADMISSIONS VERIFICATION")
        section_lbl2.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 800; letter-spacing: 0.6px;")
        card_layout.addWidget(section_lbl2)

        # Determine Assigned Room text
        room = self.student_data.get("rooms") or self.student_data.get("room") or {}
        if isinstance(room, list) and room:
            room = room[0]
        elif not isinstance(room, dict):
            room = {}

        block = room.get("block") or self.student_data.get("block")
        number = room.get("number") or self.student_data.get("room_number") or self.student_data.get("number")
        floor = room.get("floor") if room.get("floor") is not None else self.student_data.get("floor")

        if block and number:
            floor_text = f" (Floor {floor})" if floor is not None and str(floor) != "" else ""
            assigned_room_str = f"Block {block} — Room {number}{floor_text}"
        elif self.student_data.get("room_str"):
            assigned_room_str = str(self.student_data["room_str"])
        else:
            assigned_room_str = "Not assigned"

        # Room Card
        room_card = QFrame()
        room_card.setStyleSheet("""
            QFrame {
                background-color: #0d1017;
                border: 1px solid #1a2032;
                border-radius: 8px;
            }
        """)
        rc_layout = QHBoxLayout(room_card)
        rc_layout.setContentsMargins(14, 10, 14, 10)
        rc_layout.setSpacing(12)

        rc_icon = QLabel()
        rc_icon.setPixmap(get_pixmap("building", size=20, color="#38bdf8" if assigned_room_str != "Not assigned" else "#64748b"))
        rc_layout.addWidget(rc_icon)

        rc_vbox = QVBoxLayout()
        rc_vbox.setSpacing(2)
        rc_title = QLabel("ASSIGNED RESIDENTIAL ROOM")
        rc_title.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
        rc_vbox.addWidget(rc_title)

        rc_val = QLabel(assigned_room_str)
        rc_val.setStyleSheet(
            "color: #f8fafc; font-size: 13px; font-weight: 600;"
            if assigned_room_str != "Not assigned"
            else "color: #94a3b8; font-size: 13px; font-weight: 500;"
        )
        rc_vbox.addWidget(rc_val)
        rc_layout.addLayout(rc_vbox, 1)

        card_layout.addWidget(room_card)

        # Official Roster Match Banner
        roster_banner = QFrame()
        rb_layout = QHBoxLayout(roster_banner)
        rb_layout.setContentsMargins(14, 10, 14, 10)
        rb_layout.setSpacing(12)

        rb_icon = QLabel()
        rb_text_vbox = QVBoxLayout()
        rb_text_vbox.setSpacing(2)

        rb_tag = QLabel("OFFICIAL ROSTER MATCH")
        rb_tag.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")

        rb_title = QLabel()
        rb_title.setStyleSheet("font-size: 13px; font-weight: 700;")

        rb_desc = QLabel()
        rb_desc.setStyleSheet("font-size: 11px;")

        if is_verified:
            roster_banner.setStyleSheet("""
                QFrame {
                    background-color: #052e16;
                    border: 1px solid #10b981;
                    border-radius: 8px;
                }
            """)
            rb_icon.setPixmap(get_pixmap("check", size=20, color="#34d399"))
            rb_tag.setStyleSheet("color: #34d399; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
            rb_title.setText("Verified on Master Admissions List")
            rb_title.setStyleSheet("color: #34d399; font-size: 13px; font-weight: 700;")
            rb_desc.setText("Admissions record confirmed against official university master database.")
            rb_desc.setStyleSheet("color: #86efac; font-size: 11px;")
        else:
            roster_banner.setStyleSheet("""
                QFrame {
                    background-color: #2e1b04;
                    border: 1px solid #f59e0b;
                    border-radius: 8px;
                }
            """)
            rb_icon.setPixmap(get_pixmap("alert", size=20, color="#fbbf24"))
            rb_tag.setStyleSheet("color: #fbbf24; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
            rb_title.setText("Unmatched / Self-Registered")
            rb_title.setStyleSheet("color: #fbbf24; font-size: 13px; font-weight: 700;")
            rb_desc.setText("Record not confirmed on admissions roster. Verify physical registration dossier.")
            rb_desc.setStyleSheet("color: #fde68a; font-size: 11px;")

        rb_layout.addWidget(rb_icon)
        rb_text_vbox.addWidget(rb_tag)
        rb_text_vbox.addWidget(rb_title)
        rb_text_vbox.addWidget(rb_desc)
        rb_layout.addLayout(rb_text_vbox, 1)

        card_layout.addWidget(roster_banner)

        # -------------------------------------------------------------
        # 4. Modal Footer / Action Button
        # -------------------------------------------------------------
        footer_row = QHBoxLayout()
        footer_row.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(110)
        close_btn.setFixedHeight(34)
        apply_button_style(close_btn, "secondary")
        close_btn.clicked.connect(self.accept)
        footer_row.addWidget(close_btn)

        card_layout.addLayout(footer_row)


class RoomInfoCardDialog(QDialog):
    """
    Sleek Obsidian Modal Dialog displaying dormitory room specifications, capacity metrics,
    bed availability badges, and current active student resident occupants.
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

        # Room Properties
        block = str(self.room_data.get("block", "—")).strip()
        number = str(self.room_data.get("number") or self.room_data.get("room_number") or "—").strip()
        floor = str(self.room_data.get("floor", "0") if self.room_data.get("floor") is not None else "0").strip()
        gender = str(self.room_data.get("gender", "male")).strip().capitalize()
        capacity = int(self.room_data.get("capacity") or 1)

        # Window Configuration
        self.setWindowTitle(f"Room Details — Block {block} Room {number}")
        self.setModal(True)
        self.setMinimumWidth(620)
        self.setStyleSheet(MODAL_BASE_QSS)

        # Dialog Root Layout
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(0)

        # Outer Obsidian Card Container
        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 22, 22, 22)
        card_layout.setSpacing(16)
        root_layout.addWidget(card)

        # Fetch Occupants if client is provided
        occupants: list[dict[str, Any]] = []
        room_id = self.room_data.get("id")
        if self.client is not None and room_id:
            try:
                resp = (
                    self.client.table("students")
                    .select("card_id, first_name, last_name, faculty")
                    .eq("room_id", room_id)
                    .eq("status", "active")
                    .execute()
                )
                occupants = resp.data or []
            except Exception:
                occupants = self.room_data.get("occupants") or self.room_data.get("residents") or []
        elif "occupants" in self.room_data and isinstance(self.room_data["occupants"], list):
            occupants = self.room_data["occupants"]
        elif "residents" in self.room_data and isinstance(self.room_data["residents"], list):
            occupants = self.room_data["residents"]

        # Calculate Occupied & Available Beds
        if occupants:
            occupied = len(occupants)
        elif "occupied" in self.room_data and self.room_data["occupied"] is not None:
            occupied = int(self.room_data["occupied"])
        elif "occupied_beds" in self.room_data and self.room_data["occupied_beds"] is not None:
            occupied = int(self.room_data["occupied_beds"])
        else:
            occupied = 0

        available = max(0, capacity - occupied)

        # -------------------------------------------------------------
        # 1. Header Banner
        # -------------------------------------------------------------
        header_row = QHBoxLayout()
        header_row.setSpacing(14)

        # Building Icon Box
        icon_box = QLabel()
        icon_box.setFixedSize(52, 52)
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setPixmap(get_pixmap("building", size=28, color="#38bdf8"))
        icon_box.setStyleSheet("""
            background-color: #082f49;
            border: 1px solid #0284c7;
            border-radius: 12px;
        """)
        header_row.addWidget(icon_box)

        # Title & Subtitle
        header_text_vbox = QVBoxLayout()
        header_text_vbox.setSpacing(3)

        title_lbl = QLabel(f"Block {block} — Room {number}")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        header_text_vbox.addWidget(title_lbl)

        sub_lbl = QLabel(f"Floor {floor} • Designated for {gender} Students")
        sub_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        header_text_vbox.addWidget(sub_lbl)

        header_row.addLayout(header_text_vbox, 1)

        # Status Badge ("Full" in crimson or "{N} Bed(s) Available" in emerald)
        badge_lbl = QLabel()
        if available <= 0:
            badge_lbl.setText("Full")
            badge_lbl.setStyleSheet("""
                background-color: #360808;
                color: #f87171;
                border: 1px solid #ef4444;
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
            """)
        else:
            beds_text = f"{available} Bed Available" if available == 1 else f"{available} Beds Available"
            badge_lbl.setText(beds_text)
            badge_lbl.setStyleSheet("""
                background-color: #052e16;
                color: #34d399;
                border: 1px solid #10b981;
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
            """)

        header_row.addWidget(badge_lbl, 0, Qt.AlignVCenter)
        card_layout.addLayout(header_row)

        # Divider
        divider1 = QFrame()
        divider1.setFixedHeight(1)
        divider1.setStyleSheet("background-color: #1c2234;")
        card_layout.addWidget(divider1)

        # -------------------------------------------------------------
        # 2. Capacity & Occupancy Section
        # -------------------------------------------------------------
        sec_lbl1 = QLabel("CAPACITY & BED OCCUPANCY")
        sec_lbl1.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 800; letter-spacing: 0.6px;")
        card_layout.addWidget(sec_lbl1)

        stat_row = QHBoxLayout()
        stat_row.setSpacing(12)

        stat_row.addWidget(_make_stat_card("Total Beds", str(capacity), color="#f8fafc"), 1)
        stat_row.addWidget(_make_stat_card("Occupied Beds", str(occupied), color="#38bdf8"), 1)

        avail_color = "#f87171" if available <= 0 else "#34d399"
        avail_bg = "#2a0909" if available <= 0 else "#052e16"
        avail_border = "#ef4444" if available <= 0 else "#10b981"
        stat_row.addWidget(
            _make_stat_card("Available Beds", str(available), color=avail_color, bg_color=avail_bg, border_color=avail_border),
            1,
        )

        card_layout.addLayout(stat_row)

        # -------------------------------------------------------------
        # 3. Current Occupants / Residents Section
        # -------------------------------------------------------------
        sec_lbl2 = QLabel("CURRENT ROOM OCCUPANTS & RESIDENTS")
        sec_lbl2.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 800; letter-spacing: 0.6px;")
        card_layout.addWidget(sec_lbl2)

        if occupants:
            table = QTableWidget(len(occupants), 3)
            table.setHorizontalHeaderLabels(["Resident Name", "Student Card ID", "Faculty"])
            table.setSelectionBehavior(QTableWidget.SelectRows)
            table.setSelectionMode(QTableWidget.SingleSelection)
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

            for i, occ in enumerate(occupants):
                fname = str(occ.get("first_name", "")).strip()
                lname = str(occ.get("last_name", "")).strip()
                occ_name = f"{fname} {lname}".strip() or "Resident Student"

                name_item = QTableWidgetItem(occ_name)
                name_item.setIcon(get_icon("user", size=14, color="#818cf8"))

                card_item = QTableWidgetItem(str(occ.get("card_id", "—")))
                card_item.setIcon(get_icon("official_list", size=14, color="#38bdf8"))

                fac_item = QTableWidgetItem(str(occ.get("faculty", "—")))

                table.setItem(i, 0, name_item)
                table.setItem(i, 1, card_item)
                table.setItem(i, 2, fac_item)

            table.setMinimumHeight(120)
            table.setMaximumHeight(200)
            card_layout.addWidget(table)
        else:
            empty_frame = QFrame()
            empty_frame.setStyleSheet("""
                QFrame {
                    background-color: #0d1017;
                    border: 1px dashed #1f273d;
                    border-radius: 8px;
                    padding: 16px;
                }
            """)
            empty_layout = QVBoxLayout(empty_frame)
            empty_layout.setAlignment(Qt.AlignCenter)
            empty_layout.setSpacing(6)

            icon_lbl = QLabel()
            icon_lbl.setAlignment(Qt.AlignCenter)
            icon_lbl.setPixmap(get_pixmap("rooms", size=24, color="#475569"))
            empty_layout.addWidget(icon_lbl)

            empty_lbl = QLabel("No residents currently assigned to this room.")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 500;")
            empty_layout.addWidget(empty_lbl)

            card_layout.addWidget(empty_frame)

        # -------------------------------------------------------------
        # 4. Modal Footer / Action Button
        # -------------------------------------------------------------
        footer_row = QHBoxLayout()
        footer_row.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(110)
        close_btn.setFixedHeight(34)
        apply_button_style(close_btn, "secondary")
        close_btn.clicked.connect(self.accept)
        footer_row.addWidget(close_btn)

        card_layout.addLayout(footer_row)


__all__ = ["StudentInfoCardDialog", "RoomInfoCardDialog"]
