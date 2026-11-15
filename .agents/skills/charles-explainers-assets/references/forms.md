# Forms

How each form from the tree in SKILL.md is built, and the gold to copy. Paths are on main. Copy the gold's structure (crop, sizes, timing) and change its content; a copy that only changes the words isn't done.

## Demo + definition tab

Gold: `videos/eradicating-ai-slop/design-terms/` (`terms/index.html`, `tools/reel.py`), whose tab was reused in `videos/ux-principles/`.

- **One small move shows the term,** with no Before/After tag: the o slides under the T's arm (kerning), the play triangle nudges right (optical centre), the digits lock into columns (tabular numbers). In a 20-item list it follows the short-item timing in SKILL.md: it starts within 0.15 s of the cut, is done by 0.6 s and holds under the slow push-in. Why: the viewer gets about a second, so the meaning has to arrive as one move.
- **Crop the card to what the demo draws** over its whole run, then scale it up toward the slot's largest card, up to 1.2× its natural size. A small demo gets a smaller card, never empty space. Why: the tight crops are why "SETTINGS" and "box box" read at phone size.
- **The tab** sits on the card's top-left edge (`text.md`). One tab per item, staying up across the item's assets.
- **When the order is mine to suggest,** open on the three that land fastest, and never put two of the same kind (type, interface, motion) next to each other. Why: neighbours that look alike blur together.

## Flip in place

Gold: `videos/eradicating-ai-slop/unslop-designs/` for stills, `videos/design-hacks-motion/` (kit v3, `scenes/`) for motion. `kit/example/` is a motion flip with the agent cursor making the change.

- **One crop and one scale for both states.** A slow push-in, if the flip has one, runs straight through the change and never restarts on it. The state tag sits on the card's corner and flips on the change. Why: anything that moves besides the fix reads as part of the fix.
- **The before shows the flaw happening:** the pointer triggers it, time does, or the camera pushes in on it once. A demo built for the line is cropped so the flaw is the subject, and gets no mark. A still flaw on a real page (a crop of a site, where it's one detail among many) gets its red mark 0.2 s after the cut, as in the real-thing form below.
- **The change** lands on the change word. The agent cursor makes it whenever the fix lives somewhere on screen (`agent-cursor.md`).
- **The after** includes the proof beat: the same interaction again, now right. On desktop UI the agent cursor runs it; on a phone, the fingertip.
- **The clip:** 9.0 s, the change at exactly 4.50 s, both halves looping (SKILL.md, The contract).

## Side by side

Two kinds, from the two branches of the tree: a principle (the same component without it and with it) and a fix whose versions differ only in feel.

Gold for the layout: the posted cards of `videos/ux-principles/` (`kit/cards-sheet.png`, `source/cards.html`). The card is white, 960×400, with the tab on its top-left edge, two equal wells 24 px apart and a label over each. Keep that layout and drop what they got wrong: grey 21 px sublabels describing each demo, and a sentence in the tab. `pair()` in the kit draws the wells and labels (`kit.md`). `videos/eradicating-ai-slop/unslop-animations/` (148K plays) is the same idea for fixes, but its panels are too grey and its labels too small to copy.

Both kinds:
- **One component, twice.** Use the same component, crop, size and copy in both panels, so the only difference is what the principle or fix changes. Build it once as a function of the side (`build(well, side)`) so the two can't drift apart. Why: the difference is the lesson, so anything else that differs is a false lead.
- **A real component in colour, as big as its panel allows.** Its moving part stays 40 px or bigger in the final frame: a toast, a dock, a checkout button, never a grey stand-in. If it can't fit at that size in half the card, it's the wrong component for a side by side; pick a smaller real one.
- **Both start on the same frame** from the same pose, at real speed. In a list's short items, the after's move is done by 0.6 s and the end pose still shows the difference (SKILL.md, Timing, A short side by side). In a longer line the pair loops together about once a second, a cycle starts on the change word, and each cycle changes something (another item, a harder flick) so it counts as new (SKILL.md, Never stale).
- **Left is always before, right after.**
- **No agent cursor:** nothing is being fixed on screen, so a press shows as the element's own pressed state. When pointing is the lesson (Fitts's law, a hit area, where people look for the cart), or a gesture's speed is (a flick), each panel gets a plain cursor or one fingertip. So does a change whose cause would otherwise be invisible: the pointer hovering over the choices in Hick's law, or a keycap that presses as the selection moves (frequency of use). Both pointers start from the same spot on the same frame. Why: two pointers are two more things to watch unless they're the subject, but a tap with nothing tapping has no visible cause.
- **Show the difference, don't describe it.** No sublabels that say what the demo shows ("Rigid", "No wind-up", "Everything at once"). Why: the panels already show it, and in about a second there's no time for a third read.

