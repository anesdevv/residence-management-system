# Claude product UI (`ui-claude.css`, `ui-claude.js`)

The Claude apps rebuilt at about 2x desktop scale: the Claude Code terminal, the desktop and web app (light, dark,
deep dark), home, chat, steps rail, search, other-model reply cards, artifacts, split view, docs, checklists,
slides, the permission dialog, the Usage page and a docked dashboard. Every class starts with `.cl-`. Each
surface is sized in `em` from its own font-size, so one number rescales it: `.cl-term` 32 px mono, `.cl-app` 30 px
(`.cl-dense` 22 px), `.cl-doc` 30 px. The working demo of every component is `work/kit-claude/` (`out/demo.mp4`,
sheets `out/sheet_0N.jpg`; recipes d01-d09 in `compositions/`); copy markup from there.

The first two lines of a scene are `AR.names(); AR.clIcons();`. `AR.clIcons()` draws the inline SVGs:
`<i data-cl-icon="name">` (plus, chev-down, chev-right, up, mic, wave, sidebar, panel, comment, expand, close, doc,
lock, calendar, clock, copy, thumb-up, thumb-down, pencil, cap, code, cup, bulb, search, globe, check, check-c,
gear, chart, table, image, checks, text, shapes, download, play, more, enter, sprout, grid, folder, chats, star,
prev, next, pause, branch, terminal), `<i class="cl-logo">` (the pixel critter), `<i class="cl-spark">` (the coral
starburst) and `<div class="cl-cursor">` (the arrow pointer). Real logos and avatars go in
`<img class="cl-slot" src="assets/...">` inside their slot (`tools/source.py`); a `.cl-mark` letter tile is the
draft placeholder.

## Components

