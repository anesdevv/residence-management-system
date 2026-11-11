"""Tests for the updater state machine and persisted preferences."""

from __future__ import annotations

import pytest

from desktop.updater import prefs
from desktop.updater.state import UpdateState, UpdateStateMachine


PATHS_TO_STATE = {
    UpdateState.IDLE: [],
    UpdateState.CHECKING: [UpdateState.CHECKING],
    UpdateState.UP_TO_DATE: [UpdateState.CHECKING, UpdateState.UP_TO_DATE],
    UpdateState.AVAILABLE: [UpdateState.CHECKING, UpdateState.AVAILABLE],
    UpdateState.DOWNLOADING: [
        UpdateState.CHECKING,
        UpdateState.AVAILABLE,
        UpdateState.DOWNLOADING,
    ],
    UpdateState.VERIFYING: [
        UpdateState.CHECKING,
        UpdateState.AVAILABLE,
        UpdateState.DOWNLOADING,
        UpdateState.VERIFYING,
    ],
    UpdateState.READY: [
        UpdateState.CHECKING,
        UpdateState.AVAILABLE,
        UpdateState.DOWNLOADING,
        UpdateState.VERIFYING,
        UpdateState.READY,
    ],
    UpdateState.INSTALLING: [
        UpdateState.CHECKING,
        UpdateState.AVAILABLE,
        UpdateState.DOWNLOADING,
        UpdateState.VERIFYING,
        UpdateState.READY,
        UpdateState.INSTALLING,
    ],
    UpdateState.ERROR: [UpdateState.ERROR],
}


def reach(state: UpdateState) -> UpdateStateMachine:
    machine = UpdateStateMachine()
    for step in PATHS_TO_STATE[state]:
        machine.set(step)
    assert machine.state is state
    return machine


def test_initial_state_is_idle():
    machine = UpdateStateMachine()
    assert machine.state is UpdateState.IDLE


def test_normal_happy_path_transitions():
    machine = UpdateStateMachine()
    machine.set("checking")
    machine.set(UpdateState.AVAILABLE)
    machine.set(UpdateState.DOWNLOADING)
    machine.set(UpdateState.VERIFYING)
    machine.set(UpdateState.READY)
    machine.set(UpdateState.INSTALLING)
    assert machine.state is UpdateState.INSTALLING


def test_illegal_transition_raises():
    machine = UpdateStateMachine()
    assert machine.can_transition(UpdateState.READY) is False
    with pytest.raises(ValueError):
        machine.set(UpdateState.READY)

    machine.set(UpdateState.CHECKING)
    assert machine.can_transition(UpdateState.DOWNLOADING) is False
    with pytest.raises(ValueError):
        machine.set(UpdateState.DOWNLOADING)
    assert machine.state is UpdateState.CHECKING


def test_error_is_reachable_from_every_state():
    for state in UpdateState:
        machine = reach(state)
        assert machine.can_transition(UpdateState.ERROR) is True
        machine.set(UpdateState.ERROR)
        assert machine.state is UpdateState.ERROR


def test_unknown_state_rejected():
    machine = UpdateStateMachine()
    with pytest.raises(ValueError):
        machine.set("teleporting")
    assert machine.can_transition("teleporting") is False


def test_same_state_is_allowed_without_notification():
    machine = UpdateStateMachine()
    events = []
    machine.add_listener(lambda old, new: events.append((old, new)))
    machine.set(UpdateState.IDLE)
    assert events == []
    assert machine.state is UpdateState.IDLE


def test_listeners_receive_old_and_new_state():
    machine = UpdateStateMachine()
    events = []
    listener = lambda old, new: events.append((old, new))  # noqa: E731
    machine.add_listener(listener)
    machine.set(UpdateState.CHECKING)
    machine.set(UpdateState.UP_TO_DATE)
    assert events == [
        (UpdateState.IDLE, UpdateState.CHECKING),
        (UpdateState.CHECKING, UpdateState.UP_TO_DATE),
    ]

    machine.remove_listener(listener)
    machine.set(UpdateState.IDLE)
    assert len(events) == 2


def test_listener_exception_does_not_break_state():
    machine = UpdateStateMachine()

    def broken(old, new):
        raise RuntimeError("boom")

    machine.add_listener(broken)
    machine.set(UpdateState.CHECKING)
    assert machine.state is UpdateState.CHECKING


@pytest.fixture(autouse=True)
def _clean_prefs():
    prefs.reset_for_tests()
    yield
    prefs.reset_for_tests()


def test_auto_check_preference_roundtrip():
    assert prefs.get_auto_check() is True
    prefs.set_auto_check(False)
    assert prefs.get_auto_check() is False
    prefs.set_auto_check(True)
    assert prefs.get_auto_check() is True


def test_skipped_and_notified_version_roundtrip():
    assert prefs.get_skipped_version() == ""
    prefs.set_skipped_version("1.2.0")
    assert prefs.get_skipped_version() == "1.2.0"
    prefs.set_skipped_version("")
    assert prefs.get_skipped_version() == ""

    prefs.set_notified_version("1.3.0")
    assert prefs.get_notified_version() == "1.3.0"
    prefs.set_notified_version(None)
    assert prefs.get_notified_version() == ""


def test_last_check_and_should_auto_check():
    now = 1_800_000_000.0
    assert prefs.get_last_check() == 0.0
    assert prefs.should_auto_check(now=now) is True

    prefs.set_last_check(now - 60)
    assert prefs.get_last_check() == pytest.approx(now - 60)
    assert prefs.should_auto_check(now=now) is False

    prefs.set_last_check(now - 25 * 3600)
    assert prefs.should_auto_check(now=now) is True

    prefs.set_auto_check(False)
    assert prefs.should_auto_check(now=now) is False


def test_reset_for_tests_clears_updates_keys():
    prefs.set_auto_check(False)
    prefs.set_skipped_version("9.9.9")
    prefs.set_last_check(123.0)
    prefs.reset_for_tests()
    assert prefs.get_auto_check() is True
    assert prefs.get_skipped_version() == ""
    assert prefs.get_last_check() == 0.0
