"""RÉSIVO — Central resource path helper (sys._MEIPASS aware)."""

from __future__ import annotations

import sys
from pathlib import Path


def get_asset_path(subpath: str | Path) -> Path:
    """Resolve an asset path taking into account frozen PyInstaller (sys._MEIPASS).

    Supports both directory and file assets across onefile/onedir frozen builds
    and the source development tree.
    """
    sub = Path(subpath)
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "assets" / sub)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "assets" / sub)
            candidates.append(Path(meipass) / "desktop" / "assets" / sub)

    # Source development tree (desktop/assets/...)
    candidates.append(Path(__file__).resolve().parents[2] / "assets" / sub)

    for c in candidates:
        if c.exists():
            return c

    # Fall back to the dev tree candidate if none exists yet on disk
    return candidates[-1]
