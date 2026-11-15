# The kit

`kit/` draws and renders the assets. It's the motion-hacks kit v3 (`videos/design-hacks-motion/scenes/`, the clips I approved on 12 Nov), made general and given the explainer layer: the agent cursor, its selection box, the slow push-in and the definition tab. It needs Bun, Google Chrome in `/Applications` and ffmpeg. Run `bun install` in `kit/` once (in this repo you can link `kit/node_modules` to `.claude/skills/landing-craft/tools/node_modules` instead).

## A project

One folder per video, usually `videos/<video>/explainers/`:

| Path | What it is |
|---|---|
| `explain.json` | The beat sheet, the slot and every asset (below). Write it before any scene |
| `scenes/<asset id>.js` | One scene per asset |
| `assets/<asset id>.mp4` | The rendered clips (`.mov` with alpha for `"alpha": true`) and `assets/stills/` |
| `check/phone.png` | The phone sheet, one strip per asset |
| `build/` | Frames while rendering; git ignores it |

Start by copying `kit/example/`: one flip ("Scale from 0.97") where the agent double-clicks the old value in the code block and the new one lands on the word.

## explain.json

```json
{
  "video": "10 niche animation hacks",
  "format": "hack reel",
  "slot": { "name": "hack-card", "w": 1080, "h": 960, "band": [300, 890], "scale": 0.72 },
  "render": { "fps": 60, "scale": 2 },
  "ground": "#e6e9ee",
  "agents": [{ "label": "Agent", "color": "#0079CD" }],
  "lines": [{
    "id": "01", "say": "Don't scale from zero. Scale from 0.97.", "term": "Scale from 0.97",
    "takeaway": "Enter from 0.97, not from 0", "change": { "word": "Scale", "occurrence": 2, "t": null },
    "assets": [{
      "id": "01-scale-from-097", "form": "flip", "why": "one line on why this form",
      "dur": 9.0, "tFix": 4.5, "win": { "b": 1.1, "a": 1.5 },
      "words": [{ "text": "Letter-pair spacing", "kind": "tab", "in": 0.0, "out": 1.2 }],
      "cursor": [{ "agent": "Agent", "action": "double", "target": "the 0 of scale", "t": 4.5 }]
    }]
  }],
  "clicks": [{ "line": "01", "t": 4.5 }]
}
```

