#!/usr/bin/env node
/* Full-resolution web captures for design verification: stills at every width and
   color scheme, and exact frame-by-frame captures of motion.

   node web-frames.mjs <url | file.html> [options]

   Stills (the default):
     --widths 360,390,768,1024,1280,1440,1920   viewport widths in CSS px
     --height <px>        viewport height (default 844 below 768 wide, else 900)
     --scale 2            device pixel ratio of the captures
     --scheme light       light | dark | both
     --full               capture the whole page, not just the viewport
     --reduced-motion     emulate prefers-reduced-motion: reduce
     --before "<js>"      run in the page first (open a menu, fill a form, set a state)
     --wait 500           ms to let the page settle before capturing
     --out captures       output folder

   Motion (add --motion):
     --motion 1200        capture this many ms of motion, one PNG per frame
     --fps 60             frames per second
     --trigger load       what starts the motion: load | click:<selector> |
                          hover:<selector> | scroll:<y> | js:<code>
     --clip x,y,w,h       capture only this region (CSS px)
     --name <name>        name for the frame folder (default: the trigger)
     --cols 8 --tile 240  contact sheet columns and tile width (px)

   Writes <width>-<scheme>.png stills, or a <name>-<width>-<scheme>/ folder of frames
   plus a <name>-<width>-<scheme>-sheet.png labelled in ms, and console.txt with
   every console error or warning, page error, failed request, and HTTP error.

   Stills, and motion started by a trigger, begin from the settled page: finite
   animations (entrances, transitions) are jumped to their end and loops keep
   running. Use --trigger load to see the entrance itself.

   While capturing frames, time is virtual: timers, requestAnimationFrame and
   performance.now are faked and stepped exactly 1/fps per frame, and CSS
   transitions, CSS animations and Web Animations are paused and seeked to the same
   clock, so each frame is exact and repeatable. Scroll-driven animations are left alone. */
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { contactSheet, fail, launchChrome, parseArgs } from "./lib.mjs";

const a = parseArgs(process.argv.slice(2), ["full", "reduced-motion"]);
const target = a._[0];
if (!target) fail("usage: node web-frames.mjs <url | file.html> [options] (options are listed at the top of this file)");
const url = /^[a-z][a-z0-9+.-]*:/i.test(target) ? target : pathToFileURL(path.resolve(target)).href;
const widths = String(a.widths ?? "360,390,768,1024,1280,1440,1920").split(",").map(Number);
const scale = Number(a.scale ?? 2);
const schemes = a.scheme === "both" ? ["light", "dark"] : [a.scheme ?? "light"];
const out = path.resolve(a.out ?? "captures");
const motion = a.motion ? Number(a.motion) : 0;
const fps = Number(a.fps ?? 60);
const trigger = a.trigger ?? "load";
const name = a.name ?? trigger.split(":")[0];
const clip = a.clip ? a.clip.split(",").map(Number) : null;
const wait = Number(a.wait ?? 500);
fs.mkdirSync(out, { recursive: true });

// A string of statements, run as an async function in the page.
const run = (page, code) => page.evaluate(`(async () => { ${code} })()`);

const settle = (page) =>
  page.evaluate(async () => {
    await document.fonts?.ready;
    const pending = [...document.images].filter((img) => !img.complete);
    await Promise.all(pending.map((img) => new Promise((done) => (img.onload = img.onerror = done))));
  });

// Headless Chrome starts CSS animations lazily (on its next frame), so waiting
// doesn't settle a page. Jump every finite animation to its end, the state a
// person sees once the page has settled; loops keep running. Repeats so chained
// animations (started from animationend) settle too.
async function finishFinite(page, letTimePass) {
  for (let round = 0; round < 5; round++) {
    const finished = await page.evaluate(() => {
      let count = 0;
      for (const animation of document.getAnimations()) {
        if (animation.timeline && animation.timeline !== document.timeline) continue;
        if (animation.playState === "finished") continue;
        if (!Number.isFinite(animation.effect?.getComputedTiming().iterations)) continue;
        try {
          animation.finish();
          count++;
        } catch {}
      }
      return count;
    });
    if (!finished) return;
    await letTimePass(50);
  }
}

