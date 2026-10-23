"""RÉSIVO — desktop shell: authored sidebar navigation, stacked pages, live sync.

Visual layer only (``docs/DESIGN.md`` §7). Behaviour is frozen: every client
call, the ``LiveSyncWorker`` lifecycle, the cooperative worker shutdown, the
sign-out flow and the page instantiation order are unchanged.

Widget contracts kept for the tests
-----------------------------------
``MainWindow(client)``; minimum 980x640; ``QPushButton#signOutButton`` with the
text ``"Sign out"``; ``_shutdown_workers()`` (3 s bounded, never terminates);
``on_sign_out_clicked()`` (shutdown → ``client.auth.sign_out()`` → lazy
``LoginWindow``); module-level page names imported from ``.pages.*``
(monkeypatched by tests); ``self.pages`` keyed by nav label; ``self.nav`` wired
with ``currentRowChanged`` → ``stack.setCurrentIndex``;
``LiveSyncWorker(client, interval_ms=2000)`` started after the UI is built.
"""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
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

from ..client import (
    clear_local_session,
    current_role,
    forget_role,
    remember_role,
    resolve_role,
    stored_user_display_name,
    stored_user_email,
    stored_user_id,
)
from . import components, theme
from .close_policy import CloseConfirmDialog, ClosePolicy, get_confirm_close_setting
from .components import Avatar, BrandMark, Button, InlineBanner, LiveDot
from .icons import get_icon, get_pixmap
from .live_sync import LiveSyncWorker
from .photo_viewer import running_photo_fetchers
from .pages.overview import OverviewPage
from .pages.pending import PendingPage
from .pages.residents import ResidentsPage
from .pages.rooms import RoomsPage
from .pages.maintenance import MaintenancePage
from .pages.room_changes import RoomChangesPage
from .pages.official_list import OfficialListPage
from .pages.staff_accounts import StaffAccountsPage
from .pages.settings import SettingsPage
from .tasks import TaskRunner, active_task_count, human_error
from .theme import C, DESKTOP_STYLESHEET, S

_log = logging.getLogger("resivo.ui.main_window")

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
_ROLE_ERROR_TEXT = "Could not verify your role. Check your connection or configuration."
_UNVERIFIED_LABEL = "Role not verified"
_ROLE_TASK_KEY = "main-role-check"
# Cooperative shutdown: poll while a worker finishes; never terminate a thread
# that may be holding CLIENT_LOCK.
_SHUTDOWN_POLL_MS = 100


def _normalize_role(role) -> str | None:
    """Case/whitespace-insensitive role comparison value."""
    if role is None:
        return None
    normalized = str(role).strip().lower()
    return normalized or None


def _role_label(role) -> str:
    """Human label for the sidebar pill / diagnostics."""
    normalized = _normalize_role(role)
    if not normalized:
        return _UNVERIFIED_LABEL
    return _ROLE_LABELS.get(normalized, normalized.title())


def _session_email(client) -> str:
    """Signed-in email from the stored session only (never a network call)."""
    return stored_user_email(client)


def _session_user_id(client) -> str | None:
    """Signed-in user id from the stored session only (never a network call)."""
    return stored_user_id(client)


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
        f"QPushButton#{obj_name}:checked {{ background-color: {C('navy-800')}; border-left: 2px solid {C('gold-500')}; }}"
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
    return stored_user_display_name(client, "Housing staff")


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

    def clear_selection(self) -> None:
        self._current = -1
        checked = self._group.checkedButton()
        if checked is not None:
            self._group.setExclusive(False)
            checked.setChecked(False)
            self._group.setExclusive(True)

    def _activate(self, index: int) -> None:
        if not 0 <= index < len(self._rows) or index == self._current:
            return
        self._current = index
        self._rows[index].setChecked(True)
        self.currentRowChanged.emit(index)


