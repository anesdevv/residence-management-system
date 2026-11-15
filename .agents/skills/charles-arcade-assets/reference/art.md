# Making the art

All art comes from `tools/fal.py` (Nano Banana Pro for images, MiniMax / Kling / Gemini for video) and is
cleaned with `tools/sprites.py`. Code draws everything that must be exact: text, numbers, health bars, UI.
Generated images never carry text that matters.

Commands are written out in full (zsh does not split a command stored in a variable): `fal.py` runs on the
system `python3`, `sprites.py` on the repo venv (`.venv/bin/python`, see SKILL.md setup).

## One look, every time

Every prompt starts with the same style block so the whole video matches. Copy them exactly.

**Scene plates** (full-bleed backgrounds, 9:16, `--res 2K`):

> Vertical 9:16 background plate for a short-form video. Crisp retro 16-bit pixel art, cute and playful
> indie-game look, clean hard pixel edges, limited warm palette, soft pixel shading. No characters, no people
> in the foreground, no text, no UI, no HUD, no logos. ⟨the place, its light, what fills the top half⟩. The
> ⟨floor⟩ fills the lower half and stays empty as a stage for the characters.

Small crowds, stands or shelves in the far background are fine; anything in the foreground fights the sprites.
For a shorter frame, match its shape and say "Wide background plate" instead of "Vertical 9:16 background
plate": `--aspect 5:4` for 1080x960, `4:3` for 1080x768, `1:1` for a square, `16:9` for landscape. The 2:1
card (1280x630) has no exact aspect: use `21:9` (or `16:9`) and let `.bg-art` cover-crop it, so keep what
matters in the middle 70%. A tall card (1280x1550) uses `4:5`.

**Plates with screens** (monitors, a TV, a phone in the scene): ask for the screens as "a perfectly flat solid
#00FF00 bright green rectangle, with no reflections, no content and no bezel glare". Then
`.venv/bin/python $T/tools/sprites.py screen raw.png assets/art/<name>.png` cuts the screens out and prints each
one's rect and corners (also in `<name>.screens.json`). In the scene, put the live UI (a rebuilt app, a chart, a
captured page) behind the plate and fit it to a screen with `AR.mountScreen` (build.md), so the app plays inside
the pixel monitor, angled monitors included, and the camera can push into it.

**Props and objects** (an item that drops in, a crate, a chest, a console; 1:1, `--res 2K`):

> Crisp 16-bit pixel art sprite, clean hard pixel edges, no anti-aliasing blur, limited flat palette, a 1-2
> pixel dark outline, flat lighting with one small highlight. A single ⟨object⟩, centered, on a perfectly flat
> solid magenta #FF00FF background. No floor, no ground line, no shadow, no text, no border.

Then `.venv/bin/python $T/tools/sprites.py key raw.png assets/art/<name>.png`: it removes the magenta
backdrop (with its haze and ghost copies) and anything close to pure magenta, keeps darker shading inside the
outline, and trims. It also pulls leftover screen colour out of the cut edge (no green or pink rim). It drops dust
and the bits a ghost copy leaves in the haze, but keeps parts drawn on the clean screen, such as a held prop or
flying drops. `--min-part 0.0005` is the share of the biggest shape below which a separate bit counts as dust; 0
keeps them. For `slice`, one pose short still slices and names the missing pose; `--rows 2` handles grids. For a
prop with a visible label
(a version number on a crate, a price tag), leave the label blank in the prompt and put the text on it in HTML.
Objects that are pink or purple: use `--screen green` and a #00FF00 background instead.

**Never in generated images:** words that matter, numbers, logos, UI, health bars. Image models misspell and
duplicate them; HTML gets them exact and animatable.

## The cast

**The Claude critter is drawn in code** (`critter.js`, build.md): flat coral, square eyes, side nubs, four legs,
no outline, exactly the mascot viewers know. Its roles come from props it holds or wears (the props library
below), its expressions and limbs are timeline states, and recolours are free, so it needs no generated images.
Use it for every Claude or AI-tool video.

**Generated characters** live in `cast/<name>/`: `ref.png` (keyed), `ref_raw.png` (on magenta, the reference to
pass to the image model), `poses/*.png` (all on one canvas, feet aligned, same scale), `cast.json` and
`review.png`.

| Character | Is | Poses |
|---|---|---|
| `claude` | the outlined, shaded sprite version of the critter (for scenes that mix it with generated characters) | idle, walk_a, walk_b, jump, cheer, sad, fight_ready, fight_attack, fight_hurt, fight_victory, point, think, shock, talk |
| `gpt` | a chubby blue robot with a puffy cloud head and a visor face `>_` (stands for ChatGPT) | the same fourteen |

