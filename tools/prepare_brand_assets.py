#!/usr/bin/env python3
"""Generate the derived RESIVO brand assets from the master logo.

Source of truth: ``docs/resivo_logo_transparent.png`` (1254x1254 RGBA,
stacked layout: mark on top, wordmark below).  Every derived file listed in
``docs/DESIGN.md`` section 1 is produced here -- never hand-edit them.

The script is deterministic and idempotent: re-running it produces
byte-identical files.  It only needs Pillow.

    python tools/prepare_brand_assets.py

Outputs
    desktop/assets/brand/  resivo_logo_transparent.png, resivo_mark.png,
                           resivo_logo.png, resivo_mark_white.png,
                           resivo_logo_white.png, resivo.ico
    web/public/brand/      the five PNGs (same bytes as the desktop copies)
    web/public/            favicon.ico, favicon-32.png, favicon.svg,
                           resivo-logo.svg
"""

from __future__ import annotations

import base64
import io
import shutil
import struct
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "resivo_logo_transparent.png"

DESKTOP_BRAND = ROOT / "desktop" / "assets" / "brand"
WEB_BRAND = ROOT / "web" / "public" / "brand"
WEB_PUBLIC = ROOT / "web" / "public"

# Measurements of the master file, verified from its alpha channel.  The script
# recomputes them and only asserts they are close (see TOLERANCE).
EXPECTED = {
    "full ink rows": (203, 1054),
    "full ink cols": (137, 1125),
    "mark rows": (203, 777),
    "mark cols": (344, 964),
    "mark size (w x h)": (621, 575),
    "mark/wordmark gap rows": (778, 806),
}
TOLERANCE = 2  # px; anything further off means the master file changed

PAD_RATIO = 0.02  # ~2% breathing room on the tight crops
ICO_SIZES = (16, 32, 48, 64, 128, 256)
FAVICON_PX = 32
LOGO_SVG_WIDTH = 512

INK = Image.Resampling.LANCZOS


# --------------------------------------------------------------------------- #
# measurement helpers
# --------------------------------------------------------------------------- #
def ink_rows(image: Image.Image) -> list[tuple[int, int]]:
    """Contiguous row bands that contain at least one visible pixel."""
    alpha = image.getchannel("A")
    width, height = image.size
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for y in range(height):
        rows = alpha.crop((0, y, width, y + 1)).getbbox()
        if rows is None:
            if start is not None:
                runs.append((start, y - 1))
                start = None
        elif start is None:
            start = y
    if start is not None:
        runs.append((start, height - 1))
    return runs


