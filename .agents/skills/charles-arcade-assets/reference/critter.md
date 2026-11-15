# The Claude critter and its props (`critter.css`, `critter.js`, `cast/props`)

The mascot viewers know, drawn in code: flat coral, square eyes, side nubs, four legs, no outline, a soft ground
shadow. Every role, expression and pose is exact and free, and it stays crisp at any size. Use it for every Claude
or AI-tool video. For any other topic the host is **the pal** (`shape: "pal"`): the critter's neutral cousin, a
round mint bun on two feet with oval eyes, a mouth, blush and stubby mitts, in the same 12u × 8u box. Every
helper, role, prop and wearable below works on it (wearables are refitted to its head and torso). Generated
characters (`tools/cast.py`) are actors with the same helpers (`cast.js`, reference/cast.md), and any blueprint's
`HOST` can be one. The working demos are `work/kit-critter/`
(`out/demo.mp4`, `out/demo_contact.jpg`) and `work/kit-iter/` (the pal, the new blueprints, the landing page
skins: `out/kit-iter.mp4`, `out/demo_sheet_1.jpg`); the props review sheets are `cast/props/review/review.png`
and `review_2.png`.

Markup: `<div class="critter" id="b01-crit" style="left:…; top:…; --u:16px"></div>`. The box is 12u × 8u with the
feet on its bottom edge. `--u` sets the size: 16 px is Jake's card scale at 1280x630 (about 15% of the card's
width), 26 a title card, 53 a close-up. Hats, coats, suits and eyewear are drawn on the critter's own grid, so
they fit exactly and stay sharp in a close-up.

