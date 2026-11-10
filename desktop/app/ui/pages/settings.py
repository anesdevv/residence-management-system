"""RÉSIVO — Settings (visual layer only, docs/DESIGN.md §6–§7).

Cards, section overlines, token-built checkbox styling, a ``StatusPill`` health
badge, a monospace token box and flat command boxes. Everything behavioural is
unchanged: ``McpHealthWorker`` (class name, ``start()`` / ``stop()``, the local
health URL, the 5 s interval and its up/down transition signalling), the writes
off-switch RPCs (``mcp_get_settings`` / ``mcp_set_writes_enabled``) with their
fail-safe revert, the admin-only role gating, and the MCP token read / reveal /
copy flow.

After the constructor's first load, the writes RPCs and settings reload run on
the shared :class:`TaskRunner`; reveal/copy use the role cached by the page and
never re-query the network.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QFontDatabase, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    from i18n import current_language, format_date, get_saved_language, set_saved_language, t, tn
except ImportError:
    from desktop.i18n import current_language, format_date, get_saved_language, set_saved_language, t, tn

from ...client import (
    DEFAULT_RESIDENCE_NAME,
    current_role,
    fetch_residence_gender_impact,
    fetch_residence_settings_admin,
    set_residence_gender,
    set_residence_name,
    stored_user_email,
)
try:
    from desktop.auth.session_store import (
        get_remember_session_setting,
        set_remember_session_setting,
        session_manager,
    )
except ImportError:
    from auth.session_store import (
        get_remember_session_setting,
        set_remember_session_setting,
        session_manager,
    )
from ...tls import urlopen_with_tls
from .. import theme
from ..close_policy import (
    get_confirm_close_setting,
    set_confirm_close_setting,
    get_minimize_to_tray_setting,
    set_minimize_to_tray_setting,
)
from ..components import Button, Card, ConfirmDialog, InlineBanner, PageHeader, StatusPill
from ..notifications import NotificationManager
from ..residence_dialogs import ResidenceGenderChangeDialog, residence_gender_label
from ..resource import get_asset_path
from ..tasks import TaskRunner, human_error
from ..theme import C, S

try:
    from desktop.platform import autostart
except ImportError:
    from platform import autostart


MCP_HEALTH_URL = "http://127.0.0.1:8000/health"
MCP_HEALTH_TIMEOUT_S = 2.0
MCP_HEALTH_INTERVAL_MS = 5000
MCP_HOSTED_URL = "https://resivo-mcp.anes4tlm.workers.dev/mcp"

_LOAD_KEY = "settings-load"
_WRITES_KEY = "settings-writes"
_RESIDENCE_IMPACT_KEY = "settings-residence-impact"
_RESIDENCE_SAVE_KEY = "settings-residence-save"
_RESIDENCE_NAME_KEY = "settings-residence-name"
_WORKING_TEXT = "Working..."


def _writes_tooltip() -> str:
    return t("settings.writes_tooltip")


def _writes_note() -> str:
    return t("settings.writes_note")


def _mono_family() -> str:
    """System fixed-width family (empty before a QGuiApplication exists)."""
    if QGuiApplication.instance() is None:
        return ""
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


def _mono_qss() -> str:
    """Monospace command text, built from tokens only."""
    family = _mono_family()
    parts = [f'font-family: "{family}";'] if family else []
    parts.append(f"font-size: {C('fs-small')};")
    parts.append(f"color: {C('text-primary')};")
    parts.append("background: transparent; border: none;")
    return " ".join(parts)


def _token_qss() -> str:
    """Monospace token box (flat card look), built from tokens only."""
    family = _mono_family()
    parts = [f'font-family: "{family}";'] if family else []
    parts.append(f"font-size: {C('fs-small')};")
    parts.append(f"color: {C('text-primary')};")
    parts.append(f"background-color: {C('surface-subtle')};")
    parts.append(f"border: 1px solid {C('border')};")
    parts.append(f"border-radius: {C('radius-input')};")
    parts.append(f"padding: {C('pill-pad-y')} {C('pill-pad-x')};")
    return " ".join(parts)


def _hint_qss() -> str:
    """Muted hint line (tokens only)."""
    return f"color: {C('text-secondary')}; font-size: {C('fs-small')};"


def _flat_box_qss(object_name: str) -> str:
    """Flat command box: subtle surface, hairline border, card radius."""
    return (
        f"QFrame#{object_name} {{ background-color: {C('surface-subtle')};"
        f" border: 1px solid {C('border')}; border-radius: {C('radius-input')}; }}"
    )


def _checkbox_qss() -> str:
    """Token-only checkbox styling (the page also reads well outside the shell)."""
    size = S("size-icon")
    return (
        f"QCheckBox {{ color: {C('text-primary')}; font-size: {C('fs-body')};"
        f" font-weight: {C('fw-medium')}; spacing: {C('space-2')}; }}"
        f"QCheckBox::indicator {{ width: {size}px; height: {size}px;"
        f" border: 1px solid {C('border-strong')}; border-radius: {C('radius-input')};"
        f" background-color: {C('surface')}; }}"
        f"QCheckBox::indicator:hover {{ border-color: {C('teal-600')}; }}"
        f"QCheckBox::indicator:checked {{ background-color: {C('teal-600')};"
        f" border-color: {C('teal-600')}; }}"
        f"QCheckBox:disabled {{ color: {C('text-muted')}; }}"
        f"QCheckBox::indicator:disabled {{ background-color: {C('surface-subtle')};"
        f" border-color: {C('border')}; }}"
    )


def _apply_small(label: QLabel, word_wrap: bool = True) -> QLabel:
    """Hint typography (role ``small``) with optional wrapping."""
    theme.apply_role(label, "small")
    label.setWordWrap(word_wrap)
    return label


def build_mcp_url(raw: str) -> str:
    """Normalize a tunnel URL into the ChatGPT MCP server URL. Pure and testable."""
    url = (raw or "").strip()
    if not url:
        return ""
    url = url.rstrip("/")
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    if not url.lower().endswith("/mcp"):
        url = url + "/mcp"
    return url


def _normalize_role(role) -> str | None:
    """Case/whitespace-insensitive role value (``" Admin "`` -> ``"admin"``)."""
    if role is None:
        return None
    normalized = str(role).strip().lower()
    return normalized or None


def _application_root() -> Path:
    """Executable folder for frozen builds, repo root during development."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[4]


def _mcp_env_candidates() -> list[Path]:
    """Where ``mcp/.env`` may live (never bundled: it contains a secret)."""
    if getattr(sys, "frozen", False):
        candidates = [_application_root() / "mcp" / ".env"]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "mcp" / ".env")
        return candidates
    return [_application_root() / "mcp" / ".env"]