class MainWindow(QMainWindow):
    def __init__(self, client, role=None):
        super().__init__()
        self.client = client
        self._role_retry_running = False
        if role is None:
            try:
                self.role = _normalize_role(current_role(client))
            except Exception:  # noqa: BLE001 - never block the shell on a lookup
                _log.exception("Role lookup failed while opening the main window")
                self.role = None
        else:
            self.role = _normalize_role(role)

        if self.role in ("staff", "admin"):
            # Remembered so SettingsPage and later pages reuse the verified
            # role instead of issuing another profile query.
            try:
                remember_role(client, self.role)
            except Exception:  # noqa: BLE001 - cache failure is non-fatal
                _log.exception("Could not cache the verified role")
        elif not self.role:
            _log.warning(
                "Main window opened without a verified role; showing the retry banner"
            )

        self.tasks = TaskRunner(self)
        self._pending_shutdown_action: str | None = None
        self._signing_out = False
        self._sign_out_show_login = True
        self._sign_out_error: str | None = None
        self._is_session_ending = False
        self._shutdown_confirmed = False

        qapp = QGuiApplication.instance()
        if qapp is not None:
            qapp.commitDataRequest.connect(self._on_commit_data_request)
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
        if hasattr(self.official_list_page, "pending_page"):
            self.official_list_page.pending_page = self.pending_page
        if hasattr(self.official_list_page, "roster_changed"):
            self.official_list_page.roster_changed.connect(self._on_roster_changed)

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
        self.pages["Settings"] = self.settings_page
        self.stack.addWidget(self.settings_page)

        self.nav.currentRowChanged.connect(self._on_nav_row_changed)
        self.nav.setCurrentRow(0)

        # Reflect the effective role in the footer and, when it could not be
        # verified, show the retry banner instead of silently using staff.
        self._apply_role_state()

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
        self.user_avatar.setToolTip(f"{display_name} • {_role_label(self.role)}")

        self.user_texts = QWidget()
        name_column = QVBoxLayout(self.user_texts)
        name_column.setContentsMargins(0, 0, 0, 0)
        name_column.setSpacing(2)
        self.user_name = QLabel(display_name)
        theme.apply_role(self.user_name, "small")
        self.user_name.setStyleSheet(f"color: {C('text-on-dark')};")
        self.role_pill = QLabel(_role_label(self.role))
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

        # Settings (ghost, same footer treatment as the buttons above).
        self.settings_btn = Button.ghost("Settings")
        self.settings_btn.setObjectName("settingsButton")
        self.settings_btn.setCheckable(True)
        self.settings_btn.setIcon(get_icon("settings", size=18, color=C("text-on-dark")))
        self.settings_btn.setIconSize(QSize(18, 18))
        self.settings_btn.setStyleSheet(
            _ghost_on_navy_qss("settingsButton", centered=False)
        )
        self.settings_btn.setFixedHeight(38)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.setAccessibleName("Settings")
        self.settings_btn.clicked.connect(self.on_settings_clicked)
        self.sidebar_footer_layout.addWidget(self.settings_btn)

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

            self.settings_btn.setText("")
            self.settings_btn.setToolTip("Settings")
            self.settings_btn.setStyleSheet(
                _ghost_on_navy_qss("settingsButton", centered=True)
            )

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

            self.settings_btn.setText("Settings")
            self.settings_btn.setToolTip("Settings")
            self.settings_btn.setStyleSheet(
                _ghost_on_navy_qss("settingsButton", centered=False)
            )

            self.live_row.setAlignment(self.live_dot, Qt.AlignmentFlag.AlignVCenter)
            self.live_label.show()


    def _build_content(self) -> QWidget:
        content = QWidget()
        content.setProperty("background", "canvas")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(S("space-8"), S("space-8"), S("space-8"), S("space-8"))
        layout.setSpacing(S("space-4"))

        # Role gate: an unverified lookup is an error state, not a staff session.
        self.role_banner = InlineBanner(
            kind="error",
            title="Role not verified",
            message=_ROLE_ERROR_TEXT,
        )
        self.role_retry_btn = Button.secondary("Retry")
        self.role_retry_btn.setObjectName("retryRoleButton")
        self.role_retry_btn.setToolTip("Check the signed-in account's role again")
        self.role_retry_btn.clicked.connect(self._retry_role_check)
        self.role_banner.add_action(self.role_retry_btn)
        self.role_banner.setVisible(not bool(self.role))
        layout.addWidget(self.role_banner)

        self.stack = QStackedWidget()
        self.stack.currentChanged.connect(self._animate_stack_page)
        layout.addWidget(self.stack, 1)
        return content

    def _apply_role_state(self) -> None:
        """Apply the effective role to the footer, banner and role-gated pages."""
        label = _role_label(self.role)
        self.role_pill.setText(label)
        self.user_avatar.setToolTip(f"{self.user_name.text()} • {label}")

        if self.role:
            self.role_banner.setVisible(False)
        else:
            self.role_banner.set_message(_ROLE_ERROR_TEXT)
            self.role_banner.setVisible(True)

        if self.role == "admin" and "Staff accounts" not in self.pages:
            # Late promotion happens inside the retry success slot: defer the
            # page's synchronous identity/list round-trip and let its existing
            # async reload run on the worker pool.
            self.staff_accounts_page = StaffAccountsPage(
                self.client,
                defer_initial_load=True,
                current_uid=_session_user_id(self.client),
            )
            self._add_nav_item("Staff accounts", "staff_accounts", self.staff_accounts_page)

        # Pages exposing set_role() apply late verification without rebuilding
        # themselves or performing another synchronous lookup.
        if hasattr(self, "official_list_page") and hasattr(self.official_list_page, "set_role"):
            self.official_list_page.set_role(self.role)
        if hasattr(self, "settings_page") and hasattr(self.settings_page, "set_role"):
            self.settings_page.set_role(self.role)

    def _on_roster_changed(self) -> None:
        """Refresh pending student records and badges when official admissions data is updated."""
        if hasattr(self, "pending_page") and hasattr(self.pending_page, "reload"):
            self.pending_page.reload()

    def _retry_role_check(self) -> None:
        """Re-check the role off the GUI thread, then apply the gating."""
        if self._role_retry_running:
            return
        self._role_retry_running = True
        self.role_retry_btn.setEnabled(False)
        self.role_retry_btn.setText("Checking...")
        self.role_banner.set_message(_ROLE_ERROR_TEXT)
        self.role_banner.setVisible(True)

        started = self.tasks.run(
            _ROLE_TASK_KEY,
            lambda: resolve_role(self.client),
            on_success=self._on_role_retry_success,
            on_failed=self._on_role_retry_failed,
            on_finished=self._on_role_retry_finished,
        )
        if not started:
            self._on_role_retry_finished()

    def _on_role_retry_success(self, role) -> None:
        normalized = _normalize_role(role)
        if normalized not in ("staff", "admin"):
            self._on_role_retry_failed(
                "This account is not allowed to use the staff console."
            )
            return
        self.role = normalized
        try:
            remember_role(self.client, normalized)
        except Exception:  # noqa: BLE001 - cache failure is non-fatal
            _log.exception("Could not cache the re-verified role")
        _log.info("Role re-verified as %s", normalized)
        self._apply_role_state()

    def _on_role_retry_failed(self, message: str) -> None:
        _log.warning("Role retry failed: %s", message)
        self.role_banner.set_message(f"{_ROLE_ERROR_TEXT} ({message})")
        self.role_banner.setVisible(True)

    def _on_role_retry_finished(self) -> None:
        self._role_retry_running = False
        self.role_retry_btn.setText("Retry")
        self.role_retry_btn.setEnabled(True)

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
        # Every status is delivered to the page; the Transfers badge/status
        # line stays pending-only.
        request_rows = data.get("room_change_requests", data.get("pending_requests", []))
        timestamp = data.get("timestamp", "")

        p_count = len(pending_students)
        m_count = open_reports_count
        r_count = sum(
            1 for request in request_rows
            if str(request.get("status") or "pending") == "pending"
        )
        # Missing occupancy means "unknown", not zero; the Overview card keeps
        # its previous value until a payload carries a real count.
        active_count = data.get("active_residents_count")

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
        self.room_changes_page.apply_live_data(request_rows)

    # ------------------------------------------------------------------- flow
    def _long_lived_workers(self) -> list:
        """Sync/health/photo QThreads that must finish before the window dies."""
        workers = []
        sync = getattr(self, "sync_worker", None)
        if sync is not None:
            workers.append(sync)
        settings = getattr(self, "settings_page", None)
        health = getattr(settings, "health_worker", None) if settings is not None else None
        if health is not None:
            workers.append(health)
        # Photo previews may outlive the row/dialog that started them.
        workers.extend(running_photo_fetchers())
        return workers

    def _workers_running(self) -> bool:
        """True while a window thread or any action-pool task is still alive."""
        if any(worker.isRunning() for worker in self._long_lived_workers()):
            return True
        tasks = getattr(self, "tasks", None)
        if tasks is not None and tasks.is_busy("sign-out"):
            return True
        # Cover tasks reserved but not yet counted by QThreadPool, including
        # page-owned TaskRunner instances on other pools.
        if active_task_count() > 0:
            return True
        return QThreadPool.globalInstance().activeThreadCount() > 0

    def _shutdown_workers(self, wait_ms: int = 3000) -> bool:
        """Request a cooperative stop and report whether everything finished.

        ``wait_ms`` bounds how long the GUI thread may block; ``0`` only checks.
        ``QThread.terminate()`` is never used: a terminated worker can die while
        holding ``CLIENT_LOCK`` and deadlock the next session.  Callers that get
        ``False`` must defer sign-out/close and retry once the workers finish.
        """
        workers = self._long_lived_workers()
        for worker in workers:
            worker.stop()

        if wait_ms <= 0:
            return not self._workers_running()

        deadline = time.monotonic() + (wait_ms / 1000.0)
        for worker in workers:
            if not worker.isRunning():
                continue
            remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
            if remaining_ms <= 0 or not worker.wait(remaining_ms):
                return False

        remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
        if remaining_ms > 0:
            if not QThreadPool.globalInstance().waitForDone(remaining_ms):
                return False
        elif QThreadPool.globalInstance().activeThreadCount() > 0:
            return False
        return not self._workers_running()

    def _begin_shutdown(self, action: str) -> None:
        """Ask workers to stop, then complete ``action`` without blocking."""
        self._pending_shutdown_action = action
        self._shutdown_start_time = time.monotonic()
        self._shutdown_workers(0)
        if not self._workers_running():
            self._pending_shutdown_action = None
            self._complete_shutdown(action)
            return
        self.status_bar.showMessage("Finishing background work…")
        timer = getattr(self, "_shutdown_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setInterval(_SHUTDOWN_POLL_MS)
            timer.timeout.connect(self._poll_shutdown)
            self._shutdown_timer = timer
        timer.start()

    def _poll_shutdown(self) -> None:
        if self._workers_running():
            elapsed = time.monotonic() - getattr(self, "_shutdown_start_time", time.monotonic())
            if elapsed > 10.0:
                _log.warning("Workers did not finish after %.1fs; proceeding with shutdown", elapsed)
            else:
                return
        timer = getattr(self, "_shutdown_timer", None)
        if timer is not None:
            timer.stop()
        action = getattr(self, "_pending_shutdown_action", None)
        self._pending_shutdown_action = None
        if action:
            self._complete_shutdown(action)

    def _complete_shutdown(self, action: str) -> None:
        if action == "sign_out":
            self._finish_sign_out(show_login=True)
        elif action == "sign_out_close":
            # The user closed the window while sign-out was waiting: still clear
            # the session, but do not pop a login window they did not ask for.
            self._finish_sign_out(show_login=False)
        elif action == "close":
            self._stop_live_timer()
            self.close()

    def _stop_live_timer(self) -> None:
        timer = getattr(self, "_live_timer", None)
        if timer is not None:
            timer.stop()

    def _on_nav_row_changed(self, index: int) -> None:
        if hasattr(self, "settings_btn") and self.settings_btn.isChecked():
            self.settings_btn.setChecked(False)
        self.stack.setCurrentIndex(index)

    def on_settings_clicked(self) -> None:
        self.nav.clear_selection()
        if hasattr(self, "settings_btn"):
            self.settings_btn.setChecked(True)
        self.stack.setCurrentWidget(self.settings_page)

    @staticmethod
    def _sign_out_session(client):
        """Network/credential work only; never call this on the GUI thread."""
        auth = getattr(client, "auth", None)
        sign_out = getattr(auth, "sign_out", None)
        if not callable(sign_out):
            raise RuntimeError("The authentication client is not available.")
        sign_out()

    def _finish_sign_out(self, show_login: bool = True) -> None:
        """Sign out off the GUI thread, then land on the login window.

        If a close request arrives while the request is in flight,
        ``closeEvent`` flips ``_sign_out_show_login`` so the session is still
        cleared without opening a window the operator did not ask for.
        """
        self._stop_live_timer()
        self._sign_out_show_login = show_login
        self._sign_out_error = None
        if self.tasks.is_busy("sign-out"):
            self._signing_out = True
            return
        started = self.tasks.run(
            "sign-out",
            lambda: self._sign_out_session(self.client),
            on_success=self._on_sign_out_succeeded,
            on_failed=self._on_sign_out_failed,
            on_finished=self._on_sign_out_finished,
        )
        if not started:
            self._signing_out = False
            self.sign_out_btn.setEnabled(True)
            self.status_bar.showMessage("Could not start sign-out. Please try again.")
            return
        self._signing_out = True
        self.status_bar.showMessage("Signing out…")

    def _forget_cached_role(self) -> None:
        try:
            forget_role(self.client)
        except Exception as exc:  # noqa: BLE001 - local cache only
            _log.error(
                "Could not clear the cached role while signing out: %s",
                human_error(exc),
            )

    def _on_sign_out_succeeded(self, _result) -> None:
        self._forget_cached_role()

    def _on_sign_out_failed(self, message: str) -> None:
        # The window is already leaving; clear the local session explicitly so
        # a failed server call cannot leave refresh credentials behind, then
        # surface the failure on the login window.
        self._sign_out_error = message
        try:
            clear_local_session(self.client)
        except Exception as exc:  # noqa: BLE001 - reported on the login window
            self._sign_out_error = (
                f"{message} The local session could not be cleared: "
                f"{human_error(exc)}"
            )
            _log.error("Local session cleanup failed: %s", human_error(exc))
        _log.warning("Sign-out request failed: %s", message)
        self._forget_cached_role()

    def _on_sign_out_finished(self) -> None:
        self._stop_live_timer()
        self._signing_out = False
        self._shutdown_confirmed = True
        if self._sign_out_show_login:
            from .login_window import LoginWindow

            self.login_window = LoginWindow()
            if self._sign_out_error:
                self.login_window.show_error(
                    "Sign-out could not reach the server. The local session was "
                    "cleared as a precaution; check your connection before "
                    f"signing in again. ({self._sign_out_error})"
                )
            self.login_window.show()
        self.close()

    def on_sign_out_clicked(self):
        if self._signing_out or self.tasks.is_busy("sign-out"):
            return
        if getattr(self, "_pending_shutdown_action", None) in (
            "sign_out",
            "sign_out_close",
        ):
            return
        self._shutdown_confirmed = True
        self.sign_out_btn.setEnabled(False)
        self._begin_shutdown("sign_out")

    def _on_commit_data_request(self, session_manager=None) -> None:
        self._is_session_ending = True

    def request_quit(self) -> None:
        """Trigger application close, obeying confirmation policy."""
        self.close()

    def closeEvent(self, event):
        # A sign-out that is still waiting for workers must survive the close:
        # switch it to the no-login variant and keep the shutdown poll running.
        action = getattr(self, "_pending_shutdown_action", None)
        if action in ("sign_out", "sign_out_close"):
            self._sign_out_show_login = False
            self._begin_shutdown("sign_out_close")
            event.ignore()
            return

        # A sign-out already running owns the shutdown: remember that the
        # operator does not want the login window, then let the task close us.
        if self._signing_out or self.tasks.is_busy("sign-out"):
            self._sign_out_show_login = False
            event.ignore()
            return

        if not getattr(self, "_shutdown_confirmed", False):
            # A window that is not visible and not minimized to tray does not prompt.
            if not self.isVisible() and not getattr(self, "_in_tray", False):
                self._shutdown_confirmed = True
            else:
                is_busy = self._workers_running()
                is_session_ending = getattr(self, "_is_session_ending", False)
                confirm_setting = get_confirm_close_setting()

                if ClosePolicy.should_confirm(confirm_setting, is_busy, is_session_ending):
                    dlg = CloseConfirmDialog(self, is_busy=is_busy)
                    if dlg.exec() != QDialog.DialogCode.Accepted:
                        event.ignore()
                        return

                self._shutdown_confirmed = True

        self._shutdown_workers(0)
        if self._workers_running():
            # Never destroy a running QThread (or leave it holding CLIENT_LOCK):
            # keep the window alive and finish the close when they are done.
            event.ignore()
            self._begin_shutdown("close")
            return
        self._stop_live_timer()
        timer = getattr(self, "_shutdown_timer", None)
        if timer is not None:
            timer.stop()
        self._pending_shutdown_action = None
        super().closeEvent(event)
