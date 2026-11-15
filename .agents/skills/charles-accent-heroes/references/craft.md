# Craft

Read this before writing pages and again before reviewing renders. The trees are the default; leave one only for a reason you can name. `headline_note` goes into the prompt word for word, so it holds instructions for the model, not reasons.

## What the best heroes share

A dancer mid-spin trailing a loop of vermilion silk across a bottle-green stage. A folded gold-foil heron standing in god rays. A face lit by cyan and magenta gels, the word FORWARD in the magenta. A ski gondola whose cable cuts across the word POWDER. An earbud case glowing pink inside a giant dark-red flower. Each has:

- one subject, big, cut by the frame or sweeping across it (bar 2);
- a light you could name: a stage spot, god rays, two gels, the product's own glow;
- an accent that comes from the subject and reaches the type;
- a material field, and around it the quiet small type of a real site.

The flattest pages miss the first two: a whole product floating mid-frame in even studio light reads as a catalogue shot, however good the product looks.

## Type system

Choose the face by what the brand sells and how it should feel:

```
What does the brand sell?
├── Calm, luxury, wellness, craft → a high-contrast serif, light weight, with one swash or a small sparkle glyph
├── Technology, hardware, wearables → a wide, extended, heavy sans in two colours
├── Tools, software, agencies → a heavy grotesk in sentence case, the last word in the accent
├── Food, drink, pop products, festivals → one ultra-condensed giant word across the frame, split into two colours by a shape
├── Fashion, dance, culture → a tall condensed italic serif split across the frame, the subject between its words
└── Sensual products (audio, fragrance, beauty) → a script word in the accent over a refined serif
```

A reference's own type system wins when it fits the brand: it is the system the model reproduces best.

## Headline treatment

The headline belongs to the subject (bar 4). Pick by what the subject does:

```
What does the subject do?
├── Gives off light (the sun, a screen, neon, molten metal) → its light falls on the letters, and the lit word takes the accent
├── Sweeps across the frame (silk, a ribbon, a cable, a dancer) → it passes in front of some letters and behind others
├── Is made of a striking material (gold, chrome, glass, liquid) → the material runs into the letters, or one word takes its colour
├── Stands still and carries the page (a portrait, a sculpture) → the headline sits clear of it, big, one word in the accent
└── None of these → one giant word behind it, split into two colours by a shape from its world
```

Weaving through the letters is one branch, not the default: a still portrait in a glass hood or a heron in god rays is strongest with its headline left clear.

Type behind the subject is set first, then hidden. Picture the subject removed: the letters must sit at even, tight spacing, with no gap opened for a head. An image model tends to split the word around the subject instead (VI, a head, VID), which reads as type that stops for him. Name in `headline_note` the one letter the subject hides (the middle V of VIVID, the second O of COLOUR), and make the type big enough that a single letter is roughly the subject's width. A subject that hides more than one letter, or the part of a letter that defines it, breaks the word: an L that loses its foot reads as I, and a cone sitting on IDEAS made it read IDEAAS. A letter that lands in front of the subject by accident (an L lying across a man's jacket while the rest of the word sits behind him) reads as a mistake.

