"""RÉSIVO — Central resource path helper (sys._MEIPASS aware)."""

from __future__ import annotations

import sys
from pathlib import Path


def _frozen_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        roots.append(exe_dir)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            mp = Path(meipass)
            roots.append(mp)
            roots.append(mp / "desktop")
    return roots


def _desktop_source_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def get_asset_path(subpath: str | Path) -> Path:
    """Resolve an asset path taking into account frozen PyInstaller (sys._MEIPASS).

    Supports both directory and file assets across onefile/onedir frozen builds
    and the source development tree.
    """
    sub = Path(subpath)
    candidates: list[Path] = [root / "assets" / sub for root in _frozen_roots()]
    candidates.append(_desktop_source_dir() / "assets" / sub)

    for c in candidates:
        if c.exists():
            return c

    return candidates[-1]


def get_i18n_dir() -> Path:
    """Resolve the translation catalog folder (``desktop/i18n``) across frozen and dev."""
    candidates: list[Path] = []
    for root in _frozen_roots():
        candidates.append(root / "i18n")
        candidates.append(root / "desktop" / "i18n")
    candidates.append(_desktop_source_dir() / "i18n")

    for c in candidates:
        if c.is_dir() and (c / "en.json").is_file():
            return c

    return candidates[-1]


def get_qt_translations_dir(qt_lib_translations: str | None = None) -> Path | None:
    """Locate Qt base translations (``qtbase_*.qm``) across frozen and dev builds."""
    candidates: list[Path] = []
    for root in _frozen_roots():
        candidates.append(root / "translations")
        candidates.append(root / "PySide6" / "translations")
        candidates.append(root / "assets" / "i18n")
    if qt_lib_translations:
        candidates.append(Path(qt_lib_translations))
    candidates.append(_desktop_source_dir() / "assets" / "i18n")

    for c in candidates:
        try:
            if c.is_dir() and any(c.glob("qtbase_*.qm")):
                return c
        except OSError:
            continue
    return None
