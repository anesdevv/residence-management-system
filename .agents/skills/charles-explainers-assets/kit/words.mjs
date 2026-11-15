#!/usr/bin/env bun
/* The words check (SKILL.md, Words on screen; Phone check, step 4), measured in the page instead of eyeballed.
   - At each phone-check moment, every visible text in the band: its size in the final frame (font size x the scale
     it's drawn at x the slot's scale) against 26 px, 24 px for code and 30 px for a tab, and its contrast against
     the nearest opaque background behind it, against 4.5:1. Copy from 20 to 26 px is listed apart: it passes only
     as part of the picture, where the lesson isn't (SKILL.md, Sizes). So is text under 0.6 opacity: it passes only
     if it's dimmed on purpose as the lesson. Text with nothing opaque behind it in an alpha clip sits on the
     footage, so it's listed for a check by eye.
   - Each timed word in explain.json (kind tab, tag or caption, with in and out, not chrome): its characters a second
     from fully in (its fullyIn, else its in) to its out, against the 15 aim and the 20 cap.

     bun <kit>/words.mjs <project> [--only 01-a] [--times 3.6,4.1] */
import { args as parse, project, start, checkTimes } from './serve.mjs';

const { pos, opt } = parse(process.argv.slice(2), ['only', 'times']);
const P = project(pos[0]);
const only = opt.only ? String(opt.only).split(',') : null;
const fixed = opt.times ? String(opt.times).split(',').map(Number) : null;
const band = P.slot.band || [0, P.slot.h];
const S = await start(P.root);
let issues = 0;
for (const asset of P.assets.filter((a) => a.render !== false && (!only || only.includes(a.id)))) {
  const out = new Map(), dimmed = new Map(), footage = new Map(), picture = new Map();
  for (const w of asset.words || []) {
    if (!['tab', 'tag', 'caption'].includes(w.kind) || w.chrome || w.in == null || w.out == null) continue;
    const from = w.fullyIn ?? w.in, cps = w.text.length / Math.max(0.01, w.out - from);
    if (cps > 15) { out.set(`rate ${w.text}`, `"${w.text}": ${w.text.length} characters in ${(w.out - from).toFixed(2)} s = ${cps.toFixed(1)} a second, ${cps > 20 ? 'OVER the 20 cap' : 'over the 15 aim'}`); if (cps > 20) issues++; }
  }
  const page = await S.open(asset, P.slot, 1);
  const times = fixed || checkTimes(asset, await page.evaluate(() => ({ fix: window.T_FIX, dur: window.DUR, info: window.ASSET })));
  for (const t of times) {
    const found = await page.evaluate(([t, band, scale]) => {
      window.seek(t);
      const cv = (window.__wc ||= document.createElement('canvas')); cv.width = cv.height = 1;
      const cx = cv.getContext('2d', { willReadFrequently: true });
      const rgba = (c) => { cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1); const d = cx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; };
      const lum = ([r, g, b]) => [r, g, b].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }).reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0);
      const res = [];
      for (const e of document.querySelectorAll('#panel *')) {
        if (!(e instanceof HTMLElement) || e.id === 'glance-t') continue;
        const own = [...e.childNodes].filter((n) => n.nodeType === 3 && n.textContent.trim()).map((n) => n.textContent.trim()).join(' ');
        if (!own) continue;
        let op = 1, shown = true;
        for (let a = e; a; a = a.parentElement) { const cs = getComputedStyle(a); op *= Number(cs.opacity); if (cs.visibility === 'hidden' || cs.display === 'none') shown = false; if (a.id === 'panel') break; }
        const r = e.getBoundingClientRect();
        if (!shown || op < 0.05 || r.width < 1 || r.bottom < band[0] || r.top > band[1]) continue;
        const cs = getComputedStyle(e);
        const size = parseFloat(cs.fontSize) * (e.offsetHeight ? r.height / e.offsetHeight : 1) * scale;
        // What's behind the text: the topmost opaque background under its middle (a card can be a sibling, not a
        // parent), else its nearest opaque ancestor (elementsFromPoint skips pointer-events: none). An opaque thing
        // painted above the text (a scrim, the toast stacked over it) covers it.
        const stack = document.elementsFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        const self = stack.findIndex((a) => a === e || a.contains(e));
        let bg = null, covered = false;
        for (const [i, a] of stack.entries()) {
          if (a !== e && e.contains(a)) continue;
          const b = rgba(getComputedStyle(a).backgroundColor); if (b[3] > 0.5) { bg = b; covered = self >= 0 && i < self; break; }
        }
        for (let a = e; a && !bg; a = a.parentElement) { const b = rgba(getComputedStyle(a).backgroundColor); if (b[3] > 0.5) bg = b; }
        if (covered) continue;
        const fg = rgba(cs.color), mix = bg ? fg.slice(0, 3).map((v, i) => v * fg[3] + bg[i] * (1 - fg[3])) : null;
        const cr = bg ? (Math.max(lum(mix), lum(bg)) + 0.05) / (Math.min(lum(mix), lum(bg)) + 0.05) : null;
        const kind = e.closest('.tab') ? 'tab' : /JBM|mono/i.test(cs.fontFamily) ? 'code' : 'text';
        res.push({ text: own.slice(0, 32), size: +size.toFixed(1), kind, cr: cr && +cr.toFixed(2), op: +op.toFixed(2) });
      }
      return res;
    }, [t, band, P.slot.scale]);
    for (const f of found) {
      const min = { tab: 30, code: 24, text: 26 }[f.kind], small = f.size < min - 0.3, low = f.cr != null && f.cr < 4.5;
      const what = `"${f.text}" (${f.kind}): ${f.size} px${small ? ` UNDER ${min}` : ''}${f.cr != null ? `, ${f.cr}:1${low ? ' UNDER 4.5' : ''}` : ''}`;
      if (f.op < 0.6) { if (small || low) dimmed.set(f.text, `${what}, opacity ${f.op}, at ${t} s`); continue; }
      if (f.cr == null) footage.set(f.text, `${what}, over the footage, at ${t} s`);
      if (f.kind === 'text' && small && !low && f.size >= 19) { picture.set(f.text, `${what} at ${t} s`); continue; }
      if ((small || low) && !out.has(f.text)) { out.set(f.text, `${what} at ${t} s`); issues++; }
    }
  }
  await page.close();
  console.log(`${asset.id}  (t = ${times.join(', ')})`);
  for (const v of out.values()) console.log(`  ${v}`);
  for (const v of picture.values()) console.log(`  part of the picture only: ${v}`);
  for (const v of dimmed.values()) console.log(`  dimmed: ${v}`);
  for (const v of footage.values()) console.log(`  check by eye: ${v}`);
}
await S.stop();
console.log(issues ? `${issues} to fix` : 'every word is big enough, clear enough and slow enough');
