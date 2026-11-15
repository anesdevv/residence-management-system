/* The charles-explainers-assets kit: the clock, the curves, a zoom box for drawing UI at its real CSS size, the code
   block, a finger, and the explainer layer (the coloured agent cursor, its selection box, the slow push-in and the
   definition tab). Grown from the motion-hacks kit v3 (videos/design-hacks-motion, 2026-11-12).

   Each asset is a pure function of time, so render.mjs can step it frame by frame: window.seek(t) draws the frame at
   t seconds. Never read the clock or use CSS transitions or animations inside a scene: compute the value the real
   CSS would have at time t (transition(), the curves in E, springTo()). Sizes are panel px; fpx(n) converts a size
   in the final 1080x1920 frame (26 px text, 2 px outline) into panel px for the slot's scale. */
(() => {
  let W = 1080, H = 960;
  let BAND = { top: 300, bottom: 890 }; // the part of the panel the viewer sees (setSlot)
  let SLOT_SCALE = 1; // the panel's scale into the final 1080x1920 frame (setSlot)
  const fpx = (n) => n / SLOT_SCALE; // a size in the final frame, in panel px

  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  const prog = (t, a, b) => clamp((t - a) / (b - a));
  const mix = (a, b, t) => (Array.isArray(a) ? a.map((v, i) => lerp(v, b[i], t)) : lerp(a, b, t));

  function bezier(x1, y1, x2, y2) {
    const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
    const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
    const sx = (t) => ((ax * t + bx) * t + cx) * t;
    const sy = (t) => ((ay * t + by) * t + cy) * t;
    return (x) => {
      if (x <= 0) return 0;
      if (x >= 1) return 1;
      let lo = 0, hi = 1, t = x;
      for (let i = 0; i < 50; i++) {
        const v = sx(t);
        if (Math.abs(v - x) < 1e-7) break;
        if (v < x) lo = t; else hi = t;
        t = (lo + hi) / 2;
      }
      return sy(t);
    };
  }

  /* The curves. out/inOut are Charles's defaults (charles-ux-animation: ease-out for appearing, ease-in-out for moving
     or resizing on screen); the css* ones are the CSS keywords; mInOut is Motion's "easeInOut". */
  const E = {
    linear: (x) => x,
    out: bezier(0.32, 0.72, 0, 1),
    inOut: bezier(0.77, 0, 0.175, 1),
    cssEase: bezier(0.25, 0.1, 0.25, 1),
    cssOut: bezier(0, 0, 0.58, 1),
    cssInOut: bezier(0.42, 0, 0.58, 1),
    mInOut: bezier(0.42, 0, 0.58, 1),
    move: bezier(0.65, 0, 0.35, 1), // pointer moves and code-block changes (not the demos)
    quadIn: (x) => x * x,
  };

  /* A damped spring's offset from its target, t seconds after it starts: x0 is where it starts (relative to the
     target) and v0 its starting velocity, in the same units per second. Motion's { type: "spring", stiffness: k,
     damping: c, mass: m, velocity } solves this same equation. */
  function springTo(t, { k = 400, c = 40, m = 1, x0 = 1, v0 = 0 } = {}) {
    if (t <= 0) return x0;
    const w0 = Math.sqrt(k / m), z = c / (2 * Math.sqrt(k * m));
    if (Math.abs(z - 1) < 1e-9) return (x0 + (v0 + w0 * x0) * t) * Math.exp(-w0 * t);
    if (z < 1) {
      const wd = w0 * Math.sqrt(1 - z * z);
      return Math.exp(-z * w0 * t) * (x0 * Math.cos(wd * t) + ((v0 + z * w0 * x0) / wd) * Math.sin(wd * t));
    }
    const s = Math.sqrt(z * z - 1), r1 = -w0 * (z - s), r2 = -w0 * (z + s);
    const C2 = (v0 - r1 * x0) / (r2 - r1), C1 = x0 - C2;
    return C1 * Math.exp(r1 * t) + C2 * Math.exp(r2 * t);
  }

  /* Motion's { type: "spring", duration, bounce } as stiffness and damping (mass 1), the way Motion derives them:
     damping ratio 1 − bounce, and the stiffness whose envelope settles to within 0.1% of the distance by `duration`
     (from rest; the release velocity then goes in as v0). duration 0.5, bounce 0 gives k ≈ 341, c ≈ 36.9. */
  function motionSpring(duration = 0.5, bounce = 0) {
    const z = 1 - bounce;
    const env = z >= 1 ? (w) => Math.exp(-w * duration) * (w * duration + 1) - 0.001
      : (w) => 0.001 - (z * w / (w * Math.sqrt(1 - z * z))) * Math.exp(-z * w * duration);
    let lo = 0.1, hi = 200; // env(w) falls as w grows: bisect for its root
    for (let i = 0; i < 100; i++) { const m = (lo + hi) / 2; if (env(m) > 0) lo = m; else hi = m; }
    const w = (lo + hi) / 2;
    return { k: w * w, c: 2 * z * w };
  }

  /* A CSS transition, evaluated at t: a property set to each [time, value] of `events` in turn, with the given
     duration (s) and curve. A new value starts from wherever the property is at that moment, as CSS retargets.
     Values can be numbers or arrays of numbers (colours). dur 0 jumps. */
  function transition(t, events, { dur, ease = E.cssEase, init }) {
    let from = init, to = init, t0 = -1e9;
    const at = (tt) => (dur <= 0 || tt >= t0 + dur ? to : mix(from, to, ease(clamp((tt - t0) / dur))));
    for (const [te, v] of events) {
      if (te > t) break;
      from = at(te); to = v; t0 = te;
    }
    return at(t);
  }

  /* Keyframes evenly spaced over `dur` from t0, each segment with `ease` (Motion's default for a keyframes array is
     easeInOut on every segment). Returns the first value before t0 and the last after. */
  function keyframes(t, t0, dur, values, ease = E.mInOut) {
    const u = (t - t0) / dur;
    if (u <= 0) return values[0];
    if (u >= 1) return values[values.length - 1];
    const n = values.length - 1, i = Math.min(n - 1, Math.floor(u * n));
    return lerp(values[i], values[i + 1], ease(u * n - i));
  }

  // Keyframes with explicit times: keys(t, [[t0, v0], [t1, v1, ease], ...]); each segment uses its END key's ease.
  function keys(t, k) {
    if (t <= k[0][0]) return k[0][1];
    for (let i = 1; i < k.length; i++) {
      const [t1, v1, ease = E.move] = k[i];
      const [t0, v0] = k[i - 1];
      if (t <= t1) return mix(v0, v1, ease(t1 === t0 ? 1 : (t - t0) / (t1 - t0)));
    }
    return k[k.length - 1][1];
  }

  // The last event at or before t (events sorted by time), or null.
  const lastBefore = (t, times) => { let r = null; for (const x of times) if (x <= t) r = x; return r; };

  const bump = (t, a, b) => (t <= a || t >= b ? 0 : Math.sin(Math.PI * (t - a) / (b - a)));

  /* ---------- colour ---------- */
  function hexToRgb(hex) {
    const n = parseInt(hex.replace('#', ''), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  const css = (rgb, a = 1) => `rgb(${rgb.map((v) => Math.round(clamp(v, 0, 255) * 10) / 10).join(' ')}${a < 1 ? ` / ${a}` : ''})`;

  /* ---------- DOM ---------- */
  function el(tag, attrs = {}, parent) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'style' && typeof v === 'object') Object.assign(e.style, v);
      else if (k === 'html') e.innerHTML = v;
      else if (k === 'text') e.textContent = v;
      else e.setAttribute(k, v);
    }
    if (parent) parent.appendChild(e);
    return e;
  }
  const SVGNS = 'http://www.w3.org/2000/svg';
  function sv(tag, attrs = {}, parent) {
    const e = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (parent) parent.appendChild(e);
    return e;
  }
  const px = (v) => `${v}px`;
  // An absolutely positioned div: div(parent, {x, y, w, h, html | text, style}).
  function div(parent, { x = 0, y = 0, w, h, html, text, style = {} } = {}) {
    const e = el('div', { class: 'abs' }, parent);
    if (html != null) e.innerHTML = html;
    if (text != null) e.textContent = text;
    Object.assign(e.style, { left: px(x), top: px(y) }, w != null ? { width: px(w) } : {}, h != null ? { height: px(h) } : {}, style);
    return e;
  }

  /* A box for UI drawn at its real CSS size, magnified z times: zoom(stage, {w, h, z, cx, cy}) puts a w×h box
     (CSS px) centred on panel point (cx, cy), scaled by z. Everything inside, including the demo's motion, is in
     real CSS px, so a translate of 10px in the code is 10px here too. */
  function zoom(parent, { w, h, z, cx = W / 2, cy, x, y }) {
    const left = x != null ? x : cx - (w * z) / 2, top = y != null ? y : cy - (h * z) / 2;
    const box = el('div', { class: 'zoom', style: { left: px(left), top: px(top), width: px(w), height: px(h), transform: `scale(${z})` } }, parent);
    box.toPanel = (bx, by) => [left + bx * z, top + by * z]; // a point inside the box, in panel px
    return box;
  }

  /* Icons (24×24, stroked, after Lucide). icon('cart', 20) returns the SVG markup. */
  const ICONS = {
    cart: '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    chevron: '<path d="m6 9 6 6 6-6"/>',
    moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    user: '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>',
    card: '<rect width="20" height="14" x="2" y="5" rx="2"/><path d="M2 10h20"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    bold: '<path d="M6 12h9a4 4 0 0 1 0 8H7a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h7a4 4 0 0 1 0 8"/>',
    italic: '<path d="M19 4h-9M14 20H5M15 4 9 20"/>',
    underline: '<path d="M6 4v6a6 6 0 0 0 12 0V4M4 20h16"/>',
    strike: '<path d="M16 4H9a3 3 0 0 0-2.83 4M14 12a4 4 0 0 1 0 8H6M4 12h16"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    code: '<path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/>',
  };
  const icon = (name, size = 20, sw = 2) =>
    `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" style="display:block">${ICONS[name]}</svg>`;

  /* ---------- pointers ---------- */
  /* A desktop cursor (arrow), sized like a real cursor next to UI magnified about 2×. set(x, y, {press, o}) puts its
     tip at panel point (x, y); press 0→1 squeezes it a little for a click. */
  function cursor(parent, { scale = 1.3, z = 30 } = {}) {
    const e = el('div', { class: 'cursor', style: { zIndex: z } }, parent);
    const arrow = el('div', {
      class: 'arrow',
      html: '<svg viewBox="0 0 28 34" width="28" height="34"><path d="M3.2 2.2v24.3l6.1-5.9 4.1 9.4 4.4-1.9-4-9.2h8.6z" fill="#fff" stroke="#111" stroke-width="1.7" stroke-linejoin="round"/></svg>',
    }, e);
    return {
      e,
      set(x, y, { press = 0, o = 1 } = {}) {
        e.style.transform = `translate(${x}px, ${y}px)`;
        e.style.opacity = o;
        arrow.style.transform = `scale(${scale * (1 - 0.12 * clamp(press))})`;
      },
    };
  }

  /* A touch: a soft disc where a fingertip is on the glass. set(x, y, {press, o}): o shows it (0 when the finger is
     off the screen), press 0→1 firms it up. */
  function finger(parent, { size = 76, z = 30 } = {}) {
    const e = el('div', { class: 'finger', style: { zIndex: z, width: px(size), height: px(size) } }, parent);
    const dot = el('b', {}, e);
    return {
      e,
      set(x, y, { press = 1, o = 1 } = {}) {
        e.style.transform = `translate(${x - size / 2}px, ${y - size / 2}px)`;
        e.style.opacity = o;
        dot.style.transform = `scale(${1.12 - 0.12 * clamp(press)})`;
        dot.style.background = `rgb(24 26 32 / ${0.16 + 0.12 * clamp(press)})`;
      },
    };
  }

  /* ---------- the code block ----------
     The recipe on up to four lines, under the component. code = { lang: 'css' | 'js' | 'jsx', lines: [...] }.
     In a line, {{before|after}} (or [[before|after]], for JSX, whose braces would clash) marks a value that changes
     on the fix; only those animate, and the new value gets a soft highlight. A line starting with "+" is added on
     the fix: it isn't there before, and on the fix it opens up where it sits, pushing the lines below it down, so
     the block grows downward from its fixed top.
     code.still: true for an after-only clip: the after values show throughout and nothing animates.
     code.insert: true (or { t, color }) when the agent adds the "+" lines (agentAt action 'insert'): on its click (t,
     default T - 0.45) a caret in its colour shows after the line above them; 0.2 s later an empty line opens with the
     caret on it, and on the fix the new lines land there (references/agent-cursor.md). Aim with block.insertPoint(). */
  const CB = { font: 34, lh: 44, padY: 18, padX: 30, bottom: 868 };
  const escH = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  // Syntax colours, one class per character. CSS keeps its state across lines (a rule can span several).
  function tokCSS(src) {
    const cls = new Array(src.length).fill('');
    const stack = [];
    let i = 0, pending = null, inValue = false, m;
    const mark = (len, c) => { for (let k = 0; k < len; k++) cls[i + k] = c; i += len; };
    while (i < src.length) {
      const r = src.slice(i);
      if ((m = r.match(/^\/\*[\s\S]*?(\*\/|$)/))) { mark(m[0].length, 'c'); continue; }
      if ((m = r.match(/^\s+/))) { mark(m[0].length, ''); continue; }
      if (r[0] === '{') { stack.push(pending || 'rule'); pending = null; inValue = false; mark(1, 'x'); continue; }
      if (r[0] === '}') { stack.pop(); inValue = false; mark(1, 'x'); continue; }
      if (stack[stack.length - 1] !== 'rule') {
        if ((m = r.match(/^@[\w-]+/))) { mark(m[0].length, 'a'); pending = m[0] === '@keyframes' ? 'kf' : 'at'; continue; }
        if ((m = r.match(/^[,>+~]/))) { mark(1, 'x'); continue; }
        m = r.match(/^[^\s{},>+~]+/);
        mark(m[0].length, 's');
        if (!pending) pending = 'rule';
        continue;
      }
      if (r[0] === ';') { inValue = false; mark(1, 'x'); continue; }
      if (!inValue) {
        if (r[0] === ':') { inValue = true; mark(1, 'x'); continue; }
        m = r.match(/^[\w-]+/) || [r[0]];
        mark(m[0].length, 'k');
        continue;
      }
      if ((m = r.match(/^!important/))) { mark(m[0].length, 'n'); continue; }
      if ((m = r.match(/^--[\w-]+/))) { mark(m[0].length, 'k'); continue; }
      if ((m = r.match(/^[\w-]+(?=\()/))) { mark(m[0].length, 'f'); continue; }
      if ((m = r.match(/^[(),/*+]/))) { mark(1, 'x'); continue; }
      if ((m = r.match(/^"[^"]*"/))) { mark(m[0].length, 'n'); continue; }
      m = r.match(/^[^\s;(),/*+}]+/) || [r[0]];
      mark(m[0].length, 'n');
    }
    return cls;
  }
  // One JS token at the start of r: [length, class]. prev is the last non-space character before it.
  const KW = new Set(['const', 'let', 'var', 'function', 'return', 'new', 'await', 'async', 'if', 'else']);
  function jsToken(r, prev) {
    let m;
    if ((m = r.match(/^\/\/[^\n]*/))) return [m[0].length, 'c'];
    if ((m = r.match(/^\s+/))) return [m[0].length, ''];
    if ((m = r.match(/^("[^"\n]*"|'[^'\n]*'|`[^`\n]*`)/))) return [m[0].length, 'n'];
    if ((m = r.match(/^\d+(\.\d+)?/))) return [m[0].length, 'n'];
    if (/[[(,:=]/.test(prev) && (m = r.match(/^-\d+(\.\d+)?/))) return [m[0].length, 'n'];
    if ((m = r.match(/^=>/))) return [2, 'a'];
    if ((m = r.match(/^[A-Za-z_$][\w$]*/))) {
      const w = m[0], after = r.slice(w.length);
      if (KW.has(w)) return [w.length, 'a'];
      if (/^(true|false|null|undefined)$/.test(w)) return [w.length, 'n'];
      if (/^\s*\(/.test(after)) return [w.length, 'f'];
      if (/^\s*:(?!:)/.test(after) && /[{,(\n]|^$/.test(prev)) return [w.length, 'k'];
      return [w.length, 's'];
    }
    return [1, 'x'];
  }
  function tokJS(src) {
    const cls = new Array(src.length).fill('');
    let i = 0, prev = '';
    while (i < src.length) {
      const [len, c] = jsToken(src.slice(i), prev);
      for (let k = 0; k < len; k++) cls[i + k] = c;
      const tx = src.slice(i, i + len).trim();
      if (tx) prev = tx[tx.length - 1];
      else if (src.slice(i, i + len).includes('\n')) prev = '\n';
      i += len;
    }
    return cls;
  }
  function tokJSX(src) {
    const cls = new Array(src.length).fill('');
    let i = 0, depth = 0, prev = '', m;
    const mark = (len, c) => { for (let k = 0; k < len; k++) cls[i + k] = c; i += len; };
    while (i < src.length) {
      const r = src.slice(i);
      if (r[0] === '{') { depth++; prev = '{'; mark(1, 'x'); continue; }
      if (r[0] === '}') { depth = Math.max(0, depth - 1); prev = '}'; mark(1, 'x'); continue; }
      if (depth > 0) {
        const [len, c] = jsToken(r, prev);
        const tx = r.slice(0, len).trim();
        if (tx) prev = tx[tx.length - 1];
        mark(len, c);
        continue;
      }
      if ((m = r.match(/^\s+/))) { mark(m[0].length, ''); continue; }
      if ((m = r.match(/^<\/?[\w.]+/))) { mark(m[0].length, 't'); continue; }
      if ((m = r.match(/^\/?>/))) { mark(m[0].length, 't'); continue; }
      if ((m = r.match(/^[\w-]+(?==)/))) { mark(m[0].length, 'a'); continue; }
      if ((m = r.match(/^"[^"]*"/))) { mark(m[0].length, 'n'); continue; }
      mark(1, r[0] === '=' ? 'x' : 's');
    }
    return cls;
  }
  const TOK = { css: tokCSS, js: tokJS, jsx: tokJSX };

  // Coloured HTML for src[from, from + len) of a tokenised text.
  function colour(text, cls, from) {
    let out = '', cur = null, buf = '';
    const flush = () => { if (buf) out += cur ? `<i class="${cur}">${escH(buf)}</i>` : escH(buf); buf = ''; };
    for (let k = 0; k < text.length; k++) {
      const c = cls[from + k] || '';
      if (c !== cur) { flush(); cur = c; }
      buf += text[k];
    }
    flush();
    return out;
  }

  function codeBlock(root, code) {
    const lang = code.lang || 'css';
    const tok = TOK[lang];
    const parsed = code.lines.map((src) => {
      const added = src[0] === '+';
      if (added) src = src.slice(1);
      const parts = [];
      src.split(/(\{\{.*?\}\}|\[\[.*?\]\])/).forEach((p) => {
        if (!p) return;
        const m = p.match(/^(?:\{\{|\[\[)(.*?)\|(.*?)(?:\}\}|\]\])$/);
        parts.push(m ? { a: m[1], b: m[2] } : { s: p });
      });
      return { added, parts };
    });
    const lineB = (l) => l.parts.map((p) => (p.s != null ? p.s : p.a)).join('');
    const lineA = (l) => l.parts.map((p) => (p.s != null ? p.s : p.b)).join('');
    const kept = parsed.filter((l) => !l.added);
    const bText = kept.map(lineB).join('\n'), aText = parsed.map(lineA).join('\n');
    const bCls = tok(bText), aCls = tok(aText);

    const n1 = parsed.length, n0 = code.still ? n1 : kept.length;
    const h1 = CB.padY * 2 + CB.lh * n1, h0 = CB.padY * 2 + CB.lh * n0;
    const top = CB.bottom - h1;
    const box = el('div', { class: 'cblock', style: { top: px(top), height: px(h0) } }, root);
    const slots = [];
    let bo = 0, ao = 0;
    const rows = parsed.map((l) => {
      const row = el('div', { class: 'cl' }, box);
      row.tint = l.added ? el('i', { class: 'tint' }, row) : null;
      const inner = el('span', { class: 'cl-in' }, row);
      row.inner = inner;
      let bi = l.added ? null : bo, ai = ao;
      for (const p of l.parts) {
        if (p.s != null) {
          el('span', { html: colour(p.s, aCls, ai) }, inner);
          if (bi != null) bi += p.s.length;
          ai += p.s.length;
          continue;
        }
        const slot = el('span', { class: 'slot' }, inner);
        const hi = el('i', { class: 'hi' }, slot);
        const sel = el('i', { class: 'sel' }, slot);
        const v0 = el('span', { class: 'v0', html: bi != null ? colour(p.a, bCls, bi) : escH(p.a) }, slot);
        const v1 = el('span', { class: 'v1', html: colour(p.b, aCls, ai) }, slot);
        slots.push({ slot, v0, v1, hi, sel, w0: 0, w1: 0 });
        if (bi != null) bi += p.a.length;
        ai += p.b.length;
      }
      if (!l.added) bo += lineB(l).length + 1;
      ao += lineA(l).length + 1;
      row.added = l.added;
      return row;
    });

    const firstAdded = rows.findIndex((r) => r.added);
    const caret = code.insert && firstAdded >= 0 ? el('i', { class: 'caret' }, box) : null;
    // The caret's two spots, in the box's own px: after the last character of the line above the new lines, then at
    // the indent of the first new line. Monospace, so a line's width over its length is one character's advance.
    function caretAt(stage) {
      const above = rows[Math.max(0, firstAdded - 1)], add = rows[firstAdded];
      const r = stage === 0 ? above : add;
      const text = r.inner.textContent, adv = r.inner.offsetWidth / Math.max(1, text.length);
      const x = r.offsetLeft + r.inner.offsetLeft + (stage === 0 ? r.inner.offsetWidth + adv * 0.15 : adv * (text.length - text.trimStart().length));
      return { x, y: r.offsetTop + CB.lh * 0.19 };
    }
    function measure() {
      slots.forEach((s) => { s.w0 = s.v0.getBoundingClientRect().width; s.w1 = s.v1.getBoundingClientRect().width; });
      // Fix the box to its widest line in either state, so nothing re-centres while values change.
      let wMax = 0;
      for (const end of [0, 1]) {
        slots.forEach((s) => { s.slot.style.width = px(end ? s.w1 : s.w0); });
        rows.forEach((r) => { if (end || !r.added) wMax = Math.max(wMax, r.inner.getBoundingClientRect().width); });
      }
      box.style.width = px(Math.ceil(wMax + CB.padX * 2));
    }

    function render(t) {
      const T = H$.T_FIX;
      if (code.still) {
        slots.forEach((s) => { s.slot.style.width = px(s.w1); s.v0.style.opacity = 0; s.v1.style.opacity = 1; s.hi.style.opacity = 0; });
        rows.forEach((r) => { r.inner.style.opacity = 1; r.style.height = px(CB.lh); if (r.tint) r.tint.style.opacity = 0; });
        box.style.height = px(h1);
        return;
      }
      // The code changes quickly (done about 0.35 s after the fix), so the after windows read the new values.
      slots.forEach((s, k) => {
        const a = T + k * 0.04;
        const c = E.move(prog(t, a, a + 0.3));
        s.slot.style.width = px(lerp(s.w0, s.w1, c));
        s.v0.style.opacity = 1 - c; s.v0.style.filter = c > 0 && c < 1 ? `blur(${c * 5}px)` : 'none';
        s.v1.style.opacity = c; s.v1.style.filter = c > 0 && c < 1 ? `blur(${(1 - c) * 5}px)` : 'none';
        s.hi.style.opacity = s.w1 > 0 ? prog(t, a + 0.15, a + 0.35) * (1 - 0.35 * prog(t, a + 1.6, a + 2.6)) : 0;
        // The agent's double-click selects the old value in its own colour (code.select), then green takes over.
        const sc = !code.select ? null : code.select === true ? { color: AGENTS[0].color, t: T - 0.15 } : { color: AGENTS[0].color, ...code.select };
        if (sc) {
          const [r, g, b] = hexToRgb(sc.color);
          s.sel.style.background = `rgb(${r} ${g} ${b} / 0.42)`;
          s.sel.style.boxShadow = `inset 0 0 0 ${fpx(1.5)}px rgb(${r} ${g} ${b})`;
          s.sel.style.opacity = prog(t, sc.t, sc.t + 0.04) * (1 - prog(t, a + 0.04, a + 0.2));
        }
      });
      const g = E.move(prog(t, T, T + 0.3));
      const o = E.move(prog(t, T + 0.06, T + 0.36));
      const tintO = prog(t, T + 0.15, T + 0.4) * (1 - 0.35 * prog(t, T + 1.6, T + 2.6));
      const ins = caret ? { color: AGENTS[0].color, t: T - 0.45, ...(code.insert === true ? {} : code.insert) } : null;
      const pre = ins ? E.move(prog(t, ins.t + 0.2, ins.t + 0.35)) : 0; // the empty line opens 0.2 s after the click
      let h = CB.padY * 2;
      rows.forEach((r, i) => {
        if (!r.added) { h += CB.lh; return; }
        const rh = CB.lh * (i === firstAdded ? Math.max(g, pre) : g);
        r.style.height = px(rh);
        h += rh;
        r.inner.style.opacity = o;
        r.inner.style.transform = `translateY(${(1 - o) * 8}px)`;
        r.inner.style.filter = o > 0 && o < 1 ? `blur(${(1 - o) * 4}px)` : 'none';
        r.tint.style.opacity = tintO;
      });
      box.style.height = px(h);
      if (ins) {
        const p = caretAt(t < ins.t + 0.2 ? 0 : 1);
        Object.assign(caret.style, { left: px(p.x), top: px(p.y), width: px(fpx(4)), height: px(CB.lh * 0.62), background: ins.color,
          opacity: prog(t, ins.t, ins.t + 0.04) * (1 - prog(t, T, T + 0.15)) });
      }
    }
    // Where token k sits (its old value), in panel px, for aiming the agent at it. Call after measure().
    function slotBox(k = 0) {
      const r = slots[k].v0.getBoundingClientRect(), p = root.getBoundingClientRect();
      return { x: r.left - p.left, y: r.top - p.top, w: r.width, h: r.height };
    }
    // Where the agent clicks to add the "+" lines: just after the last character of the line above them, in panel px.
    function insertPoint() {
      const above = rows[Math.max(0, firstAdded - 1)], r = above.inner.getBoundingClientRect(), p = root.getBoundingClientRect();
      return { x: r.right - p.left, y: r.top - p.top, h: r.height };
    }
    return { box, measure, render, slotBox, insertPoint, top, height: h1 };
  }

  /* ---------- the explainer layer ---------- */

  /* The slot this asset is drawn for (explain.json "slot"): its panel size, the band the viewer sees, and its scale
     into the final frame. index.html calls it before the scene loads. */
  function setSlot({ w = 1080, h = 960, band, scale = 1 } = {}) {
    W = w; H = h; BAND = band ? { top: band[0], bottom: band[1] } : { top: 0, bottom: h }; SLOT_SCALE = scale;
    CB.bottom = BAND.bottom - 22;
    // Code reads at 24 px or more in the final frame (references/text.md): 34 px at the hack card's 0.72, 36 px at 0.68.
    const cpx = Math.max(34, Math.ceil(24 / SLOT_SCALE));
    CB.lh = cpx + 10;
    document.documentElement.style.setProperty('--code-px', cpx + 'px');
    document.documentElement.style.setProperty('--code-lh', CB.lh + 'px');
    Object.assign(window.H$, { W, H, BAND, SLOT_SCALE });
  }

  /* The agents' colours, in the order they're assigned (references/agent-cursor.md). Each gives its white label
     4.5:1 and its arrow 3.7:1 on the #e6e9ee ground. */
  const AGENT_COLORS = ['#0079CD', '#9747FF', '#DE04A3', '#058193'];
  /* The reel's agents from explain.json "agents" (the page calls setAgents), so a lone agent that skipped blue
     because the demos are blue is violet everywhere without passing its colour each time. */
  let AGENTS = [{ label: 'Agent', color: AGENT_COLORS[0] }];
  function setAgents(list) { if (Array.isArray(list) && list.length) AGENTS = list; }
  const agentColor = (label) => (AGENTS.find((a) => a.label === label) || AGENTS[0]).color;

  /* The agent cursor: a collaborator's cursor in Figma. A coloured arrow with a 2 px white outline and a soft
     shadow, and a name chip in the same colour below-right of its tip. agent(panel, {label, color, height}) returns
     { set(x, y, {press, o}) }, which puts the tip at panel point (x, y); press 0..1 dips the arrow to 90%. Put it on
     the panel, not inside a pushed stage, so it stays the same size. height defaults to 40 final px. */
  function agent(parent, { label = AGENTS[0].label, color = agentColor(label), height, z = 60 } = {}) {
    const h = height || fpx(40);
    const s = h / 34; // the arrow's own units are a 28x34 box with its tip at (3.2, 2.2)
    const e = el('div', { class: 'agent', style: { zIndex: z } }, parent);
    const arrow = el('div', { class: 'agent-arrow', style: { left: px(-3.2 * s), top: px(-2.2 * s), transformOrigin: `${3.2 * s}px ${2.2 * s}px`,
      filter: `drop-shadow(0 ${fpx(2)}px ${fpx(3)}px rgb(0 0 0 / 0.25))` },
      html: `<svg viewBox="0 0 28 34" width="${28 * s}" height="${34 * s}" style="overflow:visible;display:block"><path d="M3.2 2.2v24.3l6.1-5.9 4.1 9.4 4.4-1.9-4-9.2h8.6z" fill="${color}" stroke="#fff" stroke-width="${(2 * fpx(2)) / s}" stroke-linejoin="round" paint-order="stroke"/></svg>` }, e);
    const chip = el('div', { class: 'agent-chip', text: label, style: { left: px(h * 0.55), top: px(h * 0.86), background: color,
      font: `600 ${fpx(26)}px/${fpx(26)}px Inter, sans-serif`, padding: `${fpx(7)}px ${fpx(11)}px`, borderRadius: px(fpx(9)),
      boxShadow: `0 ${fpx(2)}px ${fpx(6)}px rgb(0 0 0 / 0.25)` } }, e);
    return {
      e, chip, color, height: h,
      set(x, y, { press = 0, o = 1 } = {}) {
        e.style.transform = `translate(${x}px, ${y}px)`;
        e.style.opacity = o;
        e.style.visibility = o > 0.001 ? 'visible' : 'hidden';
        arrow.style.transform = `scale(${1 - 0.1 * clamp(press)})`;
      },
    };
  }

  // A glide from a to b over [t0, t1] on the ease-in-out, bowing to one side by `bow` of the distance (at most 0.08).
  function glidePt(t, a, b, t0, t1, bow = 0.05) {
    const u = E.inOut(prog(t, t0, t1));
    const dx = b[0] - a[0], dy = b[1] - a[1], d = Math.hypot(dx, dy) || 1, k = Math.sin(Math.PI * u) * Math.min(bow, 0.08) * d;
    return [a[0] + dx * u + (dy / d) * k, a[1] + dy * u - (dx / d) * k];
  }
  // How far down a press is at t, for a press at t0 released at t1 (80 ms each way).
  const pressAt = (t, t0, t1) => prog(t, t0, t0 + 0.08) * (1 - prog(t, t1, t1 + 0.08));

  /* Where the agent is at t, for one change at T, on the timeline in references/agent-cursor.md:
       agentAt(t, { T, from, to, action: 'click' | 'double' | 'drag', dragTo, after: 'stay' | 'fade' | 'rest', rest,
                    lineLeft, enter })
     It glides from `from` (450 ms under a third of the panel's width, 600 ms over) to arrive at `to` by T - 0.6
     (T - 0.9 before a drag), fading in over 120 ms if `enter`; presses (click at T - 0.15; double-click at T - 0.3
     and T - 0.15; a drag presses at T - 0.68 and moves to `dragTo` over T - 0.6 .. T); releases at T + 0.07; holds
     to T + 0.5; then fades over 150 ms or glides to `rest` 40% faster. lineLeft (seconds of the line after T) under
     1.3 fades it at T + 0.25 instead. Returns { x, y, press, o }; pass them to agent().set. */
  function agentAt(t, { T = H$.T_FIX, from, to, action = 'click', dragTo, after = 'stay', rest, lineLeft = 9, enter = true }) {
    const drag = action === 'drag';
    const A = T - (drag || action === 'insert' ? 0.9 : 0.6);
    const g = Math.hypot(to[0] - from[0], to[1] - from[1]) < W / 3 ? 0.45 : 0.6;
    const G = A - g;
    let pos = t < G ? from : t < A ? glidePt(t, from, to, G, A) : to;
    let o = enter ? prog(t, G, G + 0.12) : 1;
    let press = 0;
    if (action === 'click') press = pressAt(t, T - 0.15, T + 0.07);
    if (action === 'double') press = Math.max(pressAt(t, T - 0.3, T - 0.22), pressAt(t, T - 0.15, T + 0.07));
    if (action === 'insert') press = pressAt(t, T - 0.45, T - 0.38); // code.insert's caret, then its empty line at T - 0.25
    if (drag) {
      press = pressAt(t, T - 0.68, T + 0.07);
      if (t >= T - 0.6) { const u = E.inOut(prog(t, T - 0.6, T)); pos = [lerp(to[0], dragTo[0], u), lerp(to[1], dragTo[1], u)]; }
    }
    const at = drag ? dragTo : to;
    if (lineLeft < 1.3) o *= 1 - prog(t, T + 0.25, T + 0.4);
    else if (after === 'fade') o *= 1 - prog(t, T + 0.5, T + 0.65);
    else if (after === 'rest' && rest && t > T + 0.5) {
      const gr = 0.6 * (Math.hypot(rest[0] - at[0], rest[1] - at[1]) < W / 3 ? 0.45 : 0.6);
      pos = glidePt(t, at, rest, T + 0.5, T + 0.5 + gr);
    }
    return { x: pos[0], y: pos[1], press, o };
  }

  /* A selection box with corner handles in the agent's colour, as Figma draws a collaborator's selection. It must
     fully enclose its element. selection(panel, {color}) returns { set(x, y, w, h, o) } in panel px. */
  function selection(parent, { color = AGENTS[0].color, z = 55 } = {}) {
    const bw = fpx(1.5), hs = fpx(9);
    const e = el('div', { class: 'agent-sel', style: { zIndex: z, border: `${bw}px solid ${color}` } }, parent);
    const handles = [0, 1, 2, 3].map(() => el('i', { style: { width: px(hs), height: px(hs), border: `${bw}px solid ${color}` } }, e));
    return {
      e,
      set(x, y, w, h, o = 1) {
        Object.assign(e.style, { left: px(x), top: px(y), width: px(w), height: px(h), opacity: o, visibility: o > 0.001 ? 'visible' : 'hidden' });
        handles.forEach((hd, i) => Object.assign(hd.style, { left: px((i % 2 ? w : 0) - hs / 2 - bw), top: px((i > 1 ? h : 0) - hs / 2 - bw) }));
      },
    };
  }

  /* The definition tab (references/text.md), for a slot whose clip draws its own: black, white Helvetica Neue bold
     at 30 final px, 14 final px either side, 1.55x the type tall. tab(panel, {x, y, text}) puts its top-left corner at
     (x, y) and returns { e, set(text) }. In the hack-reel and term cards the list kit draws it, not the clip. */
  function tab(parent, { x = 0, y = 0, text = '', z = 45 } = {}) {
    const size = fpx(30);
    const e = el('div', { class: 'tab', text, style: { left: px(x), top: px(y), height: px(size * 1.55), padding: `0 ${fpx(14)}px`,
      font: `700 ${size}px/${size * 1.55}px "Helvetica Neue", Helvetica, Arial, sans-serif`, zIndex: z } }, parent);
    return { e, set(text) { e.textContent = text; } };
  }

  /* A side by side (references/forms.md): two equal wells in the box (x, y, w, h) of the parent, a label over each,
     laid out the same on every card. pair(panel, { x, y, w, h, labels, colors, gap, dots }) returns
     { b, a, wells, ww, wh, top }: b and a are the wells (clipped, ww × wh panel px, each with its own (0, 0) at its
     top-left). Build the component once as a function of the side and call it for both, so the two can't drift
     apart. labels default to Before / After in the ink colour (a principle). A fix that differs in feel passes its
     values instead, and colors: ['var(--red-ink)', 'var(--green-ink)']. dots: false drops the dot grid. */
  function pair(parent, { x = 0, y = 0, w = W, h = H, labels = ['Before', 'After'], colors, gap = fpx(24), dots = true, z = 1 } = {}) {
    const size = fpx(30), lh = Math.round(size * 1.25), under = fpx(12);
    const ww = (w - gap) / 2, top = y + lh + under, wh = y + h - top;
    const tags = [];
    const wells = [0, 1].map((i) => {
      const lx = x + i * (ww + gap);
      tags[i] = div(parent, { x: lx, y, text: labels[i], style: { font: `600 ${size}px/${lh}px Inter, sans-serif`, color: colors ? colors[i] : 'var(--ink)',
        letterSpacing: '-0.01em', whiteSpace: 'nowrap', zIndex: z } });
      return div(parent, { x: lx, y: top, w: ww, h: wh, style: { overflow: 'hidden', borderRadius: px(fpx(8)), zIndex: z, background: 'var(--well)',
        ...(dots ? { backgroundImage: `radial-gradient(circle, var(--well-dot) ${fpx(1.3)}px, transparent ${fpx(1.7)}px)`,
          backgroundSize: `${fpx(18)}px ${fpx(18)}px`, backgroundPosition: `${fpx(9)}px ${fpx(9)}px` } : {}) } });
    });
    return { b: wells[0], a: wells[1], wells, labels: tags, ww, wh, top };
  }

  // The slow push-in that keeps a still alive (SKILL.md, Never stale): 2% a second from the asset's start, linear.
  const push = (t, rate = 0.02) => 1 + rate * Math.max(0, t);

  // A scene file registers itself with H$.scene({ code, build(stage, area, ctx), check, stills }).
  const scene = (def) => { window.SCENE = def; };

  const PAD = (n) => String(n).padStart(2, '0');

  window.H$ = {
    W, H, BAND, SLOT_SCALE, T_FIX: 4.5, DUR: 9.0, CB,
    clamp, lerp, prog, mix, bezier, E, springTo, motionSpring, transition, keyframes, keys, lastBefore, bump,
    hexToRgb, css, el, sv, px, div, zoom, icon, cursor, finger, codeBlock, PAD,
    setSlot, setAgents, fpx, AGENT_COLORS, agent, agentAt, glidePt, pressAt, selection, tab, pair, push, scene,
  };
  window.HACKS = {};
})();
