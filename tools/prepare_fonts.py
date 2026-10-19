#!/usr/bin/env python3
"""Build the static desktop fonts for RESIVO from the upstream variable fonts.

Outfit 500/600/700 and Inter 400/500/600 as static TTFs, with the name table
normalised so the families are exactly ``Outfit`` and ``Inter`` and each weight
is a distinct style (Qt/DirectWrite group them by typographic family).

    .venv/Scripts/python.exe tools/prepare_fonts.py

The upstream variable fonts and their OFL licences come from google/fonts and
are cached in the system temp directory, so re-running only re-instances.
"""

from __future__ import annotations

import tempfile
import urllib.request
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "desktop" / "assets" / "fonts"
CACHE = Path(tempfile.gettempdir()) / "resivo-fonts"

BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl"
PLAN = (
    {
        "family": "Outfit",
        "url": f"{BASE}/outfit/Outfit%5Bwght%5D.ttf",
        "cache": "Outfit[wght].ttf",
        "license": f"{BASE}/outfit/OFL.txt",
        "instances": (
            (500, "Medium", "Outfit-Medium.ttf"),
            (600, "SemiBold", "Outfit-SemiBold.ttf"),
            (700, "Bold", "Outfit-Bold.ttf"),
        ),
    },
    {
        "family": "Inter",
        "url": f"{BASE}/inter/Inter%5Bopsz,wght%5D.ttf",
        "cache": "Inter[opsz,wght].ttf",
        "license": f"{BASE}/inter/OFL.txt",
        "instances": (
            (400, "Regular", "Inter-Regular.ttf"),
            (500, "Medium", "Inter-Medium.ttf"),
            (600, "SemiBold", "Inter-SemiBold.ttf"),
        ),
    },
)

# name IDs that describe a variable font and must not survive instantiation
DROP_NAMES = (21, 22, 25)


def fetch(url: str, target: Path) -> Path:
    if target.is_file() and target.stat().st_size:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        target.write_bytes(response.read())
    return target


def set_name(font: TTFont, name_id: int, value: str) -> None:
    font["name"].setName(value, name_id, 3, 1, 0x409)  # Windows / Unicode / en-US
    font["name"].setName(value, name_id, 1, 0, 0)  # Macintosh / Roman / en


def rename(font: TTFont, family: str, style: str, ps_name: str) -> None:
    full_name = f"{family} {style}" if style != "Regular" else family
    for name_id in DROP_NAMES:
        font["name"].removeNames(nameID=name_id)
    set_name(font, 1, family)  # Font Family
    set_name(font, 2, style)  # Font Subfamily
    set_name(font, 3, f"{ps_name};RESIVO-static")  # Unique ID
    set_name(font, 4, full_name)  # Full name
    set_name(font, 6, ps_name)  # PostScript name
    set_name(font, 16, family)  # Typographic Family
    set_name(font, 17, style)  # Typographic Subfamily


def weight_flags(font: TTFont, weight: int) -> None:
    os2 = font["OS/2"]
    os2.usWeightClass = weight
    selection = os2.fsSelection & 0x80  # keep USE_TYPO_METRICS, clear the rest
    if weight == 400:
        selection |= 0x40  # REGULAR
    if weight >= 700:
        selection |= 0x20  # BOLD
    os2.fsSelection = selection
    font["head"].macStyle = 0x01 if weight >= 700 else 0x00


def instance(variable: Path, axes: dict[str, float], family: str, style: str, weight: int, target: Path) -> dict:
    font = TTFont(variable)
    font.recalcTimestamp = False  # keep byte-identical output across runs
    instancer.instantiateVariableFont(font, axes, inplace=True, updateFontNames=False)
    ps_name = f"{family}-{style}"
    rename(font, family, style, ps_name)
    weight_flags(font, weight)
    target.parent.mkdir(parents=True, exist_ok=True)
    font.save(target)
    font.close()
    with TTFont(target, lazy=True) as check:
        tables = set(check.keys())
        assert "fvar" not in tables and "gvar" not in tables, f"{target.name} is still variable"
        assert check["name"].getDebugName(1) == family, check["name"].getDebugName(1)
        assert check["name"].getDebugName(2) == style, check["name"].getDebugName(2)
        assert check["name"].getDebugName(6) == ps_name, check["name"].getDebugName(6)
    return {
        "path": target,
        "bytes": target.stat().st_size,
        "family": family,
        "style": style,
        "ps": ps_name,
        "axes": ", ".join(f"{tag}={value:g}" for tag, value in axes.items()),
    }


def main() -> int:
    results = []
    licences = []
    for plan in PLAN:
        variable = fetch(plan["url"], CACHE / plan["cache"])
        for weight, style, filename in plan["instances"]:
            axes = {"wght": float(weight)}
            if plan["family"] == "Inter":
                axes = {"wght": float(weight), "opsz": 14.0}
            results.append(instance(variable, axes, plan["family"], style, weight, OUT_DIR / filename))
        licence = OUT_DIR / f"OFL-{plan['family']}.txt"
        licence.write_bytes(fetch(plan["license"], CACHE / f"OFL-{plan['family']}.txt").read_bytes())
        licences.append(licence)

    print(f"{'file':<32} {'bytes':>9}  {'family':<7} {'style':<9} {'axes':<14} postscript")
    print("-" * 96)
    for item in results:
        print(
            f"{item['path'].relative_to(ROOT).as_posix():<32} {item['bytes']:>9,}  "
            f"{item['family']:<7} {item['style']:<9} {item['axes']:<14} {item['ps']}"
        )
    for licence in licences:
        print(f"{licence.relative_to(ROOT).as_posix():<32} {licence.stat().st_size:>9,}  OFL-1.1 text")
    print("-" * 96)
    print(f"{len(results)} static TTFs + {len(licences)} licences in {OUT_DIR.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
