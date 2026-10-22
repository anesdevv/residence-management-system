"""RÉSIVO — About & Diagnostics dialog.

Read-only support screen: application version, Supabase host (never the URL
path or any key), live-sync status, the signed-in session and the log location.
No network calls are made here.
"""

from __future__ import annotations

from urllib.parse import urlparse

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout

from .. import config
from ..client import stored_user_email
from ..logging_setup import log_path
from . import theme
from .components import Button, Card, KeyValueList
from .theme import DESKTOP_STYLESHEET, S

_ROLE_LABELS = {"admin": "Administrator", "staff": "Housing staff"}

# Module-level aliases keep the diagnostics patch point available to tests
# (``diagnostics.SUPABASE_URL``); the live value still follows ``config`` when
# these were not overridden.
_BOOTSTRAP_URL = config.SUPABASE_URL
SUPABASE_URL = config.SUPABASE_URL
SUPABASE_ANON_KEY = config.SUPABASE_ANON_KEY  # never displayed


def _session_email(client) -> str:
    """Email from the stored session only (no network call)."""
    if client is None:
        return ""
    return stored_user_email(client)


def _supabase_host() -> str:
    """Host only: no path, query string or key material."""
    url = SUPABASE_URL
    if url == _BOOTSTRAP_URL:
        url = config.SUPABASE_URL
    try:
        host = urlparse((url or "").strip()).netloc
    except Exception:
        host = ""
    return host or "Not configured"


def _role_text(role) -> str:
    normalized = str(role).strip().lower() if role is not None else ""
    if not normalized:
        return "Role not verified"
    label = _ROLE_LABELS.get(normalized, normalized.title())
    return f"{label} ({normalized})"


class DiagnosticsDialog(QDialog):
    """``DiagnosticsDialog(parent, client=..., email=..., role=..., connection_status=...)``."""

    def __init__(
        self,
        parent=None,
        client=None,
        email: str | None = None,
        role=None,
        connection_status: str | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("diagnosticsDialog")
        self.setWindowTitle("About & Diagnostics")
        self.setMinimumWidth(520)
        self.setModal(True)
        self.setStyleSheet(DESKTOP_STYLESHEET)

        email = _session_email(client) if email is None else str(email or "")
        self.info = {
            "Application": "RÉSIVO",
            "Version": config.APP_VERSION,
            "Supabase host": _supabase_host(),
            "Connection": connection_status or "Unknown",
            "Signed-in email": email or "Not signed in",
            "Effective role": _role_text(role),
            "Log file": str(log_path()),
        }

        root = QVBoxLayout(self)
        root.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        root.setSpacing(S("space-4"))

        title = QLabel("About & Diagnostics")
        theme.apply_role(title, "h1")
        subtitle = QLabel(
            "Support information for this installation. No credentials or keys are shown."
        )
        theme.apply_role(subtitle, "muted")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        card = Card("Application", "Version, connection and session", icon="info")
        self.rows = KeyValueList()
        for label, value in self.info.items():
            self.rows.add_row(label, value)
        card.add_widget(self.rows)
        root.addWidget(card)

        buttons = QHBoxLayout()
        buttons.setSpacing(S("space-2"))
        self.open_log_btn = Button.secondary("Open log folder")
        self.open_log_btn.setObjectName("openLogFolderButton")
        self.open_log_btn.clicked.connect(self.open_log_folder)
        buttons.addWidget(self.open_log_btn)
        buttons.addStretch(1)

        self.close_btn = Button.primary("Close")
        self.close_btn.setObjectName("closeDiagnosticsButton")
        self.close_btn.clicked.connect(self.accept)
        buttons.addWidget(self.close_btn)
        root.addLayout(buttons)

    def open_log_folder(self) -> None:
        """Open the directory of the active rotating log in the file manager.

        The configured folder can be unwritable, in which case logging falls
        back to the temp directory; this follows the path actually in use.
        """
        path = log_path().parent
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
