"""RÉSIVO — desktop design tokens, typography and the one global Qt style sheet.

Single source of truth for the desktop visual layer (``docs/DESIGN.md`` §2
colours, §3 typography, §4 shape/space/elevation/motion). No hex value, font
size or shadow may appear anywhere else in the desktop UI.

Public API (stable — page agents code against this)
---------------------------------------------------
``TOKENS: dict[str, str | int]``   flat token map (DESIGN.md §2–§4)
``C(name) -> str``                 token lookup, clear ``KeyError`` on typos
``S(name) -> int``                 token as integer px (spacing/radii/sizes)
``qcolor(name) -> QColor``         token (hex or ``rgba(...)``) as ``QColor``
``load_fonts() -> list[str]``      register bundled Outfit/Inter TTFs (idempotent);
                                   call once *after* the QApplication exists
``font(role) -> QFont``            display / h1 / h2 / h3 / body / muted / small /
                                   overline / nav-badge
``apply_role(widget, role)``       dynamic property ``role`` + QFont + repolish
``enable_tabular(target)``         tabular figures (``tnum``) on a QWidget or QFont
``BUTTON_STYLES: dict[str, str]``  variant -> QSS: primary, accent, secondary,
                                   danger, success, in_progress, filter, ghost
``apply_button_style(btn, key)``   direct variant styling + ``variant`` property
``status_kind(kind) -> str``       normalise any legacy badge kind
``status_tokens(kind) -> dict``    ``{"ink", "bg", "border"}`` token values
``pill_radius(height) -> str``     capsule radius that Qt will actually render
``get_badge_qss(kind, height=None)`` pill QSS for every legacy badge kind
                                   (``height`` for non-standard badge heights)
``apply_elevation(widget, level)`` level 1 = hairline only, level 2 = drop shadow
``DESKTOP_STYLESHEET: str``        the one global style sheet (apply once)

The style sheet template uses ``@token-name`` placeholders substituted from
``TOKENS`` at import time (an f-string cannot hold raw QSS braces). The
``QPushButton[variant="..."]`` rules are generated with real f-strings from
the same specs that back ``BUTTON_STYLES``.

**Qt radius limit (applies to every radius here):** Qt drops a
``border-radius`` that is not strictly smaller than half the box, and renders a
square instead — DESIGN.md's ``9999px`` pill value is therefore clamped to the
capsule radius of the real control (see ``pill_radius``).

Dynamic properties the global sheet reacts to (preferred over inline QSS):
``role`` (display/h1/h2/h3/body/small/muted/overline/nav-badge),
``variant`` (button variants), ``size`` ("sm" buttons), ``state`` ("error" on
inputs, "connected"/"reconnecting"/"offline" on the live dot),
``background`` ("canvas"/"surface" on plain container widgets),
``cardFrame`` (true) on card frames.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QPushButton, QWidget

from .resource import get_asset_path

_log = logging.getLogger("resivo.ui.theme")

# ---------------------------------------------------------------------------
# TOKENS — every colour, size, radius, shadow and duration of the desktop UI.
# This is the only place in the desktop code base where a literal value lives.
# ---------------------------------------------------------------------------
TOKENS: dict[str, str | int] = {
    # -- brand (DESIGN.md §2) ----------------------------------------------
    "navy-900": "#0A2342",
    "navy-800": "#0A2F5A",
    "navy-700": "#0D436F",
    "teal-700": "#0A5866",  # pressed state for teal buttons (added, see report)
    "teal-600": "#0D7180",
    "teal-500": "#109D9A",
    "green-500": "#0CA792",
    "gold-500": "#E5A853",
    "gold-300": "#F1CE92",
    "danger-600": "#B42323",  # danger hover (added, see report)
    "danger-700": "#7F1616",  # danger pressed (added, see report)
    # -- neutrals ------------------------------------------------------------
    "canvas": "#F5F8FB",
    "surface": "#FFFFFF",
    "surface-subtle": "#EDF2F7",
    "border": "#DCE4EE",
    "border-strong": "#C5D0DE",
    "text-primary": "#0B1B33",
    "text-secondary": "#44546A",
    "text-muted": "#5B6B82",
    "text-on-dark": "#E6EDF6",
    "text-on-dark-muted": "#9FB3CC",
    "sidebar-hover": "#10305A",
    "selection-tint": "#E6F2F4",  # table/list selection tint (DESIGN.md §6)
    # -- semantic status (colour + icon + label, never colour alone) ---------
    "status-ok-ink": "#05603A",
    "status-ok-bg": "#E8F7EF",
    "status-ok-border": "#A9E2C4",
    "status-pending-ink": "#8A4B08",
    "status-pending-bg": "#FFF6E5",
    "status-pending-border": "#F3D49B",
    "status-review-ink": "#4338CA",
    "status-review-bg": "#EEF0FF",
    "status-review-border": "#C7CBFA",
    "status-progress-ink": "#174EA6",
    "status-progress-bg": "#EAF1FD",
    "status-progress-border": "#B9D0F7",
    "status-danger-ink": "#9B1C1C",
    "status-danger-bg": "#FDEDED",
    "status-danger-border": "#F5B9B9",
    "status-neutral-ink": "#44546A",
    "status-neutral-bg": "#EDF2F7",
    "status-neutral-border": "#DCE4EE",
    # -- typography (DESIGN.md §3) ------------------------------------------
    "font-display": "Outfit",
    "font-body": "Inter",
    "font-fallback": '"Segoe UI", system-ui, sans-serif',
    "fs-display": "32px", "lh-display": "40px", "fw-display": 700, "tracking-display": "-0.02em",
    "fs-h1": "24px", "lh-h1": "32px", "fw-h1": 600, "tracking-h1": "0em",
    "fs-h2": "18px", "lh-h2": "26px", "fw-h2": 600, "tracking-h2": "0em",
    "fs-h3": "15px", "lh-h3": "22px", "fw-h3": 600, "tracking-h3": "0em",
    "fs-body": "14px", "lh-body": "22px", "fw-body": 400, "tracking-body": "0em",
    "fs-small": "12px", "lh-small": "18px", "fw-small": 500, "tracking-small": "0em",
    "fs-overline": "11px", "lh-overline": "16px", "fw-overline": 600, "tracking-overline": "0.08em",
    "fw-regular": 400, "fw-medium": 500, "fw-semibold": 600, "fw-bold": 700,
    # -- spacing / radii / control sizes (DESIGN.md §4, §6, §7) -------------
    "space-1": "4px",
    "space-2": "8px",
    "space-3": "12px",
    "space-4": "16px",
    "space-6": "24px",
    "space-8": "32px",
    "space-12": "48px",
    "radius-input": "8px",
    "radius-card": "12px",
    "radius-hero": "20px",
    # DESIGN.md §2 says "9999px" for pills; Qt renders a square whenever a
    # border-radius is >= half the box, so the capsule is the half-height of the
    # standard 25px control. Taller pills must use theme.pill_radius(height).
    "radius-pill": "12px",
    # Qt renders a border-radius larger than the widget as a square: the 10px
    # live dot needs a concrete half-size radius, not radius-pill.
    "radius-dot": "5px",
    # Same limit for the 8px-tall progress / occupancy bar.
    "radius-bar": "4px",
    "pill-pad-x": "10px",
    "pill-pad-y": "4px",
    "size-control": "36px",
    "size-row": "44px",
    "size-icon": "20px",
    "size-sidebar": "248px",
    # -- elevation (DESIGN.md §4) -------------------------------------------
    "shadow-e1": "0 1px 2px rgba(10,35,66,0.06)",
    "shadow-e2": "0 8px 24px -8px rgba(10,35,66,0.14)",
    "elevation-2-blur": "24",
    "elevation-2-offset-y": "8",
    "elevation-2-color": "rgba(10,35,66,36)",
    # -- motion (DESIGN.md §4) ----------------------------------------------
    "dur-fast": 150,
    "dur-med": 200,
    "dur-toast": 4000,
    "ease": "ease-out",
    "ease-curve": "OutCubic",
    # -- icon assets --------------------------------------------------------
    "icon-chevron-down": get_asset_path("icons/chevron-down.svg").as_posix(),
    "icon-chevron-down-disabled": get_asset_path("icons/chevron-down-disabled.svg").as_posix(),
    "icon-chevron-up": get_asset_path("icons/chevron-up.svg").as_posix(),
}

_PX_RE = re.compile(r"^(-?\d+(?:\.\d+)?)px$")
_NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
_EM_RE = re.compile(r"^(-?\d+(?:\.\d+)?)em$")
_RGBA_RE = re.compile(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$")


def C(name: str) -> str:
    """Return the raw value of a design token, with a clear error on typos."""
    try:
        return str(TOKENS[name])
    except KeyError:
        raise KeyError(
            f"Unknown design token {name!r}. Add it to TOKENS in "
            f"desktop/app/ui/theme.py (docs/DESIGN.md is the source of truth)."
        ) from None


def S(name: str) -> int:
    """Return a token as integer px (spacing, radii, control sizes)."""
    value = TOKENS.get(name)
    if value is None:
        C(name)  # raise the canonical KeyError message
        raise AssertionError  # pragma: no cover - C always raises here
    if isinstance(value, bool):  # pragma: no cover - defensive
        raise ValueError(f"Token {name!r} is not a length")
    if isinstance(value, int):
        return value
    text = str(value).strip()
    match = _PX_RE.match(text)
    if match:
        return int(round(float(match.group(1))))
    if _NUM_RE.match(text):
        return int(round(float(text)))
    raise ValueError(f"Token {name!r} ({value!r}) is not a px length.")


def qcolor(name: str) -> QColor:
    """Return a token as ``QColor`` (supports ``#RRGGBB`` and ``rgba(...)``)."""
    value = C(name)
    match = _RGBA_RE.match(value)
    if match:
        red, green, blue = (int(match.group(i)) for i in (1, 2, 3))
        alpha_raw = match.group(4)
        if alpha_raw is None:
            alpha = 255
        elif "." in alpha_raw:
            alpha = int(round(float(alpha_raw) * 255))
        else:
            alpha = int(alpha_raw)
        return QColor(red, green, blue, max(0, min(255, alpha)))
    color = QColor(value)
    if not color.isValid():
        raise ValueError(f"Token {name!r} ({value!r}) is not a valid colour.")
    return color


def _em_to_px(tracking: str, font_px: int) -> float:
    """``-0.02em`` at 32px -> -0.64px (Qt letter spacing is absolute px)."""
    match = _EM_RE.match(tracking.strip())
    if not match:
        return 0.0
    return float(match.group(1)) * font_px


# ---------------------------------------------------------------------------
# Fonts — bundled static TTFs in desktop/assets/fonts/
# ---------------------------------------------------------------------------
def _resolve_fonts_dir() -> Path:
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "assets" / "fonts")
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "assets" / "fonts")
            candidates.append(Path(meipass) / "desktop" / "assets" / "fonts")
    candidates.append(Path(__file__).resolve().parents[2] / "assets" / "fonts")
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[-1]


