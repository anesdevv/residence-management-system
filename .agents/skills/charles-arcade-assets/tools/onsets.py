#!/usr/bin/env python3
"""Snap transcript word starts to where the speech after each pause begins in the audio; check the words inside
phrases and move the ones you confirm.

  onsets.py <transcript.json> <audio> [--out transcript.json] [--window -0.15,0.45]
  onsets.py <transcript.json> <audio> --check [--tol 0.1] [--strip check.png] [--words paywall,aha] [--all]
  onsets.py <transcript.json> <audio> --move 27.68,28.72 [--move paywall=27.82] [--out transcript.json]

Speech recognisers time a word from the text, not the sound, and go wrong most on a word after a pause: Whisper
starts "kill" 0.26 s early, in the silence before it, and Parakeet's 80 ms steps add their own. This measures
the level in three bands (voicing, vowels, hiss) in 25 ms frames every 10 ms (16 kHz mono through ffmpeg,
numpy only) and finds every pause: 150 ms or more below speech level (more than 30 dB under the loud parts;
a breath counts as pause). Where speech resumes, the onset is where the level rises steeply out of the dip,
timed halfway up the rise in whichever band rises first (the hiss of an "s", the burst of a "k").
The word that starts there is the first one the recogniser put inside the pause, skipping words that close
the phrase before it (ending in . , ! ? ; : after a word that does not: said before the pause, drifted late);
else the word still sounding when speech resumes, unless it closes the phrase before; else the next. It
moves to the onset when that is within the window around its start (default 0.15 s earlier to 0.45 s later).
Words inside phrases keep their times (a word after no pause, like "slop" in "comment slop", is not
checked); the order stays monotonic (a word a move overtakes is pushed just after it), the word before a word
that moved earlier ends where it now starts, and every word lasts at least 50 ms. Running it twice changes
nothing the second time.

Prints each word that moved and by how much. Writes --out (default: the transcript itself, after keeping the
original once as <name>.raw.json). Run it after every `hf transcribe`, before planning beats. Needs ffmpeg and
numpy (the repo venv).

--check reports, without moving anything, every word whose start is more than --tol seconds (default 0.1) from
where its sound starts, with that time. Inside phrases recognisers drift by 0.1-0.25 s: early into the word
before ("the paywall"), late onto the word's own second syllable at the end of a phrase ("aha moment"). So
between two pauses it pairs the transcript's syllables, in order, with the voiced peaks of the sound (each vowel
is one), and times each word's first sound before its first vowel: the burst of a p, t or k, the hiss of an s,
f or sh, the fall into an m or n, the rise of a vowel (also after w, r, l, h and the voiced b, d, g). A word
after a place where syllables and peaks did not pair one to one (words run together, a long vowel heard as two)
is less sure: those are listed on one line, and --all lists and draws them in full. --words checks only the
words that carry hits (the beat sheet's key words) and says of each: off (with the time), ok, or not paired.
--strip draws the flagged words, the start in red and the suggestion in green, to confirm by eye. Run it after
the plain run. On clean voiceovers it flags about one word in four, most of them real drift; on fast
conversational speech most flags are less sure, so check the hit words with --words there.

--move sets the starts you confirmed, with the same bookkeeping: give a start time or a word from the report
to take its suggestion (27.68, paywall), or your own time read off the strip (paywall=27.82, 27.68=27.82).
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

import numpy as np

SR, HOP, WIN = 16000, 160, 400                   # 16 kHz, 10 ms hop, 25 ms frame
BANDS = [(80, 500), (500, 2500), (2500, 7800)]   # voicing, vowel formants, hiss and bursts
PAUSE = 15                                       # frames below speech level that make a pause (150 ms)
GAP = 0.04                                       # words keep at least this far apart


def decode(path):
    """Mono 16 kHz float samples via ffmpeg."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR),
                        "-f", "s16le", "-"], capture_output=True)
    if r.returncode:
        sys.exit(f"ffmpeg could not decode {path}: {r.stderr.decode()[-400:]}")
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768


