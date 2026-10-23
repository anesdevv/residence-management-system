"""RÉSIVO — the one authored icon set for the desktop console (DESIGN.md §5).

Lucide-style, 24px grid, ``stroke-width="1.75"``, round caps/joins, no fills.
Colour is applied by replacing ``currentColor`` before rendering, so icons
recolour cleanly at any size and stay crisp on HiDPI screens.

Public API (stable — page agents code against this)
---------------------------------------------------
``SVG_CATALOG: dict[str, str]``   name -> raw SVG (canonical names + legacy aliases)
``svg(name) -> str``              raw SVG string (unknown name -> ``dashboard``)
``names() -> list[str]``          every renderable name, sorted
``get_pixmap(name, size=20, color=None) -> QPixmap``  DPR-aware pixmap
``get_icon(name, size=20, color=None) -> QIcon``      icon wrapper

Legacy names keep working forever: crest, overview, pending, residents, rooms,
maintenance, room_changes, official_list, staff_accounts, cross, alert, logout,
login, swap, door.
"""

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from .theme import TOKENS

# Recolouring works by string replacement; keep the marker literally "currentColor".
_STROKE_COLOR = "currentColor"


def _svg(*body: str) -> str:
    """Wrap path data in the shared 24px-grid frame."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{_STROKE_COLOR}" stroke-width="1.75" stroke-linecap="round" '
        f'stroke-linejoin="round">{"".join(body)}</svg>'
    )


# ---------------------------------------------------------------------------
# Canonical set (DESIGN.md §5). One line per icon: authored paths on a 24px grid.
# ---------------------------------------------------------------------------
SVG_CATALOG: dict[str, str] = {
    "dashboard": _svg(
        '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/>'
        '<rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>'
    ),
    "users": _svg(
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
        '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
    ),
    "user": _svg(
        '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'
    ),
    "user-check": _svg(
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
        '<path d="m16 11 2 2 4-4"/>'
    ),
    "building": _svg(
        '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4"/>'
        '<path d="M8 6h.01"/><path d="M12 6h.01"/><path d="M16 6h.01"/><path d="M8 10h.01"/>'
        '<path d="M12 10h.01"/><path d="M16 10h.01"/><path d="M8 14h.01"/><path d="M12 14h.01"/>'
        '<path d="M16 14h.01"/>'
    ),
    "bed": _svg(
        '<path d="M2 4v16"/><path d="M2 8h18a2 2 0 0 1 2 2v10"/><path d="M2 17h20"/><path d="M6 8v9"/>'
    ),
    "wrench": _svg(
        '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94'
        'l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>'
    ),
    "image": _svg(
        '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/>'
        '<path d="m21 15-3.09-3.09a2 2 0 0 0-2.82 0L6 21"/>'
    ),
    "arrow-left-right": _svg(
        '<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="m16 21 4-4-4-4"/><path d="M20 17H4"/>'
    ),
    "file-spreadsheet": _svg(
        '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/>'
        '<path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M8 13h2"/><path d="M14 13h2"/>'
        '<path d="M8 17h2"/><path d="M14 17h2"/>'
    ),
    "shield": _svg(
        '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1'
        'c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>'
    ),
    "log-out": _svg(
        '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/>'
        '<line x1="21" y1="12" x2="9" y2="12"/>'
    ),
    "log-in": _svg(
        '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/>'
        '<line x1="15" y1="12" x2="3" y2="12"/>'
    ),
    "search": _svg(
        '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>'
    ),
    "filter": _svg(
        '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>'
    ),
    "plus": _svg(
        '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>'
    ),
    "minus": _svg('<line x1="5" y1="12" x2="19" y2="12"/>'),
    "trash": _svg(
        '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>'
        '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/>'
        '<line x1="14" y1="11" x2="14" y2="17"/>'
    ),
    "check": _svg('<polyline points="20 6 9 17 4 12"/>'),
    "x": _svg(
        '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>'
    ),
    "alert-triangle": _svg(
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>'
        '<line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'
    ),
    "clock": _svg(
        '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'
    ),
    "bell": _svg(
        '<path d="M10.27 21a2 2 0 0 0 3.46 0"/><path d="M3.26 15.33A1 1 0 0 0 4 17h16a1 1 0 0 0 '
        '.74-1.67C19.41 13.96 18 12.5 18 8A6 6 0 0 0 6 8c0 4.5-1.41 5.96-2.74 7.33"/>'
    ),
    "refresh": _svg(
        '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>'
        '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>'
    ),
    "chevron-right": _svg('<path d="m9 18 6-6-6-6"/>'),
    "chevron-down": _svg('<path d="m6 9 6 6 6-6"/>'),
    "chevron-left": _svg('<path d="m15 18-6-6 6-6"/>'),
    "zoom-in": _svg(
        '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>'
        '<line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/>'
    ),
    "zoom-out": _svg(
        '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>'
        '<line x1="8" y1="11" x2="14" y2="11"/>'
    ),
    "maximize": _svg(
        '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/>'
        '<path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>'
    ),
    "upload": _svg(
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/>'
        '<line x1="12" y1="3" x2="12" y2="15"/>'
    ),
    "mail": _svg(
        '<rect x="2" y="4" width="20" height="16" rx="2"/>'
        '<path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>'
    ),
    "phone": _svg(
        '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 '
        '19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 '
        '2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 '
        '12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>'
    ),
    "id-card": _svg(
        '<rect x="2" y="5" width="20" height="14" rx="2"/><circle cx="9" cy="11" r="2"/>'
        '<path d="M6.17 15a3 3 0 0 1 5.66 0"/><path d="M16 10h2"/><path d="M16 14h2"/>'
    ),
    "settings": _svg(
        '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 '
        '0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 '
        '0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 '
        '0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 '
        '2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 '
        '2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 '
        '2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 '
        '2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 '
        '2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>'
    ),
    "key": _svg(
        '<path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4"/>'
        '<path d="m21 2-9.6 9.6"/><circle cx="7.5" cy="15.5" r="5.5"/>'
    ),
    "lock": _svg(
        '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
    ),
    "info": _svg(
        '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/>'
        '<line x1="12" y1="8" x2="12.01" y2="8"/>'
    ),
    "qr": _svg(
        '<rect x="3" y="3" width="5" height="5" rx="1"/><rect x="16" y="3" width="5" height="5" rx="1"/>'
        '<rect x="3" y="16" width="5" height="5" rx="1"/><path d="M21 16h-3a2 2 0 0 0-2 2v3"/>'
        '<path d="M21 21v.01"/><path d="M12 7v3a2 2 0 0 1-2 2H7"/><path d="M3 12h.01"/>'
        '<path d="M12 3h.01"/><path d="M12 16v.01"/><path d="M16 12h1"/><path d="M21 12v.01"/>'
        '<path d="M12 21v-1"/>'
    ),
    "calendar": _svg(
        '<path d="M8 2v4"/><path d="M16 2v4"/><rect x="3" y="4" width="18" height="18" rx="2"/>'
        '<path d="M3 10h18"/>'
    ),
    "map-pin": _svg(
        '<path d="M20 10c0 4.99-5.54 10.19-7.4 11.8a1 1 0 0 1-1.2 0C9.54 20.19 4 14.99 4 10a8 8 0 0 1 16 0"/>'
        '<circle cx="12" cy="10" r="3"/>'
    ),
    "edit": _svg(
        '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>'
        '<path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>'
    ),
    "copy": _svg(
        '<rect x="8" y="8" width="14" height="14" rx="2"/>'
        '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>'
    ),
    "download": _svg(
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/>'
        '<line x1="12" y1="15" x2="12" y2="3"/>'
    ),
    "external-link": _svg(
        '<path d="M15 3h6v6"/><path d="M10 14 21 3"/>'
        '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
    ),
    "home": _svg(
        '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
        '<polyline points="9 22 9 12 15 12 15 22"/>'
    ),
    "menu": _svg(
        '<line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/>'
        '<line x1="4" y1="18" x2="20" y2="18"/>'
    ),
    "droplet": _svg(
        '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>'
    ),
    "zap": _svg(
        '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 '
        '1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>'
    ),
    "hammer": _svg(
        '<path d="m15 12-8.37 8.37a2.12 2.12 0 1 1-3-3L12 9"/><path d="m18 15 4-4"/>'
        '<path d="m21.5 11.5-1.91-1.91A2 2 0 0 1 19 8.17V7l-2.26-2.26a6 6 0 0 0-4.2-1.76L9 2.96l.92.82A6.18 '
        '6.18 0 0 1 12 8.4V10l2 2h1.17a2 2 0 0 1 1.41.59L18.5 14.5"/>'
    ),
    "wifi": _svg(
        '<path d="M12 20h.01"/><path d="M8.5 16.43a5 5 0 0 1 7 0"/><path d="M5 12.86a10 10 0 0 1 14 0"/>'
        '<path d="M2 8.82a15 15 0 0 1 20 0"/>'
    ),
    "eye": _svg(
        '<path d="M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-19.88 0"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "eye-off": _svg(
        '<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/>'
        '<path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/>'
        '<path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/>'
        '<line x1="2" y1="2" x2="22" y2="22"/>'
    ),
    "check-circle": _svg(
        '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>'
    ),
    "x-circle": _svg(
        '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>'
    ),
    "arrow-right": _svg('<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>'),
    "shield-check": _svg(
        '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1'
        'c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>'
        '<path d="m9 12 2 2 4-4"/>'
    ),
    "file-text": _svg(
        '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/>'
        '<path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>'
    ),
    "sun": _svg(
        '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/>'
        '<path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/>'
        '<path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>'
    ),
    "moon": _svg('<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9"/>'),
}

# Legacy names (DESIGN.md §5) — aliases, never removed.
_ALIASES: dict[str, str] = {
    "crest": "shield",
    "overview": "dashboard",
    "pending": "clock",
    "residents": "users",
    "rooms": "bed",
    "door": "bed",
    "maintenance": "wrench",
    "room_changes": "arrow-left-right",
    "swap": "arrow-left-right",
    "official_list": "file-spreadsheet",
    "staff_accounts": "shield-check",
    "cross": "x",
    "alert": "alert-triangle",
    "logout": "log-out",
    "login": "log-in",
}

for _alias, _canonical in _ALIASES.items():
    SVG_CATALOG[_alias] = SVG_CATALOG[_canonical]


def names() -> list[str]:
    """Every renderable icon name (canonical + legacy aliases), sorted."""
    return sorted(SVG_CATALOG)


def svg(name: str) -> str:
    """Raw SVG markup for ``name``; unknown names fall back to ``dashboard``."""
    return SVG_CATALOG.get(name) or SVG_CATALOG["dashboard"]


def _device_pixel_ratio() -> float:
    app = QGuiApplication.instance()
    if app is None:
        return 1.0
    screen = app.primaryScreen()
    if screen is None:
        return 1.0
    return float(screen.devicePixelRatio()) or 1.0


def get_pixmap(name: str, size: int = 20, color: str | None = None) -> QPixmap:
    """Icon pixmap at ``size`` logical px, rendered for the current HiDPI scale.

    ``color`` defaults to ``TOKENS["text-secondary"]``; unknown names and any
    rendering issue fall back to the dashboard icon (never raises).
    """
    paint_color = color or str(TOKENS["text-secondary"])
    markup = svg(name).replace(_STROKE_COLOR, paint_color)
    ratio = _device_pixel_ratio()
    side = max(1, int(round(size * ratio)))
    pixmap = QPixmap(side, side)
    pixmap.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(markup.encode("utf-8")))
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        renderer.render(painter)
    finally:
        painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def get_icon(name: str, size: int = 20, color: str | None = None) -> QIcon:
    """``QIcon`` for ``name`` (recoloured ``QSvgRenderer`` pixmap, HiDPI aware)."""
    return QIcon(get_pixmap(name, size=size, color=color))