_FONTS_DIR = _resolve_fonts_dir()
_FALLBACK_FAMILIES = ["Segoe UI", "system-ui", "sans-serif"]
_LOADED_FONT_FILES: set[str] = set()
_REGISTERED_FAMILIES: list[str] = []


def load_fonts() -> list[str]:
    """Register every ``*.ttf`` in ``desktop/assets/fonts`` (idempotent).

    Returns the registered family names. Logs (never raises) when a file is
    missing or cannot be loaded; call it once after the QApplication exists.
    """
    global _REGISTERED_FAMILIES
    if QGuiApplication.instance() is None:
        _log.warning("load_fonts() called before QGuiApplication; skipped for now.")
        return []
    if not _FONTS_DIR.is_dir():
        _log.warning("Font directory %s is missing; using system fallbacks.", _FONTS_DIR)
        return list(_REGISTERED_FAMILIES)
    font_files = sorted(_FONTS_DIR.glob("*.ttf"))
    if not font_files:
        _log.warning("No .ttf files in %s; using system fallbacks.", _FONTS_DIR)
        return list(_REGISTERED_FAMILIES)
    for path in font_files:
        key = str(path)
        if key in _LOADED_FONT_FILES:
            continue
        font_id = QFontDatabase.addApplicationFont(key)
        if font_id == -1:
            _log.warning("Could not register font file %s", path.name)
            continue
        _LOADED_FONT_FILES.add(key)
        for family in QFontDatabase.applicationFontFamilies(font_id):
            if family not in _REGISTERED_FAMILIES:
                _REGISTERED_FAMILIES.append(family)
    for expected in ("Outfit", "Inter"):
        if expected not in _REGISTERED_FAMILIES:
            _log.warning("Bundled font family %r was not registered.", expected)
    return list(_REGISTERED_FAMILIES)


