# RÉSIVO — "The same queue" · 20 s brand film

A 20-second advertising film for RÉSIVO, built as an OpenFilm project.
Every shot is a page, so each one can be trimmed, reordered or replaced in
Studio without touching the others.

Open it in Studio with `openfilm open` from this folder.

## Masters

| File | Frame | Rate | For |
|---|---|---|---|
| `resivo-ad.mp4` | 1920 × 1080 | 24 fps | YouTube, the site, presentations |
| `resivo-ad-vertical.mp4` | 1080 × 1920 | 24 fps | Reels, TikTok, Shorts |

```
openfilm render --fps 24                                    # → resivo-ad.mp4
# then set film.html's viewport to width=1080, height=1920
openfilm render --fps 24 --out resivo-ad-vertical.mp4       # → vertical
```

The mix sits at −14.8 LUFS integrated, −1.0 dBTP — right for online delivery.
`openfilm render --loudness=-16` re-levels the sound without touching the picture.

## The cut

| # | In | Out | Page | Beat |
|---|---|---|---|---|
| 1 | 0.0 | 3.0 | `shot1.html` | Paper wall, slow push-in, a stamp lands. "Every September, the same queue." |
| 2 | 3.0 | 6.0 | `shot2.html` | Macro in a dark basin: the stream, the bead, the drop, the rings. "Reported in September. Fixed in October." |
| 3 | 6.0 | 9.0 | `shot3.html` | The paperwork is drawn into a phone; teal blooms; the room turns light. "One tap." |
| 4 | 9.0 | 14.0 | `shot4.html` | The staff console: counters, roster-matched applications, occupancy, a ticket resolving. |
| 5 | 14.0 | 17.0 | `shot5.html` | Four 0.75 s cards: Verified / Photographed / Live / One console. |
| 6 | 17.0 | 20.0 | `shot6.html` | End card: logo, "The residence, one tap away.", the live address. |

Sound (all on tracks in `film.html`): a music bed from 0 s, a paper stamp at
2.02 s, a whoosh into the dark beat at 2.86 s, a notification ping at 7.1 s,
a whoosh into the end card at 16.88 s.

## Design notes

- **Three worlds, one grade.** Paper (shot 1, cool and desaturated), water and
  metal (shot 2, a dark basin lit by one window), screen (3–5, teal shadows,
  warm light), brand (6, navy → teal → green with gold hairline).
- **Shot 2 is a real macro, not a diagram.** The tap is cropped off the top edge:
  you see an aerator, a stream that pinches, a bead that falls and rings that
  spread on the water. The camera pushes in 1.02 → 1.10 across the shot.
- **Type.** Outfit 700 for display, Inter for UI. Overlines in tracked small caps,
  gold 4 px rule above every headline.
- **Colour** is the token set from `docs/DESIGN.md`: navy `#0A2F5A`,
  teal `#0D7180` / `#109D9A`, green `#0CA792`, gold `#E5A853`, canvas `#F5F8FB`.
  The brand gradient appears only on the end card.
- **The UI in shot 4 is drawn, not screenshotted.** It uses the real token
  values, the real roster names and card IDs from `official_students_roster.csv`,
  and the real navigation and status language — so it stays sharp at any size and
  can be re-cut without a re-record. Replace any block with a real screen
  recording if you prefer: keep the same window geometry (1320 × 924 at 520, 78).
- **Every frame is a pure function of `t`.** No CSS animations, no transitions,
  no autoplay: the picture is deterministic, which is what makes rendering and
  re-rendering safe.

## Re-framing to 9:16

Each page switches at `aspect-ratio < 1` and re-lays itself out: the headline
blocks move into the upper safe area, shot 4 puts its title on top and the
console at frame width beneath it, and shot 5 lifts its badge art above the
words. Nothing is cropped from the middle band.

To make the vertical cut: change `film.html`'s viewport to
`width=1080, height=1920`, render with `--out`, then change it back.

## Files

```
film.html        the cut, the tracks, the sound
shot1..6.html    one page per shot
theme.css        tokens, fonts, shared type
lib.js           easing and deterministic helpers
fonts/           Outfit + Inter (woff2, OFL)
assets/          logo (white), mark, music, three sound effects
```

Still manual, by design: the voice-over (write it against the cut, record,
drop it on a sound track under the music — the music is already at bed level),
and optionally real screen recordings to replace the drawn console.
