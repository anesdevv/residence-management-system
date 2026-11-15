#!/usr/bin/env python3
"""Sprite utilities for the charles-arcade-assets skill. Run with the repo venv: .venv/bin/python tools/sprites.py ...

  key    in.png out.png [--screen magenta|green] [--min-part 0.0005]
         screen background -> transparent, screen colour pulled out of the edge (despill), dust and the
         remains of ghost copies dropped, then trim
  slice  sheet.png outdir --names idle,walk,attack,cheer [--screen magenta] [--rows 1] [--min-part 0.0005]
         keys the sheet, finds each pose as a connected shape (left to right, top to bottom),
         trims it, then pads every pose onto one shared canvas, bottom-centred, so swapping
         poses in HTML keeps the feet planted. Writes poses.json. One shape short of the names
         still slices: it says which name it left out and why (the empty slot or grid cell). Two
         or more short, extra poses, or poses above or below a one-row sheet are errors. A pose
         that fades softly into the screen (a ghost copy above it, a glow) gets a warning.
  unify  cast/<name> --sets base,fight --hue 0-30               one scale + one canvas for all of a character's poses
  fit    new_keyed.png --cast assets/cast/<name> --name pose    add one new pose at the character's size
  trim   in.png out.png                                         crop to the visible pixels
  snap   in.png out.png --grid 8                                force a true pixel grid (blocky, crisp)
  sheet  out.png in1.png in2.png ...                            review sheet on flat teal (holes show)
  screen plate.png out.png                                      cut out the flat #00FF00 screens drawn into a plate
         and print their rects (+ out.screens.json), so live HTML can play inside each screen

Characters must not use the screen colour: magenta screen for most casts, green screen for pink
or purple characters.
--min-part: separate bits smaller than this share of the biggest shape are dust and go (0 keeps them).
Bits drawn on the clean screen above that size stay (a held prop, flying drops, impact stars); bits of
any size up to a quarter of the biggest shape that sit in screen-coloured haze go (a ghost copy's remains).
"""
import argparse, json, sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

SCREENS = {"magenta": (265, 345), "green": (85, 155)}


def load_rgba(path):
    return np.array(Image.open(path).convert("RGBA")).astype(np.float32)


