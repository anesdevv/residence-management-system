# Words on screen

Every kind of text a clip can carry. Sizes are in the final 1080×1920 frame, after the slot's scale. The reading-time rule (SKILL.md, Words on screen) applies to every glance text: aim for 15 characters per second it's fully on screen, never over 20.

## Definition tab

- **Look:** a black tab on the card's top-left edge, white Helvetica Neue bold at 30 px, 14 px of padding either side, 1.55× the type size tall. When the term changes, the old text fades out in the first frame as the tab starts to resize, the tab reaches its new width by 0.07 s, and the new text fades in over the next 0.07 s, so no text is ever cut off and the tab is empty for one frame at most. Count reading time from the moment the text is fully in, about 0.13 s after the cut. Gold: `videos/eradicating-ai-slop/design-terms/tools/reel.py`.
- **Words:** plain ones a 14-year-old knows, sentence case, no full stop. It says what the term means, never the term itself or a synonym for it. Why: "Explain like the reader is 14" is my rule for explanations.
- **Length:** inside the reading time for the line. A 1.2 s item has about 1.1 s fully on screen, so aim for 16 characters and never go past 22:

| Term | Too long (characters, a second) | Fits (characters, a second) |
|---|---|---|
| Kerning | Spacing between a pair of letters (33, 30) | Letter-pair spacing (19, 17) |
| Leading | The space between lines of text (31, 28) | Space between lines (19, 17) |
| Touch target | The tappable area, not just the icon (36, 33) | The tappable area (17, 15) |

- **Every term keeps its tab.** If the meaning seems to need more words, find the shortest true gloss. If nothing true fits, ask the editor for more time on that item. If the cut is fixed, use the shortest true gloss and flag its rate in `explain.json`. The full definition goes to the editor for the post caption.

## State tag

- "Before" or "After", in the same black tab, flipping on the change.
- In the hack-reel and term cards, the list kit draws the tab on the card's frame (`tagOnFrame` in `videos/design-hacks-list/edit.mjs`) and flips it at the change time in `explain.json`, so leave it out of the clip. In any other slot, draw it in the clip.
- A side by side has no state tag: a label sits over each panel instead (`forms.md`, Side by side).

## Principle tag (the Day N inspector)

My rules for the inspector layer (2026-11-07), from `videos/eradicating-ai-slop/tools/reel/tags.js`:
- It names a design principle in 4 words or fewer. No sentences, no code, no cards.
- It never repeats what I'm saying at that moment.
- Nothing goes on the AI's screen. It's the bad example, so it stays bare.
- An outline fully encloses the thing it's on and never cuts through it.
- Numbers appear only where the line is about a measurement ("24 = 32 − 8").
- Tags enter on an ease-out from 0.96 scale, never from 0, and leave about 40% faster.
- Look: the kit's tag and its selection box with corner handles, in #0d99ff, with white 26 px semibold text and a corner radius of 9 px, not fully round. White on #0d99ff is only 3.0:1, under the 4.5:1 rule in SKILL.md, but it's the blue every posted Day N reel uses, so keep it. A darker blue is my call, not the skill's.

## Code block

For a line that teaches a property or a value someone could copy. Principles never get code, except the one property that makes the whole effect, alone on one line (`perspective: 700px` under solid drawing in 3D, as posted).

- **The full working recipe:** every declaration the fix needs, at most 4 lines. Line-clamp, for example, needs `display: -webkit-box`, `-webkit-box-orient: vertical` and `overflow: hidden` as well as `line-clamp`. Why: my script doesn't say the CSS, so the screen carries it for the people who pause or screenshot.
- **Where:** under the subject, inside the band, ending at least 12 px above the band's bottom.
- **Look:** the kit's dark block, JetBrains Mono, with the kit's colours for CSS, JS and JSX (`codeBlock()` in `videos/design-hacks-type/scenes/lib.js`). 24 px or more in the final frame: the kit sets the size from the slot's scale, 34 px in the panel at the hack card's 0.72 and 36 px at its smallest, 0.68. About 44 characters fit on a line at 36 px; rewrap or shorten anything longer.
- **The change:** only the changing token animates. It morphs to the new value on the change word under a soft green highlight. If a property and its value both change, the whole declaration is the token. Lines the fix adds open where they sit under a green tint, and the block grows downward to fit them. Nothing else in the block moves. Why: the one moving token is the only part a viewer can read at speed.
- **A range in my line** ("between 150 and 250 milliseconds") shows the value I say on the change word.
- **One declaration:** a fix that is a single value can be a one-line chip in the same style (`input { font-size: 16px }`).
- **It must be true:** the block is exactly the code the demo runs. Evidence code in a reveal is the exception (`forms.md`, The real thing).

## Other captions under the subject

- One line in the code style, for a detail the line implies but doesn't say, which makes the demo copyable or honest: `perspective: 800px` under "Solid drawing in 3D" (I asked for that note).
- Never a sentence explaining the demo, and never my words.

## The agent cursor's label

"Agent", or "Agent 1", "Agent 2" when more than one is on screen: white 26 px semibold in a chip of the agent's colour. See `agent-cursor.md`.
