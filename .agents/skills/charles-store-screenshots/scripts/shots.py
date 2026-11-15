#!/usr/bin/env python3
"""Tools for building App Store screenshot sets (see ../SKILL.md).

  render <set.html> [--out DIR]          frames/NN.png at 1320 x 2868, preview.jpg, search.png
  art "<prompt>" --out art/x.png         one generated image (objects, materials, worlds; never people)
      [--size 1024x1536] [--transparent] [--quality high|medium] [--ref img ...] [--n 2]
  cutout <photo> <out.png>               a person or object cut out with BiRefNet (fal.ai)
  font "<Google Fonts family spec>" --out fonts/    e.g. "Instrument Serif:ital@0;1", "Anton"
  board <set-dir>... --out board.html [--title T] [--embed]

Keys: OPENAI_API_KEY (art) and FAL_KEY (cutout), from the environment or a .env in or above the working folder.
"""
import argparse
import base64
import io
import json
import os
import re
import sys
import time
import html as H
from pathlib import Path

import requests
from PIL import Image

FW, FH, SCALE = 440, 956, 3
# App Store sizes a set renders to: the frame's CSS size times --scale must be one of these.
STORE_SIZES = {(1320, 2868): "iPhone 6.9in", (2064, 2752): "iPad 13in", (1398, 2034): "iPhone Duo"}            # one frame in CSS px, rendered @3x
EXPORT = (FW * SCALE, FH * SCALE)       # 1320 x 2868: Apple's 6.9" iPhone size
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
IMAGE_MODEL = os.environ.get("SHOTS_IMAGE_MODEL", "gpt-image-2.6-sunburst")