# role -> (family token, size token, weight token, tracking token)
_ROLE_SPECS: dict[str, tuple[str, str, str, str]] = {
    "display": ("font-display", "fs-display", "fw-display", "tracking-display"),
    "h1": ("font-display", "fs-h1", "fw-h1", "tracking-h1"),
    "h2": ("font-display", "fs-h2", "fw-h2", "tracking-h2"),
    "h3": ("font-body", "fs-h3", "fw-h3", "tracking-h3"),
    "body": ("font-body", "fs-body", "fw-body", "tracking-body"),
    "muted": ("font-body", "fs-body", "fw-body", "tracking-body"),
    "small": ("font-body", "fs-small", "fw-small", "tracking-small"),
    "overline": ("font-body", "fs-overline", "fw-overline", "tracking-overline"),
    # QSS-only roles are usable through apply_role too (sidebar counter badge).
    "nav-badge": ("font-body", "fs-overline", "fw-semibold", "tracking-overline"),
}


def font(role: str = "body") -> QFont:
    """QFont for a typography role (``display, h1, h2, h3, body, muted, small, overline, nav-badge``)."""
    spec = _ROLE_SPECS.get(role)
    if spec is None:
        raise KeyError(
            f"Unknown font role {role!r}. Known roles: {', '.join(_ROLE_SPECS)}."
        )
    family_token, size_token, weight_token, tracking_token = spec
    qfont = QFont()
    qfont.setFamilies([C(family_token), *_FALLBACK_FAMILIES])
    pixel_size = S(size_token)
    qfont.setPixelSize(pixel_size)
    qfont.setWeight(QFont.Weight(S(weight_token)))
    tracking = C(tracking_token)
    if tracking not in ("0", "0em", "0px"):
        qfont.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, _em_to_px(tracking, pixel_size))
    return qfont


def repolish(widget: QWidget) -> QWidget:
    """Re-evaluate style sheet rules after a dynamic property change."""
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()
    return widget


def apply_role(widget: QWidget, role: str) -> QWidget:
    """Set the ``role`` dynamic property *and* the matching QFont, then repolish."""
    widget.setProperty("role", role)
    widget.setFont(font(role))
    return repolish(widget)


def _set_tnum(qfont: QFont) -> None:
    """Enable tabular figures silently; skip when Qt lacks ``setFeature``."""
    if not hasattr(qfont, "setFeature"):
        return
    try:
        tag = QFont.Tag("tnum") if hasattr(QFont, "Tag") else "tnum"
        qfont.setFeature(tag, 1)
    except Exception:  # pragma: no cover - platform dependent, skip silently
        return


def enable_tabular(target: QWidget | QFont) -> QWidget | QFont:
    """Tabular figures for card IDs, room numbers, counts, dates and tables.

    Accepts a ``QWidget`` (its font is updated in place) or a ``QFont``.
    """
    if isinstance(target, QFont):
        _set_tnum(target)
        return target
    if isinstance(target, QWidget):
        qfont = target.font()
        _set_tnum(qfont)
        target.setFont(qfont)
        return target
    raise TypeError("enable_tabular() expects a QWidget or a QFont.")


