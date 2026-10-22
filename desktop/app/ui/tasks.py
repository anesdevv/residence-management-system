"""Reusable background task runner for page actions.

Every mutating page action (approve, reject, delete, status change, import)
runs through this helper.  Network work happens on the Qt thread pool, results
are delivered back on the GUI thread through queued signals, and each action
key rejects a second submission while it is in flight.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from ..client import CLIENT_LOCK, redact_sensitive

_log = logging.getLogger("resivo.tasks")

_ACTIVE_TASKS = 0
_ACTIVE_TASKS_LOCK = threading.Lock()


def active_task_count() -> int:
    """Number of submitted tasks that have not delivered their finish signal."""
    with _ACTIVE_TASKS_LOCK:
        return _ACTIVE_TASKS


def _task_started() -> None:
    global _ACTIVE_TASKS
    with _ACTIVE_TASKS_LOCK:
        _ACTIVE_TASKS += 1


def _task_finished() -> None:
    global _ACTIVE_TASKS
    with _ACTIVE_TASKS_LOCK:
        if _ACTIVE_TASKS > 0:
            _ACTIVE_TASKS -= 1


def human_error(exc: BaseException) -> str:
    """Return a short, redacted, user-readable error rather than a traceback."""
    message = str(exc).strip()
    if not message:
        message = exc.__class__.__name__
    # Server errors are sometimes multi-line JSON/HTML; keep the first line.
    message = message.splitlines()[0].strip()
    message = redact_sensitive(message)
    if len(message) > 300:
        message = message[:297] + "..."
    return message


class _TaskSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()


class _Task(QRunnable):
    def __init__(
        self,
        fn: Callable[[], object],
        key: str,
        on_success: Callable[[object], None] | None,
        on_failed: Callable[[str], None] | None,
        on_finished: Callable[[], None] | None,
        use_client_lock: bool,
    ):
        super().__init__()
        self.fn = fn
        self.key = key
        self.on_success = on_success
        self.on_failed = on_failed
        self.on_finished = on_finished
        self.use_client_lock = use_client_lock
        self.signals = _TaskSignals()
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            if self.use_client_lock:
                with CLIENT_LOCK:
                    result = self.fn()
            else:
                result = self.fn()
        except Exception as exc:  # noqa: BLE001 - reported to the page
            message = human_error(exc)
            # Never log the raw exception: auth/storage errors can embed tokens.
            _log.error(
                "Background task %r failed (%s): %s",
                self.key,
                exc.__class__.__name__,
                message,
            )
            self.signals.failed.emit(message)
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()


class TaskRunner(QObject):
    """Runs one callable per action key and reports completion on the GUI thread."""

    busy_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None, pool: QThreadPool | None = None):
        super().__init__(parent)
        self._pool = pool or QThreadPool.globalInstance()
        self._tasks: dict[int, _Task] = {}
        self._by_key: dict[str, int] = {}

    def is_busy(self, key: str | None = None) -> bool:
        if key is None:
            return bool(self._tasks)
        return key in self._by_key

    def run(
        self,
        key: str,
        fn: Callable[[], object],
        *,
        on_success: Callable[[object], None] | None = None,
        on_failed: Callable[[str], None] | None = None,
        on_finished: Callable[[], None] | None = None,
        use_client_lock: bool = True,
    ) -> bool:
        """Start ``fn`` once for ``key``; return False if it is already running."""
        if key in self._by_key:
            return False

        task = _Task(
            fn,
            key,
            on_success,
            on_failed,
            on_finished,
            use_client_lock,
        )
        token = id(task.signals)
        self._tasks[token] = task
        self._by_key[key] = token
        task.signals.succeeded.connect(self._succeed)
        task.signals.failed.connect(self._fail)
        task.signals.finished.connect(self._finish)
        _task_started()
        try:
            self._pool.start(task)
        except Exception:
            self._tasks.pop(token, None)
            self._by_key.pop(key, None)
            _task_finished()
            raise
        self.busy_changed.emit(True)
        return True

    def _task_for_sender(self) -> _Task | None:
        sender = self.sender()
        return self._tasks.get(id(sender)) if sender is not None else None

    def _release_key(self, task: _Task) -> None:
        """Release only this task's reservation, never a newer same-key task."""
        token = id(task.signals)
        if self._by_key.get(task.key) == token:
            self._by_key.pop(task.key, None)

    @Slot(object)
    def _succeed(self, result: object) -> None:
        task = self._task_for_sender()
        if task is None:
            return
        self._release_key(task)
        if task.on_success is not None:
            try:
                task.on_success(result)
            except Exception:  # noqa: BLE001 - callbacks must not kill the app
                _log.exception("Task %r success handler failed", task.key)

    @Slot(str)
    def _fail(self, message: str) -> None:
        task = self._task_for_sender()
        if task is None:
            return
        self._release_key(task)
        if task.on_failed is not None:
            try:
                task.on_failed(message)
            except Exception:  # noqa: BLE001
                _log.exception("Task %r failure handler failed", task.key)

    @Slot()
    def _finish(self) -> None:
        task = self._task_for_sender()
        if task is None:
            return
        self._tasks.pop(id(task.signals), None)
        self._release_key(task)
        _task_finished()
        if task.on_finished is not None:
            try:
                task.on_finished()
            except Exception:  # noqa: BLE001
                _log.exception("Task %r finish handler failed", task.key)
        if not self._tasks:
            self.busy_changed.emit(False)