def env_key(name):
    if os.environ.get(name):
        return os.environ[name]
    here = Path.cwd().resolve()
    for folder in [here, *here.parents, *Path(__file__).resolve().parents]:
        env = folder / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith(f"{name}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit(f"{name} not found: set it in the environment or in a .env in or above this folder.")


# ---------------------------------------------------------------- render

def render(args):
    from playwright.sync_api import sync_playwright

    src = Path(args.html).resolve()
    out = Path(args.out).resolve() if args.out else src.parent
    (out / "frames").mkdir(parents=True, exist_ok=True)
    problems = []
    with sync_playwright() as p:
        launch = {"executable_path": CHROME} if Path(CHROME).exists() else {}
        browser = p.chromium.launch(**launch)
        scale = args.scale
        page = browser.new_page(viewport={"width": 4400, "height": 1400}, device_scale_factor=scale)
        page.on("console", lambda m: m.type in ("error", "warning") and problems.append(f"console {m.type}: {m.text}"))
        page.on("requestfailed", lambda r: problems.append(f"failed to load: {r.url}"))
        page.goto(src.as_uri(), wait_until="networkidle")
        fw, fh = page.evaluate("() => { const r = document.querySelector('.strip > .frame').getBoundingClientRect(); return [r.width, r.height]; }")
        export = (round(fw * scale), round(fh * scale))
        if export not in STORE_SIZES:
            problems.append(f"{export[0]} x {export[1]} is not a store size ({', '.join(f'{w} x {h} {n}' for (w, h), n in STORE_SIZES.items())})")
        width = page.evaluate("() => Math.ceil(document.querySelector('.strip').getBoundingClientRect().width)")
        page.set_viewport_size({"width": max(width, round(fw)), "height": round(fh)})
        state = page.evaluate("""async () => {
            await document.fonts.ready;
            await Promise.all([...document.images].map(i => i.decode().catch(() => null)));
            const fonts = [...document.fonts].filter(f => f.status === 'error').map(f => f.family);
            const images = [...document.images].filter(i => !i.naturalWidth).map(i => i.getAttribute('src'));
            const frames = [...document.querySelectorAll('.strip > .frame')].map((e, i) => {
                const r = e.getBoundingClientRect();
                return {name: e.dataset.name || String(i + 1).padStart(2, '0'), x: r.x, y: r.y, w: r.width, h: r.height};
            });
            return {fonts, images, frames};
        }""")
        page.wait_for_timeout(600)
        problems += [f"font failed: {f}" for f in state["fonts"]] + [f"image missing: {i}" for i in state["images"]]
        files = []
        for f in state["frames"]:
            if abs(f["w"] - fw) > 0.5 or abs(f["h"] - fh) > 0.5:
                problems.append(f"frame {f['name']} is {f['w']} x {f['h']}, not {fw} x {fh}")
            png = page.screenshot(clip={"x": f["x"], "y": f["y"], "width": fw, "height": fh}, type="png")
            im = Image.open(io.BytesIO(png)).convert("RGB")
            if im.size != export:
                im = im.resize(export, Image.Resampling.LANCZOS)
            dest = out / "frames" / f"{f['name']}.png"
            im.save(dest, optimize=True)
            files.append(dest)
        browser.close()

    frames = [Image.open(f) for f in files]
    strip(frames, 1200, 24, (17, 17, 17)).save(out / "preview.jpg", quality=88)
    # Search results show the first three portrait frames at about 115 pt wide (345 px on a 3x phone).
    rows = [strip(frames[:3], 750, 12, bg) for bg in ((255, 255, 255), (0, 0, 0))]
    search = Image.new("RGB", (rows[0].width, rows[0].height * 2), (128, 128, 128))
    search.paste(rows[0], (0, 0)); search.paste(rows[1], (0, rows[0].height))
    search.save(out / "search.png")
    print(f"{len(files)} frames -> {out / 'frames'}  (+ preview.jpg, search.png)")
    for prob in problems:
        print("PROBLEM", prob)
    if problems:
        sys.exit(1)


def strip(frames, height, gap, bg):
    w = round(height * frames[0].width / frames[0].height)   # each device keeps its own aspect
    canvas = Image.new("RGB", (len(frames) * (w + gap) + gap, height + 2 * gap), bg)
    for i, im in enumerate(frames):
        canvas.paste(im.resize((w, height), Image.Resampling.LANCZOS), (gap + i * (w + gap), gap))
    return canvas


# ---------------------------------------------------------------- art

def art(args):
    key = env_key("OPENAI_API_KEY")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = {"model": IMAGE_MODEL, "prompt": args.prompt, "size": args.size, "quality": args.quality,
              "n": args.n, "output_format": "png"}
    if args.transparent:
        fields["background"] = "transparent"
    headers = {"Authorization": f"Bearer {key}"}
    for attempt in (1, 2):
        t0 = time.time()
        try:
            if args.ref:
                files = [("image[]", (Path(r).name, open(r, "rb"), "image/png")) for r in args.ref]
                r = requests.post("https://api.openai.com/v1/images/edits", headers=headers,
                                  data={k: str(v) for k, v in fields.items()}, files=files, timeout=(15, 400))
            else:
                r = requests.post("https://api.openai.com/v1/images/generations", headers=headers, json=fields,
                                  timeout=(15, 400))
            if r.status_code != 200:
                raise RuntimeError(f"{r.status_code}: {r.text[:500]}")
            data = r.json()["data"]
            for i, item in enumerate(data):
                dest = out if len(data) == 1 else out.with_name(f"{out.stem}-{i + 1}{out.suffix}")
                dest.write_bytes(base64.b64decode(item["b64_json"]))
                side = {k: v for k, v in fields.items() if k != "prompt"}
                side.update(prompt=args.prompt, ref=args.ref, seconds=round(time.time() - t0, 1))
                dest.with_suffix(".json").write_text(json.dumps(side, indent=1))
                print(f"{dest}  ({side['seconds']}s)")
            return
        except Exception as e:
            if attempt == 2:
                sys.exit(f"art failed: {e}")
            print(f"retrying after: {str(e)[:200]}")


# ---------------------------------------------------------------- cutout

def cutout(args):
    key = env_key("FAL_KEY")
    src = Path(args.photo)
    im = Image.open(src)
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "PNG")
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    body = {"image_url": uri, "model": "General Use (Heavy)", "operating_resolution": "2048x2048",
            "output_format": "png", "refine_foreground": True}
    r = requests.post("https://fal.run/fal-ai/birefnet/v2", headers={"Authorization": f"Key {key}"}, json=body,
                      timeout=(15, 300))
    if r.status_code != 200:
        sys.exit(f"cutout failed: {r.status_code} {r.text[:400]}")
    url = r.json()["image"]["url"]
    png = requests.get(url, timeout=120).content
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cut = Image.open(io.BytesIO(png)).convert("RGBA")
    if cut.size != im.size:
        cut = cut.resize(im.size, Image.Resampling.LANCZOS)
    cut.save(out)
    print(f"{out}  {cut.size}")


