#!/usr/bin/env python3
"""Find the glitches a viewer sees at full speed but a contact sheet hides.

  qa.py <video> [--ranges 0-8.13,11.87-15.5 | ranges.json] [--cut 14]

Reports, with times in the video's own seconds:
  flash   one or two frames of other art between two frames that match (a beat that ends a frame early,
          a sprite that pops in and out, a scene host showing through); a shake or a white hit flash is fine
          and is not reported
  blink   a shot of one or two frames between two different shots (two cuts that should be one, or a wipe or
          iris too fast to read: give it four frames or more, or make it a cut)
  edge    a cut within two frames of a range's start or end: charles-claude-editing cuts there to its own frame grid, so a
          frame of rounding shows the neighbouring beat. Hold the range's first and last frames for 0.1 s.
  sparse  0.5 s or more where one flat colour covers nearly all the frame (an empty screen, a lone mascot)
  still   1.2 s or more with nothing moving
Look at each report before fixing it (a 12 fps strip around it): a deliberate hit frame can show up as a blink,
and a frame torn between two shots (the top from one, the bottom from the next) always is one.
--ranges (asset sets) checks edges and limits sparse and still to the ranges: the gaps are hold beats nobody
sees. A ranges.json is [[start, end], ...] or {"card": [[s, e], ...], ...} (every list is checked).
--cut is the mean colour change (0-255) that counts as a cut; lower it if real cuts go unreported.
Needs ffmpeg and numpy (the repo venv). Prints nothing but "clean" when there is nothing to fix.
"""
import argparse, json, subprocess, sys

import numpy as np

