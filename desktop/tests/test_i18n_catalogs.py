"""RÉSIVO — Unit tests for i18n JSON translation catalogs and engine parity."""

import json
from pathlib import Path
import re
import pytest

from desktop import i18n

I18N_DIR = Path(__file__).resolve().parents[1] / "i18n"
EN_PATH = I18N_DIR / "en.json"
FR_PATH = I18N_DIR / "fr.json"


def _flatten_keys(data: dict, prefix: str = "") -> dict[str, str]:
    result = {}
    for key, value in data.items():
        composite = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten_keys(value, composite))
        else:
            result[composite] = str(value)
    return result


def test_catalogs_exist_and_valid_json():
    assert EN_PATH.is_file(), f"Missing {EN_PATH}"
    assert FR_PATH.is_file(), f"Missing {FR_PATH}"

    with open(EN_PATH, "r", encoding="utf-8") as f:
        en_data = json.load(f)
    with open(FR_PATH, "r", encoding="utf-8") as f:
        fr_data = json.load(f)

    assert isinstance(en_data, dict)
    assert isinstance(fr_data, dict)


def test_catalogs_key_parity():
    with open(EN_PATH, "r", encoding="utf-8") as f:
        en_keys = _flatten_keys(json.load(f))
    with open(FR_PATH, "r", encoding="utf-8") as f:
        fr_keys = _flatten_keys(json.load(f))

    diff_en = set(en_keys.keys()) - set(fr_keys.keys())
    diff_fr = set(fr_keys.keys()) - set(en_keys.keys())

    assert not diff_en, f"Keys in en.json but missing in fr.json: {diff_en}"
    assert not diff_fr, f"Keys in fr.json but missing in en.json: {diff_fr}"
    assert len(en_keys) >= 50, "Catalog should have comprehensive key set"


def test_catalogs_placeholder_parity():
    with open(EN_PATH, "r", encoding="utf-8") as f:
        en_keys = _flatten_keys(json.load(f))
    with open(FR_PATH, "r", encoding="utf-8") as f:
        fr_keys = _flatten_keys(json.load(f))

    pattern = re.compile(r"\{([a-zA-Z0-9_]+)\}")
    for key, en_val in en_keys.items():
        fr_val = fr_keys[key]
        en_vars = set(pattern.findall(en_val))
        fr_vars = set(pattern.findall(fr_val))
        assert en_vars == fr_vars, f"Placeholder mismatch for '{key}': en={en_vars} vs fr={fr_vars}"


def test_french_typography_rules():
    with open(FR_PATH, "r", encoding="utf-8") as f:
        fr_keys = _flatten_keys(json.load(f))

    # Verify no untranslated forbidden brand strings
    # Brand rules: RÉSIVO, Cité Universitaire, Direction des Œuvres Universitaires (DOU)
    assert fr_keys.get("tray.balloon_title") == "RÉSIVO"

    # High punctuation should use non-breaking space
    for key, val in fr_keys.items():
        if "?" in val:
            # Check for non-breaking space before '?'
            assert "\u00a0?" in val, f"Missing non-breaking space before '?' in key '{key}': {val!r}"


def test_i18n_module_lookup_and_plurals():
    i18n.init("en")
    assert i18n.t("common.save") == "Save"
    assert i18n.t("common.cancel") == "Cancel"
    assert i18n.t("close_dialog.title") == "Close RÉSIVO?"
    assert i18n.tn("time.minutes_ago", count=1) == "1 minute ago"
    assert i18n.tn("time.minutes_ago", count=5) == "5 minutes ago"

    i18n.init("fr")
    assert i18n.t("common.save") == "Enregistrer"
    assert i18n.t("common.cancel") == "Annuler"
    assert i18n.t("close_dialog.title") == "Fermer RÉSIVO\u00a0?"
    # In French, count 0 and 1 are singular
    assert i18n.tn("time.minutes_ago", count=0) == "Il y a 0 minute"
    assert i18n.tn("time.minutes_ago", count=1) == "Il y a 1 minute"
    assert i18n.tn("time.minutes_ago", count=5) == "Il y a 5 minutes"
    assert i18n.tn("overview.pending_count", count=0) == "0 demande en attente"
    assert i18n.tn("overview.pending_count", count=1) == "1 demande en attente"
    assert i18n.tn("overview.pending_count", count=5) == "5 demandes en attente"
