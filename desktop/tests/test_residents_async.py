"""Async action safety for the residents page."""

from __future__ import annotations

import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from desktop.app.ui.pages import residents as residents_mod
from desktop.app.ui.pages.residents import ResidentsPage


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def _drain_tasks(qapp):
    yield
    QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()


def wait_until(qapp, predicate, timeout=4.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    qapp.processEvents()
    return bool(predicate())


class FakeQuery:
    def __init__(self, client):
        self.client = client

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        self.client.calls += 1
        if self.client.delay:
            time.sleep(self.client.delay)
        if self.client.error is not None:
            raise self.client.error
        return SimpleNamespace(data=self.client.data)


class FakeClient:
    def __init__(self):
        self.calls = 0
        self.delay = 0.05
        self.error = None
        self.data = [
            {
                "id": "st-1",
                "card_id": "CARD-001",
                "first_name": "Alice",
                "last_name": "Smith",
                "gender": "female",
                "faculty": "Science",
                "university": "State Univ",
                "rooms": {"block": "A", "number": "101", "floor": 1},
                "status": "active",
            }
        ]

    def table(self, _name):
        return FakeQuery(self)


def test_residents_reload_is_async_and_updates_table(qapp):
    client = FakeClient()
    page = ResidentsPage(client, defer_initial_load=True)

    t0 = time.monotonic()
    page.reload()
    elapsed = time.monotonic() - t0
    # Must return immediately without waiting for delay
    assert elapsed < 0.25
    assert not page.refresh_btn.isEnabled()

    assert wait_until(qapp, lambda: len(page.rows) == 1 and page.refresh_btn.isEnabled())
    assert page.table.rowCount() == 1
    assert "1 active residents" in page.count_badge.text()
    assert not page.error_banner.isVisible()


def test_residents_reload_failure_shows_error_banner(qapp):
    client = FakeClient()
    client.error = RuntimeError("DB connection dropped")
    page = ResidentsPage(client, defer_initial_load=True)

    page.reload()
    assert wait_until(qapp, lambda: not page.error_banner.isHidden() and page.refresh_btn.isEnabled())
    assert "DB connection dropped" in page.error_banner._message.text()


def test_residents_double_reload_submits_once(qapp):
    client = FakeClient()
    client.delay = 0.1
    page = ResidentsPage(client, defer_initial_load=True)

    page.reload()
    page.reload()  # Should be rejected because task is busy

    assert wait_until(qapp, lambda: page.refresh_btn.isEnabled())
    assert client.calls == 1
