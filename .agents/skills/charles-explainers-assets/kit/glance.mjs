#!/usr/bin/env bun
/* The muted glance (SKILL.md, Phone check, step 2). An agent can't play video, so it reads a clip as a grid of
   frames 0.06 s apart, left to right, each cropped to the band, shrunk to the slot's width on a phone and stamped
   with its time. An alpha clip sits over its checkBg (a frame of the footage) or dark grey. A flip covers the window
   the edit shows around its change ("win"); anything else, the whole clip.

     bun <kit>/glance.mjs <project>                                  # check/glance/<id>.png per asset
     bun <kit>/glance.mjs <project> --only 01-a --step 0.1 --cols 6 --range 3.5,6 */
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { args as parse, project, start, checkBg } from './serve.mjs';

const { pos, opt } = parse(process.argv.slice(2), ['only', 'step', 'cols', 'range']);
const P = project(pos[0]);
const only = opt.only ? String(opt.only).split(',') : null;
const step = Number(opt.step || 0.06), cols = Number(opt.cols || 5);
const band = P.slot.band || [0, P.slot.h];
const PW = Math.round(P.slot.w * P.slot.scale * 0.36);
const outDir = path.join(P.root, 'check', 'glance');
fs.mkdirSync(outDir, { recursive: true });
const ff = (a) => { const r = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', ...a], { stdio: 'inherit' }); if (r.status !== 0) throw new Error('ffmpeg failed'); };
const S = await start(P.root);
for (const asset of P.assets.filter((a) => a.render !== false && (!only || only.includes(a.id)))) {
  const page = await S.open(asset, P.slot, 1);
  const bg = asset.alpha ? (checkBg(P, asset) ? `url("/${checkBg(P, asset)}") center / cover` : '#3a3a3a') : null;
  const { fix, dur, info } = await page.evaluate(([bg, top]) => {
    if (bg) {   // the footage under an alpha clip, as the reel will show it
      document.documentElement.classList.remove('alpha');
      document.documentElement.style.background = bg;
      document.body.style.background = document.getElementById('panel').style.background = 'transparent';
    }
    const l = document.createElement('div');
    l.id = 'glance-t';
    Object.assign(l.style, { position: 'fixed', right: '10px', top: `${top + 8}px`, zIndex: 999, padding: '1px 9px', borderRadius: '7px',
      font: '600 24px/1.3 Inter, sans-serif', color: '#fff', background: 'rgb(0 0 0 / 0.6)' });
    document.body.appendChild(l);
    return { fix: window.T_FIX, dur: window.DUR, info: window.ASSET };
  }, [bg, band[0]]);
  const win = { b: 1.5, a: 2.0, ...(info.win || {}) };
  const [from, to] = opt.range ? String(opt.range).split(',').map(Number)
    : fix != null && asset.form === 'flip' ? [Math.max(0, fix - win.b), Math.min(dur, fix + win.a)] : [0, dur];
  const dir = path.join(P.root, 'build', 'glance', asset.id);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  let n = 0;
  for (let t = from; t <= to + 1e-6; t += step, n++) {
    await page.evaluate((t) => { window.seek(t); document.getElementById('glance-t').textContent = t.toFixed(2); }, t);
    await page.screenshot({ path: path.join(dir, `f${String(n).padStart(3, '0')}.png`), clip: { x: 0, y: band[0], width: P.slot.w, height: band[1] - band[0] } });
  }
  await page.close();
  const out = path.join(outDir, `${asset.id}.png`);
  ff(['-framerate', '1', '-i', path.join(dir, 'f%03d.png'), '-vf', `scale=${PW}:-2:flags=area,pad=iw+6:ih+6:0:0:white,tile=${cols}x${Math.ceil(n / cols)}:color=white`, '-frames:v', '1', out]);
  console.log(`${path.relative(P.root, out)}  ${n} frames, ${from.toFixed(2)}-${to.toFixed(2)} s`);
}
await S.stop();
