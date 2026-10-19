"""RÉSIVO — desktop shell: authored sidebar navigation, stacked pages, live sync.

Visual layer only (``docs/DESIGN.md`` §7). Behaviour is frozen: every client
call, the ``LiveSyncWorker`` lifecycle, the 3-second bounded worker shutdown,
the sign-out flow and the page instantiation order are unchanged.

Widget contracts kept for the tests
-----------------------------------
``MainWindow(client)``; minimum 980x640; ``QPushButton#signOutButton`` with the
text ``"Sign out"``; ``_shutdown_workers()`` (3 s bounded); ``on_sign_out_clicked()``
(shutdown → ``client.auth.sign_out()`` → lazy ``LoginWindow``); module-level page
names imported from ``.pages.*`` (monkeypatched by tests); ``self.pages`` keyed by
nav label; ``self.nav`` wired with ``currentRowChanged`` → ``stack.setCurrentIndex``;
``LiveSyncWorker(client, interval_ms=2000)`` started after the UI is built.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..client import current_role
from . import components, theme
from .components import Avatar, BrandMark, Button, LiveDot
from .icons import get_icon, get_pixmap
from .live_sync import LiveSyncWorker
from .pages.overview import OverviewPage
from .pages.pending import PendingPage
from .pages.residents import ResidentsPage
from .pages.rooms import RoomsPage
from .pages.maintenance import MaintenancePage
from .pages.room_changes import RoomChangesPage
from .pages.official_list import OfficialListPage
from .pages.staff_accounts import StaffAccountsPage
from .pages.settings import SettingsPage
from .theme import C, DESKTOP_STYLESHEET, S

# Menu row dimensions (enlarged for prominence and readability)
_NAV_ROW_HEIGHT = 48
_NAV_ICON_SIZE = 22
_SIDEBAR_EXPANDED_WIDTH = S("size-sidebar")  # 248 px
_SIDEBAR_MINIMIZED_WIDTH = 72

# Live-sync indicator windows (seconds): a tick this recent means connected,
# silence beyond the second value means offline; in between = reconnecting.
_LIVE_CONNECTED_WINDOW_S = 6.0
_LIVE_OFFLINE_WINDOW_S = 30.0
_IDLE_STATUS = "Live sync active"
_ROLE_LABELS = {"admin": "Administrator", "staff": "Housing staff"}


def _brand_strip_qss() -> str:
    """3 px brand-gradient line at the top of the sidebar (DESIGN.md §1/§7)."""
    return (
        "QWidget#brandStrip {"
        " background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
        f" stop:0 {C('navy-800')}, stop:0.55 {C('teal-600')}, stop:1 {C('green-500')});"
        " }"
    )


def _nav_qss() -> str:
    """Sidebar rows: hover, active navy-800 + 2 px gold marker, focus ring.

    Every state keeps the same 2 px border box, so ``navy-800``, the gold
    marker and the focus ring never shift the row content.
    """
    return (
        "QPushButton#navRow {"
        " background-color: transparent; border: 2px solid transparent;"
        f" border-radius: {C('radius-input')}; padding: 0px;"
        " }"
        f"QPushButton#navRow:hover {{ background-color: {C('sidebar-hover')}; }}"
        f"QPushButton#navRow:focus {{ border-color: {C('teal-500')}; }}"
        "QPushButton#navRow:checked {"
        f" background-color: {C('navy-800')}; border-left: 2px solid {C('gold-500')};"
        " }"
        f"QPushButton#navRow:checked:hover {{ background-color: {C('navy-800')}; }}"
    )


def _ghost_on_navy_qss(obj_name: str = "signOutButton", centered: bool = False) -> str:
    """Ghost variant tuned for the navy sidebar (sign-out and minimize buttons)."""
    align = "center" if centered else "left"
    padding = "8px 0px" if centered else f"8px {C('space-3')}"
    focus_pad = "7px 0px" if centered else "7px 11px"
    return (
        f"QPushButton#{obj_name} {{"
        " background-color: transparent;"
        f" color: {C('text-on-dark')}; border: 1px solid transparent;"
        f" border-radius: {C('radius-input')};"
        f" padding: {padding}; text-align: {align};"
        f" font-size: {C('fs-body')}; font-weight: {C('fw-semibold')};"
        " }"
        f"QPushButton#{obj_name}:hover {{"
        f" background-color: {C('sidebar-hover')}; color: {C('surface')};"
        f" border-color: {C('sidebar-hover')};"
        " }"
        f"QPushButton#{obj_name}:pressed {{ background-color: {C('navy-800')}; }}"
        f"QPushButton#{obj_name}:focus {{ border: 2px solid {C('teal-500')}; padding: {focus_pad}; }}"
    )


def _role_pill_qss() -> str:
    """Small role chip on the sidebar user card (token colours only)."""
    return (
        f"background-color: {C('navy-700')}; color: {C('text-on-dark')};"
        f" border-radius: {C('radius-input')};"
        f" padding: 1px {C('pill-pad-x')};"
        f" font-size: {C('fs-overline')}; font-weight: {C('fw-semibold')};"
    )


def _session_display_name(client) -> str:
    """User-card name from the stored session, else the neutral fallback.

    Reads the already-persisted session (no network call) and only accepts
    string metadata, so mock clients fall through to the fallback.
    """
    try:
        session = client.auth.get_session()
        user = getattr(session, "user", None)
        metadata = getattr(user, "user_metadata", None) or {}
        if isinstance(metadata, dict):
            for key in ("full_name", "name"):
                value = metadata.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        email = getattr(user, "email", None)
        if isinstance(email, str) and email.strip():
            local = email.split("@")[0].replace(".", " ").replace("_", " ").strip()
            if local:
                return local.title()
    except Exception:
        pass
    return "Housing staff"


class _NavRow(QPushButton):
    """One 48 px sidebar nav row: icon + label + optional gold count pill.

    Checkable push button inside an exclusive ``QButtonGroup``; Up/Down arrow
    keys move the selection, Tab keeps the natural focus chain.
    """

    def __init__(self, nav: "_SidebarNav", label: str, icon_name: str, parent=None):
        super().__init__(parent)
        self._nav = nav
        self._label_text = label
        self._icon_name = icon_name
        self._hovered = False
        self._badge_count = 0
        self._minimized = False
        self.setObjectName("navRow")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedHeight(_NAV_ROW_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip(label)
        self.setAccessibleName(label)

        self._row_layout = QHBoxLayout(self)
        self._row_layout.setContentsMargins(S("space-3"), 0, S("space-3"), 0)
        self._row_layout.setSpacing(S("space-3"))

        self._icon = QLabel(self)
        self._icon.setFixedSize(_NAV_ICON_SIZE, _NAV_ICON_SIZE)
        self._icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._label = QLabel(label, self)
        label_font = theme.font("h3")
        label_font.setWeight(QFont.Weight(S("fw-semibold")))
        self._label.setFont(label_font)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._badge = QLabel("", self)
        self._badge.setObjectName("navBadge")
        theme.apply_role(self._badge, "nav-badge")
        self._badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._badge.hide()

        self._row_layout.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignVCenter)
        self._row_layout.addWidget(self._label, 1, Qt.AlignmentFlag.AlignVCenter)
        self._row_layout.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.toggled.connect(lambda _checked: self._refresh())
        self._refresh()

    # -- public API ---------------------------------------------------------
    def set_badge(self, count) -> None:
        """Show/hide the gold count pill (hidden at 0)."""
        value = int(count or 0)
        self._badge_count = value
        self._badge.setText(str(value))
        if self._minimized:
            self._badge.hide()
            count_suffix = f" ({value})" if value > 0 else ""
            self.setToolTip(f"{self._label_text}{count_suffix}")
        else:
            self._badge.setVisible(value > 0)
            self.setToolTip(self._label_text)

    def set_minimized(self, minimized: bool) -> None:
        """Toggle minimized icon-only display with enriched tooltip."""
        self._minimized = minimized
        if minimized:
            self._label.hide()
            self._badge.hide()
            self._row_layout.setContentsMargins(0, 0, 0, 0)
            self._row_layout.setAlignment(self._icon, Qt.AlignmentFlag.AlignCenter)
            count_suffix = f" ({self._badge_count})" if self._badge_count > 0 else ""
            self.setToolTip(f"{self._label_text}{count_suffix}")
        else:
            self._label.show()
            self._badge.setVisible(self._badge_count > 0)
            self._row_layout.setContentsMargins(S("space-3"), 0, S("space-3"), 0)
            self._row_layout.setAlignment(self._icon, Qt.AlignmentFlag.AlignVCenter)
            self.setToolTip(self._label_text)
        self._refresh()

    # -- visual state -------------------------------------------------------
    def _refresh(self) -> None:
        if self.isChecked():
            ink = "surface"
        elif self._hovered or self.hasFocus():
            ink = "text-on-dark"
        else:
            ink = "text-on-dark-muted"
        self._label.setStyleSheet(f"color: {C(ink)}; background-color: transparent;")
        self._icon.setPixmap(get_pixmap(self._icon_name, _NAV_ICON_SIZE, C(ink)))

    def enterEvent(self, event):  # noqa: N802 - Qt API
        self._hovered = True
        self._refresh()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - Qt API
        self._hovered = False
        self._refresh()
        super().leaveEvent(event)

    def focusInEvent(self, event):  # noqa: N802 - Qt API
        super().focusInEvent(event)
        self._refresh()

    def focusOutEvent(self, event):  # noqa: N802 - Qt API
        super().focusOutEvent(event)
        self._refresh()

    def keyPressEvent(self, event):  # noqa: N802 - Qt API
        if event.key() == Qt.Key.Key_Down:
            self._nav.move_current(1)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Up:
            self._nav.move_current(-1)
            event.accept()
            return
        super().keyPressEvent(event)


class _SidebarNav(QWidget):
    """Authored sidebar navigation (replaces the old ``QListWidget``).

    Exposes the same shell contract: ``currentRowChanged``,
    ``count()``, ``currentRow()``, ``setCurrentRow()``.
    """

    currentRowChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarNav")
        self._rows: list[_NavRow] = []
        self._by_key: dict[str, _NavRow] = {}
        self._current = -1
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self._scroll)

        holder = QWidget()
        holder.setObjectName("sidebarNavList")
        self._list = QVBoxLayout(holder)
        self._list.setContentsMargins(S("space-2"), S("space-2"), S("space-2"), S("space-2"))
        self._list.setSpacing(S("space-2"))
        self._list.addStretch(1)
        self._scroll.setWidget(holder)
        self.setStyleSheet(_nav_qss())

    def set_minimized(self, minimized: bool) -> None:
        """Propagate minimized state to all rows and adjust container padding."""
        if minimized:
            self._list.setContentsMargins(S("space-1"), S("space-2"), S("space-1"), S("space-2"))
        else:
            self._list.setContentsMargins(S("space-2"), S("space-2"), S("space-2"), S("space-2"))
        for row in self._rows:
            row.set_minimized(minimized)

    def add_row(self, label: str, icon_name: str, key: str | None = None) -> _NavRow:
        row = _NavRow(self, label, icon_name)
        index = len(self._rows)
        self._rows.append(row)
        if key:
            self._by_key[key] = row
        self._group.addButton(row, index)
        row.clicked.connect(lambda _checked=False, row_index=index: self._activate(row_index))
        self._list.insertWidget(self._list.count() - 1, row)
        return row

    def set_badge(self, key: str, count) -> None:
        row = self._by_key.get(key)
        if row is not None:
            row.set_badge(count)

    def count(self) -> int:
        return len(self._rows)

    def currentRow(self) -> int:
        return self._current

    def setCurrentRow(self, index: int) -> None:
        self._activate(int(index))

    def move_current(self, delta: int) -> None:
        """Up/Down arrow navigation (keeps the QListWidget keyboard behaviour)."""
        if not self._rows:
            return
        target = max(0, min(self._current + delta, len(self._rows) - 1))
        self._activate(target)
        self._rows[target].setFocus(Qt.FocusReason.OtherFocusReason)

    def _activate(self, index: int) -> None:
        if not 0 <= index < len(self._rows) or index == self._current:
            return
        self._current = index
        self._rows[index].setChecked(True)
        self.currentRowChanged.emit(index)


class MainWindow(QMainWindow):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.role = current_role(client)
        self._sidebar_minimized = False
        self.setWindowTitle("RÉSIVO — Staff Console")
        self.setMinimumSize(980, 640)
        self.resize(1180, 760)
        self.setStyleSheet(DESKTOP_STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(self._build_content(), 1)

        # Pages instantiation — order and module-level names unchanged.
        self.pages: dict[str, QWidget] = {}
        self.overview_page = OverviewPage(client)
        self.pending_page = PendingPage(client)
        self.residents_page = ResidentsPage(client)
        self.rooms_page = RoomsPage(client)
        self.maintenance_page = MaintenancePage(client)
        self.room_changes_page = RoomChangesPage(client)
        self.official_list_page = OfficialListPage(client)

        self._add_nav_item("Overview", "overview", self.overview_page)
        self._add_nav_item("Pending accounts", "pending", self.pending_page)
        self._add_nav_item("Residents", "residents", self.residents_page)
        self._add_nav_item("Rooms", "rooms", self.rooms_page)
        self._add_nav_item("Maintenance", "maintenance", self.maintenance_page)
        self._add_nav_item("Room changes", "room_changes", self.room_changes_page)
        self._add_nav_item("Official list", "official_list", self.official_list_page)

        if self.role == "admin":
            self.staff_accounts_page = StaffAccountsPage(client)
            self._add_nav_item("Staff accounts", "staff_accounts", self.staff_accounts_page)

        self.settings_page = SettingsPage(client)
        self._add_nav_item("Settings", "settings", self.settings_page)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        # Status bar — the live-sync line only (events go to toasts).
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(_IDLE_STATUS)

        # Live-sync indicator state (driven by the existing tick/alert signals).
        self._started_at = time.monotonic()
        self._last_tick_at: float | None = None
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(2000)
        self._live_timer.timeout.connect(self._refresh_live_state)
        self._live_timer.start()
        self._set_live_state("reconnecting")

        # Start live background sync worker (unchanged behaviour).
        self.sync_worker = LiveSyncWorker(client, interval_ms=2000)
        self.sync_worker.sync_tick.connect(self.on_live_sync_tick)
        self.sync_worker.alert_event.connect(self.on_live_alert)
        self.sync_worker.start()

    # ------------------------------------------------------------------ shell
    def _build_sidebar(self) -> QWidget:
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setObjectName("sidebarContainer")
        self.sidebar_widget.setFixedWidth(_SIDEBAR_EXPANDED_WIDTH)
        layout = QVBoxLayout(self.sidebar_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 3 px brand-gradient line at the very top.
        self.brand_strip = QWidget()
        self.brand_strip.setObjectName("brandStrip")
        self.brand_strip.setFixedHeight(3)
        self.brand_strip.setStyleSheet(_brand_strip_qss())
        layout.addWidget(self.brand_strip)

        # Brand block: white mark + RÉSIVO wordmark + institutional caption.
        self.brand_block = QWidget()
        self.brand_layout = QHBoxLayout(self.brand_block)
        self.brand_layout.setContentsMargins(S("space-4"), S("space-4"), S("space-4"), S("space-3"))
        self.brand_layout.setSpacing(S("space-3"))
        self.brand_mark = BrandMark(variant="mark", color="white", size=32)
        self.brand_texts = QWidget()
        texts_layout = QVBoxLayout(self.brand_texts)
        texts_layout.setContentsMargins(0, 0, 0, 0)
        texts_layout.setSpacing(0)
        wordmark = QLabel("RÉSIVO")
        theme.apply_role(wordmark, "h2")
        wordmark.setStyleSheet(f"color: {C('surface')};")
        caption = QLabel("Cité Universitaire · Tlemcen")
        theme.apply_role(caption, "small")
        caption.setStyleSheet(f"color: {C('text-on-dark-muted')};")
        texts_layout.addWidget(wordmark)
        texts_layout.addWidget(caption)
        self.brand_layout.addWidget(self.brand_mark, 0, Qt.AlignmentFlag.AlignVCenter)
        self.brand_layout.addWidget(self.brand_texts, 1)
        layout.addWidget(self.brand_block)

        self.nav = _SidebarNav()
        layout.addWidget(self.nav, 1)
        layout.addWidget(self._build_sidebar_footer())
        return self.sidebar_widget

    def _build_sidebar_footer(self) -> QWidget:
        self.sidebar_footer = QWidget()
        self.sidebar_footer.setObjectName("sidebarFooter")
        self.sidebar_footer_layout = QVBoxLayout(self.sidebar_footer)
        self.sidebar_footer_layout.setContentsMargins(S("space-3"), S("space-3"), S("space-3"), S("space-4"))
        self.sidebar_footer_layout.setSpacing(S("space-3"))

        # User card: avatar + session name + role pill.
        display_name = _session_display_name(self.client)
        self.user_row_widget = QWidget()
        self.user_row_layout = QHBoxLayout(self.user_row_widget)
        self.user_row_layout.setContentsMargins(0, 0, 0, 0)
        self.user_row_layout.setSpacing(S("space-3"))
        self.user_avatar = Avatar(display_name, size=S("size-control"))
        self.user_avatar.setToolTip(f"{display_name} • {_ROLE_LABELS.get(self.role, 'Housing staff')}")

        self.user_texts = QWidget()
        name_column = QVBoxLayout(self.user_texts)
        name_column.setContentsMargins(0, 0, 0, 0)
        name_column.setSpacing(2)
        self.user_name = QLabel(display_name)
        theme.apply_role(self.user_name, "small")
        self.user_name.setStyleSheet(f"color: {C('text-on-dark')};")
        self.role_pill = QLabel(_ROLE_LABELS.get(self.role, "Housing staff"))
        self.role_pill.setStyleSheet(_role_pill_qss())
        name_column.addWidget(self.user_name)
        name_column.addWidget(self.role_pill, 0, Qt.AlignmentFlag.AlignLeft)

        self.user_row_layout.addWidget(self.user_avatar, 0, Qt.AlignmentFlag.AlignVCenter)
        self.user_row_layout.addWidget(self.user_texts, 1)
        self.sidebar_footer_layout.addWidget(self.user_row_widget)

        # Sign-out (ghost, icon + "Sign out"; objectName kept for the tests).
        self.sign_out_btn = Button.ghost("Sign out")
        self.sign_out_btn.setObjectName("signOutButton")
        self.sign_out_btn.setIcon(get_icon("log-out", size=18, color=C("text-on-dark")))
        self.sign_out_btn.setIconSize(QSize(18, 18))
        self.sign_out_btn.setStyleSheet(_ghost_on_navy_qss("signOutButton", centered=False))
        self.sign_out_btn.setFixedHeight(38)
        self.sign_out_btn.setToolTip("Sign out")
        self.sign_out_btn.clicked.connect(self.on_sign_out_clicked)
        self.sidebar_footer_layout.addWidget(self.sign_out_btn)

        # Minimize / Expand menu button directly below Sign out
        self.toggle_menu_btn = Button.ghost("Minimize menu")
        self.toggle_menu_btn.setObjectName("toggleMenuButton")
        self.toggle_menu_btn.setIcon(get_icon("chevron-left", size=18, color=C("text-on-dark")))
        self.toggle_menu_btn.setIconSize(QSize(18, 18))
        self.toggle_menu_btn.setStyleSheet(_ghost_on_navy_qss("toggleMenuButton", centered=False))
        self.toggle_menu_btn.setFixedHeight(38)
        self.toggle_menu_btn.setToolTip("Minimize sidebar menu")
        self.toggle_menu_btn.setAccessibleName("Minimize menu")
        self.toggle_menu_btn.clicked.connect(self.toggle_sidebar)
        self.sidebar_footer_layout.addWidget(self.toggle_menu_btn)

        # Live-sync indicator: dot + text label (never colour alone).
        self.live_row_widget = QWidget()
        self.live_row = QHBoxLayout(self.live_row_widget)
        self.live_row.setContentsMargins(0, 0, 0, 0)
        self.live_row.setSpacing(S("space-2"))
        self.live_dot = LiveDot()
        self.live_label = QLabel("Live sync")
        theme.apply_role(self.live_label, "small")
        self.live_label.setStyleSheet(f"color: {C('text-on-dark-muted')};")
        self.live_row.addWidget(self.live_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self.live_row.addWidget(self.live_label, 1)
        self.sidebar_footer_layout.addWidget(self.live_row_widget)
        return self.sidebar_footer

    def toggle_sidebar(self) -> None:
        """Collapse or expand the sidebar navigation."""
        self._sidebar_minimized = not self._sidebar_minimized
        if self._sidebar_minimized:
            self.sidebar_widget.setFixedWidth(_SIDEBAR_MINIMIZED_WIDTH)
            self.brand_texts.hide()
            self.brand_layout.setContentsMargins(0, S("space-4"), 0, S("space-3"))
            self.brand_layout.setAlignment(self.brand_mark, Qt.AlignmentFlag.AlignCenter)
            self.nav.set_minimized(True)
            self.user_texts.hide()
            self.user_row_layout.setAlignment(self.user_avatar, Qt.AlignmentFlag.AlignCenter)

            self.sidebar_footer_layout.setContentsMargins(S("space-2"), S("space-3"), S("space-2"), S("space-4"))

            self.sign_out_btn.setText("")
            self.sign_out_btn.setToolTip("Sign out")
            self.sign_out_btn.setStyleSheet(_ghost_on_navy_qss("signOutButton", centered=True))

            self.toggle_menu_btn.setText("")
            self.toggle_menu_btn.setToolTip("Expand menu")
            self.toggle_menu_btn.setAccessibleName("Expand menu")
            self.toggle_menu_btn.setIcon(get_icon("chevron-right", size=18, color=C("text-on-dark")))
            self.toggle_menu_btn.setStyleSheet(_ghost_on_navy_qss("toggleMenuButton", centered=True))

            self.live_label.hide()
            self.live_row.setAlignment(self.live_dot, Qt.AlignmentFlag.AlignCenter)
        else:
            self.sidebar_widget.setFixedWidth(_SIDEBAR_EXPANDED_WIDTH)
            self.brand_layout.setContentsMargins(S("space-4"), S("space-4"), S("space-4"), S("space-3"))
            self.brand_layout.setAlignment(self.brand_mark, Qt.AlignmentFlag.AlignVCenter)
            self.brand_texts.show()
            self.nav.set_minimized(False)
            self.user_row_layout.setAlignment(self.user_avatar, Qt.AlignmentFlag.AlignVCenter)
            self.user_texts.show()

            self.sidebar_footer_layout.setContentsMargins(S("space-3"), S("space-3"), S("space-3"), S("space-4"))

            self.sign_out_btn.setText("Sign out")
            self.sign_out_btn.setToolTip("Sign out")
            self.sign_out_btn.setStyleSheet(_ghost_on_navy_qss("signOutButton", centered=False))

            self.toggle_menu_btn.setText("Minimize menu")
            self.toggle_menu_btn.setToolTip("Minimize sidebar menu")
            self.toggle_menu_btn.setAccessibleName("Minimize menu")
            self.toggle_menu_btn.setIcon(get_icon("chevron-left", size=18, color=C("text-on-dark")))
            self.toggle_menu_btn.setStyleSheet(_ghost_on_navy_qss("toggleMenuButton", centered=False))

            self.live_row.setAlignment(self.live_dot, Qt.AlignmentFlag.AlignVCenter)
            self.live_label.show()


    def _build_content(self) -> QWidget:
        content = QWidget()
        content.setProperty("background", "canvas")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(S("space-8"), S("space-8"), S("space-8"), S("space-8"))
        layout.setSpacing(0)
        self.stack = QStackedWidget()
        self.stack.currentChanged.connect(self._animate_stack_page)
        layout.addWidget(self.stack)
        return content

    # -------------------------------------------------------------- navigation
    def _add_nav_item(self, title: str, icon_name: str, widget: QWidget):
        self.pages[title] = widget
        self.stack.addWidget(widget)
        # Badge keys reuse the legacy icon keys (pending / maintenance / room_changes).
        self.nav.add_row(title, icon_name, key=icon_name)

    def _animate_stack_page(self, index: int) -> None:
        """Fade the incoming page (150 ms) — table rows are never animated."""
        widget = self.stack.widget(index)
        if widget is None or not self.isVisible() or widget.graphicsEffect() is not None:
            return
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(S("dur-fast"))
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda w=widget: w.setGraphicsEffect(None))
        self._page_animation = animation
        animation.start()

    # --------------------------------------------------------------- live sync
    def _set_live_state(self, state: str) -> None:
        """Live indicator: dot state + matching text label + tooltip."""
        text = {
            "connected": "Live sync connected",
            "reconnecting": "Live sync reconnecting",
            "offline": "Live sync offline",
        }.get(state, "Live sync offline")
        self.live_dot.set_state(state)
        self.live_dot.setToolTip(text)
        self.live_label.setText(text)
        self.live_label.setToolTip(text)

    def _refresh_live_state(self) -> None:
        reference = self._last_tick_at if self._last_tick_at is not None else self._started_at
        elapsed = time.monotonic() - reference
        if self._last_tick_at is not None and elapsed <= _LIVE_CONNECTED_WINDOW_S:
            self._set_live_state("connected")
        elif elapsed <= _LIVE_OFFLINE_WINDOW_S:
            self._set_live_state("reconnecting")
        else:
            self._set_live_state("offline")

    def on_live_alert(self, msg: str):
        """Live event → Toast (icon + message); no emoji status text."""
        components.show_toast(self, msg, kind="info", icon="bell")

    def on_live_sync_tick(self, data: dict):
        pending_students = data.get("pending_students", [])
        reports = data.get("reports", [])
        open_reports_count = data.get("open_reports_count", 0)
        pending_requests = data.get("pending_requests", [])
        timestamp = data.get("timestamp", "")

        p_count = len(pending_students)
        m_count = open_reports_count
        r_count = len(pending_requests)
        active_count = data.get("active_residents_count", 0)

        # 1. Live-sync line: last update time + counts.
        self.status_bar.showMessage(
            f"{_IDLE_STATUS} • Last update: {timestamp} • Pending: {p_count}"
            f" • Open tickets: {m_count} • Transfers: {r_count}"
        )

        # 2. Gold count pills on the sidebar rows.
        self.nav.set_badge("pending", p_count)
        self.nav.set_badge("maintenance", m_count)
        self.nav.set_badge("room_changes", r_count)

        # 3. Live indicator: a fresh tick means connected.
        self._last_tick_at = time.monotonic()
        self._set_live_state("connected")

        # 4. Deliver live data to pages.
        self.overview_page.apply_live_data(p_count, m_count, r_count, active_count)
        self.pending_page.apply_live_data(pending_students)
        self.maintenance_page.apply_live_data(reports)
        self.room_changes_page.apply_live_data(pending_requests)

    # ------------------------------------------------------------------- flow
    def _shutdown_workers(self):
        if hasattr(self, "sync_worker") and self.sync_worker.isRunning():
            self.sync_worker.stop()
            if not self.sync_worker.wait(3000):
                self.sync_worker.terminate()
                self.sync_worker.wait(1000)
        if hasattr(self, "settings_page") and hasattr(self.settings_page, "health_worker") and self.settings_page.health_worker.isRunning():
            self.settings_page.health_worker.stop()
            if not self.settings_page.health_worker.wait(3000):
                self.settings_page.health_worker.terminate()
                self.settings_page.health_worker.wait(1000)

    def on_sign_out_clicked(self):
        self._shutdown_workers()
        try:
            if hasattr(self.client, "auth") and hasattr(self.client.auth, "sign_out"):
                self.client.auth.sign_out()
        except Exception:
            pass

        from .login_window import LoginWindow
        self.login_window = LoginWindow()
        self.login_window.show()
        self.close()

    def closeEvent(self, event):
        self._shutdown_workers()
        if getattr(self, "_live_timer", None) is not None:
            self._live_timer.stop()
        super().closeEvent(event)