def _read_mcp_token() -> str:
    """Read MCP_AUTH_TOKEN from ``mcp/.env``. The value is never logged."""
    for env_path in _mcp_env_candidates():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("MCP_AUTH_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            continue
    return ""


class McpHealthWorker(QThread):
    """Polls the local MCP server and reports up/down transitions."""

    health_changed = Signal(bool)

    def __init__(self, url: str = MCP_HEALTH_URL, timeout_s: float = MCP_HEALTH_TIMEOUT_S,
                 interval_ms: int = MCP_HEALTH_INTERVAL_MS):
        super().__init__()
        self.url = url
        self.timeout_s = timeout_s
        self.interval_ms = interval_ms
        self._running = True
        self._last_up: bool | None = None

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            up = False
            try:
                with urlopen_with_tls(self.url, timeout=self.timeout_s) as resp:
                    up = 200 <= resp.status < 300
            except Exception:
                # Connection refused / timeout / non-HTTP reply = server offline
                up = False

            if up != self._last_up:
                self._last_up = up
                self.health_changed.emit(up)

            # Responsive sleep so the thread exits cleanly without hanging
            sleep_elapsed = 0
            while self._running and sleep_elapsed < self.interval_ms:
                self.msleep(100)
                sleep_elapsed += 100


def _role_label(role: str | None) -> str:
    """Human label for user role."""
    normalized = _normalize_role(role)
    if not normalized:
        return t("roles.unverified")
    if normalized == "admin":
        return t("roles.admin")
    if normalized == "staff":
        return t("roles.staff")
    return normalized.title()


class SettingsPage(QWidget):
    sign_out_requested = Signal()
    residence_settings_changed = Signal()

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.role = _normalize_role(current_role(client))
        self._role_unverified = self.role is None
        self._health_started = False
        self._token = ""
        self._token_revealed = False
        self._writes_loading = False
        self._writes_available = False
        self._writes_saving = False
        self._settings_loading = False
        self._current_residence_name = DEFAULT_RESIDENCE_NAME
        self._current_residence_gender: str | None = None
        self._residence_loading = False
        self._residence_saving = False
        self._initializing = True
        self.tasks = TaskRunner(self)

        # Root layout hosting the QScrollArea
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Smooth scroll area ensuring all settings and developer mode steps
        # remain fully visible and comfortable across all window sizes without clipping.
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("settingsScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_content = QWidget()
        scroll_content.setObjectName("settingsScrollContent")
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(S("space-8"), S("space-8"), S("space-8"), S("space-8"))
        layout.setSpacing(S("space-6"))

        self.header = PageHeader(
            t("settings.title"),
            t("settings.subtitle"),
        )
        layout.addWidget(self.header)

        # Residence settings card (admin only)
        self.residence_card = Card(
            t("settings.residence_title"),
            t("settings.residence_subtitle"),
            icon="building",
        )

        res_name_row = QHBoxLayout()
        res_name_row.setSpacing(S("space-3"))
        self.residence_name_label = QLabel(t("settings.residence_name_label"))
        theme.apply_role(self.residence_name_label, "h3")
        self.residence_name_label.setMinimumWidth(140)
        res_name_row.addWidget(self.residence_name_label)

        self.residence_name_edit = QLineEdit(DEFAULT_RESIDENCE_NAME)
        self.residence_name_edit.setObjectName("residenceNameEdit")
        self.residence_name_edit.setPlaceholderText(t("settings.residence_name_placeholder"))
        res_name_row.addWidget(self.residence_name_edit, 1)

        self.residence_name_save_btn = Button.secondary(t("settings.residence_name_save"))
        self.residence_name_save_btn.setObjectName("residenceNameSaveButton")
        self.residence_name_save_btn.clicked.connect(self._on_residence_name_save)
        res_name_row.addWidget(self.residence_name_save_btn)
        self.residence_card.add_layout(res_name_row)

        res_type_row = QHBoxLayout()
        res_type_row.setSpacing(S("space-3"))
        self.residence_type_label = QLabel(t("settings.residence_type_label"))
        theme.apply_role(self.residence_type_label, "h3")
        self.residence_type_label.setMinimumWidth(140)
        res_type_row.addWidget(self.residence_type_label)

        self.residence_type_combo = QComboBox()
        self.residence_type_combo.setObjectName("residenceTypeCombo")
        self.residence_type_combo.addItem(t("settings.residence_type_unset"), None)
        self.residence_type_combo.addItem(t("residence.male_residence"), "male")
        self.residence_type_combo.addItem(t("residence.female_residence"), "female")
        self.residence_type_combo.currentIndexChanged.connect(self._on_residence_type_selected)
        res_type_row.addWidget(self.residence_type_combo)
        res_type_row.addStretch(1)
        self.residence_card.add_layout(res_type_row)

        self.residence_type_helper = QLabel(t("settings.residence_type_helper"))
        _apply_small(self.residence_type_helper)
        self.residence_card.add_widget(self.residence_type_helper)

        self.residence_audit_label = QLabel(t("settings.residence_never_changed"))
        self.residence_audit_label.setObjectName("residenceAuditLabel")
        _apply_small(self.residence_audit_label)
        self.residence_card.add_widget(self.residence_audit_label)

        self.residence_banner = InlineBanner(
            kind="error",
            title=t("settings.residence_error_title"),
            message="",
        )
        self.residence_banner.setVisible(False)
        self.residence_card.add_widget(self.residence_banner)

        layout.addWidget(self.residence_card)

        # General settings card
        self.general_card = Card(
            t("settings.general_title"),
            t("settings.general_subtitle"),
            icon="settings",
        )

        # Language preference setting
        lang_row = QHBoxLayout()
        lang_row.setSpacing(S("space-3"))
        self.lang_label = QLabel(t("settings.language_label"))
        theme.apply_role(self.lang_label, "h3")
        lang_row.addWidget(self.lang_label)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("Français", "fr")
        saved_lang = get_saved_language() or current_language()
        self.lang_combo.setCurrentIndex(1 if saved_lang == "fr" else 0)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch(1)
        self.general_card.add_layout(lang_row)

        self.lang_note = QLabel(t("settings.language_note"))
        _apply_small(self.lang_note)
        self.general_card.add_widget(self.lang_note)

        # Language restart notification banner
        self.lang_restart_banner = InlineBanner(
            kind="info",
            title="RÉSIVO",
            message=t("settings.restart_banner_message"),
        )
        self.restart_now_btn = Button.primary(t("settings.restart_now"))
        self.restart_now_btn.clicked.connect(self._restart_app)
        self.restart_later_btn = Button.secondary(t("settings.restart_later"))
        self.restart_later_btn.clicked.connect(lambda: self.lang_restart_banner.setVisible(False))
        self.lang_restart_banner.add_action(self.restart_now_btn)
        self.lang_restart_banner.add_action(self.restart_later_btn)
        self.lang_restart_banner.setVisible(False)
        self.general_card.add_widget(self.lang_restart_banner)

        self.confirm_close_checkbox = QCheckBox(t("settings.confirm_close_label"))
        self.confirm_close_checkbox.setStyleSheet(_checkbox_qss())
        self.confirm_close_checkbox.setChecked(get_confirm_close_setting())
        self.confirm_close_checkbox.setToolTip(t("settings.confirm_close_tooltip"))
        self.confirm_close_checkbox.toggled.connect(self._on_confirm_close_toggled)
        self.general_card.add_widget(self.confirm_close_checkbox)

        self.confirm_close_note = QLabel(t("settings.confirm_close_note"))
        _apply_small(self.confirm_close_note)
        self.general_card.add_widget(self.confirm_close_note)

        self.minimize_tray_checkbox = QCheckBox(t("settings.minimize_tray_label"))
        self.minimize_tray_checkbox.setStyleSheet(_checkbox_qss())
        self.minimize_tray_checkbox.setChecked(get_minimize_to_tray_setting())
        self.minimize_tray_checkbox.setToolTip(t("settings.minimize_tray_tooltip"))
        self.minimize_tray_checkbox.toggled.connect(self._on_minimize_tray_toggled)
        self.general_card.add_widget(self.minimize_tray_checkbox)

        self.minimize_tray_note = QLabel(t("settings.minimize_tray_note"))
        _apply_small(self.minimize_tray_note)
        self.general_card.add_widget(self.minimize_tray_note)

        # Autostart settings (Windows only)
        self.autostart_container = QWidget()
        autostart_layout = QVBoxLayout(self.autostart_container)
        autostart_layout.setContentsMargins(0, S("space-3"), 0, 0)
        autostart_layout.setSpacing(S("space-2"))

        self.autostart_checkbox = QCheckBox(t("settings.autostart_label"))
        self.autostart_checkbox.setStyleSheet(_checkbox_qss())
        self.autostart_checkbox.setToolTip(t("settings.autostart_tooltip"))
        self.autostart_checkbox.toggled.connect(self._on_autostart_toggled)
        autostart_layout.addWidget(self.autostart_checkbox)

        self.autostart_helper = QLabel(t("settings.autostart_helper"))
        _apply_small(self.autostart_helper)
        autostart_layout.addWidget(self.autostart_helper)

        self.autostart_win_note = QLabel(t("settings.autostart_win_note"))
        _apply_small(self.autostart_win_note)
        self.autostart_win_note.setStyleSheet(
            f"color: {C('status-pending-ink')}; font-size: {C('fs-small')}; font-weight: {C('fw-medium')};"
        )
        self.autostart_win_note.setVisible(False)
        autostart_layout.addWidget(self.autostart_win_note)

        # Sub-option: Start minimized
        self.start_minimized_container = QWidget()
        sm_layout = QHBoxLayout(self.start_minimized_container)
        sm_layout.setContentsMargins(S("space-6"), 0, 0, 0)
        sm_layout.setSpacing(S("space-2"))

        self.start_minimized_checkbox = QCheckBox(t("settings.start_minimized_label"))
        self.start_minimized_checkbox.setStyleSheet(_checkbox_qss())
        self.start_minimized_checkbox.setToolTip(t("settings.start_minimized_tooltip"))
        self.start_minimized_checkbox.setChecked(autostart.get_start_minimized_setting())
        self.start_minimized_checkbox.toggled.connect(self._on_start_minimized_toggled)
        sm_layout.addWidget(self.start_minimized_checkbox)
        autostart_layout.addWidget(self.start_minimized_container)

        self.autostart_error_banner = InlineBanner(kind="error")
        self.autostart_error_banner.setVisible(False)
        autostart_layout.addWidget(self.autostart_error_banner)

        self.autostart_note = QLabel(t("settings.autostart_note"))
        _apply_small(self.autostart_note)
        autostart_layout.addWidget(self.autostart_note)

        self.general_card.add_widget(self.autostart_container)
        self._update_autostart_ui()

        layout.addWidget(self.general_card)

        # Security & Sign-in settings card
        self.security_card = Card(
            t("settings.security_title"),
            t("settings.security_subtitle"),
            icon="shield",
        )

        self.remember_session_checkbox = QCheckBox(t("settings.remember_session_label"))
        self.remember_session_checkbox.setObjectName("rememberSessionCheckbox")
        self.remember_session_checkbox.setStyleSheet(_checkbox_qss())
        self.remember_session_checkbox.setChecked(get_remember_session_setting())
        self.remember_session_checkbox.toggled.connect(self._on_remember_session_toggled)
        self.security_card.add_widget(self.remember_session_checkbox)

        self.remember_session_helper = QLabel(t("settings.remember_session_helper"))
        _apply_small(self.remember_session_helper)
        self.security_card.add_widget(self.remember_session_helper)

        # Account info and Sign out row
        account_row = QHBoxLayout()
        account_row.setContentsMargins(0, S("space-3"), 0, 0)
        account_row.setSpacing(S("space-4"))

        self.signed_in_label = QLabel()
        theme.apply_role(self.signed_in_label, "body")
        self._update_signed_in_label()
        account_row.addWidget(self.signed_in_label)
        account_row.addStretch(1)

        self.security_sign_out_btn = Button.secondary(
            t("settings.security_sign_out"),
            icon="logout",
        )
        self.security_sign_out_btn.setObjectName("securitySignOutButton")
        self.security_sign_out_btn.clicked.connect(self.sign_out_requested.emit)
        account_row.addWidget(self.security_sign_out_btn)

        self.security_card.add_layout(account_row)

        layout.addWidget(self.security_card)

        # Notifications settings card
        self.notif_card = Card(
            t("settings.notifications_title"),
            t("settings.notifications_subtitle"),
            icon="bell",
        )

        self.notif_manager = NotificationManager(self)
        ns = self.notif_manager.settings

        self.notif_master_cb = QCheckBox(t("settings.notifications_enable"))
        self.notif_master_cb.setStyleSheet(_checkbox_qss())
        self.notif_master_cb.setChecked(ns.enabled)
        self.notif_master_cb.toggled.connect(self._on_notif_master_toggled)
        self.notif_card.add_widget(self.notif_master_cb)

        self.notif_options_container = QWidget()
        noc_layout = QVBoxLayout(self.notif_options_container)
        noc_layout.setContentsMargins(S("space-4"), 0, 0, 0)
        noc_layout.setSpacing(S("space-3"))

        # Event toggles
        self.notif_maint_cb = QCheckBox(t("settings.notif_maintenance"))
        self.notif_maint_cb.setStyleSheet(_checkbox_qss())
        self.notif_maint_cb.setChecked(ns.notify_maintenance)
        self.notif_maint_cb.toggled.connect(lambda v: setattr(ns, "notify_maintenance", v))
        noc_layout.addWidget(self.notif_maint_cb)

        self.notif_rooms_cb = QCheckBox(t("settings.notif_room_changes"))
        self.notif_rooms_cb.setStyleSheet(_checkbox_qss())
        self.notif_rooms_cb.setChecked(ns.notify_room_changes)
        self.notif_rooms_cb.toggled.connect(lambda v: setattr(ns, "notify_room_changes", v))
        noc_layout.addWidget(self.notif_rooms_cb)

        self.notif_regs_cb = QCheckBox(t("settings.notif_registrations"))
        self.notif_regs_cb.setStyleSheet(_checkbox_qss())
        self.notif_regs_cb.setChecked(ns.notify_registrations)
        self.notif_regs_cb.toggled.connect(lambda v: setattr(ns, "notify_registrations", v))
        noc_layout.addWidget(self.notif_regs_cb)

        # Delivery & Privacy
        self.notif_names_cb = QCheckBox(t("settings.notif_show_names"))
        self.notif_names_cb.setStyleSheet(_checkbox_qss())
        self.notif_names_cb.setChecked(ns.show_student_names)
        self.notif_names_cb.toggled.connect(lambda v: setattr(ns, "show_student_names", v))
        noc_layout.addWidget(self.notif_names_cb)

        self.notif_unfocused_cb = QCheckBox(t("settings.notif_only_unfocused"))
        self.notif_unfocused_cb.setStyleSheet(_checkbox_qss())
        self.notif_unfocused_cb.setChecked(ns.only_unfocused)
        self.notif_unfocused_cb.toggled.connect(lambda v: setattr(ns, "only_unfocused", v))
        noc_layout.addWidget(self.notif_unfocused_cb)

        self.notif_sound_cb = QCheckBox(t("settings.notif_play_sound"))
        self.notif_sound_cb.setStyleSheet(_checkbox_qss())
        self.notif_sound_cb.setChecked(ns.play_sound)
        self.notif_sound_cb.toggled.connect(lambda v: setattr(ns, "play_sound", v))
        noc_layout.addWidget(self.notif_sound_cb)

        # Quiet hours
        self.notif_quiet_cb = QCheckBox(t("settings.notif_quiet_hours"))
        self.notif_quiet_cb.setStyleSheet(_checkbox_qss())
        self.notif_quiet_cb.setChecked(ns.quiet_hours_enabled)
        self.notif_quiet_cb.toggled.connect(self._on_quiet_hours_toggled)
        noc_layout.addWidget(self.notif_quiet_cb)

        quiet_row = QHBoxLayout()
        quiet_row.setSpacing(S("space-2"))
        lbl_start = QLabel(t("settings.quiet_hours_from"))
        _apply_small(lbl_start)
        quiet_row.addWidget(lbl_start)

        self.quiet_start_edit = QLineEdit(ns.quiet_hours_start)
        self.quiet_start_edit.setFixedWidth(70)
        self.quiet_start_edit.setFixedHeight(32)
        self.quiet_start_edit.setPlaceholderText("22:00")
        self.quiet_start_edit.textChanged.connect(lambda v: setattr(ns, "quiet_hours_start", v))
        quiet_row.addWidget(self.quiet_start_edit)

        lbl_end = QLabel(t("settings.quiet_hours_to"))
        _apply_small(lbl_end)
        quiet_row.addWidget(lbl_end)

        self.quiet_end_edit = QLineEdit(ns.quiet_hours_end)
        self.quiet_end_edit.setFixedWidth(70)
        self.quiet_end_edit.setFixedHeight(32)
        self.quiet_end_edit.setPlaceholderText("07:00")
        self.quiet_end_edit.textChanged.connect(lambda v: setattr(ns, "quiet_hours_end", v))
        quiet_row.addWidget(self.quiet_end_edit)
        quiet_row.addStretch(1)

        self.quiet_row_widget = QWidget()
        self.quiet_row_widget.setLayout(quiet_row)
        self.quiet_row_widget.setVisible(ns.quiet_hours_enabled)
        noc_layout.addWidget(self.quiet_row_widget)

        # Send test notification button
        btn_row = QHBoxLayout()
        self.test_notif_btn = Button.secondary(t("settings.test_notif_button"), icon="bell")
        self.test_notif_btn.setFixedHeight(36)
        self.test_notif_btn.clicked.connect(self._on_send_test_notif)
        btn_row.addWidget(self.test_notif_btn)
        btn_row.addStretch(1)
        noc_layout.addLayout(btn_row)

        self.notif_card.add_widget(self.notif_options_container)
        self.notif_options_container.setVisible(ns.enabled)
        layout.addWidget(self.notif_card)

        # Advanced settings (developer mode) card
        self.dev_card = Card(
            t("settings.advanced_title"),
            t("settings.advanced_subtitle"),
            icon="settings",
        )

        self.dev_checkbox = QCheckBox(t("settings.dev_mode_label"))
        self.dev_checkbox.setStyleSheet(_checkbox_qss())
        self.dev_checkbox.setToolTip(t("settings.dev_mode_tooltip"))
        self.dev_checkbox.toggled.connect(self._on_dev_mode_toggled)
        self.dev_card.add_widget(self.dev_checkbox)

        self.staff_note = QLabel(t("settings.dev_mode_admin_only"))
        _apply_small(self.staff_note)
        self.dev_card.add_widget(self.staff_note)

        self.enable_note = QLabel(t("settings.dev_mode_enable_note"))
        _apply_small(self.enable_note)
        self.dev_card.add_widget(self.enable_note)

        # ChatGPT write off-switch — admin only, outside the developer-mode gate
        self.writes_checkbox = QCheckBox(t("settings.writes_label"))
        self.writes_checkbox.setStyleSheet(_checkbox_qss())
        self.writes_checkbox.setToolTip(_writes_tooltip())
        self.writes_checkbox.toggled.connect(self._on_writes_toggled)
        self.dev_card.add_widget(self.writes_checkbox)

        self.writes_note = QLabel(_writes_note())
        _apply_small(self.writes_note)
        self.dev_card.add_widget(self.writes_note)

        self.writes_banner = InlineBanner(
            "error",
            title=t("settings.writes_error_title"),
            message="",
        )
        self.writes_banner.setVisible(False)
        self.dev_card.add_widget(self.writes_banner)

        self.content = self._build_content()
        self.dev_card.add_widget(self.content)

        layout.addWidget(self.dev_card)

        # About — built outside the developer-mode gate on purpose: the credit is
        # visible for every role without toggling Developer mode.
        self.about_widget = self._build_about()
        layout.addWidget(self.about_widget)
        layout.addStretch(1)

        self.scroll_area.setWidget(scroll_content)
        root_layout.addWidget(self.scroll_area)

        # Background health poller (admins only; set_role starts/stops it)
        self.health_worker = McpHealthWorker()
        self.health_worker.health_changed.connect(self._on_health_changed)

        # Role gating — developer mode is session-only, never persisted.
        self.writes_checkbox.setEnabled(False)  # enabled once the setting loads
        self.set_role(self.role)

        self.reload()
        if self.role == "admin":
            self._load_residence_sync()
        self._initializing = False

    def _on_language_changed(self, index: int) -> None:
        lang_code = self.lang_combo.itemData(index)
        if not lang_code:
            return
        current = get_saved_language() or current_language()
        if lang_code != current:
            set_saved_language(lang_code)
            if get_remember_session_setting():
                self.lang_restart_banner.set_message(t("settings.restart_banner_message"))
            else:
                self.lang_restart_banner.set_message(t("settings.restart_banner_message_need_login"))
            self.lang_restart_banner.setVisible(True)

    def _restart_app(self) -> None:
        """Trigger safe restart of RÉSIVO, releasing single-instance lock."""
        app = QApplication.instance()
        if app is not None and hasattr(app, "_instance_lock") and app._instance_lock is not None:
            try:
                app._instance_lock.unlock()
            except Exception:
                pass

        args = [arg for arg in sys.argv[1:] if arg != "--restarted"] + ["--restarted"]
        if not getattr(sys, "frozen", False):
            main_script = str(Path(__file__).resolve().parents[3] / "main.py")
            if not args or Path(args[0]).name != "main.py":
                args = [main_script, *args]
        QProcess.startDetached(sys.executable, args)
        if app is not None:
            app.quit()

    def set_role(self, role) -> None:
        """Apply admin gating for a (re)verified role without rebuilding the UI."""
        previous = self.role
        normalized = _normalize_role(role)
        self.role = normalized
        self._role_unverified = normalized is None
        is_admin = normalized == "admin"

        if hasattr(self, "residence_card"):
            self.residence_card.setVisible(is_admin)

        if is_admin:
            self.staff_note.setVisible(False)
            self.dev_checkbox.setEnabled(True)
            self.dev_checkbox.setToolTip(t("settings.dev_mode_tooltip"))
            self.enable_note.setVisible(not self.dev_checkbox.isChecked())
            self.content.setVisible(self.dev_checkbox.isChecked())
        else:
            self.dev_checkbox.setEnabled(False)
            self.dev_checkbox.setToolTip(t("settings.dev_mode_admin_only"))
            self.staff_note.setVisible(True)
            self.enable_note.setVisible(False)
            self.content.setVisible(False)

        self.writes_checkbox.setVisible(is_admin)
        self.writes_note.setVisible(is_admin)

        if is_admin:
            if previous != "admin" and not self._initializing:
                self._token = _read_mcp_token()
                self._render_token_row()
                self.reload()
            if not self._health_started:
                self.health_worker.start()
                self._health_started = True
        else:
            self._token = ""
            self._render_token_row()
            if self._health_started:
                self.health_worker.stop()
                self._health_started = False

        self._update_signed_in_label()

    def _update_signed_in_label(self) -> None:
        if hasattr(self, "signed_in_label"):
            email = stored_user_email(self.client) or "—"
            role_text = _role_label(self.role)
            self.signed_in_label.setText(t("settings.signed_in_as", email=email, role=role_text))

    def _on_remember_session_toggled(self, checked: bool) -> None:
        set_remember_session_setting(checked)
        if checked:
            session_manager.save_current_session(self.client, remember=True)
        else:
            session_manager.clear()

    def _on_confirm_close_toggled(self, checked: bool) -> None:
        set_confirm_close_setting(checked)

    def _on_minimize_tray_toggled(self, checked: bool) -> None:
        set_minimize_to_tray_setting(checked)

    def _update_autostart_ui(self) -> None:
        """Update autostart switch and sub-option according to OS and registry."""
        if sys.platform != "win32":
            self.autostart_container.setVisible(False)
            return

        self.autostart_container.setVisible(True)
        if not autostart.is_supported():
            self.autostart_checkbox.blockSignals(True)
            self.autostart_checkbox.setEnabled(False)
            self.autostart_checkbox.setChecked(False)
            self.autostart_checkbox.blockSignals(False)
            self.autostart_helper.setText(t("settings.autostart_unsupported"))
            self.start_minimized_checkbox.setEnabled(False)
            self.start_minimized_checkbox.setChecked(autostart.get_start_minimized_setting())
            self.autostart_win_note.setVisible(False)
            return

        self.autostart_checkbox.setEnabled(True)
        self.autostart_helper.setText(t("settings.autostart_helper"))
        state = autostart.get_state()
        is_active = (state == "enabled")
        self.autostart_checkbox.blockSignals(True)
        self.autostart_checkbox.setChecked(is_active)
        self.autostart_checkbox.blockSignals(False)
        self.start_minimized_checkbox.setEnabled(is_active)
        self.start_minimized_checkbox.setChecked(autostart.get_start_minimized_setting())
        self.autostart_win_note.setVisible(state == "disabled_by_windows")

    def _on_autostart_toggled(self, checked: bool) -> None:
        self.autostart_error_banner.setVisible(False)
        if checked:
            success, err = autostart.enable()
            if not success:
                self.autostart_error_banner.set_message(err or "Failed to enable autostart")
                self.autostart_error_banner.setVisible(True)
                self.autostart_checkbox.blockSignals(True)
                self.autostart_checkbox.setChecked(False)
                self.autostart_checkbox.blockSignals(False)
                self.start_minimized_checkbox.setEnabled(False)
                return
        else:
            success, err = autostart.disable()
            if not success:
                self.autostart_error_banner.set_message(err or "Failed to disable autostart")
                self.autostart_error_banner.setVisible(True)
                self.autostart_checkbox.blockSignals(True)
                self.autostart_checkbox.setChecked(True)
                self.autostart_checkbox.blockSignals(False)
                self.start_minimized_checkbox.setEnabled(True)
                return

        state = autostart.get_state()
        is_active = (state == "enabled")
        self.autostart_checkbox.blockSignals(True)
        self.autostart_checkbox.setChecked(is_active)
        self.autostart_checkbox.blockSignals(False)
        self.start_minimized_checkbox.setEnabled(is_active)
        self.autostart_win_note.setVisible(state == "disabled_by_windows")

    def _on_start_minimized_toggled(self, checked: bool) -> None:
        autostart.set_start_minimized_setting(checked)

    def _on_notif_master_toggled(self, checked: bool) -> None:
        self.notif_manager.settings.enabled = checked
        self.notif_options_container.setVisible(checked)

    def _on_quiet_hours_toggled(self, checked: bool) -> None:
        self.notif_manager.settings.quiet_hours_enabled = checked
        self.quiet_row_widget.setVisible(checked)

    def _on_send_test_notif(self) -> None:
        parent_mw = self.window()
        nm = getattr(parent_mw, "notification_manager", self.notif_manager)
        nm.send_test_notification()

    # -------------------------------------------------------------
    # Content construction
    # -------------------------------------------------------------
    def _build_content(self) -> QWidget:
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, S("space-1"), 0, 0)
        outer.setSpacing(S("space-4"))

        # Hosted server (primary path) — Cloudflare Worker, always on
        hosted = QWidget()
        hoc = QVBoxLayout(hosted)
        hoc.setContentsMargins(0, 0, 0, 0)
        hoc.setSpacing(S("space-2"))

        hoc.addWidget(self._section_title(t("settings.hosted_server_title")))
        hoc.addWidget(self._hint(
            "Runs on Cloudflare at a permanent public URL. Connect ChatGPT once — the connection "
            "keeps working even when this PC is off."
        ))
        hoc.addWidget(self._step_title("Step 1 · Connect ChatGPT (one time)"))
        hoc.addLayout(self._numbered_line(
            "1.",
            "Open chatgpt.com/plugins, click “+”, then “Add custom MCP server”. Custom MCP servers "
            "need a ChatGPT plan that supports them (Plus/Pro).",
        ))
        hoc.addLayout(self._numbered_line("2.", "Give it a name and description — anything you like, for example “RÉSIVO Admin”."))
        hoc.addLayout(self._numbered_line("3.", "Connection — paste the server URL below (it already ends in /mcp)."))
        hoc.addLayout(self._static_url_row(MCP_HOSTED_URL))
        hoc.addLayout(self._numbered_line("4.", "A login page opens once — paste the token below, then click Allow."))
        hoc.addLayout(self._token_row())
        hoc.addWidget(self._hint(
            "The token is pasted once into that login page; ChatGPT stores its own tokens afterwards. "
            "After tool changes (a new deploy), use Refresh on the connection in ChatGPT."
        ))
        hoc.addLayout(self._numbered_line("5.", "Click “I understand and want to continue”, then “Create as a plugin”. Done."))
        outer.addWidget(hosted)

        outer.addWidget(self._divider())

        # Local server (developer/testing only)
        local = QWidget()
        loc = QVBoxLayout(local)
        loc.setContentsMargins(0, 0, 0, 0)
        loc.setSpacing(S("space-2"))

        loc.addWidget(self._section_title(t("settings.local_server_title")))
        loc.addWidget(self._hint(
            "The local Python server uses a bearer token and is meant for the MCP Inspector and other "
            "bearer-capable clients. ChatGPT itself requires the hosted server above."
        ))

        # MCP server status row
        status_row = QHBoxLayout()
        status_row.setSpacing(S("space-2"))
        status_lbl = QLabel("MCP server")
        theme.apply_role(status_lbl, "h3")
        status_row.addWidget(status_lbl)

        self.health_badge = StatusPill("neutral", "Checking…")
        self.health_badge.setToolTip("Health of the local MCP server on port 8000")
        status_row.addWidget(self.health_badge)

        port_lbl = _apply_small(QLabel("port 8000"), word_wrap=False)
        status_row.addWidget(port_lbl)
        status_row.addStretch(1)
        loc.addLayout(status_row)

        loc.addWidget(self._divider())

        # Step 1 — Start the MCP server
        step1 = QWidget()
        s1 = QVBoxLayout(step1)
        s1.setContentsMargins(0, 0, 0, 0)
        s1.setSpacing(S("space-2"))
        s1.addWidget(self._step_title(t("settings.local_step1_title")))
        repo_root = _application_root()
        s1.addWidget(self._command_box(f'cd "{repo_root}"; & "mcp\\.venv\\Scripts\\python.exe" "mcp\\server.py"'))
        s1.addWidget(self._hint("Paste into any PowerShell window and leave it open while a testing client is connected. The badge above turns green once the server is running."))
        loc.addWidget(step1)

        # Step 2 — Optional: expose the local server with a tunnel
        step2 = QWidget()
        s2 = QVBoxLayout(step2)
        s2.setContentsMargins(0, 0, 0, 0)
        s2.setSpacing(S("space-2"))
        s2.addWidget(self._step_title(t("settings.local_step2_title")))
        s2.addWidget(self._command_box("wrangler tunnel quick-start http://localhost:8000"))
        hint2 = self._hint(
            'A public https://… URL is printed in that terminal — leave it open while testing. Alternatives: '
            '<span style="font-family: %s;">cloudflared tunnel --url http://localhost:8000</span> or '
            '<span style="font-family: %s;">ngrok http 8000</span>.' % (_mono_family() or "monospace", _mono_family() or "monospace")
        )
        hint2.setTextFormat(Qt.TextFormat.RichText)
        s2.addWidget(hint2)
        s2.addLayout(self._composer_row())
        loc.addWidget(step2)

        # Step 3 — Connect with the MCP Inspector
        step3 = QWidget()
        s3 = QVBoxLayout(step3)
        s3.setContentsMargins(0, 0, 0, 0)
        s3.setSpacing(S("space-2"))
        s3.addWidget(self._step_title(t("settings.local_step3_title")))
        s3.addWidget(self._command_box("npx @modelcontextprotocol/inspector"))
        s3.addWidget(self._hint(
            "Choose transport Streamable HTTP and URL http://localhost:8000/mcp, then add the custom "
            "header Authorization: Bearer <token> — copy the token from the row above."
        ))
        loc.addWidget(step3)

        outer.addWidget(local)

        outer.addWidget(self._divider())
        footer = QLabel(
            "Admin-only. ChatGPT can read data, and — when you allow it here — make changes: it asks "
            "you to confirm every change first, and every action is logged. Full guides: "
            "mcp-worker/README.md (hosted) and mcp/README.md (local)."
        )
        _apply_small(footer)
        outer.addWidget(footer)

        return content

    def _build_about(self) -> QWidget:
        """About card — brand, creator credit, and links. Always visible, never role-gated."""
        about = Card(t("settings.about_title"), t("settings.about_subtitle"), icon="info")
        about.setObjectName("aboutSection")
        about_layout = about.body

        about_row = QHBoxLayout()
        about_row.setSpacing(S("space-4"))

        about_logo = QLabel()
        about_logo.setObjectName("aboutLogo")
        logo_path = get_asset_path("brand/resivo_logo.png")
        about_logo_px = QPixmap(str(logo_path))
        about_logo.setPixmap(about_logo_px.scaled(
            S("space-12") * 2, S("space-12") * 2,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        about_logo.setAlignment(Qt.AlignmentFlag.AlignTop)
        about_row.addWidget(about_logo)

        about_text = QVBoxLayout()
        about_text.setSpacing(S("space-1"))
        created = QLabel(t("settings.about_created_by"))
        theme.apply_role(created, "h3")
        about_text.addWidget(created)

        github_lbl = QLabel(
            f'<a href="https://github.com/anesdevv" style="color: {C("teal-600")};">GitHub: github.com/anesdevv</a>'
        )
        github_lbl.setObjectName("aboutGithubLink")
        github_lbl.setTextFormat(Qt.TextFormat.RichText)
        github_lbl.setOpenExternalLinks(True)
        about_text.addWidget(github_lbl)

        email_lbl = QLabel(
            f'<a href="mailto:anes4tlm@gmail.com" style="color: {C("teal-600")};">Email: anes4tlm@gmail.com</a>'
        )
        email_lbl.setObjectName("aboutEmailLink")
        email_lbl.setTextFormat(Qt.TextFormat.RichText)
        email_lbl.setOpenExternalLinks(True)
        about_text.addWidget(email_lbl)

        about_text.addStretch(1)
        about_row.addLayout(about_text, 1)
        about_layout.addLayout(about_row)
        return about

    def _divider(self) -> QFrame:
        div = QFrame()
        div.setFixedHeight(1)
        div.setProperty("role", "separator")
        div.setStyleSheet(f"background-color: {C('border')}; border: none;")
        return div

    def _section_title(self, text: str) -> QLabel:
        """Uppercase section overline (DESIGN.md §3)."""
        lbl = QLabel(str(text).upper())
        theme.apply_role(lbl, "overline")
        return lbl

    def _step_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        theme.apply_role(lbl, "h3")
        return lbl

    def _hint(self, text: str) -> QLabel:
        lbl = QLabel(text)
        _apply_small(lbl)
        return lbl

    def _command_box(self, command: str) -> QFrame:
        box = QFrame()
        box.setObjectName("commandBox")
        box.setStyleSheet(_flat_box_qss("commandBox"))
        row = QHBoxLayout(box)
        row.setContentsMargins(S("space-3"), S("space-3"), S("space-3"), S("space-3"))
        row.setSpacing(S("space-2"))

        cmd_lbl = QLabel(command)
        cmd_lbl.setStyleSheet(_mono_qss())
        cmd_lbl.setWordWrap(True)
        cmd_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(cmd_lbl, 1)
        row.addWidget(self._copy_button(lambda: command), 0, Qt.AlignmentFlag.AlignTop)
        return box

    def _numbered_line(self, number: str, text: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(S("space-2"))
        num_lbl = QLabel(number)
        theme.apply_role(num_lbl, "small")
        num_lbl.setStyleSheet(f"color: {C('text-muted')};")
        num_lbl.setFixedWidth(S("space-4"))
        num_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
        row.addWidget(num_lbl)
        text_lbl = QLabel(text)
        _apply_small(text_lbl)
        row.addWidget(text_lbl, 1)
        return row

    def _composer_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(S("space-4"), 0, 0, 0)
        row.setSpacing(S("space-2"))

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://xxxx.trycloudflare.com")
        self.url_input.setToolTip("Paste the public tunnel URL printed by wrangler / cloudflared / ngrok")
        self.url_input.textChanged.connect(self._on_url_input_changed)
        row.addWidget(self.url_input, 1)

        self.url_output = QLineEdit()
        self.url_output.setReadOnly(True)
        self.url_output.setToolTip("Normalized MCP server URL to paste into ChatGPT")
        row.addWidget(self.url_output, 1)

        row.addWidget(self._copy_button(lambda: self.url_output.text()))
        return row

    def _static_url_row(self, url: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(S("space-4"), 0, 0, 0)
        row.setSpacing(S("space-2"))

        url_label = QLineEdit(url)
        url_label.setReadOnly(True)
        url_label.setToolTip("Hosted MCP server URL (already ends in /mcp)")
        row.addWidget(url_label, 1)

        row.addWidget(self._copy_button(lambda: url))
        return row

    def _token_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(S("space-4"), 0, 0, 0)
        row.setSpacing(S("space-2"))

        self.token_label = QLabel("")
        self.token_label.setStyleSheet(_token_qss())
        self.token_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self.token_label, 1)

        self.reveal_btn = Button.secondary(t("common.reveal") if t("common.reveal") != "common.reveal" else "Reveal")
        self.reveal_btn.setToolTip("Show or hide the MCP bearer token")
        self.reveal_btn.clicked.connect(self._on_reveal_clicked)
        row.addWidget(self.reveal_btn)

        self.token_copy_btn = Button.secondary(t("common.copy") if t("common.copy") != "common.copy" else "Copy")
        self.token_copy_btn.setToolTip("Copy the MCP bearer token to the clipboard")
        self.token_copy_btn.clicked.connect(self._on_copy_token)
        row.addWidget(self.token_copy_btn)
        return row

    # -------------------------------------------------------------
    # Behavior
    # -------------------------------------------------------------
    def reload(self):
        """Refresh the token row and the writes off-switch."""
        if self.role != "admin":
            self._token = ""
            self._render_token_row()
            return
        if self._initializing:
            self._apply_settings(self._fetch_settings())
            return
        self._reload_async()

    def _fetch_settings(self) -> dict:
        """Token + writes off-switch gathered off the GUI thread."""
        token = _read_mcp_token()
        if self.role != "admin":
            return {"token": "", "writes_ok": False, "writes_enabled": False, "error": None}
        try:
            resp = self.client.rpc("mcp_get_settings", {}).execute()
            enabled = bool((resp.data or {}).get("writes_enabled", False))
        except Exception as exc:  # noqa: BLE001 - fail-safe state below
            return {
                "token": token,
                "writes_ok": False,
                "writes_enabled": False,
                "error": human_error(exc),
            }
        return {"token": token, "writes_ok": True, "writes_enabled": enabled, "error": None}

    def _reload_async(self) -> None:
        if self._settings_loading or self.tasks.is_busy(_LOAD_KEY):
            return
        self._settings_loading = True
        self.writes_checkbox.setEnabled(False)
        self.writes_note.setText(_WORKING_TEXT)
        self.token_label.setStyleSheet(_hint_qss())
        self.token_label.setText("Loading token…")
        self.reveal_btn.setVisible(False)
        self.token_copy_btn.setVisible(False)
        started = self.tasks.run(
            _LOAD_KEY,
            self._fetch_settings,
            on_success=self._apply_settings,
            on_failed=self._on_settings_failed,
            on_finished=self._on_settings_finished,
        )
        if not started:
            self._on_settings_finished()

    def _on_settings_finished(self) -> None:
        self._settings_loading = False
        if self.role != "admin":
            return
        self.writes_checkbox.setEnabled(self._writes_available and not self._writes_saving)
        if self._writes_available:
            self.writes_note.setText(_writes_note())
            self.writes_checkbox.setToolTip(_writes_tooltip())
        else:
            self.writes_note.setText("Could not load this setting — check the connection.")
            self.writes_checkbox.setToolTip("Disabled until the setting can be loaded")

    def _on_settings_failed(self, message: str) -> None:
        self._writes_available = False
        self.writes_note.setText("Could not load this setting — check the connection.")
        self.writes_banner.set_message(
            f"The ChatGPT writes switch stays disabled until this setting can be read again ({message}). "
            "Check the connection, then reopen Settings to retry."
        )
        self.writes_banner.setVisible(True)
        self._render_token_row()

    def _apply_settings(self, result: dict) -> None:
        """Render a fetched settings snapshot on the GUI thread."""
        self._token = str(result.get("token") or "")
        self._render_token_row()
        self._writes_available = bool(result.get("writes_ok"))
        if self.role != "admin":
            return
        if result.get("residence"):
            self._apply_residence_snapshot(result.get("residence"))
        if self._writes_available:
            self.writes_note.setText(_writes_note())
            self.writes_banner.setVisible(False)
        else:
            self.writes_note.setText("Could not load this setting — check the connection.")
            self.writes_banner.set_message(
                "The ChatGPT writes switch stays disabled until this setting can be read again. "
                "Check the connection, then reopen Settings to retry."
            )
            self.writes_banner.setVisible(True)
        self._writes_loading = True
        try:
            self.writes_checkbox.blockSignals(True)
            self.writes_checkbox.setChecked(bool(result.get("writes_enabled")))
        finally:
            self.writes_checkbox.blockSignals(False)
            self._writes_loading = False
        self.writes_checkbox.setEnabled(self._writes_available)
        self.writes_checkbox.setToolTip(
            "Disabled until the setting can be loaded" if not self._writes_available
            else _writes_tooltip()
        )

    def _on_writes_toggled(self, checked: bool):
        if self._writes_loading or self._writes_saving or self.role != "admin":
            return
        if self._settings_loading or not self._writes_available:
            return
        if self.tasks.is_busy(_WRITES_KEY):
            return
        self._writes_saving = True
        self.writes_checkbox.setEnabled(False)
        self.writes_note.setText(_WORKING_TEXT)
        self.writes_checkbox.setToolTip("Saving the setting…")
        started = self.tasks.run(
            _WRITES_KEY,
            lambda: self.client.rpc("mcp_set_writes_enabled", {"p_enabled": checked}).execute(),
            on_success=lambda _result: self._on_writes_saved(),
            on_failed=lambda message: self._on_writes_failed(checked, message),
            on_finished=self._on_writes_finished,
        )
        if not started:
            self._on_writes_finished()

    def _on_writes_saved(self) -> None:
        self.writes_banner.setVisible(False)

    def _on_writes_failed(self, checked: bool, message: str) -> None:
        # DB is the source of truth — revert the UI and tell the admin.
        self._writes_loading = True
        try:
            self.writes_checkbox.blockSignals(True)
            self.writes_checkbox.setChecked(not checked)
        finally:
            self.writes_checkbox.blockSignals(False)
            self._writes_loading = False
        self.writes_note.setText(_writes_note())
        self.writes_banner.set_message(f"The switch was reverted: {message}")
        self.writes_banner.setVisible(True)
        QMessageBox.warning(self, "Settings", f"Could not save the setting: {message}")

    def _on_writes_finished(self) -> None:
        self._writes_saving = False
        if self.role != "admin":
            return
        self.writes_checkbox.setEnabled(self._writes_available)
        self.writes_checkbox.setToolTip(
            _writes_tooltip() if self._writes_available else "Disabled until the setting can be loaded"
        )
        if self._writes_available:
            self.writes_note.setText(_writes_note())

    def _on_dev_mode_toggled(self, checked: bool):
        if self.role != "admin":
            return
        self.enable_note.setVisible(not checked)
        self.content.setVisible(checked)

    def _on_health_changed(self, up: bool):
        if up:
            self.health_badge.set_kind("ok", "Running")
        else:
            self.health_badge.set_kind("danger", "Offline")

    def _on_url_input_changed(self, text: str):
        self.url_output.setText(build_mcp_url(text))

    def _on_reveal_clicked(self):
        if self.role != "admin":
            return
        self._token_revealed = not self._token_revealed
        self._update_token_display()

    def _on_copy_token(self):
        if self.role != "admin":
            return
        self._copy_to_clipboard(self.token_copy_btn, self._token)

    def _render_token_row(self):
        has_token = bool(self._token)
        self.reveal_btn.setVisible(has_token)
        self.token_copy_btn.setVisible(has_token)
        if not has_token:
            self.token_label.setStyleSheet(_hint_qss())
            self.token_label.setText("Token not found — check mcp/.env.")
            return
        self.token_label.setStyleSheet(_token_qss())
        self._update_token_display()

    def _update_token_display(self):
        hide_text = t("common.hide") if t("common.hide") != "common.hide" else "Hide"
        reveal_text = t("common.reveal") if t("common.reveal") != "common.reveal" else "Reveal"
        if self._token_revealed:
            self.token_label.setText(self._token)
            self.reveal_btn.setText(hide_text)
        else:
            self.token_label.setText("•" * 12 + self._token[-4:])
            self.reveal_btn.setText(reveal_text)

    def _copy_button(self, text_getter):
        """Small secondary Copy button bound to a text getter."""
        btn_text = t("common.copy") if t("common.copy") != "common.copy" else "Copy"
        btn = Button(btn_text, "secondary", size="sm")
        btn.setToolTip("Copy to the clipboard")
        btn.clicked.connect(lambda: self._copy_to_clipboard(btn, text_getter()))
        return btn

    def _copy_to_clipboard(self, btn, text: str):
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        copied_text = t("common.copied") if t("common.copied") != "common.copied" else "Copied"
        copy_text = t("common.copy") if t("common.copy") != "common.copy" else "Copy"
        btn.setText(copied_text)
        QTimer.singleShot(1500, lambda: self._restore_button_text(btn, copy_text))

    def _restore_button_text(self, btn, text: str):
        try:
            btn.setText(text)
        except RuntimeError:
            pass

    # -------------------------------------------------------------
    # Single-gender residence settings (admin only)
    # -------------------------------------------------------------
    def _load_residence_sync(self) -> None:
        if self.role != "admin":
            return
        try:
            res = fetch_residence_settings_admin(self.client)
            if isinstance(res, dict) and res.get("loaded"):
                self._apply_residence_snapshot(res)
        except Exception:  # noqa: BLE001
            pass

    def reload_residence(self) -> None:
        if self.role != "admin" or self._residence_saving:
            return
        if self.tasks.is_busy("settings-residence-load"):
            return
        self.tasks.run(
            "settings-residence-load",
            lambda: fetch_residence_settings_admin(self.client),
            on_success=self._apply_residence_snapshot,
            on_failed=lambda _msg: None,
        )

    def _set_combo_residence_gender(self, value: str | None) -> None:
        self._residence_loading = True
        try:
            self.residence_type_combo.blockSignals(True)
            target_idx = 0
            for i in range(self.residence_type_combo.count()):
                if self.residence_type_combo.itemData(i) == value:
                    target_idx = i
                    break
            self.residence_type_combo.setCurrentIndex(target_idx)
        finally:
            self.residence_type_combo.blockSignals(False)
            self._residence_loading = False

    def _apply_residence_snapshot(self, res: dict | None) -> None:
        if not isinstance(res, dict):
            return
        name = str(res.get("residence_name") or DEFAULT_RESIDENCE_NAME).strip() or DEFAULT_RESIDENCE_NAME
        gender = res.get("residence_gender")
        self._current_residence_name = name
        self._current_residence_gender = gender if gender in ("male", "female") else None
        self.residence_name_edit.setText(name)
        self._set_combo_residence_gender(self._current_residence_gender)

        changed_at = res.get("last_changed_at")
        if changed_at:
            actor = str(res.get("last_changed_by_name") or t("roles.admin")).strip()
            try:
                date_str = format_date(str(changed_at))
            except Exception:
                date_str = str(changed_at)[:10]
            self.residence_audit_label.setText(
                t("settings.residence_last_changed", name=actor, date=date_str)
            )
        else:
            self.residence_audit_label.setText(t("settings.residence_never_changed"))

    def _set_residence_busy(self, busy: bool, status_text: str | None = None) -> None:
        self._residence_saving = busy
        self.residence_type_combo.setEnabled(not busy)
        self.residence_name_edit.setEnabled(not busy)
        self.residence_name_save_btn.setEnabled(not busy)
        if busy and status_text:
            self.residence_banner.set_kind("info")
            self.residence_banner.set_title(_WORKING_TEXT)
            self.residence_banner.set_message(status_text)
            self.residence_banner.setVisible(True)

    def _on_residence_name_save(self) -> None:
        if self.role != "admin" or self._residence_saving:
            return
        if self.tasks.is_busy(_RESIDENCE_NAME_KEY):
            return
        name = self.residence_name_edit.text().strip()
        if not name:
            self.residence_banner.set_kind("error")
            self.residence_banner.set_title(t("settings.residence_error_title"))
            self.residence_banner.set_message(t("settings.residence_name_required"))
            self.residence_banner.setVisible(True)
            return

        self._set_residence_busy(True, t("settings.residence_saving"))
        started = self.tasks.run(
            _RESIDENCE_NAME_KEY,
            lambda: set_residence_name(self.client, name),
            on_success=self._on_residence_name_saved,
            on_failed=self._on_residence_name_failed,
            on_finished=self._on_residence_name_finished,
        )
        if not started:
            self._set_residence_busy(False)

    def _on_residence_name_saved(self, payload: dict) -> None:
        self._current_residence_name = str(
            (payload or {}).get("residence_name") or self.residence_name_edit.text().strip()
        )
        self.residence_name_edit.setText(self._current_residence_name)
        self.residence_banner.set_kind("success")
        self.residence_banner.set_title(t("settings.residence_title"))
        self.residence_banner.set_message(t("settings.residence_name_saved"))
        self.residence_banner.setVisible(True)
        self.residence_settings_changed.emit()

    def _on_residence_name_failed(self, message: str) -> None:
        self.residence_name_edit.setText(self._current_residence_name)
        self.residence_banner.set_kind("error")
        self.residence_banner.set_title(t("settings.residence_error_title"))
        self.residence_banner.set_message(message)
        self.residence_banner.setVisible(True)

    def _on_residence_name_finished(self) -> None:
        if not self.tasks.is_busy(_RESIDENCE_SAVE_KEY):
            self._set_residence_busy(False)

    def _on_residence_type_selected(self, index: int) -> None:
        if self._residence_loading or self._residence_saving or self.role != "admin":
            return
        if self.tasks.is_busy(_RESIDENCE_IMPACT_KEY) or self.tasks.is_busy(_RESIDENCE_SAVE_KEY):
            self._set_combo_residence_gender(self._current_residence_gender)
            return

        target = self.residence_type_combo.itemData(index)
        if target not in ("male", "female"):
            self._set_combo_residence_gender(self._current_residence_gender)
            return
        if target == self._current_residence_gender:
            return

        self.residence_banner.setVisible(False)
        self._set_residence_busy(True, t("settings.residence_checking"))
        started = self.tasks.run(
            _RESIDENCE_IMPACT_KEY,
            lambda: fetch_residence_gender_impact(self.client, target),
            on_success=lambda impact: self._on_residence_impact_loaded(target, impact),
            on_failed=self._on_residence_gender_failed,
            on_finished=self._on_residence_impact_finished,
        )
        if not started:
            self._set_residence_busy(False)
            self._set_combo_residence_gender(self._current_residence_gender)

    def _on_residence_impact_finished(self) -> None:
        if not self.tasks.is_busy(_RESIDENCE_SAVE_KEY):
            self._set_residence_busy(False)

    def _on_residence_impact_loaded(self, target_gender: str, impact: dict) -> None:
        self._set_residence_busy(False)
        self.residence_banner.setVisible(False)
        needs_confirmation = bool((impact or {}).get("needs_confirmation"))

        if needs_confirmation:
            dlg = ResidenceGenderChangeDialog(self, impact, target_gender)
            accepted = dlg.exec() == QDialog.DialogCode.Accepted and dlg.confirmed
            confirmation_token: str | None = "CHANGE"
        else:
            accepted = ConfirmDialog.ask(
                self,
                t("settings.residence_simple_confirm_title"),
                t(
                    "settings.residence_simple_confirm_body",
                    target=residence_gender_label(target_gender),
                ),
                confirm_text=t("settings.residence_simple_confirm_btn"),
                danger=False,
            )
            confirmation_token = None

        if not accepted:
            self._set_combo_residence_gender(self._current_residence_gender)
            return

        self._submit_residence_gender_change(target_gender, confirmation_token)

    def _submit_residence_gender_change(
        self,
        target_gender: str,
        confirmation_token: str | None,
    ) -> None:
        self._set_residence_busy(True, t("settings.residence_saving"))

        def work():
            res = set_residence_gender(self.client, target_gender, confirmation=confirmation_token)
            try:
                admin_snap = fetch_residence_settings_admin(self.client)
            except Exception:
                admin_snap = None
            return res, admin_snap

        started = self.tasks.run(
            _RESIDENCE_SAVE_KEY,
            work,
            on_success=lambda out: self._on_residence_gender_saved(target_gender, out),
            on_failed=self._on_residence_gender_failed,
            on_finished=self._on_residence_save_finished,
        )
        if not started:
            self._set_residence_busy(False)
            self._set_combo_residence_gender(self._current_residence_gender)

    def _on_residence_gender_saved(self, target_gender: str, out) -> None:
        _res, admin_snap = out if isinstance(out, tuple) else (out, None)
        self._current_residence_gender = target_gender
        if isinstance(admin_snap, dict) and admin_snap.get("loaded"):
            self._apply_residence_snapshot(admin_snap)
        else:
            self._set_combo_residence_gender(target_gender)
            actor = stored_user_email(self.client) or t("roles.admin")
            from datetime import date
            self.residence_audit_label.setText(
                t("settings.residence_last_changed", name=actor, date=format_date(date.today().isoformat()))
            )
        self.residence_banner.set_kind("success")
        self.residence_banner.set_title(t("settings.residence_title"))
        self.residence_banner.set_message(
            t("settings.residence_changed_success", value=residence_gender_label(target_gender))
        )
        self.residence_banner.setVisible(True)
        self.residence_settings_changed.emit()

    def _on_residence_gender_failed(self, message: str) -> None:
        self._set_combo_residence_gender(self._current_residence_gender)
        self.residence_banner.set_kind("error")
        self.residence_banner.set_title(t("settings.residence_error_title"))
        self.residence_banner.set_message(message)
        self.residence_banner.setVisible(True)

    def _on_residence_save_finished(self) -> None:
        self._set_residence_busy(False)
