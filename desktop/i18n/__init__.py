"""RÉSIVO — Desktop Internationalization (i18n) Engine.

Provides:
- Stable semantic key lookup with dot notation: ``t("common.save")``.
- Pluralization support with CLDR category rules: ``tn("overview.pending_count", count=5)``.
- Fallback chain: selected language -> English (en) -> key string + log warning.
- Dynamic named parameters: ``t("login.welcome", name="Amina")``.
- Localized date, time, number, and percentage formatting helpers.
- Pseudo-locale generation (``RESIVO_PSEUDO_LOCALE=1``) for automated QA.
- Native Qt standard dialog translations (``qtbase_fr.qm``) via ``QTranslator``.
- QSettings persistence under ``QSettings("RESIVO", "StaffConsole")`` key ``general/language``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as dtime
import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import Any

# Ensure both 'i18n' and 'desktop.i18n' resolve to the exact same module instance
sys.modules.setdefault("i18n", sys.modules[__name__])
sys.modules.setdefault("desktop.i18n", sys.modules[__name__])

_log = logging.getLogger("resivo.i18n")

_I18N_DIR = Path(__file__).resolve().parent
_DEFAULT_LANG = "en"
_FALLBACK_LANG = "en"


@dataclass(frozen=True)
class LanguageInfo:
    code: str
    name: str          # Native language name shown in picker
    direction: str     # "ltr" or "rtl"
    locale_name: str   # e.g. "en_US", "fr_FR"


_REGISTRY: dict[str, LanguageInfo] = {
    "en": LanguageInfo(code="en", name="English", direction="ltr", locale_name="en_US"),
    "fr": LanguageInfo(code="fr", name="Français", direction="ltr", locale_name="fr_FR"),
}

# In-memory catalogs: { "en": { ... }, "fr": { ... } }
_CATALOGS: dict[str, dict[str, Any]] = {}
_CURRENT_LANG: str = _DEFAULT_LANG
_QT_TRANSLATOR: Any = None


def available_languages() -> dict[str, LanguageInfo]:
    """Return immutable copy of supported languages registry."""
    return dict(_REGISTRY)


def current_language() -> str:
    """Return currently active language code."""
    return _CURRENT_LANG


def is_pseudo_locale() -> bool:
    """Return True if RESIVO_PSEUDO_LOCALE environment variable is active."""
    return os.environ.get("RESIVO_PSEUDO_LOCALE", "").strip().lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------

def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Deep merge source dict into target dict in-place."""
    for k, v in source.items():
        if isinstance(v, dict) and k in target and isinstance(target[k], dict):
            _deep_merge(target[k], v)
        else:
            target[k] = v


def _load_catalog(lang_code: str) -> dict[str, Any]:
    """Load JSON translation catalog from disk with fallback to empty dict."""
    if lang_code in _CATALOGS:
        return _CATALOGS[lang_code]

    path = _I18N_DIR / f"{lang_code}.json"
    result: dict[str, Any] = {}
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    result = data
        except Exception as exc:  # noqa: BLE001
            _log.error("Failed to parse catalog JSON for locale '%s': %s", lang_code, exc)

    # Also load and merge any partial catalog_*.json files
    try:
        for extra_path in sorted(_I18N_DIR.glob("catalog_*.json")):
            try:
                with open(extra_path, "r", encoding="utf-8") as f:
                    extra_data = json.load(f)
                if isinstance(extra_data, dict):
                    if lang_code in extra_data and isinstance(extra_data[lang_code], dict):
                        _deep_merge(result, extra_data[lang_code])
                    elif lang_code not in ("en", "fr") and not any(k in extra_data for k in ("en", "fr")):
                        _deep_merge(result, extra_data)
                    elif extra_path.stem.endswith(f"_{lang_code}"):
                        _deep_merge(result, extra_data)
            except Exception as exc:  # noqa: BLE001
                _log.warning("Failed to load partial catalog %s: %s", extra_path.name, exc)
    except Exception:
        pass

    _CATALOGS[lang_code] = result
    return _CATALOGS[lang_code]


