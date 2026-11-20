"""Test configuration and fixtures for desktop tests."""

from __future__ import annotations

import os
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from desktop import i18n


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--no-sandbox"])
    yield app


@pytest.fixture(autouse=True)
def _reset_i18n_test_environment():
    """Ensure every desktop test starts with a clean, default English locale."""
    try:
        QSettings("RESIVO", "StaffConsole").remove("general/language")
    except Exception:
        pass
    i18n.init("en")
    yield
    try:
        QSettings("RESIVO", "StaffConsole").remove("general/language")
    except Exception:
        pass
    i18n.init("en")
