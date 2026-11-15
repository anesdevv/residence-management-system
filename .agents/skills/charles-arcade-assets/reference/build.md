# Building scenes in HyperFrames

A project is HTML: `index.html` mounts one scene file per beat (`compositions/<id>.html`), and HyperFrames
seeks a paused GSAP timeline frame by frame to render it. `tools/new_project.py` makes the project,
`tools/mount.py` writes the beat hosts from `beats.json`, and every scene uses the kit, loaded once by
`index.html`: `arcade.css/js` (tokens, surfaces, the core helpers), `motion.js` (camera, transitions, character
moves), `critter.css/js` (the code-drawn mascot and its props), `cast.css/js` (generated characters as actors, head
tiles, the loot bar), `ui-claude.css/js` and `ui-web.css/js` (rebuilt
apps), `annotate.css/js` (marker circles, notes, stamps, counters) and `dataviz.css/js` (charts).

## Blueprints

Tested scene files in `$T/blueprints/`, in four layouts: wide (`blueprints/wide/<name>.html`, laid out at
1280x630, for cards and landscape panels: width/height 1.3 or more), tall card (`blueprints/tallcard/<name>.html`,
1280x1550, the card that covers the face: 0.75 to 0.95), short (`blueprints/short/<name>.html`, 1080x960, for
frames in between) and tall (`blueprints/<name>.html`, 1080x1920). List one in `beats.json`
(`"blueprint": "arena-clash"`) and `mount.py` copies the layout that fits the project to `compositions/<id>.html`
with `SCENE` replaced by the id; when a blueprint has no version in that layout it copies the nearest one and
says so (re-lay it out). Then edit: the copy text, the images, and the `T` times at the top of the script. Each
file's header says what it is for and what to edit.

| Blueprint | Moment | World |
|---|---|---|
| `arena-clash` | two fighters step in, one strikes, flash, star, shake, the health bar drops | full-bleed pixel |
| `vs-select` | character select on a diagonal split; silhouettes light up on their names; VS slams | graphic |
| `title-card` | the cast on a sand mound in a white card; the name lands big | stage + card |
| `prop-reveal` | the literal object of the sentence drops into a pixel scene; the mascot reacts; one label | full-bleed pixel |
| `stat-hit` | a number counts up in a pixel panel with a stepped bar; the mascot reacts | stage + pixel panel |
| `chat-ui` | a rebuilt chat: question, answer, a phrase selected and marked doubtful, tool steps | stage + app |
| `claims-board` | a list judged row by row: pills flip, losers struck through, a result line | stage + app |
| `install-steps` | repo card, arrow, link + command typed into Claude, send, success toast | stage + app |
| `cta-follow` | Follow flips to Following, the keyword types into the comment box | stage + card |
| `ai-shot` | a generated video clip, trimmed, with exact HUD or text from code on top | full-bleed video |

The wide layout (1280x630, the 2:1 card) has its own set, built on the newer kit; each is documented in the
reference file named:

