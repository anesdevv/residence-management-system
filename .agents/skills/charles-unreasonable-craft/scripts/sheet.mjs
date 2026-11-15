#!/usr/bin/env node
/* Contact sheets from a screen recording (iOS Simulator, browser, anything ffmpeg
   reads), for reading motion frame by frame.

   node sheet.mjs <video> <sheet.png> [options]

   --auto          start at the last still frame before the screen changes (the tap)
   --from 0        start, in ms into the video (with --auto: where to start looking)
   --for 1000      how many ms to show
   --step <ms>     ms between tiles (default: every frame)
   --fps 60        resample rate. Simulator recordings are variable-rate (a frame is
                   only written when the screen changes), so they're resampled
   --crop x,y,w,h  crop, in the video's pixels, before scaling
   --cols 8 --tile 240   sheet columns and tile width (px)
   --keep <dir>    also keep the full-resolution frames, to measure with edges.mjs
   --threshold 3   changed pixels (in a 160x160 thumbnail) that count as motion, for --auto

   Tiles are labelled in ms after the start. */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { contactSheet, fail, parseArgs } from "./lib.mjs";

const a = parseArgs(process.argv.slice(2), ["auto"]);
const [video, out] = a._;
if (!video || !out) fail("usage: node sheet.mjs <video> <sheet.png> [--auto] [--for 1000] (options are listed at the top of this file)");
if (!fs.existsSync(video)) fail(`no such video: ${video}`);
try {
  execFileSync("ffmpeg", ["-version"], { stdio: "ignore" });
} catch {
  fail("ffmpeg not found. Install it (brew install ffmpeg).");
}
const fps = Number(a.fps ?? 60);
const frame = 1000 / fps;
const duration = Number(a.for ?? 1000);
const step = Number(a.step ?? frame);
const crop = a.crop ? a.crop.split(",").map(Number) : null;
let start = Number(a.from ?? 0);

if (a.auto) {
  // Small grayscale frames are enough to find where motion begins. A pixel counts
  // as changed when it moves more than 24 levels (compression noise stays below
  // that); motion starts at the first frame with --threshold changed pixels.
  const side = 160;
  const size = side * side;
  const raw = execFileSync(
    "ffmpeg",
    ["-v", "error", "-ss", String(start / 1000), "-i", video, "-vf", `fps=${fps},scale=${side}:${side},format=gray`, "-f", "rawvideo", "-"],
    { maxBuffer: 1 << 30 },
  );
  const count = Math.floor(raw.length / size);
  const threshold = Number(a.threshold ?? 3);
  let onset = -1;
  for (let i = 1; i < count && onset < 0; i++) {
    let changed = 0;
    for (let k = 0; k < size; k++) if (Math.abs(raw[i * size + k] - raw[k]) > 24) changed++;
    if (changed >= threshold) onset = i;
  }
  if (onset < 0) fail(`nothing changes on screen after ${start} ms (try a lower --threshold)`);
  start += (onset - 1) * frame;
}

const dir = fs.mkdtempSync(path.join(os.tmpdir(), "uc-frames-"));
const filters = [`fps=${fps}`, crop && `crop=${crop[2]}:${crop[3]}:${crop[0]}:${crop[1]}`].filter(Boolean).join(",");
execFileSync("ffmpeg", [
  "-v", "error", "-ss", String(start / 1000), "-i", video,
  "-t", String((duration + frame) / 1000), "-vf", filters, path.join(dir, "%05d.png"),
]);
const files = fs.readdirSync(dir).filter((f) => f.endsWith(".png")).sort();
if (!files.length) fail(`no frames between ${Math.round(start)} and ${Math.round(start + duration)} ms`);

const tiles = [];
for (let t = 0; t <= duration + 0.001; t += step) {
  const index = Math.round(t / frame);
  if (index >= files.length) break;
  tiles.push({ input: path.join(dir, files[index]), label: `${Math.round(t)} ms`, t: Math.round(t) });
}
await contactSheet(tiles, out, { cols: Number(a.cols ?? 8), width: Number(a.tile ?? 240) });
if (a.keep) {
  fs.mkdirSync(a.keep, { recursive: true });
  for (const { input, t } of tiles) fs.copyFileSync(input, path.join(a.keep, `${String(t).padStart(5, "0")}ms.png`));
}
fs.rmSync(dir, { recursive: true, force: true });
console.log(`${out}: ${tiles.length} frames from ${Math.round(start)} ms${a.keep ? `, full-size frames in ${a.keep}` : ""}`);
