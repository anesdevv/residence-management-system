# Marks, stamps, counters and charts (`annotate.css/js`, `dataviz.css/js`)

The working demo of everything here is `work/kit-annotate/` (render `out/demo.mp4`, sheet `out/demo_sheet.jpg`);
copy markup from its `compositions/`.

## Annotations (`annotate.css`, `annotate.js`)

Tokens: `--an-red` (#ef3238), `--an-ink`, `--an-sticky` (#fce070), `--an-green`, `--an-blue`. Classes: `.an-hand`
(+`.ink`) red marker script (Caveat; reachable only through `.an-hand` / `.an-sticky`); `.an-sticky` (+`.pink`)
sticky note with a curled corner; `.an-num` tag + `.an-legend`; `.an-leader` (+`.ink`) leader label;
`.an-blueprint` / `.an-paper` surfaces; `.an-stamp` (+`.check` `.cross` `.red` `.sm`); `.an-tag` + `.an-logo`
luggage tag ("FEES · 106 of 341 bad reviews"); `.an-free`; `.an-check` / `.an-cross` / `.an-down` round badges;
`.an-pill` (`<span>` label + `<b>` value; +`.dark` `.red`); `.an-calc` + `.an-res`; `.an-verdict[data-v=drop|keep]` +
`.an-claim`; `.an-q`; `.an-pen` pixel marker.

Marks (loops, lines, arrows, callout boxes, "?") are drawn into an `.an-marks` box inside a layer: the scene root
by default, the nearest `.an-layer` ancestor if there is one (put that class on a camera wrapper so marks move
with a push), or `o.layer`. Geometry is measured once when the script runs, with offset chains. Stamps, stickies
and badges get `data-layout-ignore` automatically.

| Helper | Does |
|---|---|
| `AR.circle(tl, target, t, {color, width, pad, dur, seed, tilt, start, dir, over, sx, sy, pen, lift, layer})` | a red marker loop round an element in `dur` (0.3): irregular, tilted, egg-shaped, its tail crossing past the start. With `pen` the `.an-pen` rides the tip, then lifts off. A point box `[x,y,w,h]` needs `layer` |
| `AR.underline(tl, target, t, {at, color, width, dur, ext, tilt, bow, flick, pen, lift, layer, seed})` | hand-drawn underline; `at: "through"` is a strike-through; `ext` is px past the ends or `[left, right]`; `pen` rides it |
| `AR.arrow(tl, from, to, t, {bend, head, gap, color, width, dur, layer})` | hand-drawn curved arrow between elements or `[x, y]` points: the shaft draws, the head flicks on |
| `AR.scribble(tl, sel, t, {dur, cps, rot})` | `.an-hand` text written on left to right, word by word (70 cps: "Stanley's main factory" in 0.3 s), tilted -3° |
| `AR.sticky(tl, sel, t, {rot, from, dur, gap, times})` | sticky notes slapped on (from 1.22x, land in 0.11 s, squash); several land `gap` (0.3) apart |
| `AR.callouts(tl, boxes, legendRows, t, {gap, times, pad, start, color, layer})` | numbered red boxes round regions, each landing with its legend row, `gap` (0.09) apart |
| `AR.leaders(tl, [{label, at}], t, {gap, times, color, width, dot, cps, layer})` | a dot on the object, a thin line to the label, the label types on, 0.13 s apart. White on `.an-blueprint`; `color: "#2a2620"` with `.an-leader.ink` on paper |
| `AR.slam(tl, sel, t, {rot, from, dur, blur, spin, bump, gap, times})` | heavy stamp: 2.3x, see-through and blurred for two frames, lands at t + dur (0.1) turned `rot` (-8°) with a squash while `bump` (default its parent; `false` for none) bumps 3/4/3 px. A list lands `gap` (0.1) apart (a FILLED cascade). Position it with left/top, never a CSS transform |
| `AR.badge(tl, sel, t, {rot, dur, gap, times})` | a badge pops in with a twist (FREE, ✓, ✗, thumbs-down, pills, small stamps) |
| `AR.question(tl, target, t, {q, qdx, qdy, qDelay, ...underline})` | hand underline under a claim, then a red "?" pops at its end |
| `AR.calc(tl, sel, t, {rot, gap, result})` | an `.an-calc` bubble ("1.40 × 0.70 = 0.98") pops; its red `.an-res` lands `gap` (0.2) later |
| `AR.verdicts(tl, rows, t, {gap, times, verdict, claim, color, width})` | claims board: each row's `.an-verdict` flips from "Checking" every `gap` (0.13); dropped rows get a red strike across their `.an-claim` and dim |
| `AR.typeStrike(tl, sel, t, {cps, gap, dur, width, color})` | a price types on, then a red strike draws through it |
| `AR.fmt(n, {style, digits, compact, currency, prefix, suffix})` | en-US formatting: `int` "5,259", `usd` "$1,250.00" (digits 0: "$1,250"), `pct` 99.2 → "99.2%", `x` 100 → "×100", `dec`, `compact` "1.2M" (with usd: "$73M") |
| `AR.countTo(tl, sel, t, dur, {from, to, format, digits, ease, fps, steps, times, label, sep})` | stepped counter sampled at `fps` (15), or `steps` (`[0, 5, 50, 500, 5000]` or `{value, label}` objects such as "$73M · 2019 · CNBC") shown in turn; labels go to `label` (an element) or after the value |

## Charts (`dataviz.css`, `dataviz.js`)

`.dv` is a chart box (left/top/width/height in CSS; the size is read once), with `.dv-card`, `.dv-title`, `.dv-sub`,
`.dv-big`, `.dv-plotbg`, `.dv-ledger` and SVG text classes. Every chart returns a handle with its scales and the
elements it made.

| Helper | Does |
|---|---|
| `AR.bars(tl, sel, t, {data: [{label, value, color, format}], dir, max, format, dur, gap, ease, ticks, tickFormat, labelW, valueW, barH, barW})` | bars grow while their values count; `dir: "h"` labels left, values ride the bar ends; `"v"` values ride the tops |
| `AR.lineChart(tl, sel, t, dur, {data, color, width, area, ticks, yMin, yMax, tickFormat, axis, ease, dot, rider, riderDy, counter, counterFormat, levels})` | a line draws left to right; `rider` (a sprite) rides the tip; `counter` tracks the value under the tip |
| `AR.histogram(tl, sel, t, {bins, range, color, gap, stagger, ticks, tickFormat, markers: [{x, label, sub, color, t}], bracket: {from, to, t, label}})` | bars rise left to right, dashed markers drop in with two-line labels, a bracket draws under the axis |
| `AR.candles(tl, sel, t, {data: [[o,h,l,c]], slots, up, down, stagger, ticks, yMin, yMax, axis, range: {from, to, t}, levels, zones})` | candles, an opening-range box, level lines, shaded zones |
| levels `[{y, label, color, dash, t, tag, from, to, labelX, below}]` / zones `[{y0, y1, color, opacity, from, to, t}]` | (line, candles, pathFan) a level draws across with a bold label and a filled tag on the axis; a zone grows from the left |
| `AR.pathFan(tl, sel, t, dur, {n, steps, seed, start, vol, drift, target, stop, recolor, dots, counter, count, pin, ticks})` | seeded random walks fan out from a point; at `recolor` they turn green (hit target, with hit dots), red (hit stop) or grey |
| `AR.coins(tl, sel, t, dur, {data: [{value, label, kind: "coin"\|"cash", logo}], unit, max, cap: {value, label, t}, format})` | pixel coin stacks (or a cash stack) build while their values count under a dashed cap line; `.x(i)` and `.top[i]` on the handle place the mascot |

## Blueprints (wide, 1280x630; all cut in finished)

| Blueprint | Moment | World |
|---|---|---|
| `annotate` | numbered red boxes and a legend take a page apart; a marker loop circles the price; a handwritten note; a sticky note slaps on | stage + page |
| `chart` | bars grow with counting labels; hard cut to an analytics card where the line draws with the mascot riding its tip, the number tracks it, a goal line lands | stage + card |
| `receipt` | a receipt prints line by line in a pixel room, the total counts up; a pixel marker strikes each line as the total rolls down to $0.00, circled | pixel room + receipt |

Render notes: a 3D flip (rotationX) takes the whole render off fast capture, so flips use a flat scaleY;
`filter: drop-shadow` (stickies, the pen, receipt paper) sends those frames to slower screenshot capture (correct,
just slower). Marker strokes default to 6 px at 1280 wide (Jake's measure 6-8 px at this scale).
