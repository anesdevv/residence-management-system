#!/usr/bin/env bun
/* The phone check (SKILL.md, Phone check, step 1). For each asset, frames at the moments that matter, cropped to the
   band the viewer sees and shrunk to the slot's width on a phone (its width in the final frame x 0.36, so the
   hack-reel card at scale 0.72 comes out 280 px wide), with the state tag drawn on as the list kit draws it.

     bun <kit>/check.mjs <project>                  # check/<id>.png per asset and check/phone.png with all of them
     bun <kit>/check.mjs <project> --only 01-a
     bun <kit>/check.mjs <project> --times 3.6,4.1  # these times for every asset

   Times: a scene's or asset's "check" list if it has one. Otherwise, for a flip, mid-before, 0.1 s either side of
   the change and mid-after, from "win" { b, a } (the seconds the edit shows on each side, default 1.5 and 2.0);
   for anything else, its opening, a third and two thirds through, and its end pose. */
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { args as parse, project, start, checkTimes, checkBg } from './serve.mjs';

const { pos, opt } = parse(process.argv.slice(2), ['only', 'times']);
const P = project(pos[0]);
const only = opt.only ? String(opt.only).split(',') : null;
const fixed = opt.times ? String(opt.times).split(',').map(Number) : null;
const list = P.assets.filter((a) => a.render !== false && (!only || only.includes(a.id)));
const band = P.slot.band || [0, P.slot.h];
const PW = Math.round(P.slot.w * P.slot.scale * 0.36);
// An alpha clip is checked over what it will sit on (checkBg in serve.mjs).
const bgIn = (asset) => (checkBg(P, asset) ? ['-i', path.resolve(P.root, checkBg(P, asset))] : ['-f', 'lavfi', '-i', 'color=c=0x3a3a3a:s=16x16']);
const outDir = path.join(P.root, 'check'), tmp = path.join(P.root, 'build', 'check');
fs.mkdirSync(outDir, { recursive: true }); fs.mkdirSync(tmp, { recursive: true });
const ff = (a) => { const r = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', ...a], { stdio: 'inherit' }); if (r.status !== 0) throw new Error('ffmpeg failed'); };
const S = await start(P.root);
const strips = [];
for (const asset of list) {
  const page = await S.open(asset, P.slot, 2, '&tag');
  const times = fixed || checkTimes(asset, await page.evaluate(() => ({ fix: window.T_FIX, dur: window.DUR, info: window.ASSET })));
  const files = [];
  for (const [i, t] of times.entries()) {
    const big = path.join(tmp, `${asset.id}-${i}-big.png`), small = path.join(tmp, `${asset.id}-${i}.png`);
    await page.evaluate((t) => window.seek(t), t);
    await page.screenshot({ path: big, clip: { x: 0, y: band[0], width: P.slot.w, height: band[1] - band[0] }, omitBackground: !!asset.alpha });
    if (asset.alpha) ff([...bgIn(asset), '-i', big, '-filter_complex', `[0:v][1:v]scale2ref[bg][fg];[bg][fg]overlay=format=auto,scale=${PW}:-2:flags=area`, '-frames:v', '1', small]);
    else ff(['-i', big, '-vf', `scale=${PW}:-2:flags=area`, small]);
    files.push(small);
  }
  await page.close();
  const strip = path.join(outDir, `${asset.id}.png`);
  ff([...files.flatMap((f) => ['-i', f]), '-filter_complex', `${files.map((_, i) => `[${i}:v]pad=iw+8:ih:0:0:white[p${i}]`).join(';')};${files.map((_, i) => `[p${i}]`).join('')}hstack=inputs=${files.length}[o]`, '-map', '[o]', strip]);
  strips.push({ file: strip, w: files.length * (PW + 8) });
  console.log(`${path.relative(P.root, strip)}  t = ${times.join(', ')}`);
}
if (strips.length) {
  const sheet = path.join(outDir, 'phone.png');
  // Strips with more frames (an asset with its own "check" list) are wider: pad every strip to the widest.
  const W = Math.max(...strips.map((s) => s.w));
  if (strips.length === 1) fs.copyFileSync(strips[0].file, sheet);
  else ff([...strips.flatMap((s) => ['-i', s.file]), '-filter_complex', `${strips.map((_, i) => `[${i}:v]pad=${W}:ih+8:0:0:white[p${i}]`).join(';')};${strips.map((_, i) => `[p${i}]`).join('')}vstack=inputs=${strips.length}[o]`, '-map', '[o]', sheet]);
  console.log(path.relative(P.root, sheet));
}
await S.stop();
