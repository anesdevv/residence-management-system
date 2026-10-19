"""RÉSIVO — Settings (visual layer only, docs/DESIGN.md §6–§7).

Cards, section overlines, token-built checkbox styling, a ``StatusPill`` health
badge, a monospace token box and flat command boxes. Everything behavioural is
unchanged: ``McpHealthWorker`` (class name, ``start()`` / ``stop()``, the local
health URL, the 5 s interval and its up/down transition signalling), the writes
off-switch RPCs (``mcp_get_settings`` / ``mcp_set_writes_enabled``) with their
fail-safe revert, the admin-only role gating, and the MCP token read / reveal /
copy flow.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QFontDatabase, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...client import current_role
from .. import theme
from ..components import Button, Card, InlineBanner, PageHeader, StatusPill
from ..theme import C, S


MCP_HEALTH_URL = "http://127.0.0.1:8000/health"
MCP_HEALTH_TIMEOUT_S = 2.0
MCP_HEALTH_INTERVAL_MS = 5000
MCP_HOSTED_URL = "https://resivo-mcp.anes4tlm.workers.dev/mcp"

_WRITES_NOTE = (
    "ChatGPT asks you to confirm every change first. "
    "Turn this off to make ChatGPT read-only again."
)


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


def _read_mcp_token() -> str:
    """Read MCP_AUTH_TOKEN from <repo-root>/mcp/.env. The value is never logged."""
    env_path = Path(__file__).resolve().parents[4] / "mcp" / ".env"
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("MCP_AUTH_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        return ""
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
                with urllib.request.urlopen(self.url, timeout=self.timeout_s) as resp:
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


class SettingsPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.role = current_role(client)
        self._token = ""
        self._token_revealed = False
        self._writes_loading = False

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
            "Settings",
            "Console preferences and administrative integrations.",
        )
        layout.addWidget(self.header)

        # Advanced settings (developer mode) card
        self.dev_card = Card(
            "Advanced settings",
            "Developer mode and the ChatGPT connection",
            icon="settings",
        )

        self.dev_checkbox = QCheckBox("Developer mode")
        self.dev_checkbox.setStyleSheet(_checkbox_qss())
        self.dev_checkbox.setToolTip("Show the ChatGPT connection steps for this session")
        self.dev_checkbox.toggled.connect(self._on_dev_mode_toggled)
        self.dev_card.add_widget(self.dev_checkbox)

        self.staff_note = QLabel("Developer mode is available to administrators only.")
        _apply_small(self.staff_note)
        self.dev_card.add_widget(self.staff_note)

        self.enable_note = QLabel("Enable developer mode to view the ChatGPT connection steps.")
        _apply_small(self.enable_note)
        self.dev_card.add_widget(self.enable_note)

        # ChatGPT write off-switch — admin only, outside the developer-mode gate
        self.writes_checkbox = QCheckBox("Allow ChatGPT to change data")
        self.writes_checkbox.setStyleSheet(_checkbox_qss())
        self.writes_checkbox.setToolTip("Allow the ChatGPT connection to change data after your confirmation")
        self.writes_checkbox.toggled.connect(self._on_writes_toggled)
        self.dev_card.add_widget(self.writes_checkbox)

        self.writes_note = QLabel(_WRITES_NOTE)
        _apply_small(self.writes_note)
        self.dev_card.add_widget(self.writes_note)

        self.writes_banner = InlineBanner(
            "error",
            title="Setting could not be loaded",
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

        # Role gating — developer mode is session-only, never persisted
        if self.role == "admin":
            self.staff_note.setVisible(False)
        else:
            self.dev_checkbox.setEnabled(False)
            self.dev_checkbox.setToolTip("Developer mode is available to administrators only.")
            self.enable_note.setVisible(False)
        self.writes_checkbox.setVisible(self.role == "admin")
        self.writes_note.setVisible(self.role == "admin")
        self.writes_checkbox.setEnabled(False)  # enabled once the setting loads
        self.content.setVisible(False)

        # Background health poller (admins only)
        self.health_worker = McpHealthWorker()
        self.health_worker.health_changed.connect(self._on_health_changed)
        if self.role == "admin":
            self.health_worker.start()

        self.reload()

    # -------------------------------------------------------------
    # Content construction
    # -------------------------------------------------------------
    def _build_content(self) -> QWidget:
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, S("space-1"), 0, 0)
        outer.setSpacing(S("space-4"))

        # -----------------------------------------------------------------
        # Hosted server (primary path) — Cloudflare Worker, always on
        # -----------------------------------------------------------------
        hosted = QWidget()
        hoc = QVBoxLayout(hosted)
        hoc.setContentsMargins(0, 0, 0, 0)
        hoc.setSpacing(S("space-2"))

        hoc.addWidget(self._section_title("Hosted server (always on, recommended)"))
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

        # -----------------------------------------------------------------
        # Local server (developer/testing only)
        # -----------------------------------------------------------------
        local = QWidget()
        loc = QVBoxLayout(local)
        loc.setContentsMargins(0, 0, 0, 0)
        loc.setSpacing(S("space-2"))

        loc.addWidget(self._section_title("Run it locally (developer/testing only)"))
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
        s1.addWidget(self._step_title("Step 1 · Start the MCP server"))
        repo_root = Path(__file__).resolve().parents[4]
        s1.addWidget(self._command_box(f'cd "{repo_root}"; & "mcp\\.venv\\Scripts\\python.exe" "mcp\\server.py"'))
        s1.addWidget(self._hint("Paste into any PowerShell window and leave it open while a testing client is connected. The badge above turns green once the server is running."))
        loc.addWidget(step1)

        # Step 2 — Optional: expose the local server with a tunnel
        step2 = QWidget()
        s2 = QVBoxLayout(step2)
        s2.setContentsMargins(0, 0, 0, 0)
        s2.setSpacing(S("space-2"))
        s2.addWidget(self._step_title("Step 2 · Expose it with a tunnel (optional)"))
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
        s3.addWidget(self._step_title("Step 3 · Connect with the MCP Inspector"))
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
        about = Card("About RÉSIVO", "Project credit and contact links", icon="info")
        about.setObjectName("aboutSection")
        about_layout = about.body

        about_row = QHBoxLayout()
        about_row.setSpacing(S("space-4"))

        about_logo = QLabel()
        about_logo.setObjectName("aboutLogo")
        logo_path = Path(__file__).resolve().parents[3] / "assets" / "brand" / "resivo_logo.png"
        if not logo_path.is_file():
            logo_path = Path(__file__).parent.parent / "assets" / "resivo_logo.png"
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
        created = QLabel("Created by SEBAI ANES")
        theme.apply_role(created, "h3")
        about_text.addWidget(created)

        # External links open in the OS browser/mail client (QLabel delegates to QDesktopServices.openUrl)
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

        self.reveal_btn = Button.secondary("Reveal")
        self.reveal_btn.setToolTip("Show or hide the MCP bearer token")
        self.reveal_btn.clicked.connect(self._on_reveal_clicked)
        row.addWidget(self.reveal_btn)

        self.token_copy_btn = Button.secondary("Copy")
        self.token_copy_btn.setToolTip("Copy the MCP bearer token to the clipboard")
        self.token_copy_btn.clicked.connect(self._on_copy_token)
        row.addWidget(self.token_copy_btn)
        return row

    # -------------------------------------------------------------
    # Behavior
    # -------------------------------------------------------------
    def reload(self):
        """Refresh the token row (mcp/.env is re-read on demand) and the writes off-switch."""
        if self.role == "admin":
            self._token = _read_mcp_token()
        else:
            self._token = ""
        self._render_token_row()
        self._load_writes_setting()

    def _load_writes_setting(self):
        """Read the ChatGPT off-switch from the DB. Failure leaves the checkbox disabled (fail-safe)."""
        if self.role != "admin":
            return
        self.writes_checkbox.setEnabled(False)  # no interaction while loading
        ok = True
        try:
            resp = self.client.rpc("mcp_get_settings", {}).execute()
            writes_enabled = bool((resp.data or {}).get("writes_enabled", False))
        except Exception:  # noqa: BLE001
            # Fail-safe: never show a state we could not verify.
            ok = False
            writes_enabled = False
            self.writes_note.setText("Could not load this setting — check the connection.")
            self.writes_banner.set_message(
                "The ChatGPT writes switch stays disabled until this setting can be read again. "
                "Check the connection, then reopen Settings to retry."
            )
            self.writes_banner.setVisible(True)
        else:
            self.writes_note.setText(_WRITES_NOTE)
            self.writes_banner.setVisible(False)
        self._writes_loading = True
        try:
            self.writes_checkbox.blockSignals(True)
            self.writes_checkbox.setChecked(writes_enabled)
        finally:
            self.writes_checkbox.blockSignals(False)
            self._writes_loading = False
        self.writes_checkbox.setEnabled(ok)
        self.writes_checkbox.setToolTip(
            "Disabled until the setting can be loaded" if not ok else
            "Allow the ChatGPT connection to change data after your confirmation"
        )

    def _on_writes_toggled(self, checked: bool):
        if self._writes_loading or self.role != "admin":
            return
        try:
            self.client.rpc("mcp_set_writes_enabled", {"p_enabled": checked}).execute()
        except Exception as exc:  # noqa: BLE001
            # DB is the source of truth — revert the UI and tell the admin.
            self.writes_checkbox.blockSignals(True)
            self.writes_checkbox.setChecked(not checked)
            self.writes_checkbox.blockSignals(False)
            self.writes_banner.set_message(f"The switch was reverted: {exc}")
            self.writes_banner.setVisible(True)
            QMessageBox.warning(self, "Settings", f"Could not save the setting: {exc}")
        else:
            self.writes_banner.setVisible(False)

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
        # Defense in depth: re-check the live role before showing the secret
        if current_role(self.client) != "admin":
            return
        self._token_revealed = not self._token_revealed
        self._update_token_display()

    def _on_copy_token(self):
        # Defense in depth: re-check the live role before copying the secret
        if current_role(self.client) != "admin":
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
        if self._token_revealed:
            self.token_label.setText(self._token)
            self.reveal_btn.setText("Hide")
        else:
            self.token_label.setText("•" * 12 + self._token[-4:])
            self.reveal_btn.setText("Reveal")

    def _copy_button(self, text_getter):
        """Small secondary Copy button bound to a text getter."""
        btn = Button("Copy", "secondary", size="sm")
        btn.setToolTip("Copy to the clipboard")
        btn.clicked.connect(lambda: self._copy_to_clipboard(btn, text_getter()))
        return btn

    def _copy_to_clipboard(self, btn, text: str):
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        btn.setText("Copied")
        QTimer.singleShot(1500, lambda: self._restore_button_text(btn, "Copy"))

    def _restore_button_text(self, btn, text: str):
        try:
            btn.setText(text)
        except RuntimeError:
            # Widget already destroyed (app shutting down) — nothing to restore
            pass