# ---------------------------------------------------------------------------
# Buttons — one spec table drives both BUTTON_STYLES and the global variant rules
# ---------------------------------------------------------------------------
_TEAL_FILLED = {
    "fill": "teal-600", "ink": "surface", "border": "teal-600",
    "hover_fill": "teal-500", "hover_border": "teal-500",
    "pressed_fill": "teal-700", "pressed_border": "teal-700",
    "ring": "surface",
}
_BUTTON_SPECS: dict[str, dict[str, str | bool]] = {
    "primary": {
        "fill": "navy-800", "ink": "surface", "border": "navy-800",
        "hover_fill": "navy-700", "hover_border": "navy-700",
        "pressed_fill": "navy-900", "pressed_border": "navy-900",
        "ring": "surface",
    },
    "accent": dict(_TEAL_FILLED),
    "success": dict(_TEAL_FILLED),
    "in_progress": dict(_TEAL_FILLED),
    "danger": {
        "fill": "status-danger-ink", "ink": "surface", "border": "status-danger-ink",
        "hover_fill": "danger-600", "hover_border": "danger-600",
        "pressed_fill": "danger-700", "pressed_border": "danger-700",
        "ring": "surface",
    },
    "secondary": {
        "fill": "surface", "ink": "text-secondary", "border": "border-strong",
        "hover_fill": "surface-subtle", "hover_ink": "text-primary", "hover_border": "border-strong",
        "pressed_fill": "surface-subtle", "pressed_ink": "text-primary", "pressed_border": "border-strong",
        "ring": "teal-600",
    },
    "filter": {
        "fill": "surface", "ink": "text-secondary", "border": "border-strong", "checked": True,
        "hover_fill": "surface-subtle", "hover_ink": "text-primary", "hover_border": "border-strong",
        "pressed_fill": "surface-subtle", "pressed_ink": "text-primary", "pressed_border": "border-strong",
        "ring": "teal-600",
    },
    "ghost": {
        "fill": "transparent", "ink": "text-secondary", "border": "transparent",
        "hover_fill": "surface-subtle", "hover_ink": "text-primary", "hover_border": "surface-subtle",
        "pressed_fill": "surface-subtle", "pressed_ink": "text-primary", "pressed_border": "surface-subtle",
        "ring": "teal-600",
    },
}
_PASSTHROUGH = {"transparent", "none", "currentColor"}


def _t(value: str) -> str:
    """Token value (or CSS keyword passed through untouched)."""
    return value if value in _PASSTHROUGH else C(value)


def _button_qss(spec: dict[str, str | bool], selector: str) -> str:
    """Build the full QSS for one button variant (hover/pressed/focus/disabled)."""
    ink = _t(str(spec["ink"]))
    lines = [
        f"{selector} {{",
        f"    background-color: {_t(str(spec['fill']))};",
        f"    color: {ink};",
        f"    border: 1px solid {_t(str(spec['border']))};",
        f"    border-radius: {C('radius-input')};",
        f"    padding: 8px 16px;",
        f"    min-height: 18px;",
        f"    font-size: {C('fs-body')};",
        f"    font-weight: {C('fw-semibold')};",
        "}",
        f"{selector}:hover {{",
        f"    background-color: {_t(str(spec.get('hover_fill', spec['fill'])))};",
        f"    color: {_t(str(spec.get('hover_ink', spec['ink'])))};",
        f"    border-color: {_t(str(spec.get('hover_border', spec['border'])))};",
        "}",
        f"{selector}:pressed {{",
        f"    background-color: {_t(str(spec.get('pressed_fill', spec['fill'])))};",
        f"    color: {_t(str(spec.get('pressed_ink', spec['ink'])))};",
        f"    border-color: {_t(str(spec.get('pressed_border', spec['border'])))};",
        "}",
        f"{selector}:focus {{",
        f"    border: 2px solid {_t(str(spec['ring']))};",
        "    padding: 7px 15px;",
        "}",
        f"{selector}:disabled {{",
        f"    background-color: {C('surface-subtle')};",
        f"    color: {C('text-muted')};",
        f"    border: 1px solid {C('border')};",
        "    padding: 8px 16px;",
        "}",
        f"{selector}[size=\"sm\"] {{",
        "    padding: 5px 12px;",
        f"    font-size: {C('fs-small')};",
        "    min-height: 14px;",
        "}",
    ]
    if spec.get("checked"):
        lines += [
            f"{selector}:checked {{",
            f"    background-color: {C('surface-subtle')};",
            f"    color: {C('navy-900')};",
            f"    border: 1.5px solid {C('teal-600')};",
            "    padding: 7px 15px;",
            "}",
            f"{selector}:checked:hover {{",
            f"    background-color: {C('selection-tint')};",
            f"    color: {C('navy-900')};",
            f"    border-color: {C('teal-600')};",
            "}",
        ]
    return "\n".join(lines) + "\n"


BUTTON_STYLES: dict[str, str] = {
    key: _button_qss(spec, "QPushButton") for key, spec in _BUTTON_SPECS.items()
}


