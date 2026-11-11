"""Main-window update orchestration: badge, auto-check and install hand-off."""

from __future__ import annotations

from pathlib import Path

import pytest

from PySide6.QtWidgets import QApplication

from desktop.app.ui import main_window as mw
from desktop.updater import prefs
from desktop.updater.downloader import UpdateError
from desktop.updater.state import UpdateState


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def _clean_prefs():
    prefs.reset_for_tests()
    yield
    prefs.reset_for_tests()


class FakeService:
    def __init__(self, state=UpdateState.READY, installer=None):
        self.state = state
        self.installer_path = installer
        self.release = None
        self.checked = []
        self.failed = []

    def is_busy(self) -> bool:
        return False

    def check(self, *, silent: bool = False) -> bool:
        self.checked.append(silent)
        return True

    def is_skipped(self, version) -> bool:
        return False

    def mark_installing(self) -> None:
        self.state = UpdateState.INSTALLING

    def fail_install(self, message="") -> None:
        self.failed.append(message)


class DummyWindow:
    _closing = False
    _sidebar_minimized = False
    _update_available = False
    _pending_shutdown_action = None
    _shutdown_confirmed = False
    _pending_update_path = None
    _shutdown_timer = None
    tray_icon = None

    def __init__(self, service, installer=None):
        self.update_service = service
        self.settings_update_badge = type(
            "Badge", (), {"visible": False, "setVisible": self._set_badge}
        )()
        self.shutdown_actions = []
        self.closed = False
        self._installer = installer

    def _set_badge(self, visible):
        self.settings_update_badge.visible = visible

    def _begin_shutdown(self, action):
        self.shutdown_actions.append(action)

    def _stop_live_timer(self):
        pass

    def _shutdown_workers(self, wait_ms=3000):
        return True

    def close(self):
        self.closed = True


def test_auto_check_uses_silent_mode(qapp):
    service = FakeService()
    window = DummyWindow(service)
    mw.MainWindow._auto_check_updates(window)
    assert service.checked == [True]


def test_auto_check_respects_the_daily_throttle(qapp):
    service = FakeService()
    window = DummyWindow(service)
    prefs.set_auto_check(False)
    mw.MainWindow._auto_check_updates(window)
    assert service.checked == []


def test_auto_check_is_skipped_while_closing(qapp):
    service = FakeService()
    window = DummyWindow(service)
    window._closing = True
    mw.MainWindow._auto_check_updates(window)
    assert service.checked == []


def test_install_request_starts_the_update_shutdown(qapp):
    installer = Path(r"C:\updates\Setup-RESIVO-1.2.3.exe")
    service = FakeService(installer=installer)
    window = DummyWindow(service)

    mw.MainWindow._on_update_install_requested(window, installer)

    assert window._pending_update_path == installer
    assert window._shutdown_confirmed is True
    assert window.shutdown_actions == ["update"]
    assert service.state is UpdateState.INSTALLING


def test_install_request_rejects_an_unexpected_path(qapp):
    installer = Path(r"C:\updates\Setup-RESIVO-1.2.3.exe")
    service = FakeService(installer=installer)
    window = DummyWindow(service)

    mw.MainWindow._on_update_install_requested(window, Path(r"C:\evil.exe"))

    assert window.shutdown_actions == []
    assert service.failed


def test_install_request_rejects_a_non_ready_state(qapp):
    installer = Path(r"C:\updates\Setup-RESIVO-1.2.3.exe")
    service = FakeService(state=UpdateState.AVAILABLE, installer=installer)
    window = DummyWindow(service)

    mw.MainWindow._on_update_install_requested(window, installer)

    assert window.shutdown_actions == []
    assert service.failed


def test_installer_launch_releases_the_lock_then_closes(qapp, monkeypatch):
    installer = Path(r"C:\updates\Setup-RESIVO-1.2.3.exe")
    service = FakeService(installer=installer)
    window = DummyWindow(service, installer=installer)
    window._pending_update_path = installer

    class FakeLock:
        def __init__(self):
            self.unlocked = False

        def unlock(self):
            self.unlocked = True

    lock = FakeLock()
    previous = getattr(qapp, "_instance_lock", None)
    qapp._instance_lock = lock

    launched = []
    monkeypatch.setattr(mw, "launch_installer", lambda path: launched.append(path))

    class FakeTimer:
        @staticmethod
        def singleShot(ms, fn):
            pass

    monkeypatch.setattr(mw, "QTimer", FakeTimer)
    try:
        mw.MainWindow._install_pending_update(window)
    finally:
        qapp._instance_lock = previous

    assert lock.unlocked is True
    assert launched == [installer]
    assert window.closed is True
    assert window._pending_update_path is None


def test_installer_launch_failure_keeps_the_app_open(qapp, monkeypatch):
    installer = Path(r"C:\updates\Setup-RESIVO-1.2.3.exe")
    service = FakeService(installer=installer)
    window = DummyWindow(service, installer=installer)
    window._pending_update_path = installer
    window._shutdown_confirmed = True

    def _boom(path):
        raise UpdateError("bad_installer_path")

    monkeypatch.setattr(mw, "launch_installer", _boom)
    toasts = []
    monkeypatch.setattr(
        mw.components, "show_toast", lambda *a, **k: toasts.append((a, k))
    )

    mw.MainWindow._install_pending_update(window)

    assert window.closed is False
    assert window._shutdown_confirmed is False
    assert service.failed
    assert prefs.get_install_error()
    assert toasts
