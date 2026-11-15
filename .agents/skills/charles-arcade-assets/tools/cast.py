#!/usr/bin/env python3
"""Make a recurring character for a video, or give one more poses. Run with the repo venv (.venv/bin/python).

  cast.py new  <castdir> --desc "<the character>" [--type humanoid|creature|object] [--like <castdir>]
                         [--photo face.jpg] [--face right|left] [--sets base,act] [--screen magenta|green]
  cast.py add  <castdir> --sets act[,fight]
  cast.py pose <castdir> --name <pose> --desc "<what it does, holds or wears>"
  cast.py measure <castdir> [<castdir> ...] [--no-refit]

new   draws a reference sprite and keys it, and at once writes cast.json with an idle pose cut from the
      reference, so `pose` and `add` work whatever happens next. Then it draws one sprite sheet per pose set
      from the reference, keys and slices the sheets and puts every pose at one body size on one canvas (feet
      aligned), so poses swap in HTML without jumping. A sheet that will not slice (two or more poses missing,
      an extra pose, poses out of their row, a ghost copy or glow around a pose) is drawn once more; a set that
      fails again is left out and named at the end with a `pose` command for each missing pose (exit status
      1), and the sets that worked go in. A sheet one pose short is used, and the missing pose named.
      Writes ref_raw.png (the reference to pass to the image model later), ref.png, poses/*.png, cast.json,
      review.png.
add   draws more pose sets for an existing character and fits them to its canvas (cast/claude, cast/gpt).
pose  draws one pose from the reference and fits it: any pose a set did not give, or that a beat needs.
measure  (no fal calls, about a second a pose) finds every pose's anchors and writes them into cast.json, with
      anchors.png to check them: "anchors" per pose (canvas px) feet (the point on the ground between the feet),
      head (the top of the head), face (its centre), hand_r / hand_l (the hands on the image's right and left),
      head_w (the head's width), scale (its head against the reference pose's) and stands (its standing height
      against the reference's); "height" (the reference pose's standing height, head top to feet), "box" (its
      pixels) and "feet_w". cast.js places a character by these. A pose made by `pose` whose whole body came out
      another size (an older cast.py shrank poses holding a big prop to fit the canvas) is fitted again from its cut
      in extra/ at the reference's size, the canvas growing; --no-refit only measures. new, add and pose measure
      on their own; run measure on a cast made before, or after editing poses by hand.

--type sets the default pose sets (--sets overrides them):
  humanoid  base, act   has legs and arms: a person, a robot, a mascot (the default)
  creature  creature    no walking, no weapons: a blob, a slime, a ghost, a worm
  object    object      a thing that acts: a coin, a trophy, a page, an app icon
Pose sets (one 21:9 row, except creature, a 3:2 grid of two rows of three, and object, a square two by two):
  base      idle, walk_a, walk_b, jump, cheer, sad
  act       point, think, shock, talk
  fight     fight_ready, fight_attack, fight_hurt, fight_victory (a sword and shield)
  creature  idle, cheer, taunt, hurt, ko, sad
  object    idle, bounce, squash, shine
A creature or an object is sized as a whole (hue "all"); a humanoid by its body colour. Single poses of a
creature or an object keep the reference's scale (a squash stays flat); a humanoid's are matched to the reference
pose's head (found by template matching, so a mallet held overhead or a sack never counts as body; when the head
and the standing height disagree, its body colour decides). Every pose goes on the shared canvas by its feet (the
feet on the canvas's bottom centre), and a pose that does not fit grows the canvas for every pose (padding, never
shrinking a body), so poses swap at one body size; cast.json's canvas says the size.
--like keeps another character's design and changes what --desc says (a recolour, an outfit, a crown).
--photo turns the person in a photo into the character (a pixel version of the speaker).
Each image costs about $0.15: new with base + act is $0.45, a creature or an object $0.30. Calls are cached by
fal.py, so re-running is free.
Characters must not use the screen colour: --screen green for pink or purple ones. cast.json keeps the screen,
the type and the note, so add and pose reuse them unless told otherwise.
--note goes into every prompt; use it for what the model keeps changing (claude's act set used
"Its face is only two small black square eyes and it never has a mouth; show feeling with its eyes and body.").
"""
import argparse, json, subprocess, sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sprites  # noqa: E402

SCREEN = {"magenta": "magenta #FF00FF", "green": "green #00FF00"}
STYLE = ("Crisp 16-bit pixel art sprite, clean hard pixel edges, no anti-aliasing blur, limited flat palette, "
         "a 1-2 pixel dark outline, flat lighting with one small highlight. Centered single character, full body, "
         "on a perfectly flat solid {screen} background. No floor, no ground line, no shadow, no text, no border.")
OBJECT = ("Crisp 16-bit pixel art sprite, clean hard pixel edges, no anti-aliasing blur, limited flat palette, "
          "a 1-2 pixel dark outline, flat lighting with one small highlight. A single {desc}, centered, whole and "
          "uncropped, on a perfectly flat solid {screen} background. No floor, no ground line, no shadow, no text, "
          "no border. Simple, iconic, readable at small sizes. Front view.")
KEEP = ("Keep the exact character design from the reference image: same shape, proportions, colors, face, limbs "
        "and pixel art style.")
SHEET = (KEEP + " Draw a sprite sheet: the same character in one horizontal row, evenly spaced with wide empty gaps "
         "between poses, every pose at the same size and scale with feet on the same baseline. Perfectly flat solid "
         "{screen} background. No floor, no ground line, no shadow, no text, no numbers, no labels, no border. ")
# A creature or an object is often as wide as it is tall: six of them in one 21:9 row leave most of the frame
# empty, and the model filled it with a second copy of every pose (ghosts, doubles, a second row) in each of
# four tries. A grid of square-ish cells (two rows) gives each pose the room its shape needs.
SHEET_GRID = ("Keep the exact design from the reference image: same shape, proportions, colors, face and pixel art "
              "style. Draw a sprite sheet of exactly {count} figures of the same {thing} in a grid of {grid}, each "
              "figure centred in its own cell with wide empty gaps between them, every pose at the same scale as the "
              "reference, the figures in each row resting on the same baseline. Draw each pose once, sharp and fully "
              "opaque: no ghost copies, no doubles, no afterimages, no motion trails, no speed lines. Perfectly flat "
              "solid {screen} background. No floor, no ground line, no shadow, no text, no numbers, no labels, no "
              "border, no grid lines. ")
ONCE = " Draw it once: no ghost copy, no afterimage, no motion trail."

