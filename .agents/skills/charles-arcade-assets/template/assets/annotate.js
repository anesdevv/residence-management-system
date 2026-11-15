/* annotate.js: hand-drawn marker marks, handwriting, sticky notes, numbered callouts, leader lines, heavy
   stamps, badges, verdict flips and formatted counters. Extends window.AR; load after arcade.js.

   Seek-safe: geometry is measured once, when the scene script runs (HyperFrames has loaded the fonts by then);
   every random choice comes from a seeded generator; every visible state is a tween or a set on the paused
   timeline. Marks are drawn into a layer: the scene root by default, or the nearest ancestor with class
   "an-layer" (give a camera wrapper that class so marks move with a push), or o.layer. Positions are layout
   positions (offsets), so a settle or punch running on an ancestor does not skew them. */
(function () {
  const AR = (window.AR = window.AR || {});
  const NS = "http://www.w3.org/2000/svg";
  const RED = "#ef3238";

  const all = (sel, root) => {
    if (sel == null) return [];
    if (typeof sel === "string") return Array.from((root || document).querySelectorAll(sel));
    if (sel.nodeType) return [sel];
    return Array.from(sel).flatMap((s) => (typeof s === "string" ? all(s, root) : [s]));
  };
  const one = (sel) => all(sel)[0];
  const seeded = (seed) => () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const hash = (s) => {
    let h = 2166136261;
    for (const c of String(s)) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
    return h >>> 0;
  };
  const easeFn = (e) => (typeof e === "function" ? e : gsap.parseEase(e || "none"));
  const seedFor = (o, el, tag) => o.seed ?? hash(tag + (el ? el.id + "|" + el.className + "|" + el.textContent : ""));

  // ---------- layout ----------
  // Marks live in an .an-marks box (absolute, at 0,0) inside the layer. Every position is a layout position
  // (offsetLeft/Top summed up the offset chain, which ignores transforms) taken relative to that box, so marks
  // land right whether the scene root is positioned or (as in the HyperFrames runtime) a static host in flow.
  const layerFor = (el, o = {}) => {
    if (o.layer) return one(o.layer);
    const p = el && el.parentElement;
    return (p && (p.closest(".an-layer, [data-an-layer]") || p.closest("[data-composition-id]"))) || document.body;
  };
  const pagePos = (el) => {
    let x = 0, y = 0, n = el;
    while (n) {
      x += n.offsetLeft; y += n.offsetTop;
      const p = n.offsetParent;
      if (p) { x += p.clientLeft; y += p.clientTop; }
      n = p;
    }
    return [x, y];
  };
  const marksFor = (layer) => {
    let m = Array.from(layer.children).find((c) => c.classList && c.classList.contains("an-marks"));
    if (!m) {
      m = document.createElement("div");
      m.className = "an-marks";
      m.setAttribute("data-layout-ignore", "");
      const svg = document.createElementNS(NS, "svg");
      svg.setAttribute("class", "an-svg");
      svg.setAttribute("width", "1");
      svg.setAttribute("height", "1");
      m.appendChild(svg);
      layer.appendChild(m);
    }
    return m;
  };
  const svgOf = (layer) => marksFor(layer).querySelector("svg.an-svg");
  // an element's box in its layer's marks coordinates
  const boxIn = (el, layer) => {
    const m = marksFor(layer);
    if (el instanceof HTMLElement && el.offsetParent) {
      const [ex, ey] = pagePos(el), [mx, my] = pagePos(m);
      return { x: ex - mx, y: ey - my, w: el.offsetWidth, h: el.offsetHeight };
    }
    const r = el.getBoundingClientRect(), M = m.getBoundingClientRect();
    const s = layer.offsetWidth ? layer.getBoundingClientRect().width / layer.offsetWidth || 1 : 1;
    return { x: (r.left - M.left) / s, y: (r.top - M.top) / s, w: r.width / s, h: r.height / s };
  };
  const toD = (pts) => "M" + pts.map((p) => p[0].toFixed(1) + " " + p[1].toFixed(1)).join("L");
  const stroke = (layer, pts, o, cls) => {
    const p = document.createElementNS(NS, "path");
    p.setAttribute("d", toD(pts));
    p.setAttribute("class", cls || "an-mark");
    p.setAttribute("stroke", o.color || RED);
    p.setAttribute("stroke-width", o.width ?? 6);
    p.setAttribute("pathLength", "1");
    p.style.strokeDasharray = "1 1";
    p.style.strokeDashoffset = "1";
    svgOf(layer).appendChild(p);
    return p;
  };
  const drawOn = (tl, path, t, dur, ease) => {
    tl.set(path, { opacity: 0 }, 0);
    tl.set(path, { opacity: 1 }, t);
    return tl.fromTo(path, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: dur, ease }, t);
  };
  const arcLen = (pts) => {
    const L = [0];
    for (let i = 1; i < pts.length; i++) L.push(L[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    return L;
  };
  const pointAt = (pts, L, d) => {
    if (d <= 0) return pts[0];
    const n = pts.length - 1;
    if (d >= L[n]) return pts[n];
    let lo = 0, hi = n;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (L[m] <= d) lo = m; else hi = m; }
    const f = (d - L[lo]) / (L[hi] - L[lo] || 1);
    return [pts[lo][0] + (pts[hi][0] - pts[lo][0]) * f, pts[lo][1] + (pts[hi][1] - pts[lo][1]) * f];
  };

  // type-on that keeps line breaks and nested elements (AR.type flattens an element to its text)
  const typeOn = (tl, el, t, cps) => {
    if (!el.dataset.anType) {
      el.dataset.anType = "1";
      const walk = (node) => Array.from(node.childNodes).forEach((c) => {
        if (c.nodeType === Node.TEXT_NODE) {
          const frag = document.createDocumentFragment();
          for (const ch of c.textContent) {
            if (/\s/.test(ch)) { frag.appendChild(document.createTextNode(ch)); continue; }
            const sp = document.createElement("span");
            sp.className = "an-ch";
            sp.textContent = ch;
            frag.appendChild(sp);
          }
          c.replaceWith(frag);
        } else if (c.nodeType === Node.ELEMENT_NODE && c.tagName !== "BR") walk(c);
      });
      walk(el);
    }
    const chars = el.querySelectorAll(".an-ch");
    if (chars.length) tl.fromTo(chars, { opacity: 0 }, { opacity: 1, duration: 0.001, ease: "none", stagger: 1 / cps }, t);
  };
  // stamps, stickies and badges land on content on purpose: keep check's overlap test off them
  const onTop = (el) => { if (!el.hasAttribute("data-layout-ignore")) el.setAttribute("data-layout-ignore", ""); };

  // ---------- the pen that rides a stroke ----------
  const penTip = (pen) => {
    if (pen.dataset.tip) return pen.dataset.tip.split(",").map(Number);
    return [pen.offsetWidth * 0.058, pen.offsetHeight * 0.942];
  };
  const ride = (tl, penSel, layer, pts, t, dur, ease, o = {}) => {
    const pen = one(penSel);
    if (!pen) return;
    const m = marksFor(layer);
    if (pen.parentElement !== m) m.appendChild(pen);
    const [tx, ty] = penTip(pen), L = arcLen(pts), total = L[L.length - 1], E = easeFn(ease);
    const p0 = pts[0];
    if (pen._anEnd === undefined) {
      gsap.set(pen, { x: p0[0] - tx, y: p0[1] - ty }); // waits at its first stroke's start
    } else {
      const lead = Math.max(0, Math.min(o.lead ?? 0.12, t - pen._anEnd));
      if (lead > 0.02) tl.to(pen, { x: p0[0] - tx, y: p0[1] - ty, duration: lead, ease: "power2.inOut" }, t - lead);
      else tl.set(pen, { x: p0[0] - tx, y: p0[1] - ty }, t);
    }
    const n = Math.max(6, Math.min(48, Math.round(dur * 60)));
    for (let k = 1; k <= n; k++) {
      const q = pointAt(pts, L, total * E(k / n));
      tl.to(pen, { x: q[0] - tx, y: q[1] - ty, duration: dur / n, ease: "none" }, t + (dur * (k - 1)) / n);
    }
    pen._anEnd = t + dur;
    if (o.lift) { // the pen lifts off the page so the mark it made is clear
      const [lx, ly] = Array.isArray(o.lift) ? o.lift : [48, -44];
      tl.to(pen, { x: `+=${lx}`, y: `+=${ly}`, duration: 0.22, ease: "power2.out" }, t + dur + 0.03);
      pen._anEnd = t + dur + 0.25;
    }
  };

  // ---------- shapes ----------
  // a marker loop: irregular, tilted, egg-shaped, landing a little off the line and overshooting its start
  const loop = (cx, cy, rx, ry, r, o) => {
    const tilt = ((o.tilt ?? r() * 8 - 5) * Math.PI) / 180;
    const dir = o.dir === -1 ? -1 : 1;
    const a0 = o.start != null ? (o.start * Math.PI) / 180 : -Math.PI / 2 + (r() * 2 - 1) * 0.95;
    const over = ((o.over ?? 24 + r() * 22) * Math.PI) / 180;
    const S = 2 * Math.PI + over;
    const e1 = 0.03 + r() * 0.03, p1 = r() * 6.283;
    const e2 = 0.025 + r() * 0.03, p2 = r() * 6.283;
    const e3 = 0.006 + r() * 0.008, p3 = r() * 6.283;
    // the tail ends a little outside (or inside) the start, and the pen lands further out (or in) still, so the
    // tail crosses the start stroke the way a quick marker loop does
    const drift = o.drift ?? (r() < 0.62 ? 1 : -1) * (0.04 + r() * 0.035);
    const kin = Math.sign(drift || 1) * (Math.abs(drift) + 0.035 + r() * 0.04);
    const pts = [], n = 150;
    for (let i = 0; i <= n; i++) {
      const s = (S * i) / n, th = a0 + dir * s;
      let k = 1 + e1 * Math.cos(th - p1) + e2 * Math.cos(2 * th - p2) + e3 * Math.cos(5 * th - p3) + drift * (s / S);
      if (s < 0.8) k += kin * Math.pow(1 - s / 0.8, 2);
      const x = rx * k * Math.cos(th), y = ry * k * Math.sin(th);
      pts.push([cx + x * Math.cos(tilt) - y * Math.sin(tilt), cy + x * Math.sin(tilt) + y * Math.cos(tilt)]);
    }
    return pts;
  };
  const isPoint = (v) => Array.isArray(v) && typeof v[0] === "number";
  const edgePoint = (b, toward, gap) => {
    const cx = b.x + b.w / 2, cy = b.y + b.h / 2, dx = toward[0] - cx, dy = toward[1] - cy;
    const k = Math.min(Math.abs(dx) > 1e-6 ? (b.w / 2 + gap) / Math.abs(dx) : Infinity, Math.abs(dy) > 1e-6 ? (b.h / 2 + gap) / Math.abs(dy) : Infinity);
    return k === Infinity ? [cx, cy] : [cx + dx * Math.min(k, 1), cy + dy * Math.min(k, 1)];
  };

  // ---------- number formatting ----------
  const NF = {};
  const nf = (opts) => {
    const key = JSON.stringify(opts);
    return NF[key] || (NF[key] = new Intl.NumberFormat("en-US", opts));
  };
  const fmtFn = (f, o = {}) => {
    if (typeof f === "function") return f;
    const spec = typeof f === "string" ? { style: f, digits: o.digits, compact: o.compact } : f || { style: "int", digits: o.digits };
    return (v) => AR.fmt(v, spec);
  };

  Object.assign(AR, {
    // AR.fmt(1250, {style: "usd", digits: 0}) -> "$1,250"; styles int, usd, pct (99.2 -> "99.2%"), x (100 -> "×100"),
    // dec, compact (1200000 -> "1.2M"); {compact: true} works with usd too ("$73M"); prefix/suffix wrap it.
    // Replaces motion.js's simpler AR.fmt (loaded earlier) and still reads its {decimals} option.
    fmt(n, o = {}) {
      if (typeof o === "string") o = { style: o };
      const style = o.style || "int", compact = o.compact || style === "compact";
      let d = o.digits ?? o.decimals; // decimals: the name motion.js's counters use
      const opts = {};
      if (compact) { opts.notation = "compact"; opts.maximumFractionDigits = d ?? 1; opts.minimumFractionDigits = o.minDigits ?? 0; }
      else {
        d = d ?? (style === "usd" ? 2 : style === "pct" || style === "dec" ? 1 : 0);
        opts.minimumFractionDigits = d; opts.maximumFractionDigits = d;
      }
      if (style === "usd") { opts.style = "currency"; opts.currency = o.currency || "USD"; }
      const q = Math.pow(10, -(compact ? 3 : d)) / 2;
      const v = Math.abs(n) < q ? 0 : n;
      let s = nf(opts).format(v);
      if (style === "pct") s += "%";
      if (style === "x") s = "×" + s;
      return (o.prefix || "") + s + (o.suffix || "");
    },

    // a counter that ticks: smooth values sampled at o.fps (15: stepped like a scoreboard), or o.steps, a list of
    // values ([0, 5, 50, 500, 5000]) or {value, label} objects shown in turn (at o.times, or evenly over dur).
    // A step's label goes to o.label (an element) or after the value (" · label"). format: a style name, a
    // fmt() spec, or a function. The first countTo on an element paints its start value at build time.
    countTo(tl, sel, t, dur, o = {}) {
      const els = all(sel);
      if (!els.length) return tl;
      const f = fmtFn(o.format, o), labelEls = o.label ? all(o.label) : [];
      const pts = [];
      if (o.steps) {
        const n = o.steps.length;
        o.steps.forEach((s, i) => {
          const st = typeof s === "object" ? s : { value: s };
          const time = o.times ? o.times[i] : t + (n > 1 ? (dur * i) / (n - 1) : 0);
          const num = st.text ?? f(st.value);
          pts.push({ time, text: st.label != null && !labelEls.length ? num + (o.sep ?? " · ") + st.label : num, label: st.label });
        });
      } else {
        const from = o.from ?? 0, to = o.to ?? 0, E = easeFn(o.ease ?? "power2.out");
        const n = Math.max(1, Math.round(dur * (o.fps ?? 15)));
        for (let k = 0; k <= n; k++) pts.push({ time: t + (dur * k) / n, text: f(from + (to - from) * E(k / n)) });
        pts[n].text = f(to);
      }
      els.forEach((el) => {
        if (!el.dataset.anCount) { el.dataset.anCount = "1"; el.textContent = pts[0].text; }
        let prev = null;
        pts.forEach((p) => { if (p.text !== prev) tl.set(el, { textContent: p.text }, p.time); prev = p.text; });
      });
      labelEls.forEach((le) => {
        if (!le.dataset.anCount && pts[0].label != null) { le.dataset.anCount = "1"; le.textContent = pts[0].label; }
        pts.forEach((p) => { if (p.label != null) tl.set(le, { textContent: p.label }, p.time); });
      });
      return tl;
    },

    // ---------- hand-drawn marks ----------
    // a red marker loop drawn round an element (or round [x, y, w, h], px in o.layer, which a box needs).
    // o: color, width (6), pad (12), dur (0.3), ease, seed, tilt (deg), start (deg: 0 = 3 o'clock, -90 = top),
    // dir (1 clockwise, -1), over (overshoot deg), sx / sy (radius per half-width / half-height: 1.14 / 1.24),
    // pen (a .an-pen that rides the tip, then lifts off; lift: false keeps it down, [dx, dy] moves it there),
    // layer. Returns the path.
    circle(tl, target, t, o = {}) {
      const el = isPoint(target) ? null : one(target);
      if (!el && !isPoint(target)) return null;
      const layer = el ? layerFor(el, o) : one(o.layer) || document.body;
      const b = el ? boxIn(el, layer) : { x: target[0], y: target[1], w: target[2], h: target[3] };
      const r = seeded(seedFor(o, el, "circle" + b.x + "," + b.y));
      const pad = o.pad ?? 12;
      const cx = b.x + b.w / 2 + (o.dx ?? 0), cy = b.y + b.h / 2 + (o.dy ?? 0);
      const rx = (b.w / 2) * (o.sx ?? 1.14) + pad, ry = Math.max((b.h / 2) * (o.sy ?? 1.24) + pad * 0.8, rx * (o.minRatio ?? 0.34));
      const pts = loop(cx, cy, rx, ry, r, o);
      const path = stroke(layer, pts, o);
      const dur = o.dur ?? 0.3, ease = o.ease ?? "power1.inOut";
      drawOn(tl, path, t, dur, ease);
      if (o.pen) ride(tl, o.pen, layer, pts, t, dur, ease, { lift: true, ...o });
      return path;
    },

    // a hand-drawn line under an element; o.at: "under" (default), "through" (a strike-through) or a fraction
    // of its height. o: color, width (6), dur (0.24, 0.2 through), ext (px past each end, or [left, right]),
    // tilt, bow, flick (false: no end flick), pen (rides the tip; o.lift lifts it off after), layer, seed.
    // Returns the path.
    underline(tl, target, t, o = {}) {
      const el = one(target);
      if (!el) return null;
      const layer = layerFor(el, o), b = boxIn(el, layer);
      const through = o.at === "through" || o.at === "strike";
      const frac = typeof o.at === "number" ? o.at : through ? 0.56 : 1;
      const r = seeded(seedFor(o, el, through ? "strike" : "under"));
      const ext = o.ext ?? (through ? 12 : 4), [eL, eR] = Array.isArray(ext) ? ext : [ext, ext];
      const x0 = b.x - eL - r() * 5, x1 = b.x + b.w + eR + r() * 5, w = x1 - x0;
      const y0 = b.y + b.h * frac + (through ? 0 : o.gap ?? 5);
      const tilt = ((o.tilt ?? (r() * 2 - 1) * (through ? 1.3 : 0.9)) * Math.PI) / 180;
      const bow = o.bow ?? (r() * 2 - 1) * (through ? 1.5 : 3.5);
      const f = 1.2 + r() * 1.3, ph = r() * 6.283, wob = o.wobble ?? 1.1;
      const pts = [];
      for (let i = 0; i <= 40; i++) {
        const u = i / 40;
        pts.push([x0 + u * w, y0 + (u - 0.5) * w * Math.tan(tilt) + bow * 4 * u * (1 - u) + wob * Math.sin(6.283 * f * u + ph) * Math.sin(Math.PI * u)]);
      }
      if (!through && o.flick !== false) {
        const [ex, ey] = pts[pts.length - 1];
        pts.push([ex + 5, ey - 2.5], [ex + 8, ey - 7]);
      }
      const path = stroke(layer, pts, o);
      const dur = o.dur ?? (through ? 0.2 : 0.24), ease = o.ease ?? "power2.inOut";
      drawOn(tl, path, t, dur, ease);
      if (o.pen) ride(tl, o.pen, layer, pts, t, dur, ease, o);
      return path;
    },

    // a hand-drawn arrow from one element or [x, y] (px in the scene, or in o.layer) to another; it leaves and
    // stops short of element boxes by o.gap (10). o: bend (about 0.2 of the length; its sign picks the side),
    // head (px), color, width (6), dur (0.32), seed, layer. The shaft draws, then the head flicks on.
    // Returns [shaft, head].
    arrow(tl, from, to, t, o = {}) {
      const fe = isPoint(from) ? null : one(from), te = isPoint(to) ? null : one(to);
      const layer = o.layer ? one(o.layer) : layerFor(fe || te, o);
      const fb = fe && boxIn(fe, layer), tb = te && boxIn(te, layer);
      const fc = fe ? [fb.x + fb.w / 2, fb.y + fb.h / 2] : from, tc = te ? [tb.x + tb.w / 2, tb.y + tb.h / 2] : to;
      const gap = o.gap ?? 10;
      const A = fe ? edgePoint(fb, tc, gap) : fc, B = te ? edgePoint(tb, fc, gap) : tc;
      const r = seeded(seedFor(o, fe || te, "arrow" + A.join(",") + B.join(",")));
      const dx = B[0] - A[0], dy = B[1] - A[1], dist = Math.hypot(dx, dy) || 1;
      const nx = -dy / dist, ny = dx / dist;
      const bend = o.bend ?? (r() < 0.5 ? -1 : 1) * (0.14 + r() * 0.1);
      const C = [(A[0] + B[0]) / 2 + nx * bend * dist, (A[1] + B[1]) / 2 + ny * bend * dist];
      const shaft = [], ph = r() * 6.283;
      for (let i = 0; i <= 40; i++) {
        const u = i / 40, a = (1 - u) * (1 - u), b2 = 2 * u * (1 - u), c = u * u;
        const wob = 1.2 * Math.sin(6.283 * 1.6 * u + ph) * Math.sin(Math.PI * u);
        shaft.push([a * A[0] + b2 * C[0] + c * B[0] + nx * wob, a * A[1] + b2 * C[1] + c * B[1] + ny * wob]);
      }
      const tx = B[0] - C[0], ty = B[1] - C[1], tn = Math.hypot(tx, ty) || 1, ux = tx / tn, uy = ty / tn;
      const hl = o.head ?? Math.max(16, Math.min(30, dist * 0.14));
      const rot = (deg, len) => {
        const a = (deg * Math.PI) / 180;
        return [B[0] - len * (ux * Math.cos(a) - uy * Math.sin(a)), B[1] - len * (ux * Math.sin(a) + uy * Math.cos(a))];
      };
      const head = [rot(27 + r() * 6, hl), B, rot(-(27 + r() * 6), hl * (0.85 + r() * 0.15))];
      const dur = o.dur ?? 0.32;
      const s = stroke(layer, shaft, o), h = stroke(layer, head, o);
      drawOn(tl, s, t, dur * 0.7, o.ease ?? "power2.in");
      drawOn(tl, h, t + dur * 0.7, dur * 0.3, "power2.out");
      return [s, h];
    },

    // handwriting written on left to right, word by word, in red marker script. The element carries the text and
    // class an-hand (Caveat 700, red; add class ink for dark pen). o: dur (default chars / cps), cps (70: "Stanley's
    // main factory" in 0.3 s), rot (deg, -3: a quick hand runs uphill). Nested elements stay whole.
    scribble(tl, sel, t, o = {}) {
      if (AR.names) AR.names();
      all(sel).forEach((el) => {
        if (!el.dataset.anHand) {
          el.dataset.anHand = "1";
          Array.from(el.childNodes).forEach((node) => {
            if (node.nodeType === Node.ELEMENT_NODE) { node.classList.add("an-w"); return; }
            const frag = document.createDocumentFragment();
            node.textContent.split(/(\s+)/).forEach((p) => {
              if (!p) return;
              if (/^\s+$/.test(p)) { frag.appendChild(document.createTextNode(p)); return; }
              const s = document.createElement("span");
              s.className = "an-w";
              s.textContent = p;
              frag.appendChild(s);
            });
            node.replaceWith(frag);
          });
          gsap.set(el, { rotation: o.rot ?? -3 });
        }
        const words = Array.from(el.querySelectorAll(".an-w"));
        const chars = words.reduce((n, w) => n + Math.max(1, w.textContent.length), 0);
        const dur = o.dur ?? Math.max(0.18, chars / (o.cps ?? 70));
        const wg = Math.min(0.03, dur / (words.length * 6)), per = (dur - wg * (words.length - 1)) / chars;
        let c = t;
        words.forEach((w) => {
          const d = Math.max(1, w.textContent.length) * per;
          tl.fromTo(w, { "--an-p": "-12%" }, { "--an-p": "112%", duration: d, ease: "none" }, c);
          c += d + wg;
        });
      });
      return tl;
    },

    // a sticky note slapped on: lands from a little larger and turned, settles with a squash. Several notes land
    // o.gap (0.3) apart. o: rot (deg; default alternates -2.5, 1.8, -1.2, 2.4), from (1.22), dur (0.11)
    sticky(tl, sel, t, o = {}) {
      all(sel).forEach((el, i) => {
        const ti = o.times ? o.times[i] : t + i * (o.gap ?? 0.3);
        const rot = o.rot ?? (el.dataset.rot != null ? +el.dataset.rot : [-2.5, 1.8, -1.2, 2.4][i % 4]);
        const d = o.dur ?? 0.11;
        onTop(el);
        tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: d * 0.6, ease: "none" }, ti);
        tl.fromTo(el, { scale: o.from ?? 1.22, rotation: rot + 6, y: -16 }, { scale: 1, rotation: rot, y: 0, duration: d, ease: "power3.in" }, ti);
        tl.to(el, { scaleX: 1.025, scaleY: 0.97, duration: 0.04, ease: "power1.out" }, ti + d);
        tl.to(el, { scaleX: 1, scaleY: 1, duration: 0.16, ease: "back.out(3)" }, ti + d + 0.04);
      });
      return tl;
    },

    // numbered red boxes drawn round regions, in step with a legend: box i and legend row i land together, o.gap
    // (0.09) apart, or at o.times. boxes: elements to outline; legend: its rows (a missing .an-num tag is added).
    // o: pad (6 px), start (1), layer. Returns the boxes.
    callouts(tl, boxes, legend, t, o = {}) {
      const B = all(boxes), Lg = legend ? all(legend) : [];
      if (!B.length) return [];
      const layer = layerFor(B[0], o), pad = o.pad ?? 6, n0 = o.start ?? 1;
      return B.map((el, i) => {
        const b = boxIn(el, layer), ti = o.times ? o.times[i] : t + i * (o.gap ?? 0.09);
        const d = document.createElement("div");
        d.className = "an-callout";
        d.setAttribute("data-layout-ignore", "");
        Object.assign(d.style, { left: b.x - pad + "px", top: b.y - pad + "px", width: b.w + 2 * pad + "px", height: b.h + 2 * pad + "px" });
        if (o.color) d.style.borderColor = o.color;
        const num = document.createElement("b");
        num.className = "an-num";
        num.textContent = n0 + i;
        if (o.color) num.style.background = o.color;
        d.appendChild(num);
        marksFor(layer).appendChild(d);
        tl.fromTo(d, { opacity: 0, scale: 1.07 }, { opacity: 1, scale: 1, duration: 0.1, ease: "power2.out" }, ti);
        tl.fromTo(num, { scale: 0.3 }, { scale: 1, duration: 0.18, ease: "back.out(3)" }, ti);
        const row = Lg[i];
        if (row) {
          let tag = row.querySelector(".an-num");
          if (!tag) { tag = document.createElement("b"); tag.className = "an-num"; tag.textContent = n0 + i; row.prepend(tag); }
          tl.fromTo(row, { opacity: 0, x: -16 }, { opacity: 1, x: 0, duration: 0.14, ease: "power2.out" }, ti + 0.02);
          tl.fromTo(tag, { scale: 0.4 }, { scale: 1, duration: 0.18, ease: "back.out(3)" }, ti + 0.02);
        }
        return d;
      });
    },

    // leader lines: from points on an object to labels that type on, o.gap (0.13) apart. items: [{label, at}]:
    // label is a positioned .an-leader element (<br/> breaks lines; class ink for dark text), at is [x, y] in
    // scene px or an element (its centre). The line runs from a dot on the object to the label's near side.
    // o: color ("#fff" on a blueprint; "#2a2620" for ink on paper), width (3), dot (7), cps (45), gap, times,
    // layer. Returns the line paths.
    leaders(tl, items, t, o = {}) {
      const color = o.color || "#fff";
      return items.map((it, i) => {
        const lab = one(it.label);
        const layer = o.layer ? one(o.layer) : layerFor(lab, o);
        const lb = boxIn(lab, layer);
        let P = it.at;
        if (!isPoint(P)) { const ab = boxIn(one(P), layer); P = [ab.x + ab.w / 2, ab.y + ab.h / 2]; }
        // attach at the label's near side, beside its first line; under or over it when the point is in its span
        const lh = parseFloat(getComputedStyle(lab).lineHeight) || 36;
        const E = P[0] > lb.x + lb.w ? [lb.x + lb.w + 10, lb.y + Math.min(lb.h, lh) * 0.62]
          : P[0] < lb.x ? [lb.x - 10, lb.y + Math.min(lb.h, lh) * 0.62]
          : [P[0], P[1] < lb.y ? lb.y - 8 : lb.y + lb.h + 6];
        const ti = o.times ? o.times[i] : t + i * (o.gap ?? 0.13);
        const line = stroke(layer, [P, E], { color, width: o.width ?? 3 }, "an-leader-line");
        line.style.strokeLinecap = "butt";
        const dot = document.createElementNS(NS, "circle");
        dot.setAttribute("cx", P[0]); dot.setAttribute("cy", P[1]); dot.setAttribute("r", o.dot ?? 7); dot.setAttribute("fill", color);
        svgOf(layer).appendChild(dot);
        tl.fromTo(dot, { scale: 0, transformOrigin: "50% 50%" }, { scale: 1, duration: 0.12, ease: "back.out(3)" }, ti);
        drawOn(tl, line, ti, 0.1, "power2.out");
        typeOn(tl, lab, ti + 0.06, o.cps ?? 45);
        return line;
      });
    },

    // ---------- stamps and badges ----------
    // a heavy stamp: oversized, see-through and motion-blurred for two frames, then it lands at t + dur (0.1),
    // turned o.rot (-8), with a squash, while its container (o.bump: an element, default its parent; false for
    // none) bumps down 3, 4, 3 px over three frames. Several elements land o.gap (0.1) apart (a FILLED cascade).
    // Position the stamp with left/top, never a CSS transform. o: from (2.3), blur (9), spin (6 deg)
    slam(tl, sel, t, o = {}) {
      all(sel).forEach((el, i) => {
        const ti = o.times ? o.times[i] : t + i * (o.gap ?? 0.1);
        const rot = o.rot ?? (el.dataset.rot != null ? +el.dataset.rot : -8), d = o.dur ?? 0.1;
        onTop(el);
        tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: d, ease: "power1.out" }, ti);
        tl.fromTo(el, { scale: o.from ?? 2.3, rotation: rot - (o.spin ?? 6), filter: `blur(${o.blur ?? 9}px)` },
          { scale: 1, rotation: rot, filter: "blur(0px)", duration: d, ease: "power2.in" }, ti);
        tl.set(el, { filter: "none" }, ti + d);
        tl.to(el, { scale: 0.955, duration: 0.035, ease: "power1.out" }, ti + d);
        tl.to(el, { scale: 1, duration: 0.15, ease: "back.out(3)" }, ti + d + 0.035);
        let bump = o.bump === false ? null : o.bump ? one(o.bump) : el.parentElement;
        if (bump && (bump.hasAttribute("data-composition-id") || bump.classList.contains("an-layer"))) bump = null;
        if (bump) [3, 4, 3, 0].forEach((y, k) => tl.set(bump, { y }, ti + d + k / 30));
      });
      return tl;
    },

    // a badge pops in with a twist (.an-free, .an-check, .an-down, .an-cross, .an-pill, .an-stamp.sm ...).
    // Several pop o.gap (0.08) apart. o: rot (deg it ends at), dur (0.3)
    badge(tl, sel, t, o = {}) {
      all(sel).forEach((el, i) => {
        const ti = o.times ? o.times[i] : t + i * (o.gap ?? 0.08), rot = o.rot ?? 0;
        onTop(el);
        tl.fromTo(el, { scale: 0, rotation: rot - 16, opacity: 0 }, { scale: 1, rotation: rot, opacity: 1, duration: o.dur ?? 0.3, ease: "back.out(2.6)" }, ti);
      });
      return tl;
    },

    // a doubtful claim: a hand underline draws under it, then a red "?" pops beside its end (o.q: your own
    // element, else one is made). Underline options pass through. Returns the "?".
    question(tl, target, t, o = {}) {
      const el = one(target);
      if (!el) return null;
      const layer = layerFor(el, o), b = boxIn(el, layer), dur = o.dur ?? 0.24;
      AR.underline(tl, el, t, { ...o, pen: o.pen, dur });
      let q = o.q ? one(o.q) : null;
      if (!q) {
        q = document.createElement("b");
        q.className = "an-q";
        q.textContent = "?";
        q.setAttribute("data-layout-ignore", "");
        marksFor(layer).appendChild(q);
        q.style.left = b.x + b.w + (o.qdx ?? 12) + "px";
        q.style.top = b.y + b.h - q.offsetHeight + (o.qdy ?? 8) + "px";
      }
      tl.fromTo(q, { scale: 0, rotation: -30, opacity: 0, transformOrigin: "50% 90%" },
        { scale: 1, rotation: 8, opacity: 1, duration: 0.28, ease: "back.out(3)" }, t + dur + (o.qDelay ?? 0.06));
      return q;
    },

    // a calc bubble pops (.an-calc), then its red result (.an-res) lands o.gap (0.2) later. o: rot, result
    calc(tl, sel, t, o = {}) {
      all(sel).forEach((el) => {
        AR.badge(tl, el, t, { rot: o.rot ?? 0, dur: 0.26 });
        const res = el.querySelector(o.result || ".an-res");
        if (res) tl.fromTo(res, { opacity: 0, scale: 0.5 }, { opacity: 1, scale: 1, duration: 0.2, ease: "back.out(3)" }, t + (o.gap ?? 0.2));
      });
      return tl;
    },

    // a claims board judged on a fixed beat: row i's verdict pill (.an-verdict, data-v="drop" or "keep") flips
    // from "Checking" at t + i * o.gap (0.13). Dropped rows get a red strike drawn across their claim (o.claim,
    // default ".an-claim") and dim. Empty pills are filled: data-label overrides "Dropped" / "Defended".
    verdicts(tl, rows, t, o = {}) {
      all(rows).forEach((row, i) => {
        const v = row.querySelector(o.verdict || ".an-verdict");
        if (!v) return;
        const kind = v.dataset.v === "keep" ? "keep" : "drop";
        if (!v.children.length) {
          v.innerHTML = `<i class="an-v-wait">${v.dataset.wait || "Checking"}</i><i class="an-v-drop">${kind === "drop" && v.dataset.label ? v.dataset.label : "Dropped"}</i><i class="an-v-keep">${kind === "keep" && v.dataset.label ? v.dataset.label : "Defended"}</i>`;
        }
        const ti = o.times ? o.times[i] : t + i * (o.gap ?? 0.13);
        const wait = v.querySelector(".an-v-wait"), fin = v.querySelector(kind === "keep" ? ".an-v-keep" : ".an-v-drop");
        // a flat flip (scaleY through 0): reads like a 3D card flip but keeps the render's fast 2D capture path
        tl.to(v, { scaleY: 0, duration: 0.06, ease: "power1.in" }, ti);
        tl.set(wait, { opacity: 0 }, ti + 0.06);
        tl.set(fin, { opacity: 1 }, ti + 0.06);
        tl.to(v, { scaleY: 1, duration: 0.12, ease: "back.out(2.2)" }, ti + 0.06);
        if (kind === "drop") {
          const claim = row.querySelector(o.claim || ".an-claim");
          if (claim) {
            AR.underline(tl, claim, ti + 0.04, { at: "through", dur: 0.16, width: o.width ?? 5, color: o.color || "#d4342b", layer: o.layer, ext: 6 });
            tl.to(claim, { opacity: 0.5, duration: 0.16, ease: "power1.out" }, ti + 0.12);
          }
        }
      });
      return tl;
    },

    // an expensive price types on, then a red strike draws through it (receipt lines: "$0.0015" beside "$0.15").
    // o: cps (30), gap (0.04 after typing), dur (0.16), width (4), color
    typeStrike(tl, sel, t, o = {}) {
      all(sel).forEach((el) => {
        const cps = o.cps ?? 30, d = AR.typeDur ? AR.typeDur(el, cps) : 0;
        if (AR.type) AR.type(tl, el, t, { cps });
        AR.underline(tl, el, t + d + (o.gap ?? 0.04), { at: "through", dur: o.dur ?? 0.16, width: o.width ?? 4, color: o.color || "#d4342b", ext: 4, tilt: o.tilt ?? 0, bow: 0, layer: o.layer, seed: o.seed });
      });
      return tl;
    },
  });
})();