def apply_button_style(btn: QPushButton, style_key: str = "secondary") -> QPushButton:
    """Apply a variant to a plain ``QPushButton`` (kept for legacy pages).

    Sets the ``variant`` dynamic property (so the global sheet also matches)
    *and* the variant QSS directly, so styling survives inside dialogs with
    their own style sheets. Unknown keys fall back to ``secondary``.
    """
    key = style_key if style_key in BUTTON_STYLES else "secondary"
    btn.setProperty("variant", key)
    btn.setStyleSheet(BUTTON_STYLES[key])
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


# ---------------------------------------------------------------------------
# Status kinds and badge pills
# ---------------------------------------------------------------------------
_BADGE_KINDS: dict[str, str] = {
    # ok — Active, Approved, Resolved, Matched
    "ok": "ok", "approved": "ok", "resolved": "ok", "active": "ok", "success": "ok", "matched": "ok",
    # pending
    "pending": "pending", "warning": "pending",
    # review
    "review": "review", "under_review": "review",
    # progress
    "progress": "progress", "in_progress": "progress", "info": "progress",
    # danger
    "danger": "danger", "rejected": "danger", "error": "danger",
    "urgent": "danger", "not_in_roster": "danger",
    # neutral
    "neutral": "neutral", "neutral_info": "neutral",
}


def status_kind(kind: str) -> str:
    """Normalise any legacy badge kind to ``ok/pending/review/progress/danger/neutral``."""
    return _BADGE_KINDS.get(str(kind), "neutral")


def status_tokens(kind: str) -> dict[str, str]:
    """``{"ink", "bg", "border"}`` token values for a status kind (legacy welcome)."""
    base = status_kind(kind)
    return {
        "ink": C(f"status-{base}-ink"),
        "bg": C(f"status-{base}-bg"),
        "border": C(f"status-{base}-border"),
    }


def pill_radius(height: int) -> str:
    """Capsule border-radius for a control of ``height`` px that Qt will render.

    Qt draws a square when the radius is not smaller than half the box, so the
    DESIGN "9999px" pill value is expressed as half the real control height.
    """
    return f"{max(2, int(height) // 2)}px"


def get_badge_qss(kind: str, height: int | None = None) -> str:
    """Pill QSS for a status badge; accepts every legacy badge kind.

    ``height`` is the badge's rendered height in px when it differs from the
    standard 25px pill (Qt drops a radius larger than half the box).
    """
    tokens = status_tokens(kind)
    radius = pill_radius(height) if height else C("radius-pill")
    return (
        f"color: {tokens['ink']};"
        f" background-color: {tokens['bg']};"
        f" border: 1px solid {tokens['border']};"
        f" border-radius: {radius};"
        f" padding: {C('pill-pad-y')} {C('pill-pad-x')};"
        f" font-size: {C('fs-small')};"
        f" font-weight: {C('fw-semibold')};"
    )


# ---------------------------------------------------------------------------
# Elevation (QSS has no box-shadow; cards get a hairline, dialogs a real shadow)
# ---------------------------------------------------------------------------
def apply_elevation(widget: QWidget, level: int = 1) -> QWidget:
    """level 1 → hairline border only (no effect); level 2 → soft drop shadow.

    ``e2`` (blur 24, offset 0/8, rgba(10,35,66,36)) is used sparingly: dialogs,
    popovers and toasts only — never on cards or tables.
    """
    if level <= 1:
        widget.setGraphicsEffect(None)
        return widget
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(S("elevation-2-blur"))
    shadow.setOffset(0, S("elevation-2-offset-y"))
    shadow.setColor(qcolor("elevation-2-color"))
    widget.setGraphicsEffect(shadow)
    return widget


