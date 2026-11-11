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

import importlib
import inspect
import logging
from pathlib import Path
import sys
import time

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QSettings,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtGui import QFont, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

try:
    from i18n import current_language, t, tn
except ImportError:
    from desktop.i18n import current_language, t, tn

from desktop.auth.session_store import session_manager
from desktop.updater import prefs as update_prefs
from desktop.updater.installer import launch_installer
from desktop.updater.service import UpdateService
from desktop.updater.state import UpdateState

from ..client import (
    DEFAULT_RESIDENCE_NAME,
    invalidate_official_lookup_cache,
    clear_local_session,
    current_role,
    fetch_residence_public,
    forget_role,
    get_cached_residence_settings,
    remember_role,
    resolve_role,
    stored_user_display_name,
    stored_user_email,
    stored_user_id,
)
from ..startup_debug import mark, timeline
from . import components, theme
from .close_policy import (
    CloseConfirmDialog,
    ClosePolicy,
    get_confirm_close_setting,
    get_minimize_to_tray_setting,
)
from .components import Avatar, BrandMark, Button, InlineBanner, LiveDot
from .notifications import NotificationManager
from .residence_dialogs import ResidenceSetupDialog
from .icons import get_icon, get_pixmap
from .live_sync import LiveSyncWorker
from .photo_viewer import running_photo_fetchers
from .pages.overview import OverviewPage
from .tasks import TaskRunner, active_task_count, human_error
from .theme import C, DESKTOP_STYLESHEET, S, apply_app_stylesheet

_LAZY_PAGE_MODULES: dict[str, str] = {
    "PendingPage": ".pages.pending",
    "ResidentsPage": ".pages.residents",
    "RoomsPage": ".pages.rooms",
    "MaintenancePage": ".pages.maintenance",
    "RoomChangesPage": ".pages.room_changes",
    "OfficialListPage": ".pages.official_list",
    "StaffAccountsPage": ".pages.staff_accounts",
    "SettingsPage": ".pages.settings",
}


def __getattr__(name: str):
    """Lazily import secondary page classes on first access (PEP 562)."""
    rel_mod = _LAZY_PAGE_MODULES.get(name)
    if rel_mod is not None:
        mod = importlib.import_module(rel_mod, package=__package__)
        cls = getattr(mod, name)
        globals()[name] = cls
        return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _page_factory(name: str):
    """Resolve a page constructor dynamically (honors test monkeypatches)."""
    return getattr(sys.modules[__name__], name)


def _instantiate_page(factory, client, **kwargs):
    """Call *factory(client, ...)* passing only kwargs accepted by its signature."""
    try:
        sig = inspect.signature(factory)
    except (TypeError, ValueError):
        return factory(client)
    accepts_var_kw = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    filtered = {}
    for key, val in kwargs.items():
        if val is None and key not in ("current_uid",):
            continue
        if accepts_var_kw or key in sig.parameters:
            filtered[key] = val
    return factory(client, **filtered)