def save(arr, path):
    """Write an RGBA array; fully transparent pixels get black RGB, so no screen colour hides under them for
    a tool that scales without premultiplying alpha to bleed into the edge."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    if arr.ndim == 3 and arr.shape[2] == 4:
        arr[arr[..., 3] == 0, :3] = 0
    Image.fromarray(arr).save(path)


def hsv(a):
    rgb = a[..., :3] / 255.0
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.zeros_like(mx)
    nz = d > 1e-6
    rm = nz & (mx == r)
    gm = nz & (mx == g) & ~rm
    bm = nz & ~rm & ~gm
    h[rm] = (60 * ((g[rm] - b[rm]) / d[rm])) % 360
    h[gm] = 60 * ((b[gm] - r[gm]) / d[gm]) + 120
    h[bm] = 60 * ((r[bm] - g[bm]) / d[bm]) + 240
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0)
    return h, s, mx


def key(a, screen="magenta", edge=3):
    """Remove the screen: every in-band pixel joined, through in-band pixels, to the border or to a pixel close
    to the pure screen colour. That takes the backdrop with its haze, gradients and ghost copies, and the holes
    enclosed by a loop (between legs, inside a claw) with their fringe. Darker in-band shading inside the
    outline (maroon wood, purple shadow) touches neither, so it stays. Then despill() takes the screen colour
    out of what is left at the cut edge (edge px deep)."""
    lo, hi = SCREENS[screen]
    h, s, v = hsv(a)
    band = (h >= lo) & (h <= hi) & (s > 0.22) & (v > 0.18)
    pure = (h >= lo + 15) & (h <= hi - 15) & (s > 0.55) & (v > 0.6)
    out = a.copy()
    out[..., 3] = np.where(outside(band, pure) | pure | (a[..., 3] < 128), 0, 255)
    return despill(out, screen, edge)


def grow(mask, n):
    """mask grown by n pixels (4-neighbour steps)."""
    for _ in range(n):
        g = mask.copy()
        g[1:] |= mask[:-1]; g[:-1] |= mask[1:]; g[:, 1:] |= mask[:, :-1]; g[:, :-1] |= mask[:, 1:]
        mask = g
    return mask


def despill(a, screen="magenta", edge=3):
    """Pull residual screen colour out of the kept pixels: those within edge px of the cut-out edge (the fringe
    the key leaves) and, anywhere, those with a strong cast of the screen colour. On green, G is limited to
    max(R, B); on magenta, R and B come down together until the smaller of them is no more than G. The fringe
    then takes the colour of the outline it borders instead of glowing green or pink."""
    out = a.copy()
    solid = a[..., 3] > 0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    spill = g - np.maximum(r, b) if screen == "green" else np.minimum(r, b) - g
    lo, hi = SCREENS[screen]
    h, _, v = hsv(a)
    strong = (h >= lo + 10) & (h <= hi - 10) & (spill > 24) & (spill > 0.3 * v * 255)
    fix = solid & (spill > 0) & (strong | grow(~solid, edge))
    if screen == "green":
        out[..., 1] = np.where(fix, g - spill, g)
    else:
        out[..., 0] = np.where(fix, r - spill, r)
        out[..., 2] = np.where(fix, b - spill, b)
    return out


def outside(mask, seeds=None, scale=2):
    """The part of mask joined to the image border, or to a seed pixel, through mask pixels: 4-connected on a
    2x grid, then grown back into the anti-aliased fringe."""
    H, W = mask.shape
    h, w = H // scale, W // scale
    small = mask[:h * scale, :w * scale].reshape(h, scale, w, scale).all((1, 3))
    flat = bytearray(small.astype(np.uint8).tobytes())  # 1 in the mask, 2 reached
    edge = list(range(w)) + list(range((h - 1) * w, h * w)) + list(range(0, h * w, w)) + list(range(w - 1, h * w, w))
    if seeds is not None:
        seeded = seeds[:h * scale, :w * scale].reshape(h, scale, w, scale).all((1, 3)) & small
        edge += np.flatnonzero(seeded).tolist()
    q = deque(i for i in edge if flat[i] == 1)
    for i in q:
        flat[i] = 2
    n = h * w
    while q:
        i = q.popleft()
        x = i % w
        for j in (i - w, i + w, i - 1 if x else -1, i + 1 if x < w - 1 else -1):
            if 0 <= j < n and flat[j] == 1:
                flat[j] = 2
                q.append(j)
    reached = np.frombuffer(bytes(flat), np.uint8).reshape(h, w) == 2
    full = np.zeros((H, W), bool)
    full[:h * scale, :w * scale] = np.kron(reached, np.ones((scale, scale), bool))
    for _ in range(scale + 2):
        g = full.copy()
        g[1:] |= full[:-1]; g[:-1] |= full[1:]; g[:, 1:] |= full[:, :-1]; g[:, :-1] |= full[:, 1:]
        full = g & mask
    return full


MIN_PART = 0.0005  # loose bits below this share of the biggest shape are dust
HAZE = 0.3         # loose bits whose surroundings are hazier than this are what is left of a ghost copy


def clean(a, min_part=MIN_PART, haze=HAZE, report=None):
    """Tidy a keyed image: drop drawn floor lines (very wide, very thin) and loose bits. A loose bit is a
    separate shape (8-connected, full resolution) that is
      - dust: smaller than min_part of the biggest shape (0.0005 = 0.05%; specks measure under 0.04%, while
        drawn impact stars and flying drops are 0.1-1.5%), or
      - the remains of a ghost copy or afterimage: up to a quarter of the biggest shape and sitting in haze,
        i.e. more than `haze` of the backdrop around it was a blend of the screen colour rather than the
        clean screen. Parts drawn on the clean screen (a held prop, flying drops, impact stars) stay at any
        size.
    min_part=0 and haze=1 keep every bit. With report, appends (dust count, haze count) to it.
    Returns (image, labels, kept comps, scale): the shapes `slice` cuts poses from, found on a 4x grid with
    small gaps bridged so a sword stays with its hand."""
    H, W = a.shape[:2]
    out = a.copy()
    solid = a[..., 3] > 0
    labels, comps = parts(solid)
    dust = hazy_bits = 0
    if comps:
        biggest = max(c["area"] for c in comps)
        hazy = backdrop_haze(a)
        drop = []
        for c in comps:
            x0, y0, x1, y1 = c["box"]
            if (x1 - x0) > 0.5 * W and (y1 - y0) < 0.05 * H:
                drop.append(c["label"])
            elif c["area"] < biggest * min_part:
                drop.append(c["label"])
                dust += 1
            elif hazy is not None and c["area"] < biggest * 0.25 and haze_around(labels, c, solid, hazy) > haze:
                drop.append(c["label"])
                hazy_bits += 1
        if drop:
            out[np.isin(labels, drop), 3] = 0
    if report is not None:
        report.append((dust, hazy_bits))
    labels, comps, sc = components(out[..., 3] > 0)
    keep = []
    for c in comps:
        x0, y0, x1, y1 = c["box"]
        if (x1 - x0) > 0.5 * W and (y1 - y0) < 0.05 * H:  # a dashed floor line, joined up by the bridging
            out[np.kron(labels == c["label"], np.ones((sc, sc), bool))[:H, :W], 3] = 0
        else:
            keep.append(c)
    return out, labels, keep, sc


def parts(mask):
    """The separate shapes of a mask at full resolution, 8-connected: (labels, comps), labels 1.. on the shapes
    and 0 elsewhere, each comp {label, area, box (x0, y0, x1, y1), end exclusive}. Works on runs of pixels."""
    H, W = mask.shape
    d = np.diff(np.pad(mask.astype(np.int8), ((0, 0), (1, 1))), axis=1)
    sy, sx = np.nonzero(d == 1)
    ex = np.nonzero(d == -1)[1]  # runs in row-major order: row sy[i], columns sx[i] .. ex[i]-1
    n = len(sx)
    labels = np.zeros((H, W), np.int32)
    if n == 0:
        return labels, []
    parent = list(range(n))

    def find(i):
        root = i
        while parent[root] != root:
            root = parent[root]
        while parent[i] != root:
            parent[i], i = root, parent[i]
        return root

    first = np.searchsorted(sy, np.arange(H + 1)).tolist()
    xs, xe = sx.tolist(), ex.tolist()
    for y in range(1, H):
        i, i1, j, j1 = first[y], first[y + 1], first[y - 1], first[y]
        while i < i1 and j < j1:
            if xs[i] <= xe[j] and xs[j] <= xe[i]:  # touching, diagonals included
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj
            if xe[i] < xe[j]:
                i += 1
            else:
                j += 1
    roots = np.array([find(i) for i in range(n)])
    _, lab = np.unique(roots, return_inverse=True)
    lab = lab + 1
    labels[mask] = np.repeat(lab, ex - sx)
    k = int(lab.max())
    area = np.bincount(lab, weights=ex - sx, minlength=k + 1)
    x0 = np.full(k + 1, W); y0 = np.full(k + 1, H); x1 = np.zeros(k + 1, int); y1 = np.zeros(k + 1, int)
    np.minimum.at(x0, lab, sx); np.minimum.at(y0, lab, sy)
    np.maximum.at(x1, lab, ex); np.maximum.at(y1, lab, sy + 1)
    return labels, [{"label": i, "area": int(area[i]), "box": (int(x0[i]), int(y0[i]), int(x1[i]), int(y1[i]))}
                    for i in range(1, k + 1)]


def backdrop_haze(a):
    """Cleared pixels that were not the clean backdrop colour (the median of the cleared border pixels): the
    screen's haze, glow and ghost copies. None when the cleared pixels carry no colour to compare."""
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    border = border[border[:, 3] == 0, :3]
    if len(border) < 16:
        return None
    clear = a[..., 3] == 0
    far = np.abs(a[..., :3] - np.median(border, 0)).sum(-1) > 90
    return clear & far if far[clear].any() else None


