# Generated characters as actors (`cast.css`, `cast.js`)

A character made with `tools/cast.py` (pixel Charles from a photo, a goo monster, a rival) acts like the critter:
placed by its feet, flipped, posed, holding and wearing library props, talking in the critter's bubbles, hopping
with a ground shadow. cast.js reads `assets/cast/<name>/cast.json` once when a scene builds; its anchors (written
by `cast.py measure`, and by new/add/pose) say where each pose's feet, head top, face and hands are. A cast without
anchors logs a warning: run `.venv/bin/python $T/tools/cast.py measure assets/cast/<name>`. Open its `anchors.png`
before giving it hand props: when a hand dot sits inside the body (arms held against the torso fool the measure),
set that pose's hand points in cast.json by hand, and note them, because running `measure` again overwrites them. Working demo:
`work/kit-cast/` (`out/kit-cast.mp4`, `tall/out/kit-cast-tall.mp4`; `labs/remount.py` re-applies its edits).

Any blueprint that features the host takes `HOST`: "critter" (the default), "pal", or a cast folder ("charles").
Critter-only calls (`AR.crit.eyes`, `AR.crit.arms`) do nothing to an actor, and `AR.cast.act` does nothing to a
critter, so a blueprint calls both. Options in u (bob amp, hop h, knock dx) mean the same on both: an actor is 8u
tall for them. Props are sized in u where a head is 8u wide.

| Helper | Does |
|---|---|
| `AR.cast.make(parent, who, {id, x, y, h, pose, flip, face, poses, ground, hold, wear, role, z})` | an actor with its feet at (x, y), h px tall in its reference pose (head top to feet, 300); `face: "left"` or `flip` mirrors it (text and emotes stay readable); `ground: false` drops the shadow. Its box is the reference pose's pixels, feet on its bottom edge |
| `AR.cast.host(parent, HOST, o)` | the critter or pal (`AR.crit.make`) or an actor (h defaults to 9.5 × o.u) |
| `AR.cast.pose(tl, sel, t, name)` / `poses` / `act(tl, sel, t, what, {dur, back})` | switch poses; held props and hats follow the new pose's anchors. `act` takes a meaning and falls back to the nearest pose the cast has (cheer, sad, shock, point, talk, think, hurt, ko, attack, ready, taunt) |
| `AR.cast.flip(tl, sel, t, on)` | turn around on the word |
| `AR.cast.hold(sel, prop, {hand: "r" or "l", w, rot, dx, dy, text})` / `wear(sel, prop, {w, sink, slot})` / `role(sel, name)` | library props at the hand anchors; hats on the head anchor (`hat-*`, and the critter's crown, fedora, hardhat, cap, beret map to them); a role's props and hats (its drawn clothes are left off) |
| `AR.cast.dress` / `unwear` / `give` / `letgo` / `swing` / `photo` | as the critter's |
| `AR.cast.say` / `typing` / `emote` | the critter's bubble (tail above the head or hat; `dx`, `dy` px) and glyphs |
| `AR.cast.victory` / `hurt` / `ko` / `alive` / `walk` | cheer pose + hop; hurt pose + knockback; ko pose, props drop, stars; a stepped bob; walk_a/walk_b while moving (a cast with no walk poses hops along; `turn: true` faces the way it goes) |
| `AR.hop` `AR.bob` `AR.drop` `AR.walk` `AR.pose(s)` `AR.blink` `AR.emote` on an actor | move its body, the shadow stays on the floor (a hop from the idle pose shows its jump pose); any other target gets the helper as it was |
| `AR.cast.handAt(sel, side, pose)` / `headAt(sel, pose)` / `hand(host, side, state)` / `item(host, name)` / `items(host)` | positions in the parent's px (for ropes, cords, items held overhead), for a critter or an actor |
| `AR.cast.portrait(parent, who, {size, fill, top, pose})` | a head tile: the pose cropped to the head (tier lists, loot slots) |
| `AR.loot.bar(parent, {id, n, have, items, size, x, y, center, label})` / `fill(tl, bar, t, {slot, from, dur, scale})` / `call` / `complete` | the loot bar as a HUD in any scene: items in `FACTS.loot`, `have` the slots filled on the cut (per beat, or `FACTS.lootAt[sceneId]`); `fill` flies the next item in from an element or [x, y], the slot bumps and k/N ticks; the last one shows LOOT COMPLETE! |

## Blueprints (wide 1280x630; the same files lay themselves out for the tall card)

| Blueprint | Moment |
|---|---|
| `tier-list` | rows (GOD/S/A/B/C or your own); ranked items sit in their rows; each new one (a real cover, logo, emoji or head tile) drops in on its word with a squash, its row flashes and a stamp slams onto it; a head tile can rocket from the bottom row to the top with ghosts, rays and a crown; `CUT` cuts in on a row |
| `loot-bar` | the inventory big across the frame: the host holds up what it found (a generated character holds it beside its head), it flies into the next slot on its word, k/N ticks, LOOT COMPLETE! |
| `book-reveal` | a pixel chest drawn in code rattles and bursts open, the real cover rises out of it (or out of a glow on the floor) on its title with rays and sparkles, the title and author plates land on the words; it can fly onto a shelf or into the loot bar |
| `author-card` | a credited photo (or a capture of the person's site, `site: true`) in a hanging gold frame, the credit readable in its corner; the host points up; the nameplate slams on the name, with an optional line under it |

The tall-card copies in `blueprints/tallcard/` are the same files with a different header and root size: edit the
wide file and regenerate the tall copy, or the two drift apart.