| Blueprint | Moment | Reference |
|---|---|---|
| `hook-gag` | the mascot yanks the plug, monitors die in a random stagger, an RIP stone slams down | critter.md |
| `title-card` | "It's called X": the costumed critter drops onto a sand mound, the name lands big | critter.md |
| `roster` | the lone host at work; on "N of them" the camera pulls back, N variants fill tiles, the chip counts to N; spotlight, promote | critter.md |
| `rpg-battle` | "N fixes": the problem is a monster with an HP box; each fix is a move, the hit lands, HP drains; the last one KOs it | critter.md |
| `crowd-signs` | a crowd raises paddles (AI, ?, X, a logo) one by one, pumps them; optional verdict flip and draining TRUST meter | critter.md |
| `lineup` | a police lineup: each thing named steps in with its placard on its word, camera flash | critter.md |
| `cta-follow` | the creator's card: Follow flips to Following, the keyword types in, a paper plane flies off on "I'll send it" | build.md |
| `zoom-through` | push onto a pixel monitor, through the screen into the live app, pull back with parallax | motion.md |
| `compare` | the mascot drags a before/after slider while a match counter climbs; a stamp lands | motion.md |
| `montage` | app cards stack with checks, then fan into a hand | motion.md |
| `claude-code` | a skill runs in the Claude Code terminal: tool lines, status, todos, bars | ui-claude.md |
| `claude-chat` | question, streaming answer, artifact, split view with a doc being written | ui-claude.md |
| `claude-home` | greeting, the prompt types, the cursor clicks send | ui-claude.md |
| `permission` | "Claude wants to use…": Allow once, the result takes its place | ui-claude.md |
| `browser-page` | a real page in Chrome: hover, click, navigation cut, push onto a field | ui-web.md |
| `github-repo` | the repo page complete on the cut; a FREE pill stamps on | ui-web.md |
| `phone-notify` | an iPhone lock screen; notifications slide in on their words and stack | ui-web.md |
| `insta` | select-all on a profile grid while the counter races, cut to the clone | ui-web.md |
| `data-table` | rows insert live, a row is clicked, the detail page scrolls to a red-boxed field | ui-web.md |
| `annotate` | numbered callouts take a page apart, a marker loop, a handwritten note, a sticky note | annotate.md |
| `chart` | bars grow and count; a line draws with the mascot riding its tip | annotate.md |
| `receipt` | a receipt prints, a pixel marker strikes each line, the total counts to $0.00, circled | annotate.md |
| `quest-map` | an overworld map of the N mistakes or steps: the route from START to the goal; per beat the player hops onto node N on "number N" with a giant N, the X marks cascade, "fix them" flips every X to a check, the chest opens at the end | ui-web.md |
| `setup-flow` | "paste this link into Claude and say install skill": the repo page readable from the cut, Code → copy → "Copied!", the link flies as a chip into Claude's input, "install skill" types, send, "Skill installed" with a push | ui-web.md |
| `tier-list` | a ranking: items (real covers, logos, emoji, a head tile) drop into their row with a stamp on the word; a head tile rockets from the bottom row to the top, rays, a crown | cast.md |
| `loot-bar` | an N-slot inventory: the found item flies into its slot on its word, k/N ticks, LOOT COMPLETE!; also a HUD for any scene (`AR.loot`) | cast.md |
| `book-reveal` | the real cover rises out of a pixel chest (or a glow) on its title; title and author plates land on the words; optional shelf, loot bar | cast.md |
| `author-card` | the credited photo (or their site) in a gold frame, the nameplate slams on the name, the credit stays readable | cast.md |

The blueprints that feature the host (title-card, roster, cta-follow, crowd-signs, rpg-battle, lineup, hook-gag,
loot-bar, book-reveal, author-card) take `HOST`: "critter" (the default), "pal", or a cast.py character's folder
in assets/cast ("charles"); a generated character acts with its poses (cast.md).

The tall-card layout (1280x1550, the card that covers the face) has its own set in `blueprints/tallcard/`:

| Blueprint | Moment | Reference |
|---|---|---|
| `quest-map` | the same map with the route climbing bottom to top; intro, hop, fix and goal beats | ui-web.md |
| `setup-flow` | the repo page on top and Claude's home below, both on screen the whole beat; the chip arcs down into the input; the success card at the end | ui-web.md |
| `title-card` | the name big at the top, the subtitle under it, the host dropping onto a sand mound below | critter.md |
| `cta-follow` | the creator's card across the top two thirds, the Follow button under the name, the keyword box full width, the host under the card | build.md |
| `crowd-signs` | a bigger crowd across the lower half, paddles over their heads, the meter on top | critter.md |
| `tier-list`, `loot-bar`, `book-reveal`, `author-card` | the wide scenes laid out for the tall card (title on top, author under the floor, rows of 250 px tiles) | cast.md |

quest-map and setup-flow have no 1080x1920 version; mount.py copies the tall-card one. Set `MAP.bottom` to 470
and the banner's top to 262 px, and keep setup-flow's two windows inside y 250-1450 (`work/kit-phone/full`
shows both).

Blueprints are starting points, not templates to fill blindly. Change layout, add a second prop, cut what the
beat does not need. For a moment no blueprint covers, write a custom scene from the skeleton below, using the
kit; a custom scene per video is normal (a cheat-code panel, a shelf of cartridges, an office, a lie detector).

## Timing

Scene time starts at 0 at the beat's start. For every key moment: `T.x = word.start - beat.start`, taken from
`transcript.json`. Entrances start 0.05-0.12 s before the word so they land on it. Beats are contiguous
(each starts where the previous ends) and hard cuts are the default between them. When a beat's timing
changes, edit `beats.json` and run `mount.py` again; scene files are never overwritten.

## The kit

