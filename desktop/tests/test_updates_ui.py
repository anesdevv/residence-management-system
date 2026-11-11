"""Settings → Updates card and its plain-text release-note rendering."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from desktop.app.ui.components import ConfirmDialog
from desktop.app.ui.pages.settings import SettingsPage
from desktop.app.ui.updates_ui import UpdatesSection, markdown_to_plain
from desktop.updater.release import ReleaseInfo
from desktop.updater.state import UpdateState


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class StubService(QObject):
    state_changed = Signal(str, object)
    check_finished = Signal(object)
    progress_changed = Signal(int, int)
    download_cancelled = Signal()
    error_occurred = Signal(str, str)
    available_changed = Signal(bool)
    skipped_changed = Signal(str)

    def __init__(self, state: UpdateState = UpdateState.AVAILABLE) -> None:
        super().__init__()
        self.state = state
        self.release = _release()
        self.installer_path = Path(r"C:\updates\Setup-RESIVO-1.2.3.exe")
        self.silent = False
        self.skipped = ""
        self.checked = 0
        self.skipped_calls = 0
        self.download_calls = 0
        self.reset_calls = 0

    def check(self, *, silent: bool = False) -> bool:
        self.checked += 1
        return True

    def start_download(self) -> bool:
        self.download_calls += 1
        return True

    def cancel_download(self) -> None:
        pass

    def skip_current(self) -> None:
        self.skipped_calls += 1
        self.skipped = self.release.version_str if self.release else ""
        self.available_changed.emit(False)

    def is_skipped(self, version: str | None = None) -> bool:
        return bool(version) and version == self.skipped

    def reset(self) -> None:
        self.reset_calls += 1


def _release(version: str = "1.2.3") -> ReleaseInfo:
    return ReleaseInfo(
        version=tuple(int(part) for part in version.split(".")),
        version_str=version,
        tag=f"v{version}",
        name=f"RÉSIVO {version}",
        notes="## What's new\n\n- Faster startup\n\n[Details](https://example.com)",
        published_at="2026-01-01T00:00:00Z",
        published_dt=datetime(2026, 1, 1, tzinfo=timezone.utc),
        installer_name=f"Setup-RESIVO-{version}.exe",
        installer_url="https://github.com/x/y/download/Setup.exe",
        installer_size=10,
        checksum_url="https://github.com/x/y/download/SHA256SUMS.txt",
        checksum_size=10,
        html_url="https://github.com/x/y/releases/tag/v1.2.3",
    )


def test_markdown_to_plain_is_safe_and_readable():
    text = markdown_to_plain(
        "# Notes\n\n**Bold** and `code`\n\n[Link](https://example.com)\n\n* bullet"
    )
    assert "NOTES" in text
    assert "Bold and code" in text
    assert "Link (https://example.com)" in text
    assert "- bullet" in text
    assert "<" not in text


def test_markdown_to_plain_truncates():
    text = markdown_to_plain("x" * 50, max_chars=10)
    assert len(text) <= 10
    assert text.endswith("…")


def test_section_renders_available_release(qapp):
    service = StubService()
    section = UpdatesSection(service)

    assert section.update_button.isVisibleTo(section)
    assert section.skip_button.isVisibleTo(section)
    assert section.notes_box.isVisibleTo(section)
    assert "Faster startup" in section.notes_box.toPlainText()
    assert section.status_label.text()


def test_check_button_starts_a_manual_check(qapp):
    service = StubService(UpdateState.IDLE)
    section = UpdatesSection(service)
    section.check_button.click()
    assert service.checked == 1


def test_install_confirm_emits_the_verified_path(qapp, monkeypatch):
    service = StubService()
    section = UpdatesSection(service)
    emitted: list[object] = []
    section.install_requested.connect(emitted.append)
    monkeypatch.setattr(ConfirmDialog, "ask", classmethod(lambda cls, *a, **k: True))

    section.update_button.click()
    assert emitted == [service.installer_path]


def test_install_cancelled_by_user_does_nothing(qapp, monkeypatch):
    service = StubService()
    section = UpdatesSection(service)
    emitted: list[object] = []
    section.install_requested.connect(emitted.append)
    monkeypatch.setattr(ConfirmDialog, "ask", classmethod(lambda cls, *a, **k: False))

    section.update_button.click()
    assert emitted == []


def test_update_now_downloads_when_no_installer_is_ready(qapp):
    service = StubService(UpdateState.AVAILABLE)
    service.installer_path = None
    section = UpdatesSection(service)
    section.update_button.click()
    assert service.download_calls == 1


def test_skip_hides_the_actions(qapp):
    service = StubService()
    section = UpdatesSection(service)
    section.skip_button.click()
    assert service.skipped_calls == 1
    assert not section.update_button.isVisibleTo(section)


def test_error_codes_map_to_localized_banners(qapp):
    service = StubService(UpdateState.ERROR)
    section = UpdatesSection(service)
    section._on_error("checksum_mismatch", "")
    assert section.error_banner.isVisibleTo(section)
    assert "checksum" in section.error_banner._message.text().lower()


def test_silent_check_errors_stay_quiet(qapp):
    service = StubService(UpdateState.IDLE)
    service.silent = True
    section = UpdatesSection(service)
    section._on_error("offline", "")
    assert not section.error_banner.isVisibleTo(section)


def test_progress_and_cancel_visibility(qapp):
    service = StubService(UpdateState.DOWNLOADING)
    section = UpdatesSection(service)
    section._on_progress(5, 10)
    assert section.progress_bar.value() == 50
    service.download_cancelled.emit()
    assert section.progress_bar.value() == 0


def test_settings_page_embeds_the_shared_service_and_forwards_install(qapp):
    from unittest.mock import MagicMock

    service = StubService()
    page = SettingsPage(MagicMock(), defer_initial_load=True, role="staff", update_service=service)
    try:
        assert page.updates_section is not None
        forwarded: list[object] = []
        page.update_install_requested.connect(forwarded.append)
        page.updates_section.install_requested.emit(service.installer_path)
        assert forwarded == [service.installer_path]
    finally:
        page.deleteLater()


def test_settings_page_without_service_has_no_updates_card(qapp):
    from unittest.mock import MagicMock

    page = SettingsPage(MagicMock(), defer_initial_load=True, role="staff")
    try:
        assert page.updates_section is None
    finally:
        page.deleteLater()
