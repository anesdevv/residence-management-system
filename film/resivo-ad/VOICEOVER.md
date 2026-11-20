# Voice-over — ElevenLabs sheet

For the 20 s cut in `film.html`. One line per shot pocket, generated as separate
clips so each can be nudged to its timecode.

## 1. The script (paste into ElevenLabs, one clip per numbered line)

Model: **Eleven v3** (expressive). If you are on Multilingual v2, delete the
bracketed tags and keep only the punctuation — the pauses are written into it.

**L1 — 0.70 s** (shot 1, paper queue)
> [warm] Every September, the same queue.

**L2 — 3.15 s** (shot 2, the dripping tap)
> A tap. [pause] Still dripping.

**L3 — 5.30 s** (shot 2, the fix)
> One photo, and it's fixed.

**L4 — 6.75 s** (shot 3, the phone)
> One tap.

**L5 — 9.20 s** (shot 4, the console)
> The whole residence, on one screen.

**L6 — 11.95 s** (shot 4, roster / ticket)
> Every application checked. Every repair photographed.

**L7 — 14.60 s** (shot 5, the four cards)
> Live. [pause] Room by room.

**L8 — 17.25 s** (shot 6, end card)
> RÉSIVO. The residence, one tap away.

44 words, ~155 wpm across the 17 s of speech, with the pauses absorbing the
music hits at 2.02 s, 7.1 s and 16.88 s.

## 2. Settings

| Setting | Value | Why |
|---|---|---|
| Model | Eleven v3 | The two-beat lines ("One tap.") need sentence-level control. |
| Stability | 45–50 | Below 40 it drifts into a trailer voice; above 60 it goes flat. |
| Similarity | 75–80 | Enough character, still clean on S/Z. |
| Style | 0 | The script already carries the warmth; style exaggeration makes "queue" curdle. |
| Speaker boost | on | Keeps the low end on phone speakers. |
| Speed | 0.96 | The cut is 20 s; do not buy time by rushing the read. |
| Output | MP3 192 kbps / 44.1 kHz, or WAV if your plan allows | |

## 3. Voice to cast (or Voice Design prompt)

> A woman in her early thirties, warm and low-mid, speaking calm conversational
> English at a measured pace. A light North African French accent on the vowels —
> the sound of someone who works in an Algerian university residence and is not
> performing. Close, dry, no reverb, no smile in the voice. Documentary, not
> corporate.

A male read works too if you drop the pitch slightly and keep the same restraint.
Avoid: bright American "explainer" voices, anything with vibrato, anything that
sounds like a startup video.

## 4. Pronunciation

Add a pronunciation dictionary entry for **RÉSIVO** before generating, or the
model will say "reh-SEE-vo" on one line and "REH-zee-vo" on the next.

- Target: **RAY-zee-vo** — French é, stress on the first syllable.
- Respelling fallback if the API will not take IPA: `Rayzivo`.
- Confirm the official pronunciation with the team and lock it once — every line
  and every future asset should match.

## 5. Placing it in the film

1. Drop the eight clips on a new sound track in `film.html` at the timecodes above.
2. Duck the music under the lines by about 6 dB (the bed is already at −14.8 LUFS;
   the lines should sit at −16 LUFS, which is right for speech over music).
3. Re-render with `--loudness=-15` to keep the whole mix legal after the VO lands.
4. Keep the ping at 7.1 s and the whoosh at 16.88 s — they read as the app
   answering, and the VO pauses are cut around them on purpose.

## 6. What the voice must not say

No numbers that read as a product claim: no "thousands of students", no
"24 applications", no percentages, no time saved. The film's promise is
capability — verified, photographed, live — not scale.

## 7. French version (if you cut one)

Same timing, same restraint. Note that the tap pun works in both languages.

**L1** Chaque septembre, la même file d'attente.
**L2** Un robinet. [pause] Toujours là.
**L3** Une photo, et c'est réglé.
**L4** Un seul geste.
**L5** Toute la résidence, sur un écran.
**L6** Chaque dossier vérifié. Chaque réparation photographiée.
**L7** En direct. [pause] Chambre par chambre.
**L8** RÉSIVO. La résidence, à portée de main.

For the French read, cast a French or Algerian French voice, stability 50,
speed 0.95 — French needs slightly more room than English on the same cut.
