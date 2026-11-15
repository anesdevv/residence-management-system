#!/usr/bin/env node
/* Measures where ink starts and stops in a full-resolution capture, so spacing and
   alignment get checked to the point instead of by eye.

   node edges.mjs <capture.png> [--rows y0-y1,...] [--cols x0-x1,...] [options]

   --rows y0-y1,...  horizontal bands: the left and right edge of each element in
                     the band, and the gaps between them
   --cols x0-x1,...  vertical bands: the top and bottom edge of each element in the
                     band, and the gaps between them
   --scale 3         pixels per point: 3 for iPhone captures, 2 for iPad and for
                     web-frames captures at its default --scale. Bands and results
                     are in points (pixels when --scale is 1, the default)
   --within a-b      limit the scan across a band to a-b (columns for --rows,
                     rows for --cols)
   --min 40          how far (0-255) a pixel must be from the band's background
                     brightness to count as ink
   --merge 6         join ink closer than this into one element, so the letters of
                     a label read as one element; use 0 to see every glyph

   The background is the band's median brightness, so measure over flat areas. Over
   a photo or a gradient, narrow the band or raise --min. */
import { fail, need, parseArgs } from "./lib.mjs";

const a = parseArgs(process.argv.slice(2));
const file = a._[0];
if (!file || (!a.rows && !a.cols)) fail("usage: node edges.mjs <capture.png> --rows y0-y1[,...] | --cols x0-x1[,...] [--scale 3]");
const sharp = (await need("sharp")).default;
const scale = Number(a.scale ?? 1);
const unit = scale === 1 ? "px" : "pt";
const min = Number(a.min ?? 40);
const merge = Number(a.merge ?? 6);
const within = a.within ? a.within.split("-").map(Number) : null;
const { data, info } = await sharp(file).greyscale().raw().toBuffer({ resolveWithObject: true });
const { width: W, height: H } = info;
const bands = (value) => (value ? String(value).split(",").map((band) => band.split("-").map(Number)) : []);
const fmt = (px) => String(Math.round((px / scale) * 10) / 10);
const clampPx = (v, max) => Math.max(0, Math.min(max, Math.round(v * scale)));

function measure(kind, [lo, hi]) {
  const rows = kind === "rows";
  const bandMax = rows ? H : W;
  const scanMax = rows ? W : H;
  const b0 = clampPx(lo, bandMax);
  const b1 = clampPx(hi, bandMax);
  const s0 = within ? clampPx(within[0], scanMax) : 0;
  const s1 = within ? clampPx(within[1], scanMax) : scanMax;
  if (b1 <= b0 || s1 <= s0) return console.log(`${kind} ${lo}-${hi}: outside the ${W}x${H} capture`);
  const pixel = (along, across) => (rows ? data[across * W + along] : data[along * W + across]);

  // Median brightness of the band, from a histogram.
  const histogram = new Uint32Array(256);
  for (let i = s0; i < s1; i++) for (let j = b0; j < b1; j++) histogram[pixel(i, j)]++;
  const half = ((s1 - s0) * (b1 - b0)) / 2;
  let background = 0;
  for (let seen = 0; background < 255 && seen + histogram[background] < half; background++) seen += histogram[background];

  const elements = [];
  let open = -1;
  for (let i = s0; i <= s1; i++) {
    let ink = false;
    if (i < s1) for (let j = b0; j < b1 && !ink; j++) ink = Math.abs(pixel(i, j) - background) > min;
    if (ink && open < 0) open = i;
    if (!ink && open >= 0) {
      const last = elements.at(-1);
      if (last && (open - last[1]) / scale < merge) last[1] = i;
      else elements.push([open, i]);
      open = -1;
    }
  }
  const [from, to] = rows ? ["left", "right"] : ["top", "bottom"];
  const head = `${kind} ${lo}-${hi} ${unit} (background ${background})`;
  if (!elements.length) return console.log(`${head}: no ink`);
  console.log(`${head}: ink ${from} ${fmt(elements[0][0])}, ${to} ${fmt(elements.at(-1)[1])}`);
  const parts = elements.map(([s, e], i) => {
    const gap = i ? `gap ${fmt(s - elements[i - 1][1])}  ` : "";
    return `${gap}[${fmt(s)} → ${fmt(e)}, ${rows ? "w" : "h"} ${fmt(e - s)}]`;
  });
  console.log(`  ${parts.join("  ")}`);
}

for (const band of bands(a.rows)) measure("rows", band);
for (const band of bands(a.cols)) measure("cols", band);
