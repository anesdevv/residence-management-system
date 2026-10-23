"""Unit tests for C8: Desktop notifications, grouping, settings, and tray integration."""

from datetime import time
from unittest.mock import MagicMock, patch
import pytest

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from desktop.app.ui.notifications import (
    NotificationManager,
    is_in_quiet_hours,
)
from desktop.app.ui.pages.settings import SettingsPage


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_quiet_hours_calculation():
    # 1. Normal daytime range: 09:00 to 17:00
    assert is_in_quiet_hours("09:00", "17:00", time(10, 30)) is True
    assert is_in_quiet_hours("09:00", "17:00", time(8, 59)) is False
    assert is_in_quiet_hours("09:00", "17:00", time(17, 0)) is False

    # 2. Night range wrapping midnight: 22:00 to 07:00
    assert is_in_quiet_hours("22:00", "07:00", time(22, 0)) is True
    assert is_in_quiet_hours("22:00", "07:00", time(23, 45)) is True
    assert is_in_quiet_hours("22:00", "07:00", time(3, 15)) is True
    assert is_in_quiet_hours("22:00", "07:00", time(6, 59)) is True
    assert is_in_quiet_hours("22:00", "07:00", time(7, 0)) is False
    assert is_in_quiet_hours("22:00", "07:00", time(14, 0)) is False


def test_notification_classification_and_privacy(monkeypatch):
    test_settings = {}
    monkeypatch.setattr(QSettings, "value", lambda self, key, default=None: test_settings.get(key, default))
    monkeypatch.setattr(QSettings, "setValue", lambda self, key, val: test_settings.__setitem__(key, val))

    nm = NotificationManager()

    # Maintenance with name
    nm.settings.show_student_names = True
    c, t, b = nm.classify_event("New maintenance report: Plumbing (John Doe)")
    assert c == "maintenance"
    assert t == "New Maintenance Report"
    assert "John Doe" in b

    # Maintenance without name (privacy on)
    nm.settings.show_student_names = False
    c, t, b = nm.classify_event("New maintenance report: Plumbing (John Doe)")
    assert "John Doe" not in b
    assert b == "New maintenance report: Plumbing"

    # Registration with name
    nm.settings.show_student_names = True
    c, t, b = nm.classify_event("New registration: Jane Smith (Card: C123)")
    assert c == "registrations"
    assert "Jane Smith" in b

    # Registration without name
    nm.settings.show_student_names = False
    c, t, b = nm.classify_event("New registration: Jane Smith (Card: C123)")
    assert "Jane Smith" not in b
    assert "Card: C123" in b

    # Room change
    nm.settings.show_student_names = True
    c, t, b = nm.classify_event("New room-change request from Alice")
    assert c == "room_changes"
    assert "Alice" in b

    nm.settings.show_student_names = False
    c, t, b = nm.classify_event("New room-change request from Alice")
    assert "Alice" not in b


def test_notification_deduplication(monkeypatch):
    test_settings = {}
    monkeypatch.setattr(QSettings, "value", lambda self, key, default=None: test_settings.get(key, default))
    monkeypatch.setattr(QSettings, "setValue", lambda self, key, val: test_settings.__setitem__(key, val))

    nm = NotificationManager()
    res1 = nm.handle_alert_event("New maintenance report: Heating (Student A)", now=100.0)
    assert res1 is not None

    # Immediate duplicate message is dropped
    res2 = nm.handle_alert_event("New maintenance report: Heating (Student A)", now=101.0)
    assert res2 is None


def test_burst_grouping_over_three_events(monkeypatch):
    test_settings = {}
    monkeypatch.setattr(QSettings, "value", lambda self, key, default=None: test_settings.get(key, default))
    monkeypatch.setattr(QSettings, "setValue", lambda self, key, val: test_settings.__setitem__(key, val))

    nm = NotificationManager()

    # Event 1 (t=1.0) -> single notification
    r1 = nm.handle_alert_event("New registration: S1 (Card: 1)", now=1.0)
    assert r1["title"] == "New Student Application"

    # Event 2 (t=3.0) -> single notification
    r2 = nm.handle_alert_event("New maintenance report: Water (S2)", now=3.0)
    assert r2["title"] == "New Maintenance Report"

    # Event 3 (t=5.0) -> single notification
    r3 = nm.handle_alert_event("New room-change request from S3", now=5.0)
    assert r3["title"] == "New Room-Change Request"

    # Event 4 (t=7.0, 4 events within 10s -> group!)
    r4 = nm.handle_alert_event("New maintenance report: Electricity (S4)", now=7.0)
    assert r4["title"] == "RÉSIVO Updates"
    assert "4 new residence updates" in r4["body"]
    assert "2 maintenance reports" in r4["body"]
    assert "1 application" in r4["body"]
    assert "1 room change" in r4["body"]


def test_notification_settings_filters(monkeypatch):
    test_settings = {}
    monkeypatch.setattr(QSettings, "value", lambda self, key, default=None: test_settings.get(key, default))
    monkeypatch.setattr(QSettings, "setValue", lambda self, key, val: test_settings.__setitem__(key, val))

    nm = NotificationManager()

    # 1. Master switch off
    nm.settings.enabled = False
    assert nm.handle_alert_event("New maintenance report: Door (S1)", now=10.0) is None
    nm.settings.enabled = True

    # 2. Per-event toggle off
    nm.settings.notify_maintenance = False
    assert nm.handle_alert_event("New maintenance report: Door (S2)", now=20.0) is None
    nm.settings.notify_maintenance = True

    # 3. Only when unfocused
    nm.settings.only_unfocused = True
    assert nm.handle_alert_event("New room-change request from S3", now=30.0, is_window_active=True) is None
    assert nm.handle_alert_event("New room-change request from S4", now=31.0, is_window_active=False) is not None
    nm.settings.only_unfocused = False

    # 4. Quiet hours filter
    nm.settings.quiet_hours_enabled = True
    nm.settings.quiet_hours_start = "22:00"
    nm.settings.quiet_hours_end = "07:00"
    assert nm.handle_alert_event("New registration: S5", now=40.0, check_time=time(23, 0)) is None
    assert nm.handle_alert_event("New registration: S6", now=41.0, check_time=time(14, 0)) is not None


def test_settings_page_notifications_ui(qapp, monkeypatch):
    test_settings = {}
    monkeypatch.setattr(QSettings, "value", lambda self, key, default=None: test_settings.get(key, default))
    monkeypatch.setattr(QSettings, "setValue", lambda self, key, val: test_settings.__setitem__(key, val))

    mock_client = MagicMock()
    page = SettingsPage(mock_client)
    page.show()
    qapp.processEvents()

    assert hasattr(page, "notif_card")
    assert hasattr(page, "notif_master_cb")
    assert hasattr(page, "test_notif_btn")

    # Toggle master switch off hides options
    page.notif_master_cb.setChecked(False)
    assert page.notif_options_container.isHidden()
    assert page.notif_manager.settings.enabled is False

    # Toggle master switch on shows options
    page.notif_master_cb.setChecked(True)
    assert not page.notif_options_container.isHidden()
    assert page.notif_manager.settings.enabled is True

    # Test notification button dispatches test payload
    with patch.object(page.notif_manager, "dispatch_notification") as mock_dispatch:
        page.test_notif_btn.click()
        assert mock_dispatch.called
        args, _ = mock_dispatch.call_args
        assert "RÉSIVO Notifications" in args[0]
