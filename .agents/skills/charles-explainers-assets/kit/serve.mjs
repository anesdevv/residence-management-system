/* Shared by render.mjs and check.mjs: read a project's explain.json, serve the kit at /kit/ and the project at /,
   and open an asset's page in headless Chrome. */
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright-core';

export const kit = path.dirname(new URL(import.meta.url).pathname);

export function args(argv, withValue) {
  const pos = [], opt = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) { pos.push(a); continue; }
    const k = a.slice(2);
    if (withValue.includes(k)) opt[k] = argv[++i]; else opt[k] = true;
  }
  return { pos, opt };
}

export function project(dir) {
  const root = path.resolve(dir || '.');
  const file = path.join(root, 'explain.json');
  if (!fs.existsSync(file)) throw new Error(`no explain.json in ${root}`);
  const ex = JSON.parse(fs.readFileSync(file, 'utf8'));
  const assets = (ex.lines || []).flatMap((l) => (l.assets || []).map((a) => ({ ...a, lineId: l.id })));
  const slot = { w: 1080, h: 960, scale: 1, ...(ex.slot || {}) };
  return { root, ex, assets, slot };
}

// The phone check's moments for an asset: its own "check" list; for a flip, mid-before, 0.1 s either side of the
// change and mid-after, from "win" { b, a } (default 1.5 and 2.0 s); for anything else, its opening, a third and two
// thirds through, and its end pose. `page` is { fix: T_FIX, dur: DUR, info: ASSET } from the asset's page.
export function checkTimes(asset, { fix, dur, info }) {
  const win = { b: 1.5, a: 2.0, ...(info.win || {}) };
  return (info.check || (fix != null && asset.form === 'flip'
    ? [fix - win.b / 2, fix - 0.1, fix + 0.1, fix + win.a / 2]
    : [0.1, dur / 3, (2 * dur) / 3, dur - 0.05])).map((t) => +t.toFixed(3));
}

// What an alpha clip is checked over: the asset's or the slot's checkBg (a frame of the footage), else dark grey.
export const checkBg = (P, asset) => asset.checkBg || P.slot.checkBg || null;

export async function start(root) {
  const server = Bun.serve({
    port: 0,
    fetch(req) {
      let p = decodeURIComponent(new URL(req.url).pathname);
      if (p.endsWith('/')) p += 'index.html';
      const [base, rel] = p.startsWith('/kit/') ? [kit, p.slice(5)] : [root, p.slice(1)];
      const file = path.join(base, path.normalize(rel));
      if (!file.startsWith(base) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return new Response('not found', { status: 404 });
      return new Response(Bun.file(file));
    },
  });
  const CHROME = [process.env.CHROME_PATH, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'].find((p) => p && fs.existsSync(p));
  if (!CHROME) throw new Error('needs Google Chrome in /Applications, or CHROME_PATH');
  const browser = await chromium.launch({ headless: true, executablePath: CHROME, args: ['--force-color-profile=srgb', '--hide-scrollbars', '--font-render-hinting=none'] });
  const open = async (asset, slot, scale, extra = '') => {
    const page = await browser.newPage({ viewport: { width: slot.w, height: slot.h }, deviceScaleFactor: scale });
    page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log(`[${asset.id}] ${m.type()}: ${m.text()}`); });
    page.on('pageerror', (e) => console.log(`[${asset.id}] page error: ${e.message}`));
    await page.goto(`http://localhost:${server.port}/kit/index.html?asset=${encodeURIComponent(asset.id)}${extra}`, { waitUntil: 'load' });
    await page.evaluate(() => window.ready);
    return page;
  };
  const stop = async () => { await browser.close(); server.stop(true); };
  return { open, stop };
}