# ---------------------------------------------------------------- font

def fetch(url, tries=4, headers=None):
    for attempt in range(1, tries + 1):
        try:
            r = requests.get(url, timeout=(10, 60), headers=headers)
            r.raise_for_status()
            return r.content
        except requests.RequestException:
            if attempt == tries:
                raise
            time.sleep(2 * attempt)


def font(args):
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    url = "https://fonts.googleapis.com/css2?family=" + args.family.replace(" ", "+") + "&display=block"
    css = fetch(url, headers={"User-Agent": ua}).decode()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rules = []
    for subset, block in re.findall(r"/\* ([\w-]+) \*/\s*(@font-face \{.*?\})", css, re.S):
        if subset not in ("latin", "latin-ext"):
            continue
        family = re.search(r"font-family: '([^']+)'", block).group(1)
        style = re.search(r"font-style: (\w+)", block).group(1)
        weight = re.search(r"font-weight: ([\d ]+)", block).group(1)
        src = re.search(r"url\((https://[^)]+)\)", block).group(1)
        name = f"{family.replace(' ', '')}-{style}-{weight.replace(' ', '_')}-{subset}.woff2"
        (out / name).write_bytes(fetch(src))
        rules.append(block.replace(src, name))
    if not rules:
        sys.exit("font failed: no latin faces in the response")
    with open(out / "fonts.css", "a") as f:
        f.write(f"/* {args.family} */\n" + "\n".join(rules) + "\n")
    print(f"{len(rules)} faces -> {out}/fonts.css")


# ---------------------------------------------------------------- board

def data_uri(im, quality=84):
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def board(args):
    out = Path(args.out).resolve()
    cards, tiles = [], []
    for d in map(Path, args.sets):
        d = d.resolve()
        preview = d / "preview.jpg"
        if not preview.exists():
            print(f"skipping {d.name}: no preview.jpg (render it first)")
            continue
        plan = {}
        page = d / "set.html"
        if page.exists():
            m = re.search(r"<!--(.*?)-->", page.read_text(), re.S)
            for line in (m.group(1).splitlines() if m else []):
                if ":" in line and not line.strip().startswith(("|", "-")):
                    k, v = line.split(":", 1)
                    plan[k.strip().lower()] = v.strip()
        name = H.escape(plan.get("name", d.name))
        if args.embed:
            im = Image.open(preview)
            im.thumbnail((5200, 1200))
            src = data_uri(im)
        else:
            src = os.path.relpath(preview, out.parent)
        # The first three frames as search results show them: small, side by side.
        thumbs = []
        for i in (1, 2, 3):
            frame = d / "frames" / f"{i:02d}.png"
            if not frame.exists():
                break
            im = Image.open(frame).convert("RGB")
            im.thumbnail((345, 750), Image.Resampling.LANCZOS)
            if args.embed:
                thumbs.append(data_uri(im, 86))
            else:
                (d / "thumbs").mkdir(exist_ok=True)
                im.save(d / "thumbs" / f"{i:02d}.jpg", quality=86)
                thumbs.append(os.path.relpath(d / "thumbs" / f"{i:02d}.jpg", out.parent))
        if len(thumbs) == 3:
            shots = "".join(f'<img src="{t}" alt="" loading="lazy">' for t in thumbs)
            tiles.append(f'<a class="tile" href="#{H.escape(d.name)}"><span>{name}</span><div>{shots}</div></a>')
        meta = " · ".join(H.escape(plan[k]) for k in ("lane", "move") if plan.get(k))   # the hook is the picture itself
        cards.append(f'<section class="set" id="{H.escape(d.name)}"><h2>{name}</h2><p>{meta}</p>'
                     f'<div class="row"><img src="{src}" alt="{H.escape(d.name)}" loading="lazy"></div></section>')
    page = (BOARD.replace("{{TITLE}}", H.escape(args.title)).replace("{{TILES}}", "\n".join(tiles))
            .replace("{{SETS}}", "\n".join(cards)))
    out.write_text(page)
    print(f"{out}  ({len(cards)} sets)")


