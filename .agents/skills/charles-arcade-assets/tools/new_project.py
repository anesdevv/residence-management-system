#!/usr/bin/env python3
"""Start an arcade HyperFrames project, or a set of them that share one look.

  new_project.py <dir> [--audio voice.m4a] [--cast claude,gpt] [--size 1080x1920] [--duration seconds]
  new_project.py <dir> --set card:1280x630,tall:1280x1550,full:1080x1920 --duration seconds [--start s] [--cast ...]

Copies the template (index.html, arcade.css/js, names.js, pixel fonts), the chosen cast members (poses +
ref.png) into assets/cast/, and the audio (reel mode) to assets/voice.m4a. Without --audio the project is in clip
mode: no voice track, --duration sets the part's length, and render it with a transparent format when it goes
over footage.

--set makes one folder for a video whose assets come in several sizes (a 2:1 card, a tall card, a full screen):
one project per size (<dir>/card, <dir>/tall, ...), each with its own index.html, beats.json and compositions/,
all on the same clock (--duration, the whole span the set covers), and one shared <dir>/assets that every
project's assets/ links to: the kit, names.js, video.css and video.js (this video's own styles and helpers,
loaded by every size), cast/, art/, logos/, clips/. Fetch, generate and key everything into <dir>/assets once;
every size sees it. Transcribe in <dir>. It prints each project's mount and render commands; renders go to
<dir>/out/part_<start>_<W>x<H>.mp4 (--start names them: the set's start in the source video, default 0).
"""
import argparse, json, os, re, shutil, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
T = "skills/charles-arcade-assets"
HF = "npx --yes hyperframes@0.8.217"
SHARED = ("art", "cast", "clips", "logos")


def copy_cast(assets, cast):
    """The props library and the named cast members into assets/cast."""
    if (SKILL / "cast" / "props").is_dir():
        shutil.copytree(SKILL / "cast" / "props", assets / "cast" / "props", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("raw", "review", "*.fal.json", "costs.jsonl"))
    for name in [c.strip() for c in cast.split(",") if c.strip()]:
        src = SKILL / "cast" / name
        if not src.is_dir():
            sys.exit(f"no cast member '{name}' in {SKILL / 'cast'}")
        dst = assets / "cast" / name
        shutil.copytree(src / "poses", dst / "poses", dirs_exist_ok=True)
        shutil.copy(src / "ref.png", dst / "ref.png")
        shutil.copy(src / "cast.json", dst / "cast.json")


def write_index(out, w, h, audio, duration, extra_head=""):
    """index.html at this size; the voice track in reel mode, none in clip mode. Returns the duration."""
    idx = (out / "index.html").read_text()
    idx = idx.replace('data-width="1080" data-height="1920"', f'data-width="{w}" data-height="{h}"')
    idx = idx.replace("width=1080, height=1920", f"width={w}, height={h}")
    idx = idx.replace("width: 1080px; height: 1920px;", f"width: {w}px; height: {h}px;")
    if h < w:
        idx = idx.replace('data-resolution="portrait"', 'data-resolution="landscape"')
    if extra_head:                                # after the kit's own files, before the page style
        at = idx.find("    <style>", 0, idx.find("</head>"))
        at = at if at >= 0 else idx.find("  </head>")
        idx = idx[:at] + extra_head + idx[at:]
    if audio:
        voice = "assets/voice.m4a" if audio.endswith(".m4a") else f"assets/{Path(audio).name}"
        idx = idx.replace('src="assets/voice.m4a"', f'src="{voice}"')
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio],
                               capture_output=True, text=True)
        duration = round(float(probe.stdout.strip()), 2)
        idx = idx.replace('data-duration="DURATION"', f'data-duration="{duration}"')
    else:
        idx = re.sub(r'\s*<audio id="voice".*?</audio>', "", idx, flags=re.S)
        duration = round(duration, 3) if duration else 0.0
        idx = idx.replace('data-duration="DURATION"', f'data-duration="{duration or 1}"')
    (out / "index.html").write_text(idx)
    (out / "beats.json").write_text(json.dumps({"duration": duration, "beats": []}, indent=1) + "\n")
    return duration


def copy_audio(audio, assets):
    shutil.copy(audio, assets / "voice.m4a" if audio.endswith(".m4a") else assets / Path(audio).name)