def _lookup_key(catalog: dict[str, Any], key: str) -> str | None:
    """Traverse nested dictionary with dot notation."""
    parts = key.split(".")
    curr: Any = catalog
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return None
    return str(curr) if curr is not None and not isinstance(curr, dict) else None


# ---------------------------------------------------------------------------
# Pseudo-locale transformation
# ---------------------------------------------------------------------------

_VOWEL_MAP = {
    "a": "ȧ", "e": "ḗ", "i": "ḯ", "o": "ṓ", "u": "ṻ", "y": "ẏ",
    "A": "Ȧ", "E": "Ḗ", "I": "Ḯ", "O": "Ṓ", "U": "Ṻ", "Y": "Ẏ",
}


def pseudo_transform(text: str) -> str:
    """Transform text for pseudo-locale QA: ~40% expansion with accented characters.

    Named placeholders such as ``{name}`` or ``{count}`` are strictly preserved.
    """
    if not text:
        return text

    # Split on named placeholders so {var} remains untouched
    tokens = re.split(r"(\{[^{}]+\})", text)
    transformed_parts: list[str] = []

    for token in tokens:
        if token.startswith("{") and token.endswith("}"):
            transformed_parts.append(token)
        else:
            # Replace vowels and add ~40% length expansion
            chars = [_VOWEL_MAP.get(ch, ch) for ch in token]
            expanded = "".join(chars)
            # Add length padding if non-empty
            if len(expanded.strip()) > 3:
                pad_len = max(1, int(len(expanded) * 0.35))
                expanded += " " + ("~" * pad_len)
            transformed_parts.append(expanded)

    return f"[!! {''.join(transformed_parts)} !!]"


# ---------------------------------------------------------------------------
# Core Translation functions: t and tn
# ---------------------------------------------------------------------------

def t(key: str, **params: Any) -> str:
    """Translate semantic key with parameter interpolation and fallback chain."""
    active_catalog = _load_catalog(_CURRENT_LANG)
    fallback_catalog = _load_catalog(_FALLBACK_LANG)

    raw_text = _lookup_key(active_catalog, key)
    if raw_text is None:
        if _CURRENT_LANG != _FALLBACK_LANG:
            raw_text = _lookup_key(fallback_catalog, key)
        if raw_text is None:
            _log.warning("Missing translation key: '%s' in locale '%s'", key, _CURRENT_LANG)
            # Fallback to the key's leaf or key itself
            raw_text = key.rsplit(".", 1)[-1].replace("_", " ")

    # Interpolate named parameters
    if params:
        try:
            # Custom formatting helper for params if passed
            formatted_params = {k: str(v) for k, v in params.items()}
            raw_text = raw_text.format(**formatted_params)
        except KeyError as exc:
            _log.warning("Missing placeholder %s for key '%s'", exc, key)
        except Exception as exc:  # noqa: BLE001
            _log.warning("Interpolation error for key '%s': %s", key, exc)

    if is_pseudo_locale():
        return pseudo_transform(raw_text)

    return raw_text


def tn(key: str, count: int, **params: Any) -> str:
    """Translate plural semantic key following CLDR rules for active language.

    Rule:
    - English: count == 1 -> key_one, else key_other
    - French: count in (0, 1) -> key_one, else key_other
    """
    params["count"] = count

    if _CURRENT_LANG == "fr":
        plural_suffix = "one" if count in (0, 1) else "other"
    else:
        plural_suffix = "one" if count == 1 else "other"

    plural_key = f"{key}_{plural_suffix}"
    result = t(plural_key, **params)

    # If specific plural key not found and returned fallback, try base key
    if result == plural_key or result == plural_key.rsplit(".", 1)[-1].replace("_", " "):
        base_result = t(key, **params)
        if base_result != key:
            return base_result

    return result


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