| Helper | Does |
|---|---|
| `AR.critter(sel, {shape, color, eyes, arms, hold, wear, role, ground, u})` | renders into each `.critter`. `shape: "pal"` (or `data-shape="pal"`) draws the pal; its default colour is mint #45BFA0 and its shade, shine and blush follow `color`; `AR.crit.SHAPES.pal` gives its anatomy points. `color`: coral teal purple blue green gold pink grey black navy red, or any CSS colour (another company's agent; Claude's own sessions and roles stay coral and differ by props). `hold: ["magnifier", "clipboard"]` fills the right hand then the left (`[name, {rot, w, dx, dy, text}]` allowed). `ground: false` drops the shadow |
| `AR.crit.make(parent, {id, x, y, u, …})` | creates a critter with its feet centre at (x, y) |
| `AR.crit.eyes(tl, sel, t, kind)` | normal, happy (^^), closed, x, wide, look-left, look-right, look-up, look-down, sad, angry, squeeze (><) |
| `AR.crit.blink(tl, sel, t, {dur, back})` / `AR.crit.alive(tl, sel, t, dur, {seed, bob, amp})` | one blink / seeded blinks every 1.3-2.4 s plus a stepped bob (call `alive` last) |
| `AR.crit.arms(tl, sel, t, kind, {dur, fps, end})` | down (the nubs), up, point, point-left, out, hold-up, limp; `wave` for `dur`; held props follow the hand |
| `AR.crit.walk(tl, sel, t, dur, {x, y, fps, ease, look})` | leg-swap walk that moves the whole critter, eyes looking the way it goes |
| `AR.crit.color(tl, sel, t, color)` / `AR.crit.pose(tl, sel, t, name)` | recolour on the word / the sprite pose names (idle cheer sad point think shock talk jump fight_*) as critter states |
| `AR.hop` `AR.bob` `AR.drop` `AR.walk` `AR.pose(s)` `AR.blink` on a critter | move its body while the ground shadow stays on the floor and shrinks under a hop; any other target gets the original helper unchanged (`AR.<name>.__orig`) |
| `AR.crit.hold(sel, prop, {hand, rot, w, dx, dy})` / `AR.crit.wear(sel, prop, {slot, at, w, colors})` | a prop in a hand / a wearable on (setup, not timed) |
| `AR.crit.role(sel, name)` | a whole costume from `AR.crit.ROLES`: detective scout spy closer trader analyst builder architect designer painter qa engineer accountant banker planner coach researcher writer marketer champion knight guard launcher shopper navigator judge labeler timekeeper newsie operator support barista developer gardener digger drafter mascot filer king receptionist lawyer referee photographer colorist courier monster (purple with horns: give it angry eyes) |
| `AR.crit.dress(tl, sel, prop, t, {dur, from, rot, stretch, hand})` | costume drop on the word: the item falls and lands at t with a squash; head, ear and face items squash first and stretch up into them; also re-wears an item taken off |
| `AR.crit.unwear(tl, sel, prop, t, {to, dist, spin, fade})` | an item flies off (up, left, right, down) and hovers there until dressed again (the sunglasses gag across a cut) |
| `AR.crit.letgo(tl, sel, prop, t)` / `AR.crit.give(tl, sel, prop, t)` | a held prop drops to the floor / pops into the hand |
| `AR.crit.pull(tl, sel, t, dur, {dir, n, hold})` | hauls a rope: leans back, squeezed eyes, tugs in steps; tie the rope with `AR.tether` to `.crit-hand[data-hand="r"]` |
| `AR.crit.block` / `ko` / `victory` (tl, sel, t, o) | shield swings in front, crouch, pushed back / X eyes, knocked back, held props drop, stars / arms and props up, happy eyes, hop |
| `AR.crit.sink(tl, sel, t, dur, {depth})` | sinks into a spreading mud puddle (stuck), arms flailing, sweat drop |
| `AR.crit.dig` / `water` / `lookout` / `sweep` / `paint` / `flourish` (tl, sel, t, dur, o) | shovel thrusts with dirt / can tilts and drips / binoculars up, scanning / magnifier sweeps `dx` u / brush dabs colour onto an easel / pen loops a signature while the ink draws (`{prop, x, y}`) |
| `AR.crit.flip(tl, sel, t, {h})` / `AR.crit.swing(tl, sel, t, {n})` / `AR.crit.trace(tl, sel, t, dur, {path})` | coin tossed and caught / a held tool winds up and strikes / rides a giant pencil along a `pathLength="1"` path as it draws |
| `AR.crit.say(tl, sel, t, text, {dur, side, size, typing, x, y})` / `AR.crit.typing(tl, sel, t, dur)` | tailed pixel speech bubble in mixed-case pixel text (`.pxt`), above any hat; `typing` shows "…" first |
| `AR.crit.emote(tl, sel, t, kind, {dur})` | a bare pixel glyph over the head: ! ? sweat heart spark stars anger (`AR.emote` draws one inside a bubble) |
| `AR.crit.lineup(parent, {x, y, sizes, gap})` | the same critter at several sizes on one baseline (model tiers) |
| `AR.crit.perch(sel, card, {at, edge, peek})` / `AR.crit.pin(tl, cast, cam, t, dur, {to, x, y})` | stand on, or peek up over, a card's edge / pull the camera back while the cast stays pinned to that edge at full size (don't mix `pin` with `AR.frame` on one camera) |
| `AR.crit.crowd(parent, {x, y, w, h, n, rows, seed})` | the chibi NPC crowd for "most people…"; add `AR.emote(…, "?")` over them. It returns their boxes and sits in its own layer (`npcs.layer`), so UI added to the parent later is in front of it |
| `AR.crit.signs(npcs, {text, back, color, backColor, bg, w, tilt, seed, id})` | paddles behind the heads of a crowd, hidden until raised, returned left to right. `text`: "AI", "?", "10", "X" (a red X), `{img: src}` (a logo), or an array with one per person; `back` is the face `turnSigns` flips to |
| `AR.crit.raise(tl, signs, t, {gap, dur, order})` / `AR.crit.pump(tl, signs, t, dur, {n, amp, npcs, hop})` / `AR.crit.turnSigns(tl, signs, t, {gap})` | the paddles go up one by one, 0.045 s apart / everyone pumps them (with `npcs`, the crowd hops on each pump) / every board flips to its back face |
| `AR.crit.blow(tl, sel, t, dur, {prop, n, color, lines, out})` | blows a whistle: up to the mouth just before t, cheeks puff, eyes squeeze, sound lines burst out `n` times (2) over `dur` (0.5); attaches the whistle if not held |
| `AR.crit.photo(tl, sel, t, {prop, flash, peak, hold})` | takes a photo: the camera comes up to the eyes, a white pixel star bursts at its flash on t, and `flash` (a `.flash` element) flashes the scene; down after `hold` (0.35) |
| `AR.crit.put(parent, name, {x, y, w, u, anchor, text, flip, id})` | a library prop standing on its own in a scene (its anchor, else its bottom centre, at x, y; `w` px or `u` × its width); returns the element for `AR.drop`, `AR.stamp`, `AR.toss`. Throw into a bin with `AR.toss(tl, el, t, {to: can, toAt: AR.crit.PROPS.trashcan.mouth, fade: true})` |
| `text` on `hold` / `wear` / `put` | a prop with a blank face (`label` in props.json) shows text there, mirrored with the prop; the stop sign defaults to STOP |
| `AR.crit.prop(name, {src, size, w, grip, slot})` / `AR.crit.handAt(sel, side)` | register a new prop for the page / a hand's position for ropes and cords |