The fight_* poses hold a sword and shield. Sprites face right in fight poses except `gpt`, which faces left;
mirror a sprite with an inner `<div class="flip">` around its poses, never with a transform on the `.sprite`.

**A character for the topic** (Slop the goo monster, a crowned marketer, a rival product, Charles as a pixel
character), in one command, about $0.45 ($0.60 when a sheet has to be redrawn):

```bash
.venv/bin/python $T/tools/cast.py new videos/<video>/graphics/x/assets/cast/slop --type creature --desc "a gooey purple-grey slime blob monster with two mismatched sparkle eyes, dripping glossy violet gradient goo" --screen green
.venv/bin/python $T/tools/cast.py new videos/<video>/graphics/x/assets/cast/charles --photo charles.jpg --desc "wearing a black t-shirt"
.venv/bin/python $T/tools/cast.py new videos/<video>/graphics/x/assets/cast/teal --like $T/cast/gpt --desc "recoloured teal"
```

It draws the reference, the `base` and `act` pose sheets (idle, walk_a, walk_b, jump, cheer, sad; point, think,
shock, talk), keys and slices them, and puts every pose at one body size on one canvas. Add `--sets base,act,fight`
for sword-and-shield poses. Purple or pink characters need `--screen green`. When the model keeps changing
something it must not (a mouth on a character without one), say so with `--note "..."`: it goes into every
prompt. Open `review.png`; redraw a bad set by deleting its sheet and running again.

`--type` picks the pose sets:
- `humanoid` (default) draws `base` and `act`.
- `creature` is for anything that doesn't walk or hold things (a blob, a ghost, a worm). It draws idle, cheer,
  taunt, hurt, ko and sad as a 2x3 grid, about $0.30.
- `object` is for a thing that acts (a coin, a page). It draws idle, bounce, squash and shine as a 2x2 grid.

cast.json and an idle pose from the reference exist as soon as the reference is drawn. A sheet that won't slice
(two or more poses missing, an extra pose, poses out of their row, a ghost copy) is drawn once more. A set that
fails again is named in a FAILED line, with a `cast.py pose` command for each missing pose, and the command exits 1.
cast.json remembers the screen, type and note, so `add` and `pose` reuse them.

Every pose records its anchors in cast.json: feet, head top, face, both hands and the head's width, plus the
reference pose's standing height (`height`). cast.js places the character by them (reference/cast.md). Poses are
sized by matching the reference pose's head, so a mallet held overhead or a sack never shrinks the body, and set
on the shared canvas by their feet; a pose too big for the canvas grows the canvas for every pose (padded, never
shrunk). Open `anchors.png` (dots on the head top, face, hands and feet of every pose) next to `review.png`.
A cast made before, or with poses edited by hand: `.venv/bin/python $T/tools/cast.py measure <castdir> [...]`
(no fal calls, about a second a pose). It also refits from `extra/` any pose whose whole body came out another
size; `--no-refit` only measures. A pose drawn with other proportions (a bigger head, a crouch) is flagged
"unsure" and left as drawn; its anchors are approximate.

**A pose a beat needs that does not exist** (holding a magnifying glass, wearing a miner helmet, sitting at a
desk): `.venv/bin/python $T/tools/cast.py pose <castdir> --name detective --desc "wearing small round black
glasses and holding a magnifying glass"`. It is fitted to the reference pose's head size and placed by its feet (the canvas grows when a prop needs
room), so it swaps with
the other poses without jumping. `cast.py add <castdir> --sets act` draws a whole missing set. A creature's or
object's pose keeps the reference's scale. If it warns about a ghost copy or glow, delete
`extra/<name>_raw.png` and run it again.

**Props** (`cast/props`, copied into every project as `assets/cast/props`): flat pixel props for the mascot's
roles (magnifier, hard hat, hammer, bug net, briefcase, binoculars, stopwatch, newspaper, visor, calculator,
goggles, clock, shield, phone, bell, marker, clipboard, headset, fedora, coat, crown, trophy, megaphone, laptop,
mug, rocket, roller, wrench, chart board, money bag, coin, bill, sword), each with its grip point in
`props.json`. A prop the library lacks: one image of up to six props in a row, keyed and sliced (the prop block
above, `sprites.py slice`).

## Real things

Show the real thing instead of drawing it (`tools/source.py`): `page <url>` captures the live site at 2x
(`--full` for a scroll, `--dark`, `--crop`), `app "<name>"` the App Store icon, `site <domain>` the site icon,
`logo <slug>` a one-colour brand mark, `book "<title>" --author "<name>"` the cover, `person "<name>"` a photo of
a person, `photo "<search>"` a freely licensed photo of anything else from Wikimedia Commons with its credit line.
Open each one: a login wall, a cookie banner or the wrong app means another source. Never generate a real person
or a real logo.