def band_levels(x, hop=HOP):
    """dB level per frame in each band, and in all of them together: shape (frames, len(BANDS) + 1)."""
    n = max(1, 1 + (len(x) - WIN) // hop)
    x = np.pad(x, (0, max(0, WIN + (n - 1) * hop - len(x))))
    f = np.fft.rfftfreq(512, 1 / SR)
    win = np.hanning(WIN)
    out = []
    for s in range(0, n, 8192):                  # in blocks, so a long file does not need gigabytes
        k = np.arange(s, min(n, s + 8192))
        power = np.abs(np.fft.rfft(x[np.arange(WIN)[None, :] + hop * k[:, None]] * win, 512, axis=1)) ** 2
        cols = [power[:, (f >= lo) & (f < hi)].sum(1) for lo, hi in BANDS]
        cols.append(sum(cols))
        out.append(10 * np.log10(np.stack(cols, 1) + 1e-10))
    return np.concatenate(out)


def frame_time(k):
    return (k * HOP + WIN / 2) / SR


def rise_time(e, k, back=8, ahead=8):
    """Where band level e climbs out of its dip into frame k: halfway (in dB) from the lowest level in the `back`
    frames before k to the highest in the `ahead` frames from k, interpolated between frames. (time, rise dB)"""
    lo = max(0, k - back)
    d = lo + int(np.argmin(e[lo:k + 1]))
    p = k + int(np.argmax(e[k:min(len(e), k + ahead)]))
    half = (e[d] + e[p]) / 2
    j = d
    while j < p and e[j + 1] < half:
        j += 1
    if j >= p:
        return frame_time(p), e[p] - e[d]
    return frame_time(j) + (half - e[j]) / max(e[j + 1] - e[j], 1e-6) * HOP / SR, e[p] - e[d]


def pause_onsets(levels):
    """[(onset time, pause length s)] for every place speech resumes after a pause of PAUSE frames or more.
    Speech is any frame within 30 dB of the loud parts (95th percentile); the onset is the earliest band rise
    of 12 dB or more into the first speech frame, else that frame's time."""
    total = levels[:, -1]
    speech = total >= np.percentile(total, 95) - 30
    out, quiet = [], PAUSE   # the start of the audio counts as a pause
    for k in range(len(total)):
        if not speech[k]:
            quiet += 1
            continue
        if quiet >= PAUSE:
            times = [rise_time(levels[:, b], k) for b in range(len(BANDS))]
            rising = [t for t, rise in times if rise >= 12 and t <= frame_time(k) + 0.02]
            out.append((min(rising) if rising else frame_time(k), quiet * HOP / SR))
        quiet = 0
    return out


ENDS = (".", ",", "!", "?", ";", ":")


def phrase_final(words, j):
    """The word closes a phrase without opening one: it ends in punctuation and the word before it does not."""
    return j > 0 and words[j]["text"].strip().endswith(ENDS) and not words[j - 1]["text"].strip().endswith(ENDS)


def settle(words, changed):
    """After moving the words in `changed`: keep the order (a word a move overtook goes just after it), make a
    moved word last 50 ms or more, and end the word before it by its start. Returns the words pushed later."""
    pushed, changed = [], set(changed)
    for k in range(1, len(words)):
        a, b = words[k - 1], words[k]
        if k - 1 in changed and b["start"] < a["start"] + GAP:
            pushed.append(b["text"].strip())
            b["start"] = round(a["start"] + GAP, 3)
            changed.add(k)
    for k in sorted(changed):
        w = words[k]
        nxt = words[k + 1]["start"] if k + 1 < len(words) else None
        w["end"] = round(min(max(w["end"], w["start"] + 0.05), nxt if nxt is not None else 1e9), 3)
        if k and words[k - 1]["end"] > w["start"]:
            words[k - 1]["end"] = round(max(w["start"], words[k - 1]["start"] + 0.01), 3)
    return pushed


def snap(words, onsets, lo, hi):
    """Move the first word of each speech run to its onset; returns ([(word index, old start)], [pushed words]).
    The first word is one the recogniser put inside the pause (after any that close the phrase before it: those
    were said before the pause and drifted late), else the word still sounding when speech resumes (unless it
    closes the phrase before), else the one after it, when that one spans the pause."""
    moved, i0 = [], 0
    for t, plen in onsets:
        p0 = t - plen
        inside = [j for j in range(i0, len(words)) if words[j]["start"] >= p0 - 0.02 and words[j]["end"] <= t + 0.02
                  and words[j]["end"] > p0 + 0.02]
        finals = [k for k, j in enumerate(inside) if phrase_final(words, j)]
        cands = inside[finals[-1] + 1:] if finals else inside
        i = i0
        while i < len(words) and words[i]["end"] <= t + 0.02:   # words that ended before speech resumed
            i += 1
        cands += [j for j in (i, i + 1) if j < len(words) and not (j == i and phrase_final(words, j))]
        for j in cands:
            if lo <= t - words[j]["start"] <= hi:
                if abs(t - words[j]["start"]) >= 0.005:
                    moved.append((j, words[j]["start"]))
                    words[j]["start"] = round(t, 3)
                i0 = j + 1
                break
    pushed = settle(words, {j for j, _ in moved})
    return moved, pushed


# ---- --check: where does each word's sound start? ----

CHOP = 80                    # 5 ms frames for the check
CFPS = SR / CHOP
SMOOTH, PROM, MIN_SEP, PEAK_DB, VOICE_DB = 7, 3.0, 14, 20, 20   # vowel peaks: 35 ms smoothing, 3 dB apart, 70 ms
MISS = EXTRA = 0.5           # cost of a syllable without a peak, or a peak without a syllable (in seconds of shift)
UP = 0.3                     # a rise is timed 30% of the way up (in dB): where it is first heard

ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
        "seventeen eighteen nineteen").split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
