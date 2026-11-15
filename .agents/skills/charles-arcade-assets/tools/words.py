#!/usr/bin/env python3
"""Print a transcript as timed phrases and words, the view you plan beats from, or draw it over the sound.

  words.py <project>/transcript.json [--offset 12.4]
  words.py <project>/transcript.json --strip check.png [--from 27.3 --to 29.6] [--audio part.m4a] [--row 6]

transcript.json is what `npx hyperframes transcribe <audio> -d <project>` writes: [{text, start, end}, ...].
--offset subtracts a clip's start, so a part of a longer video reads in the part's own seconds.
Phrases break on pauses of 0.25 s or more and after . ! ? so each line is a candidate beat.

--strip draws the sound with every word's start marked, to check a hit by eye: a spectrogram (the hiss of an s
at the top, the burst of a p or k as a thin vertical line, vowels as bright bands at the bottom) over the
waveform, a red line and the word and its start at each start, and a ruler in 0.1 s. A start is right when its
line sits where that word's sound begins: the edge where the waveform swells out of a dip and the spectrogram
lights up. --from/--to pick the span in the listing's seconds (default: all of it), drawn in rows of --row
seconds (default 6, 300 px a second); seven rows to an image, then <out>_2.png and on. The audio is --audio,
else part.m4a, assets/voice.* or voice.* next to the transcript. Needs ffmpeg; standard library only.
"""
import argparse, base64, json, math, struct, subprocess, sys, unicodedata, zlib
from array import array
from pathlib import Path

SR = 16000
WIDTH = 1800                 # strip image width in px
ROWS_PER_IMAGE = 7
LABEL_H, SPEC_H, WAVE_H, RULER_H, GAP = 84, 120, 100, 30, 18   # one row of the strip, top to bottom
RED, GREEN, INK, GREY, BLUE = (225, 30, 30), (0, 165, 70), (30, 30, 40), (150, 150, 160), (70, 120, 235)
# Monaco 10 px without antialiasing: ASCII 32-126, 6x13 cells, one byte per row (bit 5 = leftmost pixel).
FONT = ("eNpdVNuK4zAMNa4oppjBU7yQXTzFmEzImn0IZSh9CJ7//6uRLclxV5QS+UjHR5dEqRczzZRpjvf+QC6Xb/zRiQl5newlhxb3/jf7y6/P1MKmObr1"
        "M300BwB6vgZjHJoxoJUzABoNwDikyyFkM4ooZnCVtdDd8iLXWuJuRC7G6oS05HtKgaimtRZEWSGhCBe7Y7XmMLB+LqK2xLgnrXe6waEjbCXVi1hbwNOO1Keb"
        "hmnQxdrEkRJOdrMndZRzFITndjuEyhTsdcl5cW8yH+9Lol6jsKpt55yIxnKeM56n+dnrQaiMTuw5i5SACaVmEUKLQMitjqqHzeu2rTOFRTKiTo9H7gTpfkfV"
        "S+rd6a1qkg8FhMBJEKFGbaHPpxheTBZ6sNUn7zuSc5atxXNslshpQRxW2i6y6jcjhh1u64mbSQpALNTGe5/Uf0YMBsazGwpa/nB3/t37fKjbrFrrIawiRRDr"
        "9vqWuBc2HQ42EmHUVCXTioFIfbYwHJA0kSuTTfzK1dgZ2HgOYUR2nhAroJY8JpT27DkTcI5rqq9yTxqLG+ZDE+pfFRrQS5ijS8vxnp5rAVv9O6s+qkZHhw1u"
        "kb8XYvoB0dlCPA==")
GW, GH = 6, 13


def load_words(path):
    words = json.load(open(path))
    if isinstance(words, dict):
        words = words.get("words", [])
    return words