def single(args):
    out = Path(args.dir)
    if (out / "index.html").exists():
        sys.exit(f"{out} already has a project")
    shutil.copytree(SKILL / "template", out, dirs_exist_ok=True)
    for d in ("assets/art", "assets/clips", "assets/cast", "compositions"):
        (out / d).mkdir(parents=True, exist_ok=True)
    copy_cast(out / "assets", args.cast)
    w, h = (int(x) for x in args.size.split("x"))
    if args.audio:
        copy_audio(args.audio, out / "assets")
    duration = write_index(out, w, h, args.audio, args.duration)
    print(f"project: {out}  ({w}x{h}, {'reel, ' + str(duration) + ' s of audio' if args.audio else 'clip mode, no audio'})")


def parse_set(text):
    sizes = []
    for item in [s.strip() for s in text.split(",") if s.strip()]:
        m = re.fullmatch(r"([A-Za-z][\w-]*):(\d+)x(\d+)", item)
        if not m:
            sys.exit(f"--set {item}: write each size as name:WxH, e.g. card:1280x630")
        sizes.append((m.group(1), int(m.group(2)), int(m.group(3))))
    names = [n for n, _, _ in sizes]
    if len(set(names)) != len(names) or {"assets", "out"} & set(names):
        sys.exit("--set: give every size its own name (not 'assets' or 'out')")
    return sizes


def asset_set(args):
    sizes = parse_set(args.set)
    if not args.duration and not args.audio:
        sys.exit("--set needs --duration: the whole span the set covers, in seconds")
    root = Path(args.dir)
    assets = root / "assets"
    fresh = not (assets / "arcade.js").exists()
    if fresh:                                     # the one shared assets folder
        shutil.copytree(SKILL / "template" / "assets", assets, dirs_exist_ok=True)
        (assets / "video.css").write_text(
            "/* This video's own styles, shared by every size in the set (each index.html loads it after the kit).\n"
            "   Size-specific rules go in the scene files. */\n")
        (assets / "video.js").write_text(
            "/* This video's own helpers, shared by every size in the set (loaded after the kit, before the scenes):\n"
            "   e.g. window.VID = { hud(tl, sel, t) { ... } }. */\n")
    for d in SHARED:
        (assets / d).mkdir(parents=True, exist_ok=True)
    copy_cast(assets, args.cast)
    if args.audio:
        copy_audio(args.audio, assets)
    (root / "out").mkdir(parents=True, exist_ok=True)
    head = ('    <link rel="stylesheet" href="assets/video.css" />\n'
            '    <script src="assets/video.js"></script>\n')
    made, rows = [], []
    for name, w, h in sizes:
        proj = root / name
        if (proj / "index.html").exists():
            rows.append((name, w, h, proj, "exists, left as it is"))
            continue
        proj.mkdir(parents=True, exist_ok=True)
        for f in ("index.html", "hyperframes.json", "package.json"):
            shutil.copy(SKILL / "template" / f, proj / f)
        (proj / "compositions").mkdir(exist_ok=True)
        link = proj / "assets"
        if link.is_symlink() or link.exists():
            sys.exit(f"{link} already exists: move it away first (the set links each size's assets/ to {assets})")
        os.symlink(os.path.relpath(assets, proj), link)
        duration = write_index(proj, w, h, args.audio, args.duration, head)
        made.append(name)
        rows.append((name, w, h, proj, f"{duration} s"))
    tag = f"{args.start:05.1f}"
    print(f"set: {root}  one look, {len(sizes)} sizes, shared assets in {assets}/ "
          f"({'made' if fresh else 'kept'}: kit, names.js, video.css, video.js, {', '.join(d + '/' for d in SHARED)})")
    for name, w, h, proj, note in rows:
        print(f"  {name:6} {w}x{h}  {proj}/  ({note})")
    print("Each size is its own project: write its beats.json, then mount, check and render it:")
    for name, w, h, proj, note in rows:
        print(f"  python3 {T}/tools/mount.py {proj}")
    for name, w, h, proj, note in rows:
        print(f"  cd {proj} && {HF} render -o ../out/part_{tag}_{w}x{h}.mp4")
    print(f"Fetch and generate into {assets}/ (art, cast, logos, photos, web), put names and facts in "
          f"{assets}/names.js and shared CSS/JS in video.css and video.js: every size uses them. Transcribe in "
          f"{root}/ (one transcript for the set).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir")
    ap.add_argument("--audio")
    ap.add_argument("--cast", default="claude,gpt")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--duration", type=float, help="clip mode: the part's length in seconds")
    ap.add_argument("--set", help="several sizes sharing one assets folder: name:WxH,name:WxH,...")
    ap.add_argument("--start", type=float, default=0.0, help="--set: the set's start in the source video (names renders)")
    args = ap.parse_args()
    if args.set:
        asset_set(args)
    else:
        single(args)


if __name__ == "__main__":
    main()