// Pause every document-timeline animation and seek it to virtual time t. An
// animation seen for the first time keeps the progress it already has, unless
// rewind is set (motion that started during page load is replayed from 0).
function pin([t, rewind]) {
  const origins = (window.__ucOrigins ??= new WeakMap());
  for (const animation of document.getAnimations()) {
    if (animation.timeline && animation.timeline !== document.timeline) continue;
    if (!origins.has(animation)) origins.set(animation, t - (rewind ? 0 : animation.currentTime ?? 0));
    animation.pause();
    animation.currentTime = t - origins.get(animation);
  }
}

async function start(page) {
  const [kind, ...rest] = trigger.split(":");
  const value = rest.join(":");
  if (kind === "click") await page.click(value, { force: true });
  else if (kind === "hover") await page.hover(value, { force: true });
  else if (kind === "scroll") await page.evaluate((y) => window.scrollTo({ top: y, behavior: "instant" }), Number(value));
  else if (kind === "js") await run(page, value);
  else fail(`unknown --trigger "${trigger}"`);
}

async function captureMotion(page, tag) {
  const dir = path.join(out, `${name}-${tag}`);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  const fromLoad = trigger === "load";
  // Time is frozen before the page exists, so nothing runs ahead of frame 0, and
  // the page settles in virtual time before a trigger.
  await page.clock.install();
  await page.clock.pauseAt(Date.now() + 1000);
  await page.goto(url, { waitUntil: "load" });
  await settle(page);
  if (a.before) await run(page, a.before);
  if (!fromLoad) {
    await page.clock.runFor(wait);
    await finishFinite(page, async (ms) => {
      await page.waitForTimeout(ms);
      await page.clock.runFor(ms);
    });
    await page.evaluate(pin, [0, false]);
    await start(page);
  }
  const step = 1000 / fps;
  const count = Math.floor(motion / step) + 1;
  const tiles = [];
  let now = 0;
  for (let i = 0; i < count; i++) {
    const t = Math.round(i * step);
    if (t > now) await page.clock.runFor(t - now);
    now = t;
    await page.evaluate(pin, [t, fromLoad && i === 0]);
    const file = path.join(dir, `${String(i).padStart(4, "0")}.png`);
    await page.screenshot({
      path: file,
      animations: "allow",
      ...(clip ? { clip: { x: clip[0], y: clip[1], width: clip[2], height: clip[3] } } : {}),
    });
    tiles.push({ input: file, label: `${t} ms` });
  }
  const sheet = path.join(out, `${name}-${tag}-sheet.png`);
  await contactSheet(tiles, sheet, { cols: Number(a.cols ?? 8), width: Number(a.tile ?? 240) });
  console.log(`${path.relative(process.cwd(), dir)}/ (${count} frames at ${fps} fps)  ${path.relative(process.cwd(), sheet)}`);
}

const browser = await launchChrome();
const problems = [];
for (const width of widths) {
  for (const scheme of schemes) {
    const height = Number(a.height ?? (width < 768 ? 844 : 900));
    const tag = `${width}-${scheme}`;
    const context = await browser.newContext({
      viewport: { width, height },
      deviceScaleFactor: scale,
      colorScheme: scheme,
      reducedMotion: a["reduced-motion"] ? "reduce" : "no-preference",
    });
    const page = await context.newPage();
    const note = (text) => problems.push(`[${tag}] ${text}`);
    page.on("console", (m) => ["error", "warning"].includes(m.type()) && note(`console.${m.type()}: ${m.text()}`));
    page.on("pageerror", (e) => note(`page error: ${e.message}`));
    page.on("requestfailed", (r) => note(`request failed: ${r.url()} (${r.failure()?.errorText})`));
    page.on("response", (r) => r.status() >= 400 && note(`HTTP ${r.status()}: ${r.url()}`));
    if (motion) {
      await captureMotion(page, tag);
    } else {
      await page.goto(url, { waitUntil: "load" });
      await settle(page);
      if (a.before) await run(page, a.before);
      await page.waitForTimeout(wait);
      await finishFinite(page, (ms) => page.waitForTimeout(ms));
      const file = path.join(out, `${tag}.png`);
      await page.screenshot({ path: file, fullPage: !!a.full });
      console.log(path.relative(process.cwd(), file));
    }
    await context.close();
  }
}
await browser.close();
fs.writeFileSync(path.join(out, "console.txt"), problems.length ? `${problems.join("\n")}\n` : "");
console.log(problems.length ? `console.txt: ${problems.length} problem(s). Read it.` : "console.txt: clean");