**Books.** `book` sizes the cover of every English edition on Open Library and takes Google Books' largest image,
then keeps the biggest real one, preferring publisher images and the edition Open Library shows over library
scans. It prints the size (Influence 1578x2400, $100M Offers 1536x2400) and the other candidates: a barcode
sticker, another edition's design or a summary book means `--pick N`. Always pass `--author`.

**People.** `person "<name>"` takes the photo Wikidata lists for them on Commons, else a Commons file named after
them, and writes its credit line to `<out>.credit.txt` ("Photo: Viktorbuehler, CC BY-SA 3.0"). Most creators have
none, and it says so: then `--site <url>` captures their portrait from their own page (an about page, their
newsletter, their YouTube channel) as the image file itself at its largest, credited to the site ("Photo:
acquisition.com"). It lists the images it found; `--pick N` takes another when the first is a logo, a book or
someone else. Make sure the page is theirs: alexhormozi.com is a parked domain (his is
acquisition.com/about-alex-hormozi-acquisition). Show the credit small in the photo's corner. Under 400 px (a
48 px avatar), find a bigger one.

**An app's own screens** (a sign-up wall, a permission prompt, a paywall, a lesson): `source.py` can't capture
inside an app. `source.py screens "<app>" --out assets/ref/<app>/` saves its App Store screenshots at full size
(1242x2688) as references: rebuild the screen exactly with the UI kit from them (layout, copy, colours), with the
real icon and name. They are Apple marketing shots (captions, device frames, staged data), so they never go on
screen. Other references: a screen recording the creator gives you, or the system's own dialog (iOS alerts have
exact wording); never from memory. Without a reference, keep the screen generic and put an invented app's name on
it, not the real one's.

## Checking art before using it

Open every generated image. Regenerate (same prompt, `--force`, at most twice) when you see: text or letters,
a second copy of the subject, a drawn floor or shadow under a prop, extra limbs, a character off-model (wrong
colour, wrong shape, eyes moved), mush instead of crisp pixels, or a busy foreground where sprites must stand.
When it drew the wrong thing (a strawberry that reads as a tomato), a retry rarely fixes it: rewrite the prompt
with what makes the object recognisable (seeds on the skin, a leafy green top, the shape).
Put the keyed sprites on one review sheet, `.venv/bin/python $T/tools/sprites.py sheet review.png a.png b.png ...`,
and open it: it is flat teal so a hole or a speck left by the key shows. If keying ate part of an object, or a
pink or purple object went with the backdrop, use `python3 $T/tools/fal.py rmbg --image raw.png --out cut.png`
(then `sprites.py trim`) or regenerate on `--screen green` (#00FF00).

## Video (hero moments only)

A generated clip is worth it when the motion itself is the point and code cannot fake it: a real sword fight, a
crowd going wild, a world turning, a creature transforming. At most one or two per 30 s; everything else is
code animating stills, which lands exactly on the words.

1. Build the still first: the scene plate with the cast composited into it, or generate the full scene image
   with the cast (pass both `ref_raw.png` files as `--ref`). No text, no HUD in the still.
2. `python3 $T/tools/fal.py video --image still.png --prompt "..." --model minimax --duration 5 --out assets/clips/<name>.mp4`
   - `minimax` (H3 Max): fast (~15 s), cheap (~$0.16), the most dynamic action. Default.
   - `kling` (Kling 4): pass `--end end_frame.png` to land on an exact final pose; slowest (~3-4 min), ~$0.80.
   - `gemini` (Omni Flash): 8 s, ~$0.24; tends to idle for the first 2-3 s.
   Prompt the action plainly, then: "Keep crisp 16-bit pixel art with hard pixel edges, keep both character
   designs exactly the same, keep the camera steady. No text, no HUD, no health bars."
3. Watch it (`ffmpeg ... -vf fps=4,tile=...`). Reject identity drift, melted limbs, new characters, text. Pick
   the best 1-2.5 s and play only that (`data-media-start` in the ai-shot blueprint). The clip stays muted.

## Costs (October 2026)

Image or edit $0.15 · background removal (`fal.py rmbg`, only when keying fails) $0.018 · MiniMax 5 s
~$0.16 · Kling 5 s ~$0.79 · Gemini 8 s ~$0.24. `fal.py` logs each call to `costs.jsonl` next to the output.
A 30 s reel usually needs 6-12 images and 0-2 clips: about $1.50-$4. Say the total when you hand over.
