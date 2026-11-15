#!/usr/bin/env bun
/* Renders a project's explainer assets. Each scene is a pure function of time (window.seek), so this steps it one
   frame at a time in headless Chrome, screenshots every frame and encodes the clip with ffmpeg.

     bun <kit>/render.mjs <project>                    # every asset in explain.json, plus its stills
     bun <kit>/render.mjs <project> --only 01-a,03-b   # just these
     bun <kit>/render.mjs <project> --stills 4.0,5.2   # PNGs at these times instead of clips (to check a scene)

   Output: <project>/assets/<id>.mp4 (H.264, or ProRes 4444 with alpha as <id>.mov for an asset with "alpha": true)
   and <project>/assets/stills/<id>-<name>.png. Frames go to <project>/build/ and are deleted after encoding.
   Options: --jobs 4 (pages at once), --fps and --scale override explain.json's render { fps: 60, scale: 2 }. */
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { args as parse, project, start } from './serve.mjs';

const { pos, opt } = parse(process.argv.slice(2), ['only', 'stills', 'jobs', 'fps', 'scale']);
const P = project(pos[0]);
const fps = Number(opt.fps || P.ex.render?.fps || 60);
const scale = Number(opt.scale || P.ex.render?.scale || 2);
const jobs = Number(opt.jobs || 4);
const only = opt.only ? String(opt.only).split(',') : null;
const stillTimes = opt.stills ? String(opt.stills).split(',').map(Number) : null;
const list = P.assets.filter((a) => a.render !== false && (!only || only.includes(a.id)));
if (!list.length) throw new Error('nothing to render: check --only against the asset ids in explain.json');
const outDir = path.join(P.root, 'assets');
const ff = (a) => { const r = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', ...a], { stdio: 'inherit' }); if (r.status !== 0) throw new Error('ffmpeg failed'); };
const S = await start(P.root);

async function stills(asset) {
  const page = await S.open(asset, P.slot, scale);
  const dir = path.join(P.root, 'build', 'stills');
  fs.mkdirSync(dir, { recursive: true });
  for (const t of stillTimes) {
    await page.evaluate((t) => window.seek(t), t);
    await page.screenshot({ path: path.join(dir, `${asset.id}-t${t.toFixed(2)}.png`), omitBackground: !!asset.alpha });
  }
  await page.close();
  console.log(`${asset.id}: ${stillTimes.length} stills in ${dir}`);
}

async function clip(asset) {
  const t0 = Date.now();
  const page = await S.open(asset, P.slot, scale);
  const { dur, fix, info } = await page.evaluate(() => ({ dur: window.DUR, fix: window.T_FIX, info: window.ASSET }));
  const frames = Math.round(dur * fps);
  const dir = path.join(P.root, 'build', `frames-${asset.id}`);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  fs.mkdirSync(path.join(outDir, 'stills'), { recursive: true });
  const ext = asset.alpha ? 'png' : 'jpg';
  for (let i = 0; i < frames; i++) {
    await page.evaluate((t) => window.seek(t), i / fps);
    await page.screenshot({ path: path.join(dir, `f${String(i).padStart(4, '0')}.${ext}`), ...(asset.alpha ? { omitBackground: true } : { type: 'jpeg', quality: 95 }) });
  }
  const st = { ...(fix != null ? { before: fix - 0.3, after: fix + 0.3 } : { mid: dur / 2 }), ...(info.stills || {}) };
  for (const [name, t] of Object.entries(st)) {
    await page.evaluate((t) => window.seek(t), t);
    await page.screenshot({ path: path.join(outDir, 'stills', `${asset.id}-${name}.png`), omitBackground: !!asset.alpha });
  }
  await page.close();
  const out = path.join(outDir, `${asset.id}.${asset.alpha ? 'mov' : 'mp4'}`);
  const enc = asset.alpha
    ? ['-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', '-vendor', 'apl0']
    : ['-c:v', 'libx264', '-preset', 'slow', '-crf', '15', '-pix_fmt', 'yuv420p', '-movflags', '+faststart'];
  ff(['-framerate', String(fps), '-i', path.join(dir, `f%04d.${ext}`), ...enc, out]);
  fs.rmSync(dir, { recursive: true, force: true });
  console.log(`${path.relative(P.root, out)}: ${frames} frames in ${((Date.now() - t0) / 1000).toFixed(0)} s`);
}

const started = Date.now();
const queue = [...list];
const run = stillTimes ? stills : clip;
await Promise.all(Array.from({ length: Math.min(jobs, queue.length) }, async () => { while (queue.length) await run(queue.shift()); }));
await S.stop();
console.log(`done in ${((Date.now() - started) / 1000).toFixed(0)} s`);