FADE = 0.015  # a pose with more soft fade than this share of its area has a ghost copy or a glow


def fades(raw, screen):
    """Where the raw image fades softly into the screen colour: partly screen-coloured pixels whose screen share
    changes gently (15-150 over 8 px) in a band several px thick. That is the edge of a ghost copy, an
    afterimage or a glow; clean pixel art meets the screen within 2-3 px, and a flat colour does not change."""
    r, g, b = raw[..., 0], raw[..., 1], raw[..., 2]
    spill = g - np.maximum(r, b) if screen == "green" else np.minimum(r, b) - g
    edge = np.concatenate([raw[0], raw[-1], raw[:, 0], raw[:, -1]])
    full = max(float(np.median(edge[:, 1] - np.maximum(edge[:, 0], edge[:, 2]) if screen == "green" else
                               np.minimum(edge[:, 0], edge[:, 2]) - edge[:, 1])), 60.0)
    dy = np.zeros_like(spill); dy[4:-4] = np.abs(spill[8:] - spill[:-8])
    dx = np.zeros_like(spill); dx[:, 4:-4] = np.abs(spill[:, 8:] - spill[:, :-8])
    soft = (spill > 0.15 * full) & (spill < 0.85 * full) & (((dy >= 15) & (dy <= 150)) | ((dx >= 15) & (dx <= 150)))
    return ~grow(~soft, 2)  # 2 px eroded: thin anti-aliasing goes, bands stay


