# Craft

## Lanes

Walk this tree once per set. It picks the lane; the lane sets the defaults below.

```
How should the app feel to the person it's for?
├── Loud, social, playful
│   ├── Its personality lives in many small moments (messages, votes, reactions) → Chaotic
│   └── It has one strong world or character (a mascot, a place, a game) → Fun / gen z
├── Capable, serious, focused (AI, money, work, training plans) → Clean / editorial
├── Taste, calm, the senses (inspiration, wellness, fashion, food) → Aesthetic
└── Creative culture with memory (photo, film, music, style) → Y2K
```

An app can honestly fit several lanes. When you make several versions, use the others too.

| | Fun / gen z | Chaotic | Clean / editorial | Aesthetic | Y2K |
| --- | --- | --- | --- | --- | --- |
| **Type** | Chunky rounded or heavy grotesk, mixed weights in one headline; inflatable or chrome 3D letters for the hook | Condensed caps for the lead; many faces allowed as texture | A serif, or a refined grotesk, with one italic word | Grotesk with an italic-serif emphasis word | Small uppercase labels plus plain sentence case |
| **Palette** | One saturated world (sky blue, electric blue, meadow green) | Y2K sky, cream collage or electric blue | Off-white, near-black and one warm or brand colour, alternating | Bone or off-white with one off-colour frame | Film photos with their own colour; text in white |
| **Imagery** | One continuous world, 3D props, a mascot, real people cut out | Collage of props, stickers and real people | One cinematic photo across 1–2, then calm frames | Curated images, collage shapes, grids crossing seams | Full-bleed photos as backgrounds (often blurred copies of the content), grain, date stamps |
| **UI treatment** | Phones with UI bubbles and cards spilling out | UI bubbles everywhere, phones half-hidden | Frameless cards or one phone per frame | Frameless cards | Frameless cards, before/after splits |
| **Rhythm after the hook** | Alternate the phone high and low, and the headline with it | Give every frame its own composition | Hold one layout; alternate two ground colours | Hold one layout; one off-colour frame, and change the scale | Hold one layout; change the photo |
| **Voice** | Playful, short, "you" | Funny, specific, slang | Calm, declarative, confident | Quiet, sensory | Manifesto-like |
| **Words** | Headline plus 1–3 floating bubbles | One lead line; the rest is texture | Headline only | Headline only | Label plus one sentence |
| **Swipe** | Flooz, Daimon, Peer, TripBFF, Bump concept | Picky AI, Sugar, Bump | Claude, Perplexity, Open | Cosmos (both sets) | VSCO |

## Hooks

Pick one per set, and use a different one for each version.

| Technique | Use it when | How |
| --- | --- | --- |
| One photo across both | You have a strong real photo of the person or scene | The subject sits in frame 1, and the scene runs on behind frame 2's headline or phone. Never put a face on the seam. (Claude, Perplexity) |
| Giant headline across the seam | The promise is two to four punchy words | The type is at least 30% of the frame height. Split it between words, never inside a word, so each frame still reads when they sit apart. (TripBFF, Bump concept) |
| An object crossing the seam | The product has a signature object (a bar, search field, hand or plane) | The object's centre sits within 60 px of the seam. Frame 1 holds the headline and frame 2 holds the UI. (Cosmos alt, Picky AI) |
| A continuous world | The lane is fun / gen z or aesthetic | A sky, meadow, map or texture runs through the whole set. The hook places the subject, the logo and the promise in it. (Flooz, Peer) |
| A sentence that carries on | The pitch works as two beats | Beat one ends frame 1, and beat two opens frame 2 or 3, in the same face and size. (TripBFF) |

## Seams

- **A continuous background** is the simplest crossing: one image, gradient or texture spanning the strip (`.span`), never a fresh background per frame that happens to match. Alternating colours (light, dark, light) need an object across each change instead.
- **Objects on a seam** split no more unevenly than 40/60. Keep a shape that crosses a seam simple, because any detail on the seam line is cut in half when the frames sit apart in the store.
- **A phone straddling a seam** tilts 12° at most, and its screen stays readable in one frame.
- **Type on a seam** is cut only between words.
- **A recurring line** (a path, graph, route or thread) passing through every seam is the strongest continuity device. It also makes a good signature move.
- **Light** comes from one direction across the whole strip, and every shadow agrees with it.
- **A seam never crosses a face.** The store leaves a gap between screenshots that cuts a strip out of anything on the seam. A photo of a person can straddle a seam, and their body or the bar can take the cut, but their face can't. Note where each face sits across its photo and keep the seam at least 10% of the photo's width away from it. Face detectors miss profiles and fire on hands and shoes, so mark faces by eye. Seam photos sit in the gutter between screens, never over the UI. Two prints stacked on one seam make a good accent.

## Type