When edits can't get the spacing exact, set the type yourself:
1. Remove the headline with an edit.
2. Cut the subject out with a subject mask (macOS Vision's foreground mask works).
3. Draw the words in a real font behind it, at a size and offset where the subject covers the chosen letter.
4. Paste the subject back on top, and add a little grain to the type to match the photo.

## Layouts

The values for `layout`. Without a reference, the script writes the chosen one into the prompt as the composition.

| `layout` | Composition |
| --- | --- |
| `left-headline` | The headline fills the left half, the subject the right half |
| `word-behind` | One giant word across the full width, the subject in front of it |
| `split` | The headline split across the frame, the subject between its words |
| `centred` | A symmetrical poster: the subject centred, the headline centred above or below it |
| `vertical` | The headline set vertically or on a curve beside the subject |
| `macro` | An extreme close-up of the subject filling the frame, the headline over a quiet part of it |

At most half a batch shares one layout, and six pages or more use at least four. The first two layouts are what an image model draws by default, so a batch made only of them looks like one template.

## Colour

**The formula**, measured on 21 award-style heroes: the two regular colours are one dark and one light, at least 0.4 apart in OKLCH lightness (median 0.48). Usually one of them is a real colour and the other near-neutral (17 of 21). The accent is the most vivid colour on the page and mid-light: at least 80% of the chroma its hue can reach at that lightness. That is about 0.2 for most hues; greens and teals top out near 0.15.

**Distance.** Put the accent 120-180° around the wheel from the other two colours; 75° is the minimum. Creams, greys, blacks and whites (OKLCH chroma under 0.04) don't count. The further the accent sits from the other two, the harder the page pops. An accent in the same family as a regular colour reads as a shade, not a new colour (fuchsia after pale pink), unless it takes the tonal route. For reference, the minimum still lets a strong page through: a kintsugi bowl's gold seams sit 87° from its celadon.

**The tonal route.** When the accent is the light itself (gold sunlight in a gold-brown room), it may share the field's colour family, because what pops is brightness, not hue. It must then read as light: at least 1.8 times the chroma of either regular colour and at least 0.3 lighter than the field, on top of the 80% vividness rule. Set `route` to `tonal` and `check` measures that instead of the distance. Use it only when one strong light fills the scene (god rays, a glow, its reflection in gold or chrome); everywhere else the far accent wins.

**Hot against cold** pops hardest: orange on cobalt, gold on indigo, pink on black, lemon on sky blue.

**Size and place.** The accent covers 15-30% of the frame and lives on the subject: its light, its paint, its material. From there it may spill onto the headline. A thin line of it (a laser stripe on the floor) or a small object of it (a pool in a desert) leaves the page flat.

Palettes that pass the formula, as field + second colour + accent:

- Lemon `#F4E04D` + Charcoal `#2A2A2E` + Electric Lavender `#9B5CFF`
- Midnight `#0B1026` + Sky `#BCD4F2` + Acid Lime `#B8F01E`
- Ivory `#F6F1E4` + Forest `#1F4A3A` + Vermilion `#F04A24`
- Deep Teal `#014342` + Bone White `#FEFCF5` + Fuchsia `#F02391`
- Plum `#3A1430` + Blush `#F3D9DE` + Jade `#00B48A`

## Light

Name one setup in `light`, and where it falls. Unnamed light comes out soft and even, and even light is what made the flattest pages look like catalogue shots.

| Setup | Use it for | What it gives |
| --- | --- | --- |
| Two coloured gels, one from each side | faces, glossy products, technology | colour that models the shape; the stronger gel is the accent |
| God rays through haze | wellness, hospitality, craft | shafts of light the subject stands in; the light carries the accent |
| Hard on-camera flash | fashion, food and drink, anything mid-splash | frozen motion, a crisp cast shadow, real skin |
| The product's own glow as the only light | products that light up or make sound | a dark field lit by the subject. Give the glow a shape that crosses the frame (an aurora sweeping round a watch), never a halo round a centred product |
| One stage spot on a dark stage | dance, theatre, music | the figure lit, the stage falling away to dark |
| Light through the accent material | glass, liquid, silk, petals | the accent glowing from inside the material |
| High sun with hard shadows | outdoors, sport, travel | a deep sky, crisp shadows, snow or water catching the light |

## Backgrounds

Name a material from the brand's world in `background`. Never leave a flat digital colour: it is the first thing that looks generated, and it covers most of the frame.

- Wellness, craft, hospitality: limewash, handmade paper, plaster, linen.
- Technology, hardware: brushed aluminium, frosted or fluted glass, matte ceramic.
- Food and drink: enamel, risograph ink, waxed paper, glazed tile.
- Fashion and beauty: a studio paper backdrop with a cast shadow, vinyl, velvet.
- Outdoors and sport: snow grain, sandstone, rubber.
- Culture and galleries: halftone print, gallery plaster, screen-printed ink.

## People and objects

**People** are photographed under one of the light setups, with real skin (pores, fine hairs), film grain and a little halation on the brightest highlights. Flawless skin under even studio light is what reads as AI first. A person in motion fills the frame on a plain field or a stage: a dancer mid-leap, a kayaker mid-stroke, frozen by flash. The same activity as a small figure in a wide scene fails, because image models fall apart on small faces, hands and crowds, and the wide view reads as a stock photo.

**Objects** keep real proportions (a running shoe's cushion is about 4 cm at the heel) and crisp small parts: dial ticks, screen text, stitching.

**Catalogue categories** (watches, coffee, shoes, headphones, perfume) come out as packshots by default. Either crop the product huge and give its accent a shape across the frame (a watch cut by the frame's edge, an aurora sweeping across its dial), or set it in another category's world: earbuds glowing inside a giant flower read as a surprise, while perfume among petals reads as every perfume ad.

## Small type

A wordmark, three to five nav links, one button, and at most three captions. Each caption is real information: a date, a spec, a price, a place ("8 Feb to 24 Mar", "395 g", "64 pistes"). Slogans in four corners crowd the page and say nothing. Quote every word in `ui` so it is spelled right.

Vary the button across a batch: a round badge, a text link with an arrow, a ticket stub, an outline pill. In a batch of six or more, give one page only a wordmark and one link instead of a full nav.

## The tells

Walk every render against this list. One hit sends it back for an edit, or for a re-roll if the subject itself is wrong.

- A small figure in a wide scene, or a wide landscape with a small subject.
- A whole product floating mid-frame with a margin all round, in even light: a catalogue shot.
- A product glowing in the middle of an empty dark field: the stock premium ad. A glow with a shape (gels on a face, an aurora round a watch) is fine.
- Flawless skin under even light.
- A flat digital field.
- Fire, lava, lightning or molten cracks as decoration.
- Impossible proportions or a warped object.
- Smeared dials, screens or small text.
- A small or pale accent, or a same-family accent that isn't clearly the brightest thing on the page.
- A letter hidden by the subject, or in front of it by accident.
- More than three captions, or slogans as captions.
- A clever metaphor that hides what the business sells.

## Variations

The five renders of a page are near neighbours, each changing one thing: the crop (the whole subject, or cut by two edges), the moment (still, or the peak of its movement), the camera (lower or closer), or how far its long part sweeps. The accent colour stays the page's own, because the prompt and the check hold every render to its palette. The user picks one version of a page they already like, so unrelated ideas waste renders.
