#!/usr/bin/env python3
"""Mount the beats of an arcade project into its index.html.

  mount.py <dir>

Reads <dir>/beats.json:
  {"duration": 22.4, "beats": [{"id": "b01", "start": 0, "dur": 1.7, "blueprint": "prop-reveal"}, ...]}
For a beat with a "blueprint" whose compositions/<id>.html does not exist yet, copies the blueprint there with
SCENE replaced by the id (edit it afterwards). The project's shape picks the layout: wide frames (width/height
1.3 or more, like the 2:1 card) get blueprints/wide/ (laid out at 1280x630), tall cards (0.75 to 0.95, like
1280x1550) get blueprints/tallcard/ (laid out at 1280x1550), full screens (under 0.75, like 1080x1920) get
blueprints/, everything between gets blueprints/short/ (laid out at 1080x960). A blueprint missing from that
family is copied from the nearest one, with a note to re-lay it out.
A beat without a blueprint needs its own compositions/<id>.html.
Writes one host per beat into index.html and sets the root duration (the audio length, or the last beat's end).
Run it again after any timing change; it never touches existing scene files.
"""
import json, re, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
FAMILIES = {"wide": ("wide", 1280, 630), "short": ("short", 1080, 960), "tallcard": ("tallcard", 1280, 1550),
            "tall": ("", 1080, 1920)}
NEAREST = {"wide": ["wide", "short", "tallcard", "tall"], "short": ["short", "tallcard", "wide", "tall"],
           "tallcard": ["tallcard", "short", "tall", "wide"], "tall": ["tall", "tallcard", "short", "wide"]}


def family(w, h):
    r = w / h
    return "wide" if r >= 1.3 else "tall" if r < 0.75 else "tallcard" if r < 0.95 else "short"


def find_blueprint(name, fam):
    for f in NEAREST[fam]:
        src = SKILL / "blueprints" / FAMILIES[f][0] / f"{name}.html"
        if src.exists():
            return src, f
    return None, None


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    root = Path(sys.argv[1])
    spec = json.loads((root / "beats.json").read_text())
    beats = spec["beats"]
    idx = (root / "index.html").read_text()
    w = re.search(r'data-width="(\d+)"', idx).group(1)
    h = re.search(r'data-height="(\d+)"', idx).group(1)
    fam = family(int(w), int(h))
    _, dw, dh = FAMILIES[fam]
    if abs(int(w) / int(h) - dw / dh) > 0.1 * dw / dh:
        print(f"note: {fam} blueprints are laid out at {dw}x{dh}; at {w}x{h}, move each scene's content inside "
              f"its text area and re-space it")
    hosts, end, problems = [], 0.0, []
    for b in sorted(beats, key=lambda b: b["start"]):
        sid, start, dur = b["id"], float(b["start"]), float(b["dur"])
        scene = root / "compositions" / f"{sid}.html"
        if not scene.exists():
            if b.get("blueprint"):
                src, got = find_blueprint(b["blueprint"], fam)
                if not src:
                    problems.append(f"{sid}: no blueprint named {b['blueprint']}")
                    continue
                text = src.read_text().replace("SCENE", sid)
                text = re.sub(r'(<div id="root"[^>]*?)data-width="\d+" data-height="\d+"',
                              rf'\g<1>data-width="{w}" data-height="{h}"', text, count=1)
                scene.write_text(text)
                note = "" if got == fam else f"; it has no {fam} version, so this is the {got} one: re-lay it out for {w}x{h}"
                print(f"{sid}: copied {got} blueprint {b['blueprint']} -> {scene} (now edit it{note})")
            else:
                problems.append(f"{sid}: {scene} is missing")
        hosts.append(f'      <div id="{sid}" data-composition-id="{sid}" data-composition-src="compositions/{sid}.html"\n'
                     f'           data-start="{start:.3f}" data-duration="{dur:.3f}" data-track-index="1" data-track-kind="graphics"\n'
                     f'           data-width="{w}" data-height="{h}"></div>')
        end = max(end, start + dur)
    total = float(spec.get("duration") or 0) or end
    block = "      <!-- beats:start -->\n" + "\n".join(hosts) + "\n      <!-- beats:end -->"
    if "<!-- beats:start -->" in idx:
        idx = re.sub(r"      <!-- beats:start -->.*?<!-- beats:end -->", block, idx, flags=re.S)
    else:
        idx = re.sub(r"(<div\s+id=\"root\"[^>]*>)", r"\1\n" + block.replace("\\", "\\\\"), idx, count=1)
    idx = re.sub(r'(<div\s+id="root"[^>]*?data-duration=")[^"]*(")', rf"\g<1>{total:.2f}\2", idx, count=1)
    idx = re.sub(r'(<audio id="voice"[^>]*?data-duration=")[^"]*(")', rf"\g<1>{total:.2f}\2", idx, count=1)
    (root / "index.html").write_text(idx)
    gaps = []
    t = 0.0
    for b in sorted(beats, key=lambda b: b["start"]):
        if b["start"] - t > 0.05:
            gaps.append(f"{t:.2f}-{b['start']:.2f}")
        t = max(t, b["start"] + b["dur"])
    print(f"mounted {len(hosts)} beats, root {total:.2f} s" + (f"; uncovered: {', '.join(gaps)}" if gaps else ""))
    if end > total + 0.01:
        problems.append(f"beats run to {end:.2f} s, past the root duration {total:.2f} s")
    for p in problems:
        print("PROBLEM:", p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