def listing(words, offset):
    phrases, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt is None or nxt["start"] - w["end"] >= 0.25 or w["text"].rstrip().endswith((".", "!", "?")):
            phrases.append(cur)
            cur = []
    print("PHRASES (start-end | text)")
    for p in phrases:
        s, e = p[0]["start"] - offset, p[-1]["end"] - offset
        print(f"{s:6.2f}-{e:6.2f} | {' '.join(w['text'].strip() for w in p)}")
    print("\nWORDS (start word)")
    line = []
    for w in words:
        line.append(f"{w['start'] - offset:.2f} {w['text'].strip()}")
        if len(line) == 6:
            print("  ".join(line))
            line = []
    if line:
        print("  ".join(line))


# ---- a tiny RGB canvas that writes PNG with zlib ----

_GLYPHS = []


def ascii_text(s):
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace("→", ">")
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode() or "?"


class Canvas:
    def __init__(self, w, h, bg=(255, 255, 255)):
        self.w, self.h = w, h
        self.px = bytearray(bytes(bg) * (w * h))

    def rect(self, x0, y0, x1, y1, c):
        x0, x1 = max(0, int(round(x0))), min(self.w, int(round(x1)))
        y0, y1 = max(0, int(round(y0))), min(self.h, int(round(y1)))
        if x0 >= x1:
            return
        run = bytes(c) * (x1 - x0)
        for y in range(y0, y1):
            o = (y * self.w + x0) * 3
            self.px[o:o + len(run)] = run

    def dashed(self, x, y0, y1, c, w=2, on=6, off=4):
        y = y0
        while y < y1:
            self.rect(x, y, x + w, min(y + on, y1), c)
            y += on + off

    def blit(self, x, y, w, h, rgb):
        for r in range(h):
            o = ((y + r) * self.w + x) * 3
            self.px[o:o + w * 3] = rgb[r * w * 3:(r + 1) * w * 3]

    def text(self, x, y, s, c, scale=1, bg=None):
        if not _GLYPHS:
            _GLYPHS.append(zlib.decompress(base64.b64decode(FONT)))
        font = _GLYPHS[0]
        s = ascii_text(s)
        if bg:
            self.rect(x - 2, y - 1, x + text_w(s, scale) + 2, y + GH * scale + 1, bg)
        for k, ch in enumerate(s):
            i = ord(ch) - 32 if 32 <= ord(ch) < 127 else ord("?") - 32
            gx = x + k * GW * scale
            for r, bits in enumerate(font[i * GH:(i + 1) * GH]):
                for col in range(GW):
                    if bits & (32 >> col):
                        self.rect(gx + col * scale, y + r * scale, gx + (col + 1) * scale, y + (r + 1) * scale, c)

    def png(self, path):
        stride = self.w * 3
        raw = b"".join(b"\x00" + bytes(self.px[y * stride:(y + 1) * stride]) for y in range(self.h))

        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
                              + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def text_w(s, scale=1):
    return len(ascii_text(s)) * GW * scale


# ---- the sound ----

def decode(audio):
    """The whole audio as mono 16 kHz int16 samples."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                       capture_output=True)
    if r.returncode:
        sys.exit(f"ffmpeg could not decode {audio}: {r.stderr.decode()[-400:]}")
    a = array("h")
    a.frombytes(r.stdout[:len(r.stdout) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    return a


def spectrogram(samples, w, h):
    """ffmpeg's grayscale spectrogram (0-8 kHz, low at the bottom) of these samples as w x h RGB bytes."""
    buf = array("h", samples)
    if sys.byteorder == "big":
        buf.byteswap()
    data = buf.tobytes()
    r = subprocess.run(["ffmpeg", "-v", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-", "-lavfi",
                        f"showspectrumpic=s={w}x{h}:legend=0:scale=log:color=channel:fscale=lin:drange=75",
                        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], input=data, capture_output=True)
    return r.stdout if len(r.stdout) == w * h * 3 else None


def find_audio(transcript):
    d = Path(transcript).resolve().parent
    for pat in ("part.m4a", "assets/voice.*", "voice.*", "part.*", "*.m4a", "*.mp3", "*.wav"):
        hits = sorted(p for p in d.glob(pat) if p.suffix.lower() in (".m4a", ".mp3", ".wav", ".aac", ".mp4", ".mov", ".flac"))
        if hits:
            return hits[0]
    return None


