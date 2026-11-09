"""Unit tests for desktop/i18n module (D2 Phase 1 infrastructure)."""

from datetime import date, datetime, time as dtime
import os
from unittest.mock import MagicMock, patch
import pytest

from PySide6.QtCore import QSettings
from desktop import i18n


@pytest.fixture(autouse=True)
def reset_i18n_state():
    """Ensure tests run with a predictable language and non-pseudo locale by default."""
    old_pseudo = os.environ.get("RESIVO_PSEUDO_LOCALE")
    if "RESIVO_PSEUDO_LOCALE" in os.environ:
        del os.environ["RESIVO_PSEUDO_LOCALE"]
    i18n.init("en")
    yield
    if old_pseudo is not None:
        os.environ["RESIVO_PSEUDO_LOCALE"] = old_pseudo
    elif "RESIVO_PSEUDO_LOCALE" in os.environ:
        del os.environ["RESIVO_PSEUDO_LOCALE"]
    i18n.init("en")


def test_registry_and_current_language():
    langs = i18n.available_languages()
    assert "en" in langs
    assert "fr" in langs
    assert langs["en"].name == "English"
    assert langs["fr"].name == "Français"
    assert langs["en"].direction == "ltr"
    assert langs["fr"].direction == "ltr"

    i18n.init("fr")
    assert i18n.current_language() == "fr"

    i18n.init("en")
    assert i18n.current_language() == "en"


def test_t_lookup_and_interpolation():
    i18n.init("en")
    assert i18n.t("common.save") == "Save"
    assert i18n.t("login.welcome", name="Amina") == "Welcome, Amina"

    i18n.init("fr")
    assert i18n.t("common.save") == "Enregistrer"
    assert i18n.t("login.welcome", name="Amina") == "Bienvenue, Amina"


def test_t_fallback_chain(caplog):
    # Test key that exists in English but is missing in French
    i18n.init("fr")
    with patch.dict(i18n._CATALOGS.get("fr", {}), {}, clear=False):
        # Even if a key was somehow missing in French, it falls back to English
        val = i18n.t("common.save")
        assert val == "Enregistrer"  # From loaded catalog

    # Totally missing key in both catalogs
    val = i18n.t("nonexistent.missing_key_example")
    assert "missing key example" in val.lower() or val == "nonexistent.missing_key_example"


def test_tn_plurals_english():
    i18n.init("en")
    # English: 1 -> one, 0 and 2+ -> other
    assert i18n.tn("overview.pending_count", 0) == "0 pending applications"
    assert i18n.tn("overview.pending_count", 1) == "1 pending application"
    assert i18n.tn("overview.pending_count", 2) == "2 pending applications"
    assert i18n.tn("overview.pending_count", 50) == "50 pending applications"


def test_tn_plurals_french():
    i18n.init("fr")
    # French CLDR: 0 and 1 -> one, 2+ -> other
    msg_0 = i18n.tn("overview.pending_count", 0)
    msg_1 = i18n.tn("overview.pending_count", 1)
    msg_2 = i18n.tn("overview.pending_count", 2)

    assert "0" in msg_0 and "attente" in msg_0
    assert "1" in msg_1 and "attente" in msg_1
    assert "2" in msg_2 and "attente" in msg_2
    # Verify singular phrasing for 0 and 1
    assert "demande en attente" in msg_0  # singular
    assert "demande en attente" in msg_1  # singular
    assert "demandes en attente" in msg_2  # plural


def test_formatting_numbers():
    # English
    assert i18n.format_number(1234, locale="en") == "1,234"
    assert i18n.format_number(1234567.89, decimals=2, locale="en") == "1,234,567.89"
    assert i18n.format_number(-42000, locale="en") == "-42,000"

    # French (uses non-breaking space and comma)
    fr_num = i18n.format_number(1234, locale="fr")
    assert fr_num == "1\u00A0234"
    fr_float = i18n.format_number(1234567.89, decimals=2, locale="fr")
    assert fr_float == "1\u00A0234\u00A0567,89"


def test_formatting_percents():
    assert i18n.format_percent(95.5, decimals=1, locale="en") == "95.5%"
    assert i18n.format_percent(95.5, decimals=1, locale="fr") == "95,5\u00A0%"


def test_formatting_dates():
    d = date(2026, 10, 12)
    # English
    assert i18n.format_date(d, format="short", locale="en") == "10/12/2026"
    assert i18n.format_date(d, format="medium", locale="en") == "Oct 12, 2026"
    assert i18n.format_date(d, format="full", locale="en") == "October 12, 2026"

    # French
    assert i18n.format_date(d, format="short", locale="fr") == "12/10/2026"
    assert "oct." in i18n.format_date(d, format="medium", locale="fr")
    assert "12 octobre 2026" in i18n.format_date(d, format="full", locale="fr")


def test_formatting_times_and_datetimes():
    t_val = dtime(14, 30)
    assert i18n.format_time(t_val) == "14:30"

    dt = datetime(2026, 10, 12, 14, 30)
    en_dt = i18n.format_datetime(dt, format="medium", locale="en")
    assert "Oct 12, 2026 at 14:30" in en_dt

    fr_dt = i18n.format_datetime(dt, format="medium", locale="fr")
    assert "12 oct. 2026 à 14:30" in fr_dt


def test_pseudo_locale():
    # Test pseudo_transform preserves placeholders
    transformed = i18n.pseudo_transform("Welcome, {name}!")
    assert "{name}" in transformed
    assert transformed.startswith("[!! ")
    assert transformed.endswith(" !!]")
    # Vowels should be accented
    assert "Wḗlcṓmḗ" in transformed or "ḗ" in transformed

    # When env var is active
    os.environ["RESIVO_PSEUDO_LOCALE"] = "1"
    assert i18n.is_pseudo_locale() is True
    res = i18n.t("common.save")
    assert res.startswith("[!! ")
    assert res.endswith(" !!]")


def test_qsettings_persistence(monkeypatch):
    test_settings = {}
    monkeypatch.setattr(QSettings, "value", lambda self, key, default=None, **kwargs: test_settings.get(key, default))
    monkeypatch.setattr(QSettings, "setValue", lambda self, key, val: test_settings.__setitem__(key, val))

    i18n.set_saved_language("fr")
    assert i18n.get_saved_language() == "fr"

    i18n.set_saved_language("en")
    assert i18n.get_saved_language() == "en"

    # Invalid language raises ValueError
    with pytest.raises(ValueError):
        i18n.set_saved_language("es")