def haze_around(labels, c, solid, hazy, near=6, far=40):
    """Share of the cleared pixels 6-40 px around a part (past its anti-aliased rim) that are haze."""
    H, W = labels.shape
    x0, y0, x1, y1 = c["box"]
    ys, xs = slice(max(0, y0 - far), min(H, y1 + far)), slice(max(0, x0 - far), min(W, x1 + far))
    inner = grow(labels[ys, xs] == c["label"], near)
    ring = grow(inner, far - near) & ~inner & ~solid[ys, xs]
    return float(hazy[ys, xs][ring].mean()) if ring.any() else 0.0


def components(mask, scale=4, bridge=3):
    """Label connected shapes on a downsampled mask; bridge closes small gaps (sword to hand)."""
    H, W = mask.shape
    h, w = (H + scale - 1) // scale, (W + scale - 1) // scale
    pad = np.zeros((h * scale, w * scale), bool)
    pad[:H, :W] = mask
    small = pad.reshape(h, scale, w, scale).any((1, 3))
    grown = small.copy()
    for _ in range(bridge):
        g = grown.copy()
        g[1:] |= grown[:-1]; g[:-1] |= grown[1:]; g[:, 1:] |= grown[:, :-1]; g[:, :-1] |= grown[:, 1:]
        grown = g
    labels = np.zeros((h, w), np.int32)
    comps = []
    for y0 in range(h):
        for x0 in range(w):
            if not grown[y0, x0] or labels[y0, x0]:
                continue
            n = len(comps) + 1
            q = deque([(y0, x0)])
            labels[y0, x0] = n
            ys, xs, area = [y0], [x0], 0
            while q:
                y, x = q.popleft()
                area += small[y, x]
                for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                    if 0 <= yy < h and 0 <= xx < w and grown[yy, xx] and not labels[yy, xx]:
                        labels[yy, xx] = n
                        q.append((yy, xx))
                        ys.append(yy); xs.append(xx)
            comps.append({"label": n, "area": int(area),
                          "box": (min(xs) * scale, min(ys) * scale, (max(xs) + 1) * scale, (max(ys) + 1) * scale)})
    return labels, comps, scale


def bbox(a):
    ys, xs = np.where(a[..., 3] > 0)
    if len(xs) == 0:
        return None
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def trim(a):
    b = bbox(a)
    if b is None:
        return a
    x0, y0, x1, y1 = b
    return a[y0:y1, x0:x1]