SAID = {  # syllables as usually spoken, where the spelling misleads
    "every": 2, "everyone": 3, "everything": 3, "everywhere": 3, "everybody": 4, "everyday": 3, "different": 2,
    "business": 2, "several": 2, "favorite": 2, "favourite": 2, "camera": 2, "family": 2, "interesting": 3,
    "evening": 2, "chocolate": 2, "comfortable": 3, "actually": 3, "basically": 3, "probably": 3, "literally": 3,
    "usually": 3, "really": 2, "fire": 1, "hour": 1, "our": 1, "real": 1, "idea": 3, "ideas": 3, "create": 2,
    "created": 3, "video": 3, "videos": 3, "area": 3, "media": 3, "social": 2, "special": 2, "being": 2,
    "doing": 2, "going": 2, "seeing": 2, "saying": 2, "playing": 2, "paying": 2, "trying": 2, "buying": 2,
    "science": 2, "quiet": 2, "client": 2, "giant": 2, "via": 2, "duo": 2, "duolingo": 4, "react": 2,
    "someone": 2, "something": 2, "sometimes": 2, "somewhere": 2, "anyone": 3, "people": 2, "little": 2}


def spell(n):
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        return ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + spell(n % 100))
    for v, name in ((10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")):
        if n >= v:
            return spell(n // v) + " " + name + ("" if n % v == 0 else " " + spell(n % v))
    return ""


def spoken(text):
    """The words as said: numbers spelled out, an initialism (AI, CTA) as letters marked with #."""
    out = []
    for tok in re.findall(r"[A-Za-z0-9$%&+.,']+", text):
        core = tok.strip(".,'")
        if core.isalpha() and core.isupper() and 1 < len(core) <= 4:
            out += ["#" + c.lower() for c in core]
            continue
        t = core.lower().replace("%", " percent").replace("&", " and ").replace("+", " plus ")

        def num(m):
            s = m.group(0).replace(",", "")
            try:
                return " " + spell(int(float(s))) + " "
            except (ValueError, OverflowError):
                return " " + " ".join(ONES[int(c)] for c in s if c.isdigit()) + " "
        t = re.sub(r"\d[\d,]*(\.\d+)?", num, t)
        t = re.sub(r"(?<=\s)k\b", " thousand ", t)
        t = re.sub(r"(?<=\s)m\b", " million ", t)
        out += re.findall(r"[a-z']+", t) + (["dollars"] if "$" in tok else [])
    return out


def syllables(text):
    n_all = 0
    for w in spoken(text):
        if w.startswith("#"):
            n_all += 3 if w == "#w" else 1
            continue
        w = w.replace("'", "")
        if not w:
            continue
        if w in SAID:
            n_all += SAID[w]
            continue
        if not re.search(r"[aeiouy]", w):
            n_all += len(w)
            continue
        n = len(re.findall(r"[aeiouy]+", w))
        if w.endswith("e") and not w.endswith(("le", "ee", "ye")) and n > 1:
            n -= 1
        elif re.search(r"[^aeiouy]les$", w):
            pass
        elif w.endswith("es") and n > 1 and not re.search(r"(s|z|x|ch|sh|ce|ge)es$", w):
            n -= 1
        elif re.search(r"[^aeiouydt]ed$", w) and n > 1:
            n -= 1
        n_all += max(1, n)
    return max(1, n_all)


def first_sound(text):
    """burst (p t k), hiss (s f sh th ch), nasal (m n) or vowel (vowels, w y r l h, and b d g, whose voiced
    closure shows only as a dip in the vowel band): what the start of the word looks like."""
    ws = spoken(text)
    w = ws[0] if ws else ""
    if w.startswith("#"):
        c = w[1:]
        return "nasal" if c in "mn" else "hiss" if c in "fhsx" else "burst" if c in "cgjkpqtvz" else "vowel"
    if not w or w.startswith(("wh", "wr")):
        return "vowel"
    if w.startswith(("sh", "ch", "th", "ph")):
        return "hiss"
    if w.startswith("kn"):
        return "nasal"
    c = w[0]
    if c == "c":
        return "hiss" if w[1:2] in ("e", "i", "y") else "burst"
    return "hiss" if c in "szfvjx" else "burst" if c in "ptkq" else "nasal" if c in "mn" else "vowel"


def ctime(k):
    return (k * CHOP + WIN / 2) / SR


def speech_runs(total):
    """[(first frame, end frame)] of speech between pauses of 150 ms or more (5 ms frames)."""
    speech = total >= np.percentile(total, 95) - 30
    runs, k, n = [], 0, len(total)
    while k < n:
        if not speech[k]:
            k += 1
            continue
        a, quiet, last = k, 0, k
        while k < n and quiet < 30:
            if speech[k]:
                quiet, last = 0, k
            else:
                quiet += 1
            k += 1
        runs.append((a, last + 1))
    return runs


def vowel_peaks(vow, voice, a, b, vref, lref):
    """Frames of the voiced peaks of the (smoothed) vowel band in [a, b): one per syllable, 3 dB apart."""
    cand = [k for k in range(max(a, 1), min(b, len(vow) - 1)) if vow[k] >= vow[max(a, k - 6):k + 7].max() - 1e-9
            and vow[k] >= vref - PEAK_DB and voice[k] >= lref - VOICE_DB]
    merged = True
    while merged and len(cand) > 1:
        merged = False
        for i in range(len(cand) - 1):
            p, q = cand[i], cand[i + 1]
            if min(vow[p], vow[q]) - vow[p:q + 1].min() < PROM or q - p < MIN_SEP:
                del cand[i + 1 if vow[p] >= vow[q] else i]
                merged = True
                break
    return cand


def up_time(e, d, p, frac=UP):
    """When level e has risen `frac` of the way (in dB) from frame d to frame p."""
    lvl = e[d] + frac * (e[p] - e[d])
    j = d
    while j < p and e[j + 1] < lvl:
        j += 1
    return ctime(p) if j >= p else ctime(j) + (lvl - e[j]) / max(e[j + 1] - e[j], 1e-6) / CFPS


def down_time(e, p, d, frac=0.4):
    """When level e has fallen `frac` of the way from frame p to frame d."""
    lvl = e[p] - frac * (e[p] - e[d])
    j = p
    while j < d and e[j + 1] > lvl:
        j += 1
    return ctime(d) if j >= d else ctime(j) + (e[j] - lvl) / max(e[j] - e[j + 1], 1e-6) / CFPS


def sound_start(L, vow, lo, p, kind, ref):
    """Where a syllable whose vowel peaks at frame p starts, looking back to the previous peak lo. (time, how)"""
    total, hiss = L[:, 3], L[:, 2]
    dip = lo + int(np.argmin(vow[lo:p + 1]))
    rise = up_time(vow, dip, p) if vow[p] - vow[dip] >= 4 else ctime(dip)
    if kind == "nasal":
        return down_time(vow, lo, dip), "nasal"
    hp = lo + int(np.argmax(hiss[lo:p + 1]))           # the hiss before the vowel: an s, or a k's burst
    hd = lo + int(np.argmin(hiss[lo:hp + 1])) if hp > lo else hp
    hissed = up_time(hiss, hd, hp) if hiss[hp] - hiss[hd] >= 8 and hiss[hp] >= ref - 35 else None
    if kind == "hiss" and hissed is not None:
        return hissed, "hiss"
    if kind == "burst":
        d = lo + int(np.argmin(total[lo:p + 1]))            # the closure before it
        closed = up_time(total, d, d + int(np.argmax(total[d:p + 1]))) if total[p] - total[d] >= 10 else None
        if closed is not None or hissed is not None:     # the later one: an earlier dip or hiss is the word before
            return max(t for t in (closed, hissed) if t is not None), "burst"
    return rise, "vowel"


def sound_starts(words, x):
    """{word index: (time its sound starts, how, sure)} for every word that lines up with the sound."""
    L = band_levels(x, CHOP)
    total = L[:, 3]
    ref = np.percentile(total, 95)
    vow = np.convolve(L[:, 1], np.ones(SMOOTH) / SMOOTH, mode="same")
    vref, lref = np.percentile(L[:, 1], 95), np.percentile(L[:, 0], 95)
    resumes = pause_onsets(band_levels(x))
    out = {}
    for a, b in speech_runs(total):
        ta, tb = ctime(a), ctime(b)
        ws = [i for i, w in enumerate(words) if ta - 0.15 <= w["start"] < tb - 0.05]
        if not ws:
            continue
        near = [t for t, _ in resumes if abs(t - ta) < 0.12]
        out[ws[0]] = (round(float(near[0] if near else ta), 3), "pause", True)
        peaks = vowel_peaks(vow, L[:, 0], a, b, vref, lref)
        if len(peaks) < 2 or len(ws) < 2:
            continue
        syl = []                                  # (word, syllable of it, when the recogniser has it)
        for n, i in enumerate(ws):
            m = syllables(words[i]["text"])
            s = min(max(words[i]["start"], ta), tb - 0.05)
            e = min(max(words[ws[n + 1]]["start"] if n + 1 < len(ws) else tb, s + 0.05), tb)
            syl += [(i, j, s + (j + 0.5) * (e - s) / m) for j in range(m)]
        T = [ctime(p) for p in peaks]
        S, N = len(syl), len(T)
        D = np.full((S + 1, N + 1), 1e9)
        B = np.zeros((S + 1, N + 1), int)
        D[0, :] = np.arange(N + 1) * EXTRA
        D[:, 0] = np.arange(S + 1) * MISS
        for i in range(1, S + 1):
            for j in range(1, N + 1):
                c = (D[i - 1, j - 1] + abs(T[j - 1] - syl[i - 1][2]), D[i - 1, j] + MISS, D[i, j - 1] + EXTRA)
                B[i, j] = int(np.argmin(c))
                D[i, j] = c[B[i, j]]
        i, j, ops = S, N, []
        while i > 0 or j > 0:                     # trace back: pairs, and the skips between them
            if i > 0 and j > 0 and B[i, j] == 0:
                ops.append((i - 1, j - 1))
                i, j = i - 1, j - 1
            elif j == 0 or (i > 0 and B[i, j] == 1):
                ops.append((i - 1, None))
                i -= 1
            else:
                ops.append((None, j - 1))
                j -= 1
        skips = 0
        for si, k in reversed(ops):
            if si is None or k is None:
                skips += 1
                continue
            wi, sj, _ = syl[si]
            if sj or wi == ws[0] or k == 0:
                continue
            t, how = sound_start(L, vow, peaks[k - 1], peaks[k], first_sound(words[wi]["text"]), ref)
            out[wi] = (round(float(t), 3), how, skips == 0)
    return out


HOW = {"pause": "speech resumes after a pause", "burst": "the burst of its first consonant",
       "hiss": "the hiss of its first consonant", "nasal": "where its m or n begins", "vowel": "where its vowel rises"}


def check(words, x, tol):
    """[(word index, start, sound start, how, sure)] for every word more than tol from where its sound starts."""
    found = sound_starts(words, x)
    return [(i, words[i]["start"], t, how, sure) for i, (t, how, sure) in sorted(found.items())
            if abs(t - words[i]["start"]) > tol], found


def check_strip(audio, words, flags, out):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import words as W                             # the strip drawer (standard library)
    rows = []
    for i, start, t, how, sure in flags:
        a, b = min(start, t) - 0.6, max(start, t) + 0.6
        if rows and a <= rows[-1][1] and b - rows[-1][0] <= 3.0:
            rows[-1] = (rows[-1][0], b)
        else:
            rows.append((a, b))
    marks = [(t, f"> {words[i]['text'].strip()} {t:.2f}{'' if sure else ' ?'}", W.GREEN)
             for i, start, t, how, sure in flags if abs(t - start) > 0.001]
    title = "onsets.py --check: red = the transcript's start, green = where the sound starts (? = less sure)"
    return W.draw_strip(audio, words, out, rows, marks=marks, title=title)


def norm(text):
    return re.sub(r"[^a-z0-9']", "", text.lower())


def parse_moves(items, words, found, tol):
    """{word index: new start} from --move items: a start time or a word (take the suggestion), or either
    followed by =time (your own)."""
    moves = {}
    for item in [s.strip() for arg in items for s in arg.split(",") if s.strip()]:
        key, _, val = item.partition("=")
        try:
            t0 = float(key)
            idx = [i for i, w in enumerate(words) if abs(w["start"] - t0) < 0.015]
        except ValueError:
            idx = [i for i, w in enumerate(words) if norm(w["text"]) == norm(key)]
            if len(idx) > 1 and not val:
                off = [i for i in idx if i in found and abs(found[i][0] - words[i]["start"]) > tol]
                idx = off if len(off) == 1 else idx
        if len(idx) != 1:
            sys.exit(f"--move {item}: " + ("no word starts there" if not idx else "several words match (" +
                     ", ".join(f"{words[i]['start']:.2f}" for i in idx) + "): give its start time instead"))
        i = idx[0]
        if val:
            moves[i] = round(float(val), 3)
        elif i in found:
            moves[i] = found[i][0]
        else:
            sys.exit(f"--move {item}: no suggestion for '{words[i]['text'].strip()}': give the time ({key}=<s>)")
    return moves


def parse_window(text):
    lo, hi = (float(v) for v in text.split(","))
    if lo > 0 or hi < 0:
        sys.exit("--window is before,after in seconds around each start, e.g. -0.15,0.45")
    return lo, hi


def write(data, src, out):
    out = Path(out) if out else src
    if out.resolve() == src.resolve():
        raw = src.with_name(src.stem + ".raw.json")
        if not raw.exists():
            raw.write_text(src.read_text())
            print(f"original kept as {raw}")
    out.write_text(json.dumps(data, indent=2))
    print(f"wrote {out}")


def main():
    argv = sys.argv[1:]
    for i, v in enumerate(argv[:-1]):   # "--window -0.15,0.45" would read as an option
        if v == "--window":
            argv[i:i + 2] = [f"--window={argv[i + 1]}"]
            break
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcript")
    ap.add_argument("audio")
    ap.add_argument("--out", help="where to write (default: over the transcript, keeping <name>.raw.json once)")
    ap.add_argument("--window", default="-0.15,0.45", help="seconds before,after each start to look in")
    ap.add_argument("--check", action="store_true", help="report words whose start is off their sound; move nothing")
    ap.add_argument("--tol", type=float, default=0.1, help="--check: how far off a start may be (default 0.1 s)")
    ap.add_argument("--strip", metavar="OUT.png", help="--check: draw every flagged word over the sound")
    ap.add_argument("--words", action="append", metavar="W1,W2", help="--check: only these words (the ones that carry hits)")
    ap.add_argument("--all", action="store_true", help="--check: list and draw the less sure ones in full too")
    ap.add_argument("--move", action="append", metavar="WHICH[=TIME]",
                    help="move these words: a start time or a word takes the suggestion; =TIME sets your own")
    a = ap.parse_args(argv)
    src = Path(a.transcript)
    data = json.loads(src.read_text())
    words = data.get("words", []) if isinstance(data, dict) else data
    if not words:
        sys.exit(f"no words in {src}")
    x = decode(a.audio)

    if a.check:
        flags, found = check(words, x, a.tol)
        if a.words:                               # only the words that carry hits
            keys = {norm(k) for arg in a.words for k in arg.split(",") if k.strip()}
            picked = [i for i, w in enumerate(words) if norm(w["text"]) in keys]
            if not picked:
                sys.exit("--words: none of those words are in the transcript")
            off = {f[0]: f for f in flags}
            full = [off[i] for i in picked if i in off]
            print(f"CHECK  {len(picked)} words: off by more than {a.tol:.2f} s from where their sound starts? "
                  "(nothing moved)")
            for i in picked:
                w = words[i]
                if i in off:
                    _, start, t, how, sure = off[i]
                    print(f"  {start:6.2f} -> {t:6.2f}  {t - start:+.2f}  {w['text'].strip():16}  {HOW[how]}"
                          + ("" if sure else "  (less sure: look first)"))
                elif i in found:
                    print(f"  {w['start']:6.2f}  ok      {w['text'].strip():16}  sound at {found[i][0]:.2f}")
                else:
                    print(f"  {w['start']:6.2f}  ?       {w['text'].strip():16}  not paired with the sound: look on the strip")
            full += [(i, words[i]["start"], words[i]["start"], "vowel", False) for i in picked if i not in found]
            full.sort()
        else:
            full = [f for f in flags if f[4] or a.all]
            unsure = [f for f in flags if not f[4] and not a.all]
            print(f"CHECK  starts more than {a.tol:.2f} s from where the word's sound starts (nothing moved)")
            print("  start -> sound   shift  word              how")
            for i, start, t, how, sure in full:
                print(f"  {start:6.2f} -> {t:6.2f}  {t - start:+.2f}  {words[i]['text'].strip():16}  {HOW[how]}"
                      + ("" if sure else "  (less sure)"))
            if unsure:
                print(f"  less sure ({len(unsure)}: the syllables before them did not pair one to one with the "
                      "sound; --all lists and draws them):")
                line = "   "
                for i, start, t, how, sure in unsure:
                    item = f" {words[i]['text'].strip()} {start:.2f}->{t:.2f},"
                    if len(line) + len(item) > 110:
                        print(line)
                        line = "   "
                    line += item
                print(line.rstrip(","))
            print(f"{len(flags)} of {len(words)} words flagged ({len(unsure) if not a.all else sum(1 for f in flags if not f[4])} "
                  f"less sure); {len(words) - len(found)} could not be paired with the sound and were not checked.")
        if full:
            if a.strip:
                for p in check_strip(a.audio, words, full, a.strip):
                    print(f"strip: {p}")
            else:
                print("Look before moving: add --strip check.png to draw them.")
            print("Move the ones that are right: --move " + ",".join(f"{f[1]:.2f}" for f in full[:3])
                  + (",..." if len(full) > 3 else "") + " (takes the suggestion), or word=<time> for your own.")
        return

    if a.move:
        found = sound_starts(words, x)
        moves = parse_moves(a.move, words, found, a.tol)
        changed = set()
        for i, t in sorted(moves.items()):
            prev = words[i - 1]["start"] if i else -1e9
            nxt = words[i + 1]["start"] if i + 1 < len(words) else 1e9
            if not prev + GAP <= t:
                print(f"skipped {words[i]['text'].strip()}: {t:.3f} is not after the word before ({prev:.2f})")
                continue
            if t >= nxt and i + 1 not in moves:
                print(f"note: {words[i]['text'].strip()} at {t:.3f} passes the next word ({nxt:.2f}), which moves after it")
            print(f"{words[i]['start']:7.2f} -> {t:7.3f}  {t - words[i]['start']:+.2f}  {words[i]['text'].strip()}")
            words[i]["start"] = t
            changed.add(i)
        pushed = settle(words, changed)
        print(f"{len(changed)} moved" + (f"; pushed later to keep the order: {', '.join(pushed)}" if pushed else ""))
        write(data, src, a.out)
        return

    lo, hi = parse_window(a.window)
    found = pause_onsets(band_levels(x))
    moved, pushed = snap(words, found, lo, hi)
    for j, old in moved:
        new = words[j]["start"]
        print(f"{old:7.2f} -> {new:7.3f}  {new - old:+.2f}  {words[j]['text'].strip()}")
    print(f"{len(moved)} of {len(words)} words moved to the onset after a pause ({len(found)} pauses, window "
          f"{lo:+.2f}..{hi:+.2f} s)" + (f"; pushed later to keep the order: {', '.join(pushed)}" if pushed else ""))
    write(data, src, a.out)


if __name__ == "__main__":
    main()
