"""Accent heroes: landing-page hero images made with GPT Image as close variations of reference screenshots, or from a written
layout when a page has no reference; checked, fixed with targeted edits, and shown on a board.

  python3 -I heroes.py check  --project <folder> [--also <another concepts.json>]
  python3 -I heroes.py render --project <folder> [--concepts a,b] [--dry-run]
  python3 -I heroes.py fix    --project <folder> --render <page>-<n> --note "what to change" [--n 2]
  python3 -I heroes.py review --project <folder> [--concepts a,b]
  python3 -I heroes.py board  --project <folder> [--title "..."]

The project folder holds concepts.json. Everything generated goes to <project>/out/:
  out/variants/<page>-<n>.png   one per render, each with a .json sidecar (prompt, reference, model, seconds, usage)
  out/review/, out/board/variants/, out/check.json, out/log.jsonl
"""
import argparse
import base64
import html
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import requests
from PIL import Image

MODEL = "gpt-image-2.6-sunburst"
SIZE = "1536x1024"
SCRIPTS = Path(__file__).resolve().parent
HOMOGLYPHS = str.maketrans("АВЕКМНОРСТХУаеорсхуΑΒΕΖΗΙΚΜΝΟΡΤΥΧ", "ABEKMHOPCTXYaeopcxyABEZHIKMNOPTYX")  # Vision mixes in look-alikes

# A page made from a reference screenshot. The reference rides along as the edit's input image, so its layout, type system,
# small type, colour structure and finish carry over; everything named below is new.
SWIPE = """Use the attached landing-page screenshot as the design reference. Make a new website hero that is a close micro-variation of it: keep its layout and composition, its typographic system (the same kind of display typeface, sizes, weights, colouring and the way the headline interacts with the subject), its small interface details and their placement, its colour structure, its lighting and its polish. Change the brand, the subject and every word, as described below. Do not copy the reference's people or faces, brand names, logos or any of its text.

Output: a single desktop website hero, a flat full-bleed screenshot at 3:2, no browser window or device frame.

Brand: {brand}, {what}.
Subject: {subject}
Background: {background}
{light}Headline: "{headline}", set the way the reference sets its headline. {headline_note} Every letter stays whole and readable.
Small text and interface, placed where the reference places its equivalents: {ui}
Colours: {colours}
{photo}
{variation}
Spell every word exactly as written. Add no other text, logos or watermarks."""

# A page with no reference: its layout is written out as the composition. Less reliable than a reference; expect re-rolls.
WRITTEN = """Design a single desktop website hero section, shown as a flat full-bleed screenshot at 3:2, with no browser window, device or mockup frame.

Brand: {brand}, {what}.
Subject: {subject}
Composition: {layout}.
Background: {background}
{light}Headline: "{headline}". {headline_note} Every letter stays whole and readable.
Small text and interface, small, quiet and crisp: {ui}
Colours: {colours}
{photo}
{variation}
Craft: award-winning art direction, the kind of hero that wins Awwwards Site of the Day; precise kerning and alignment on a 12-column grid with generous margins.
Spell every word exactly as written. Add no other text, numbers, logos or watermarks."""

PHOTO = ("Photographed, not rendered: any person has real skin with pores and film grain; objects keep real proportions and crisp "
         "small parts.")

# craft.md's layouts. With a reference they only feed the variety check; without one, they become the composition.
LAYOUTS = {
    "left-headline": "the headline fills the left half and the subject the right half",
    "word-behind": "one giant word across the full width, the subject in front of it",
    "split": "the headline split across the frame, the subject between its words",
    "centred": "a symmetrical poster, the subject centred and the headline centred above or below it",
    "vertical": "the headline set vertically or on a curve beside the subject",
    "macro": "an extreme close-up of the subject filling the frame, the headline over a quiet part of it",
}
REQUIRED = ("brand", "what", "layout", "subject", "background", "light", "headline", "headline_note", "ui", "palette", "variations")
VARIATIONS = 5  # renders per page: most pages have one standout render, and three left it out too often

# A fix keeps the render and changes one named thing: an edit holds the composition, a re-roll throws it away.
FIX = ("Edit this website hero. Keep the typography, the headline, every small text, the layout, the colours and the background exactly "
       "as they are. Change only what is described. Spell every word exactly as it is now and add no new text. Change: {note}")


