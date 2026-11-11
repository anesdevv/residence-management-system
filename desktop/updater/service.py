"""Qt adapter for the updater engine.

All HTTP and file work runs through the existing :class:`TaskRunner`, so the
GUI thread only ever handles signals.  Progress events are emitted from the
worker thread and delivered to widgets through queued connections.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from desktop.version import __version__

from desktop.app.ui.tasks import TaskRunner
from . import config, prefs
from .checker import CheckResult, check_for_update, default_cache_path
from .downloader import (
    DownloadCancelled,
    UpdateError,
    clean_updates_dir,
    download_installer,
)
from .release import ReleaseError, ReleaseInfo
from .state import UpdateState, UpdateStateMachine

__all__ = ["UpdateService"]

_log = logging.getLogger("resivo.updater")

_CHECK_KEY = "updates-check"
_DOWNLOAD_KEY = "updates-download"


class UpdateService(QObject):
    """Owns the updater state and runs engine work off the GUI thread."""

    state_changed = Signal(str, object)  # UpdateState value, ReleaseInfo | None
    progress_changed = Signal(int, int)  # downloaded bytes, total bytes
    check_finished = Signal(object)  # CheckResult
    download_finished = Signal(object)  # Path
    download_cancelled = Signal()
    error_occurred = Signal(str, str)  # code, fallback message
    available_changed = Signal(bool)
    skipped_changed = Signal(str)

    def __init__(self, tasks: TaskRunner, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.tasks = tasks
        self.machine = UpdateStateMachine()
        self._release: ReleaseInfo | None = None
        self._installer_path: Path | None = None
        self._cancel = threading.Event()
        self._silent = False
        self.machine.add_listener(self._on_state)

    # ------------------------------------------------------------------ state
    @property
    def state(self) -> UpdateState:
        return self.machine.state

    @property
    def release(self) -> ReleaseInfo | None:
        return self._release

    @property
    def installer_path(self) -> Path | None:
        return self._installer_path

    @property
    def silent(self) -> bool:
        """True while the current check was started in the background."""
        return self._silent

    def _on_state(self, _old: UpdateState, new: UpdateState) -> None:
        self.state_changed.emit(new.value, self._release)

    def _set_state(self, target: UpdateState) -> None:
        if self.machine.state is target:
            return
        try:
            self.machine.set(target)
        except ValueError:
            # UI-driven resets are always allowed; rebuild the machine if the
            # strict transition table would otherwise trap the user.
            self.machine = UpdateStateMachine(target)
            self.machine.add_listener(self._on_state)
            self.state_changed.emit(target.value, self._release)

    def is_busy(self) -> bool:
        return self.state in (
            UpdateState.CHECKING,
            UpdateState.DOWNLOADING,
            UpdateState.VERIFYING,
            UpdateState.INSTALLING,
        )

    def mark_installing(self) -> None:
        self._set_state(UpdateState.INSTALLING)

    def fail_install(self, message: str = "") -> None:
        """Surface a failed installer launch without leaving the UI busy."""
        self._fail("error_installer", message)

    # ------------------------------------------------------------------ check
    def check(self, *, silent: bool = False) -> bool:
        """Start a check on the worker pool. Returns False when already busy."""
        if self.is_busy():
            return False
        if self.tasks.is_busy(_CHECK_KEY) or self.tasks.is_busy(_DOWNLOAD_KEY):
            return False
        self._silent = silent
        self._release = None
        self._installer_path = None
        self._set_state(UpdateState.CHECKING)

        def work() -> CheckResult:
            try:
                clean_updates_dir()
            except Exception:  # noqa: BLE001 - cleanup must never block a check
                _log.warning("update cleanup skipped")
            return check_for_update(
                current_version=__version__,
                cache_path=default_cache_path(),
            )

        started = self.tasks.run(
            _CHECK_KEY,
            work,
            on_success=self._on_check_result,
            on_failed=lambda message: self._fail("error", message),
            on_finished=lambda: None,
            use_client_lock=False,
        )
        if not started:
            self._set_state(UpdateState.IDLE)
            return False
        return True

    def _on_check_result(self, result: CheckResult) -> None:
        try:
            prefs.set_last_check(result.checked_at or time.time())
        except Exception:  # noqa: BLE001 - preference write is best effort
            pass
        self.check_finished.emit(result)
        if result.kind == "available" and result.release is not None:
            self._release = result.release
            self._installer_path = None
            self._set_state(UpdateState.AVAILABLE)
            self.available_changed.emit(True)
            return
        if result.kind == "up_to_date":
            self._release = None
            self._set_state(UpdateState.UP_TO_DATE)
            self.available_changed.emit(False)
            return
        if result.kind == "no_releases":
            self._release = None
            self._set_state(UpdateState.UP_TO_DATE)
            self.available_changed.emit(False)
            return
        # rate_limited / offline / error
        self._fail(result.code or result.kind, result.message)

    def _fail(self, code: str, message: str) -> None:
        self.error_occurred.emit(code, message)
        self._set_state(UpdateState.ERROR)

    # --------------------------------------------------------------- download
    def start_download(self) -> bool:
        if self._release is None:
            return False
        if self.state not in (UpdateState.AVAILABLE, UpdateState.ERROR):
            return False
        if self.tasks.is_busy(_DOWNLOAD_KEY):
            return False
        self._silent = False
        self._cancel.clear()
        self._installer_path = None
        self._set_state(UpdateState.DOWNLOADING)

        release = self._release

        def work() -> dict:
            def on_progress(done: int, total: int) -> None:
                self.progress_changed.emit(int(done), int(total))

            try:
                path = download_installer(
                    release,
                    progress=on_progress,
                    cancel=self._cancel,
                )
            except DownloadCancelled:
                return {"ok": False, "cancelled": True, "code": "cancelled"}
            except (UpdateError, ReleaseError) as exc:
                return {
                    "ok": False,
                    "cancelled": False,
                    "code": getattr(exc, "code", "error"),
                    "message": str(exc),
                }
            except OSError:
                return {"ok": False, "cancelled": False, "code": "offline"}
            except Exception:  # noqa: BLE001 - never leak a traceback to the UI
                _log.error("update failed: unexpected download error")
                return {"ok": False, "cancelled": False, "code": "error"}
            return {"ok": True, "path": path, "code": ""}

        started = self.tasks.run(
            _DOWNLOAD_KEY,
            work,
            on_success=self._on_download_result,
            on_failed=lambda message: self._fail("error", message),
            use_client_lock=False,
        )
        if not started:
            self._set_state(UpdateState.AVAILABLE)
            return False
        return True

    def _on_download_result(self, outcome: dict) -> None:
        if not isinstance(outcome, dict):
            self._fail("error", "")
            return
        if outcome.get("cancelled"):
            self._installer_path = None
            self._set_state(UpdateState.IDLE)
            self.download_cancelled.emit()
            return
        if not outcome.get("ok"):
            self._fail(str(outcome.get("code") or "error"), str(outcome.get("message") or ""))
            return
        path = outcome.get("path")
        if not isinstance(path, Path):
            self._fail("error", "")
            return
        self._installer_path = path
        # Download already verified the file; surface the short verifying
        # state so the UI explains the gap before "Ready to install".
        self._set_state(UpdateState.VERIFYING)
        self._set_state(UpdateState.READY)
        _log.info("download verified")
        self.download_finished.emit(path)

    def cancel_download(self) -> None:
        if self.state is UpdateState.DOWNLOADING:
            self._cancel.set()

    # ------------------------------------------------------------- preferences
    def skip_current(self) -> None:
        if self._release is None:
            return
        prefs.set_skipped_version(self._release.version_str)
        self.skipped_changed.emit(self._release.version_str)
        self.available_changed.emit(False)
        self._set_state(UpdateState.IDLE)

    def is_skipped(self, version: str | None = None) -> bool:
        target = version or (self._release.version_str if self._release else "")
        return bool(target) and prefs.get_skipped_version() == target

    def reset(self) -> None:
        if self.state is not UpdateState.INSTALLING:
            self._release = None
            self._installer_path = None
            self._set_state(UpdateState.IDLE)
            self.available_changed.emit(False)