**Props** (`assets/cast/props`, copied into every project; grip points, sizes and tips in `props.json`, mirrored in
`critter.js`):
- Hand props (generated): magnifier binoculars clipboard flashlight newspaper briefcase phone hammer wrench shovel
  blueprint pencil roller moneybag coin bill calculator chartboard stopwatch scales folder chartscroll filebox
  scroll quill pen labelgun laptop whistle megaphone trophy target rocket bell brush wateringcan sapling
  shoppingbag map pushpin bugnet shield sword clock mug marker headphones camera paintbucket paintchips (a fan)
  stopsign (labelled) paperplane envelope redcard yellowcard; `hat-*` (generated hats, as objects).
- Placed or worn: easel (on the ground), trashcan (on the ground, with a `mouth` for things thrown in), badge (on
  the chest).
- Drawn in code (wearables): coat suit vest shirt refshirt fedora hardhat hardhat-white cap beret crown visor
  headset earpiece sunglasses goldshades glasses goggles horns.
- A prop the library lacks: generate one sheet of up to eight in the prop style (art.md), slice it, and register
  it on the page with `AR.crit.prop()`.

## Blueprints (wide, 1280x630)

| Blueprint | Moment | World |
|---|---|---|
| `hook-gag` | the mascot yanks the plug, six live monitors die in a random stagger, the lights go out, an RIP stone slams down with dust and a shake | pixel room drawn in code; `HOST` (a generated character reaches out with the plug in its point pose, and the outlet is drawn where the plug is) |
| `title-card` | "It's called X": the costumed critter drops onto a sand mound, one more costume piece drops on "called", the name lands big; the subtitle is on screen from the cut | white card |
| `roster` | the lone host fills about a third of the frame's height, doing its job (an action from its prop) during a slow push, with a "1 SKILL" chip. On "N of them" the camera pulls back, the host shrinks into a line-up as the variants pop in and the chip counts to "N SKILLS"; tiles rise, the critters hop in, labels hold at least 0.7 s (it warns in the console when they can't); spotlight, then promote. Picks the column count that gives the biggest critters with labels of at least 28 px (40 px in a tall frame) per 1280 px; 2-12 roles at any size. `HOST`: "critter", "pal", or a cast.py character (its variants hold the role's props and wear its hats) | stage + tiles |
| `rpg-battle` | "N fixes": the problem is a monster (a horned pal, or a cast.py character: `MONSTER.cast: "slop"`; `HOST` is the hero) with name, Lv and HP box. On each word the menu cursor picks the move, "X used Y!", the host dashes in and hits, flash and shake, HP drains, SUPER EFFECTIVE!; the last move KOs it. `ROUNDS` picks the rounds a beat plays; HP and struck-out moves carry over between beats | grass arena |
| `crowd-signs` | "everyone can tell": the NPC crowd raises paddles (AI, ?, X, 10, a logo) one by one on the word, then pumps them; the host sweats. Optional verdict flip (`SIGNS.back`, `T.turn`) and a TRUST meter that drains (`METER`, `T.drain`) | stage |
| `lineup` | a list said fast: a police lineup with a height chart. On each word a cut-in on the next spot, the suspect (emoji, image, critter, pal, or a cast.py character: `cast: "mrno"`) steps in with its placard, camera flash; then the wide lineup and the photographer's flash | lineup wall |