BOARD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{{TITLE}}</title>
<style>
:root{--bg:#0f0f11;--ink:#f2f2f4;--ink2:#9d9da6;--line:#26262b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text",sans-serif;-webkit-font-smoothing:antialiased}
header{padding:36px 24px 8px;max-width:1400px;margin:0 auto}h1{font-size:clamp(26px,3.6vw,42px);letter-spacing:-.02em;margin:0 0 6px}
header p{color:var(--ink2);margin:0}.set{max-width:1400px;margin:28px auto 0;padding:0 24px}
h2{font-size:18px;margin:0 0 2px}.set p,.search p{color:var(--ink2);margin:0 0 12px;font-size:14px}
.row{overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:#000}
.row img{display:block;height:min(62vh,640px);width:auto;cursor:zoom-in}
.lb{position:fixed;inset:0;background:rgba(0,0,0,.95);display:none;overflow:auto;cursor:zoom-out;z-index:9}
.lb.on{display:block}.lb img{height:96vh;width:auto;display:block;margin:2vh auto}
.search{max-width:1400px;margin:24px auto 0;padding:0 24px}.search h2{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.search button{font:inherit;font-size:13px;color:var(--ink);background:#1b1b1f;border:1px solid var(--line);border-radius:999px;padding:5px 12px;cursor:pointer}
.search button:focus-visible,.tile:focus-visible{outline:2px solid #ffd34d;outline-offset:2px}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr))}
.tile{display:block;background:#fff;color:#111;border-radius:16px;padding:12px;text-decoration:none;scroll-margin-top:12px}
.tile span{display:block;font-size:13px;font-weight:600;margin:0 2px 8px}
.tile div{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.tile img{display:block;width:100%;height:auto;border-radius:9px}
.grid.dark .tile{background:#000;color:#f2f2f4}.set{scroll-margin-top:12px}
@media (max-width:640px){header,.set,.search{padding:0 16px}header{padding-top:24px}.row img{height:52vh}}
</style></head><body><header><h1>{{TITLE}}</h1><p>First, how each set looks in search results. Below that, every set in full: scroll it sideways, or click it to see it full height.</p></header>
<section class="search"><h2>In search results <button type="button" aria-pressed="false">Show on dark</button></h2>
<p>Search shows a set's first three frames at about this size. Click one to jump to the full set.</p>
<div class="grid">
{{TILES}}
</div></section>
{{SETS}}
<div class="lb"><img alt=""></div>
<script>const lb=document.querySelector('.lb'),li=lb.querySelector('img');
document.querySelectorAll('.row img').forEach(i=>i.onclick=()=>{li.src=i.src;lb.classList.add('on')});
lb.onclick=()=>lb.classList.remove('on');document.onkeydown=e=>{if(e.key==='Escape')lb.classList.remove('on')};
const g=document.querySelector('.grid'),b=document.querySelector('.search button');
b.onclick=()=>{const d=g.classList.toggle('dark');b.setAttribute('aria-pressed',d);b.textContent=d?'Show on light':'Show on dark'};</script>
<div style="height:64px"></div></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("render"); p.add_argument("html"); p.add_argument("--out")
    p.add_argument("--scale", type=float, default=3, help="device scale: 3 for iPhone and iPhone Duo, 2 for iPad")
    p = sub.add_parser("art"); p.add_argument("prompt"); p.add_argument("--out", required=True)
    p.add_argument("--size", default="1024x1536"); p.add_argument("--quality", default="high")
    p.add_argument("--transparent", action="store_true"); p.add_argument("--ref", nargs="*")
    p.add_argument("--n", type=int, default=1)
    p = sub.add_parser("cutout"); p.add_argument("photo"); p.add_argument("out")
    p = sub.add_parser("font"); p.add_argument("family"); p.add_argument("--out", required=True)
    p = sub.add_parser("board"); p.add_argument("sets", nargs="+"); p.add_argument("--out", required=True)
    p.add_argument("--title", default="Screenshot sets"); p.add_argument("--embed", action="store_true")
    args = ap.parse_args()
    {"render": render, "art": art, "cutout": cutout, "font": font, "board": board}[args.cmd](args)


if __name__ == "__main__":
    main()
