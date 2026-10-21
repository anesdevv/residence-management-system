"""TaskRunner key reservations must survive a same-key follow-up task."""

import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from desktop.app.ui.tasks import TaskRunner


def _qapp():
    return QApplication.instance() or QApplication([])


def _wait_until(predicate, timeout=4.0):
    app = _qapp()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    app.processEvents()
    return bool(predicate())


def test_follow_up_same_key_keeps_reservation_until_it_finishes():
    qapp = _qapp()
    pool = QThreadPool()
    runner = TaskRunner(pool=pool)
    release = threading.Event()
    follow_up_started = threading.Event()
    follow_up_finished = threading.Event()

    def second():
        follow_up_started.set()
        assert release.wait(4.0)
        return "second"

    def on_first(_result):
        runner.run("same", second, on_finished=follow_up_finished.set)

    assert runner.run("same", lambda: "first", on_success=on_first)

    assert _wait_until(follow_up_started.is_set)
    # Drain the queued finished signal for the first task.  A buggy release
    # would let the same key start a third task while the follow-up is running.
    settle = time.monotonic() + 0.2
    while time.monotonic() < settle:
        qapp.processEvents()
        time.sleep(0.01)
    assert runner.is_busy("same")
    assert not runner.run("same", lambda: "third")

    release.set()
    assert _wait_until(follow_up_finished.is_set)
    assert _wait_until(lambda: not runner.is_busy("same"))
    qapp.processEvents()
    pool.waitForDone(4000)