def ink_bbox(image: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Tight bbox (left, top, right_exclusive, bottom_exclusive) inside ``box``."""
    region = image.crop(box)
    bbox = region.getbbox()
    if bbox is None:
        raise ValueError(f"region {box} is fully transparent")
    left, top, right, bottom = bbox
    return (box[0] + left, box[1] + top, box[0] + right, box[1] + bottom)


def stated(bbox: tuple[int, int, int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
    """PIL half-open bbox -> inclusive (rows, cols) as quoted in the spec."""
    left, top, right, bottom = bbox
    return (top, bottom - 1), (left, right - 1)


def check(label: str, actual: object, expected: object) -> None:
    if isinstance(actual, tuple) and isinstance(expected, tuple) and len(actual) == 2:
        if all(isinstance(v, int) for v in actual + expected):
            ok = all(abs(int(a) - int(b)) <= TOLERANCE for a, b in zip(actual, expected))
            if not ok:
                raise SystemExit(f"measurement drift: {label} is {actual}, expected {expected}")
            return
    if actual != expected:
        raise SystemExit(f"measurement drift: {label} is {actual}, expected {expected}")


def pad_box(
    image: Image.Image, bbox: tuple[int, int, int, int], ratio: float = PAD_RATIO
) -> tuple[int, int, int, int]:
    """Grow ``bbox`` by ``ratio`` of its longest side, clamped to the image."""
    left, top, right, bottom = bbox
    pad = round(ratio * max(right - left, bottom - top))
    width, height = image.size
    return (
        max(0, left - pad),
        max(0, top - pad),
        min(width, right + pad),
        min(height, bottom + pad),
    )


# --------------------------------------------------------------------------- #
# image helpers
# --------------------------------------------------------------------------- #
def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def write_png(image: Image.Image, path: Path) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = png_bytes(image)
    path.write_bytes(bytes(data))
    return {"path": path, "bytes": len(data), "dims": f"{image.width}x{image.height}"}


def forced_white(image: Image.Image) -> Image.Image:
    """Every pixel with alpha > 0 becomes pure white; alpha is preserved."""
    white = Image.new("RGBA", image.size, (255, 255, 255, 0))
    white.putalpha(image.getchannel("A"))
    return white


def resized(image: Image.Image, width: int) -> Image.Image:
    height = max(1, round(image.height * width / image.width))
    return image.resize((width, height), INK)


def square(image: Image.Image, size: int) -> Image.Image:
    """``size`` x ``size`` transparent canvas with the art fitted and centred."""
    scale = min(size / image.width, size / image.height)
    fitted = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))), INK
    )
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    canvas.paste(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))
    return canvas


# --------------------------------------------------------------------------- #
# SVG + ICO writers
# --------------------------------------------------------------------------- #
def favicon_svg(favicon: Image.Image) -> str:
    data = base64.b64encode(png_bytes(favicon)).decode("ascii")
    size = FAVICON_PX
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}"'
        ' width="{s}" height="{s}" role="img" aria-label="R\u00c9SIVO">\n'
        '  <image x="0" y="0" width="{s}" height="{s}"'
        ' preserveAspectRatio="xMidYMid meet"'
        ' href="data:image/png;base64,{d}"/>\n'
        "</svg>\n"
    ).format(s=size, d=data)


def logo_svg(logo: Image.Image) -> str:
    width, height = logo.size
    data = base64.b64encode(png_bytes(resized(logo, LOGO_SVG_WIDTH))).decode("ascii")
    scaled_h = round(LOGO_SVG_WIDTH * height / width)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}"'
        ' width="{w}" height="{h}" role="img" aria-label="R\u00c9SIVO">\n'
        '  <image x="0" y="0" width="{vw}" height="{vh}"'
        ' preserveAspectRatio="xMidYMid meet"'
        ' href="data:image/png;base64,{d}"/>\n'
        "</svg>\n"
    ).format(vw=width, vh=height, w=LOGO_SVG_WIDTH, h=scaled_h, d=data)


def ico_frames(mark: Image.Image) -> list[tuple[int, bytes]]:
    """Square frames for every ICO size: BMP (DIB) up to 64px, PNG above."""
    frames: list[tuple[int, bytes]] = []
    for size in ICO_SIZES:
        art = square(mark, size)
        if size <= 64:
            frames.append((size, dib_frame(art)))
        else:
            frames.append((size, png_bytes(art)))
    return frames


def dib_frame(image: Image.Image) -> bytes:
    """32-bit bottom-up BMP frame (BITMAPINFOHEADER + BGRA rows + 1bpp AND mask)."""
    size = image.width
    assert image.size == (size, size), "ICO frames must be square"

    red, green, blue, alpha = image.split()
    bgra = Image.merge("RGBA", (blue, green, red, alpha))  # bytes on disk: B,G,R,A
    xor_bitmap = bytearray()
    and_mask = bytearray()
    mask_stride = ((size + 31) // 32) * 4
    transparent = alpha.point(lambda a: 255 if a == 0 else 0)
    for y in range(size - 1, -1, -1):  # DIB rows are stored bottom-up
        xor_bitmap += bgra.crop((0, y, size, y + 1)).tobytes()
        row = bytearray(mask_stride)
        for x in range(size):
            if transparent.getpixel((x, y)):
                row[x // 8] |= 0x80 >> (x % 8)
        and_mask += row

    header = struct.pack(
        "<IiiHHIIiiII",
        40,  # biSize
        size,  # biWidth
        size * 2,  # biHeight (colour + mask halves)
        1,  # biPlanes
        32,  # biBitCount
        0,  # biCompression = BI_RGB
        len(xor_bitmap),  # biSizeImage
        0, 0, 0, 0,  # resolution + palette
    )
    return header + bytes(xor_bitmap) + bytes(and_mask)


def write_ico(mark: Image.Image, path: Path) -> dict[str, object]:
    frames = ico_frames(mark)
    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = len(header) + 16 * len(frames)
    directory = bytearray()
    payload = bytearray()
    for size, data in frames:
        directory += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,
            0 if size >= 256 else size,
            0, 0, 1, 32, len(data), offset,
        )
        payload += data
        offset += len(data)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + bytes(directory) + bytes(payload))
    with Image.open(path) as probe:
        present = sorted(w for w, _ in probe.ico.sizes())
    return {
        "path": path,
        "bytes": path.stat().st_size,
        "dims": f"{max(present)}x{max(present)} ({','.join(str(s) for s in present)})",
    }


def write_text(text: str, path: Path, dims: str) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    path.write_bytes(data)
    return {"path": path, "bytes": len(data), "dims": dims}


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    if not SOURCE.is_file():
        print(f"error: master logo not found at {SOURCE}", file=sys.stderr)
        return 1

    with Image.open(SOURCE) as opened:
        source = opened.convert("RGBA")
    source_bytes = SOURCE.read_bytes()
    print(f"source: {SOURCE.relative_to(ROOT)}  {source.width}x{source.height}  {len(source_bytes)} bytes")

    runs = ink_rows(source)
    if len(runs) < 2:
        raise SystemExit("expected the mark and the wordmark as separate ink bands")
    mark_rows = runs[0]
    gap_rows = (mark_rows[1] + 1, runs[1][0] - 1)

    full_box = (0, 0, source.width, source.height)
    full_bbox = ink_bbox(source, full_box)
    mark_bbox = ink_bbox(source, (0, mark_rows[0], source.width, mark_rows[1] + 1))
    mark_stated = stated(mark_bbox)
    full_stated = stated(full_bbox)

    check("full ink rows", full_stated[0], EXPECTED["full ink rows"])
    check("full ink cols", full_stated[1], EXPECTED["full ink cols"])
    check("mark rows", mark_stated[0], EXPECTED["mark rows"])
    check("mark cols", mark_stated[1], EXPECTED["mark cols"])
    mw, mh = mark_bbox[2] - mark_bbox[0], mark_bbox[3] - mark_bbox[1]
    check("mark size (w x h)", (mw, mh), EXPECTED["mark size (w x h)"])
    check("mark/wordmark gap rows", gap_rows, EXPECTED["mark/wordmark gap rows"])

    print(
        "measured: mark rows {0[0]}..{0[1]}, cols {1[0]}..{1[1]} ({2}x{3}); "
        "full ink rows {4[0]}..{4[1]}, cols {5[0]}..{5[1]}; gap rows {6[0]}..{6[1]}\n".format(
            mark_stated[0], mark_stated[1], mw, mh, full_stated[0], full_stated[1], gap_rows
        )
    )

    mark = source.crop(pad_box(source, mark_bbox))
    logo = source.crop(pad_box(source, full_bbox))
    mark_white = forced_white(mark)
    logo_white = forced_white(logo)

    results: list[dict[str, object]] = []
    for brand_dir in (DESKTOP_BRAND, WEB_BRAND):
        copy = brand_dir / SOURCE.name
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE, copy)
        results.append({"path": copy, "bytes": copy.stat().st_size, "dims": f"{source.width}x{source.height}"})
    results.append(write_png(mark, DESKTOP_BRAND / "resivo_mark.png"))
    results.append(write_png(logo, DESKTOP_BRAND / "resivo_logo.png"))
    results.append(write_png(mark_white, DESKTOP_BRAND / "resivo_mark_white.png"))
    results.append(write_png(logo_white, DESKTOP_BRAND / "resivo_logo_white.png"))

    results.append(write_png(mark, WEB_BRAND / "resivo_mark.png"))
    results.append(write_png(logo, WEB_BRAND / "resivo_logo.png"))
    results.append(write_png(mark_white, WEB_BRAND / "resivo_mark_white.png"))
    results.append(write_png(logo_white, WEB_BRAND / "resivo_logo_white.png"))

    ico = DESKTOP_BRAND / "resivo.ico"
    results.append(write_ico(mark, ico))

    favicon_ico = WEB_PUBLIC / "favicon.ico"
    favicon_ico.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ico, favicon_ico)
    results.append({"path": favicon_ico, "bytes": favicon_ico.stat().st_size, "dims": results[-1]["dims"]})

    favicon = square(mark, FAVICON_PX)
    results.append(write_png(favicon, WEB_PUBLIC / "favicon-32.png"))
    results.append(
        write_text(
            favicon_svg(favicon),
            WEB_PUBLIC / "favicon.svg",
            f"{FAVICON_PX}x{FAVICON_PX} (vector + {FAVICON_PX}px raster)",
        )
    )
    results.append(
        write_text(
            logo_svg(logo),
            WEB_PUBLIC / "resivo-logo.svg",
            f"{logo.width}x{logo.height} viewBox + {LOGO_SVG_WIDTH}px raster",
        )
    )

    print(f"{'file':<58} {'bytes':>9}  {'dimensions'}")
    print("-" * 96)
    for item in results:
        rel = Path(item["path"]).relative_to(ROOT).as_posix()
        print(f"{rel:<58} {item['bytes']:>9,}  {item['dims']}")
    print("-" * 96)
    print(f"{len(results)} files written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
