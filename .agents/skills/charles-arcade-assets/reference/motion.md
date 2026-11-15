# Camera, transitions and motion (`motion.js`)

Every helper takes the timeline first and is seek-safe. Positions are measured once, when the scene builds, with
offset chains inside the scene, so give the boxes they measure explicit sizes. The working demo of every helper is
`work/kit-motion/` (`out/demo.mp4`, 12 fps strip `out/demo_best_12fps.jpg`; `compositions/k1`-`k14`, and `ft`, the
`AR.frame` precision test).

**Camera rule.** A beat cuts in complete and stays locked. The camera moves only for a reason: a cut-in to a closer
framing of the same plate (`AR.zoomCut`), a push onto content as it fills (`AR.frame`, about 1.45x in 0.25 s), a
pull-back that reveals the whole app (about 0.2 s, with the cast on a layer outside the camera so it stays full
size), a zoom-through, a shake on a hit. Nest a second camera inside a layer (`#app > #appcam`) for moves inside
the app.

| Helper | Does |
|---|---|
| `AR.frame(tl, cam, target, t, dur, {pad, fit, at, scale, max, clamp, ease, layers})` | moves and scales a camera wrapper so `target` (a selector, element or list: their combined box) fills the frame (the camera's parent) with `pad` px around it (number or [x, y]); `fit` contain/cover/width/height; `at` where the target's centre lands ([0.5, 0.5]); `scale` forces the zoom, `max` caps it; `clamp` (default on) never shows past the camera's world. Measures the resting layout box (entrances in progress ignored, static transforms kept), so frames chain exactly; zooms in log space. Ease power3.out up to 0.4 s, else power2.inOut |
| `AR.zoomCut(tl, cam, target, t, {pad, fit, at, scale})` | the same framing as a one-frame cut: a jump cut-in to a closer framing of the same plate |
| `AR.frameReset(tl, cam, t, dur, {ease})` | back to the camera's resting framing (for a pull-back reveal keep the cast on a layer outside the camera) |
| `AR.camLayers(tl, cam, [{sel, depth}])` | parallax layers that follow every move of this camera, including moves added earlier: depth 1 moves with it, above 1 nearer and faster, 0 still |
| `AR.zoomThrough(tl, {cam, screen, next, t, dur, dir, to, ease, layers, reveal})` | through a screen: `next` is a full-frame layer outside the camera (the app) that sits exactly on the `screen` box from the first frame. `dir: "in"` (0.4 s, power2.inOut) pushes until the screen fills the frame, so the app ends at its real size in one move; `"out"` (power3.out) pulls back from the app to `to` or the camera's rest, with `layers` in parallax; `reveal` fades `next` in or out. Pairs with green-screen plates (`sprites.py screen`, `AR.mountScreen`) |
| `AR.parallax(tl, [{sel, depth}], t, dur, {x, y, scale, origin, ease})` | moves layers without a camera: each pans x·depth, y·depth and zooms scale^depth about `origin` |
| `AR.toss(tl, sel, t, {from, to, fromAt, toAt, anchor, h, dur, spin, scale, squash, fade, show, gap})` | a parabolic arc with ballistic timing from `from` (a point in the element's parent, or an element; default where it is) to `to`, peaking `h` px above the higher end; `anchor` is the travelling point ([0.5, 1] = feet); `squash` lands with a squash, `fade` vanishes on landing (into a machine), `show` keeps it hidden until thrown |
| `AR.carry(tl, item, carrier, t, dur, {at, anchor, dx, dy, pick})` | an item follows a moving sprite: its `anchor` ([0.5, 1]) sits on the carrier's `at` point ([0.5, 0.2], the head); `pick` is the lift time; dropped items stay. Call after the carrier's moves |
| `AR.ride(tl, sel, path, t, dur, {ease, anchor, dx, dy, rotate})` | moves along an SVG path (or points) by arc length; with the same t, dur and ease as `AR.draw` it rides the tip of a drawing line; `rotate` follows its direction |
| `AR.flyToSlot(tl, sel, slots, t, dur, {arc, at, anchor, fit, gap, squash})` | each element hops along an arc into its slot (paired in order); `fit` scales to that share of the slot; `gap` staggers (0.035) |
| `AR.shrinkInto(tl, hero, slot, t, dur, {fit, at, ease})` | the hero shrinks into a slot, e.g. slot 1 of a grid (0.12 s, expo.out); then pop the variants with `AR.stagger(..., {gap: 0.035, dur: 0.16})` |
| `AR.spotlight(tl, items, chosen, t, {dim, outline, color, width, lift})` | the others dim to `dim` (0.28), the chosen gets a 4 px ring; `chosen` can be several elements (a tile and its sprite) |
| `AR.promote(tl, chosen, t, {size, scale, at, lift, dur, tile, dimTile})` | the chosen sprite hops out of its tile and scales toward the camera to `size` of the frame height (0.62), above the other tiles (its tile must not clip) |
| `AR.listPush(tl, list, items, t, {gap, dur, select})` | new items enter on top and push the list down, one every `gap` (0.17); `list` is the moving track inside a clipping viewport; `items` are the new rows already at its top, in arrival order; `select` is a class that moves to the newest row |
| `AR.fan(tl, cards, t, {spread, angle, scale, x, y, dur})` | a stacked deck opens into a hand on an arc to ±`spread` px and ±`angle`° |
| `AR.radial(tl, tiles, t, {from, dur, pop, fly, counter, start, prefix, suffix})` | tiles pop in by distance from the centre over `dur`, bursting into a mosaic; `counter` counts them as they land (×100) |
| `AR.flip3d(tl, sel, t, {axis, dur, deg})` | a 3D flip; faces are children with `data-face="front"` and `data-face="back"` |
| `AR.compare(tl, {before, after, handle, rider}, t, dur, {dir, from, to, ease, riderDx, counter: {sel, from, to, decimals, prefix, suffix}})` | a before/after wipe: `after` sits on `before` and shows on one side of the handle; the handle and the pushing sprite move with the wipe; `counter` climbs with an ease-out |
| `AR.explode(tl, layers, t, {gap, tilt, angle, scale, level})` | an isometric exploded view: the stack spins `angle` in its plane, tilts by `tilt`, the layers after the first lift `gap` px (`level: "one"` puts them on one level). No overflow or opacity on the stack |
| `AR.deck(tl, cards, t, {gap, step, tilt, check})` | stacked-cards montage: each card fades in 6% larger on top, older cards step back, each card's `check` pops |
| `AR.discard(tl, cards, t, {keep, gap, dir})` | cards grey out and fly off one by one, rotating, until `keep` (default the last) is left; top card first |
| `AR.scrollTo(tl, scroller, y, t, dur, {steps, offset})` | scrolls content inside its clipping parent to `y` px or an element; `steps` makes jump scrolls (Claude panes: `AR.clScroll`; web pages: `AR.pageTo`) |
| `AR.screensOff(tl, sel, t, {seed, span, crt})` / `AR.screensOn(...)` | screens go dark or light up one by one in a seeded random order across `span` (0.17); `crt` collapses each like an old monitor |
| `AR.dim(tl, sel, t, {to, dur})` | darkens a background under an overlay (brightness 0.45) |
| `AR.pushSwap(tl, out, in, t, {dir, dur})` / `AR.swipe(tl, out, in, t, {dir, gap})` | paired view push (0.17 s) / carousel swipe with a gap between cards (0.12 s) |
| `AR.wipeRide(tl, {before, after, bar, rider}, t, dur, {dir})` | a wipe turns `before` into `after` while a bar sweeps across (down, up, right, left) with the rider standing on its edge (the paint roller reskinning the app) |
| `AR.insert(tl, item, t, {dy, dur, clipAt, rider})` | slot insert: the item slides down `dy` behind the console's front layer (put that layer after it in the DOM), or below a line at `clipAt`; `rider` rides it down |
| `AR.povMask(tl, sel, t, {kind, dur})` | binoculars, keyhole or scope vignette over `sel`; cuts in complete, `dur` irises it open |
| `AR.beam(tl, {from, target}, t, {r, at, xray, xrayAt, off})` | a flashlight cone lights a spot on `target`; `xray` reveals a second layer through it (the cargo behind a door) |
| `AR.lens(tl, {lens, hidden}, t, {until, r})` | the hidden layer shows through a circle that follows a moving magnifier (call after the lens moves) |
| `AR.emit(tl, sel, t, dur, {rate, from, to, angle, spread, speed, gravity, life, scale, spin, stack, fade, seed})` | seek-safe particles cloned from a template: a ballistic spray (dust, coins out of a piggy bank) or, with `to`, arcs that pour into a target and pile up (`stack: {cols, step}`) |
| `AR.dealRows(tl, rows, t, {gap, rot})` | rows land tilted and see-through, then settle |
| `AR.swing(tl, sel, t, {deg, dur, swings, origin})` | pendulum swing about the pin at `origin`, settling (price tags, scale pans) |
| `AR.grow(tl, sel, t, dur, {from, steps, origin, cam, to})` | grows from its base; `steps` gives pixel stages; with `cam` the camera pulls back to `to` as it grows (a seed into a money tree) |
| `AR.tether(tl, a, b, t, dur, {at, sag, until, off})` | an SVG rope between two moving anchors, taut while pulling, sagging with a bounce after; call after the anchors' moves |
| `AR.rip(tl, sel, t, {teeth, fall})` | tears the element into two jagged halves that fall, rotating |
| `AR.recoil(tl, sel, t, {dx, rot, ticks})` / `AR.ticks(tl, at, t)` | a hit object jolts, overshoots and settles (repeats cleanly: a head-butt every 0.57 s) / white impact ticks |
| `AR.flyOut(tl, sel, tCut, {dir, speed})` / `AR.flyIn(tl, sel, t, {dir, speed, bounce})` | a gag across a cut: in shot A a prop leaves the frame finishing exactly on the cut; in shot B it enters from the same side and lands (same `speed` in both) |
| `AR.emote(tl, sprite, kind, t, {dur, size, at})` | a pixel reaction in a bubble inside the sprite (follows hops): "!", "?", "…", "heart", "anger", "sweat" |
| `AR.blink(tl, eyes, t)` | squashes eye elements shut for 0.1 s or switches to a `blink` pose and back (critters: `AR.crit.blink`) |

## Blueprints (wide, 1280x630)

| Blueprint | Moment | World |
|---|---|---|
| `zoom-through` | a pixel room with the live app on its monitor: push onto the monitor, through the screen, a push onto a detail in the app, then a pull-back into the room with parallax | pixel room + app |
| `compare` | the mascot drags a before/after slider while a match counter climbs, then a stamp lands | app |
| `montage` | app cards stack one by one with checks, then fan into a hand held by the mascot | card stage |

Pitfalls: GSAP does not tween clip-path strings that start from nothing (`inset(0px)`, a zero-width polygon), so
wipes tween a CSS variable inside a static clip-path. Scenes are `visibility: hidden` while they build: anything
copying computed styles must skip visibility. `carry`, `tether` and `lens` read the timeline when called, so they
come after the moves they follow. Emote bubbles scale with their sprite: after a big promote pass a smaller `size`.
