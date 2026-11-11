"""Update flow state machine (GUI-thread only; no locking)."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Callable

__all__ = ["UpdateState", "UpdateStateMachine"]

_log = logging.getLogger("resivo.updater")

Listener = Callable[["UpdateState", "UpdateState"], None]


class UpdateState(str, Enum):
    IDLE = "idle"
    CHECKING = "checking"
    UP_TO_DATE = "up_to_date"
    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    READY = "ready"
    INSTALLING = "installing"
    ERROR = "error"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


_ALLOWED: dict[UpdateState, frozenset[UpdateState]] = {
    UpdateState.IDLE: frozenset(
        {UpdateState.CHECKING, UpdateState.AVAILABLE, UpdateState.ERROR}
    ),
    UpdateState.CHECKING: frozenset(
        {
            UpdateState.IDLE,
            UpdateState.UP_TO_DATE,
            UpdateState.AVAILABLE,
            UpdateState.ERROR,
        }
    ),
    UpdateState.UP_TO_DATE: frozenset(
        {UpdateState.IDLE, UpdateState.CHECKING, UpdateState.ERROR}
    ),
    UpdateState.AVAILABLE: frozenset(
        {
            UpdateState.IDLE,
            UpdateState.CHECKING,
            UpdateState.DOWNLOADING,
            UpdateState.ERROR,
        }
    ),
    UpdateState.DOWNLOADING: frozenset(
        {
            UpdateState.IDLE,
            UpdateState.VERIFYING,
            UpdateState.ERROR,
        }
    ),
    UpdateState.VERIFYING: frozenset(
        {UpdateState.IDLE, UpdateState.READY, UpdateState.ERROR}
    ),
    UpdateState.READY: frozenset(
        {
            UpdateState.IDLE,
            UpdateState.AVAILABLE,
            UpdateState.INSTALLING,
            UpdateState.ERROR,
        }
    ),
    UpdateState.INSTALLING: frozenset({UpdateState.IDLE, UpdateState.ERROR}),
    UpdateState.ERROR: frozenset(
        {UpdateState.IDLE, UpdateState.CHECKING, UpdateState.ERROR}
    ),
}


class UpdateStateMachine:
    """Tracks the updater state and notifies listeners on legal changes.

    Listener callbacks receive ``(old_state, new_state)``.  Callbacks run on
    the caller's thread (the GUI thread) and exceptions raised by a listener
    are logged and swallowed so the state machine cannot be corrupted.
    """

    def __init__(self, initial: UpdateState = UpdateState.IDLE) -> None:
        self._state = UpdateState(initial)
        self.listeners: list[Listener] = []

    @property
    def state(self) -> UpdateState:
        return self._state

    def can_transition(self, new_state: UpdateState | str) -> bool:
        try:
            target = UpdateState(new_state)
        except ValueError:
            return False
        if target is self._state:
            return True
        if target is UpdateState.ERROR:
            return True
        return target in _ALLOWED.get(self._state, frozenset())

    def add_listener(self, callback: Listener) -> None:
        if callback not in self.listeners:
            self.listeners.append(callback)

    def remove_listener(self, callback: Listener) -> None:
        if callback in self.listeners:
            self.listeners.remove(callback)

    def set(self, new_state: UpdateState | str) -> UpdateState:
        try:
            target = UpdateState(new_state)
        except ValueError as exc:
            raise ValueError(f"unknown update state: {new_state!r}") from exc
        if target is self._state:
            return self._state
        if not self.can_transition(target):
            raise ValueError(
                f"illegal update state transition: {self._state.value} -> {target.value}"
            )
        old = self._state
        self._state = target
        for listener in tuple(self.listeners):
            try:
                listener(old, target)
            except Exception:  # pragma: no cover - defensive UI isolation
                _log.exception("update state listener failed")
        return self._state
