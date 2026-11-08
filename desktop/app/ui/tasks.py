"""Reusable background task runner for page actions.

Every mutating page action (approve, reject, delete, status change, import)
runs through this helper.  Network work happens on the Qt thread pool, results
are delivered back on the GUI thread through queued signals, and each action
key rejects a second submission while it is in flight.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from ..client import CLIENT_LOCK, redact_sensitive
from ..timeouts import (
    NetworkError,
    NetworkTimeoutError,
    is_connection_error,
    is_timeout_exception,
)

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
    if isinstance(exc, (NetworkTimeoutError, NetworkError)):
        return str(exc)
    if is_timeout_exception(exc):
        return NetworkTimeoutError.READ_MESSAGE
    if is_connection_error(exc):
        return NetworkError.DEFAULT_MESSAGE
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


@dataclass
class GatherResult:
    results: dict[str, Any]
    errors: dict[str, str]
    request_id: int = 0

    @property
    def all_succeeded(self) -> bool:
        return not bool(self.errors)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def get(self, key: str, default: Any = None) -> Any:
        return self.results.get(key, default)


class _GatherSignals(QObject):
    completed = Signal(object)


class _GatherCoordinator:
    def __init__(
        self,
        key: str,
        callables: dict[str, Callable[[], Any]],
        on_complete: Callable[[GatherResult], None],
        on_finished: Callable[[], None] | None,
        request_id: int,
    ):
        self.key = key
        self.callables = callables
        self.on_complete = on_complete
        self.on_finished = on_finished
        self.request_id = request_id
        self.signals = _GatherSignals()
        self.results: dict[str, Any] = {}
        self.errors: dict[str, str] = {}
        self._lock = threading.Lock()
        self._remaining = len(callables)

    def record_success(self, sub_key: str, val: Any) -> bool:
        with self._lock:
            self.results[sub_key] = val
            self._remaining -= 1
            return self._remaining == 0

    def record_failure(self, sub_key: str, err: str) -> bool:
        with self._lock:
            self.errors[sub_key] = err
            self._remaining -= 1
            return self._remaining == 0

    def make_result(self) -> GatherResult:
        with self._lock:
            return GatherResult(
                results=dict(self.results),
                errors=dict(self.errors),
                request_id=self.request_id,
            )


class _GatherSubTask(QRunnable):
    def __init__(
        self,
        sub_key: str,
        fn: Callable[[], Any],
        coordinator: _GatherCoordinator,
        use_client_lock: bool,
    ):
        super().__init__()
        self.sub_key = sub_key
        self.fn = fn
        self.coordinator = coordinator
        self.use_client_lock = use_client_lock
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            if self.use_client_lock:
                with CLIENT_LOCK:
                    val = self.fn()
            else:
                val = self.fn()
        except Exception as exc:  # noqa: BLE001 - reported to the page
            msg = human_error(exc)
            _log.warning(
                "Gather subtask %r under key %r failed (%s): %s",
                self.sub_key,
                self.coordinator.key,
                exc.__class__.__name__,
                msg,
            )
            is_last = self.coordinator.record_failure(self.sub_key, msg)
        else:
            is_last = self.coordinator.record_success(self.sub_key, val)
        finally:
            _task_finished()
            if is_last:
                res = self.coordinator.make_result()
                self.coordinator.signals.completed.emit(res)


class TaskRunner(QObject):
    """Runs one callable per action key and reports completion on the GUI thread."""

    busy_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None, pool: QThreadPool | None = None):
        super().__init__(parent)
        self._pool = pool or QThreadPool.globalInstance()
        self._tasks: dict[int, _Task] = {}
        self._gathers: dict[int, _GatherCoordinator] = {}
        self._by_key: dict[str, int] = {}

    def is_busy(self, key: str | None = None) -> bool:
        if key is None:
            return bool(self._tasks) or bool(self._gathers)
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

    def gather(
        self,
        key: str,
        callables: dict[str, Callable[[], Any]],
        *,
        on_complete: Callable[[GatherResult], None],
        on_finished: Callable[[], None] | None = None,
        request_id: int = 0,
        use_client_lock: bool = False,
    ) -> bool:
        """Run multiple independent callables concurrently on the pool.

        Delivers one consolidated GatherResult on the GUI thread when all
        sub-tasks finish (or fail). Does not cancel sibling tasks if one fails.
        Returns False if a task or gather is already in flight under `key`.
        """
        if key in self._by_key:
            return False

        if not callables:
            res = GatherResult(results={}, errors={}, request_id=request_id)
            if on_complete is not None:
                on_complete(res)
            if on_finished is not None:
                on_finished()
            return True

        coordinator = _GatherCoordinator(
            key=key,
            callables=callables,
            on_complete=on_complete,
            on_finished=on_finished,
            request_id=request_id,
        )
        token = id(coordinator.signals)
        self._gathers[token] = coordinator
        self._by_key[key] = token
        coordinator.signals.completed.connect(self._gather_completed)

        for sub_key, fn in callables.items():
            _task_started()
            subtask = _GatherSubTask(sub_key, fn, coordinator, use_client_lock)
            try:
                self._pool.start(subtask)
            except Exception:
                _task_finished()
                done = coordinator.record_failure(sub_key, "Could not start worker thread")
                if done:
                    coordinator.signals.completed.emit(coordinator.make_result())

        self.busy_changed.emit(True)
        return True

    @Slot(object)
    def _gather_completed(self, result: GatherResult) -> None:
        sender = self.sender()
        token = id(sender) if sender is not None else None
        coordinator = self._gathers.pop(token, None) if token is not None else None
        if coordinator is None:
            return

        if self._by_key.get(coordinator.key) == token:
            self._by_key.pop(coordinator.key, None)

        if coordinator.on_complete is not None:
            try:
                coordinator.on_complete(result)
            except Exception:  # noqa: BLE001
                _log.exception("Gather %r completion handler failed", coordinator.key)

        if coordinator.on_finished is not None:
            try:
                coordinator.on_finished()
            except Exception:  # noqa: BLE001
                _log.exception("Gather %r on_finished handler failed", coordinator.key)

        if not self._tasks and not self._gathers:
            self.busy_changed.emit(False)
