"""Overview refresh must not block the GUI thread or hide failures."""

import os
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from desktop.app.ui.pages import overview as overview_mod
from desktop.app.ui.pages.overview import OverviewPage


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
    def __init__(self, client, table):
        self.client = client
        self.table = table

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def neq(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self.client.delay:
            time.sleep(self.client.delay)
        if self.client.error is not None:
            raise self.client.error
        return SimpleNamespace(count=self.client.counts[self.table], data=[])


class FakeClient:
    def __init__(self):
        self.counts = {
            "students": 3,
            "maintenance_reports": 2,
            "room_change_requests": 1,
        }
        self.delay = 0.2
        self.error = None

    def table(self, name):
        return FakeQuery(self, name)


def test_overview_reload_is_async_and_reports_failure(qapp, monkeypatch):
    monkeypatch.setattr(
        overview_mod, "room_occupancy", lambda _client, **_kwargs: {}
    )
    client = FakeClient()

    started = time.monotonic()
    page = OverviewPage(client)
    elapsed = time.monotonic() - started

    assert elapsed < 0.15
    assert page._loading is True
    assert not page.skeleton.isHidden()
    assert wait_until(qapp, lambda: not page._loading)
    assert page.pending_card._value.text() == "3"
    assert page.reports_card._value.text() == "2"
    assert page.requests_card._value.text() == "1"
    assert page.error_banner.isHidden()

    client.error = RuntimeError("read timed out")
    page.reload()
    assert page._loading is True
    assert wait_until(qapp, lambda: not page._loading)
    assert not page.error_banner.isHidden()
    assert "read timed out" in page.error_banner._message.text()
    assert page.refresh_btn.isEnabled()
    page.close()


def test_live_tick_during_reload_is_not_overwritten(qapp, monkeypatch):
    monkeypatch.setattr(
        overview_mod, "room_occupancy", lambda _client, **_kwargs: {}
    )
    client = FakeClient()
    client.delay = 0.2

    page = OverviewPage(client)
    assert page._loading is True
    # A live-sync tick lands while the older snapshot is still being fetched.
    page.apply_live_data(99, 88, 77, 66)
    assert wait_until(qapp, lambda: not page._loading)

    assert page.pending_card._value.text() == "99"
    assert page.reports_card._value.text() == "88"
    assert page.requests_card._value.text() == "77"
    assert page.occupancy_card._value.text() == "66"
    assert page.error_banner.isHidden()
    page.close()


def test_live_tick_without_occupancy_keeps_snapshot_occupancy(qapp, monkeypatch):
    monkeypatch.setattr(
        overview_mod, "room_occupancy", lambda _client, **_kwargs: {"room-1": 5}
    )
    client = FakeClient()
    client.delay = 0.2

    page = OverviewPage(client)
    page.apply_live_data(99, 88, 77, None)
    assert wait_until(qapp, lambda: not page._loading)

    assert page.pending_card._value.text() == "99"
    assert page.reports_card._value.text() == "88"
    assert page.requests_card._value.text() == "77"
    assert page.occupancy_card._value.text() == "5"
    page.close()


def test_occupancy_read_failure_is_visible_not_zero(qapp, monkeypatch):
    def failing_occupancy(_client, **_kwargs):
        raise RuntimeError("occupancy read timed out")

    monkeypatch.setattr(overview_mod, "room_occupancy", failing_occupancy)
    client = FakeClient()

    page = OverviewPage(client)
    assert wait_until(qapp, lambda: not page._loading)
    assert not page.error_banner.isHidden()
    assert "occupancy read timed out" in page.error_banner._message.text()
    page.close()