_MONTH_NAMES_EN = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
_MONTH_NAMES_EN_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MONTH_NAMES_FR = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
_MONTH_NAMES_FR_ABBR = ["", "janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def format_number(val: int | float, decimals: int | None = None, locale: str | None = None) -> str:
    """Format number with locale-appropriate grouping and decimal separators."""
    loc = locale or _CURRENT_LANG
    if decimals is not None:
        fmt = f"{{:.{decimals}f}}"
        num_str = fmt.format(val)
        parts = num_str.split(".")
        int_part = parts[0]
        dec_part = parts[1] if len(parts) > 1 else ""
    else:
        num_str = str(val)
        if "." in num_str:
            int_part, dec_part = num_str.split(".", 1)
        else:
            int_part, dec_part = num_str, ""

    # Group thousands
    is_neg = int_part.startswith("-")
    clean_int = int_part[1:] if is_neg else int_part

    grouped = ""
    for idx, char in enumerate(reversed(clean_int)):
        if idx > 0 and idx % 3 == 0:
            sep = "\u00A0" if loc == "fr" else ","
            grouped = sep + grouped
        grouped = char + grouped

    if is_neg:
        grouped = "-" + grouped

    if dec_part:
        dec_sep = "," if loc == "fr" else "."
        return f"{grouped}{dec_sep}{dec_part}"
    return grouped


def format_percent(val: float, decimals: int = 1, locale: str | None = None) -> str:
    """Format percentage value with localized decimal and non-breaking space."""
    loc = locale or _CURRENT_LANG
    num = format_number(val, decimals=decimals, locale=loc)
    if loc == "fr":
        return f"{num}\u00A0%"
    return f"{num}%"


def _parse_date_input(dt: date | datetime | str) -> date:
    """Normalize date/datetime/ISO string input into date object."""
    if isinstance(dt, datetime):
        return dt.date()
    if isinstance(dt, date):
        return dt
    if isinstance(dt, str):
        # Try ISO format
        clean = dt.replace("Z", "").split("+")[0].split(".")[0]
        if "T" in clean:
            return datetime.fromisoformat(clean).date()
        return date.fromisoformat(clean)
    raise ValueError(f"Cannot parse date from {dt!r}")


def _parse_time_input(t_val: dtime | datetime | str) -> dtime:
    """Normalize time/datetime/string input into time object."""
    if isinstance(t_val, datetime):
        return t_val.time()
    if isinstance(t_val, dtime):
        return t_val
    if isinstance(t_val, str):
        clean = t_val.strip()
        if "T" in clean:
            clean = clean.split("T", 1)[1]
        clean = clean.replace("Z", "").split("+")[0].split(".")[0]
        parts = clean.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        second = int(parts[2]) if len(parts) > 2 else 0
        return dtime(hour, minute, second)
    raise ValueError(f"Cannot parse time from {t_val!r}")


def format_date(d: date | datetime | str, format: str = "medium", locale: str | None = None) -> str:
    """Format date in localized format (short: 12/10/2026, medium: 12 oct. 2026, full: 12 octobre 2026)."""
    loc = locale or _CURRENT_LANG
    dt = _parse_date_input(d)

    if loc == "fr":
        if format == "short":
            return f"{dt.day:02d}/{dt.month:02d}/{dt.year}"
        if format == "full":
            return f"{dt.day} {_MONTH_NAMES_FR[dt.month]} {dt.year}"
        # medium
        return f"{dt.day} {_MONTH_NAMES_FR_ABBR[dt.month]} {dt.year}"

    # English
    if format == "short":
        return f"{dt.month:02d}/{dt.day:02d}/{dt.year}"
    if format == "full":
        return f"{_MONTH_NAMES_EN[dt.month]} {dt.day}, {dt.year}"
    # medium
    return f"{_MONTH_NAMES_EN_ABBR[dt.month]} {dt.day}, {dt.year}"


def format_time(t_val: dtime | datetime | str, locale: str | None = None) -> str:
    """Format time in standard 24h format: HH:MM."""
    tm = _parse_time_input(t_val)
    return f"{tm.hour:02d}:{tm.minute:02d}"


def format_datetime(dt: datetime | str, format: str = "medium", locale: str | None = None) -> str:
    """Format datetime combining localized date and 24h time."""
    loc = locale or _CURRENT_LANG
    d_part = format_date(dt, format=format, locale=loc)
    t_part = format_time(dt, locale=loc)
    if loc == "fr":
        return f"{d_part} à {t_part}"
    return f"{d_part} at {t_part}"


# ---------------------------------------------------------------------------
# Qt and QSettings integration
# ---------------------------------------------------------------------------

def get_saved_language() -> str | None:
    """Read saved language preference from QSettings."""
    try:
        from PySide6.QtCore import QSettings
        settings = QSettings("RESIVO", "StaffConsole")
        val = settings.value("general/language", None)
        if val and str(val).strip().lower() in _REGISTRY:
            return str(val).strip().lower()
    except Exception:  # noqa: BLE001
        pass
    return None


def set_saved_language(lang_code: str) -> None:
    """Persist language preference to QSettings and activate in memory."""
    code = lang_code.strip().lower()
    if code not in _REGISTRY:
        raise ValueError(f"Unsupported language code: {lang_code}")
    global _CURRENT_LANG
    _CURRENT_LANG = code
    _load_catalog(code)
    try:
        from PySide6.QtCore import QSettings
        settings = QSettings("RESIVO", "StaffConsole")
        settings.setValue("general/language", code)
    except Exception as exc:  # noqa: BLE001
        _log.error("Failed to save language setting: %s", exc)


def resolve_startup_language() -> str:
    """Resolve language on startup: saved QSettings -> system locale -> default 'en'."""
    saved = get_saved_language()
    if saved:
        return saved

    try:
        from PySide6.QtCore import QLocale
        sys_lang = QLocale.system().language()
        if sys_lang == QLocale.Language.French:
            return "fr"
    except Exception:  # noqa: BLE001
        pass

    return _DEFAULT_LANG


def _install_qt_translations(app: Any, lang_code: str) -> None:
    """Install qtbase_<lang>.qm into QApplication for native Qt dialog buttons."""
    global _QT_TRANSLATOR
    if app is None or lang_code == "en":
        return

    try:
        from PySide6.QtCore import QLibraryInfo, QTranslator

        translator = QTranslator(app)
        loaded = False

        # 1. Search in PySide6 translations dir
        trans_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if trans_path and translator.load(f"qtbase_{lang_code}", trans_path):
            loaded = True

        # 2. Search in bundled assets/i18n
        if not loaded:
            asset_path = _I18N_DIR.parent / "assets" / "i18n"
            if asset_path.is_dir() and translator.load(f"qtbase_{lang_code}", str(asset_path)):
                loaded = True

        if loaded:
            app.installTranslator(translator)
            _QT_TRANSLATOR = translator
            _log.info("Loaded Qt base translations for '%s'", lang_code)
        else:
            _log.warning("Could not locate qtbase_%s.qm", lang_code)
    except Exception as exc:  # noqa: BLE001
        _log.warning("Failed to install Qt translations: %s", exc)


def init(language: str | None = None, app: Any = None) -> str:
    """Initialize the i18n engine with selected or auto-detected language."""
    global _CURRENT_LANG

    selected = language or resolve_startup_language()
    if selected not in _REGISTRY:
        _log.warning("Unknown language '%s', defaulting to '%s'", selected, _DEFAULT_LANG)
        selected = _DEFAULT_LANG

    _CURRENT_LANG = selected

    # Preload catalogs into memory
    _load_catalog(_FALLBACK_LANG)
    if _CURRENT_LANG != _FALLBACK_LANG:
        _load_catalog(_CURRENT_LANG)

    if app is not None:
        _install_qt_translations(app, _CURRENT_LANG)

    _log.info("i18n initialized. Language: '%s', Pseudo-locale: %s", _CURRENT_LANG, is_pseudo_locale())
    return _CURRENT_LANG