# What each pose is, for the sheets of the newer sets and for the `pose` commands printed when a pose is missing.
POSE = {
    "idle": "standing at rest", "walk_a": "walking, mid-stride with one leg stepping forward",
    "walk_b": "walking, mid-stride with the other leg stepping forward", "jump": "jumping up with legs tucked under",
    "cheer": "cheering with both arms raised and a happy face", "sad": "sad, slumped and drooping with a sad face",
    "point": "pointing up and to the right with one arm, confident",
    "think": "thinking, one arm raised to its chin, looking up", "shock": "shocked, leaning back with wide eyes",
    "talk": "talking, one arm out in an explaining gesture",
    "fight_ready": "in a ready stance, a small silver pixel sword raised in one hand and a small round wooden "
                   "shield with a white cross in the other",
    "fight_attack": "lunging forward to the right, swinging a small silver pixel sword down, a small round wooden "
                    "shield with a white cross in the other hand",
    "fight_hurt": "hurt, knocked backward with squeezed X-shaped eyes, holding a small silver sword and a round "
                  "wooden shield", "fight_victory": "victorious, a small silver sword held high overhead, a happy face",
}
CREATURE = {
    "idle": "resting in its usual shape, calm and at ease",
    "cheer": "cheering, bouncing with joy, a big happy open-mouthed smile",
    "taunt": "taunting, leaning toward the right with a smug, mocking grin",
    "hurt": "hurt, recoiling backward and squashed a little, with squeezed X-shaped eyes",
    "ko": "knocked out, collapsed flat and limp on the ground with X-shaped eyes",
    "sad": "sad, sagging and drooping with a sad face",
}
THING = {
    "idle": "upright and at rest",
    "bounce": "bouncing, stretched taller and thinner as if springing up, tilted a little to the right",
    "squash": "squashed, pressed flat and wider as if it just landed",
    "shine": "shining, with brighter highlights and two or three small sparkle glints drawn on it",
}


def grid(descs, count, view):
    return f"{count} poses, {view}, left to right, top row first: " + "; ".join(
        f"{i + 1} {d}" for i, d in enumerate(descs.values())) + "."


# set: (pose names, sheet prompt template with {screen}, what the poses are, sheet aspect, rows of poses)
SETS = {
    "base": (["idle", "walk_a", "walk_b", "jump", "cheer", "sad"], SHEET,
             "Six poses, front view, left to right: 1 idle standing; 2 walking, mid-stride with one leg stepping "
             "forward; 3 walking, mid-stride with the other leg stepping forward; 4 jumping up with legs tucked "
             "under; 5 cheering with both arms raised and a happy face; 6 sad, slumped and drooping with a sad face.",
             "21:9", 1),
    "act": (["point", "think", "shock", "talk"], SHEET,
            "Four poses, turned three-quarters to face right, its face drawn exactly as in the reference (add no "
            "mouth, eyebrows or features it does not have), left to right: 1 pointing up and to the right with one "
            "arm, confident; 2 thinking, one arm raised to its chin, looking up; 3 shocked, leaning back with wide "
            "eyes; 4 talking, one arm out in an explaining gesture.", "21:9", 1),
    "fight": (["fight_ready", "fight_attack", "fight_hurt", "fight_victory"], SHEET,
              "Four poses, turned three-quarters to face right. It holds a small silver pixel sword in one hand and a "
              "small round wooden shield with a white cross in the other. Left to right: 1 ready stance with the "
              "sword raised; 2 attacking, lunging forward to the right with the sword swinging down; 3 hurt, knocked "
              "backward with squeezed X-shaped eyes; 4 victory, sword held high overhead with a happy face.",
              "21:9", 1),
    "creature": (list(CREATURE), SHEET_GRID.replace("{thing}", "creature").replace("{count}", "six")
                 .replace("{grid}", "two rows of three"),
                 grid(CREATURE, "Six", "front view") + " It keeps its own body and size in every pose: no legs, "
                 "arms, hands, weapons or props it does not have in the reference, and it never walks; it acts by "
                 "leaning, squashing and sagging.", "3:2", 2),
    "object": (list(THING), SHEET_GRID.replace("{thing}", "object").replace("{count}", "four")
               .replace("{grid}", "two rows of two"),
               grid(THING, "Four", "front view") + " It stays the same object in every pose: add no face, arms or "
               "legs it does not have in the reference.", "1:1", 2),
}
TYPES = {"humanoid": "base,act", "creature": "creature", "object": "object"}
REF_BODY = 400   # body height of the idle cut from the reference while no pose set has given the cast its size