def colours_line(c):
    (fn, fh), (sn, sh), (an, ah) = c["palette"]
    if c.get("route") == "tonal":
        role = (f"{an} {ah} the one accent, in the field's own colour family but far brighter and more vivid: it is the light itself "
                "(a glow, sun through haze, its reflection in metal), about 15 to 30% of the frame, and it may colour part of the headline.")
    else:
        role = (f"{an} {ah} the one accent: the most saturated colour, about 15 to 30% of the frame, part of the subject (its light, "
                "paint or material), glowing or vivid against the field, and it may colour part of the headline.")
    return f"{fn} {fh} is the field; {sn} {sh} the type and quiet surfaces; {role}"


def light_line(c):
    return f"Light: {c['light']}\n" if c.get("light") else ""


def swipe_prompt(c, variation):
    return SWIPE.format(brand=c["brand"], what=c["what"], subject=c["subject"], background=c.get("background", ""), light=light_line(c),
                        headline=c["headline"], headline_note=c.get("headline_note", ""), ui=c["ui"], colours=colours_line(c), photo=PHOTO,
                        variation=variation)


def written_prompt(c, variation):
    return WRITTEN.format(brand=c["brand"], what=c["what"], subject=c["subject"], layout=LAYOUTS[c["layout"]],
                          background=c.get("background", ""), light=light_line(c), headline=c["headline"],
                          headline_note=c.get("headline_note", ""), ui=c["ui"], colours=colours_line(c), photo=PHOTO, variation=variation)


def ref_path(c, project):
    """The page's reference screenshot: an absolute path, or relative to the project folder or the folder the script runs from."""
    r = Path(c["ref"])
    if r.is_absolute():
        return r
    return next((base / r for base in (project, Path.cwd()) if (base / r).exists()), project / r)


def openai_key(project):
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    for folder in [project.resolve(), *project.resolve().parents, Path.cwd()]:
        env = folder / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("OPENAI_API_KEY not found: set it in the environment or in a .env in or above the project folder.")


def load(project):
    path = project / "concepts.json"
    if not path.exists():
        sys.exit(f"{path} is missing. Write the concepts first (see SKILL.md).")
    return json.loads(path.read_text())


def variant_files(project, key):
    return sorted((project / "out" / "variants").glob(f"{key}-*.png"), key=lambda p: int(p.stem.rsplit("-", 1)[1]))


