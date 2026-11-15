/* dataviz.js: charts drawn as crisp SVG and animated on the timeline: bar series whose labels count, a line chart
   that draws (optionally with a rider on its tip and a counter that tracks it), a histogram with marker lines and
   a bracket, candlesticks with a range box, level lines with axis tags and shaded zones, a fan of seeded random
   walks recoloured by outcome, and pixel coin-stack bars under a cap line. Extends window.AR; load after
   arcade.js and annotate.js (AR.fmt formats every number).

   Each chart fills a box you place and size in the scene's CSS (class dv: position absolute, left, top, width,
   height); the chart reads that size once when the scene script runs, so set it in CSS, not by animation.
   Calls take the timeline, the box, the start time and options; parts with their own moment (levels, zones,
   markers, a recolour) take their own `t` inside the options. Every call returns a handle with the scales
   (x(i), y(v)) and the elements it made, for anything extra you want to place on the chart. Seek-safe: data
   and random walks are fixed when the script runs; every visible change is a tween or set on the timeline. */
(function () {
  const AR = (window.AR = window.AR || {});
  const NS = "http://www.w3.org/2000/svg";
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
  const easeFn = (e) => (typeof e === "function" ? e : gsap.parseEase(e || "none"));
  let uid = 0;
  const S = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };
  const text = (parent, x, y, str, cls, attrs = {}) => {
    const e = S("text", { x, y, class: cls, ...attrs }, parent);
    e.textContent = str;
    return e;
  };
  const fmt = (v, f) => (typeof f === "function" ? f(v) : AR.fmt ? AR.fmt(v, f || {}) : String(Math.round(v)));
  // numbers ticking on a text element: the same sampling as AR.countTo, written here so charts can share an ease
  const tick = (tl, el, t, dur, from, to, f, ease, fps = 15) => {
    const E = easeFn(ease), n = Math.max(1, Math.round(dur * fps));
    el.textContent = fmt(from, f);
    let prev = el.textContent;
    for (let k = 1; k <= n; k++) {
      const s = fmt(k === n ? to : from + (to - from) * E(k / n), f);
      if (s !== prev) tl.set(el, { textContent: s }, t + (dur * k) / n);
      prev = s;
    }
  };
  const nice = (lo, hi, n = 4) => {
    const span = hi - lo || Math.abs(hi) || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw;
    const a = Math.floor(lo / step) * step, b = Math.ceil(hi / step) * step, ticks = [];
    for (let v = a; v <= b + step * 1e-6; v += step) ticks.push(+v.toFixed(10));
    return { lo: a, hi: b, ticks };
  };
  const host = (sel) => {
    const el = one(sel);
    el.classList.add("dv");
    const W = el.offsetWidth, H = el.offsetHeight;
    const svg = S("svg", { class: "dv-svg", width: W, height: H, viewBox: `0 0 ${W} ${H}`, "data-layout-ignore": "" });
    el.insertBefore(svg, el.firstChild);
    return { el, W, H, svg, id: (el.id || "dv") + "-c" + ++uid };
  };
  const pad4 = (p, d) => (p == null ? d : typeof p === "number" ? [p, p, p, p] : p);

  // ---------- a y-axis plot: grid, ticks, levels, zones (line, candles, fan) ----------
  const plot = (sel, o, def) => {
    const P = host(sel);
    const [pt, pr, pb, pl] = pad4(o.pad, def.pad);
    Object.assign(P, { x0: pl, x1: P.W - pr, y0: pt, y1: P.H - pb });
    const rng = o.ticks ? { lo: Math.min(...o.ticks), hi: Math.max(...o.ticks), ticks: o.ticks } : nice(def.lo, def.hi, o.tickCount ?? 4);
    P.lo = o.yMin ?? rng.lo;
    P.hi = o.yMax ?? rng.hi;
    P.y = (v) => P.y1 - ((v - P.lo) / (P.hi - P.lo)) * (P.y1 - P.y0);
    P.g = {};
    ["grid", "zones", "data", "levels", "top"].forEach((k) => (P.g[k] = S("g", { class: "dv-" + k }, P.svg)));
    const side = o.axis === undefined ? def.axis : o.axis;
    if (side) {
      const tf = o.tickFormat ?? def.tickFormat;
      rng.ticks.forEach((v) => {
        if (v < P.lo - 1e-9 || v > P.hi + 1e-9) return;
        const y = P.y(v);
        if (o.grid !== false) S("line", { x1: P.x0, x2: P.x1, y1: y, y2: y, class: "dv-grid" }, P.g.grid);
        const x = side === "right" ? P.x1 + 18 : P.x0 - 18;
        text(P.g.grid, x, y, fmt(v, tf), "dv-tick", { "text-anchor": side === "right" ? "start" : "end", "dominant-baseline": "central" });
      });
      if (side === "right") S("line", { x1: P.x1, x2: P.x1, y1: P.y0 - 20, y2: P.y1 + 20, class: "dv-axis" }, P.g.grid);
    }
    P.side = side;
    return P;
  };
  // a horizontal level: a line that draws across, a bold label riding it, a filled tag on the axis
  const level = (tl, P, lv, o) => {
    const color = lv.color || "#13a37f", y = P.y(lv.y), t = lv.t ?? 0;
    const xs = lv.from != null ? P.xAt(lv.from) : P.x0, xe = lv.to != null ? P.xAt(lv.to) : P.x1;
    const g = S("g", { class: "dv-level" }, P.g.levels);
    const line = S("line", { x1: xs, y1: y, x2: xs, y2: y, stroke: color, "stroke-width": lv.width ?? 3, "stroke-dasharray": lv.dash === false ? null : lv.dash || "11 8" }, g);
    tl.set(g, { opacity: 0 }, 0);
    tl.set(g, { opacity: 1 }, t);
    tl.fromTo(line, { attr: { x2: xs } }, { attr: { x2: xe }, duration: lv.dur ?? 0.3, ease: "power2.out" }, t);
    let label = null, tag = null;
    if (lv.label) {
      const below = lv.below === true;
      const lx = lv.labelX != null ? P.xAt(lv.labelX) : xs + 10;
      label = text(g, lx, below ? y + 34 : y - 14, lv.label, "dv-lvl-label", { fill: color });
      tl.fromTo(label, { opacity: 0, y: below ? -8 : 8 }, { opacity: 1, y: 0, duration: 0.2, ease: "power2.out" }, t + 0.1);
    }
    if (lv.tag !== false && P.side) {
      const str = lv.tag || fmt(lv.y, o.tagFormat ?? o.tickFormat ?? { style: "dec", digits: 2 });
      tag = S("g", { class: "dv-tag" }, P.g.top);
      const right = P.side === "right";
      const tx = text(tag, 0, y, str, "dv-tag-text", { "dominant-baseline": "central", "text-anchor": "middle" });
      const w = Math.max(72, tx.getComputedTextLength() + 24), x = right ? P.x1 + 2 : P.x0 - 2 - w;
      const rect = S("rect", { x, y: y - 19, width: w, height: 38, rx: 3, fill: color });
      tag.insertBefore(rect, tx);
      tx.setAttribute("x", x + w / 2);
      tl.fromTo(tag, { opacity: 0, scale: 0.6, transformOrigin: right ? "0% 50%" : "100% 50%" }, { opacity: 1, scale: 1, duration: 0.2, ease: "back.out(3)" }, t + 0.04);
    }
    return { g, line, label, tag };
  };
  const zone = (tl, P, z) => {
    const ya = P.y(z.y0), yb = P.y(z.y1), top = Math.min(ya, yb), h = Math.abs(ya - yb);
    const xs = z.from != null ? P.xAt(z.from) : P.x0, xe = z.to != null ? P.xAt(z.to) : P.x1;
    const r = S("rect", { x: xs, y: top, width: 0, height: h, fill: z.color || "#13a37f", "fill-opacity": z.opacity ?? 0.16 }, P.g.zones);
    tl.set(r, { opacity: 0 }, 0);
    tl.set(r, { opacity: 1 }, z.t ?? 0);
    tl.fromTo(r, { attr: { width: 0 } }, { attr: { width: xe - xs }, duration: z.dur ?? 0.35, ease: "power2.out" }, z.t ?? 0);
    return r;
  };

  Object.assign(AR, {
    // bars that grow while their value labels count. data: [{label, value, color}]. o.dir "h" (rows, labels on
    // the left, values riding the bar ends) or "v" (columns, labels under, values riding the tops); max (axis
    // end), format (value labels: a fmt() spec), dur (0.6), gap (0.12 between bars), ease ("power2.out"), ticks
    // + tickFormat (an axis under h bars), labelW (h: label column px), barH / barW, colors.
    bars(tl, sel, t, o = {}) {
      const P = host(sel), data = o.data || [], n = data.length, dir = o.dir || "h";
      const max = o.max ?? Math.max(...data.map((d) => d.value)) * 1.12, dur = o.dur ?? 0.6, ease = o.ease ?? "power2.out";
      const colors = o.colors || ["#22894f", "#d9714f", "#b0ad9f", "#3f6fe0", "#f7c531"];
      const f = o.format ?? { style: "int" };
      const out = { el: P.el, svg: P.svg, bars: [], values: [], labels: [] };
      if (dir === "h") {
        const labelW = o.labelW ?? Math.round(P.W * 0.3), valueW = o.valueW ?? 150, axisH = o.ticks ? 58 : 0;
        const x0 = labelW + 22, x1 = P.W - valueW, rowH = (P.H - axisH) / n, bh = o.barH ?? Math.min(70, rowH * 0.66);
        const X = (v) => x0 + (Math.max(0, v) / max) * (x1 - x0);
        out.x = X;
        data.forEach((d, i) => {
          const cy = rowH * (i + 0.5), ti = t + i * (o.gap ?? 0.12), w = X(d.value) - x0;
          out.labels.push(text(P.svg, labelW, cy, d.label, "dv-label", { "text-anchor": "end", "dominant-baseline": "central" }));
          const bar = S("rect", { x: x0, y: cy - bh / 2, width: 0, height: bh, rx: o.radius ?? 4, fill: d.color || colors[i % colors.length] }, P.svg);
          const val = text(P.svg, x0 + 16, cy, "", "dv-value", { "dominant-baseline": "central" });
          tl.fromTo(bar, { attr: { width: 0 } }, { attr: { width: w }, duration: dur, ease }, ti);
          tl.fromTo(val, { attr: { x: x0 + 16 } }, { attr: { x: x0 + w + 16 }, duration: dur, ease }, ti);
          tick(tl, val, ti, dur, 0, d.value, d.format ?? f, ease);
          out.bars.push(bar); out.values.push(val);
        });
        if (o.ticks) {
          const ay = P.H - axisH + 10;
          S("line", { x1: x0, x2: x1, y1: ay, y2: ay, class: "dv-axis" }, P.svg);
          o.ticks.forEach((v) => text(P.svg, X(v), ay + 30, fmt(v, o.tickFormat ?? f), "dv-tick", { "text-anchor": "middle", "dominant-baseline": "central" }));
        }
      } else {
        const labelH = o.labelH ?? 60, valueH = o.valueH ?? 56, base = P.H - labelH, top = valueH;
        const colW = P.W / n, bw = o.barW ?? Math.min(130, colW * 0.6);
        const Y = (v) => base - (Math.max(0, v) / max) * (base - top);
        out.y = Y;
        S("line", { x1: 0, x2: P.W, y1: base, y2: base, class: "dv-axis" }, P.svg);
        data.forEach((d, i) => {
          const cx = colW * (i + 0.5), ti = t + i * (o.gap ?? 0.12), h = base - Y(d.value);
          out.labels.push(text(P.svg, cx, base + labelH / 2 + 2, d.label, "dv-label", { "text-anchor": "middle", "dominant-baseline": "central" }));
          const bar = S("rect", { x: cx - bw / 2, y: base, width: bw, height: 0, rx: o.radius ?? 4, fill: d.color || colors[i % colors.length] }, P.svg);
          const val = text(P.svg, cx, base - 16, "", "dv-value", { "text-anchor": "middle" });
          tl.fromTo(bar, { attr: { y: base, height: 0 } }, { attr: { y: base - h, height: h }, duration: dur, ease }, ti);
          tl.fromTo(val, { attr: { y: base - 16 } }, { attr: { y: base - h - 16 }, duration: dur, ease }, ti);
          tick(tl, val, ti, dur, 0, d.value, d.format ?? f, ease);
          out.bars.push(bar); out.values.push(val);
        });
      }
      return out;
    },

    // a line chart that draws left to right over dur. o.data: values (evenly spaced) or [x, y] pairs; color
    // ("#b5179e"), width (5), area (true: a soft fill under it), ticks / yMin / yMax / tickFormat / axis ("left",
    // "right", false), ease ("none": the tip moves at a steady x speed), dot (a dot on the tip), rider (an element,
    // say a .sprite, that rides the tip: it is moved into the chart box, its feet on the line, o.riderDy to sink
    // or lift it), counter (an element that shows the value under the tip, formatted by o.counterFormat),
    // levels [{y, label, color, dash, t, tag, from, below}].
    lineChart(tl, sel, t, dur, o = {}) {
      const pts0 = (o.data || []).map((d, i, a) => (Array.isArray(d) ? d : [i / Math.max(1, a.length - 1), d]));
      const xs = pts0.map((p) => p[0]), ys = pts0.map((p) => p[1]);
      const xa = Math.min(...xs), xb = Math.max(...xs);
      const P = plot(sel, o, { pad: [30, 30, 30, 120], axis: "left", lo: Math.min(0, ...ys), hi: Math.max(...ys) * 1.05, tickFormat: { style: "compact" } });
      P.xAt = (f) => P.x0 + f * (P.x1 - P.x0);
      const X = (v) => P.x0 + ((v - xa) / (xb - xa || 1)) * (P.x1 - P.x0);
      const pts = pts0.map((p) => [X(p[0]), P.y(p[1])]);
      const color = o.color || "#b5179e", width = o.width ?? 5, ease = o.ease ?? "none", E = easeFn(ease);
      const clipId = P.id + "-clip";
      const defs = S("defs", {}, P.svg);
      const clip = S("clipPath", { id: clipId }, defs);
      const cr = S("rect", { x: P.x0 - width * 2, y: -P.H, width: 0, height: P.H * 3 }, clip);
      const d = "M" + pts.map((p) => p[0].toFixed(1) + " " + p[1].toFixed(1)).join("L");
      if (o.area) {
        const gid = P.id + "-grad", grad = S("linearGradient", { id: gid, x1: 0, x2: 0, y1: 0, y2: 1 }, defs);
        S("stop", { offset: "0%", "stop-color": color, "stop-opacity": 0.22 }, grad);
        S("stop", { offset: "100%", "stop-color": color, "stop-opacity": 0 }, grad);
        S("path", { d: d + `L${pts[pts.length - 1][0]} ${P.y1}L${pts[0][0]} ${P.y1}Z`, fill: `url(#${gid})`, "clip-path": `url(#${clipId})` }, P.g.data);
      }
      const line = S("path", { d, fill: "none", stroke: color, "stroke-width": width, "stroke-linejoin": "round", "stroke-linecap": "round", "clip-path": `url(#${clipId})` }, P.g.data);
      const full = P.x1 - P.x0 + width * 4;
      tl.fromTo(cr, { attr: { width: 0 } }, { attr: { width: full }, duration: dur, ease }, t);
      // the tip: x moves with the clip; y is the line's height there
      const yAtX = (x) => {
        if (x <= pts[0][0]) return pts[0][1];
        for (let i = 1; i < pts.length; i++) if (x <= pts[i][0]) {
          const f = (x - pts[i - 1][0]) / (pts[i][0] - pts[i - 1][0] || 1);
          return pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f;
        }
        return pts[pts.length - 1][1];
      };
      const vAtX = (x) => P.lo + ((P.y1 - yAtX(x)) / (P.y1 - P.y0)) * (P.hi - P.lo);
      const N = Math.max(8, Math.min(60, Math.round(dur * 30)));
      const tipX = (k) => Math.min(P.x1, P.x0 + E(k / N) * (P.x1 - P.x0));
      const out = { el: P.el, svg: P.svg, line, x: X, y: P.y, points: pts };
      out.levels = (o.levels || []).map((lv) => level(tl, P, lv, o));
      if (o.dot) {
        const dot = S("circle", { cx: pts[0][0], cy: pts[0][1], r: o.dot === true ? 9 : o.dot, fill: color, stroke: "#fff", "stroke-width": 4 }, P.g.top);
        for (let k = 1; k <= N; k++) tl.to(dot, { attr: { cx: tipX(k), cy: yAtX(tipX(k)) }, duration: dur / N, ease: "none" }, t + (dur * (k - 1)) / N);
        out.dot = dot;
      }
      if (o.rider) {
        const rd = one(o.rider);
        if (rd.parentElement !== P.el) P.el.appendChild(rd);
        Object.assign(rd.style, { left: "0px", top: "0px" });
        const rw = rd.offsetWidth, rh = rd.offsetHeight, dy = o.riderDy ?? 0;
        const at = (x) => ({ x: x - rw / 2, y: yAtX(x) - rh + dy });
        gsap.set(rd, at(pts[0][0]));
        for (let k = 1; k <= N; k++) tl.to(rd, { ...at(tipX(k)), duration: dur / N, ease: "none" }, t + (dur * (k - 1)) / N);
        out.rider = rd;
      }
      if (o.counter) {
        const c = one(o.counter), cf = o.counterFormat ?? { style: "int" }, n = Math.max(4, Math.round(dur * (o.fps ?? 15)));
        c.textContent = fmt(ys[0], cf);
        let prev = c.textContent;
        for (let k = 1; k <= n; k++) {
          const x = Math.min(P.x1, P.x0 + E(k / n) * (P.x1 - P.x0));
          const s = fmt(k === n ? ys[ys.length - 1] : vAtX(x), cf);
          if (s !== prev) tl.set(c, { textContent: s }, t + (dur * k) / n);
          prev = s;
        }
      }
      return out;
    },

    // a histogram: bars rise left to right, then marker lines drop in with two-line labels, then a bracket draws
    // under the axis. o.bins: counts; range [lo, hi] (the value span of the bins); color ("#d9714f"); gap (px
    // between bars, 6); stagger (0.03); dur (0.22 per bar); ticks + tickFormat (x labels); markers [{x, label,
    // sub, color, t, dash}]; bracket {from, to, t, label}; pad [top, right, bottom, left].
    histogram(tl, sel, t, o = {}) {
      const P = host(sel), bins = o.bins || [], n = bins.length;
      const [pt, pr, pb, pl] = pad4(o.pad, [120, 10, o.bracket ? 112 : 60, 10]);
      const x0 = pl, x1 = P.W - pr, y0 = pt, y1 = P.H - pb;
      const [lo, hi] = o.range || [0, n];
      const X = (v) => x0 + ((v - lo) / (hi - lo)) * (x1 - x0);
      const top = Math.max(...bins) * 1.04, bw = (x1 - x0) / n, gap = o.gap ?? 6;
      const out = { el: P.el, svg: P.svg, x: X, bars: [], markers: [] };
      const gBars = S("g", {}, P.svg), gMk = S("g", {}, P.svg);
      S("line", { x1: x0, x2: x1, y1: y1, y2: y1, class: "dv-axis" }, gBars);
      bins.forEach((c, i) => {
        const h = (c / top) * (y1 - y0), ti = t + i * (o.stagger ?? 0.03);
        const r = S("rect", { x: x0 + i * bw + gap / 2, y: y1, width: bw - gap, height: 0, rx: 2, fill: o.color || "#d9714f" }, gBars);
        tl.fromTo(r, { attr: { y: y1, height: 0 } }, { attr: { y: y1 - h, height: h }, duration: o.dur ?? 0.22, ease: "power2.out" }, ti);
        out.bars.push(r);
      });
      (o.ticks || []).forEach((v) => text(gBars, X(v), y1 + 32, fmt(v, o.tickFormat ?? { style: "usd", digits: 0 }), "dv-tick", { "text-anchor": "middle", "dominant-baseline": "central" }));
      (o.markers || []).forEach((m) => {
        const x = X(m.x), color = m.color || "#1f1e1c", tm = m.t ?? t, g = S("g", {}, gMk);
        const ly = y0 - 82;
        const line = S("line", { x1: x, x2: x, y1: y0 - 10, y2: y0 - 10, stroke: color, "stroke-width": 3, "stroke-dasharray": m.dash === false ? null : "8 6" }, g);
        const a = m.label ? text(g, x, ly, m.label, "dv-mk-label", { "text-anchor": "middle", fill: color }) : null;
        const b = m.sub ? text(g, x, ly + 36, m.sub, "dv-mk-sub", { "text-anchor": "middle", fill: color }) : null;
        tl.set(g, { opacity: 0 }, 0);
        tl.set(g, { opacity: 1 }, tm);
        tl.fromTo(line, { attr: { y2: y0 - 10 } }, { attr: { y2: y1 } , duration: 0.28, ease: "power2.inOut" }, tm);
        [a, b].forEach((e, k) => e && tl.fromTo(e, { opacity: 0, y: -10 }, { opacity: 1, y: 0, duration: 0.2, ease: "power2.out" }, tm + k * 0.05));
        out.markers.push(g);
      });
      if (o.bracket) {
        const bk = o.bracket, xa = X(bk.from), xb = X(bk.to), by = y1 + 78;
        const p = S("path", { d: `M${xa} ${by - 16}V${by}H${xb}V${by - 16}`, fill: "none", stroke: bk.color || "#1f1e1c", "stroke-width": 4, "stroke-linejoin": "round", pathLength: 1 }, P.svg);
        p.style.strokeDasharray = "1 1";
        tl.set(p, { opacity: 0 }, 0);
        tl.set(p, { opacity: 1 }, bk.t ?? t);
        tl.fromTo(p, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: 0.35, ease: "power2.inOut" }, bk.t ?? t);
        if (bk.label) {
          const lab = text(P.svg, (xa + xb) / 2, by + 30, bk.label, "dv-mk-label", { "text-anchor": "middle", fill: bk.color || "#1f1e1c" });
          tl.fromTo(lab, { opacity: 0 }, { opacity: 1, duration: 0.2 }, (bk.t ?? t) + 0.25);
        }
        out.bracket = p;
      }
      return out;
    },

    // candlesticks, left to right. o.data: [[open, high, low, close], ...]; slots (candle places across, default
    // the data length: more leaves room on the right); up / down colours; stagger (0.05); ticks / yMin / yMax /
    // tickFormat ({style: "dec", digits: 2}) / axis ("right"); range {from, to, t, y0, y1}: the opening-range box
    // round candles from..to; levels [{y, label, color, dash, t, tag, from, below}]; zones [{y0, y1, color,
    // from, to, t, opacity}] (from / to: candle index). The handle's x(i) is candle i's centre.
    candles(tl, sel, t, o = {}) {
      const data = o.data || [], lows = data.map((c) => c[2]), highs = data.map((c) => c[1]);
      const lvY = (o.levels || []).map((l) => l.y).concat((o.zones || []).flatMap((z) => [z.y0, z.y1]));
      const P = plot(sel, o, { pad: [24, 150, 24, 20], axis: "right", lo: Math.min(...lows, ...lvY), hi: Math.max(...highs, ...lvY), tickFormat: { style: "dec", digits: 2 } });
      const slots = o.slots ?? data.length, sw = (P.x1 - P.x0) / slots;
      const X = (i) => P.x0 + sw * (i + 0.5);
      P.xAt = (i) => (i >= slots ? P.x1 : P.x0 + sw * i);
      const up = o.up || "#13a37f", down = o.down || "#e5484d", bw = Math.max(6, sw * (o.body ?? 0.62));
      const out = { el: P.el, svg: P.svg, x: X, y: P.y, candles: [] };
      if (o.range) {
        const R = o.range, seg = data.slice(R.from, R.to + 1);
        const ya = P.y(R.y1 ?? Math.max(...seg.map((c) => c[1]))) - 10, yb = P.y(R.y0 ?? Math.min(...seg.map((c) => c[2]))) + 10;
        const xa = P.xAt(R.from) + 2, wd = sw * (R.to - R.from + 1) - 4;
        const rr = S("rect", { x: xa, y: ya, width: wd, height: yb - ya, fill: R.color || "#e3e8fb", stroke: R.stroke || "#8ea2e8", "stroke-width": 3 }, P.g.zones);
        tl.fromTo(rr, { opacity: 0, attr: { width: 0 } }, { opacity: 1, attr: { width: wd }, duration: 0.3, ease: "power2.out" }, R.t ?? t);
        out.range = rr;
      }
      data.forEach(([op, hi, lo, cl], i) => {
        const g = S("g", {}, P.g.data), c = cl >= op ? up : down, ti = t + i * (o.stagger ?? 0.05);
        const yt = P.y(Math.max(op, cl)), yb = Math.max(yt + 4, P.y(Math.min(op, cl)));
        const wick = S("line", { x1: X(i), x2: X(i), y1: P.y(hi), y2: P.y(lo), stroke: c, "stroke-width": 3 }, g);
        const body = S("rect", { x: X(i) - bw / 2, y: yt, width: bw, height: yb - yt, fill: c }, g);
        const yo = P.y(op);
        tl.fromTo(g, { opacity: 0 }, { opacity: 1, duration: 0.06, ease: "none" }, ti);
        tl.fromTo(body, { attr: { y: yo, height: 1 } }, { attr: { y: yt, height: yb - yt }, duration: o.dur ?? 0.18, ease: "power2.out" }, ti);
        tl.fromTo(wick, { scaleY: 0.2, transformOrigin: "50% 50%" }, { scaleY: 1, duration: o.dur ?? 0.18, ease: "power2.out" }, ti);
        out.candles.push(g);
      });
      out.zones = (o.zones || []).map((z) => zone(tl, P, z));
      out.levels = (o.levels || []).map((lv) => level(tl, P, lv, o));
      return out;
    },

    // a fan of seeded random walks spraying from one point (Monte Carlo replays), then recoloured by outcome at
    // o.recolor: walks that reach o.target first turn green (with hit dots where they cross), ones that reach
    // o.stop first turn red, the rest go grey. o: n (60), steps (32), seed, start (value), vol (per step), drift,
    // from (start x as a fraction, 0.04), yMin / yMax / ticks / tickFormat / axis, color, width (1.6), opacity
    // (0.5), target / stop {y, color, label, t} (drawn as levels at their t), dots (14 max), counter + count (a
    // number that counts the replays while they draw), pin (true: a lollipop at the start).
    pathFan(tl, sel, t, dur, o = {}) {
      const r = seeded(o.seed ?? 7), n = o.n ?? 60, steps = o.steps ?? 32, v0 = o.start ?? 100, vol = o.vol ?? 1, drift = o.drift ?? 0;
      const gauss = () => { const u = 1 - r(), v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(6.2832 * v); };
      const walks = [];
      for (let i = 0; i < n; i++) {
        const w = [v0];
        for (let k = 1; k <= steps; k++) w.push(w[k - 1] + drift + vol * gauss());
        walks.push(w);
      }
      const flat = walks.flat(), tg = o.target, st = o.stop;
      const lv = [tg, st].filter(Boolean).map((l) => l.y);
      const P = plot(sel, o, { pad: [24, 150, 24, 20], axis: "right", lo: Math.min(...flat, ...lv), hi: Math.max(...flat, ...lv), tickFormat: { style: "dec", digits: 2 } });
      P.xAt = (f) => P.x0 + f * (P.x1 - P.x0);
      const xs = P.xAt(o.from ?? 0.04), X = (k) => xs + (k / steps) * (P.x1 - xs);
      const color = o.color || "#4f6fe0", recolor = o.recolor;
      const out = { el: P.el, svg: P.svg, y: P.y, paths: [], hits: [] };
      const dots = [];
      walks.forEach((w, i) => {
        const d = "M" + w.map((v, k) => X(k).toFixed(1) + " " + P.y(v).toFixed(1)).join("L");
        const p = S("path", { d, fill: "none", "stroke-width": o.width ?? 1.6, "stroke-linejoin": "round", pathLength: 1 }, P.g.data);
        p.style.stroke = color;
        p.style.strokeOpacity = o.opacity ?? 0.5;
        p.style.strokeDasharray = "1 1";
        const ti = t + (i / n) * dur * 0.55;
        tl.set(p, { opacity: 0 }, 0);
        tl.set(p, { opacity: 1 }, ti);
        tl.fromTo(p, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: dur * 0.45, ease: "power1.out" }, ti);
        let kind = "none", hx = 0;
        for (let k = 1; k <= steps; k++) {
          if (tg && w[k] >= tg.y) { kind = "hit"; hx = X(k - 1) + ((tg.y - w[k - 1]) / (w[k] - w[k - 1])) * (X(k) - X(k - 1)); break; }
          if (st && w[k] <= st.y) { kind = "stop"; break; }
        }
        if (recolor != null) {
          const c = kind === "hit" ? tg.color || "#13a37f" : kind === "stop" ? st.color || "#e5484d" : o.none || "#a8a59c";
          tl.to(p, { stroke: c, strokeOpacity: kind === "none" ? 0.35 : 0.75, duration: 0.25, ease: "power1.out" }, recolor + i * (0.35 / n));
        }
        if (kind === "hit") dots.push(hx);
        out.paths.push(p);
      });
      if (o.pin !== false) {
        const py = P.y(v0);
        S("line", { x1: xs, x2: xs, y1: py, y2: P.y1 + 30, stroke: o.pinColor || "#13a37f", "stroke-width": 6 }, P.g.top);
        S("circle", { cx: xs, cy: py, r: 10, fill: "#fff", stroke: o.pinColor || "#13a37f", "stroke-width": 5 }, P.g.top);
      }
      if (tg) out.target = level(tl, P, { color: tg.color || "#13a37f", dash: false, ...tg, t: tg.t ?? recolor ?? t }, o);
      if (st) out.stop = level(tl, P, { color: st.color || "#e5484d", ...st, t: st.t ?? recolor ?? t }, o);
      if (tg && recolor != null && o.dots !== false) {
        dots.sort((a, b) => a - b).slice(0, o.dots ?? 14).forEach((x, j) => {
          const c = S("circle", { cx: x, cy: P.y(tg.y), r: 8, fill: "#fff", stroke: tg.color || "#13a37f", "stroke-width": 4 }, P.g.top);
          tl.fromTo(c, { scale: 0, transformOrigin: "50% 50%" }, { scale: 1, duration: 0.2, ease: "back.out(3)" }, recolor + 0.12 + j * 0.03);
          out.hits.push(c);
        });
      }
      if (o.counter) tick(tl, one(o.counter), t, dur, 0, o.count ?? n, o.counterFormat ?? { style: "int" }, "power1.in");
      return out;
    },

    // pixel coin-stack bars: coins stack one by one (a column of cash for kind "cash") while each value label
    // counts in the same steps, under an optional cap line. data: [{value, label, kind, logo (img src)}]; o: unit
    // (value per coin; default fits about 26 coins in the tallest), max (value at the top), cap {value, label, t,
    // color}, format ({style: "usd", digits: 0}), dur (the tallest stack's time; shorter stacks finish sooner),
    // stagger (0.05), labelH (room under the stacks: 106, 130 with logos), colW. The handle's top(i) is the y of
    // stack i's last coin and x(i) its centre, both in the box's px.
    coins(tl, sel, t, dur, o = {}) {
      const P = host(sel), data = o.data || [], n = data.length, r = seeded(o.seed ?? 11);
      const vmax = Math.max(...data.map((d) => d.value));
      const max = o.max ?? Math.max(vmax, o.cap ? o.cap.value : 0) * 1.12;
      const logos = data.some((d) => d.logo);
      const unit = o.unit ?? vmax / 26, labelH = o.labelH ?? (logos ? 130 : 106), y1 = P.H - labelH, y0 = o.top ?? 10;
      const pitch = ((y1 - y0) * unit) / max, ch = Math.max(8, Math.round(pitch + 2));
      const colW = P.W / n, cw = o.colW ?? Math.min(150, colW * 0.74);
      const f = o.format ?? { style: "usd", digits: 0 };
      const out = { el: P.el, svg: P.svg, stacks: [], values: [], top: [], x: (i) => (P.W / n) * (i + 0.5) };
      const coin = (g, x, y, w) => {
        S("rect", { x: x + 2, y, width: w - 4, height: ch, fill: "#6b4612" }, g);
        S("rect", { x, y: y + 2, width: w, height: ch - 4, fill: "#6b4612" }, g);
        S("rect", { x: x + 2, y: y + 2, width: w - 4, height: ch - 4, fill: "#f0b93a" }, g);
        S("rect", { x: x + 4, y: y + 2, width: w - 8, height: 2, fill: "#ffe08a" }, g);
        S("rect", { x: x + 2, y: y + ch - 4, width: w - 4, height: 2, fill: "#c78a1f" }, g);
      };
      const bill = (g, x, y, w) => {
        S("rect", { x, y, width: w, height: ch, fill: "#2f6b3d" }, g);
        S("rect", { x: x + 2, y: y + 2, width: w - 4, height: ch - 4, fill: "#73b97f" }, g);
        S("rect", { x: x + 2, y: y + 2, width: w - 4, height: 2, fill: "#a5d8ac" }, g);
        S("rect", { x: x + w / 2 - 9, y: y + 2, width: 18, height: ch - 4, fill: "#e2b53e" }, g);
      };
      const longest = Math.max(...data.map((d) => Math.max(1, Math.round(d.value / unit))));
      data.forEach((d, i) => {
        const cx = colW * (i + 0.5), x = cx - cw / 2, cnt = Math.max(1, Math.round(d.value / unit));
        const g = S("g", { "shape-rendering": "crispEdges" }, P.svg), ti = t + i * (o.stagger ?? 0.05), per = dur / longest;
        const coinEls = [];
        for (let k = 0; k < cnt; k++) {
          const cy = y1 - (k + 1) * pitch - (ch - pitch), jx = Math.round((r() * 2 - 1) * 3);
          const cg = S("g", {}, g);
          (d.kind === "cash" ? bill : coin)(cg, x + jx, cy, cw);
          tl.fromTo(cg, { opacity: 0, y: -14 }, { opacity: 1, y: 0, duration: Math.min(0.08, per * 1.5), ease: "power2.in" }, ti + k * per);
          coinEls.push(cg);
        }
        out.top.push(y1 - cnt * pitch);
        const val = text(P.svg, cx, y1 + (logos ? 116 : 90), "", "dv-coin-value", { "text-anchor": "middle" });
        val.textContent = fmt(0, f);
        let prev = val.textContent;
        for (let k = 1; k <= cnt; k++) {
          const s = fmt(k === cnt ? d.value : Math.min(d.value, k * unit), f);
          if (s !== prev) tl.set(val, { textContent: s }, ti + (k - 1) * per + 0.04);
          prev = s;
        }
        if (d.logo) {
          const sz = 56, ly = y1 + 14;
          S("rect", { x: cx - sz / 2, y: ly, width: sz, height: sz, rx: 14, fill: "#fff", stroke: "#e2ded5", "stroke-width": 2 }, P.svg);
          S("image", { href: d.logo, x: cx - sz / 2 + 8, y: ly + 8, width: sz - 16, height: sz - 16 }, P.svg);
        } else if (d.label) text(P.svg, cx, y1 + 30, d.label, "dv-coin-label", { "text-anchor": "middle", "dominant-baseline": "central" });
        out.stacks.push(coinEls); out.values.push(val);
      });
      S("line", { x1: 0, x2: P.W, y1: y1 + 1, y2: y1 + 1, class: "dv-axis" }, P.svg);
      if (o.cap) {
        const cp = o.cap, cy = y1 - ((cp.value / unit) * pitch), color = cp.color || "#d0393f", tc = cp.t ?? t;
        const g = S("g", {}, P.svg);
        const line = S("line", { x1: 0, x2: 0, y1: cy, y2: cy, stroke: color, "stroke-width": 4, "stroke-dasharray": "12 8" }, g);
        tl.set(g, { opacity: 0 }, 0);
        tl.set(g, { opacity: 1 }, tc);
        tl.fromTo(line, { attr: { x2: 0 } }, { attr: { x2: P.W } , duration: 0.35, ease: "power2.out" }, tc);
        if (cp.label) {
          const lab = text(g, P.W - 4, cy - 14, cp.label, "dv-cap-label px", { "text-anchor": "end", fill: color });
          tl.fromTo(lab, { opacity: 0 }, { opacity: 1, duration: 0.15 }, tc + 0.2);
        }
        out.cap = g;
      }
      return out;
    },
  });
})();