# ---------------------------------------------------------------------------
# The one global style sheet. Authored with @token placeholders; @name is
# substituted from TOKENS at import time (see _substitute()).
# ---------------------------------------------------------------------------
_SHEET = """
/* ===========================================================================
   1. Base — canvas surfaces and typography
   =========================================================================== */

QWidget {
    font-family: "Inter";
    font-size: @fs-body;
    color: @text-primary;
}

QMainWindow, QDialog, QStackedWidget, QSplitter {
    background-color: @canvas;
}

QLabel {
    background: transparent;
}

/* Opt-in backgrounds for plain containers (dynamic property). */
QWidget[background="canvas"] { background-color: @canvas; }
QWidget[background="surface"] { background-color: @surface; }
QWidget#sidebarContainer, QWidget#sidebarFooter { background-color: @navy-900; }

/* --- text roles (set the dynamic property via theme.apply_role) ---------- */
QLabel[role="display"] {
    font-family: "Outfit"; font-size: @fs-display; font-weight: @fw-display;
    color: @text-primary; letter-spacing: @tracking-display;
}
QLabel[role="h1"] {
    font-family: "Outfit"; font-size: @fs-h1; font-weight: @fw-h1; color: @text-primary;
}
QLabel[role="h2"] {
    font-family: "Outfit"; font-size: @fs-h2; font-weight: @fw-h2; color: @text-primary;
}
QLabel[role="h3"] {
    font-family: "Inter"; font-size: @fs-h3; font-weight: @fw-h3; color: @text-primary;
}
QLabel[role="body"] { font-size: @fs-body; color: @text-primary; }
QLabel[role="small"] { font-size: @fs-small; font-weight: @fw-small; color: @text-secondary; }
QLabel[role="muted"] { font-size: @fs-body; color: @text-secondary; }
/* Advisory: Qt ignores letter-spacing / text-transform in QSS; real tracking is
   applied by theme.font(). Headers are uppercased by configure_table(). */
QLabel[role="overline"] {
    font-size: @fs-overline; font-weight: @fw-overline; color: @text-muted;
    letter-spacing: @tracking-overline; text-transform: uppercase;
}
/* Small gold-on-navy counter pill for sidebar nav items (≈18px tall: r8 badge). */
QLabel[role="nav-badge"] {
    background-color: @gold-500; color: @navy-900; border-radius: @radius-input;
    padding: 1px 7px; font-size: @fs-overline; font-weight: @fw-semibold;
}
QLabel[role="error"] { color: @status-danger-ink; font-size: @fs-small; font-weight: @fw-medium; }

/* ===========================================================================
   2. Buttons — defaults + variant rules (generated from _BUTTON_SPECS)
   =========================================================================== */

QPushButton {
    background-color: @surface;
    color: @text-secondary;
    border: 1px solid @border-strong;
    border-radius: @radius-input;
    padding: 8px 16px;
    min-height: 18px;
    font-size: @fs-body;
    font-weight: @fw-semibold;
}
QPushButton:hover { background-color: @surface-subtle; color: @text-primary; }
QPushButton:pressed { background-color: @surface-subtle; color: @text-primary; }
QPushButton:focus { border: 2px solid @teal-600; padding: 7px 15px; }
QPushButton:disabled {
    background-color: @surface-subtle; color: @text-muted; border: 1px solid @border;
}
QPushButton#signOutButton { text-align: left; padding: 8px 12px; }

/* ===========================================================================
   3. Inputs and form controls (36px tall, 8px radius, teal focus ring)
   =========================================================================== */

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
QDateEdit, QTimeEdit, QDateTimeEdit {
    background-color: @surface;
    color: @text-primary;
    border: 1px solid @border;
    border-radius: @radius-input;
    padding: 5px 12px;
    min-height: 24px;
    font-size: @fs-body;
    selection-background-color: @selection-tint;
    selection-color: @navy-900;
}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover,
QSpinBox:hover, QDoubleSpinBox:hover, QDateEdit:hover, QTimeEdit:hover,
QDateTimeEdit:hover {
    border-color: @border-strong;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTimeEdit:focus,
QDateTimeEdit:focus {
    border: 2px solid @teal-600;
    padding: 4px 11px;
}
QLineEdit[state="error"], QTextEdit[state="error"], QPlainTextEdit[state="error"],
QComboBox[state="error"], QSpinBox[state="error"], QDateEdit[state="error"] {
    border-color: @status-danger-border;
    background-color: @status-danger-bg;
}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled, QDateEdit:disabled, QTimeEdit:disabled,
QDateTimeEdit:disabled {
    background-color: @surface-subtle; color: @text-muted; border-color: @border;
}
QLineEdit:read-only { background-color: @surface-subtle; color: @text-secondary; }
QComboBox, QDateEdit, QTimeEdit, QDateTimeEdit {
    padding-right: 32px;
}
QComboBox::drop-down, QDateEdit::drop-down, QTimeEdit::drop-down, QDateTimeEdit::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    border: none;
    background: transparent;
}
QComboBox::down-arrow, QDateEdit::down-arrow, QTimeEdit::down-arrow, QDateTimeEdit::down-arrow {
    image: url(@icon-chevron-down);
    width: 14px;
    height: 14px;
}
QComboBox::down-arrow:disabled, QDateEdit::down-arrow:disabled, QTimeEdit::down-arrow:disabled, QDateTimeEdit::down-arrow:disabled {
    image: url(@icon-chevron-down-disabled);
    width: 14px;
    height: 14px;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid @border;
    border-bottom: 1px solid @border;
    background-color: @surface-subtle;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
    background-color: @border;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url(@icon-chevron-up);
    width: 10px;
    height: 10px;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid @border;
    background-color: @surface-subtle;
}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: @border;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url(@icon-chevron-down);
    width: 10px;
    height: 10px;
}
NumberStepper {
    background-color: @surface;
    border: 1px solid @border;
    border-radius: @radius-input;
    min-height: 40px;
    max-height: 40px;
}
NumberStepper:hover {
    border-color: @border-strong;
}
NumberStepper[focused="true"] {
    border: 2px solid @teal-600;
}
NumberStepper:disabled {
    background-color: @surface-subtle;
    border-color: @border;
}
QComboBox QAbstractItemView {
    background-color: @surface;
    color: @text-primary;
    border: 1px solid @border;
    border-radius: @radius-input;
    padding: 4px;
    outline: none;
    selection-background-color: @selection-tint;
    selection-color: @navy-900;
}

/* ===========================================================================
   4. Tables — sticky overline header, 44px rows, no gridlines
   =========================================================================== */

QTableWidget, QTableView {
    background-color: @surface;
    alternate-background-color: @surface;
    border: 1px solid @border;
    border-radius: @radius-card;
    gridline-color: @border;
    outline: none;
    font-size: @fs-body;
    selection-background-color: @selection-tint;
    selection-color: @navy-900;
}
QTableWidget::item, QTableView::item {
    height: @size-row;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid @border;
    color: @text-primary;
}
QTableWidget::item:hover, QTableView::item:hover { background-color: @surface-subtle; }
QTableWidget::item:selected, QTableView::item:selected {
    background-color: @selection-tint;
    color: @navy-900;
}
QHeaderView { background-color: @surface-subtle; border: none; }
QHeaderView::section {
    background-color: @surface-subtle;
    color: @text-muted;
    font-size: @fs-overline;
    font-weight: @fw-overline;
    letter-spacing: @tracking-overline;
    text-transform: uppercase;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid @border;
    border-right: 1px solid @border;
}
QHeaderView::section:last { border-right: none; }
QHeaderView::section:hover { color: @text-secondary; }
QTableCornerButton::section { background-color: @surface-subtle; border: none; border-bottom: 1px solid @border; }

/* ===========================================================================
   5. Lists — generic list/tree widgets and the sidebar navigation
   =========================================================================== */

QListWidget, QTreeWidget, QListView, QTreeView, QListWidget::item, QTreeWidget::item {
    font-size: @fs-body;
}
QListWidget, QTreeWidget {
    background-color: @surface;
    border: 1px solid @border;
    border-radius: @radius-input;
    outline: none;
    padding: 4px;
}
QListWidget::item, QTreeWidget::item { padding: 6px 8px; border-radius: @radius-input; }
QListWidget::item:hover, QTreeWidget::item:hover { background-color: @surface-subtle; }
QListWidget::item:selected, QTreeWidget::item:selected { background-color: @selection-tint; color: @navy-900; }
QListView {
    background-color: @surface;
    border: 1px solid @border;
    border-radius: @radius-input;
    outline: none;
}
QListView::item { padding: 6px 8px; border-radius: @radius-input; }
QListView::item:hover { background-color: @surface-subtle; }
QListView::item:selected { background-color: @selection-tint; color: @navy-900; }

/* --- sidebar navigation (desktop shell §7) ------------------------------- */
QListWidget#sidebarNav {
    background-color: @navy-900;
    border: none;
    outline: none;
    padding: @space-2;
}
QListWidget#sidebarNav::item {
    color: @text-on-dark-muted;
    height: 40px;
    padding-left: @space-3;
    padding-right: @space-3;
    margin-bottom: @space-1;
    border-radius: @radius-input;
    font-weight: @fw-medium;
}
QListWidget#sidebarNav::item:hover { background-color: @sidebar-hover; color: @text-on-dark; }
QListWidget#sidebarNav::item:selected {
    background-color: @navy-800;
    color: @surface;
    font-weight: @fw-semibold;
    border-left: 2px solid @gold-500;
}

/* ===========================================================================
   6. Scroll areas, scrollbars, splitters
   =========================================================================== */

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QAbstractScrollArea::corner { background: transparent; border: none; }

QScrollBar:vertical { background: transparent; width: 8px; margin: 0px; border: none; }
QScrollBar::handle:vertical {
    background-color: @border-strong; border-radius: 4px; min-height: 32px; margin: 1px;
}
QScrollBar::handle:vertical:hover { background-color: @text-muted; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 0px; border: none; }
QScrollBar::handle:horizontal {
    background-color: @border-strong; border-radius: 4px; min-width: 32px; margin: 1px;
}
QScrollBar::handle:horizontal:hover { background-color: @text-muted; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; background: transparent; border: none; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QSplitter::handle { background-color: transparent; width: 2px; height: 2px; }
QSplitter::handle:hover { background-color: @selection-tint; }
QSplitter::handle:pressed { background-color: @teal-600; }

/* ===========================================================================
   7. Menus, tooltips, popups
   =========================================================================== */

QToolTip {
    background-color: @navy-900;
    color: @text-on-dark;
    border: 1px solid @navy-700;
    border-radius: @radius-input;
    padding: 6px 10px;
    font-size: @fs-small;
}
QMenu {
    background-color: @surface;
    color: @text-primary;
    border: 1px solid @border;
    border-radius: @radius-input;
    padding: 4px;
}
QMenu::item { padding: 7px 28px 7px 12px; border-radius: @radius-input; }
QMenu::item:selected { background-color: @selection-tint; color: @navy-900; }
QMenu::item:disabled { color: @text-muted; }
QMenu::separator { height: 1px; background-color: @border; margin: 4px 8px; }

/* ===========================================================================
   8. Tabs, status bar, progress, checkboxes, sliders
   =========================================================================== */

QTabWidget::pane { background-color: @surface; border: 1px solid @border; border-radius: @radius-card; top: -1px; }
QTabBar::tab {
    background-color: @surface;
    color: @text-secondary;
    border: 1px solid @border-strong;
    border-radius: @radius-input;
    padding: 7px 14px;
    margin-right: @space-1;
    font-size: @fs-body;
    font-weight: @fw-semibold;
}
QTabBar::tab:hover { background-color: @surface-subtle; color: @text-primary; }
QTabBar::tab:selected {
    background-color: @surface-subtle;
    color: @navy-900;
    border: 1.5px solid @teal-600;
    padding: 6.5px 13.5px;
}
QTabBar::tab:disabled { color: @text-muted; background-color: @surface-subtle; }

QStatusBar {
    background-color: @surface;
    color: @text-secondary;
    border-top: 1px solid @border;
    font-size: @fs-small;
    padding: 4px 12px;
}
QStatusBar::item { border: none; }

QProgressBar {
    background-color: @surface-subtle;
    border: none;
    border-radius: @radius-bar;
    height: 8px;
    text-align: center;
    color: @text-primary;
    font-size: @fs-small;
}
QProgressBar::chunk { background-color: @teal-500; border-radius: @radius-bar; }

QCheckBox, QRadioButton { color: @text-primary; font-size: @fs-body; spacing: @space-2; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 18px; height: 18px;
    border: 1px solid @border-strong;
    background-color: @surface;
}
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator { border-radius: 9px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: @teal-600; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: @teal-600; border-color: @teal-600;
}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {
    background-color: @surface-subtle; border-color: @border;
}

QSlider::groove:horizontal { background-color: @surface-subtle; height: 4px; border-radius: 2px; }
QSlider::sub-page:horizontal { background-color: @teal-500; border-radius: 2px; }
QSlider::handle:horizontal {
    background-color: @surface; border: 2px solid @teal-600; width: 14px; height: 14px;
    margin: -6px 0; border-radius: 8px;
}
QSlider::groove:vertical { background-color: @surface-subtle; width: 4px; border-radius: 2px; }
QSlider::handle:vertical {
    background-color: @surface; border: 2px solid @teal-600; width: 14px; height: 14px;
    margin: 0 -6px; border-radius: 8px;
}

/* ===========================================================================
   9. Frames — cards, heroes, live dot, group boxes
   =========================================================================== */

QFrame#cardFrame, QFrame[cardFrame="true"] {
    background-color: @surface;
    border: 1px solid @border;
    border-radius: @radius-card;
}
QFrame[role="hero"] {
    background-color: @surface;
    border: 1px solid @border;
    border-radius: @radius-hero;
}
QFrame#gradientHero {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 @navy-800, stop:0.55 @teal-600, stop:1 @green-500);
    border: none;
    border-radius: @radius-hero;
}
QFrame[role="separator"], QFrame[separator="true"] { background-color: @border; border: none; max-height: 1px; }

QLabel#liveDot, QLabel#liveDotOn, QLabel#liveDotOff, QLabel[role="live-dot"] {
    border-radius: @radius-dot;
}
QLabel#liveDotOn { background-color: @teal-500; }
QLabel#liveDotOff { background-color: @status-danger-ink; }
QLabel#liveDot { background-color: @status-danger-ink; }
QLabel#liveDot[state="connected"] { background-color: @teal-500; }
QLabel#liveDot[state="reconnecting"] { background-color: @gold-500; }
QLabel#liveDot[state="offline"] { background-color: @status-danger-ink; }

QGroupBox {
    background-color: @surface;
    border: 1px solid @border;
    border-radius: @radius-card;
    margin-top: @space-3;
    padding: @space-4 @space-3 @space-3 @space-3;
    font-size: @fs-body;
    font-weight: @fw-semibold;
}
QGroupBox::title { subcontrol-origin: margin; left: @space-3; padding: 0 4px; color: @text-secondary; }

/* ===========================================================================
   10. Misc — message boxes, calendar, tool buttons
   =========================================================================== */

QMessageBox { background-color: @surface; }
QMessageBox QLabel { color: @text-primary; font-size: @fs-body; }

QCalendarWidget QWidget { background-color: @surface; color: @text-primary; }
QCalendarWidget QToolButton { background-color: transparent; color: @text-primary; padding: 4px 8px; }
QCalendarWidget QToolButton:hover { background-color: @surface-subtle; }
QCalendarWidget QAbstractItemView:enabled {
    background-color: @surface;
    color: @text-primary;
    selection-background-color: @teal-600;
    selection-color: @surface;
    outline: none;
}
QCalendarWidget QAbstractItemView:disabled { color: @text-muted; }

QToolButton {
    background-color: transparent;
    color: @text-secondary;
    border: 1px solid transparent;
    border-radius: @radius-input;
    padding: 5px 8px;
    font-size: @fs-body;
}
QToolButton:hover { background-color: @surface-subtle; color: @text-primary; }
QToolButton:pressed { background-color: @surface-subtle; }
QToolButton:checked {
    background-color: @surface-subtle; color: @navy-900; border: 1.5px solid @teal-600;
}
QToolButton:disabled { color: @text-muted; }
"""

_TOKEN_PLACEHOLDER_RE = re.compile(r"@([a-z][a-z0-9-]*)")


def _substitute(template: str) -> str:
    """Replace ``@token-name`` placeholders with TOKENS values."""

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        try:
            return C(name)
        except KeyError:
            raise KeyError(f"Style sheet placeholder '@{name}' is not a known token.") from None

    return _TOKEN_PLACEHOLDER_RE.sub(replace, template)


_DESKTOP_VARIANTS = "\n".join(
    _button_qss(spec, f'QPushButton[variant="{key}"]') for key, spec in _BUTTON_SPECS.items()
)

DESKTOP_STYLESHEET: str = (
    _substitute(_SHEET)
    + "\n/* ===========================================================================\n"
    "   11. Button variants — generated from _BUTTON_SPECS (BUTTON_STYLES)\n"
    "   =========================================================================== */\n"
    + _DESKTOP_VARIANTS
)