def cmd_key(args):
    report = []
    save(trim(clean(key(load_rgba(args.inp), args.screen), args.min_part, report=report)[0]), args.out)
    dust, hazy = report[0]
    dropped = ", ".join(t for t in (f"{dust} specks" if dust else "", f"{hazy} ghost bits" if hazy else "") if t)
    print(f"keyed: {args.out}" + (f" (dropped {dropped})" if dropped else ""))


def cmd_trim(args):
    save(trim(load_rgba(args.inp)), args.out)
    print(f"trimmed: {args.out}")


def cmd_slice(args):
    """Cut a sheet into poses and return the names written. One shape short of the names still slices: the
    names run in order and the one with no shape is left out (see missing_pose), with a note saying which.
    A pose with a ghost copy or a glow fading into the screen gets a warning, or stops the slice when
    args.no_fades is set (cast.py then draws the sheet again)."""
    raw = load_rgba(args.sheet)
    a, labels, comps, sc = clean(key(raw, args.screen), getattr(args, "min_part", MIN_PART))
    names = [n.strip() for n in args.names.split(",")]
    if not comps:
        sys.exit("nothing left after keying: is the background the screen colour?")
    biggest = max(c["area"] for c in comps)
    main = sorted([c for c in comps if c["area"] >= biggest * 0.12], key=lambda c: -c["area"])
    if len(main) < len(names) - 1:
        sys.exit(f"found {len(main)} poses but {len(names)} names; regenerate the sheet with wider gaps")
    if len(main) > len(names) and main[len(names)]["area"] >= 0.35 * main[len(names) // 2]["area"]:
        sys.exit(f"found {len(main)} poses for {len(names)} names: the sheet has extra poses; regenerate it")
    main = main[:len(names)]
    H = a.shape[0]
    if args.rows == 1 and len(main) > 1:
        base = sorted(c["box"][3] for c in main)[len(main) // 2]
        off = sum(abs(c["box"][3] - base) > 0.25 * H for c in main)
        if off:
            sys.exit(f"the poses are not in one row ({off} stand above or below the rest); regenerate the sheet")
    centre = lambda c: ((c["box"][0] + c["box"][2]) / 2, (c["box"][1] + c["box"][3]) / 2)
    main.sort(key=lambda c: (int(centre(c)[1] / H * args.rows), centre(c)[0]))
    if len(main) < len(names):
        gone, why = missing_pose([c["box"] for c in main], a.shape[1], len(names), args.rows, a.shape[0])
        print(f"found {len(main)} poses for {len(names)} names, so '{names[gone]}' is left out: {why}")
        names = names[:gone] + names[gone + 1:]
    crops, faded = [], []
    soft = fades(raw, args.screen)
    for name, c in zip(names, main):
        x0, y0, x1, y1 = c["box"]
        piece = a[y0:y1, x0:x1].copy()
        own = np.kron(labels[y0 // sc:(y1 + sc - 1) // sc, x0 // sc:(x1 + sc - 1) // sc] == c["label"],
                      np.ones((sc, sc), bool))[:y1 - y0, :x1 - x0]
        piece[~own, 3] = 0
        crops.append(trim(piece))
        pad = soft[max(0, y0 - 10):y1 + 10, max(0, x0 - 10):x1 + 10]
        if pad.sum() > FADE * max(1, (piece[..., 3] > 0).sum()):
            faded.append(name)
    if faded:
        msg = (f"{', '.join(faded)} fade{'s' if len(faded) == 1 else ''} softly into the screen colour: a ghost copy "
               f"or a glow drawn around {'it' if len(faded) == 1 else 'them'}")
        if getattr(args, "no_fades", False):
            sys.exit(msg + "; regenerate the sheet")
        print(f"warning: {msg}; check them on the review sheet")
    W = max(c.shape[1] for c in crops) + 8
    H = max(c.shape[0] for c in crops) + 4
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    meta = {"canvas": [int(W), int(H)], "poses": {}}
    for name, t in zip(names, crops):
        canvas = np.zeros((H, W, 4), np.float32)
        x = (W - t.shape[1]) // 2
        y = H - t.shape[0] - 2
        canvas[y:y + t.shape[0], x:x + t.shape[1]] = t
        save(canvas, out / f"{name}.png")
        meta["poses"][name] = {"file": f"{name}.png", "sprite_size": [int(t.shape[1]), int(t.shape[0])]}
    (out / "poses.json").write_text(json.dumps(meta, indent=1))
    print(f"{len(names)} poses -> {out} (canvas {W}x{H})")
    return names


def missing_pose(boxes, W, n, rows=1, H=None):
    """Which of n names has no shape when n poses came out as n-1 shapes (boxes in reading order): (index,
    reason). In a grid, the empty cell. In one row, an empty slot (a gap of about two poses' spacing, or a wide
    margin at either end); else one shape about twice as wide as the others means two poses ran together, so
    the name after it goes. Else the last name goes."""
    m = len(boxes)
    if rows > 1 and H:
        cols = -(-n // rows)
        cells = [int((b[1] + b[3]) / 2 / H * rows) * cols + int((b[0] + b[2]) / 2 / W * cols) for b in boxes]
        empty = [i for i in range(n) if i not in cells]
        if len(set(cells)) == m and len(empty) == 1:
            r, c = divmod(empty[0], cols)
            return empty[0], f"row {r + 1}, place {c + 1} of the grid is empty"
    if rows == 1 and m >= 2:
        cx = [(b[0] + b[2]) / 2 for b in boxes]
        gaps = [b - a for a, b in zip(cx, cx[1:])]
        step = sorted(gaps)[(len(gaps) - 1) // 2]
        big = max(range(len(gaps)), key=lambda i: gaps[i])
        if gaps[big] > 1.6 * step:
            return big + 1, f"there is an empty slot between shapes {big + 1} and {big + 2}"
        if cx[0] > 1.1 * step:
            return 0, "the row starts with an empty slot"
        if W - cx[-1] > 1.1 * step:
            return n - 1, "the row ends with an empty slot"
        widths = [b[2] - b[0] for b in boxes]
        wide = max(range(m), key=lambda i: widths[i])
        others = sorted(widths[:wide] + widths[wide + 1:])
        if widths[wide] > 1.7 * others[len(others) // 2]:
            return wide + 1, (f"shape {wide + 1} is about twice as wide as the others, so two poses probably ran "
                              f"together there; it is saved under the first one's name")
    return n - 1, ("nothing shows which pose is missing, so the names run in order and the last is left out; "
                   "check that each pose got the right name")


def parse_hue(text):
    """'0-30' -> (0, 30); 'all' -> None (measure the whole sprite, for characters without one body colour)."""
    return None if text == "all" else tuple(int(x) for x in text.split("-"))


def body_height(a, hue):
    if hue is None:
        ys = np.where(a[..., 3] > 0)[0]
        return (ys.max() - ys.min() + 1) if len(ys) else a.shape[0]
    lo, hi = hue
    h, s, v = hsv(a)
    inband = ((h >= lo) & (h <= hi)) if lo <= hi else ((h >= lo) | (h <= hi))
    ys = np.where(inband & (s > 0.35) & (v > 0.3) & (a[..., 3] > 0))[0]
    return (ys.max() - ys.min() + 1) if len(ys) else a.shape[0]


def cmd_unify(args):
    unify_sets(args.char, [s.strip() for s in args.sets.split(",")], args.hue)


def unify_sets(root, sets, hue_text, prefix=True):
    """Rescale every pose set of one character to the same body size and pad all poses onto one canvas.
    With prefix, poses from every set after the first are saved as <set>_<pose>."""
    root = Path(root)
    hue = parse_hue(hue_text)
    loaded = {}
    target = None
    for s in sets:
        meta = json.loads((root / s / "poses.json").read_text())
        names = list(meta["poses"])
        imgs = {n: Image.open(root / s / meta["poses"][n]["file"]).convert("RGBA") for n in names}
        unit = body_height(np.array(imgs[names[0]]).astype(np.float32), hue)
        target = target or unit
        f = target / unit
        if abs(f - 1) > 0.01:
            imgs = {n: im.resize((max(1, round(im.width * f)), max(1, round(im.height * f))), Image.Resampling.LANCZOS)
                    for n, im in imgs.items()}
        loaded[s] = imgs
        print(f"{s}: body {unit}px -> x{f:.3f}")
    W = max(im.width for imgs in loaded.values() for im in imgs.values())
    H = max(im.height for imgs in loaded.values() for im in imgs.values())
    out = root / "poses"
    out.mkdir(exist_ok=True)
    cast = {"canvas": [W, H], "body_px": int(target), "hue": hue_text, "poses": []}
    if (root / "cast.json").is_file():  # keep what else the cast records (its screen, type, note)
        cast.update({k: v for k, v in json.loads((root / "cast.json").read_text()).items() if k not in cast})
    for s, imgs in loaded.items():
        for n, im in imgs.items():
            canvas = Image.new("RGBA", (W, H))
            canvas.alpha_composite(trim_img(im), ((W - trim_img(im).width) // 2, H - trim_img(im).height - 2))
            name = n if s == sets[0] or not prefix else f"{s}_{n}"
            canvas.save(out / f"{name}.png")
            cast["poses"].append(name)
    (root / "cast.json").write_text(json.dumps(cast, indent=1))
    print(f"{len(cast['poses'])} poses -> {out} (canvas {W}x{H}, body {target}px)")
    return cast


def trim_img(im):
    b = im.getbbox()
    return im.crop(b) if b else im


def cmd_fit(args):
    """Scale a new keyed pose to a cast member's body size and pad it onto the cast canvas."""
    cast_dir = Path(args.cast)
    cast = json.loads((cast_dir / "cast.json").read_text())
    hue = parse_hue(cast["hue"])
    im = trim_img(Image.open(args.inp).convert("RGBA"))
    unit = body_height(np.array(im).astype(np.float32), hue)
    f = cast["body_px"] / unit
    im = im.resize((max(1, round(im.width * f)), max(1, round(im.height * f))), Image.Resampling.LANCZOS)
    W, H = cast["canvas"]
    if im.width > W or im.height > H:
        W, H = max(W, im.width + 8), max(H, im.height + 4)
        print(f"note: pose is larger than the cast canvas; this pose uses {W}x{H}, size its sprite box to match")
    canvas = Image.new("RGBA", (W, H))
    canvas.alpha_composite(im, ((W - im.width) // 2, H - im.height - 2))
    out = cast_dir / "poses" / f"{args.name}.png"
    canvas.save(out)
    if args.name not in cast["poses"]:
        cast["poses"].append(args.name)
        (cast_dir / "cast.json").write_text(json.dumps(cast, indent=1))
    print(f"fitted x{f:.3f} -> {out}")


def cmd_snap(args):
    img = Image.open(args.inp).convert("RGBA")
    small = img.resize((max(1, img.width // args.grid), max(1, img.height // args.grid)), Image.Resampling.BOX)
    a = np.array(small)
    a[..., 3] = np.where(a[..., 3] > 127, 255, 0)
    Image.fromarray(a).resize((small.width * args.grid, small.height * args.grid), Image.Resampling.NEAREST).save(args.out)
    print(f"snapped to a {args.grid}px grid: {args.out}")


def cmd_screen(args):
    """Find the flat green screens drawn into a plate, cut them out, and report where they are."""
    a = load_rgba(args.inp)
    h, s, v = hsv(a)
    green = (h >= 95) & (h <= 145) & (s > 0.55) & (v > 0.55)
    labels, comps, sc = components(green, bridge=0)
    H, W = green.shape
    rects = []
    for c in sorted(comps, key=lambda c: -c["area"]):
        if c["area"] * sc * sc < 0.002 * H * W:
            continue
        x0, y0, x1, y1 = c["box"]
        own = np.kron(labels == c["label"], np.ones((sc, sc), bool))[:H, :W] & green
        ys, xs = np.nonzero(own)
        corner = lambda k: [int(xs[k]), int(ys[k])]
        quad = [corner(np.argmin(xs + ys)), corner(np.argmax(xs - ys)), corner(np.argmax(xs + ys)),
                corner(np.argmin(xs - ys))]  # top-left, top-right, bottom-right, bottom-left
        rects.append({"x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0), "quad": quad,
                      "pct": [round(100 * x0 / W, 2), round(100 * y0 / H, 2),
                              round(100 * (x1 - x0) / W, 2), round(100 * (y1 - y0) / H, 2)]})
    hole = green.copy()
    for _ in range(2):  # take the anti-aliased rim with it
        g = hole.copy()
        g[1:] |= hole[:-1]; g[:-1] |= hole[1:]; g[:, 1:] |= hole[:, :-1]; g[:, :-1] |= hole[:, 1:]
        hole = g & ((h >= 70) & (h <= 170) & (s > 0.25))
    out = a.copy()
    out[hole | green, 3] = 0
    save(out, args.out)
    rects.sort(key=lambda r: (r["y"] // 40, r["x"]))
    Path(args.out).with_suffix(".screens.json").write_text(json.dumps({"size": [W, H], "screens": rects}, indent=1))
    for i, r in enumerate(rects):
        print(f"screen {i}: x {r['x']} y {r['y']} w {r['w']} h {r['h']}  (left {r['pct'][0]}% top {r['pct'][1]}% "
              f"width {r['pct'][2]}% height {r['pct'][3]}%)")
    print(f"{len(rects)} screen(s) cut out -> {args.out} (+ .screens.json)")


def cmd_sheet(args):
    imgs = [Image.open(p).convert("RGBA") for p in args.inputs]
    th = 300
    imgs = [im.resize((max(1, int(im.width * th / im.height)), th), Image.Resampling.NEAREST) for im in imgs]
    W = sum(im.width for im in imgs) + 20 * (len(imgs) + 1)
    sheet = Image.new("RGBA", (W, th + 40), (38, 128, 120, 255))
    x = 20
    for im in imgs:
        sheet.alpha_composite(im, (x, 20))
        x += im.width + 20
    sheet.convert("RGB").save(args.out)
    print(f"sheet: {args.out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("key"); k.add_argument("inp"); k.add_argument("out")
    k.add_argument("--screen", default="magenta", choices=list(SCREENS))
    s = sub.add_parser("slice"); s.add_argument("sheet"); s.add_argument("outdir")
    s.add_argument("--names", required=True); s.add_argument("--screen", default="magenta", choices=list(SCREENS))
    s.add_argument("--rows", type=int, default=1, help="rows of poses in the sheet")
    for q in (k, s):
        q.add_argument("--min-part", type=float, default=MIN_PART,
                       help="drop separate bits smaller than this share of the biggest shape (default 0.0005)")
    u = sub.add_parser("unify"); u.add_argument("char"); u.add_argument("--sets", required=True)
    u.add_argument("--hue", required=True, help="body hue band in degrees, e.g. 5-25 (orange), 205-240 (blue), or all")
    fi = sub.add_parser("fit"); fi.add_argument("inp"); fi.add_argument("--cast", required=True, help="assets/cast/<name>")
    fi.add_argument("--name", required=True, help="pose name to save as")
    t = sub.add_parser("trim"); t.add_argument("inp"); t.add_argument("out")
    n = sub.add_parser("snap"); n.add_argument("inp"); n.add_argument("out"); n.add_argument("--grid", type=int, required=True)
    h = sub.add_parser("sheet"); h.add_argument("out"); h.add_argument("inputs", nargs="+")
    c = sub.add_parser("screen"); c.add_argument("inp"); c.add_argument("out")
    args = ap.parse_args()
    {"key": cmd_key, "slice": cmd_slice, "unify": cmd_unify, "fit": cmd_fit, "trim": cmd_trim, "snap": cmd_snap,
     "sheet": cmd_sheet, "screen": cmd_screen}[args.cmd](args)


if __name__ == "__main__":
    main()