- **`slot`:** the panel's size in design px, the band the viewer sees (`[top, bottom]`, the whole panel if left out) and the panel's scale into the final 1080×1920 frame. `fpx()` and the phone check use the scale, so get it from the editor or `slots.md`.
- **`form`:** `flip`, `side-by-side`, `after-only`, `demo-tab`, `real-thing`, `measure`, `cause-effect`, `level` or `showcase`, from the tree in SKILL.md.
- **`tFix`:** where a flip changes. A flip is 9.0 s with `tFix` 4.5 (SKILL.md, The contract). Leave it out for an asset with no change.
- **`win`:** the seconds the edit shows before (`b`) and after (`a`) the change. The phone check takes its frames from it.
- **`words`:** every word on screen with its kind (`tab`, `tag`, `pause` for code, `caption`, or `ui` for copy inside the demo, which reads as part of the subject and isn't timed) and its in and out times on the line, for the reading-time check.
- **`cursor`:** each action the agent takes: `click`, `double` or `drag`, what it acts on, and when the change lands.
- **`agents`:** the reel's agents in the order they first act, each with its label and colour (`agent-cursor.md`, The look). The kit draws every cursor, selection and caret in them, so a lone violet agent needs no colour in its scenes.
- **`parts`:** for an asset built in parts (a crop-in, a second subject): `[{ "n", "at", "form", "subject", "say", "transition" }]`, with `at` in clip seconds. The editor still gets one clip; this is for the phone check and the next reader.
- **`alpha`:** `true` renders a transparent ProRes 4444 `.mov`, for a card the editor lays over footage. The phone check and the glance put it over its `checkBg`, else `slot.checkBg` (a frame of the footage under it, relative to the project), else dark grey. To hand it over at 1× (VP9 for the UX-principles `assemble.py`), scale with premultiplied alpha, `format=gbrap16le,premultiply=inplace=1,scale=W:H:flags=area,unpremultiply=inplace=1`, or its edge picks up a dark fringe.
- **`render: false`** on an asset that's handed over as an existing file (a screenshot, a recording).

## A scene

```js
(() => {
  const { zoom, div, E, prog, agent, agentAt, fpx } = H$;
  H$.scene({
    // Optional. {{before|after}} marks the value that changes on the fix; a line starting with + is added on the
    // fix; select: true shows the agent's double-click selection on the old value, in the agent's colour;
    // insert: true shows its caret and an empty line before the + lines land (agentAt action 'insert').
    code: { lang: 'css', select: true, lines: ['button:active {', '  scale: {{1|0.97}};', '}'] },
    push: true,                          // optional: the slow push-in on the stage, 2% a second
    stills: { before: 3.7, after: 5.5 }, // review PNGs
    check: [3.4, 4.4, 4.6, 5.6],         // optional: the phone check's times
    build(stage, area, ctx) {
      // area: the band above the code block ({ top, bottom, mid }). ctx: { panel, block, T, DUR, asset, line, ex }.
      // Build the DOM once here, then return the function that draws the frame at t.
      return (t) => {};
    },
  });
})();
```

Every scene is a pure function of time: `seek(t)` draws the frame at t, so the renderer can step it one frame at a time. Never read the clock, and never use CSS transitions or animations. Compute the value the real CSS would have at t with `transition()`, the curves in `E` or `springTo()`. Why: a frame-stepped render is exact and repeatable, and a jank flaw can only be shown by holding frames on purpose.

## Helpers on `H$`

| Helper | What it does |
|---|---|
| `zoom(stage, { w, h, z, cy })` | A box for UI at its real CSS size, magnified `z` times (about 2 in the hack card), so 10px in the code moves 10 px in the demo |
| `div`, `el`, `sv`, `icon(name)` | DOM, SVG and Lucide-style icons |
| `E.out`, `E.inOut`, `E.cssEase`, `E.cssOut`, `E.mInOut`, `E.move` | The curves: my ease-out `cubic-bezier(0.32, 0.72, 0, 1)`, my ease-in-out `(0.77, 0, 0.175, 1)`, the CSS keywords and Motion's easeInOut |
| `transition(t, events, { dur, ease, init })`, `keyframes`, `keys`, `springTo`, `motionSpring` | What a CSS transition, a keyframes array or a spring would be at t |
| `codeBlock` | Built by the page from `scene.code`, under the band, at 24 px or more in the final frame (34 px in the panel, more on a slot scaled under 0.71). `ctx.block.slotBox(k)` is where token k sits, and `ctx.block.insertPoint()` where the agent clicks to add the `+` lines (`code.insert: true`), for aiming it |
| `agent(ctx.panel, { label, color })` | The agent cursor; `.set(x, y, { press, o })` puts its tip at (x, y). Put it on `ctx.panel`, never in the pushed stage |
| `agentAt(t, { T, from, to, action, dragTo, after, rest, lineLeft })` | The agent's position, press and opacity at t on the timeline in `agent-cursor.md`; `action` is `click`, `double`, `drag` or `insert` (with `code.insert`) |
| `glidePt`, `pressAt` | A single glide or press, for a proof beat the agent runs itself |
| `selection(ctx.panel, { color })` | The selection box with corner handles; `.set(x, y, w, h, o)` |
| `tab(ctx.panel, { x, y, text })` | The definition tab, for a slot whose clip draws its own |
| `pair(parent, { x, y, w, h, labels, colors, dots })` | A side by side (`forms.md`): two equal wells in the box with a 30 px label over each, Before and After unless you pass a fix's values. Returns `{ b, a, labels, ww, wh }`; build the component once as `build(well, side)` and call it for both |
| `cursor`, `finger` | A plain pointer and the fingertip disc, for interactions that aren't the agent's |
| `fpx(n)` | n px in the final frame, in panel px: text is `fpx(26)` or more, an outline `fpx(2)` |
| `AGENT_COLORS` | Blue, violet, magenta, teal, in the order they're assigned |

## Commands

```bash
bun skills/charles-explainers-assets/kit/render.mjs <project>                 # every asset into assets/, with its stills
bun skills/charles-explainers-assets/kit/render.mjs <project> --only 01-a,03-b
bun skills/charles-explainers-assets/kit/render.mjs <project> --stills 4.0,5.2  # PNGs in build/stills/ to check a scene
bun skills/charles-explainers-assets/kit/check.mjs <project>                  # check/phone.png
bun skills/charles-explainers-assets/kit/glance.mjs <project>                 # check/glance/<id>.png, the muted glance's frame grid
bun skills/charles-explainers-assets/kit/words.mjs <project>                  # sizes, contrast and reading rates, measured
```

A 9.0 s clip at 60 fps and 2× takes about 30 s, and four render at once (`--jobs`). `check.mjs` draws the state tag on, crops each frame to the band and shrinks it to the slot's width on a phone: 280 px for the hack card.
