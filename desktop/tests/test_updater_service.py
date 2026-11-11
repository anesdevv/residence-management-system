"""UpdateService (Qt adapter) behaviour without real threads or network."""

from __future__ import annotations

from pathlib import Path
import time

import pytest

from PySide6.QtWidgets import QApplication

from desktop.updater import prefs
from desktop.updater.checker import CheckResult
from desktop.updater.release import ReleaseInfo
from desktop.updater.service import UpdateService
from desktop.updater.state import UpdateState


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class FakeTasks:
    """Captures submissions so tests can drive their callbacks synchronously."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object, dict]] = []

    def is_busy(self, key=None) -> bool:
        return False

    def run(self, key, fn, **kwargs) -> bool:
        self.calls.append((key, fn, kwargs))
        return True


def _release(version: str = "1.2.3") -> ReleaseInfo:
    return ReleaseInfo(
        version=tuple(int(part) for part in version.split(".")),
        version_str=version,
        tag=f"v{version}",
        name=f"RÉSIVO {version}",
        notes="### Fixed\n\n- A thing",
        published_at="2026-01-01T00:00:00Z",
        published_dt=None,
        installer_name=f"Setup-RESIVO-{version}.exe",
        installer_url=f"https://github.com/x/y/releases/download/v{version}/Setup-RESIVO-{version}.exe",
        installer_size=1234,
        checksum_url=f"https://github.com/x/y/releases/download/v{version}/SHA256SUMS.txt",
        checksum_size=64,
        html_url=f"https://github.com/x/y/releases/tag/v{version}",
    )


@pytest.fixture(autouse=True)
def _clean_prefs():
    prefs.reset_for_tests()
    yield
    prefs.reset_for_tests()


def test_check_runs_off_the_gui_thread_and_reports_available(qapp):
    tasks = FakeTasks()
    service = UpdateService(tasks)
    states: list[str] = []
    available: list[bool] = []
    service.state_changed.connect(lambda value, _release: states.append(value))
    service.available_changed.connect(available.append)

    assert service.check() is True
    assert service.state is UpdateState.CHECKING
    assert tasks.calls and tasks.calls[0][2]["use_client_lock"] is False

    release = _release()
    tasks.calls[0][2]["on_success"](
        CheckResult("available", release=release, checked_at=time.time())
    )

    assert service.release is release
    assert service.state is UpdateState.AVAILABLE
    assert available[-1] is True
    assert "available" in states


def test_check_is_rejected_while_busy(qapp):
    tasks = FakeTasks()
    service = UpdateService(tasks)
    assert service.check() is True
    assert service.check() is False
    assert len(tasks.calls) == 1


def test_up_to_date_and_error_results(qapp):
    tasks = FakeTasks()
    service = UpdateService(tasks)
    service.check()
    tasks.calls[0][2]["on_success"](
        CheckResult("up_to_date", checked_at=time.time())
    )
    assert service.state is UpdateState.UP_TO_DATE

    errors: list[tuple[str, str]] = []
    service.error_occurred.connect(lambda code, msg: errors.append((code, msg)))
    service.check()
    tasks.calls[1][2]["on_success"](
        CheckResult("rate_limited", code="rate_limited", message="slow down", checked_at=time.time())
    )
    assert service.state is UpdateState.ERROR
    assert errors[-1][0] == "rate_limited"


def test_download_moves_to_ready_and_keeps_installer(qapp, tmp_path):
    tasks = FakeTasks()
    service = UpdateService(tasks)
    service.check()
    tasks.calls[0][2]["on_success"](
        CheckResult("available", release=_release(), checked_at=time.time())
    )

    assert service.start_download() is True
    assert service.state is UpdateState.DOWNLOADING
    assert tasks.calls[1][2]["use_client_lock"] is False

    installer = tmp_path / "Setup-RESIVO-1.2.3.exe"
    tasks.calls[1][2]["on_success"]({"ok": True, "path": installer, "code": ""})
    assert service.state is UpdateState.READY
    assert service.installer_path == installer


def test_cancelled_download_returns_to_idle(qapp):
    tasks = FakeTasks()
    service = UpdateService(tasks)
    service.check()
    tasks.calls[0][2]["on_success"](
        CheckResult("available", release=_release(), checked_at=time.time())
    )
    service.start_download()
    cancelled: list[bool] = []
    service.download_cancelled.connect(lambda: cancelled.append(True))

    tasks.calls[1][2]["on_success"]({"ok": False, "cancelled": True, "code": "cancelled"})
    assert service.state is UpdateState.IDLE
    assert service.installer_path is None
    assert cancelled == [True]


def test_fail_install_surfaces_error(qapp):
    tasks = FakeTasks()
    service = UpdateService(tasks)
    service.check()
    tasks.calls[0][2]["on_success"](
        CheckResult("available", release=_release(), checked_at=time.time())
    )
    service.start_download()
    service.fail_install("could not start")
    assert service.state is UpdateState.ERROR


def test_reset_clears_release_and_badge(qapp):
    tasks = FakeTasks()
    service = UpdateService(tasks)
    service.check()
    tasks.calls[0][2]["on_success"](
        CheckResult("available", release=_release(), checked_at=time.time())
    )
    available: list[bool] = []
    service.available_changed.connect(available.append)

    service.reset()
    assert service.release is None
    assert service.state is UpdateState.IDLE
    assert available[-1] is False


def test_skip_current_is_persisted(qapp):
    tasks = FakeTasks()
    service = UpdateService(tasks)
    service.check()
    tasks.calls[0][2]["on_success"](
        CheckResult("available", release=_release("2.0.0"), checked_at=time.time())
    )
    service.skip_current()
    assert prefs.get_skipped_version() == "2.0.0"
    assert service.is_skipped("2.0.0") is True
    assert service.is_skipped("2.0.1") is False


def test_silent_flag_tracks_the_current_check(qapp):
    tasks = FakeTasks()
    service = UpdateService(tasks)
    assert service.silent is False
    service.check(silent=True)
    assert service.silent is True
    tasks.calls[0][2]["on_success"](
        CheckResult("available", release=_release(), checked_at=time.time())
    )
    service.start_download()
    assert service.silent is False
