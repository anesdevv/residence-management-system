"""Tests for C5: Password show/hide toggle on LoginWindow."""

import os
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLineEdit, QToolButton

from desktop.app.ui.login_window import LoginWindow

_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


@pytest.fixture
def login_win():
    win = LoginWindow()
    yield win
    win.close()


def test_password_default_echo_mode_is_hidden(login_win):
    assert login_win.password.echoMode() == QLineEdit.EchoMode.Password
    assert hasattr(login_win, "toggle_password_btn")
    btn = login_win.toggle_password_btn
    assert isinstance(btn, QToolButton)
    assert btn.toolTip() == "Show password"
    assert btn.accessibleName() == "Show password"


def test_password_toggle_click_cycles_echo_mode(login_win):
    btn = login_win.toggle_password_btn

    # First click: reveals password
    btn.click()
    _qapp.processEvents()
    assert login_win.password.echoMode() == QLineEdit.EchoMode.Normal
    assert btn.toolTip() == "Hide password"
    assert btn.accessibleName() == "Hide password"

    # Second click: hides password again
    btn.click()
    _qapp.processEvents()
    assert login_win.password.echoMode() == QLineEdit.EchoMode.Password
    assert btn.toolTip() == "Show password"
    assert btn.accessibleName() == "Show password"


def test_password_accessible_by_tab_and_enter(login_win):
    # Ensure window is visible offscreen for focus handling
    login_win.show()
    _qapp.processEvents()

    # Move focus to password input
    login_win.password.setFocus()
    _qapp.processEvents()
    assert _qapp.focusWidget() == login_win.password

    # Tab advances to toggle_password_btn
    login_win.focusNextChild()
    _qapp.processEvents()
    assert _qapp.focusWidget() == login_win.toggle_password_btn

    # Space or Enter on the button toggles
    login_win.toggle_password_btn.click()
    _qapp.processEvents()
    assert login_win.password.echoMode() == QLineEdit.EchoMode.Normal


def test_enter_in_password_field_triggers_attempt(login_win, monkeypatch):
    called = []
    monkeypatch.setattr(login_win, "attempt", lambda: called.append(True))

    login_win.password.setFocus()
    # Emitting returnPressed directly (as hitting Enter in QLineEdit does)
    login_win.password.returnPressed.emit()
    assert len(called) == 1


def test_password_resets_to_hidden_on_reopen(login_win):
    # Show password
    login_win.toggle_password_btn.click()
    assert login_win.password.echoMode() == QLineEdit.EchoMode.Normal

    # Window hidden then reopened (showEvent)
    login_win.hide()
    _qapp.processEvents()
    login_win.show()
    _qapp.processEvents()

    assert login_win.password.echoMode() == QLineEdit.EchoMode.Password
    assert login_win.toggle_password_btn.toolTip() == "Show password"
