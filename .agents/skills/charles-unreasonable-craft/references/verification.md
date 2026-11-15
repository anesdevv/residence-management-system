# Verification

How to capture the work, read its motion frame by frame, and measure it. In the commands below, `<skill>` is this skill's folder and `<log>` is the design log folder. Run them from the project.

## Contents
- Capture the web
- Capture the iOS Simulator
- Read motion frame by frame
- Measure spacing and alignment
- Cover every state
- When a script fails

## Capture the web

Stills at every width, light and dark:

```bash
node <skill>/scripts/web-frames.mjs http://localhost:3000 --scheme both --out <log>/shots
```

The default widths run from a small phone to a wide desktop (360, 390, 768, 1024, 1280, 1440, 1920). Add the widths where the layout changes, with `--widths`. Add `--full` for whole pages, and `--before "<js>"` to set up a state first (open a menu, fill a form, show an error). Stills show the settled page, with entrances finished.

Motion, one PNG per frame plus a labelled contact sheet:

```bash
node <skill>/scripts/web-frames.mjs http://localhost:3000 --widths 390,1440 --motion 800 --trigger "click:#start"
```

Triggers: `load` (the entrance itself), `click:<selector>`, `hover:<selector>`, `scroll:<y>`, `js:<code>`. `--clip x,y,w,h` zooms in on one element. Time is virtual during the capture, so every frame is exact and repeatable. Capture again with `--reduced-motion`: the motion should turn into a fade or nothing, and never break.

Every run writes `console.txt`, listing console errors and warnings, page errors, failed requests and HTTP errors. It should be empty.

## Capture the iOS Simulator

```bash
<skill>/scripts/sim.sh shot <log>/shots/home.png          # full resolution, 3x on iPhone
<skill>/scripts/sim.sh start <log>/rec/open.mp4           # then do the interaction
<skill>/scripts/sim.sh stop <log>/rec/open.mp4
```

Pass a UDID or simulator name as the last argument when more than one is booted (`xcrun simctl list devices booted`), and use the one running the build you're checking. Cycle these settings too, then put them back when you're done:

```bash
xcrun simctl ui <device> appearance dark
xcrun simctl ui <device> content_size accessibility-extra-large
xcrun simctl ui <device> increase_contrast enabled
```

## Read motion frame by frame

```bash
node <skill>/scripts/sheet.mjs <log>/rec/open.mp4 <log>/rec/open-sheet.png --auto --for 800
```

`--auto` starts at the last still frame before the screen changes (the tap). `--crop x,y,w,h` (video pixels) zooms in, and `--keep <dir>` saves full-size frames to measure. Recordings only write frames when the screen changes, so a sheet ends where the motion ends.

Open the sheet and read it tile by tile. Look for:

- a jump, a pop, or a one-frame flash anywhere in the sequence
- an abrupt start or stop where the motion should ease, or easing where the response should be instant
- overshoot that never settles, or a visible wobble at the end
- straight-line paths where an arc would be natural, and arcs that kink
- anticipation and follow-through where the principle calls for them, and nothing that teleports
- layout shifting or text reflowing mid-animation, and anything clipped by its container
- things that move together arriving together, or staggered on purpose
- interruption: trigger it again mid-flight, and it should redirect from where it is, not snap back

## Measure spacing and alignment

```bash
node <skill>/scripts/edges.mjs <log>/shots/home.png --scale 3 --rows 120-160,200-260
node <skill>/scripts/edges.mjs <log>/shots/home.png --scale 3 --cols 16-60 --within 100-700
```

A `--rows` band prints each element's left and right edges and the gaps between them. A `--cols` band prints top and bottom edges and the vertical gaps. Units are points: use `--scale 3` for iPhone captures, and `--scale 2` for iPad and for web captures at the default scale. Read the screenshot first to pick the bands.

These checks caught real defects that looked fine by eye:

- **One text edge per screen.** Every column of text, label and list on a screen starts on the same line, and a screen's tabs share it.
- **Icon buttons line up by the glyph, not the tap target.** A ×, ••• or chevron ends on the content edge, even though its 44 pt target extends past it.
- **The same relationship gets the same gap everywhere:** below the header on every tab, between every card, inside every button of a kind.
- **Bleeds pay back.** A frame that bleeds into the margin pads its content back by the bleed, so that content still sits on the text edge.
- **No seams** where a photo, scrim or material meets the page.
- **Nothing peeks** around a floating button, and nothing sits under the status bar, notch or home indicator.
- **Optical centering is deliberate.** Center play triangles, arrows and odd-shaped icons by eye, then measure to confirm the offset is the one you chose.
- **No widows or orphans** in headings and short paragraphs.

## Cover every state

Capture every screen as empty, loading, error, success and offline. Also capture it with long text and a missing image, with one item and with many, and as a first run and as a returning user. Do all of that in light and dark, with reduced motion, at every screen size, and at large text sizes on native.

## When a script fails

- A missing package: `npm install --prefix <skill>/scripts`.
- No Chrome: install Google Chrome or set `CHROME_PATH`.
- No ffmpeg: `brew install ffmpeg`.
- A sandbox blocks Chrome or the simulator: rerun the command with permission to run outside the sandbox.

Don't skip verification because a tool failed. Fix the tool, or capture another way.