W = 64                                  # frames are compared at this width


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate", "-of", "json", path], capture_output=True, text=True)
    if out.returncode:
        sys.exit(f"ffprobe could not read {path}: {out.stderr[-300:]}")
    s = json.loads(out.stdout)["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return s["width"], s["height"], float(num) / float(den)


def frames(path, w, h):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-fps_mode", "passthrough", "-vf", f"scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    data = p.stdout.read()
    p.wait()
    n = len(data) // (w * h * 3)
    return np.frombuffer(data[:n * w * h * 3], np.uint8).reshape(n, h, w, 3).astype(np.float32)


def parse_ranges(arg):
    if not arg:
        return []
    if arg.endswith(".json"):
        r = json.load(open(arg))
        lists = r.values() if isinstance(r, dict) else [r]
        return sorted((float(a), float(b)) for lst in lists for a, b in lst)
    return sorted(tuple(float(x) for x in part.split("-")) for part in arg.split(","))


def spans(mask, fps, min_len):
    """[(start s, end s)] of runs of True at least min_len seconds long."""
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            if (j - i) / fps >= min_len:
                out.append((i / fps, j / fps))
            i = j
        else:
            i += 1
    return out


def fade_step(mid, a, b, change):
    """True when `mid` is a cross-fade of `a` and `b` (a quick dissolve or a fade-in), not a frame of something else
    or a frame torn between the two (the top from one shot, the bottom from the next)."""
    return min(np.abs(mid - (x * a + (1 - x) * b)).mean() for x in np.linspace(0, 1, 11)) < 0.35 * change


def hit_effect(odd, ref, change):
    """True when `odd` is `ref` shaken (moved a few pixels) and/or flashed (brighter, darker or tinted, over the whole
    frame or one band of it, like a card above a face): a hit effect, not a glitch. Tries every shift up to 3 px at
    64 px wide and fits a brightness change per channel in each quarter of the frame's height."""
    h, w, _ = odd.shape
    best = change
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            a = odd[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)]
            b = ref[max(0, -dy):h + min(0, -dy), max(0, -dx):w + min(0, -dx)]
            res, rows = 0.0, np.array_split(np.arange(a.shape[0]), 4)
            for r in rows:
                for c in range(3):
                    x, y = a[r, :, c].ravel(), b[r, :, c].ravel()
                    gain, off = np.polyfit(x, y, 1) if x.std() > 1 else (0.0, y.mean())
                    res += np.abs(gain * x + off - y).mean() / (3 * len(rows))
            best = min(best, res)
    return best < 0.45 * change


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--ranges", default="")
    ap.add_argument("--cut", type=float, default=14.0)
    args = ap.parse_args()

    vw, vh, fps = probe(args.video)
    h = max(2, round(W * vh / vw / 2) * 2)
    f = frames(args.video, W, h)
    n = len(f)
    if n < 3:
        sys.exit("too few frames")
    d = np.zeros(n)                                  # d[i]: change from frame i-1 to frame i
    d[1:] = np.abs(f[1:] - f[:-1]).mean(axis=(1, 2, 3))
    skip = np.full(n, 999.0)                         # skip[i]: frame i-1 against frame i+1
    skip[1:-1] = np.abs(f[2:] - f[:-2]).mean(axis=(1, 2, 3))
    skip2 = np.full(n, 999.0)                        # skip2[i]: frame i-1 against frame i+2
    skip2[1:-2] = np.abs(f[3:] - f[:-3]).mean(axis=(1, 2, 3))
    calm = d < args.cut / 2                          # frame i looks like frame i-1

    def steady(i):                                   # frame i continues a held or slow shot (fast motion is not one)
        return i <= 0 or i >= n or calm[i]

    cuts = [i for i in range(1, n) if d[i] >= args.cut and steady(i - 1)]
    ranges = parse_ranges(args.ranges)

    def shown(t):
        return not ranges or any(a - 0.1 <= t < b + 0.1 for a, b in ranges)

    issues = []
    for i in range(1, n - 1):
        t = i / fps
        if not shown(t) or d[i] < args.cut or not steady(i - 1):
            continue
        for k, back in ((1, skip), (2, skip2)):     # a k-frame shot: frames i..i+k-1, then a change back or on
            if i + k >= n or d[i + k] < args.cut or (k == 2 and not calm[i + 1]) or not steady(i + k + 1):
                continue
            span = f"frame {i}" if k == 1 else f"frames {i}-{i + 1}"
            if back[i] < 0.4 * min(d[i], d[i + k]):
                if not all(hit_effect(f[j], f[i - 1], d[i]) for j in range(i, i + k)):
                    issues.append((t, "flash", f"{span} ({t:.2f} s) unlike the frames either side, which match"))
            elif not all(fade_step(f[j], f[i - 1], f[i + k], back[i]) or hit_effect(f[j], f[i - 1], d[i])
                         or hit_effect(f[j], f[i + k], d[i + k]) for j in range(i, i + k)):
                issues.append((t, "blink", f"a {k}-frame shot at {t:.2f} s between two cuts"))
            break
    for a, b in ranges:
        for edge, name in ((a, "start"), (b, "end")):
            hold = f"hold its first frame from {a - 0.1:.2f}" if name == "start" else f"hold its last frame to {b + 0.1:.2f}"
            for c in cuts:
                off = c / fps - edge
                if abs(off) <= 2 / fps + 1e-6:
                    issues.append((c / fps, "edge", f"cut at {c / fps:.2f} s, {abs(off) * 1000:.0f} ms from the range "
                                   f"{name} {edge:.2f}: {hold}"))
    q = (f // 16).astype(np.int32)
    keys = q[..., 0] * 256 + q[..., 1] * 16 + q[..., 2]
    flat = np.array([np.bincount(k.ravel()).max() / k.size for k in keys])
    for s, e in spans(flat > 0.88, fps, 0.5):
        if shown((s + e) / 2):
            issues.append((s, "sparse", f"{s:.2f}-{e:.2f} s: one flat colour covers {flat[int(s * fps):int(e * fps)].mean():.0%} "
                           f"of the frame"))
    for s, e in spans(d < 0.25, fps, 1.2):
        if shown((s + e) / 2):
            issues.append((s, "still", f"{s:.2f}-{e:.2f} s: nothing moves for {e - s:.1f} s"))

    if not issues:
        print("clean")
        return
    for t, kind, msg in sorted(issues):
        print(f"{kind:6} {msg}")


if __name__ == "__main__":
    main()
