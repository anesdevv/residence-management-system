import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)
from ...client import current_role
from ..theme import apply_button_style, get_badge_qss


MCP_HEALTH_URL = "http://127.0.0.1:8000/health"
MCP_HEALTH_TIMEOUT_S = 2.0
MCP_HEALTH_INTERVAL_MS = 5000
MCP_HOSTED_URL = "https://residence-mcp.anes4tlm.workers.dev/mcp"

MUTED_QSS = "font-size: 11px; color: #64748b;"
STEP_TITLE_QSS = "font-size: 13px; font-weight: 600; color: #e2e8f0;"
STEP_TEXT_QSS = "font-size: 12px; color: #cbd5e1;"
STEP_NUMBER_QSS = "font-size: 12px; font-weight: 700; color: #64748b;"
SECTION_TITLE_QSS = "font-size: 13px; font-weight: 800; color: #e2e8f0; letter-spacing: 0.3px;"
MONO_QSS = "font-family: Consolas, monospace; font-size: 12px; color: #e2e8f0; background: transparent; border: none;"
TOKEN_QSS = "font-family: Consolas, monospace; font-size: 12px; color: #cbd5e1;"

CHECKBOX_QSS = """
QCheckBox {
    color: #e2e8f0;
    font-size: 13px;
    font-weight: 600;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #1f2638;
    border-radius: 4px;
    background-color: #090b10;
}
QCheckBox::indicator:hover {
    border-color: #3e4c6c;
}
QCheckBox::indicator:checked {
    background-color: #4f46e5;
    border-color: #6366f1;
}
QCheckBox:disabled {
    color: #475569;
}
QCheckBox::indicator:disabled {
    background-color: #10131d;
    border-color: #1c2233;
}
"""


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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Row
        header_vbox = QVBoxLayout()
        header_vbox.setSpacing(2)
        title_lbl = QLabel("Settings")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #f8fafc;")
        sub_lbl = QLabel("Console preferences and administrative integrations.")
        sub_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        header_vbox.addWidget(title_lbl)
        header_vbox.addWidget(sub_lbl)
        layout.addLayout(header_vbox)

        # Advanced Settings (Developer Mode) Card
        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)

        section_lbl = QLabel("ADVANCED SETTINGS (DEVELOPER MODE)")
        section_lbl.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 800; letter-spacing: 0.6px;")
        card_layout.addWidget(section_lbl)

        self.dev_checkbox = QCheckBox("Developer mode")
        self.dev_checkbox.setStyleSheet(CHECKBOX_QSS)
        self.dev_checkbox.toggled.connect(self._on_dev_mode_toggled)
        card_layout.addWidget(self.dev_checkbox)

        self.staff_note = QLabel("Developer mode is available to administrators only.")
        self.staff_note.setWordWrap(True)
        self.staff_note.setStyleSheet(MUTED_QSS)
        card_layout.addWidget(self.staff_note)

        self.enable_note = QLabel("Enable developer mode to view the ChatGPT connection steps.")
        self.enable_note.setWordWrap(True)
        self.enable_note.setStyleSheet(MUTED_QSS)
        card_layout.addWidget(self.enable_note)

        # ChatGPT write off-switch — admin only, outside the developer-mode gate
        self.writes_checkbox = QCheckBox("Allow ChatGPT to change data")
        self.writes_checkbox.setStyleSheet(CHECKBOX_QSS)
        self.writes_checkbox.toggled.connect(self._on_writes_toggled)
        card_layout.addWidget(self.writes_checkbox)

        self.writes_note = QLabel(
            "ChatGPT asks you to confirm every change first. "
            "Turn this off to make ChatGPT read-only again."
        )
        self.writes_note.setWordWrap(True)
        self.writes_note.setStyleSheet(MUTED_QSS)
        card_layout.addWidget(self.writes_note)

        self.content = self._build_content()
        card_layout.addWidget(self.content)

        layout.addWidget(card)
        layout.addStretch(1)

        # Role gating — developer mode is session-only, never persisted
        if self.role == "admin":
            self.staff_note.setVisible(False)
        else:
            self.dev_checkbox.setEnabled(False)
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
        outer.setContentsMargins(0, 4, 0, 0)
        outer.setSpacing(14)

        # -----------------------------------------------------------------
        # Hosted server (primary path) — Cloudflare Worker, always on
        # -----------------------------------------------------------------
        hosted = QWidget()
        hoc = QVBoxLayout(hosted)
        hoc.setContentsMargins(0, 0, 0, 0)
        hoc.setSpacing(10)

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
        hoc.addLayout(self._numbered_line("2.", "Give it a name and description — anything you like, for example “Residence Admin”."))
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
        loc.setSpacing(10)

        loc.addWidget(self._section_title("Run it locally (developer/testing only)"))
        loc.addWidget(self._hint(
            "The local Python server uses a bearer token and is meant for the MCP Inspector and other "
            "bearer-capable clients. ChatGPT itself requires the hosted server above."
        ))

        # MCP server status row
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        status_lbl = QLabel("MCP server")
        status_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #cbd5e1;")
        status_row.addWidget(status_lbl)

        self.health_badge = QLabel("Checking…")
        self.health_badge.setStyleSheet(get_badge_qss("neutral"))
        status_row.addWidget(self.health_badge)

        port_lbl = QLabel("port 8000")
        port_lbl.setStyleSheet(MUTED_QSS)
        status_row.addWidget(port_lbl)
        status_row.addStretch(1)
        loc.addLayout(status_row)

        loc.addWidget(self._divider())

        # Step 1 — Start the MCP server
        step1 = QWidget()
        s1 = QVBoxLayout(step1)
        s1.setContentsMargins(0, 0, 0, 0)
        s1.setSpacing(8)
        s1.addWidget(self._step_title("Step 1 · Start the MCP server"))
        repo_root = Path(__file__).resolve().parents[4]
        s1.addWidget(self._command_box(f'cd "{repo_root}"; & "mcp\\.venv\\Scripts\\python.exe" "mcp\\server.py"'))
        s1.addWidget(self._hint("Paste into any PowerShell window and leave it open while a testing client is connected. The badge above turns green once the server is running."))
        loc.addWidget(step1)

        # Step 2 — Optional: expose the local server with a tunnel
        step2 = QWidget()
        s2 = QVBoxLayout(step2)
        s2.setContentsMargins(0, 0, 0, 0)
        s2.setSpacing(8)
        s2.addWidget(self._step_title("Step 2 · Expose it with a tunnel (optional)"))
        s2.addWidget(self._command_box("wrangler tunnel quick-start http://localhost:8000"))
        hint2 = self._hint(
            'A public https://… URL is printed in that terminal — leave it open while testing. Alternatives: '
            '<span style="font-family: Consolas, monospace;">cloudflared tunnel --url http://localhost:8000</span> or '
            '<span style="font-family: Consolas, monospace;">ngrok http 8000</span>.'
        )
        hint2.setTextFormat(Qt.RichText)
        s2.addWidget(hint2)
        s2.addLayout(self._composer_row())
        loc.addWidget(step2)

        # Step 3 — Connect with the MCP Inspector
        step3 = QWidget()
        s3 = QVBoxLayout(step3)
        s3.setContentsMargins(0, 0, 0, 0)
        s3.setSpacing(8)
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
        footer.setWordWrap(True)
        footer.setStyleSheet(MUTED_QSS)
        outer.addWidget(footer)

        return content

    def _divider(self) -> QFrame:
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background-color: #1c2234; border: none;")
        return div

    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(SECTION_TITLE_QSS)
        return lbl

    def _step_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(STEP_TITLE_QSS)
        return lbl

    def _hint(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(MUTED_QSS)
        return lbl

    def _command_box(self, command: str) -> QFrame:
        box = QFrame()
        box.setObjectName("commandBox")
        box.setStyleSheet("""
            QFrame#commandBox {
                background-color: #0b0d14;
                border: 1px solid #1c2234;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        cmd_lbl = QLabel(command)
        cmd_lbl.setStyleSheet(MONO_QSS)
        cmd_lbl.setWordWrap(True)
        cmd_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(cmd_lbl, 1)
        row.addWidget(self._copy_button(lambda: command))
        return box

    def _numbered_line(self, number: str, text: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        num_lbl = QLabel(number)
        num_lbl.setStyleSheet(STEP_NUMBER_QSS)
        num_lbl.setFixedWidth(16)
        num_lbl.setAlignment(Qt.AlignTop)
        row.addWidget(num_lbl)
        text_lbl = QLabel(text)
        text_lbl.setStyleSheet(STEP_TEXT_QSS)
        text_lbl.setWordWrap(True)
        row.addWidget(text_lbl, 1)
        return row

    def _composer_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(22, 0, 0, 0)
        row.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://xxxx.trycloudflare.com")
        self.url_input.textChanged.connect(self._on_url_input_changed)
        row.addWidget(self.url_input, 1)

        self.url_output = QLineEdit()
        self.url_output.setReadOnly(True)
        row.addWidget(self.url_output, 1)

        row.addWidget(self._copy_button(lambda: self.url_output.text()))
        return row

    def _static_url_row(self, url: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(22, 0, 0, 0)
        row.setSpacing(8)

        url_label = QLineEdit(url)
        url_label.setReadOnly(True)
        row.addWidget(url_label, 1)

        row.addWidget(self._copy_button(lambda: url))
        return row

    def _token_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(22, 0, 0, 0)
        row.setSpacing(8)

        self.token_label = QLabel("")
        self.token_label.setStyleSheet(TOKEN_QSS)
        self.token_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(self.token_label, 1)

        self.reveal_btn = QPushButton("Reveal")
        apply_button_style(self.reveal_btn, "secondary")
        self.reveal_btn.clicked.connect(self._on_reveal_clicked)
        row.addWidget(self.reveal_btn)

        self.token_copy_btn = QPushButton("Copy")
        apply_button_style(self.token_copy_btn, "secondary")
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
        else:
            self.writes_note.setText(
                "ChatGPT asks you to confirm every change first. "
                "Turn this off to make ChatGPT read-only again."
            )
        self._writes_loading = True
        try:
            self.writes_checkbox.blockSignals(True)
            self.writes_checkbox.setChecked(writes_enabled)
        finally:
            self.writes_checkbox.blockSignals(False)
            self._writes_loading = False
        self.writes_checkbox.setEnabled(ok)

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
            QMessageBox.warning(self, "Settings", f"Could not save the setting: {exc}")

    def _on_dev_mode_toggled(self, checked: bool):
        if self.role != "admin":
            return
        self.enable_note.setVisible(not checked)
        self.content.setVisible(checked)

    def _on_health_changed(self, up: bool):
        if up:
            self.health_badge.setText("Running")
            self.health_badge.setStyleSheet(get_badge_qss("success"))
        else:
            self.health_badge.setText("Offline")
            self.health_badge.setStyleSheet(get_badge_qss("danger"))

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
            self.token_label.setStyleSheet(MUTED_QSS)
            self.token_label.setText("Token not found — check mcp/.env.")
            return
        self.token_label.setStyleSheet(TOKEN_QSS)
        self._update_token_display()

    def _update_token_display(self):
        if self._token_revealed:
            self.token_label.setText(self._token)
            self.reveal_btn.setText("Hide")
        else:
            self.token_label.setText("•" * 12 + self._token[-4:])
            self.reveal_btn.setText("Reveal")

    def _copy_button(self, text_getter) -> QPushButton:
        btn = QPushButton("Copy")
        apply_button_style(btn, "secondary")
        btn.clicked.connect(lambda: self._copy_to_clipboard(btn, text_getter()))
        return btn

    def _copy_to_clipboard(self, btn: QPushButton, text: str):
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        btn.setText("Copied ✓")
        QTimer.singleShot(1500, lambda: self._restore_button_text(btn, "Copy"))

    def _restore_button_text(self, btn: QPushButton, text: str):
        try:
            btn.setText(text)
        except RuntimeError:
            # Widget already destroyed (app shutting down) — nothing to restore
            pass