def fal_image(prompt, out, refs=(), aspect="1:1", force=False):
    """Draw an image with fal.py; True when it was drawn now, False when fal.py had it cached."""
    cmd = [sys.executable, str(HERE / "fal.py"), "image", "--prompt", prompt, "--aspect", aspect, "--res", "2K",
           "--out", str(out)]
    for r in refs:
        cmd += ["--ref", str(r)]
    if force:
        cmd.append("--force")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not Path(out).exists():
        sys.exit(f"fal.py failed for {out}:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    return "cached:" not in r.stdout


def keyed(src, out, screen):
    """Key, clean and trim an image; warn when it fades softly into the screen (a ghost copy or a glow)."""
    raw = sprites.load_rgba(src)
    a = sprites.clean(sprites.key(raw, screen))[0]
    sprites.save(sprites.trim(a), out)
    if sprites.fades(raw, screen).sum() > sprites.FADE * max(1, (a[..., 3] > 0).sum()):
        print(f"warning: {Path(src).name} fades softly into the screen colour (a ghost copy or a glow?): open "
              f"{Path(out).name}; to draw it again, delete {Path(src).name} and run the command again")


def dominant_hue(path):
    """The 30-degree hue band holding most of the body's saturated pixels, or 'all' when no colour dominates."""
    a = sprites.load_rgba(path)
    h, s, v = sprites.hsv(a)
    opaque = int((a[..., 3] > 0).sum())
    m = (a[..., 3] > 0) & (s > 0.35) & (v > 0.3)
    hist = np.bincount(h[m].astype(int) % 360, minlength=360)
    win = np.convolve(np.concatenate([hist, hist[:30]]), np.ones(31, int), "valid")[:360]
    if win.max() < 0.2 * opaque:
        return "all"
    lo = int(win.argmax())
    return f"{lo}-{(lo + 30) % 360}"


def load_cast(castdir):
    return json.loads((castdir / "cast.json").read_text())


def save_cast(castdir, cast):
    (castdir / "cast.json").write_text(json.dumps(cast, indent=1))


def body(im, hue_text):
    return sprites.body_height(np.array(im).astype(np.float32), sprites.parse_hue(hue_text))


def start_cast(castdir, hue, screen, kind, note):
    """cast.json with one pose, idle, cut from the keyed reference at REF_BODY px of body on a roomy canvas, so
    `pose` and `add` have a character to fit to before (or without) any pose set."""
    ref = sprites.trim_img(Image.open(castdir / "ref.png").convert("RGBA"))
    f = REF_BODY / body(ref, hue)
    ref = ref.resize((max(1, round(ref.width * f)), max(1, round(ref.height * f))), Image.Resampling.LANCZOS)
    W, H = 2 * round(ref.width * 0.8), 2 * round(ref.height * 0.68)  # room for raised arms, a lunge, a puddle
    canvas = Image.new("RGBA", (W, H))
    canvas.alpha_composite(ref, ((W - ref.width) // 2, H - ref.height - 2))
    (castdir / "poses").mkdir(exist_ok=True)
    canvas.save(castdir / "poses" / "idle.png")
    save_cast(castdir, {"canvas": [W, H], "body_px": REF_BODY, "hue": hue, "poses": ["idle"], "type": kind,
                        "screen": screen, "note": note})
    print(f"cast.json: idle from the reference, canvas {W}x{H}; `pose` and `add` work from here")


def ensure_cast(castdir, screen):
    """Make cast.json from the reference when a character has none yet (made by hand, or by an older run)."""
    if (castdir / "cast.json").is_file():
        return
    if not (castdir / "ref.png").is_file():
        if not (castdir / "ref_raw.png").is_file():
            sys.exit(f"{castdir} has no cast.json and no reference: make it with `cast.py new`")
        keyed(castdir / "ref_raw.png", castdir / "ref.png", screen)
    start_cast(castdir, dominant_hue(castdir / "ref.png"), screen, "humanoid", "")


def draw_set(castdir, name, screen, note=""):
    """One sprite sheet for a pose set, sliced into <castdir>/<name>/; a fresh sheet once if slicing fails.
    Returns the pose names it got (one may be missing, see sprites.missing_pose), or None when both failed."""
    names, template, poses, aspect, rows = SETS[name]
    sheet = castdir / f"sheet_{name}.png"
    for attempt in range(2):
        fal_image(template.format(screen=SCREEN[screen]) + poses + (" " + note if note else ""), sheet,
                  [castdir / "ref_raw.png"], aspect, force=attempt > 0)
        try:
            return sprites.cmd_slice(SimpleNamespace(sheet=str(sheet), outdir=str(castdir / name),
                                                     names=",".join(names), screen=screen, rows=rows, no_fades=True))
        except SystemExit as e:
            print(f"{name}: {e}" + ("; drawing the sheet again" if attempt == 0 else ""))
    return None


def scale_of(castdir, cast, img):
    """How much to scale a single pose drawn from the reference. A humanoid keeps its height across poses, so
    its body is matched to the cast's; a creature or an object squashes and stretches, so it is drawn at the
    reference's scale and scaled as the reference was."""
    if cast.get("type", "humanoid") == "humanoid":
        return cast["body_px"] / body(img, cast["hue"])
    return cast["body_px"] / body(sprites.trim_img(Image.open(castdir / "ref.png").convert("RGBA")), cast["hue"])


# ---------- measuring poses: where the feet, head, face and hands are, and how big the body is ----------
# cast.json "anchors" give, per pose and in canvas px, the feet (the point on the ground between them), the head (the
# top of the head), the face (its centre), the hands (hand_r on the image's right, hand_l on its left) and head_w (the
# head's width, for a hat), so cast.js places a character by its feet, swaps poses without a jump and hangs props and
# hats on it. "height" is the reference pose's standing height (head top to feet) that a body height is measured in.
# The yardstick is the reference pose's head (idle): it is found in every pose by template matching (colour and
# silhouette, scale 0.5-1.75, mirrored too, the character standing upright), so a raised mallet, a sack or a sword is
# never counted as body. A pose is "sure" when the matched head and the pose's own feet agree on how tall it stands
# (a crouch, a jump or a pose drawn with other proportions is not); only sure poses are rescaled.
WORK_H = 180          # the reference pose stands this tall (px) while matching


def rgba(im):
    """float RGBA (0-1, straight alpha) of a PIL image or a path"""
    if not isinstance(im, Image.Image):
        im = Image.open(im)
    return np.asarray(im.convert("RGBA")).astype(np.float32) / 255.0


def rescale(a, f):
    """float RGBA resized by f with premultiplied bilinear resampling (no dark fringe); straight alpha out"""
    h, w = a.shape[:2]
    W, H = max(1, round(w * f)), max(1, round(h * f))
    pm = a.copy()
    pm[..., :3] *= pm[..., 3:4]
    out = np.stack([np.asarray(Image.fromarray(np.ascontiguousarray(pm[..., c])).resize((W, H), Image.Resampling.BILINEAR))
                    for c in range(4)], -1)
    al = out[..., 3:4]
    out[..., :3] = np.where(al > 1e-4, out[..., :3] / np.maximum(al, 1e-4), 0)
    return out


def feats(a):
    """what matching compares: colour (premultiplied) and the silhouette, weighted up"""
    return np.concatenate([a[..., :3] * a[..., 3:4], a[..., 3:4] * 1.5], -1)


class Matcher:
    """Squared-difference template matching over one image by FFT; a template may hang off the image by its size."""

    def __init__(self, a, hm, wm):
        self.hm, self.wm = hm, wm
        self.I = np.pad(feats(a), ((hm, hm), (wm, wm), (0, 0)))
        self.shape = (self.I.shape[0] + hm, self.I.shape[1] + wm)
        self.F = [np.fft.rfft2(self.I[..., c], self.shape) for c in range(4)]
        self.S = np.pad((self.I ** 2).sum(-1), ((1, 0), (1, 0))).cumsum(0).cumsum(1)

    def errors(self, T):
        """mean squared difference for every top-left position of T: errors[y + hm, x + wm]"""
        Ht, Wt = T.shape[:2]
        acc = 0
        for c in range(4):
            acc = acc + self.F[c] * np.conj(np.fft.rfft2(T[..., c], self.shape))
        H, W = self.I.shape[0] - Ht + 1, self.I.shape[1] - Wt + 1
        cc = np.fft.irfft2(acc, self.shape)[:H, :W]
        S = self.S
        i2 = S[Ht:Ht + H, Wt:Wt + W] - S[:H, Wt:Wt + W] - S[Ht:Ht + H, :W] + S[:H, :W]
        return ((T ** 2).sum() + i2 - 2 * cc) / (Ht * Wt)


def run_at(row, cx, reach):
    """(first, last) column of the run of opaque pixels through column cx, or the nearest run within reach px"""
    xs = np.where(row)[0]
    if not len(xs):
        return None
    if not row[cx]:
        near = xs[np.argmin(np.abs(xs - cx))]
        if abs(near - cx) > reach:
            return None
        cx = int(near)
    a = cx
    while a > 0 and row[a - 1]:
        a -= 1
    b = cx
    while b < len(row) - 1 and row[b + 1]:
        b += 1
    return a, b


def feet_of(al, x=None, span=None):
    """The feet of a pose (alpha mask): [x, y], the middle of the lowest rows' pixels near x (or, without x, of the
    biggest group of them, plus a second foot beside it) and the ground line under them."""
    ys, xs = np.where(al)
    H = ys.max() - ys.min() + 1
    if x is not None:
        half = span / 2
        c0, c1 = int(max(0, x - half)), int(min(al.shape[1] - 1, x + half))
        sub = al[:, c0:c1 + 1]
        if sub.any():
            rows = np.where(sub.any(1))[0]
            yb = rows.max()
            cols = np.where(sub[max(0, yb - max(2, int(0.04 * H))):yb + 1].any(0))[0] + c0
            return [float((cols.min() + cols.max() + 1) / 2), float(yb + 1)]
    yb = ys.max()
    cols = np.where(al[max(0, yb - max(2, int(0.04 * H))):yb + 1].any(0))[0]
    groups, start = [], cols[0]
    for i in range(1, len(cols) + 1):
        if i == len(cols) or cols[i] - cols[i - 1] > 0.12 * H:
            groups.append((start, cols[i - 1]))
            if i < len(cols):
                start = cols[i]
    big = max(groups, key=lambda g: g[1] - g[0])
    keep = [g for g in groups if g is big or min(abs(g[0] - big[1]), abs(big[0] - g[1])) < 0.25 * H]
    return [float((min(g[0] for g in keep) + max(g[1] for g in keep) + 1) / 2), float(yb + 1)]


SKIN = 0.115        # colour distance (0-1 RGB) within which a pixel counts as one of the face's skin tones


def tone_dist(a, tones):
    return np.min([np.sqrt(((a[..., :3] - t) ** 2).sum(-1)) for t in tones], 0)


class Ref:
    """The reference pose (idle): where its feet, head, face and hands are, its head as a template, its skin."""

    def __init__(self, a, kind="humanoid"):
        al = a[..., 3] > 0.5
        ys, xs = np.where(al)
        x0, y0, y1 = xs.min(), ys.min(), ys.max()
        self.kind, self.a, self.al, self.y0 = kind, a, al, y0
        self.stand = Hs = int(y1 - y0 + 1)
        fb = al[max(0, y1 - max(2, int(0.04 * Hs))):y1 + 1]
        fc = np.where(fb.any(0))[0]
        self.feet = [float((fc.min() + fc.max() + 1) / 2), float(y1 + 1)]   # the reference holds nothing on the floor
        self.feet_span = float(fc.max() - fc.min() + 1)
        # the head: the run of pixels through the head's middle column, row by row, down to where it narrows (the neck)
        tc = np.where(al[y0:y0 + max(2, int(0.08 * Hs))].any(0))[0]
        cx = int(round((tc.min() + tc.max()) / 2))
        runs = [run_at(al[y], cx, 0.08 * Hs) for y in range(y0, min(al.shape[0], y0 + int(0.62 * Hs)))]
        widths = [r[1] - r[0] + 1 if r else 0 for r in runs]
        top = widths[:max(1, int(0.45 * Hs))]
        hw, widest = max(top), int(np.argmax(top))
        neck = next((y0 + i for i in range(max(widest, int(0.15 * Hs)), len(runs)) if widths[i] < 0.72 * hw), None)
        self.neck = neck if neck is not None else y0 + int(0.5 * Hs)
        rs = [r for r in runs[:self.neck - y0] if r] or [(cx, cx)]
        self.hx0, self.hx1 = min(r[0] for r in rs), max(r[1] for r in rs)
        self.head_w = float(self.hx1 - self.hx0 + 1)
        self.hcx = (self.hx0 + self.hx1 + 1) / 2
        self.head = [self.hcx, float(y0)]
        self.face = [self.hcx, y0 + 0.66 * (self.neck - y0)]
        # the head as a template, at the working scale
        self.g = g = WORK_H / Hs
        small = rescale(a, g)
        m = max(2, int(0.02 * WORK_H))
        self.tx0, self.ty0 = max(0, int(self.hx0 * g) - m), max(0, int(y0 * g) - m)
        self.tx1 = min(small.shape[1], int((self.hx1 + 1) * g) + m)
        self.ty1 = max(self.ty0 + 4, int(min(self.neck, y0 + 0.5 * Hs) * g))
        self.T = small[self.ty0:self.ty1, self.tx0:self.tx1]
        # skin: the face's main colours, when they are skin-like and not the colour of the whole character
        self.skin = None
        fx, fy = int(self.face[0]), int(self.face[1])
        win = a[max(0, fy - int(0.06 * Hs)):fy + int(0.06 * Hs), max(0, int(fx - 0.2 * hw)):int(fx + 0.2 * hw)]
        px = win[win[..., 3] > 0.5][:, :3]
        if len(px) > 20:
            h, s, v = sprites.hsv(px[None] * 255.0)
            h, s, v = h[0], s[0], v[0]
            keep = (v > 0.35) & (s > 0.1)
            if keep.sum() > 20:
                hb = (h[keep] // 10).astype(int) % 36
                sel = hb == np.bincount(hb, minlength=36).argmax()
                hh, ss, vv = np.median(h[keep][sel]), np.median(s[keep][sel]), np.median(v[keep][sel])
                if (hh <= 50 or hh >= 345) and 0.12 <= ss <= 0.8 and vv > 0.3 and sel.sum() > 0.3 * keep.sum():
                    c = px[keep][sel]
                    lum = c.mean(1)
                    hi, lo = c[lum > np.median(lum)], c[lum <= np.median(lum)]
                    tones = [t for t in (hi.mean(0) if len(hi) else None, lo.mean(0) if len(lo) else None) if t is not None]
                    share = ((tone_dist(a, tones) < SKIN) & al).sum() / max(1, al.sum())
                    if share < 0.45:
                        self.skin = tones
        # the face's own skin pixels (a hand in front of the hair or an ear is still a hand)
        self.face_px = np.zeros((0, 2))
        if self.skin is not None:
            fm = np.zeros_like(al)
            fm[y0:self.neck + 1, self.hx0:self.hx1 + 1] = True
            fy_, fx_ = np.where(fm & al & (tone_dist(a, self.skin) < SKIN))
            self.face_px = np.stack([fx_, fy_], 1)[::3].astype(np.float32)
        self.match = {"scale": 1.0, "x": self.tx0 / g, "y": self.ty0 / g, "mirror": False, "err": 0.0}
        self.hands = find_hands(self, a, al, self.match)

    def to_pose(self, M, p):
        """a point of the reference pose, in a pose's canvas px, through a head match M"""
        s, g = M["scale"], self.g
        x = (self.tx1 / g - p[0]) if M["mirror"] else (p[0] - self.tx0 / g)
        return [M["x"] + x * s, M["y"] + (p[1] - self.ty0 / g) * s]


def match_head(ref, a, upright=0.16, lo=0.5, hi=1.75):
    """Find the reference's head in a pose (float RGBA at the reference's canvas scale): {scale, x, y, mirror, err},
    x, y the template's top-left in the pose's px. upright: how far (share of the standing height) the head may sit
    from where an upright character of that scale standing on the pose's lowest pixel would have it."""
    g, T = ref.g, ref.T
    small = rescale(a, g)
    al = small[..., 3] > 0.5
    ys = np.where(al.any(1))[0]
    yb = ys.max() + 1
    Ht, Wt = T.shape[:2]
    hm, wm = int(Ht * hi * 1.06) + 2, int(Wt * hi * 1.06) + 2
    mt = Matcher(small, hm, wm)
    head_dy = (ref.feet[1] - ref.y0) * g          # the reference's head top above its feet, working px
    top_in_t = ref.y0 * g - ref.ty0               # the head top's row inside the template

    def best(TT, scales):
        out = None
        for s in scales:
            Ts = rescale(TT, s) if abs(s - 1) > 1e-3 else TT
            E = mt.errors(feats(Ts))
            if upright is not None:
                want = yb - head_dy * s - top_in_t * s      # where the template's top should be
                rows = np.arange(E.shape[0]) - hm
                E = np.where((np.abs(rows - want) <= upright * WORK_H * s)[:, None], E, np.inf)
            k = np.unravel_index(np.argmin(E), E.shape)
            if np.isfinite(E[k]) and (out is None or E[k] < out[0]):
                out = (float(E[k]), float(s), k[0] - hm, k[1] - wm)
        return out

    coarse = best(T, np.geomspace(lo, hi, 26))
    mirror = False
    if coarse is None:
        return None
    if coarse[0] > 0.01:
        cm = best(T[:, ::-1], np.geomspace(lo, hi, 26))
        if cm and cm[0] < 0.8 * coarse[0]:
            coarse, mirror = cm, True
    s0 = coarse[1]
    fine = best(T[:, ::-1] if mirror else T, np.linspace(s0 * 0.95, s0 * 1.05, 11)) or coarse
    e, s, y, x = fine
    return {"scale": s, "x": x / g, "y": y / g, "mirror": mirror, "err": e}


def find_hands(ref, a, al, M):
    """The hands of a pose: {"l": [x, y] or None, "r": ...} (image left and right). With skin-coloured hands: the two
    biggest skin-coloured parts that are not the head, the neck or specks. Without: the outermost points of the
    silhouette between the head and the feet."""
    s = M["scale"]
    Hs = ref.stand * s
    head_top = ref.to_pose(M, ref.head)[1]
    neck = ref.to_pose(M, [ref.hcx, ref.neck])[1]
    hcx = ref.to_pose(M, [ref.hcx, ref.y0])[0]
    hw = ref.head_w * s
    fc = ref.to_pose(M, ref.face)
    fh = (ref.neck - ref.y0) * s
    found = []
    if ref.skin is not None:
        sm = al & (tone_dist(a, ref.skin) < SKIN)
        # the face's skin, mapped from the reference and grown a little, is not a hand
        hm = np.zeros_like(al)
        if len(ref.face_px):
            q = np.array([ref.to_pose(M, p) for p in ref.face_px])
            ok = (q[:, 0] >= 0) & (q[:, 0] < al.shape[1]) & (q[:, 1] >= 0) & (q[:, 1] < al.shape[0])
            hm[q[ok, 1].astype(int), q[ok, 0].astype(int)] = True
            hm = sprites.grow(hm, max(3, int(0.012 * Hs)))
        lab, comps = sprites.parts(sm)
        for c in comps:
            x0, y0, x1, y1 = c["box"]
            m = lab[y0:y1, x0:x1] == c["label"]
            if (hm[y0:y1, x0:x1] & m).sum() > 0.5 * m.sum():
                continue
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if ((cx - fc[0]) / (0.42 * hw)) ** 2 + ((cy - fc[1]) / (0.55 * fh)) ** 2 < 1:
                continue                                             # inside the face: a cheek split off by a moustache
            if abs(cx - hcx) < 0.2 * hw and neck - 0.05 * Hs <= cy <= neck + 0.1 * Hs and c["area"] < 0.004 * Hs ** 2:
                continue                                             # the neck, a collar
            if c["area"] < 0.0005 * Hs ** 2:
                continue
            yy, xx = np.where(lab[y0:y1, x0:x1] == c["label"])
            found.append([float(xx.mean() + x0), float(yy.mean() + y0), c["area"]])
        found.sort(key=lambda h: -h[2])
        if found:
            found = [h for h in found if h[2] >= 0.2 * found[0][2]][:2]
    else:
        feet = feet_of(al)
        ya, yb = int(head_top + 0.25 * Hs), int(feet[1] - 0.12 * Hs)
        sub = al[max(0, ya):max(ya + 1, yb)]
        cols = np.where(sub.any(0))[0]
        if len(cols):
            for xc, inset in ((cols.min(), 1), (cols.max(), -1)):
                yy = np.where(sub[:, xc])[0]
                found.append([float(xc + inset * 0.01 * Hs), float(max(0, ya) + yy.mean()), 0])
    hands = {"l": None, "r": None}
    if len(found) == 2:
        l, r = sorted(found, key=lambda h: h[0])
        hands = {"l": l[:2], "r": r[:2]}
    elif len(found) == 1:
        h = found[0][:2]
        hands["r" if h[0] >= hcx else "l"] = h
    return hands


def silhouette_top(al, x, half):
    """the topmost opaque row within half px of column x (the top of the head, whatever a hand holds aside)"""
    sub = al[:, int(max(0, x - half)):int(min(al.shape[1], x + half + 1))]
    rows = np.where(sub.any(1))[0]
    return float(rows.min()) if len(rows) else None


def measure_pose(ref, a, upright=0.16, lo=0.5, hi=1.75, M=None):
    """Anchors of one pose (float RGBA, in its own px), "scale" (its head against the reference's) and "stands" (its
    standing height, head top to feet, against the reference's). M: a head match already made (the reference pose
    itself passes ref.match)."""
    al = a[..., 3] > 0.5
    M = M or match_head(ref, a, upright, lo, hi)
    ys = np.where(al.any(1))[0]

    def aligned():
        # no head match to trust: the reference as it stands, its feet on this pose's feet
        f = feet_of(al)
        return {"scale": 1.0, "x": ref.tx0 / ref.g + f[0] - ref.feet[0], "y": ref.ty0 / ref.g + f[1] - ref.feet[1],
                "mirror": False, "err": 9.0}

    M = M or aligned()
    s = M["scale"]
    want = ref.to_pose(M, ref.feet)
    feet = feet_of(al, want[0], ref.feet_span * s + 0.2 * ref.stand * s)
    top = silhouette_top(al, ref.to_pose(M, [ref.hcx, ref.y0])[0], 0.25 * ref.head_w * s)
    stands = (feet[1] - (top if top is not None else ys.min())) / ref.stand
    if (s < 0.6 or s > 1.6) and 0.8 < stands < 1.25:
        M = aligned()                            # an implausible match (a laughing face tipped back): fall back
        s = 1.0
        feet = feet_of(al, ref.to_pose(M, ref.feet)[0], ref.feet_span + 0.2 * ref.stand)
    head = ref.to_pose(M, ref.head)
    face = ref.to_pose(M, ref.face)
    hands = find_hands(ref, a, al, M)
    # a hand not found: the other one mirrored about the head's middle, or the reference's hand carried over
    mid = ref.to_pose(M, [ref.hcx, ref.y0])[0]
    for side, other in (("l", "r"), ("r", "l")):
        if hands[side] is None:
            if hands[other] is not None:
                hands[side] = [2 * mid - hands[other][0], hands[other][1]]
            elif ref.hands.get(side) is not None:
                hands[side] = ref.to_pose(M, ref.hands[side])
            else:
                hands[side] = [feet[0] + (-1 if side == "l" else 1) * 0.3 * ref.head_w * s, (head[1] + feet[1]) / 2]
    r1 = lambda p: [round(float(p[0]), 1), round(float(p[1]), 1)]
    out = {"feet": r1(feet), "head": r1(head), "face": r1(face), "hand_r": r1(hands["r"]), "hand_l": r1(hands["l"]),
           "head_w": round(float(ref.head_w * s), 1), "scale": round(float(s), 3), "stands": round(float(stands), 3),
           "match": round(float(min(M["err"], 9.0)), 3)}
    if M["mirror"]:
        out["mirror"] = True
    if abs(stands - s) > 0.06 * s:
        out["unsure"] = True                     # the head and the feet disagree: a crouch, other proportions, a miss
    return out


def resized(an, tol=0.15):
    """The factor a pose's whole body is off by, when its head and its standing height are both off the same way by
    more than tol (a pose scaled as a whole: shrunk to fit a mallet onto the canvas); None when it is the reference's
    size or only drawn another way (a head drawn a little bigger, a crouch: matching is not that exact)."""
    s, h = an["scale"], an.get("stands", an["scale"])
    if an.get("match", 0) > 0.3:
        return None                              # the head was not found cleanly (covered by arms, a scream, a turn)
    if abs(s - 1) > tol and abs(h - 1) > tol and (s - 1) * (h - 1) > 0 and abs(s - h) < 0.08 * s:
        return (s + h) / 2
    return None


def ref_pose(cast):
    return "idle" if "idle" in cast["poses"] else cast["poses"][0]


def grow_canvas(castdir, W2, H2):
    """Make the shared canvas W2 x H2 (never smaller): every pose is padded around its bottom centre, so feet stay on
    the bottom centre and nothing is scaled. Anchors move with the poses."""
    cast = load_cast(castdir)
    W, H = cast["canvas"]
    W2, H2 = max(W, W2), max(H, H2)
    W2 += (W2 - W) % 2
    if (W2, H2) == (W, H):
        return
    dx, dy = (W2 - W) // 2, H2 - H
    for p in cast["poses"]:
        f = castdir / "poses" / f"{p}.png"
        if f.is_file():
            im = Image.open(f).convert("RGBA")
            c = Image.new("RGBA", (W2, H2))
            c.alpha_composite(im, (dx, dy))
            c.save(f)
    for an in (cast.get("anchors") or {}).values():
        for k, v in an.items():
            if isinstance(v, list) and len(v) == 2:
                an[k] = [round(v[0] + dx, 1), round(v[1] + dy, 1)]
    cast["canvas"] = [W2, H2]
    save_cast(castdir, cast)
    print(f"canvas grown to {W2}x{H2} (poses padded, not shrunk)")


def place(castdir, im, name, feet_x):
    """Put a scaled, trimmed pose on the cast canvas with its feet (feet_x px from its left edge) on the canvas's
    bottom centre; when it does not fit, the canvas grows for every pose instead. Adds it to cast.json."""
    cast = load_cast(castdir)
    W, H = cast["canvas"]
    left = W / 2 - feet_x
    over = max(0.0, 4 - left, left + im.width - (W - 4))
    if over > 0 or im.height + 4 > H:
        grow_canvas(castdir, W + 2 * int(np.ceil(over)), max(H, im.height + 4))
        cast = load_cast(castdir)
        W, H = cast["canvas"]
        left = W / 2 - feet_x
    canvas = Image.new("RGBA", (W, H))
    canvas.alpha_composite(im, (int(round(left)), H - im.height - 2))
    (castdir / "poses").mkdir(exist_ok=True)
    canvas.save(castdir / "poses" / f"{name}.png")
    if name not in cast["poses"]:
        cast["poses"].append(name)
        save_cast(castdir, cast)


def fit_into(castdir, img, name, f=None):
    """Scale a keyed pose and put it on the cast canvas by its feet, growing the canvas (never shrinking the pose)
    when it does not fit. f: the scale; when None, a humanoid's head is matched to the reference pose's head (so a
    mallet held overhead or a sack on the back is not counted as body), and anything else is scaled by scale_of."""
    cast = load_cast(castdir)
    im = sprites.trim_img(img)
    rp = castdir / "poses" / f"{ref_pose(cast)}.png"
    ref = Ref(rgba(rp)) if cast.get("type", "humanoid") == "humanoid" and rp.is_file() else None
    if f is None and ref is not None:
        f0 = ref.stand / im.height                     # a first guess: as tall as the reference stands
        an = measure_pose(ref, rescale(rgba(im), f0), upright=0.6, lo=0.4, hi=2.2)
        if not an.get("unsure") or cast.get("hue", "all") == "all":
            f = f0 / an["scale"]                       # the head says how big it is (a body colour would count a prop)
            if an.get("unsure"):
                print(f"note: {name}: sized by its head, which did not quite agree with its standing height (a crouch, "
                      f"a hat, other proportions): check it on review.png")
        else:
            print(f"note: {name}: its head and its standing height disagree (a head drawn bigger, or not found); "
                  f"sized by its body colour instead: check it on review.png")
    f = f or scale_of(castdir, cast, im)
    im = im.resize((max(1, round(im.width * f)), max(1, round(im.height * f))), Image.Resampling.LANCZOS)
    a = rgba(im)
    fx = measure_pose(ref, a, upright=0.6)["feet"][0] if ref is not None else feet_of(a[..., 3] > 0.5)[0]
    place(castdir, im, name, fx)


def fit_set(castdir, s, only=None):
    """Fit a sliced set to the cast: one scale for the whole set, from its first pose, so a squash stays a squash."""
    meta = json.loads((castdir / s / "poses.json").read_text())
    names = [n for n in meta["poses"] if only is None or n in only]
    imgs = {n: Image.open(castdir / s / meta["poses"][n]["file"]).convert("RGBA") for n in names}
    cast = load_cast(castdir)
    first = sprites.trim_img(Image.open(castdir / s / meta["poses"][next(iter(meta["poses"]))]["file"]).convert("RGBA"))
    f = cast["body_px"] / body(first, cast["hue"])
    for n, im in imgs.items():
        fit_into(castdir, im, n, f)


def measure_cast(castdir, refit=True, center=False, quiet=False):
    """Measure every pose against the reference pose and write the anchors into cast.json (and anchors.png).
    refit: a pose made by `pose` (its cut in extra/) whose whole body came out another size (shrunk to fit a mallet
    onto the canvas, scaled by a prop) is fitted again from that cut at the reference's size, the canvas growing for
    it. A pose that is off the same way but has no cut gets "zoom" (cast.js scales it). center: every pose is moved so
    its feet sit on the canvas's bottom centre (for a new cast; older casts keep their pixels)."""
    cast = load_cast(castdir)
    kind = cast.get("type", "humanoid")
    upright = 0.16 if kind == "humanoid" else 0.6
    rp = ref_pose(cast)

    def measure_all():
        ref = Ref(rgba(castdir / "poses" / f"{rp}.png"), kind)
        out = {}
        for p in load_cast(castdir)["poses"]:
            f = castdir / "poses" / f"{p}.png"
            if f.is_file():
                out[p] = measure_pose(ref, ref.a, M=ref.match) if p == rp else measure_pose(ref, rgba(f), upright)
        out[rp]["scale"] = 1.0
        return out

    anchors = measure_all()
    refitted = []
    if refit and kind == "humanoid":
        for p, an in anchors.items():
            cut = castdir / "extra" / f"{p}.png"
            k = resized(an)
            if p != rp and k and cut.is_file():
                src = sprites.trim_img(Image.open(cut).convert("RGBA"))
                now = sprites.trim_img(Image.open(castdir / "poses" / f"{p}.png").convert("RGBA"))
                f_old = max(now.width / src.width, now.height / src.height)
                fit_into(castdir, src, p, f_old / k)
                refitted.append(f"{p} x{1 / k:.2f}")
        if refitted:
            anchors = measure_all()
    if center:
        cast = load_cast(castdir)
        W, H = cast["canvas"]
        shift, extra = {}, 0.0
        for p, an in anchors.items():
            d = W / 2 - an["feet"][0]
            box = Image.open(castdir / "poses" / f"{p}.png").getbbox()
            if abs(d) >= 1 and box:
                shift[p] = int(round(d))
                extra = max(extra, 4 - (box[0] + d), box[2] + d - (W - 4))
        if shift:
            if extra > 0:
                grow_canvas(castdir, W + 2 * int(np.ceil(extra)), H)
            for p, d in shift.items():
                f = castdir / "poses" / f"{p}.png"
                im = Image.open(f).convert("RGBA")
                c = Image.new("RGBA", im.size)
                c.alpha_composite(im, (d, 0)) if d >= 0 else c.alpha_composite(im.crop((-d, 0, im.width, im.height)), (0, 0))
                c.save(f)
            anchors = measure_all()
    in_sets = {n for v in SETS.values() for n in v[0]}
    for p, an in anchors.items():
        if p != rp and p not in in_sets and resized(an):
            an["zoom"] = round(1 / resized(an), 3)    # a lone pose still another size (no cut to refit): cast.js scales it
    cast = load_cast(castdir)
    ref = Ref(rgba(castdir / "poses" / f"{rp}.png"), kind)
    ys, xs = np.where(ref.al)
    cast["ref"] = rp
    cast["height"] = round(anchors[rp]["feet"][1] - anchors[rp]["head"][1], 1)
    cast["box"] = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]   # the reference pose's pixels
    cast["feet_w"] = round(ref.feet_span, 1)
    cast["anchors"] = anchors
    save_cast(castdir, cast)
    draw_anchors(castdir)
    if not quiet:
        print(f"{castdir}: anchors for {len(anchors)} poses (reference {rp}, standing {cast['height']:.0f} px on a "
              f"{cast['canvas'][0]}x{cast['canvas'][1]} canvas)" + (f"; refitted {', '.join(refitted)}" if refitted else ""))
        for p, an in anchors.items():
            if p == rp:
                continue
            note = (" zoomed by cast.js (no cut in extra/ to refit from)" if "zoom" in an else
                    " (drawn with other proportions, crouched or turned: anchors approximate)" if an.get("unsure") else "")
            print(f"  {p:14s} head x{an['scale']:.2f}{note}")
        print(f"Open {castdir / 'anchors.png'}: dots on the head top (yellow), face (orange), hands (pink right, "
              f"blue left) and feet (white) of every pose.")
    return anchors


def draw_anchors(castdir):
    """anchors.png: every pose on teal with its anchors as dots and its feet line"""
    from PIL import ImageDraw
    cast = load_cast(castdir)
    tiles = []
    for p in cast["poses"]:
        f = castdir / "poses" / f"{p}.png"
        an = cast["anchors"].get(p)
        if not f.is_file() or not an:
            continue
        im = Image.open(f).convert("RGBA")
        bg = Image.new("RGBA", im.size, (38, 128, 120, 255))
        bg.alpha_composite(im)
        d = ImageDraw.Draw(bg)
        r = max(5, int(0.011 * cast.get("height", im.height)))
        d.line([an["feet"][0], 0, an["feet"][0], im.height], fill=(255, 255, 255, 140), width=2)
        for k, col in (("head", (255, 230, 0)), ("face", (255, 140, 0)), ("hand_r", (255, 60, 200)),
                       ("hand_l", (60, 170, 255)), ("feet", (255, 255, 255))):
            x, y = an[k]
            d.ellipse([x - r, y - r, x + r, y + r], fill=col + (255,), outline=(0, 0, 0, 255), width=2)
        hw = an["head_w"] / 2
        d.line([an["head"][0] - hw, an["head"][1], an["head"][0] + hw, an["head"][1]], fill=(255, 230, 0, 255), width=3)
        tiles.append(bg)
    if not tiles:
        return
    hh = 340
    tiles = [t.resize((max(1, round(t.width * hh / t.height)), hh), Image.Resampling.LANCZOS) for t in tiles]
    sheet = Image.new("RGBA", (sum(t.width for t in tiles) + 10 * (len(tiles) + 1), hh + 20), (28, 28, 30, 255))
    x = 10
    for t in tiles:
        sheet.alpha_composite(t, (x, 10))
        x += t.width + 10
    sheet.save(castdir / "anchors.png")


def review(castdir):
    cast = load_cast(castdir)
    sprites.cmd_sheet(SimpleNamespace(out=str(castdir / "review.png"),
                                      inputs=[str(castdir / "poses" / f"{p}.png") for p in cast["poses"]]))
    spent = sum(json.loads(l).get("usd_est", 0) for f in castdir.rglob("costs.jsonl")
                for l in f.read_text().splitlines() if l)
    print(f"{castdir}: {len(cast['poses'])} poses ({', '.join(cast['poses'])}), canvas {cast['canvas'][0]}x"
          f"{cast['canvas'][1]}, hue {cast['hue']}; fal total for this character ${spent:.2f}. "
          f"Open review.png: every pose on-model, no holes, same size.")


def report(castdir, wanted, failed):
    """Say plainly which sets failed and which poses the cast lacks, with the `pose` command for each. Exit 1
    when a whole set failed; a set that came out one pose short is only noted."""
    have = set(load_cast(castdir)["poses"])
    lines = []
    for s in wanted:
        lost = [n for n in SETS[s][0] if n not in have]
        if s in failed:
            lines.append(f"FAILED {s}: sheet_{s}.png would not slice after two drawings (open it to see why)." +
                         (" The poses from its earlier sheet are kept." if not lost else ""))
        elif lost:
            lines.append(f"{s}: the sheet had no shape for {', '.join(lost)}.")
        if lost:
            lines.append(f"The cast works without {', '.join(lost)}; draw any a beat needs as a single pose:")
            descs = CREATURE if s == "creature" else THING if s == "object" else POSE
            lines += [f'  .venv/bin/python {HERE}/cast.py pose {castdir} --name {n} --desc "{descs[n]}"' for n in lost]
    if lines:
        print("\n".join(lines))
    if failed:
        sys.exit(1)


def cmd_new(a):
    castdir = Path(a.castdir)
    castdir.mkdir(parents=True, exist_ok=True)
    screen = a.screen or "magenta"
    sets = [s.strip() for s in (a.sets or TYPES[a.type]).split(",")]
    for s in sets:
        if s not in SETS:
            sys.exit(f"unknown pose set {s}; the sets are {', '.join(SETS)}")
    face = f"Three-quarter view facing {a.face}."
    if a.like:
        prompt = (f"{KEEP} Change only this: {a.desc}. Centered single character, full body, on a perfectly flat "
                  f"solid {SCREEN[screen]} background. No floor, no ground line, no shadow, no text, no border. {face}")
        refs = [Path(a.like) / "ref_raw.png"]
    elif a.photo:
        prompt = (f"{STYLE.format(screen=SCREEN[screen])} The character: a cute chibi pixel-art version of the person "
                  f"in the reference photo, keeping their hair style and colour, skin tone, face shape and clothing "
                  f"colours, with a big head and a small body. {a.desc}. {face}")
        refs = [a.photo]
    elif a.type == "object":
        prompt = OBJECT.format(desc=a.desc, screen=SCREEN[screen])
        refs = []
    else:
        prompt = (f"{STYLE.format(screen=SCREEN[screen])} The character: {a.desc}. Simple, iconic, readable at small "
                  f"sizes. {face}")
        refs = []
    old = load_cast(castdir) if (castdir / "cast.json").is_file() else None
    drawn = fal_image(prompt + (" " + a.note if a.note else ""), castdir / "ref_raw.png", refs, "1:1")
    if drawn or old is None or not (castdir / "ref.png").is_file():
        keyed(castdir / "ref_raw.png", castdir / "ref.png", screen)
    # a humanoid is measured by its body colour (hats and raised arms aside); a creature or object as a whole
    hue = a.hue or (dominant_hue(castdir / "ref.png") if a.type == "humanoid" else "all")
    if drawn or old is None:
        start_cast(castdir, hue, screen, a.type, a.note)
    ok = [s for s in sets if draw_set(castdir, s, screen, a.note)]
    if ok:
        cast = load_cast(castdir)
        cast.update(type=a.type, screen=screen, note=a.note)
        save_cast(castdir, cast)
        sprites.unify_sets(castdir, ok, hue, prefix=False)
        if "idle" not in load_cast(castdir)["poses"]:  # no set gave an idle: the reference's goes back in, first
            fit_into(castdir, Image.open(castdir / "ref.png").convert("RGBA"), "idle")
            cast = load_cast(castdir)
            cast["poses"] = ["idle"] + [p for p in cast["poses"] if p != "idle"]
            save_cast(castdir, cast)
        if not drawn:
            restore(castdir, old, ok)
    measure_cast(castdir, refit=False, center=bool(ok), quiet=True)
    review(castdir)
    report(castdir, sets, [s for s in sets if s not in ok])


def restore(castdir, old, redrawn):
    """Poses an earlier run, `add` or `pose` gave that this run's sets did not (the reference is unchanged, so
    they still match): fitted back in from their sources."""
    if not old:
        return
    have = set(load_cast(castdir)["poses"])
    lost = [p for p in old["poses"] if p not in have]
    for s in SETS:
        if s not in redrawn and (castdir / s / "poses.json").is_file():
            mine = [p for p in lost if p in json.loads((castdir / s / "poses.json").read_text())["poses"]]
            if mine:
                fit_set(castdir, s, mine)
                lost = [p for p in lost if p not in mine]
    for p in lost:
        if (castdir / "extra" / f"{p}.png").is_file():
            fit_into(castdir, Image.open(castdir / "extra" / f"{p}.png").convert("RGBA"), p)


def settings(a, castdir):
    """--screen and --note for add and pose: as given, else what cast.json recorded, else magenta and none."""
    cast = load_cast(castdir) if (castdir / "cast.json").is_file() else {}
    screen = a.screen or cast.get("screen") or "magenta"
    note = a.note if a.note is not None else cast.get("note", "")
    return screen, note


def cmd_add(a):
    castdir = Path(a.castdir)
    screen, note = settings(a, castdir)
    ensure_cast(castdir, screen)
    sets = [s.strip() for s in a.sets.split(",")]
    for s in sets:
        if s not in SETS:
            sys.exit(f"unknown pose set {s}; the sets are {', '.join(SETS)}")
    ok = []
    for s in sets:
        if draw_set(castdir, s, screen, note):
            fit_set(castdir, s)
            ok.append(s)
    measure_cast(castdir, refit=False, quiet=True)
    review(castdir)
    report(castdir, sets, [s for s in sets if s not in ok])


def cmd_pose(a):
    castdir = Path(a.castdir)
    screen, note = settings(a, castdir)
    ensure_cast(castdir, screen)
    raw = castdir / "extra" / f"{a.name}_raw.png"
    raw.parent.mkdir(exist_ok=True)
    if load_cast(castdir).get("type") == "object":
        prompt = (f"{KEEP} The same object, whole, {a.desc}. Single object centered on a perfectly flat solid "
                  f"{SCREEN[screen]} background. No floor, no shadow, no text.")
    else:
        prompt = (f"{KEEP} The same character, full body, {a.desc}, three-quarter view facing right. Single character "
                  f"centered on a perfectly flat solid {SCREEN[screen]} background. No floor, no shadow, no text.")
    fal_image(prompt + ONCE + (" " + note if note else ""), raw, [castdir / "ref_raw.png"], "1:1")
    cut = castdir / "extra" / f"{a.name}.png"
    keyed(raw, cut, screen)
    fit_into(castdir, Image.open(cut).convert("RGBA"), a.name)
    measure_cast(castdir, refit=False, quiet=True)
    review(castdir)


def cmd_measure(a):
    for d in a.castdir:
        castdir = Path(d)
        if not (castdir / "cast.json").is_file():
            sys.exit(f"{castdir} has no cast.json")
        measure_cast(castdir, refit=not a.no_refit)
        if not a.no_refit:
            review(castdir)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("castdir")
    n.add_argument("--desc", required=True)
    n.add_argument("--type", default="humanoid", choices=list(TYPES),
                   help="humanoid (base, act), creature (creature set: no walking, no weapons) or object (object set)")
    n.add_argument("--like", help="another character's folder whose design to keep")
    n.add_argument("--photo", help="a photo of the person to turn into the character")
    n.add_argument("--face", default="right", choices=["right", "left"])
    n.add_argument("--sets", help="pose sets to draw, e.g. base,act,fight (default: the type's)")
    n.add_argument("--hue", help="body hue band, e.g. 0-30; found from the reference when left out")
    d = sub.add_parser("add")
    d.add_argument("castdir")
    d.add_argument("--sets", required=True)
    p = sub.add_parser("pose")
    p.add_argument("castdir")
    p.add_argument("--name", required=True)
    p.add_argument("--desc", required=True)
    for q in (n, d, p):
        q.add_argument("--screen", choices=list(SCREEN), help="magenta (default for new) or green; add and pose "
                       "use the one cast.json recorded")
        q.add_argument("--note", default=None if q is not n else "",
                       help="a sentence added to every prompt: what must never change "
                       "(\"Its face is only two black square eyes; it never has a mouth.\")")
    m = sub.add_parser("measure")
    m.add_argument("castdir", nargs="+")
    m.add_argument("--no-refit", action="store_true", help="only measure: leave every pose's pixels as they are")
    a = ap.parse_args()
    {"new": cmd_new, "add": cmd_add, "pose": cmd_pose, "measure": cmd_measure}[a.cmd](a)


if __name__ == "__main__":
    main()