`arcade.css` tokens and classes: `--stage --paper --ink --charcoal --muted --claude --gpt --gold --hp --hp-hurt
--ok --bad --select --marker`; `.stage` (cream grid background), `.card`, `.bg-art` (full-bleed image),
`.pixel` (crisp scaling), `.sprite` + `.pose[data-pose]` (+ `.on` for the first visible pose) + `.flip`,
`.px` / `.px-outline` (pixel font text), `.label` (dark mono pill), `.title-xl`, `.hud` + `.hp` (+ `.rtl`,
inner `<i>` fill, `<b>` hurt layer) + `.hud-icon`, `.banner` (+ `.center-x`), `.nameplate`, `.vs`, `.flash`,
`.spark`, `.panel-pixel`, `.num-xl`, `.app` + `.app-bar` + `.dots` + `.chat` + `.msg-user` + `.msg-ai` +
`.tool-row` + `.composer` + `.chip` + `.send` + `.greeting`, `.sel` (selection sweep), `.mark` (marker),
`.doubt` + `.squiggle` + `.q`, `.cursor`, `.pill .wait/.ok/.bad`, `.strike`, `.repo` + `.file`, `.badge`,
`.toast` + `.tick`. Fonts: Silkscreen (`.px`, `.banner`, `.nameplate`) and Press Start 2P (`.px2`, `.num-xl`,
`.vs`), plus HyperFrames' bundled Inter, JetBrains Mono, Space Mono and EB Garamond. Reach the pixel fonts only
through those classes: a scene style that names one in `font-family` fails `hf check` (its lint cannot see the
kit's `@font-face`).

`arcade.js` helpers. All take the timeline, a selector, and a scene time in seconds; all are seek-safe.

| Helper | Does |
|---|---|
| `AR.settle(tl, sel, t, {from, dy, dur})` | a beat's main surface on the cut: visible from its first frame, settles into place |
| `AR.pop(tl, sel, t, {from, dur, ease, fade})` | scale-up entrance with overshoot (`fade: false` keeps it opaque) |
| `AR.drop(tl, sel, t, {dy, dur})` | falls in and bounces |
| `AR.slide(tl, sel, t, {from: "left/right/top/bottom", dist, dur})` | fast slide-in |
| `AR.out(tl, sel, t, {kind: "shrink/fade/down"})` | exit |
| `AR.stagger(tl, sel, t, {gap, from, y})` | many elements pop in sequence |
| `AR.pose(tl, sprite, name, t)` / `AR.poses(tl, sprite, [[t, name], ...])` | swap a sprite's pose |
| `AR.walk(tl, sprite, t, dur, {x, fps, a, b, end})` | stepped walk cycle while moving |
| `AR.hop(tl, sel, t, {h, dur, base})` | jump with a landing squash; lands on `base` (default 0, where its CSS put it) |
| `AR.bob(tl, sel, t, dur, {fps, amp})` | stepped idle bob (characters only) |
| `AR.lunge(tl, sel, t, {dx})` / `AR.knockback(tl, sel, t, {dx, rot})` | strike and recoil |
| `AR.shake(tl, sel, t, {amp, dur})` | screen or object shake |
| `AR.flash(tl, sel, t)` / `AR.burst(tl, sel, t, {scale})` / `AR.stamp(tl, sel, t, {rot, from, dur})` | impact (a stamp lands at t + dur, 0.16 by default) |
| `AR.push(tl, sel, t, dur, {to, x, y})` / `AR.punch(tl, sel, t)` | camera move on a wrapper |
| `AR.names()` | fills every `[data-name="key"]` with `window.NAMES.key` and every `[data-fact="key"]` with `window.FACTS.key` from `assets/names.js`; first line of every scene |
| `AR.mountScreen(sel, quad, {scale, dx, dy})` | warps a live HTML element onto a screen cut out of a plate (`sprites.py screen` gives the quad: top-left, top-right, bottom-right, bottom-left in plate px; scale/dx/dy map plate px to the scene). Put the element behind the plate; it keeps its own width and height, so animate its children |
| `AR.type(tl, sel, t, {cps})` / `AR.typeDur(sel, cps)` | typewriter (plain-text elements only) |
| `AR.words(tl, sel, t, {gap, times})` | words land one by one; nested elements stay whole; a `.q` or `[data-own]` child keeps its own entrance |
| `AR.count(tl, sel, t, dur, {from, to, step})` | number counter |
| `AR.bar(tl, sel, t, dur, {from, to})` / `AR.steppedBar(...{steps})` | health, progress, power bars (scaleX) |
| `AR.sweep(tl, sel, t)` / `AR.marker(tl, sel, t)` | selection or marker highlight on `.sel` / `.mark` |
| `AR.draw(tl, pathSel, t)` | draws an SVG path with `pathLength="1"` and `stroke-dasharray: 1` |
| `AR.strike(tl, sel, t)` | strike-through line grows (a `.strike` stays hidden until struck) |
| `AR.cursor(tl, sel, t, dur, x, y)` / `AR.click(...)` / `AR.press(...)` | cursor moves, clicks, buttons press |
| `AR.scatter(tl, sel, t, {spread, dur, fade})` | pieces burst apart tumbling, then fade |
| `AR.swap(tl, outSel, inSel, t)` | blur swap of two elements on one stage |

## Custom scene skeleton

```html
<template>
  <style>
    #root { position: absolute; inset: 0; overflow: hidden; }
    #b05-cam { position: absolute; inset: 0; transform-origin: 50% 60%; }
    /* every id starts with the scene id */
  </style>
  <div id="root" data-composition-id="b05" data-width="1080" data-height="1920">
    <div id="b05-cam" data-layout-allow-overflow>
      <img class="bg-art pixel" src="assets/art/office.png" data-layout-ignore />
      <div class="sprite" id="b05-hero" style="left:120px; top:1050px; width:430px; height:358px">
        <img class="pose on" data-pose="idle" src="assets/cast/claude/poses/idle.png" />
        <img class="pose" data-pose="cheer" src="assets/cast/claude/poses/cheer.png" />
      </div>
    </div>
    <div class="flash" id="b05-flash" data-layout-ignore></div>
  </div>
  <script>
    const T = { hit: 0.62 };
    const tl = gsap.timeline({ paused: true });
    AR.names();
    // the world is on screen and still from the cut; the camera moves only on an event
    AR.poses(tl, "#b05-hero", [[T.hit, "cheer"]]);
    AR.hop(tl, "#b05-hero", T.hit, { h: 90 });
    AR.punch(tl, "#b05-cam", T.hit);                  // a punch-in on the hit
    window.__timelines["b05"] = tl;
  </script>
</template>
```

Place generated characters with `AR.cast.make` (cast.md): by their feet at a body height, from cast.json's
anchors. A raw `.sprite` box still works: keep the canvas aspect ratio from cast.json, height = width x canvas
height / canvas width.

## Names in one place

Every product name, skill name, handle and comment keyword the video shows lives in `assets/names.js`
(`window.NAMES = { skill: "Scout", keyword: "SCOUT" }`). In scenes, write `<span data-name="skill"></span>`
instead of the word; `AR.names()` fills them before anything types or splits the text. A wrong guess is then one
line in `names.js` and a re-render.

## HyperFrames rules that bite

- Ids: the host id in index.html, the scene's `data-composition-id` and the `window.__timelines[...]` key are
  the same. Every other id in a scene starts with the scene id (`#b05-hero`); ids are global on the page.
- Everything in a scene file sits inside `<template>`; style the scene root as `#root`.
- Seek-safe only: no `Date.now()`, `Math.random()` (use `AR.rnd(seed)`), timers, `repeat: -1`, network fetches,
  or `onUpdate` callbacks. Every visible state is a function of the timeline time.
- `fromTo()` paints its from-state from frame 0: right for entrances, wrong for effects that start visible.
  For a flash or squash: `tl.set(...)` at the moment, then `tl.to(...)` away (as `AR.flash` does).
- Never put a CSS `transform` on an element GSAP transforms; wrap it instead. Never tween `display` or
  `visibility`; use opacity.
- Camera moves tween a wrapper (`#id-cam`), never the scene root or a timed clip. A push and a shake never
  share an element: push `#id-cam`, shake `#id-shake` inside it (the arena and prop blueprints show it).
- The cut lands on a complete, locked frame: a beat's world (plate, card, app window) is visible and still on
  its first frame (`AR.settle` at 0); only the things inside it enter. A pop or fade-in from nothing at time 0
  flashes an empty stage between beats, and a settle or slow drift on every cut reads like a slideshow. Camera
  moves are events with a reason: `AR.zoomCut` cut-ins on the same plate, `AR.frame` pushes onto what fills or
  matters, pull-backs that reveal the whole app (the cast on its own unscaled layer), shakes on hits.
- Decorative full-frame layers (backgrounds, flashes, split shapes, connector arrows) get `data-layout-ignore`;
  camera wrappers that scale past the frame get `data-layout-allow-overflow`. Otherwise `check` reports them
  as covering the content.
- Asset paths are `assets/...` with no leading slash. A `<video>` is `class="clip"` with `data-start`,
  `data-duration`, `muted playsinline`.
- Text size is about what the phone shows (the asset's size times the scale charles-claude-editing shows it at: a 1280x630
  card shows at about 0.7). Key text, the thing the beat is about (a title, the number, the stamped word, the
  line the voice says), is 30 px or more on the phone (43 px or more in a 1280x630 card). Supporting UI text
  that should look real (a chat reply, table rows, file names) can be 18-22 px on the phone (26-30 px in the
  card); texture text (timestamps, sizes, chrome) down to about 12 px on the phone (18 px in the card). When the
  viewer must read something small, push the camera onto it (`AR.frame`). On 1080x1920 keep text between y 250
  and y 1450 and x 80-1000 (the platform UI covers the rest); in any other frame, inside the text area charles-claude-editing
  gives. Footage and art can fill the whole frame.
- Emoji render (Apple Color Emoji on this Mac). Use them when the emoji is the subject (the "rocket, sparkles,
  lightning" of an emoji feature grid); draw UI icons as inline SVG.
- An element that starts hidden is hidden in its CSS (`opacity: 0`) or by `fromTo`, not by
  `tl.set(..., {opacity: 0}, 0)`: a set at 0 does not apply on frame 0, and `hf check` flags it.
- CSS `filter` (blur, drop-shadow) and 3D transforms push frames onto the slower screenshot capture: a reel with
  them renders in 1-2.5 minutes instead of ~15 s. Use them where they matter, not on every element.
- Measure positions with offset chains relative to an element of the scene (`offsetLeft`/`offsetTop` up to the
  camera or layer), never `getBoundingClientRect` against the page: each scene's host sits stacked in document
  flow (scene N at y = frame height x (N-1)), so page-relative rects land off-screen in every scene after the
  first, while a one-scene snapshot looks fine. Test a helper that measures in a project with three scenes.
- A `fromTo` that only reveals opacity in its from-vars fails the cold-seek lint: repeat the opacity in the
  to-vars (`{opacity: 0}` → `{opacity: 1}`).
- Name only fonts that have an `@font-face` in the kit (`arcade.css`); a fallback font with no face, even after
  a comma, fails the lint.
- `AR.crit.crowd` keeps its rows and paddles in their own layer (`npcs.layer`): anything added to the same parent
  after the crowd sits in front of it; add an element before the crowd to keep it behind.
- Two tweens on the same property of one element must not overlap in time (a pop-in still running when a hide
  starts): a backward seek renders them in reverse order and the earlier one wins.
- `AR.frame` clamps the camera to the frame: to pan along something taller than the frame (a phone scrolled top
  to bottom), pass `clamp: false`.
- `hf preview` (the studio) writes attributes into every scene file it opens: don't open it on a project you are
  building, or strip what it added before rendering.
- `-webkit-text-stroke` draws broken outlines in the capture: outline text with a stacked `text-shadow` instead.
- A generated character's held props inside the "after" layer of `AR.compare` or `AR.wipeRide` don't render while
  the wipe runs: keep the character outside the wiped layer, or clear the wipe once it finishes.

## Commands

Run from the project folder; `npx --yes hyperframes@0.8.217 <cmd>` (the pinned version, written `hf` here).

| Need | Command |
|---|---|
| word timings | `hf transcribe assets/voice.m4a -d . --json`, then `.venv/bin/python $T/tools/onsets.py transcript.json assets/voice.m4a` (snaps the word after each pause to its sound), then `python3 $T/tools/words.py transcript.json` |
| word times inside phrases | `.venv/bin/python $T/tools/onsets.py transcript.json assets/voice.m4a --check --strip review/words.png` (every word more than 0.1 s off its sound, with the time; `--words a,b` only the hit words; moves nothing) |
| move confirmed words | `.venv/bin/python $T/tools/onsets.py transcript.json assets/voice.m4a --move paywall,27.68` (takes the suggestion) or `--move moment=29.22` (your own) |
| look at a hit | `python3 $T/tools/words.py transcript.json --strip review/w.png --from 27.3 --to 29.6` (spectrogram, waveform, each word's start) |
| assets at several sizes | `python3 $T/tools/new_project.py videos/<video>/graphics/<name> --set card:1280x630,tall:1280x1550,full:1080x1920 --duration <s>` (one project per size, one shared assets/; prints each render command) |
| lint + runtime + layout gate | `hf check --json` (fix every error; layout and craft warnings are advice) |
| look at moments | `hf snapshot --at 0.4,1.9,3.2 --no-end -o review/` (writes PNGs and `contact-sheet.jpg`) |
| one scene's frames | `hf snapshot --composition b05 --frames 6 -o review/b05` |
| full review set | `hf snapshot --review -o review/` |
| compare to a reference video | `hf snapshot --at ... --against ref.mp4 -o review/` |
| render a reel or an asset | `hf render -o out/<name>.mp4` |
| render an overlay with transparency | `hf render --format webm -o out/<name>.webm` (or `--format mov` for ProRes 4444) |

Renders are fast on this Mac (a 22 s reel took 13 s), snapshots and checks take 20-60 s; run renders in the
background anyway.
