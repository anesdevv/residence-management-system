#!/usr/bin/env python3
"""Generate multi-size Windows icon desktop/assets/brand/resivo.ico.

Sizes: 16, 24, 32, 48, 64, 128, 256 px.
Source: desktop/assets/brand/resivo_mark.png (or cropped from resivo_logo_transparent.png).
The art is tightly cropped on a transparent background and squared so it stays crisp at all scales.
"""

from __future__ import annotations

import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MARK_PNG = ROOT / "desktop" / "assets" / "brand" / "resivo_mark.png"
LOGO_PNG = ROOT / "desktop" / "assets" / "brand" / "resivo_logo_transparent.png"
TARGET_ICO = ROOT / "desktop" / "assets" / "brand" / "resivo.ico"

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def get_source_mark() -> Image.Image:
    """Load the mark PNG, or crop it from the transparent master logo if missing."""
    if MARK_PNG.is_file():
        im = Image.open(MARK_PNG).convert("RGBA")
    elif LOGO_PNG.is_file():
        logo = Image.open(LOGO_PNG).convert("RGBA")
        # Approximate mark bounds: upper section of the stacked logo
        box = (344, 203, 965, 778)
        im = logo.crop(box)
    else:
        raise FileNotFoundError(f"Neither {MARK_PNG} nor {LOGO_PNG} found")

    # Tight crop around visible alpha pixels
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)

    # Pad onto a square transparent canvas centered so aspect ratio is preserved
    w, h = im.size
    max_dim = max(w, h)
    canvas = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
    canvas.paste(im, ((max_dim - w) // 2, (max_dim - h) // 2))
    return canvas


def generate_ico(output_path: Path = TARGET_ICO) -> list[int]:
    """Generate the multi-resolution ICO file."""
    canvas = get_source_mark()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="ICO", sizes=ICO_SIZES)

    with Image.open(output_path) as probe:
        present = sorted(w for w, _ in probe.ico.sizes())
    return present


def main() -> int:
    present = generate_ico(TARGET_ICO)
    print(f"Generated {TARGET_ICO} with sizes: {present}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