A principle:
- **Labels:** "Before" and "After" in Inter semibold, 30 px in the final frame, in the ink colour. Each sits over its well's top-left corner, in the same place on every card. They're chrome, not a read (SKILL.md, The frame budget).
- **The tab** says what the principle means (`text.md`). A number the principle is about goes in the tab ("Keep UI under 300ms"), not under the panels.
- **A property in each well** only when one CSS property makes the whole difference, inside the well along its bottom edge so the card's chrome stays the same on every item, in the code style: `perspective: none` under the before and `perspective: 700px` under the after. The two are the clip's pause text.

A fix that differs in feel:
- **Only when the versions differ in feel** (the same duration on another curve, a spring against a tween, durations under 2× apart), on a simple element: a toggle's knob, a progress bar, one card.
- **Never in a slot whose editor tags every clip Before/After** (the hack-reel card): there, flip in place. Why: a Before tag over two versions at once tells the viewer something false.
- **Labels:** each version's value only ("ease-in", "ease-out"), 30 px or more, over its well: the before's value in red, the after's in green. There's no tab and no "Before"/"After": the pair of values is the clip's one glance text.

## After only

Gold: `videos/design-hacks-motion/assets/02-press-feedback.mp4`.

- The fix in action for the whole line, looping, tagged After. Nothing stands in for a missing before.

## The real thing, marked

Gold: `videos/eradicating-ai-slop/slop-tells/` (`tools/make_examples.py`, `picks.json`).

- **In a list, the plain screenshot cuts in on the item's first word,** and the red marks snap on 0.2 s later. Hard cut to the next item on its word.
- **The red never covers the tell.** Text gets an underline or a box. Round things get a ring. A line or a shape that is itself the tell (a border, a divider, a pill) gets arrows from open space or a rule under it. An outline encloses its thing completely and never cuts through it. Why: the viewer has to see the tell itself, not the mark.
- **Crop so the marked part sits near the top** of the slot. The bottom can fall under the caption.
- **A reveal** (what a product secretly does): the effect comes first, on the real screen, while I set it up (the Boost counter jumping between real captures). The evidence comes in on the word that names the cause, and its mark lands on that word.
- **Evidence code** is the source's own lines, verbatim, 4 lines at most, with any renames for readability marked. It's for the claim, so it doesn't have to run.
- **A big claim** shows its source (the official page, the headline, the code) with the words I'm saying highlighted. Web pages follow charles-claude-editing's rules for them (dark mode, starting at the visual part), except when the page's own look is the claim: an AI tell is shown as the model built it.
- **Keep the source of each one** (the page, the model that built it, the app version, the URL) in `explain.json`.

## Measure

Gold: `videos/eradicating-ai-slop/tools/reel/tags.js` (its `measure`, `arc` and `bars` kinds).

- A redline between the same edge of two elements with the number at its middle, a corner's radius traced as it draws in, or a wordless timeline bar for durations.
- It draws in over 250 ms on the number's word. Numbers are 40 px or more, and the equation shows only if the line says it ("24 = 32 − 8").

## Cause → effect

- The trigger acts (the agent cursor, a timer, a server reply), then the result lands. Everything else holds still for that beat. Why: two things moving at once hide which one caused the other.
- When cause and effect are more than half the slot apart, carry the eye: the result starts at the cause and travels to where it lands (a chip flying into a row). Otherwise the order of the motion is enough.

## Levels (Day N)

Gold: `videos/eradicating-ai-slop/day-09-password/`, with `tools/reel/tags.js` for the inspector layer.

- One card is the live demo. Each level morphs from the last on my word (View Transitions, stepped on the render's clock).
- The AI's version stays bare. No tags on the bad example.
- Tags name principles only (`text.md`).

## Showcase

Gold: `videos/unslop-repos/part-1/`, recorded with `unslop repos reel/source/rec.mjs`.

- Survey every example the project ships before picking. Use the strongest 3-8 per item at 0.5-1.5 s each, with a cut on most caption lines.
- Prefer recognisable subjects (iconic cards, real places) over test props, and show exactly the effect I name.