| Component | Structure | What it is |
|---|---|---|
| Terminal | `.cl-term` > `.cl-term-bar` (`.cl-lights` with 3 `<i>`, `.cl-term-title`) + `.cl-term-body` > `.cl-scroll` > lines | Claude Code window: #201C1C body, #3C3C38 bar |
| Welcome | `.cl-welcome` > `i.cl-logo` + `.cl-hdr` (`<b>Claude Code</b> <span>v2.1.175</span><br><span>Opus 5.5 · Claude Max</span><br><span>/Users/…</span>`) | the pixel-logo header |
| Prompt | `.cl-prompt.cl-l` > `.cl-field` > `.cl-text` with `<span class="cl-slash">/cmd</span>` | the "> " band; type it with `AR.composer(tl, sel, t, null)` |
| Lines | `.cl-l`; `.cl-l.cl-tool` > `<i class="cl-dot"></i><b>Fetch</b>(args)` (green; `.cl-run` grey, `.cl-err` red, `.cl-warn` coral); `.cl-l.cl-out` (└ result; `.cl-cont` drops the └); `.cl-ind`, `.cl-ind2`, `.cl-gap`, `.cl-sum` (✓ summary); colours `.cl-dim`, `.cl-faint`, `.cl-ok-c`, `.cl-coral-c` | terminal output |
| Status | `.cl-l.cl-status` > `i.cl-glyph` + `Verb… <span class="cl-meta">(esc to interrupt · <b class="cl-secs">0</b>s · ↓ <b class="cl-tok">0.0</b>k tokens)</span>` | spinner line for `AR.status` |
| Todos | `.cl-todos` > `.cl-todo` (`data-state="active"`/`"done"`) > `i.cl-cb` + `span.cl-tt` | terminal checklist |
| Terminal bars | `.cl-bars` > `.cl-brow` > `<b>AAPL</b>` + `span.cl-bar[data-v]` > `<i></i><em>22.04%</em>` (optional `.cl-bars-head`; `.cl-b2` is a coral second series) | inline bar chart |
| App | `.cl-app` (+ `.cl-dark` #242424 / sidebar #201C1C / input #30302C; + `.cl-dark.cl-deep` near-black; + `.cl-dense`) > [`.cl-side`] + `.cl-main` > `.cl-top` + `.cl-thread` > `.cl-flow` [+ `.cl-dock` > `.cl-composer`] | Claude desktop/web window |
| Top bar | `.cl-top` > `.cl-lights` + `i.cl-sideico[data-cl-icon=sidebar]` + `.cl-title` + `.cl-right` > `.cl-btn` | title and Share |
| Sidebar | `.cl-side` > `.cl-side-top` + `.cl-new` (`.cl-plus`) + `.cl-nav` rows + `<h6>Recents</h6>` + `.cl-recents` > `.cl-recent` (`.on`) + `.cl-me` (`.cl-ava`, name with `<small>` plan) | Recents list |
| Chat parts | `.cl-user` (bubble); `.cl-reply` (serif); `.cl-used` ("Used X skill ›"); `.cl-statusrow` > `i.cl-spark` + text; `.cl-actions` (thumbs, copy, Retry); `.cl-widget` ("Dashboard · 4 messages to answer") | message pieces |
| Steps rail | `.cl-steps` > `.cl-step` > `span.cl-sico` (icon, `.cl-spark`, or `.cl-sico.cl-tile` holding a logo slot) + label with an `<em>` grey suffix; `i.cl-rail` inside a step joins it to the one above | Working / Using the duel skill / Asking ChatGPT |
| Search | `.cl-search` > `.cl-shead` (globe, label, `.cl-q`, `.cl-n`) + `.cl-sbox` > `.cl-sres` > `.cl-fav` slot + `.cl-st` + `.cl-sd` | web search with favicon rows |
| Agent card | `.cl-agent` > `.cl-alogo` slot + `.cl-ahead` ("GPT-6 Astra <span>Round 1 · Attack</span>") + `.cl-abody` | another model's reply inside the chat |
| Artifact chip | `.cl-art` > `.cl-art-ico` + `.cl-art-txt` (`.cl-art-t`, `.cl-art-s` "Document · lock · Only you") + `.cl-btn` Open | chip under the answer |
| Toggle chip | `.cl-togchip` > `.cl-switch` + `Label · <span class="cl-onoff"><span class="cl-off">Off</span><span class="cl-on">On</span></span>` | "Cheapest model · On" |
| Composer | `.cl-composer` > `.cl-field` (> `span.cl-ph`) + `.cl-crow` (`.cl-sq` +, `.cl-seg` Chat/Cowork with `span.on`, `.cl-model` "Opus 5.5" with optional `<em>Extra</em>`, `.cl-cico` mic, `.cl-sendslot` > `.cl-voice` + `.cl-send`) | input box |
| Home | `.cl-home` > `.cl-greet` (`i.cl-spark` + `<span>Good afternoon, Name</span>`) + `.cl-composer` + `.cl-chips` > `.cl-chip` | Claude home |
| Pane | `.cl-pane` > `.cl-pane-top` + `.cl-pane-tools` (Tabs, icons, `.cl-sep`) + `.cl-pane-body` > `.cl-doc` | artifact pane |
| Split view | `.cl-app.cl-split` with `.cl-main` and `.cl-pane` as direct children; widths `--cl-chat-w` (37%) and `--cl-pane-w` (63%) | chat left, doc right |
| Doc | `.cl-doc` > `.cl-doc-title` (serif) + `.cl-docmeta` > `.cl-mchip` (icon + text) or `.cl-mdot` + `.cl-h` + `.cl-p` + `span.cl-ul` (underline phrase) + `table.cl-table` (`tr.cl-row`, `.cl-cellico` > `.cl-tslot`, `.cl-sub`, `.cl-num`, `.cl-star`, `.cl-flag` slot) | doc artifact |
| Doc chart | `.cl-hchart` > per row `<span>Label</span>` + `span.cl-bar[data-v]` (`.g` green, `.c` coral) > `<i></i><em>29.4%</em>`, then `.cl-axis` > spans | bar chart in a doc |
| Doc checklist | `.cl-checks` > `.cl-checks-head` (`.cl-h` + `span.cl-ready` > `i[data-cl-icon=check]` + `<span><b>1</b> of 8 ready</span>`) + `.cl-check` (`data-on="1"` pre-ticked) > `i.cl-box` + `<b>Item</b>` + `<span>detail</span>` | "N of 8 ready" list |
| Permission | `.cl-perm` > `.cl-perm-head` (`.cl-plogo` slot, "Claude wants to use <b>X</b>", chevron) + `.cl-json` + `.cl-perm-btns` > `.cl-allow` + `.cl-deny`; result `.cl-result` (`.cl-okc`, text, `.cl-rsub`); `.cl-swapstack` puts both in one spot | tool-permission dialog |
| Slides | `.cl-slides` > `.cl-slides-top` + `.cl-slides-tools` (`.cl-tgroup`, `.cl-zoom` 66%) + `.cl-slide-stage` > `.cl-slide-frame` > `.cl-slide` (`.on`; `.cl-kick`, `.cl-big`, `.cl-subt`, `.cl-foot`) + `.cl-thumbs` > `.cl-thumb` (`.on`, `.cl-tbig`) + `i.cl-thumb-ring` | slides editor |
| Usage | `.cl-usage` > `.cl-usage-card` > `.cl-usage-head` + `.cl-meter[data-from][data-to]` > `.cl-meter-top` (label, `<span class="cl-pct">n</span>% used`) + `.cl-track` > `<i>` + `<small>Resets…</small>` | dark Usage page |
| Dashboard | `.cl-dash` > `.cl-dash-top` + `.cl-tabs` > `.cl-tab` (`.on`, `<small>1</small>`) + `.cl-tabpanes` > `.cl-tabpane` (`.on`): to-dos (`.cl-newtodo`, `.cl-dtodo` (`data-on="1"`) > `i.cl-box` + `span.cl-dt`, `.cl-dfoot`), messages (`.cl-dmsg` > `.cl-mlogo` + `.cl-mwho`/`.cl-mtxt` + `.cl-dbtn` + `.cl-dreply` > `.cl-dfield` > `.cl-field`), calendar (`.cl-dcal-day`, `.cl-dev` `.g`/`.o`), music (`.cl-dmusic-now`, `.cl-dmusic`, `.cl-prog`, `.cl-ptimes`, `.cl-pctl`) | docked dark dashboard |
| Cursor | `<div class="cl-cursor" style="left:…; top:…">` in the scene root, outside camera wrappers | pointer for `AR.clAim` + `AR.cursor` |

## Helpers

| Helper | Does |
|---|---|
| `AR.clIcons(root)` / `AR.clIcon(name)` | draws all icons, logo, spark, spinner frames, ticks, strike and underline lines, switch knobs and the cursor (idempotent; every helper calls it) / one icon's SVG |
| `AR.stream(tl, sel, t, {wps, grey, fade, times, tag, tagOff, jitter, seed})` | LLM streaming: words land at `wps` (14) with seeded jitter, grey (0.4 alpha of their colour), then darken over `fade` (0.24 s); keeps `<b>` and `.cl-ul`; `tag: "Claude"` adds the orange collaborator caret and name tag on the newest word |
| `AR.streamDur(sel, wps)` | seconds a stream takes |
| `AR.composer(tl, sel, t, text, {cps, focus, blur, send})` | types into a `.cl-field` or terminal prompt with a caret (block caret in the terminal; `text` null types the HTML's own text), hides the placeholder on the first key, lights `.cl-send` |
| `AR.composerDur(sel, text, cps)` | seconds the typing takes |
| `AR.clAim(cursorSel, targetSel, {ax, ay})` | `{x, y}` for `AR.cursor` so the tip lands on the target (centre, or fractions `ax`/`ay`). Layout positions, so it works in any scene; add any scroll or push the target has had by click time |
| `AR.termLines(tl, sel, t, {gap, times, fade, scroll, pad, sdur})` | terminal lines appear in order (`gap` 0.12; a line's `data-dt` overrides) and `.cl-scroll` scrolls up when one lands below the fold |
| `AR.clScroll(tl, sel, t, y, {dur, ease, offset})` | scrolls a `.cl-scroll`, `.cl-flow` or `.cl-doc` to `y` px or an element, continuing from where `termLines` stopped (generic pages: `AR.scrollTo` in motion.js) |
| `AR.status(tl, sel, t, dur, {secs:[a,b], tokens:[a,b], fps, stop})` | the spinner glyph cycles, `.cl-secs` ticks seconds and `.cl-tok` counts k-tokens over `dur`; the line greys at the end (`stop: false` keeps it coral) |
| `AR.checklist(tl, sel, t, {gap, times, active})` | terminal `.cl-todo`s go done (green ✓, grey strike) `gap` (0.14) apart while the next goes active; doc `.cl-check`s tick, `.cl-ready` counts "N of M ready" and turns green with ✓ at M of M (Jake uses 0.11 s) |
| `AR.clBars(tl, sel, t, {max, len, dur, gap})` | each `.cl-bar[data-v]` grows to v/max × len while its `<em>` counts in its own format |
| `AR.clSpark(tl, sel, t, dur, {turns})` | the coral starburst turns while Claude works |
| `AR.clSteps(tl, sel, t, {gap, times})` | steps fade up one by one (`gap` 0.3); `.cl-rail` lines draw down |
| `AR.clRows(tl, sel, t, {gap, dy, dur})` | rows populate (`gap` 0.07); `<tr>` rows fade only |
| `AR.clToggle(tl, sel, t, {color})` | the switch flips on: knob slides, track turns blue, Off becomes On |
| `AR.clUnderline(tl, sel, t, dur)` | the green underline draws under a `.cl-ul` phrase |
| `AR.clSplit(tl, sel, t, {to, dur, ease})` | opens the split view (start the app at `--cl-chat-w: 100%`; `dur: 0` cuts) |
| `AR.clFocus(tl, sel, t, {scale, x, y, dur, ease})` | split view to doc: the chat slides out left, the pane fills the window, its bars leave, the doc scales to `scale` (1.45) |
| `AR.clAllow(tl, sel, t, {deny, hold, result})` | Allow once (or Deny) presses, the dialog folds, `result` fades up in its place |
| `AR.clSlide(tl, sel, t, i, {thumb, dur, punch})` | cuts to slide i; the selection ring jumps to thumbnail `thumb` |
| `AR.clUsage(tl, sel, t, dur, {gap})` | meters fill from `data-from` to `data-to` % while `.cl-pct` counts |
| `AR.clTab(tl, sel, t, i)` | the tabbed widget cuts to tab i |
| `AR.clTodo(tl, sel, t)` | a dashboard to-do checks and strikes; `.cl-dfoot` recounts ("2 open · 2 done"); call in time order |
| `AR.clReply(tl, sel, t, {text, cps, h})` | Reply presses, the reply field opens with a focus ring, `text` types into it |

## Blueprints (wide, 1280x630; all cut in finished)

| Blueprint | Moment |
|---|---|
| `claude-code` | a skill runs in the Claude Code terminal: the command types, tool lines stream with └ results, the status ticks seconds and tokens while todos tick, bars grow and count, the camera snaps onto the result |
| `claude-chat` | question, "Used X skill", the serif answer streams, artifact chip, cut to the split view where Claude writes the doc under its cursor tag and table rows populate, zoom onto the doc, green underline |
| `claude-home` | greeting, the prompt types, send turns coral, the cursor clicks it, cut to the new conversation (`cl-dark` for dark) |
| `permission` | "Claude wants to use Place Stock Order": the cursor clicks Allow once, the dialog folds, the result and answer take its place |

`AR.clAim` measures at build time: a target inside a scrolled or pushed wrapper needs that move added by hand.
`AR.status` greys its line at the end rather than removing it.
