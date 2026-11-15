# The agent cursor

A labelled, coloured pointer, like a collaborator's cursor in Figma, that makes the change on my word, so the viewer's eye is already where the change happens and sees what caused it.

Why: in 1-5 s, with my face, the list and the captions competing, the eye has to be at the change before it happens. A moving pointer is the strongest cue on screen, and press-then-change shows cause and effect: this value did that. It also says what my reels are about: telling your agent what to change ("Give this to your AI agent:").

## When it appears

```
Is the line 2 s or longer, with a fix or a change of state on screen?
├── No → no agent cursor. A plain pointer or a fingertip shows up only if the demo's
│   interaction needs one
└── Yes → the agent cursor makes the change
    Does the demo also need a pointer to show the interaction?
    ├── Desktop UI → the agent cursor does that too, before and after the change:
    │   one pointer for the whole clip
    ├── Touch UI → a fingertip taps inside the phone and the agent cursor only makes the change;
    │   the finger lifts away before the cursor enters and comes back for the proof beat after it leaves
    └── No → the agent cursor enters for the change and leaves after it
```

## What it acts on

```
Where does the fix live?
├── In the code block → it double-clicks the old token; on the word the new value morphs in
│   under a green highlight. If a property and its value both change, the whole declaration
│   is the token
├── In lines the fix adds → it clicks right after the last character of the line above. A caret
│   in its colour appears there, an empty line opens under it with the caret on it, and on the
│   word the new lines land there under green (the kit's `code.insert`). Why: a click past the
│   end of a line read as pointing at nothing, and an empty line with a caret reads as
│   "adding here"
├── In a control the viewer would recognise (a toggle, a slider, a select, an inspector field)
│   → it clicks or drags the control the way a hand would
├── In the component's own shape (a radius, a gap, a size) → on the press a selection box with
│   corner handles wraps the element, and the cursor drags a handle; the box fully encloses it
└── Nowhere on screen (a principle with no single control) → no agent cursor; the flip happens
    on the word by itself
```

Why: the press has to be on the real cause. A press on the component for a fix that lives in the code teaches the wrong thing.

## More than one agent

Only when my line is about more than one: agents working in parallel, a handoff, one checking another's work. Each gets its own cursor, labelled Agent 1, Agent 2 and so on in the order they first act, each in its own colour (The look). At most 4 on screen. They may glide at the same time, but their changes land one at a time, at least 0.5 s apart, unless my line's point is that they work at once. Why: one change at a time is the frame budget, and the eye needs about half a second to find each one. A line about parallel agents is the one place where things happening at once is the lesson.

## The look

- **A coloured arrow, like a collaborator's cursor in Figma:** filled with the agent's colour, with a 2 px white outline and a soft shadow (0 2px 6px at 25% black). Why: I asked for coloured cursors like Figma's. The colour sets the cursor apart from the UI it acts on, and the outline keeps it visible on the dark code block.
- **Its size** is what a real pointer would be at the demo's zoom (the kit's `cursor()` at scale 1.3, next to UI magnified about 2×), and never under 36 px tall in the final frame.
- **The label:** "Agent", in a chip of the same colour attached below-right of the arrow's tip, the way Figma shows a collaborator's name. With more than one on screen, "Agent 1", "Agent 2" and so on. White 26 px semibold text, corner radius 9 px like the principle tag. Always Agent, never a product name.
- **The colours,** in this order: blue #0079CD, violet #9747FF, magenta #DE04A3, teal #058193. Assign them once per reel, skipping any colour the reel's demos use as an accent, so a cursor never blends into what it clicks: a lone agent is blue, or violet when the demos' buttons are blue. List them in `explain.json` "agents", and the kit draws every cursor and selection in them. Never red or green, which mean the flaw and the fix. Each agent keeps its colour for the whole reel. Why: these are Figma-style hues, each darkened only as far as its white label needs for 4.5:1 (Figma's own blue, #0D99FF, gives 3.0:1). Each is also at least 3.7:1 against the hack reels' #e6e9ee ground, so the arrow shows even where its white outline doesn't.
- **What it selects takes its colour,** as a collaborator's selection does in Figma: the token it double-clicks, and the selection box and handles it drags. The new value still lands under green, because green is the fix.
- **The fingertip** is the kit's soft dark disc (`finger()` in `videos/design-hacks-motion/scenes/lib.js`). Never an emoji hand or a photo of a finger.
- **No trails, glows, sparkles or simulated hand shake.** Why: they're noise, and they're AI tells.

## The timeline, with the change at T

**Moving in.** It arrives by T − 0.6 s (T − 0.9 s before a drag), so it starts that much earlier than its glide: from where it is, or from the slot's edge nearest the target, fading in over 120 ms if it's entering. The glide is 450 ms across less than a third of the slot and 600 ms across more, on the ease-in-out `cubic-bezier(0.77, 0, 0.175, 1)`, along a slight arc that bows no more than 8% of the distance. Once it arrives, the target shows its own hover state, if it has one.

**The action:**

| Action | Timeline |
|---|---|
| Click a control | Presses at T − 0.15 s (the arrow dips to 90% over 80 ms); the control changes at T; releases at T + 0.07 s |
| Double-click a code token | Presses at T − 0.3 s and T − 0.15 s, and the token shows as selected after the second; the new value morphs in at T; releases at T + 0.07 s |
| Drag a slider or a handle | Presses at T − 0.68 s and drags for 600 ms (a slider's full travel), so the value arrives at T; releases at T + 0.07 s |
| Add lines of code | Arrives by T − 0.9 s and clicks at T − 0.45 s, so its caret shows; the empty line opens over T − 0.25 to T − 0.1 s, and the new lines land at T |

**After the change.**
- It holds still until T + 0.5 s while the result lands. If less than 1.3 s of the line is left after T, it fades out at T + 0.25 s instead.
- On desktop UI, where it runs the proof beat itself, it then goes straight to that interaction. Otherwise it leaves for a rest spot 60 px clear of anything that changes, or fades out over 150 ms. Exits run about 40% faster than entrances.

Why: the eye needs about half a second to find a pointer and follow it, the press just before the word puts the cause right before the effect, and a pointer that moves while the result lands pulls the eye off it.

## Never

- **Covering what it changes.** Aim inside the target but off its text: a code token's lower-left corner, a button's empty side. Why lower left: a value grows rightward when it changes (0 → 0.97), so a tip on the right ends up on the new value. The label hangs below-right of the tip, over the line under the token, so never put a token that changes at the same moment right below it; reorder the declarations if you must.
- **Moving without a reason.** Every move goes to the next action or clears the way. It never circles, wanders or rests on the subject.
- **Sharing the screen with a pointer that isn't another agent in my line.** A fingertip and the agent cursor take turns (When it appears).
- **Faking a state.** The cursor's path drives the demo's own states: the kit's `agentAt()` gives its position and press at every frame for the scene to react to, as `pointerAt()` does in `videos/eradicating-ai-slop/tools/reel/tags.js`, so hover and press are the component's own. Why: states drawn on top drift off the cursor and look fake.