def claim(project, key, count):
    """Reserve the next `count` render names of a page. Each name is claimed by creating its sidecar exclusively, so two fix
    runs on one page at once can't take the same number (in round 7 one overwrote the other). Numbers in superseded/ stay used."""
    folder = project / "out" / "variants"
    folder.mkdir(parents=True, exist_ok=True)
    used = [int(p.stem.rsplit("-", 1)[1]) for p in folder.rglob(f"{key}-*") if p.stem.rsplit("-", 1)[0] == key and p.stem.rsplit("-", 1)[1].isdigit()]
    n, dests = max(used, default=0), []
    while len(dests) < count:
        n += 1
        try:
            os.close(os.open(folder / f"{key}-{n}.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:
            continue
        dests.append(folder / f"{key}-{n}.png")
    return dests


def call(project, key, text, dest, src=None, meta=None, tries=2):
    headers = {"Authorization": f"Bearer {key}"}
    for attempt in range(1, tries + 1):
        t0 = time.time()
        try:
            if src is None:
                body = {"model": MODEL, "prompt": text, "size": SIZE, "quality": "high", "n": 1, "output_format": "png"}
                r = requests.post("https://api.openai.com/v1/images/generations", headers=headers, json=body, timeout=(15, 300))
            else:
                data = {"model": MODEL, "prompt": text, "size": SIZE, "quality": "high", "n": "1", "output_format": "png"}
                with open(src, "rb") as f:
                    r = requests.post("https://api.openai.com/v1/images/edits", headers=headers, data=data,
                                      files={"image[]": (Path(src).name, f, "image/png")}, timeout=(15, 300))
            if r.status_code != 200:
                raise RuntimeError(f"{r.status_code}: {r.text[:400]}")
            j = r.json()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(base64.b64decode(j["data"][0]["b64_json"]))
            side = {"model": MODEL, "seconds": round(time.time() - t0, 1), "usage": j.get("usage", {}), "prompt": text,
                    "src": str(src) if src else None, **(meta or {})}
            dest.with_suffix(".json").write_text(json.dumps(side, indent=1))
            log(project, {"t": t0, "dest": str(dest), "seconds": side["seconds"], "usage": side["usage"], **(meta or {})})
            return f"{dest.name}: ok {side['seconds']}s"
        except Exception as e:  # a hung or failed call is retried once, then reported; the batch keeps going
            log(project, {"t": t0, "dest": str(dest), "error": str(e)[:400], "attempt": attempt, **(meta or {})})
            if attempt == tries:
                return f"{dest.name}: FAILED {str(e)[:200]}"


def log(project, entry):
    (project / "out").mkdir(parents=True, exist_ok=True)
    with open(project / "out" / "log.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")


def oklab(rgb):
    """OKLab lightness, chroma and hue (degrees) of an (n, 3) array of sRGB values 0-255."""
    c = rgb / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    l = np.cbrt(c @ np.array([0.4122214708, 0.5363325363, 0.0514459929]))
    m = np.cbrt(c @ np.array([0.2119034982, 0.6806995451, 0.1073969566]))
    s = np.cbrt(c @ np.array([0.0883024619, 0.2817188376, 0.6299787005]))
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, np.hypot(A, B), (np.degrees(np.arctan2(B, A)) + 360) % 360


def lch(hexcode):
    L, C, H = oklab(np.array([[int(hexcode[i:i + 2], 16) for i in (1, 3, 5)]], dtype=float))
    return float(L[0]), float(C[0]), float(H[0])


def max_chroma(L, h):
    """The most chroma sRGB allows at this OKLCH lightness and hue. Greens and teals top out near 0.15, so a fixed floor of
    0.2 would rule them out as accents."""
    def inside(C):
        a, b = C * np.cos(np.radians(h)), C * np.sin(np.radians(h))
        l, m, s = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3, (L - 0.1055613458 * a - 0.0638541728 * b) ** 3, (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
        rgb = (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
               -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)
        return all(-1e-4 <= v <= 1 + 1e-4 for v in rgb)
    lo, hi = 0.0, 0.4
    for _ in range(30):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if inside(mid) else (lo, mid)
    return lo


def small(path):
    return np.asarray(Image.open(path).convert("RGB").resize((400, 267)), dtype=float)


def hue_dist(a, b):
    d = np.abs(np.asarray(a, dtype=float) - b) % 360
    return np.minimum(d, 360 - d)


def circular_mean(hues):
    r = np.radians(hues)
    return float(np.degrees(np.arctan2(np.sin(r).mean(), np.cos(r).mean())) % 360)


def accent_share(arr, hexcode):
    """The accent's share of the frame (%) and the hue it rendered at. The model drifts 10-30° from the planned hex, so the
    share is counted around the rendered hue: the peak of the vivid pixels within 45° of the plan."""
    _, ac, ah = lch(hexcode)
    L, C, H = oklab(arr.reshape(-1, 3))
    vivid = C > max(0.06, ac * 0.45)
    near = vivid & (hue_dist(H, ah) < 45)
    peak = ah
    if near.sum() >= 50:
        hist, edges = np.histogram(H[near], bins=72, range=(0, 360))
        peak = float(edges[hist.argmax()] + 2.5)
    return float((vivid & (hue_dist(H, peak) < 22)).mean() * 100), peak


def norm(s):
    return re.sub(r"[^A-Z0-9$]", "", s.translate(HOMOGLYPHS).upper().replace("→", ""))


def read_text(paths):
    """Vision's reading of each image: {file name: (all its text, normalised; its line boxes as fractions of the image)}."""
    out = subprocess.run(["swift", str(SCRIPTS / "ocr.swift"), *map(str, paths)], capture_output=True, text=True, check=True).stdout
    return {Path(j["path"]).name: (norm(" ".join(j["lines"])), j["boxes"]) for j in map(json.loads, out.splitlines())}


def found(target, text):
    """True when Vision read the copy, allowing for its misreads of small tracked capitals; otherwise the closest stretch it
    read. Vision reads a malformed letter as the right one (a broken F read as F), so look at the small copy at full size too."""
    t = norm(target)
    if t in text:
        return True
    ratio, near = max(((SequenceMatcher(None, t, text[i:i + len(t)]).ratio(), text[i:i + len(t)]) for i in range(max(1, len(text) - len(t) + 1))), default=(0, ""))
    return True if ratio >= 0.9 else near  # 0.85 let one-letter slips through (BOUTQUES for BOUTIQUES)


def palette_formula(palette, route=None):
    """The palette formula, measured on 21 award-style heroes: the two regular colours one dark and one light (lightness gap
    0.4 or more); the accent the most saturated (chroma about 0.2) and far around the wheel from any regular colour that has
    real colour: 120-180° pops hardest, 75° is the minimum. Creams, greys, blacks and whites (chroma under 0.04) don't count.
    The tonal route drops the distance: the accent shares the field's family but reads as light, because it is at least 1.8
    times as saturated as either regular colour and 0.3 lighter than the field (gold sunlight on gold-brown measured 2.1 and 0.41)."""
    (_, bh), (_, sh), (_, ah) = palette
    B, S, A = lch(bh), lch(sh), lch(ah)
    flags = []
    if abs(B[0] - S[0]) < 0.4:
        flags.append(f"the two regular colours are only {abs(B[0] - S[0]):.2f} apart in lightness (0.4 or more: one dark, one light)")
    peak = max_chroma(A[0], A[2])
    if A[1] < 0.8 * peak:
        flags.append(f"the accent's chroma is {A[1]:.2f}, under 80% of the {peak:.2f} its hue reaches at this lightness: make it more vivid")
    if A[1] < max(B[1], S[1]):
        flags.append("the accent isn't the most saturated of the three")
    gaps = [float(hue_dist(A[2], col[2])) for col in (B, S) if col[1] >= 0.04]
    gap = round(min(gaps)) if gaps else None
    if route == "tonal":
        if A[1] < 1.8 * max(B[1], S[1]):
            flags.append(f"tonal accent's chroma is {A[1]:.2f}, under 1.8 times the regular colours' {max(B[1], S[1]):.2f}: it reads as a shade, not light")
        if A[0] < B[0] + 0.3:
            flags.append(f"tonal accent's lightness is {A[0]:.2f}, under the field's {B[0]:.2f} + 0.3: it reads as a shade, not light")
    elif gap is not None and gap < 75:
        flags.append(f"the accent is only {gap}° from a regular colour (at least 75; 120-180 pops hardest; or the tonal route)")
    return {"palette_flags": flags, "accent_gap": gap}


def crowded_hues(rows, width=30, most=2):
    """Runs of accents where some window of `width` degrees holds more than `most` of them, overlapping windows merged.
    Fixed 30° bands missed clusters that straddle a band edge."""
    hues = sorted((r["hue"], r["key"]) for r in rows)
    runs = []
    for h0, _ in hues:
        window = {k for h, k in hues if (h - h0) % 360 < width}
        if len(window) > most:
            for run in [r for r in runs if r & window]:
                runs.remove(run)
                window |= run
            runs.append(window)
    order = {k: h for h, k in hues}
    return [sorted(run, key=order.get) for run in runs]


def cmd_review(project, a):
    """A 320 px copy (judge wow there) and the four quarters at full size (hunt defects there) of each render."""
    concepts = load(project)
    out = project / "out" / "review"
    out.mkdir(parents=True, exist_ok=True)
    lanczos = getattr(Image, "Resampling", Image).LANCZOS
    for k in (a.concepts.split(",") if a.concepts else concepts):
        for p in variant_files(project, k):
            im = Image.open(p).convert("RGB")
            w, h = im.size
            im.resize((320, round(320 * h / w)), lanczos).save(out / f"{p.stem}-320.jpg", quality=92)
            for i, (x, y) in enumerate([(0, 0), (w // 2, 0), (0, h // 2), (w // 2, h // 2)], 1):
                im.crop((x, y, x + w // 2, y + h // 2)).save(out / f"{p.stem}-q{i}.jpg", quality=92)
            print(f"{p.stem}: {out}/{p.stem}-320.jpg, -q1 to -q4.jpg (top left, top right, bottom left, bottom right)")


def webp(src, dest, width=1400):
    if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
        im = Image.open(src).convert("RGB")
        if im.width > width:
            im = im.resize((width, round(im.height * width / im.width)), Image.Resampling.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "WEBP", quality=84, method=6)
    with Image.open(dest) as im:
        return im.size


def write_board(out, title, lead, sections, files, css="", script=""):
    """Write index.html and files.json, and delete images or clips from earlier builds that this board no longer shows."""
    out.mkdir(parents=True, exist_ok=True)
    for folder in ("img", "video"):
        for p in (out / folder).glob("*"):
            if f"{folder}/{p.name}" not in files:
                p.unlink()
    page = (BOARD.replace("{{TITLE}}", html.escape(title)).replace("{{LEAD}}", html.escape(lead)).replace("{{SECTIONS}}", "\n".join(sections))
            .replace("{{CSS}}", css).replace("{{SCRIPT}}", script))
    (out / "index.html").write_text(page)
    (out / "files.json").write_text(json.dumps([{"path": f} for f in sorted(files)]))
    print(f"{len(files)} files -> {out}/index.html")
    print("Open it in a browser. To publish it as an Artifact: file_path=<that index.html>, root=<that folder>, files=the list in files.json.")


def take_of(p):
    try:
        return json.loads(p.with_suffix(".json").read_text()).get("take", 0)
    except (OSError, ValueError):
        return 0


def cmd_swipe(project, a):
    """One render per variation (five per page): from the page's reference screenshot when it has one, otherwise from its
    written layout."""
    concepts = load(project)
    keys = a.concepts.split(",") if a.concepts else list(concepts)
    jobs = []
    for k in keys:
        c = concepts[k]
        ref = ref_path(c, project) if c.get("ref") else None
        if ref is not None and not ref.exists():
            sys.exit(f"{k}: reference {c['ref']} not found")
        if ref is None and c.get("layout") not in LAYOUTS:
            sys.exit(f"{k}: with no reference it needs a layout, one of: {', '.join(LAYOUTS)}")
        count = len(c["variations"])
        dests = [Path(f"{k}-variation-{i}.png") for i in range(1, count + 1)] if a.dry_run else claim(project, k, count)
        for i, (var, dest) in enumerate(zip(c["variations"], dests), 1):
            text = swipe_prompt(c, var) if ref else written_prompt(c, var)
            jobs.append((text, dest, ref, {"concept": k, "take": i, "ref": c.get("ref")}))
    if a.dry_run:
        for text, dest, ref, meta in jobs:
            print(f"===== {dest.name} (variation {meta['take']}, {'reference ' + ref.name if ref else 'no reference'})\n{text}\n")
        return
    key = openai_key(project)
    with ThreadPoolExecutor(max_workers=12) as pool:
        for f in as_completed([pool.submit(call, project, key, t, d, r, m) for t, d, r, m in jobs]):
            print(f.result(), flush=True)


def cmd_fix(project, a):
    src = project / "out" / "variants" / f"{a.render}.png"
    if not src.exists():
        sys.exit(f"{src} not found")
    meta = json.loads(src.with_suffix(".json").read_text())
    k = meta.get("concept", a.render.rsplit("-", 1)[0])
    key = openai_key(project)
    jobs = claim(project, k, a.n)
    with ThreadPoolExecutor(max_workers=a.n) as pool:
        for r in pool.map(lambda d: call(project, key, FIX.format(note=a.note), d, src,
                                         {"concept": k, "take": meta.get("take", 0), "fix_of": a.render, "note": a.note}), jobs):
            print(r, flush=True)


def expected_copy(c):
    """Every word to read back. The headline goes word by word: a split layout sets its words apart, and Vision reads the
    small type between them."""
    return [*c["headline"].split(), *re.findall(r'"([^"]+)"', c.get("ui", ""))]


def cmd_check(project, a):
    concepts = load(project)
    variants = [p for k in concepts for p in variant_files(project, k)]
    texts = {}
    if variants:
        try:
            texts = read_text(variants)
        except (OSError, subprocess.CalledProcessError):
            texts = None
            print("Word check skipped: it needs macOS Vision (the swift command). Read every word by eye.\n")
        print("RENDERS  (every word read back; the accent 15-30% of the frame)")
    rows, hues = {}, {}
    for p in variants:
        k = p.stem.rsplit("-", 1)[0]
        c = concepts[k]
        misses = [] if texts is None else [w for w in expected_copy(c) if found(w, texts.get(p.name, ("", []))[0]) is not True]
        share, hue = accent_share(small(p), c["palette"][2][1])
        hues.setdefault(k, []).append(hue)
        flags = ([f"read by eye: {misses}"] if misses else []) + ([f"accent {share:.1f}%, under 15"] if share < 15 else [])
        rows[p.stem] = {"accent_share": round(share, 1), "accent_hue": round(hue), "copy_flags": misses}
        print(f"  {p.stem:22s} accent {share:5.1f}% at {round(hue):3d}°  {'; '.join(flags) or 'ok'}")
    also = {}
    for path in a.also or []:
        also.update(json.loads(Path(path).read_text()))
    table = []
    for src_name, cs in (("new", concepts), ("also", also)):
        for k, c in cs.items():
            if "palette" not in c:
                continue
            h = circular_mean(hues[k]) if k in hues else lch(c["palette"][2][1])[2]
            table.append({"key": k, "source": src_name, "hue": round(h) % 360, "ref": c.get("ref") or "-", "layout": c.get("layout") or "-",
                          "route": c.get("route"), **palette_formula(c["palette"], c.get("route"))})
    # The spread rule is within the batch. Pages made before (--also) can already cover the wheel, so they are listed beside
    # each new accent that sits near them rather than flagged.
    new = [r for r in table if r["source"] == "new"]
    others = [r for r in table if r["source"] == "also"]
    flags = []
    for k, c in concepts.items():
        missing = [f for f in REQUIRED if not c.get(f)]
        if missing:
            flags.append(f"{k}: missing {', '.join(missing)}")
        if c.get("layout") and c["layout"] not in LAYOUTS:
            flags.append(f"{k}: layout {c['layout']} isn't one of {', '.join(LAYOUTS)}")
        if c.get("route") not in (None, "tonal"):
            flags.append(f"{k}: route {c['route']} isn't tonal (leave it out for the default)")
        if c.get("variations") and len(c["variations"]) < VARIATIONS:
            flags.append(f"{k}: {len(c['variations'])} variations ({VARIATIONS} per page)")
    for r in new:
        flags += [f"{r['key']}: {f}" for f in r["palette_flags"]]
        r["near"] = [s["key"] for s in others if float(hue_dist(r["hue"], s["hue"])) <= 15]
    for run in crowded_hues(new):
        flags.append(f"{len(run)} accents crowd one 30° stretch ({', '.join(run)}): at most 2")
    refs = Counter(r["ref"] for r in new if r["ref"] != "-")
    flags += [f"reference {Path(ref).name} used {n} times (once per batch)" for ref, n in refs.items() if n > 1]
    # A batch made only of the model's two default layouts reads as one template.
    layouts = Counter(c["layout"] for c in concepts.values() if c.get("layout"))
    if len(concepts) >= 2 and layouts:
        top, n = layouts.most_common(1)[0]
        if n > len(concepts) / 2:
            flags.append(f"{n} of {len(concepts)} pages use the {top} layout (half at most)")
    if len(concepts) >= 6 and len(layouts) < 4:
        flags.append(f"only {len(layouts)} layouts for {len(concepts)} pages (at least 4)")
    print("\nSET")
    for r in table:
        gap = ("(tonal)" if r.get("route") == "tonal" else f"({r['accent_gap']}° from the others)" if r.get("accent_gap") is not None
               else "(the others neutral)")
        ref = Path(r["ref"]).name if r["ref"] != "-" else "no reference"
        tail = (f"  near {', '.join(r['near'])}" if r.get("near") else "") if r["source"] == "new" else "  (made before)"
        print(f"  {r['key']:14s} accent {r['hue']:>3d}° {gap:22s} {r['layout']:14s} {ref}{tail}")
    print("\n" + ("\n".join(f"  FLAG {f}" for f in flags) if flags else "  set ok"))
    (project / "out").mkdir(parents=True, exist_ok=True)
    (project / "out" / "check.json").write_text(json.dumps({"renders": rows, "set": table, "set_flags": flags}, indent=1))


def cmd_board(project, a):
    """One section per page, its renders numbered from 1 with each fix right after the render it edits. Renders moved into
    out/variants/superseded/ are left out."""
    concepts = load(project)
    out = project / "out" / "board" / "variants"
    sections, files = [], []
    for k, c in concepts.items():
        tiles = []
        for i, p in enumerate(sorted(variant_files(project, k), key=lambda q: (take_of(q), q.stem)), 1):
            rel = f"img/{p.stem}.webp"
            w, h = webp(p, out / rel)
            files.append(rel)
            tiles.append(f'<figure class="tile"><div class="pic"><img src="{rel}" width="{w}" height="{h}" alt="{html.escape(c["brand"])} {i}" loading="lazy" decoding="async"></div><figcaption><b>{i}</b><span>{p.stem}</span></figcaption></figure>')
        if tiles:
            sections.append(f'<section><h2>{html.escape(c["brand"])}</h2><div class="grid">{"".join(tiles)}</div></section>')
    if not files:
        sys.exit(f"Nothing to show: no renders in {project / 'out' / 'variants'} yet.")
    write_board(out, a.title, f"{len(files)} renders of {len(sections)} pages, numbered per page.", sections, files)


BOARD = """<title>{{TITLE}}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,300..800&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: a dark gallery, two heroes per row; numbers and names only so the work does the talking. */
:root {
  --bg: #0d0e10; --fg: #eceef0; --muted: #9aa0a8; --line: rgba(236, 238, 240, 0.12); --tile: #16181b;
  --display: "Bricolage Grotesque", "Helvetica Neue", Arial, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
  color-scheme: dark;
}
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--fg); font-family: var(--display); margin: 0;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 0 80px; }
header, section { max-width: 1400px; margin: 0 auto; }
header { padding-block: 56px 8px; display: grid; gap: 14px; }
h1 { font-size: clamp(40px, 7vw, 88px); font-weight: 760; font-stretch: 78%; line-height: .9; letter-spacing: -0.03em; margin: 0; }
header p { color: var(--muted); font-size: 16px; margin: 0; max-width: 62ch; }
section { padding-block: 56px 40px; border-bottom: 1px solid var(--line); }
h2 { font-size: clamp(26px, 3.4vw, 40px); font-weight: 700; font-stretch: 82%; letter-spacing: -0.02em; margin: 0 0 20px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 560px), 1fr)); gap: 28px 20px; }
.tile { margin: 0; display: grid; gap: 8px; }
.pic { position: relative; display: block; width: 100%; padding: 0; border: 0; background: var(--tile); border-radius: 6px; overflow: hidden; }
.pic img, video { display: block; width: 100%; height: auto; }
video { border-radius: 6px; background: var(--tile); }
figcaption { display: flex; align-items: center; gap: 12px; font-family: var(--mono); font-size: 13px; color: var(--muted); min-height: 22px; }
figcaption b { color: var(--fg); font-size: 15px; font-weight: 500; }
:focus-visible { outline: 2px solid var(--fg); outline-offset: 3px; }
{{CSS}}
</style>
<header>
  <h1>{{TITLE}}</h1>
  <p>{{LEAD}}</p>
</header>
{{SECTIONS}}
{{SCRIPT}}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("render", "swipe", "fix", "check", "review", "board"):
        p = sub.add_parser(name, help="the older name of render" if name == "swipe" else None)
        p.add_argument("--project", required=True, type=Path)
        if name in ("render", "swipe", "review"):
            p.add_argument("--concepts", help="comma-separated keys from concepts.json; all of them when left out")
        if name in ("render", "swipe"):
            p.add_argument("--dry-run", action="store_true", help="print the prompts and stop")
        if name == "fix":
            p.add_argument("--render", required=True, help="the render to edit, like strata-2")
            p.add_argument("--note", required=True, help="what to change, in one or two plain sentences")
            p.add_argument("--n", type=int, default=2, help="how many versions of the fix (default 2)")
        if name == "check":
            p.add_argument("--also", action="append", help="the concepts.json of pages made before; each new accent lists the ones it sits within 15° of")
        if name == "board":
            p.add_argument("--title", default="Hero renders")
    a = ap.parse_args()
    {"render": cmd_swipe, "swipe": cmd_swipe, "fix": cmd_fix, "check": cmd_check, "review": cmd_review, "board": cmd_board}[a.cmd](a.project, a)


if __name__ == "__main__":
    main()