class _LazyPagesDict(dict):
    """Page registry dict preserving O(1) membership checks and lazy lookup."""

    def __init__(self, owner: "MainWindow"):
        super().__init__()
        self._owner = owner
        self._slot_by_title: dict[str, str] = {}

    def bind_slot(self, title: str, slot_key: str) -> None:
        self._slot_by_title[title] = slot_key

    def __getitem__(self, key):
        slot_key = self._slot_by_title.get(key)
        if slot_key is not None and not self._owner._is_page_built(slot_key):
            return self._owner._ensure_page(slot_key)
        return dict.__getitem__(self, key)

    def get(self, key, default=None):
        if key in self:
            return self[key]
        return default

    def values(self):
        return [self[k] for k in self.keys()]

    def items(self):
        return [(k, self[k]) for k in self.keys()]

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
        return t("roles.unverified")
    if normalized == "admin":
        return t("roles.admin")
    if normalized == "staff":
        return t("roles.staff")
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
        if not any(e.name == "main_window_init_start" for e in timeline().entries):
            mark("main_window_init_start")
        else:
            mark("main_window_ctor_start")
        self._startup_first_data_marked = False
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
        self.update_service = UpdateService(self.tasks, self)
        self.update_service.available_changed.connect(self._on_update_available)
        self._update_available = False
        self._pending_update_path = None
        self._pending_shutdown_action: str | None = None
        self._signing_out = False
        self._sign_out_show_login = True
        self._sign_out_error: str | None = None
        self._is_session_ending = False
        self._shutdown_confirmed = False
        self._closing = False
        self._residence_prompt_shown = False

        qapp = QGuiApplication.instance()
        if qapp is not None:
            qapp.commitDataRequest.connect(self._on_commit_data_request)
        self._sidebar_minimized = False
        self._in_tray = False
        self._prev_window_state = self.windowState()
        self._minimize_shortcut = QShortcut(QKeySequence("Ctrl+M"), self)
        self._minimize_shortcut.activated.connect(self._on_minimize_shortcut)
        self.setWindowTitle(t("app.console_title"))
        self.setMinimumSize(980, 640)
        init_w, init_h = 1180, 760
        try:
            screen = qapp.primaryScreen() if qapp is not None else None
            if screen is not None:
                avail = screen.availableGeometry()
                if avail.width() > 0 and avail.height() > 0:
                    init_w = max(980, min(init_w, avail.width()))
                    init_h = max(640, min(init_h, avail.height()))
        except Exception:  # pragma: no cover - headless fallback
            pass
        self.resize(init_w, init_h)
        apply_app_stylesheet(self)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(self._build_content(), 1)

        # Pages instantiation — OverviewPage + shell build immediately; all
        # secondary pages are deferred until first visit/access.
        self._in_init = True
        self._current_uid = _session_user_id(client)
        self._built_pages: dict[str, QWidget] = {}
        self._placeholders: dict[str, QWidget] = {}
        self._nav_slot_keys: list[str] = []
        self._cached_live_data: dict | None = None
        self._sync_error_seen: bool = False
        self.pages: dict[str, QWidget] = _LazyPagesDict(self)

        self.overview_page = _instantiate_page(_page_factory("OverviewPage"), client)
        self._built_pages["overview"] = self.overview_page
        mark("page:OverviewPage")

        self._add_nav_item(t("nav.overview"), "overview", self.overview_page, canonical_name="Overview", slot_key="overview")
        self._add_lazy_nav_item(t("nav.pending"), "pending", "pending", canonical_name="Pending accounts")
        self._add_lazy_nav_item(t("nav.residents"), "residents", "residents", canonical_name="Residents")
        self._add_lazy_nav_item(t("nav.rooms"), "rooms", "rooms", canonical_name="Rooms")
        self._add_lazy_nav_item(t("nav.maintenance"), "maintenance", "maintenance", canonical_name="Maintenance")
        self._add_lazy_nav_item(t("nav.room_changes"), "room_changes", "room_changes", canonical_name="Room changes")
        self._add_lazy_nav_item(t("nav.official_list"), "official_list", "official_list", canonical_name="Official list")

        if self.role == "admin":
            self._add_lazy_nav_item(t("nav.staff_accounts"), "staff_accounts", "staff_accounts", canonical_name="Staff accounts")

        settings_placeholder = QWidget(self.stack)
        self._placeholders["settings"] = settings_placeholder
        self.pages[t("nav.settings")] = settings_placeholder
        self.pages["Settings"] = settings_placeholder
        self.pages.bind_slot(t("nav.settings"), "settings")
        self.pages.bind_slot("Settings", "settings")
        self.stack.addWidget(settings_placeholder)

        self.nav.currentRowChanged.connect(self._on_nav_row_changed)
        self.nav.setCurrentRow(0)

        # Reflect the effective role in the footer and, when it could not be
        # verified, show the retry banner instead of silently using staff.
        self._apply_role_state()

        # Status bar — the live-sync line only (events go to toasts).
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(t("live_sync.active"))

        # Live-sync indicator state (driven by the existing tick/alert signals).
        self._started_at = time.monotonic()
        self._last_tick_at: float | None = None
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(2000)
        self._live_timer.timeout.connect(self._refresh_live_state)
        self._live_timer.start()
        self._set_live_state("connecting")
        self._in_init = False

        # System tray icon and desktop notifications (tray created right after
        # first paint so MainWindow appears faster).
        self.tray_icon = None
        self.notification_manager = NotificationManager(self, tray_icon=None)
        QTimer.singleShot(0, self._setup_tray_icon_deferred)

        # Start live background sync worker (unchanged behaviour).
        self.sync_worker = LiveSyncWorker(client, interval_ms=2000)
        self.sync_worker.sync_tick.connect(self.on_live_sync_tick)
        self.sync_worker.alert_event.connect(self.on_live_alert)
        self.sync_worker.sync_error.connect(self.on_live_sync_error)
        self.sync_worker.residence_loaded.connect(self._on_residence_checked)
        self.sync_worker.start()
        mark("workers_started")
        mark("main_window_init_end")

        # Background update check: at most once every 24 h (persisted).
        QTimer.singleShot(2500, self._auto_check_updates)

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
        self.brand_caption = QLabel(DEFAULT_RESIDENCE_NAME)
        theme.apply_role(self.brand_caption, "small")
        self.brand_caption.setStyleSheet(f"color: {C('text-on-dark-muted')};")
        texts_layout.addWidget(wordmark)
        texts_layout.addWidget(self.brand_caption)
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
        self.sign_out_btn = Button.ghost(t("nav.sign_out"))
        self.sign_out_btn.setObjectName("signOutButton")
        self.sign_out_btn.setIcon(get_icon("log-out", size=18, color=C("text-on-dark")))
        self.sign_out_btn.setIconSize(QSize(18, 18))
        self.sign_out_btn.setStyleSheet(_ghost_on_navy_qss("signOutButton", centered=False))
        self.sign_out_btn.setFixedHeight(38)
        self.sign_out_btn.setToolTip(t("nav.sign_out"))
        self.sign_out_btn.clicked.connect(self.on_sign_out_clicked)
        self.sidebar_footer_layout.addWidget(self.sign_out_btn)

        # Minimize / Expand menu button directly below Sign out
        self.toggle_menu_btn = Button.ghost(t("nav.collapse_menu"))
        self.toggle_menu_btn.setObjectName("toggleMenuButton")
        self.toggle_menu_btn.setIcon(get_icon("chevron-left", size=18, color=C("text-on-dark")))
        self.toggle_menu_btn.setIconSize(QSize(18, 18))
        self.toggle_menu_btn.setStyleSheet(_ghost_on_navy_qss("toggleMenuButton", centered=False))
        self.toggle_menu_btn.setFixedHeight(38)
        self.toggle_menu_btn.setToolTip(t("nav.collapse_menu"))
        self.toggle_menu_btn.setAccessibleName(t("nav.collapse_menu"))
        self.toggle_menu_btn.clicked.connect(self.toggle_sidebar)
        self.sidebar_footer_layout.addWidget(self.toggle_menu_btn)

        # Settings (ghost, same footer treatment as the buttons above).
        self.settings_btn = Button.ghost(t("nav.settings"))
        self.settings_btn.setObjectName("settingsButton")
        self.settings_btn.setCheckable(True)
        self.settings_btn.setIcon(get_icon("settings", size=18, color=C("text-on-dark")))
        self.settings_btn.setIconSize(QSize(18, 18))
        self.settings_btn.setStyleSheet(
            _ghost_on_navy_qss("settingsButton", centered=False)
        )
        self.settings_btn.setFixedHeight(38)
        self.settings_btn.setToolTip(t("nav.settings"))
        self.settings_btn.setAccessibleName(t("nav.settings"))
        self.settings_btn.clicked.connect(self.on_settings_clicked)
        self.sidebar_footer_layout.addWidget(self.settings_btn)

        # Updates badge (hidden until a newer release is found).
        self.settings_update_badge = QLabel(t("updates.available_badge"))
        self.settings_update_badge.setObjectName("settingsUpdateBadge")
        self.settings_update_badge.setStyleSheet(
            f"background-color: {C('teal-600')}; color: {C('text-on-dark')};"
            f" border-radius: {C('radius-input')}; padding: 1px {C('pill-pad-x')};"
            f" font-size: {C('fs-overline')}; font-weight: {C('fw-semibold')};"
        )
        self.settings_update_badge.setToolTip(t("updates.available_badge"))
        self.settings_update_badge.setVisible(False)
        self.sidebar_footer_layout.addWidget(
            self.settings_update_badge, 0, Qt.AlignmentFlag.AlignLeft
        )

        # Live-sync indicator: dot + text label (never colour alone).
        self.live_row_widget = QWidget()
        self.live_row = QHBoxLayout(self.live_row_widget)
        self.live_row.setContentsMargins(0, 0, 0, 0)
        self.live_row.setSpacing(S("space-2"))
        self.live_dot = LiveDot()
        self.live_label = QLabel(t("nav.live_sync"))
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
            self.sign_out_btn.setToolTip(t("nav.sign_out"))
            self.sign_out_btn.setStyleSheet(_ghost_on_navy_qss("signOutButton", centered=True))

            self.toggle_menu_btn.setText("")
            self.toggle_menu_btn.setToolTip(t("nav.expand_menu"))
            self.toggle_menu_btn.setAccessibleName(t("nav.expand_menu"))
            self.toggle_menu_btn.setIcon(get_icon("chevron-right", size=18, color=C("text-on-dark")))
            self.toggle_menu_btn.setStyleSheet(_ghost_on_navy_qss("toggleMenuButton", centered=True))

            self.settings_btn.setText("")
            self.settings_btn.setToolTip(t("nav.settings"))
            self.settings_btn.setStyleSheet(
                _ghost_on_navy_qss("settingsButton", centered=True)
            )
            self.settings_update_badge.hide()

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

            self.sign_out_btn.setText(t("nav.sign_out"))
            self.sign_out_btn.setToolTip(t("nav.sign_out"))
            self.sign_out_btn.setStyleSheet(_ghost_on_navy_qss("signOutButton", centered=False))

            self.toggle_menu_btn.setText(t("nav.collapse_menu"))
            self.toggle_menu_btn.setToolTip(t("nav.collapse_menu"))
            self.toggle_menu_btn.setAccessibleName(t("nav.collapse_menu"))
            self.toggle_menu_btn.setIcon(get_icon("chevron-left", size=18, color=C("text-on-dark")))
            self.toggle_menu_btn.setStyleSheet(_ghost_on_navy_qss("toggleMenuButton", centered=False))

            self.settings_btn.setText(t("nav.settings"))
            self.settings_btn.setToolTip(t("nav.settings"))
            self.settings_btn.setStyleSheet(
                _ghost_on_navy_qss("settingsButton", centered=False)
            )
            self.settings_update_badge.setVisible(self._update_available)

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
            title=t("roles.unverified"),
            message=t("login.role_error"),
        )
        self.role_retry_btn = Button.secondary(t("common.retry"))
        self.role_retry_btn.setObjectName("retryRoleButton")
        self.role_retry_btn.setToolTip(t("roles.retry_tooltip"))
        self.role_retry_btn.clicked.connect(self._retry_role_check)
        self.role_banner.add_action(self.role_retry_btn)
        self.role_banner.setVisible(not bool(self.role))
        layout.addWidget(self.role_banner)

        self.residence_unset_banner = InlineBanner(
            kind="warning",
            title=t("residence.unset_banner_title"),
            message=t("residence.unset_banner_staff"),
        )
        self.residence_settings_btn = Button.secondary(t("residence.open_settings_btn"))
        self.residence_settings_btn.setObjectName("openResidenceSettingsButton")
        self.residence_settings_btn.clicked.connect(self.on_settings_clicked)
        self.residence_unset_banner.add_action(self.residence_settings_btn)
        self.residence_settings_btn.setVisible(self.role == "admin")
        self.residence_unset_banner.setVisible(False)
        layout.addWidget(self.residence_unset_banner)

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
            self.role_banner.set_message(t("login.role_error"))
            self.role_banner.setVisible(True)

        if self.role == "admin" and "Staff accounts" not in self.pages:
            # Late promotion happens inside the retry success slot: defer the
            # page's synchronous identity/list round-trip and let its existing
            # async reload run on the worker pool.
            staff_cls = _page_factory("StaffAccountsPage")
            staff_page = _instantiate_page(
                staff_cls,
                self.client,
                defer_initial_load=True,
                current_uid=getattr(self, "_current_uid", None) or _session_user_id(self.client),
            )
            self._built_pages["staff_accounts"] = staff_page
            self._add_nav_item(
                t("nav.staff_accounts"),
                "staff_accounts",
                staff_page,
                canonical_name="Staff accounts",
                slot_key="staff_accounts",
            )

        # Forward role updates ONLY to already-built pages; lazy pages receive
        # the effective role when constructed on first visit.
        if self._is_page_built("official_list"):
            ol_page = self._built_pages["official_list"]
            if hasattr(ol_page, "set_role"):
                ol_page.set_role(self.role)
        if self._is_page_built("settings"):
            st_page = self._built_pages["settings"]
            if hasattr(st_page, "set_role"):
                st_page.set_role(self.role)
        if hasattr(self, "residence_settings_btn"):
            self.residence_settings_btn.setVisible(self.role == "admin")

    def _check_residence_setup(self) -> None:
        """Check configured residence_gender off the GUI thread right after startup."""
        if getattr(self, "_closing", False) or not self.role:
            return
        if self.tasks.is_busy("residence-setup-check"):
            return
        self.tasks.run(
            "residence-setup-check",
            lambda: fetch_residence_public(self.client, force=True),
            on_success=self._on_residence_checked,
            on_failed=lambda _msg: None,
        )

    def _apply_residence_banner(self, res: dict | None) -> None:
        if not isinstance(res, dict) or not res.get("loaded"):
            return
        res_name = str(res.get("residence_name") or DEFAULT_RESIDENCE_NAME).strip() or DEFAULT_RESIDENCE_NAME
        if hasattr(self, "brand_caption"):
            self.brand_caption.setText(res_name)
        if hasattr(self, "overview_page") and hasattr(self.overview_page, "set_residence_name"):
            self.overview_page.set_residence_name(res_name)

        res_gender = res.get("residence_gender")
        self._cached_residence_gender = res_gender
        for slot_key in ("pending", "residents", "rooms"):
            if self._is_page_built(slot_key):
                page = self._built_pages[slot_key]
                if hasattr(page, "set_residence_gender"):
                    page.set_residence_gender(res_gender)

        if res_gender in ("male", "female"):
            self.residence_unset_banner.setVisible(False)
            return

        if self.role == "admin":
            self.residence_unset_banner.set_message(t("residence.unset_banner_admin"))
            self.residence_settings_btn.setVisible(True)
        else:
            self.residence_unset_banner.set_message(t("residence.unset_banner_staff"))
            self.residence_settings_btn.setVisible(False)
        self.residence_unset_banner.setVisible(True)

    def _on_residence_checked(self, res: dict) -> None:
        if getattr(self, "_closing", False):
            return
        self._apply_residence_banner(res)
        if not isinstance(res, dict) or not res.get("loaded"):
            return
        if res.get("residence_gender") in ("male", "female"):
            return
        if self.role == "admin" and not self._residence_prompt_shown:
            self._residence_prompt_shown = True
            dlg = ResidenceSetupDialog(self, client=self.client)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.saved_gender:
                self._on_residence_settings_changed()

    def _on_residence_settings_changed(self) -> None:
        cached = get_cached_residence_settings(self.client)
        if cached:
            self._apply_residence_banner(cached)
        else:
            self._check_residence_setup()
        if self._is_page_built("pending"):
            p_page = self._built_pages["pending"]
            if hasattr(p_page, "show_detail"):
                p_page.show_detail()
        if self._is_page_built("settings"):
            s_page = self._built_pages["settings"]
            if hasattr(s_page, "reload"):
                s_page.reload()

    def _on_roster_changed(self) -> None:
        """Refresh pending student records and badges when official admissions data is updated."""
        invalidate_official_lookup_cache(self.client)
        if self._is_page_built("pending"):
            p_page = self._built_pages["pending"]
            if hasattr(p_page, "reload"):
                p_page.reload()

    def _retry_role_check(self) -> None:
        """Re-check the role off the GUI thread, then apply the gating."""
        if self._role_retry_running:
            return
        self._role_retry_running = True
        self.role_retry_btn.setEnabled(False)
        self.role_retry_btn.setText(t("roles.checking"))
        self.role_banner.set_message(t("login.role_error"))
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
                t("roles.denied_console")
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
        self.role_banner.set_message(f"{t('login.role_error')} ({message})")
        self.role_banner.setVisible(True)

    def _on_role_retry_finished(self) -> None:
        self._role_retry_running = False
        self.role_retry_btn.setText(t("common.retry"))
        self.role_retry_btn.setEnabled(True)

    # -------------------------------------------------------------- navigation & lazy pages
    def _is_page_built(self, slot_key: str) -> bool:
        return slot_key in self._built_pages

    def _add_nav_item(
        self,
        title: str,
        icon_name: str,
        widget: QWidget,
        canonical_name: str | None = None,
        *,
        slot_key: str | None = None,
    ):
        resolved_slot = slot_key or icon_name
        self._built_pages.setdefault(resolved_slot, widget)
        self.pages[title] = widget
        if canonical_name and canonical_name != title:
            self.pages[canonical_name] = widget
        self.stack.addWidget(widget)
        self._nav_slot_keys.append(resolved_slot)
        # Badge keys reuse the legacy icon keys (pending / maintenance / room_changes).
        self.nav.add_row(title, icon_name, key=icon_name)

    def _add_lazy_nav_item(
        self,
        title: str,
        icon_name: str,
        slot_key: str,
        *,
        canonical_name: str | None = None,
    ) -> QWidget:
        placeholder = QWidget(self.stack)
        self._placeholders[slot_key] = placeholder
        self.pages[title] = placeholder
        if isinstance(self.pages, _LazyPagesDict):
            self.pages.bind_slot(title, slot_key)
        if canonical_name and canonical_name != title:
            self.pages[canonical_name] = placeholder
            if isinstance(self.pages, _LazyPagesDict):
                self.pages.bind_slot(canonical_name, slot_key)
        self.stack.addWidget(placeholder)
        self._nav_slot_keys.append(slot_key)
        self.nav.add_row(title, icon_name, key=icon_name)
        return placeholder

    def _ensure_page(self, slot_key: str) -> QWidget:
        """Build and wire a secondary page on first visit or programmatic access."""
        built = self._built_pages.get(slot_key)
        if built is not None:
            return built

        factory_map = {
            "pending": ("PendingPage", {"defer_initial_load": True}),
            "residents": ("ResidentsPage", {"defer_initial_load": True}),
            "rooms": ("RoomsPage", {"defer_initial_load": True}),
            "maintenance": ("MaintenancePage", {"defer_initial_load": True}),
            "room_changes": ("RoomChangesPage", {"defer_initial_load": True}),
            "official_list": ("OfficialListPage", {"defer_initial_load": True, "role": self.role}),
            "staff_accounts": (
                "StaffAccountsPage",
                {"defer_initial_load": True, "current_uid": getattr(self, "_current_uid", None)},
            ),
            "settings": (
                "SettingsPage",
                {
                    "defer_initial_load": True,
                    "role": self.role,
                    "update_service": self.update_service,
                },
            ),
        }
        if slot_key not in factory_map:
            return self.overview_page

        cls_name, kwargs = factory_map[slot_key]
        cls = _page_factory(cls_name)
        widget = _instantiate_page(cls, self.client, **kwargs)
        self._built_pages[slot_key] = widget
        mark(f"page:{cls_name}")

        # Swap out placeholder at the exact stack index & update self.pages map.
        placeholder = self._placeholders.pop(slot_key, None)
        if placeholder is not None:
            idx = self.stack.indexOf(placeholder)
            was_current = self.stack.currentWidget() is placeholder
            if idx >= 0:
                self.stack.insertWidget(idx, widget)
                self.stack.removeWidget(placeholder)
            else:
                self.stack.addWidget(widget)
            if was_current:
                self.stack.setCurrentWidget(widget)
            placeholder.deleteLater()
            for title, mapped in list(dict.items(self.pages)):
                if mapped is placeholder:
                    dict.__setitem__(self.pages, title, widget)
        elif self.stack.indexOf(widget) < 0:
            self.stack.addWidget(widget)

        # Wire cross-page links and signals.
        if slot_key == "pending":
            if self._is_page_built("official_list"):
                ol = self._built_pages["official_list"]
                if hasattr(ol, "pending_page"):
                    ol.pending_page = widget
        elif slot_key == "official_list":
            if hasattr(widget, "pending_page"):
                widget.pending_page = self._built_pages.get("pending")
            if hasattr(widget, "roster_changed"):
                widget.roster_changed.connect(self._on_roster_changed)
            if hasattr(widget, "set_role") and self.role is not None:
                widget.set_role(self.role)
        elif slot_key == "settings":
            if hasattr(widget, "sign_out_requested"):
                widget.sign_out_requested.connect(self.on_sign_out_clicked)
            if hasattr(widget, "residence_settings_changed"):
                widget.residence_settings_changed.connect(self._on_residence_settings_changed)
            if hasattr(widget, "update_install_requested"):
                widget.update_install_requested.connect(self._on_update_install_requested)
            updates_section = getattr(widget, "updates_section", None)
            if updates_section is not None:
                updates_section.set_busy_checker(
                    lambda: self._signing_out or bool(self._pending_shutdown_action)
                )
            if hasattr(widget, "set_role") and self.role is not None:
                widget.set_role(self.role)

        # Hydrate immediately with cached live-sync snapshot or kick off async reload.
        live = getattr(self, "_cached_live_data", None) or {}
        if slot_key == "pending":
            if "pending_students" in live and hasattr(widget, "apply_live_data"):
                widget.apply_live_data(live["pending_students"])
            elif hasattr(widget, "reload"):
                widget.reload()
        elif slot_key == "maintenance":
            if "reports" in live and hasattr(widget, "apply_live_data"):
                widget.apply_live_data(live["reports"])
            elif hasattr(widget, "reload"):
                widget.reload()
        elif slot_key == "room_changes":
            rows = live.get("room_change_requests") or live.get("pending_requests")
            if rows is not None and hasattr(widget, "apply_live_data"):
                widget.apply_live_data(rows)
            elif hasattr(widget, "reload"):
                widget.reload()
        elif slot_key in ("residents", "rooms", "official_list"):
            if hasattr(widget, "reload"):
                widget.reload()

        cached_gender = getattr(self, "_cached_residence_gender", None)
        if cached_gender is not None and slot_key in ("pending", "residents", "rooms") and hasattr(widget, "set_residence_gender"):
            widget.set_residence_gender(cached_gender)
        elif slot_key == "settings":
            if hasattr(widget, "reload"):
                widget.reload()
            if hasattr(widget, "reload_residence"):
                widget.reload_residence()

        return widget

    def _set_custom_page(self, slot_key: str, value: QWidget) -> None:
        self._built_pages[slot_key] = value
        placeholder = self._placeholders.pop(slot_key, None)
        if placeholder is not None:
            for title, mapped in list(dict.items(self.pages)):
                if mapped is placeholder:
                    dict.__setitem__(self.pages, title, value)

    @property
    def pending_page(self) -> QWidget:
        return self._ensure_page("pending")

    @pending_page.setter
    def pending_page(self, value: QWidget) -> None:
        self._set_custom_page("pending", value)

    @property
    def residents_page(self) -> QWidget:
        return self._ensure_page("residents")

    @residents_page.setter
    def residents_page(self, value: QWidget) -> None:
        self._set_custom_page("residents", value)

    @property
    def rooms_page(self) -> QWidget:
        return self._ensure_page("rooms")

    @rooms_page.setter
    def rooms_page(self, value: QWidget) -> None:
        self._set_custom_page("rooms", value)

    @property
    def maintenance_page(self) -> QWidget:
        return self._ensure_page("maintenance")

    @maintenance_page.setter
    def maintenance_page(self, value: QWidget) -> None:
        self._set_custom_page("maintenance", value)

    @property
    def room_changes_page(self) -> QWidget:
        return self._ensure_page("room_changes")

    @room_changes_page.setter
    def room_changes_page(self, value: QWidget) -> None:
        self._set_custom_page("room_changes", value)

    @property
    def official_list_page(self) -> QWidget:
        return self._ensure_page("official_list")

    @official_list_page.setter
    def official_list_page(self, value: QWidget) -> None:
        self._set_custom_page("official_list", value)

    @property
    def staff_accounts_page(self) -> QWidget:
        return self._ensure_page("staff_accounts")

    @staff_accounts_page.setter
    def staff_accounts_page(self, value: QWidget) -> None:
        self._set_custom_page("staff_accounts", value)

    @property
    def settings_page(self) -> QWidget:
        return self._ensure_page("settings")

    @settings_page.setter
    def settings_page(self, value: QWidget) -> None:
        self._set_custom_page("settings", value)

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
            "connected": t("live_sync.connected"),
            "connecting": t("live_sync.connecting"),
            "reconnecting": t("live_sync.reconnecting"),
            "offline": t("live_sync.offline"),
        }.get(state, t("live_sync.offline"))
        self.live_dot.set_state(state)
        self.live_dot.setToolTip(text)
        self.live_label.setText(text)
        self.live_label.setToolTip(text)

    def _refresh_live_state(self) -> None:
        reference = self._last_tick_at if self._last_tick_at is not None else self._started_at
        elapsed = time.monotonic() - reference
        if self._last_tick_at is not None and elapsed <= _LIVE_CONNECTED_WINDOW_S:
            self._set_live_state("connected")
        elif self._last_tick_at is None and elapsed < 4.0 and not getattr(self, "_sync_error_seen", False):
            self._set_live_state("connecting")
        elif elapsed <= _LIVE_OFFLINE_WINDOW_S:
            self._set_live_state("reconnecting")
        else:
            self._set_live_state("offline")

    # --------------------------------------------------------------- updates
    def _auto_check_updates(self) -> None:
        """Silent background check, throttled to once per day by preferences."""
        if getattr(self, "_closing", False):
            return
        try:
            if not update_prefs.should_auto_check():
                return
            if self.update_service.is_busy():
                return
            self.update_service.check(silent=True)
        except Exception:  # noqa: BLE001 - never block startup on updates
            _log.exception("Automatic update check could not start")

    def _on_update_available(self, available: bool) -> None:
        release = self.update_service.release
        if available and release is not None and self.update_service.is_skipped(
            release.version_str
        ):
            available = False
        self._update_available = bool(available)
        badge = getattr(self, "settings_update_badge", None)
        if badge is not None:
            badge.setVisible(self._update_available and not self._sidebar_minimized)
        if not available or release is None:
            return
        if update_prefs.get_notified_version() == release.version_str:
            return
        try:
            update_prefs.set_notified_version(release.version_str)
        except Exception:  # noqa: BLE001 - notification is best effort
            pass
        components.show_toast(
            self,
            t("updates.available_toast", version=release.version_str),
            kind="info",
            icon="download",
        )

    def _on_update_install_requested(self, path) -> None:
        expected = self.update_service.installer_path
        if expected is None or Path(path) != Path(expected):
            self.update_service.fail_install("")
            return
        if self.update_service.state is not UpdateState.READY:
            self.update_service.fail_install("")
            return
        self._pending_update_path = Path(expected)
        self.update_service.mark_installing()
        self._shutdown_confirmed = True
        self._begin_shutdown("update")

    def _install_pending_update(self) -> None:
        path = self._pending_update_path
        if path is None:
            return
        self._stop_live_timer()
        self._shutdown_workers(0)
        timer = getattr(self, "_shutdown_timer", None)
        if timer is not None:
            timer.stop()
        if getattr(self, "tray_icon", None) is not None:
            self.tray_icon.hide()

        # The installer relaunches RÉSIVO; the single-instance lock must be
        # free before that child starts.
        app = QGuiApplication.instance()
        lock = getattr(app, "_instance_lock", None) if app is not None else None
        if lock is not None:
            try:
                lock.unlock()
            except Exception:  # noqa: BLE001 - best effort release
                _log.warning("Could not release the single-instance lock")
            app._instance_lock = None

        try:
            launch_installer(path)
        except Exception as exc:  # noqa: BLE001 - keep the old install usable
            _log.error("Could not launch the update installer: %s", exc.__class__.__name__)
            message = human_error(exc)
            try:
                update_prefs.set_install_error(message)
            except Exception:  # noqa: BLE001
                pass
            self._pending_update_path = None
            self._shutdown_confirmed = False
            self.update_service.fail_install(message)
            components.show_toast(
                self,
                t("updates.error_installer"),
                kind="error",
                icon="alert-triangle",
            )
            return

        _log.info("Update installer launched; closing for restart")
        try:
            update_prefs.set_install_error("")
        except Exception:  # noqa: BLE001
            pass
        self._pending_update_path = None
        self._closing = True
        self.close()
        if app is not None:
            QTimer.singleShot(0, app.quit)

    # ----------------------------------------------------------- updates end
    def _setup_tray_icon_deferred(self) -> None:
        if getattr(self, "_closing", False) or self.tray_icon is not None:
            return
        self._setup_tray_icon()
        if hasattr(self, "notification_manager") and self.notification_manager is not None:
            self.notification_manager.tray_icon = self.tray_icon

    def _setup_tray_icon(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(self)
        app_icon = self.windowIcon()
        if not app_icon.isNull():
            tray.setIcon(app_icon)
        tray.setToolTip(t("tray.tooltip"))

        tray_menu = QMenu(self)
        open_action = tray_menu.addAction(t("tray.open"))
        open_action.triggered.connect(self._restore_from_tray)
        min_action = tray_menu.addAction(t("tray.minimize"))
        min_action.triggered.connect(self.minimize_to_tray)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction(t("tray.quit"))
        quit_action.triggered.connect(self.request_quit)

        tray.setContextMenu(tray_menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        self.tray_icon = tray

    def minimize_to_tray(self) -> None:
        """Hide the window to system tray, keeping live sync and notifications running."""
        if not getattr(self, "tray_icon", None) or not self.tray_icon.isVisible():
            self.showMinimized()
            return
        self._in_tray = True
        self.hide()
        settings = QSettings("RESIVO", "StaffConsole")
        if not settings.value("general/tray_notice_shown", False, type=bool):
            settings.setValue("general/tray_notice_shown", True)
            self.tray_icon.showMessage(
                t("tray.balloon_title"),
                t("tray.balloon_msg"),
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )

    def _restore_from_tray(self) -> None:
        """Restore window from system tray back to foreground with original state."""
        self._in_tray = False
        prev = getattr(self, "_prev_window_state", None)
        if prev is not None and bool(prev & Qt.WindowState.WindowMaximized):
            self.setWindowState(Qt.WindowState.WindowMaximized)
            self.show()
        else:
            self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_minimize_shortcut(self) -> None:
        if get_minimize_to_tray_setting():
            self.minimize_to_tray()
        else:
            self.showMinimized()

    def _on_tray_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            if self.isVisible() and not self.isMinimized() and self.isActiveWindow():
                if get_minimize_to_tray_setting():
                    self.minimize_to_tray()
                else:
                    self.showMinimized()
            else:
                self._restore_from_tray()

    def changeEvent(self, event):  # noqa: N802 - Qt event override
        if event.type() == QEvent.Type.WindowStateChange:
            if not self.isMinimized():
                self._prev_window_state = self.windowState()
            elif get_minimize_to_tray_setting():
                if getattr(self, "tray_icon", None) and self.tray_icon.isVisible():
                    QTimer.singleShot(0, self.minimize_to_tray)
        super().changeEvent(event)

    def on_live_alert(self, msg: str):
        """Live event → In-app Toast + Desktop Notification."""
        components.show_toast(self, msg, kind="info", icon="bell")
        if hasattr(self, "notification_manager"):
            self.notification_manager.process_alert(msg, window=self)

    def on_live_sync_error(self, _err_msg: str):
        """Worker timed out or lost connection: show reconnecting in amber."""
        self._sync_error_seen = True
        self._set_live_state("reconnecting")

    def on_live_sync_tick(self, data: dict):
        if not getattr(self, "_startup_first_data_marked", False):
            self._startup_first_data_marked = True
            mark("first_data_received")
            timeline().dump_summary()
        self._sync_error_seen = False
        self._cached_live_data = dict(data)
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
            t(
                "live_sync.status_bar",
                status=t("live_sync.active"),
                timestamp=timestamp,
                pending=p_count,
                open_tickets=m_count,
                transfers=r_count,
            )
        )

        # 2. Gold count pills on the sidebar rows.
        self.nav.set_badge("pending", p_count)
        self.nav.set_badge("maintenance", m_count)
        self.nav.set_badge("room_changes", r_count)

        # 3. Live indicator: a fresh tick means connected.
        self._last_tick_at = time.monotonic()
        self._set_live_state("connected")

        # 4. Deliver live data ONLY to built pages (lazy pages hydrate when opened).
        if hasattr(self.overview_page, "apply_live_data"):
            self.overview_page.apply_live_data(p_count, m_count, r_count, active_count)
        built_pages = getattr(self, "_built_pages", None)
        for slot_key, attr_name, payload in (
            ("pending", "pending_page", pending_students),
            ("maintenance", "maintenance_page", reports),
            ("room_changes", "room_changes_page", request_rows),
        ):
            page = (
                built_pages.get(slot_key)
                if built_pages is not None
                else getattr(self, attr_name, None)
            )
            if page is not None and hasattr(page, "apply_live_data"):
                page.apply_live_data(payload)

    # ------------------------------------------------------------------- flow
    def _long_lived_workers(self) -> list:
        """Sync/health/photo QThreads that must finish before the window dies."""
        workers = []
        sync = getattr(self, "sync_worker", None)
        if sync is not None:
            workers.append(sync)
        settings = self._built_pages.get("settings") if hasattr(self, "_built_pages") else None
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
        elif action == "update":
            self._install_pending_update()

    def _stop_live_timer(self) -> None:
        timer = getattr(self, "_live_timer", None)
        if timer is not None:
            timer.stop()

    def _on_nav_row_changed(self, index: int) -> None:
        if hasattr(self, "settings_btn") and self.settings_btn.isChecked():
            self.settings_btn.setChecked(False)
        slot_key = self._nav_slot_keys[index] if 0 <= index < len(self._nav_slot_keys) else None
        if slot_key is not None:
            page = self._ensure_page(slot_key)
            self.stack.setCurrentWidget(page)
        else:
            self.stack.setCurrentIndex(index)

    def on_settings_clicked(self) -> None:
        self.nav.clear_selection()
        if hasattr(self, "settings_btn"):
            self.settings_btn.setChecked(True)
        page = self._ensure_page("settings")
        self.stack.setCurrentWidget(page)
        if hasattr(page, "on_shown"):
            page.on_shown()
        if hasattr(page, "reload_residence"):
            page.reload_residence()

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
        try:
            session_manager.clear()
        except Exception as exc:
            _log.warning("Could not clear stored session file during sign-out: %s", exc)
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
        try:
            session_manager.clear()
        except Exception:
            pass
        self._forget_cached_role()

    def _on_sign_out_failed(self, message: str) -> None:
        # The window is already leaving; clear the local session explicitly so
        # a failed server call cannot leave refresh credentials behind, then
        # surface the failure on the login window.
        self._sign_out_error = message
        try:
            session_manager.clear()
        except Exception:
            pass
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
        self._closing = True
        # A sign-out that is still waiting for workers must survive the close:
        # switch it to the no-login variant and keep the shutdown poll running.
        action = getattr(self, "_pending_shutdown_action", None)
        if action == "update":
            # The update owns the shutdown: ignore extra close requests until
            # the verified installer has been launched (or failed).
            event.ignore()
            return
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
                    code = dlg.exec()
                    if getattr(dlg, "was_minimized_to_tray", False):
                        event.ignore()
                        self.minimize_to_tray()
                        return
                    if code != QDialog.DialogCode.Accepted:
                        self._closing = False
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
        if getattr(self, "tray_icon", None) is not None:
            self.tray_icon.hide()
        self._pending_shutdown_action = None
        super().closeEvent(event)