- **Faces:** brand fonts first. Otherwise, by lane:
  - serif: Instrument Serif, Newsreader, Fraunces, Playfair is banned
  - condensed: Anton, Big Shoulders Display, Mona Sans at 75% width
  - grotesk: Inter Tight, Space Grotesk, Bricolage Grotesque
  - mono for labels: JetBrains Mono, IBM Plex Mono
- **Emphasis:** one word per headline, by a single method for the whole set: accent colour, italic serif, weight, a highlight bar, or the app's own UI (a chat bubble, a tag).
- **Sizes:** see the bar. Hook lettering can be any size above that. Line height is 0.9–1.0 for caps and condensed faces, and 1.0–1.1 for sentence case.
- **Line breaks:** break by meaning ("Know what / to lift next"). No orphan word, and no line more than twice as long as another.
- **Space:** at least 32 px between the headline and the frame edge, and 24 px to the UI below it. Overlapping a headline onto a photo or object is deliberate, and the headline stays readable.

## Copy

Hook patterns:

| Pattern | Example |
| --- | --- |
| Problem / stop | "Stop guessing what to lift" |
| Invitation | "Meet your AI coach" |
| Outcome | "Hang with friends IRL" |
| Identity | "Become who you keep saying you'll be" |
| Manifesto | Three short lines |
| Two-beat sentence | "Make new friends…" then "and travel the world" |

- **Feature frames** are results or experiences: "Know what to lift next", not "Smart workout tracker". A feature name is fine when the name is the benefit ("Search by colour").
- **Banned:** easy, powerful, seamless, all-in-one, ultimate, revolutionary, effortless, "AI-powered" as a lead. Never use exclamation marks in clean, aesthetic or Y2K sets.
- **Numbers** go in only when true: lengths, counts and tiers from the brief.
- **Voice** follows the lane table. Read every headline aloud in the brand's voice; if it sounds like an ad template, rewrite it.

## UI

- **Crop to the payoff.** Find the moment in the capture where the feature pays off, and show that part large: the target line, the rank, the answer. A whole screen is context; the crop is the proof.
- **Lift one line out.** When the payoff is a sentence or a number, show it again outside the screen as a larger crop of the same capture (never retyped), overlapping the phone's edge. One lifted piece per frame at most.
- **Echo it in the headline.** The strongest frames repeat something from the screen in the headline or art: "Go for 7" above the tracker's 7, a chalk ring on the real number, a crest beside the rank it shows.
- **Nothing covers what must be read.** A phone or card in front of giant type can turn "?" into "2". Check every giant word and number at full size against whatever overlaps it.

## Colour

- At most three colours plus one accent. The accent marks one thing per frame: the emphasised word, the proof number, or the moment in the UI.
- UI captures carry their own colours. Pick backgrounds that let the capture's accent read: dark UI on a light set needs a phone or card edge, and light UI on a dark set needs a soft shadow.
- Every frame keeps an edge against both the white and the black App Store: no pure #FFFFFF or #000000 background reaching the frame edge unless something else defines it.

## Art

Generate only objects, materials, skies, worlds and lettering. Prompt formula:

> [subject, exact], [material and finish], [palette hexes], [light: direction, quality, colour], [camera: lens, angle, framing], [background: transparent / plain / the world], no text, no people, no logos.

Examples:
- "Inflatable vinyl letters spelling GET STRONG, glossy pearl-white plastic with soft seams, catching a warm key light from the upper left, studio product shot, 50mm, transparent background"
- "A chalk-dusted steel barbell plate, matte black rubber with a worn white rim, raking light from the left, 85mm, three-quarter view, transparent background"

Reject and regenerate any image with melted or extra details, wrong lettering, a light direction that doesn't match the set, plastic CGI sheen in a photographic set, or anything shaped like a person.

## The tells

Fail a frame that shows any of these:

- a gradient background, a phone centred in it, and a caption above: the default template
- an indigo, violet or purple gradient as the ground: the first thing people read as AI-made
- headlines that name features ("Smart tracker", "Advanced analytics")
- text over a busy part of a photo, with no scrim or clear area
- empty states, onboarding, login or placeholder data in a capture
- phones at different sizes or angles across the set, with no reason
- stock-looking 3D icons (floating check marks, coins, rockets, sparkles) that aren't from the app's world
- glows with no light source, neon outlines, glassmorphism on everything
- every frame using the same layout with only the screenshot swapped: no change of ground, scale, crop or photo (see each lane's rhythm)
- generated people, or a real person's body altered
- a seam cutting through a face, a word or the UI being sold
- more than one emphasis per headline, or a second headline in the frame

## Review

Answer each in `review.md`:

1. **The 3-second test:** from `search.png` alone, what is the app, and who is it for?
2. **Seams:** what crosses each seam?
3. **One idea:** what is each frame's one idea, and could any word go?
4. **The swipe:** does frame 2 make you want frame 3?
5. **Logo swap:** would a competitor's logo fit?
6. **The move:** where is it in each frame?
7. **The closest swipe reference:** where is this set better, and where is it weaker?