def draw_strip(audio, words, out, rows, offset=0.0, marks=(), title=None, samples=None):
    """Draw rows of the sound with word starts marked.

    rows: [(t0, t1), ...] in display seconds (audio time minus offset); each row is WIDTH px wide, and every row
    of one call uses the scale of the longest. marks: [(t, label, colour)] extra lines in display seconds (a
    suggested time is drawn dashed green). Writes out, then <out>_2.png ... for every ROWS_PER_IMAGE rows; returns
    the paths."""
    a = samples if samples is not None else decode(audio)
    n, pad = len(a), 200
    spans = []                                 # per row: its samples (zeros past the audio), prefix sums of squares
    for t0, t1 in rows:
        s0, s1 = int(round((t0 + offset) * SR)) - pad, int(round((t1 + offset) * SR)) + pad
        seg = array("h", [0]) * max(0, -s0) + a[max(0, s0):max(0, min(n, s1))]
        seg += array("h", [0]) * max(0, (s1 - s0) - len(seg))
        sq, acc = array("d", [0.0]), 0.0
        for v in seg:
            acc += v * v
            sq.append(acc)
        spans.append((s0, seg, sq))
    peak = max([1] + [max(abs(min(seg)), abs(max(seg))) for _, seg, _ in spans if seg])
    loud = sorted(math.sqrt((sq[i + 320] - sq[i]) / 320) for _, seg, sq in spans for i in range(0, len(seg) - 320, 160))
    ref = loud[int(len(loud) * 0.95)] if loud else 1.0
    span = max(t1 - t0 for t0, t1 in rows)
    pps = (WIDTH - 20) / span                  # px per second
    row_h = LABEL_H + SPEC_H + WAVE_H + RULER_H + GAP
    head = 34 if title else 0
    paths = []
    for page in range(0, len(rows), ROWS_PER_IMAGE):
        chunk_rows = rows[page:page + ROWS_PER_IMAGE]
        cv = Canvas(WIDTH, head + row_h * len(chunk_rows))
        if title:
            cv.text(10, 8, title, INK, 2 if text_w(title, 2) < WIDTH - 20 else 1)
        for k, (t0, t1) in enumerate(chunk_rows):
            y0 = head + k * row_h
            x_of = lambda t: 10 + (t - t0) * pps
            xw = int(round((t1 - t0) * pps))
            ys, yw, yr = y0 + LABEL_H, y0 + LABEL_H + SPEC_H, y0 + LABEL_H + SPEC_H + WAVE_H
            base, seg, sq = spans[page + k]
            r0 = int(round((t0 + offset) * SR))
            spec = spectrogram(seg[pad:len(seg) - pad], xw, SPEC_H) if xw > 8 else None
            if spec:
                cv.blit(10, ys, xw, SPEC_H, spec)
            else:
                cv.rect(10, ys, 10 + xw, yw, (20, 20, 24))
            cv.rect(10, yw, 10 + xw, yr, (246, 247, 251))
            mid = yw + WAVE_H // 2
            prev = None
            for x in range(xw):                # waveform (min-max per column) and level line in dB
                c0 = r0 - base + int(x / pps * SR)
                c1 = max(c0 + 1, r0 - base + int((x + 1) / pps * SR))
                part = seg[c0:c1]
                if part:
                    top = mid - max(part) / peak * (WAVE_H / 2 - 4)
                    bot = mid - min(part) / peak * (WAVE_H / 2 - 4)
                    cv.rect(10 + x, top, 11 + x, bot + 1, (150, 180, 245))
                c = (c0 + c1) // 2
                w0, w1 = max(0, c - 160), min(len(seg), c + 160)
                lv = math.sqrt((sq[w1] - sq[w0]) / max(1, w1 - w0)) if w1 > w0 else 0.0
                db = 20 * math.log10(max(lv, 1e-9) / ref)
                yl = yw + 3 + (min(0.0, max(-60.0, db)) / -60.0) * (WAVE_H - 6)
                if prev is not None:
                    cv.rect(9 + x, min(prev, yl) - 1, 11 + x, max(prev, yl) + 1, (35, 45, 90))
                prev = yl
            # ruler: a tick every 0.05 s, a long one and a label every 0.1 s (0.5 s when crowded)
            step = 0.1 if pps * 0.1 >= text_w("00.0") + 6 else 0.5
            t = math.ceil(t0 * 20 - 1e-6) / 20
            while t <= t1 + 1e-6:
                x = x_of(t)
                tenth = abs(t * 10 - round(t * 10)) < 1e-6
                cv.rect(x, yr, x + 1, yr + (9 if tenth else 4), INK if tenth else GREY)
                if tenth and abs(t / step - round(t / step)) < 1e-6:
                    cv.text(int(x) - text_w(f"{t:.1f}") // 2, yr + 11, f"{t:.1f}", INK)
                t = round(t + 0.05, 4)
            cv.rect(10, yr, 10 + xw, yr + 1, INK)
            # word starts: a red line through the sound, the word (and its start) in one of three lanes above
            lanes = [-1e9, -1e9, -1e9]
            for w in words:
                ts = w["start"] - offset
                if not t0 <= ts <= t1:
                    continue
                x = x_of(ts)
                label, sub = w["text"].strip(), f"{ts:.2f}"
                lw = text_w(label, 2) + 4 + text_w(sub) + 12
                lane = next((i for i, e in enumerate(lanes) if e <= x), min(range(3), key=lambda i: lanes[i]))
                lanes[lane] = x + lw
                ly = y0 + 2 + lane * 27
                cv.rect(x, ly, x + 1, yr, RED)
                cv.rect(x - 1, ys, x + 2, yr, RED)
                cv.text(int(x) + 4, ly, label, RED, 2, bg=(255, 255, 255))
                cv.text(int(x) + 4 + text_w(label, 2) + 4, ly + 12, sub, RED, 1, bg=(255, 255, 255))
            for tm, label, colour in marks:
                if t0 <= tm <= t1:
                    x = x_of(tm)
                    cv.dashed(int(x) - 1, ys, yr, colour, w=3)
                    cv.text(int(x) + 4, yr - 16, label, colour, 1, bg=(255, 255, 255))
        path = Path(out) if page == 0 else Path(out).with_name(f"{Path(out).stem}_{page // ROWS_PER_IMAGE + 1}{Path(out).suffix}")
        cv.png(path)
        paths.append(path)
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcript")
    ap.add_argument("--offset", type=float, default=0.0)
    ap.add_argument("--strip", metavar="OUT.png", help="draw the sound with each word's start marked")
    ap.add_argument("--from", dest="t0", type=float, help="strip start, in the listing's seconds")
    ap.add_argument("--to", dest="t1", type=float, help="strip end, in the listing's seconds")
    ap.add_argument("--row", type=float, default=6.0, help="seconds per strip row (default 6)")
    ap.add_argument("--audio", help="the audio the transcript was made from (default: found next to it)")
    args = ap.parse_args()
    words = load_words(args.transcript)
    if not args.strip:
        listing(words, args.offset)
        return
    audio = Path(args.audio) if args.audio else find_audio(args.transcript)
    if not audio or not audio.exists():
        sys.exit("no audio found next to the transcript: pass --audio <the file it was transcribed from>")
    a = decode(audio)
    end = len(a) / SR - args.offset
    t0 = max(-args.offset, args.t0 if args.t0 is not None else (words[0]["start"] - args.offset - 0.3 if words else 0)) + 0.0
    t1 = min(end, args.t1 if args.t1 is not None else end)
    if t1 <= t0:
        sys.exit(f"nothing to draw between {t0:.2f} and {t1:.2f} s")
    if t1 - t0 <= args.row * 1.25:
        rows = [(t0, t1)]
    else:
        rows = [(t0 + args.row * i, min(t1, t0 + args.row * (i + 1))) for i in range(math.ceil((t1 - t0) / args.row))]
    title = f"{Path(args.transcript).name} over {audio.name}: {t0:.2f}-{t1:.2f} s (red: each word's start)"
    for p in draw_strip(audio, words, args.strip, rows, args.offset, title=title, samples=a):
        print(f"saved: {p}")


if __name__ == "__main__":
    main()
