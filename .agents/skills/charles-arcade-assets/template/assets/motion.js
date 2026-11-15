/* motion.js: camera, transitions, character moves and card moves for the arcade kit. Extends window.AR (load it
   after arcade.js). Every helper takes the timeline first and adds seekable tweens at scene seconds. Nothing reads
   the clock and nothing runs per frame: positions are measured once while the scene builds (give the boxes a helper
   measures, such as camera targets, screens, slots and tiles, explicit sizes), and everything after that is a
   function of the timeline's time.

   Camera rule (from Jake's reels): a shot cuts in complete and stays locked. The camera moves only when the story
   moves it: a jump cut-in to a closer framing of the same plate (AR.zoomCut), a push onto content as it fills
   (AR.frame, about 1.45x in 0.25 s), a pull-back reveal (AR.frame to a wide box or AR.frameReset, about 0.2 s)
   while the cast stays full size on a layer outside the camera, a zoom through a screen (AR.zoomThrough), a shake on
   a hit (AR.shake on a wrapper inside the camera). No slow drift and no settle on a cut.

   Helpers that follow another element's motion (carry, tether, lens) sample the timeline when they are called:
   call them after the moves they follow. Never give an element a CSS transform that a helper animates; wrap it. */
(function () {
  const AR = (window.AR = window.AR || {});
  const G = () => window.gsap;

  // ---------- shared ----------
  const els = (sel, root) => {
    if (sel == null || typeof sel === "number" || typeof sel === "boolean") return [];
    if (typeof sel === "string") return Array.from((root || document).querySelectorAll(sel));
    if (sel.nodeType === 1) return [sel];
    if (typeof sel.length === "number") return Array.from(sel).flatMap((s) => els(s, root));
    return [sel];
  };
  const one = (sel, root) => els(sel, root)[0] || null;
  const rnd = (seed) => () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const EASE = (e, d) => (typeof e === "function" ? e : G().parseEase(e || d || "none"));
  const lerp = (a, b, p) => a + (b - a) * p;
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const NS = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs = {}) => {
    const e = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
    return e;
  };
  let UID = 0;

  // Measuring. GSAP writes transforms inline; while measuring they are cleared, so an entrance or a camera move in
  // progress does not skew the layout. Static transforms (AR.mountScreen, a CSS-scaled screen) stay.
  const gsapMoved = (n) => n && n._gsap && n._gsap.renderTransform && n.style && n.style.transform;
  const chainOf = (n) => { const out = []; for (; n && n.nodeType === 1; n = n.parentElement) out.push(n); return out; };
  function atRest(nodes, fn) {
    const saved = [];
    nodes.forEach((n) => { if (gsapMoved(n)) { saved.push([n, n.style.transform]); n.style.transform = "none"; } });
    try { return fn(); } finally { saved.forEach(([n, v]) => { n.style.transform = v; }); }
  }
  const kOf = (ref, R) => (ref.offsetWidth ? R.width / ref.offsetWidth : 1);
  const rel = (r, R, k) => ({ x: (r.left - R.left) / k, y: (r.top - R.top) / k, w: r.width / k, h: r.height / k });
  // el's resting box in ref's own coordinates (ref's border box, before ref's own GSAP transform)
  function rest(el, ref) {
    return atRest(new Set([...chainOf(el), ...chainOf(ref)]), () => {
      const R = ref.getBoundingClientRect();
      return rel(el.getBoundingClientRect(), R, kOf(ref, R));
    });
  }
  function restUnion(list, ref) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    list.forEach((e) => {
      const r = rest(e, ref);
      x0 = Math.min(x0, r.x); y0 = Math.min(y0, r.y); x1 = Math.max(x1, r.x + r.w); y1 = Math.max(y1, r.y + r.h);
    });
    return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
  }
  // where el is drawn right now (every transform applied), in ref's coordinates
  function live(el, ref) {
    const R = ref.getBoundingClientRect();
    return rel(el.getBoundingClientRect(), R, kOf(ref, R));
  }
  const space = (el) => el.offsetParent || el.parentElement;
  // the scene's frame: the scene root inside the host HyperFrames mounts it in. Never the host: hosts are static
  // blocks stacked down the page (and can have no height), while the scene's content is laid out against its root.
  // Every measurement in this file is relative between two elements of the same scene, never against the page.
  const sceneRoot = (el) => {
    const host = el.closest("[data-composition-id]");
    if (!host || host === el) return host || document.body;
    let n = el;
    while (n.parentElement && n.parentElement !== host) n = n.parentElement;
    return n;
  };
  const originOf = (el) => {
    const o = getComputedStyle(el).transformOrigin.split(" ").map(parseFloat);
    return [o[0] || 0, o[1] || 0];
  };
  // a point given as [x, y] (in sp's coordinates) or an element (its resting box at the fractions `at`)
  function pointIn(p, sp, at) {
    if (Array.isArray(p) && typeof p[0] === "number") return p;
    const e = one(p);
    if (!e) return [0, 0];
    const r = rest(e, sp), a = at || [0.5, 0.5];
    return [r.x + r.w * a[0], r.y + r.h * a[1]];
  }
  // GSAP x/y that put the point at fractions A of el's box on P (sp coordinates) at scale s
  function placeAt(el, sp, P, A, s) {
    const r = rest(el, sp), O = originOf(el);
    return { x: P[0] - r.x - O[0] - s * (r.w * A[0] - O[0]), y: P[1] - r.y - O[1] - s * (r.h * A[1] - O[1]) };
  }
  // the offsets, scale and rotation the motion helpers have given each element, in build order
  const POS = new WeakMap();
  const pos = (el) => POS.get(el) || { x: 0, y: 0, s: 1, r: 0 };
  const setPos = (el, p) => POS.set(el, { ...pos(el), ...p });

  // Plays the timeline at build time and calls fn at t0, at every 1/fps step on the fps grid and at t1. Puts the
  // playhead back and flushes recorded start values, so tweens added later still start from the right place.
  function sampleTl(tl, t0, t1, fps, fn) {
    const prev = tl.time(), times = [t0], out = [];
    for (let i = Math.ceil(t0 * fps + 1e-6); i / fps < t1 - 1e-6; i++) times.push(i / fps);
    if (t1 > t0) times.push(t1);
    times.forEach((tt) => { tl.time(tt, true); out.push([tt, fn(tt)]); });
    tl.time(prev, true);
    tl.invalidate();
    return out;
  }
  // a text value per frame (formatted counters); text before t stays as the HTML has it
  function textTrack(tl, el, t, dur, f, fps = 60) {
    const n = Math.max(1, Math.round(dur * fps));
    let last = null;
    for (let i = 0; i <= n; i++) {
      const s = f(i / n);
      if (s !== last) tl.set(el, { textContent: s }, t + (dur * i) / n);
      last = s;
    }
  }
  // Clips are driven by a CSS variable that GSAP tweens as a plain number (it does not reliably tween clip-path
  // strings that start degenerate or collapse, such as inset(0px)); the clip shape itself is static CSS.
  const PCT = "calc(var(--ar-p) * 100%)";
  const WIPE = {
    right: `polygon(0% 0%, ${PCT} 0%, ${PCT} 100%, 0% 100%)`, left: `polygon(${PCT} 0%, 100% 0%, 100% 100%, ${PCT} 100%)`,
    down: `polygon(0% 0%, 100% 0%, 100% ${PCT}, 0% ${PCT})`, up: `polygon(0% ${PCT}, 100% ${PCT}, 100% 100%, 0% 100%)`,
  };
  function varTween(tl, el, name, a, b, t, dur, ease) {
    el.style.setProperty(name, a);
    return tl.fromTo(el, { [name]: a }, { [name]: b, duration: dur, ease, immediateRender: false }, t);
  }
  const fmtNum = (v, o = {}) => {
    const d = o.decimals ?? 0;
    const s = Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
    return (o.prefix ?? "") + s + (o.suffix ?? "");
  };

  // ================= camera =================
  // A camera is a wrapper inside the frame (its parent, normally the scene root). Each wrapper keeps its state, so
  // frames chain: build a camera's moves in time order. State in frame space: P -> s*P + c (P = a resting point).
  const RIGS = new WeakMap();
  const geoOf = (el, frame) => { const r = rest(el, frame); return { L: [r.x, r.y], O: originOf(el), w: r.w, h: r.h }; };
  const toGsap = (geo, S) => ({
    scale: S.s,
    x: S.c[0] - (1 - S.s) * (geo.L[0] + geo.O[0]),
    y: S.c[1] - (1 - S.s) * (geo.L[1] + geo.O[1]),
  });
  function rigOf(cam) {
    const c = one(cam);
    let rig = RIGS.get(c);
    if (!rig) {
      const frame = c.parentElement;
      rig = { cam: c, frame, F: [frame.clientWidth, frame.clientHeight], geo: geoOf(c, frame), S: { s: 1, c: [0, 0] }, hist: [], layers: [] };
      RIGS.set(c, rig);
    }
    return rig;
  }
  // one tween from S0 to S1 along the zoom about their fixed point; the zoom runs in log space, so a 3x push feels
  // as even as a 1.2x one, and layers at other depths stay coherent with it
  function moveS(tl, el, geo, S0, S1, t, dur, E) {
    const b = toGsap(geo, S1);
    if (!dur) {
      if (t <= 1e-6) G().set(el, b);
      return tl.set(el, b, t);
    }
    const a = toGsap(geo, S0), r = S1.s / S0.s, e = EASE(E);
    const ez = Math.abs(Math.log(r)) < 1e-6 ? e : (p) => (Math.pow(r, e(p)) - 1) / (r - 1);
    return tl.fromTo(el, a, { ...b, duration: dur, ease: ez, immediateRender: false }, t);
  }
  function layerStep(tl, ly, st) {
    const k = ly.depth, rk = Math.pow(st.r, k);
    const f = Math.abs(st.r - 1) < 1e-9 ? k : (1 - rk) / (1 - st.r);
    const S0 = ly.S, S1 = { s: rk * S0.s, c: [rk * S0.c[0] + st.v[0] * f, rk * S0.c[1] + st.v[1] * f] };
    ly.S = S1;
    moveS(tl, ly.el, ly.geo, S0, S1, st.t, st.dur, st.E);
  }
  function camStep(tl, rig, S1, t, dur, E) {
    const S0 = rig.S, r = S1.s / S0.s;
    const st = { t, dur, E, r, v: [S1.c[0] - r * S0.c[0], S1.c[1] - r * S0.c[1]] };
    rig.hist.push(st);
    rig.S = S1;
    moveS(tl, rig.cam, rig.geo, S0, S1, t, dur, E);
    rig.layers.forEach((ly) => layerStep(tl, ly, st));
  }
  function addLayers(tl, rig, layers) {
    (layers || []).forEach((l) => els(l.sel || l.el || l).forEach((el) => {
      if (el === rig.cam || rig.layers.some((x) => x.el === el)) return;
      const ly = { el, depth: l.depth ?? 1, geo: geoOf(el, rig.frame), S: l.S || { s: 1, c: [0, 0] } };
      rig.layers.push(ly);
      if (l.S) G().set(el, toGsap(ly.geo, ly.S));
      rig.hist.forEach((st) => layerStep(tl, ly, st));
    }));
  }
  function frameS(rig, target, o = {}) {
    const [FW, FH] = rig.F, geo = rig.geo, list = els(target);
    const B = o.rect ? { x: o.rect[0], y: o.rect[1], w: o.rect[2], h: o.rect[3] }
      : list.length ? restUnion(list, rig.cam) : { x: 0, y: 0, w: geo.w, h: geo.h };
    const pad = o.pad ?? Math.round(Math.min(FW, FH) * 0.06);
    const [px, py] = Array.isArray(pad) ? pad : [pad, pad];
    const aw = Math.max(1, FW - 2 * px), ah = Math.max(1, FH - 2 * py), fit = o.fit || "contain";
    let s = o.scale ?? (fit === "cover" ? Math.max(aw / B.w, ah / B.h) : fit === "width" ? aw / B.w
      : fit === "height" ? ah / B.h : Math.min(aw / B.w, ah / B.h));
    if (o.max) s = Math.min(s, o.max);
    if (o.min) s = Math.max(s, o.min);
    const at = o.at || [0.5, 0.5];
    const c = [at[0] * FW - s * (geo.L[0] + B.x + B.w / 2), at[1] * FH - s * (geo.L[1] + B.y + B.h / 2)];
    if (o.clamp !== false) [0, 1].forEach((i) => { // never show past the camera's world when it can cover the frame
      const lo = s * geo.L[i] + c[i], size = s * (i ? geo.h : geo.w), F = i ? FH : FW;
      if (size >= F - 0.5) c[i] += lo > 0 ? -lo : lo + size < F ? F - lo - size : 0;
    });
    return { s, c };
  }
  const camEase = (o, d) => o.ease || (d <= 0.4 ? "power3.out" : "power2.inOut");

  AR.frame = function (tl, cam, target, t, dur = 0.3, o = {}) {
    const rig = rigOf(cam);
    addLayers(tl, rig, o.layers);
    camStep(tl, rig, frameS(rig, target, o), t, dur, camEase(o, dur));
    return tl;
  };
  AR.zoomCut = function (tl, cam, target, t, o = {}) {
    const rig = rigOf(cam);
    addLayers(tl, rig, o.layers);
    camStep(tl, rig, frameS(rig, target, o), t, 0);
    return tl;
  };
  AR.frameReset = function (tl, cam, t, dur = 0.3, o = {}) {
    const rig = rigOf(cam);
    addLayers(tl, rig, o.layers);
    camStep(tl, rig, { s: 1, c: [0, 0] }, t, dur, camEase(o, dur));
    return tl;
  };
  AR.camLayers = function (tl, cam, layers) { addLayers(tl, rigOf(cam), layers); return tl; };
  AR.zoomThrough = function (tl, o) {
    const rig = rigOf(o.cam), screen = one(o.screen), next = one(o.next), t = o.t ?? 0, dur = o.dur ?? 0.4;
    addLayers(tl, rig, o.layers);
    if (next && !rig.layers.some((l) => l.el === next)) { // the next layer rides the screen like a sticker
      const S = rest(screen, rig.cam), geo = geoOf(next, rig.frame);
      const sp = Math.min(S.w / geo.w, S.h / geo.h);
      const cx = rig.geo.L[0] + S.x + S.w / 2, cy = rig.geo.L[1] + S.y + S.h / 2;
      addLayers(tl, rig, [{ el: next, depth: 1, S: { s: sp, c: [cx - sp * (geo.L[0] + geo.w / 2), cy - sp * (geo.L[1] + geo.h / 2)] } }]);
    }
    const fill = { pad: 0, fit: "contain", clamp: false };
    if ((o.dir || "in") === "in") {
      camStep(tl, rig, frameS(rig, screen, fill), t, dur, o.ease || "power2.inOut");
      if (next && o.reveal) tl.fromTo(next, { opacity: 0 }, { opacity: 1, duration: 0.1, ease: "none" }, t + dur * 0.45);
    } else {
      camStep(tl, rig, frameS(rig, screen, fill), rig.hist.length ? t : 0, 0);
      camStep(tl, rig, o.to ? frameS(rig, o.to, o) : { s: 1, c: [0, 0] }, t, dur, o.ease || "power3.out");
      if (next && o.reveal) tl.to(next, { opacity: 0, duration: 0.1, ease: "none" }, t + dur * 0.6);
    }
    return tl;
  };
  const PAR = new WeakMap();
  AR.parallax = function (tl, layers, t, dur, o = {}) {
    (layers || []).forEach((l) => els(l.sel || l.el || l).forEach((el) => {
      const frame = el.parentElement;
      let st = PAR.get(el);
      if (!st) { st = { geo: geoOf(el, frame), S: { s: 1, c: [0, 0] } }; PAR.set(el, st); }
      const k = l.depth ?? 1, rk = Math.pow(o.scale ?? 1, k);
      const org = o.origin ? pointIn(o.origin, frame) : [frame.clientWidth / 2, frame.clientHeight / 2];
      const v = [org[0] * (1 - rk) + (o.x ?? 0) * k, org[1] * (1 - rk) + (o.y ?? 0) * k];
      const S0 = st.S, S1 = { s: rk * S0.s, c: [rk * S0.c[0] + v[0], rk * S0.c[1] + v[1]] };
      st.S = S1;
      moveS(tl, el, st.geo, S0, S1, t, dur, o.ease || "power2.inOut");
    }));
    return tl;
  };

  // ================= character motion =================
  AR.toss = function (tl, sel, t, o = {}) {
    els(sel).forEach((el, i) => {
      const sp = space(el), cur = pos(el), A = o.anchor || [0.5, 0.5], s0 = cur.s, s1 = o.scale ?? s0;
      const r = rest(el, sp), O = originOf(el);
      const T = (P, s) => [P[0] - r.x - O[0] - s * (r.w * A[0] - O[0]), P[1] - r.y - O[1] - s * (r.h * A[1] - O[1])];
      const P0 = o.from != null ? pointIn(o.from, sp, o.fromAt)
        : [r.x + O[0] + cur.x + s0 * (r.w * A[0] - O[0]), r.y + O[1] + cur.y + s0 * (r.h * A[1] - O[1])];
      const P1 = pointIn(o.to, sp, o.toAt);
      const [x0, y0] = T(P0, s0), [x1, y1] = T(P1, s1);
      const dist = Math.hypot(P1[0] - P0[0], P1[1] - P0[1]);
      const h = o.h ?? Math.max(50, dist * 0.35), dur = o.dur ?? clamp(0.22 + dist / 2400, 0.24, 0.6);
      const ya = Math.min(y0, y1) - h, ra = Math.sqrt(y0 - ya), rf = Math.sqrt(y1 - ya), ta = (dur * ra) / (ra + rf);
      const t0 = t + i * (o.gap ?? 0);
      if (o.show) tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.001 }, t0);
      tl.fromTo(el, { x: x0 }, { x: x1, duration: dur, ease: "none", immediateRender: false }, t0);
      tl.fromTo(el, { y: y0 }, { y: ya, duration: ta, ease: "power1.out", immediateRender: false }, t0);
      tl.fromTo(el, { y: ya }, { y: y1, duration: dur - ta, ease: "power1.in", immediateRender: false }, t0 + ta);
      if (s1 !== s0) tl.fromTo(el, { scale: s0 }, { scale: s1, duration: dur, ease: "power1.inOut", immediateRender: false }, t0);
      if (o.spin) tl.fromTo(el, { rotation: cur.r }, { rotation: cur.r + o.spin, duration: dur, ease: "none", immediateRender: false }, t0);
      if (o.squash) {
        tl.set(el, { scaleX: s1 * 1.16, scaleY: s1 * 0.82 }, t0 + dur);
        tl.to(el, { scaleX: s1, scaleY: s1, duration: 0.18, ease: "back.out(3)" }, t0 + dur);
      }
      if (o.fade) tl.to(el, { opacity: 0, duration: 0.08, ease: "none" }, t0 + dur - 0.06);
      setPos(el, { x: x1, y: y1, s: s1, r: cur.r + (o.spin || 0) });
    });
    return tl;
  };
  AR.carry = function (tl, item, carrier, t, dur, o = {}) {
    const it = one(item), ca = one(carrier), sp = space(it), r = rest(it, sp), O = originOf(it), cur = pos(it);
    const A = o.anchor || [0.5, 1], C = o.at || [0.5, 0.2], pick = o.pick ?? 0.1;
    const samples = sampleTl(tl, t, t + dur, o.fps ?? 60, () => {
      const c = live(ca, sp);
      return [c.x + c.w * C[0] + (o.dx ?? 0), c.y + c.h * C[1] + (o.dy ?? 0)];
    });
    let prev = null;
    samples.forEach(([tt, P], i) => {
      const u = pick > 0 ? clamp((tt - t) / pick, 0, 1) : 1, w = u * u * (3 - 2 * u);
      const x = lerp(cur.x, P[0] - r.x - O[0] - cur.s * (r.w * A[0] - O[0]), w);
      const y = lerp(cur.y, P[1] - r.y - O[1] - cur.s * (r.h * A[1] - O[1]), w);
      if (prev) tl.fromTo(it, { x: prev.x, y: prev.y }, { x, y, duration: tt - prev.t, ease: "none", immediateRender: false }, prev.t);
      prev = { x, y, t: tt };
    });
    if (prev) setPos(it, { x: prev.x, y: prev.y });
    return tl;
  };
  function pathPts(path, sp, n) {
    if (Array.isArray(path)) return path.map((p) => [p[0], p[1]]);
    const pe = one(path);
    return atRest(new Set([...chainOf(pe), ...chainOf(sp)]), () => {
      const L = pe.getTotalLength(), m = pe.getScreenCTM(), R = sp.getBoundingClientRect(), k = kOf(sp, R), out = [];
      for (let i = 0; i <= n; i++) {
        const q = pe.getPointAtLength((L * i) / n);
        out.push([(m.a * q.x + m.c * q.y + m.e - R.left) / k, (m.b * q.x + m.d * q.y + m.f - R.top) / k]);
      }
      return out;
    });
  }
  AR.ride = function (tl, sel, path, t, dur, o = {}) {
    const el = one(sel), sp = space(el), r = rest(el, sp), O = originOf(el), cur = pos(el), A = o.anchor || [0.5, 1];
    const pts = pathPts(path, sp, o.samples ?? 200), cum = [0];
    for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    const at = (f) => {
      const want = f * cum[cum.length - 1];
      let i = 1;
      while (i < cum.length - 1 && cum[i] < want) i++;
      const u = (want - cum[i - 1]) / (cum[i] - cum[i - 1] || 1);
      return [lerp(pts[i - 1][0], pts[i][0], u), lerp(pts[i - 1][1], pts[i][1], u), Math.atan2(pts[i][1] - pts[i - 1][1], pts[i][0] - pts[i - 1][0])];
    };
    const E = EASE(o.ease, "power2.inOut"), n = Math.max(2, Math.round(dur * (o.fps ?? 60)));
    let prev = null, lastRot = null;
    for (let i = 0; i <= n; i++) {
      const P = at(clamp(E(i / n), 0, 1));
      const v = { x: P[0] + (o.dx ?? 0) - r.x - O[0] - cur.s * (r.w * A[0] - O[0]), y: P[1] + (o.dy ?? 0) - r.y - O[1] - cur.s * (r.h * A[1] - O[1]) };
      if (o.rotate) {
        let deg = (P[2] * 180) / Math.PI;
        if (lastRot != null) while (deg - lastRot > 180) deg -= 360;
        if (lastRot != null) while (deg - lastRot < -180) deg += 360;
        v.rotation = lastRot = deg;
      }
      if (prev) tl.fromTo(el, prev, { ...v, duration: dur / n, ease: "none", immediateRender: false }, t + ((i - 1) * dur) / n);
      prev = v;
    }
    setPos(el, { x: prev.x, y: prev.y });
    return tl;
  };
  AR.flyToSlot = function (tl, sel, slot, t, dur = 0.26, o = {}) {
    const items = els(sel), slots = els(slot);
    items.forEach((el, i) => {
      const s = slots[i % slots.length];
      if (!s) return;
      let scale = o.scale;
      if (o.fit) { const a = rest(el, space(el)), b = rest(s, space(el)); scale = Math.min((b.w * o.fit) / a.w, (b.h * o.fit) / a.h); }
      AR.toss(tl, el, t + i * (o.gap ?? 0.035), {
        to: s, toAt: o.at || [0.5, 0.5], anchor: o.anchor || [0.5, 0.5], h: o.arc ?? 70, dur, scale, squash: o.squash ?? true,
      });
    });
    return tl;
  };
  AR.shrinkInto = function (tl, hero, slot, t, dur = 0.12, o = {}) {
    const el = one(hero), s = one(slot), sp = space(el), a = rest(el, sp), b = rest(s, sp), cur = pos(el);
    const fit = o.fit ?? 0.86, sc = Math.min((b.w * fit) / a.w, (b.h * fit) / a.h), At = o.at || [0.5, 0.5];
    const p = placeAt(el, sp, [b.x + b.w * At[0], b.y + b.h * At[1]], o.anchor || [0.5, 0.5], sc);
    tl.fromTo(el, { x: cur.x, y: cur.y, scale: cur.s }, { x: p.x, y: p.y, scale: sc, duration: dur, ease: o.ease || "expo.out", immediateRender: false }, t);
    setPos(el, { x: p.x, y: p.y, s: sc });
    return tl;
  };

  // ================= selection and lists =================
  AR.spotlight = function (tl, items, chosen, t, o = {}) {
    const keep = els(chosen), c = keep[0], d = o.dur ?? 0.12;
    const others = els(items).filter((e) => !keep.some((k) => e === k || e.contains(k)));
    tl.to(others, { opacity: o.dim ?? 0.28, duration: d, ease: "power2.out" }, t);
    tl.to(keep, { opacity: 1, duration: d }, t);
    if (o.outline !== false) {
      const col = o.color ?? "#b8862e", w = o.width ?? 4, base = getComputedStyle(c).boxShadow;
      const tail = base && base !== "none" ? ", " + base : "";
      tl.fromTo(c, { boxShadow: `${col} 0px 0px 0px 0px${tail}` },
        { boxShadow: `${col} 0px 0px 0px ${w}px${tail}`, duration: 0.1, ease: "power2.out", immediateRender: false }, t);
    }
    if (o.lift) tl.to(c, { scale: o.lift, duration: 0.16, ease: "back.out(2)" }, t);
    return tl;
  };
  AR.promote = function (tl, chosen, t, o = {}) {
    const el = one(chosen), sp = space(el), F = rest(o.frame ? one(o.frame) : sceneRoot(el), sp), r = rest(el, sp), cur = pos(el);
    const S = o.scale ?? (F.h * (o.size ?? 0.62)) / r.h, at = o.at || [0.5, 0.56], lift = o.lift ?? r.h * 0.22;
    const p = placeAt(el, sp, [F.x + F.w * at[0], F.y + F.h * at[1]], [0.5, 0.5], S);
    const tile = o.tile ? one(o.tile) : el.parentElement;
    if (tile) tl.set(tile, { zIndex: 40 }, t);
    tl.fromTo(el, { y: cur.y }, { y: cur.y - lift, duration: 0.07, ease: "power2.out", immediateRender: false }, t);
    tl.fromTo(el, { x: cur.x, y: cur.y - lift, scale: cur.s }, { x: p.x, y: p.y, scale: S, duration: o.dur ?? 0.22, ease: o.ease || "power3.out", immediateRender: false }, t + 0.07);
    if (o.dimTile) tl.to(els(o.dimTile), { opacity: o.dim ?? 0.28, duration: 0.12 }, t + 0.07);
    setPos(el, { x: p.x, y: p.y, s: S });
    return tl;
  };
  AR.listPush = function (tl, list, items, t, o = {}) {
    const track = one(list), news = els(items), gap = o.gap ?? 0.17, d = o.dur ?? 0.1, E = o.ease || "power2.out";
    if (!track || !news.length) return tl;
    const top = (e) => rest(e, track).y, first = news[0], after = first.nextElementSibling;
    const tops = news.map(top), y0 = -(after ? top(after) : tops[0] + rest(first, track).h);
    const cls = (e) => (e.getAttribute("class") || "").split(/\s+/).filter((c) => c && c !== o.select).join(" ");
    news.forEach((e, i) => {
      const ti = t + i * gap;
      tl.fromTo(track, { y: i ? -tops[i - 1] : y0 }, { y: -tops[i], duration: d, ease: E, immediateRender: i === 0 }, ti);
      tl.fromTo(e, { opacity: 0, x: o.dx ?? 8 }, { opacity: 1, x: 0, duration: d * 1.5, ease: "power2.out" }, ti);
      if (o.select) {
        const below = i ? news[i - 1] : after;
        tl.set(e, { attr: { class: (cls(e) + " " + o.select).trim() } }, ti);
        if (below) tl.set(below, { attr: { class: cls(below) } }, ti);
      }
    });
    return tl;
  };

  // ================= card moves =================
  AR.fan = function (tl, cards, t, o = {}) {
    const list = els(cards), n = list.length, mid = (n - 1) / 2, ang = o.angle ?? 9, spread = o.spread ?? 220;
    const R = spread / Math.max(0.05, Math.sin((ang * Math.PI) / 180)), d = o.dur ?? 0.3;
    list.forEach((el, i) => {
      const u = mid ? (i - mid) / mid : 0, th = (ang * u * Math.PI) / 180, cur = pos(el);
      const x = R * Math.sin(th) + (o.x ?? 0), y = R * (1 - Math.cos(th)) + (o.y ?? 0), rot = ang * u, s = o.scale ?? cur.s;
      tl.fromTo(el, { x: cur.x, y: cur.y, rotation: cur.r, scale: cur.s },
        { x, y, rotation: rot, scale: s, duration: d, ease: o.ease || "power3.out", immediateRender: false }, t + Math.abs(i - mid) * (o.gap ?? 0.02));
      setPos(el, { x, y, r: rot, s });
    });
    return tl;
  };
  AR.radial = function (tl, tiles, t, o = {}) {
    const list = els(tiles);
    if (!list.length) return tl;
    const sp = list[0].parentElement, boxes = list.map((e) => rest(e, sp)), U = restUnion(list, sp);
    const C = o.from && o.from !== "center" ? pointIn(o.from, sp) : [U.x + U.w / 2, U.y + U.h / 2];
    const dist = boxes.map((b) => Math.hypot(b.x + b.w / 2 - C[0], b.y + b.h / 2 - C[1]));
    const dmax = Math.max(...dist) || 1, dur = o.dur ?? 0.18, pop = o.pop ?? 0.1, fly = o.fly ?? 0;
    const when = dist.map((d) => t + (d / dmax) * dur);
    list.forEach((e, i) => {
      const b = boxes[i];
      tl.fromTo(e, { opacity: 0, scale: o.fromScale ?? 0.3, x: (C[0] - b.x - b.w / 2) * fly, y: (C[1] - b.y - b.h / 2) * fly },
        { opacity: 1, scale: 1, x: 0, y: 0, duration: pop, ease: o.ease || "back.out(1.8)" }, when[i]);
    });
    if (o.counter) {
      const c = one(o.counter), order = list.map((e, i) => i).sort((a, b) => when[a] - when[b]);
      order.forEach((i, k) => tl.set(c, { textContent: fmtNum((o.start ?? 0) + k + 1, o) }, when[i]));
    }
    return tl;
  };
  const FLIP = new WeakMap();
  AR.flip3d = function (tl, sel, t, o = {}) {
    els(sel).forEach((el) => {
      const ax = (o.axis || "y").toLowerCase() === "x" ? "X" : "Y", prop = "rotation" + ax;
      if (!el.dataset.arFlip) { // faces: children with data-face="front" / "back"
        el.dataset.arFlip = ax;
        el.style.transformStyle = "preserve-3d";
        el.querySelectorAll(":scope > [data-face]").forEach((f) => {
          Object.assign(f.style, { position: "absolute", inset: "0", backfaceVisibility: "hidden", webkitBackfaceVisibility: "hidden" });
          if (f.dataset.face === "back") f.style.transform = `rotate${ax}(180deg)`;
        });
        G().set(el, { transformPerspective: o.perspective ?? 1600 });
      }
      const cur = FLIP.get(el) || 0, to = cur + (o.deg ?? 180), d = o.dur ?? 0.34;
      tl.fromTo(el, { [prop]: cur }, { [prop]: to, duration: d, ease: o.ease || "power2.inOut", immediateRender: false }, t);
      tl.to(el, { scale: o.dip ?? 0.9, duration: d / 2, ease: "power1.out" }, t);
      tl.to(el, { scale: 1, duration: d / 2, ease: "power1.in" }, t + d / 2);
      FLIP.set(el, to);
    });
    return tl;
  };
  AR.compare = function (tl, o, t, dur = 0.55, opt = {}) {
    const after = one(o.after), handle = one(o.handle), rider = one(o.rider), dir = opt.dir || "right", E = EASE(opt.ease, "power1.inOut");
    const p0 = opt.from ?? (dir === "right" ? 0 : 1), p1 = opt.to ?? (dir === "right" ? 1 : 0);
    // "right": after shows left of the handle and grows as it moves right; "left": after shows right of it
    after.style.clipPath = dir === "right" ? WIPE.right : WIPE.left;
    varTween(tl, after, "--ar-p", p0, p1, t, dur, E);
    const follow = (el, dx) => {
      if (!el) return;
      const sp = space(el), a = rest(after, sp), r = rest(el, sp), cur = pos(el);
      const X = (p) => a.x + p * a.w - (r.x + r.w / 2) + dx;
      G().set(el, { x: X(p0) });
      tl.fromTo(el, { x: X(p0) }, { x: X(p1), duration: dur, ease: E, immediateRender: false }, t);
      setPos(el, { x: X(p1), y: cur.y });
    };
    follow(handle, 0);
    if (rider) { const rw = rest(rider, space(rider)).w; follow(rider, opt.riderDx ?? (p1 < p0 ? 1 : -1) * (rw * 0.5 + 6)); }
    if (opt.counter) {
      const c = opt.counter, el = one(c.sel), ce = EASE(c.ease, "power2.out");
      textTrack(tl, el, t, dur, (p) => fmtNum(lerp(c.from ?? 0, c.to ?? 100, ce(p)), c));
    }
    return tl;
  };
  function eulerZYX(tilt, spin) { // CSS rotateX(tilt) rotateZ(spin) as GSAP's rotation, rotationY, rotationX
    const a = (tilt * Math.PI) / 180, b = (spin * Math.PI) / 180, sa = Math.sin(a), ca = Math.cos(a), sb = Math.sin(b), cb = Math.cos(b);
    const d = (v) => (v * 180) / Math.PI;
    return { rotation: d(Math.atan2(ca * sb, cb)), rotationY: d(Math.asin(clamp(-sa * sb, -1, 1))), rotationX: d(Math.atan2(sa * cb, ca)) };
  }
  AR.explode = function (tl, layers, t, o = {}) {
    const list = els(layers);
    if (!list.length) return tl;
    const stack = o.stack ? one(o.stack) : list[0].parentElement, d = o.dur ?? 0.24, gap = o.gap ?? 30;
    stack.style.transformStyle = "preserve-3d";
    G().set(stack, { transformPerspective: o.perspective ?? 2600 });
    const rot = eulerZYX(o.tilt ?? 54, o.angle ?? -32);
    tl.fromTo(stack, { rotation: 0, rotationY: 0, rotationX: 0, scale: 1 },
      { ...rot, scale: o.scale ?? 0.74, duration: d, ease: o.ease || "power3.out", immediateRender: false }, t);
    list.forEach((l, i) => {
      if (i === 0 && o.base !== false) return;
      const k = o.level === "one" ? 1 : o.base === false ? i + 1 : i; // each layer a level higher, or all on one level
      tl.fromTo(l, { z: 0 }, { z: k * gap, duration: d * 1.3, ease: "back.out(1.5)", immediateRender: false }, t + d * 0.3 + i * 0.03);
      if (o.shadow !== false) tl.fromTo(l, { boxShadow: "rgba(20,30,60,0) 0px 0px 0px 0px" }, { boxShadow: "rgba(20,30,60,0.28) 0px 18px 30px 0px", duration: d, immediateRender: false }, t + d * 0.3);
    });
    return tl;
  };
  AR.deck = function (tl, cards, t, o = {}) {
    const list = els(cards), gap = o.gap ?? 0.2, step = o.step ?? 7, r = rnd(o.seed ?? 5);
    list.forEach((c, i) => {
      const ti = t + i * gap, tilt = o.tilt ? (r() * 2 - 1) * o.tilt : 0;
      if (i > 0 || o.first) {
        tl.fromTo(c, { opacity: 0 }, { opacity: 1, duration: o.fade ?? 0.07, ease: "none" }, ti);
        tl.fromTo(c, { scale: o.from ?? 1.06, rotation: tilt }, { scale: 1, rotation: tilt, duration: 0.18, ease: "power2.out", immediateRender: false }, ti);
      } else if (tilt) G().set(c, { rotation: tilt });
      for (let j = 0; j < i; j++) tl.to(list[j], { x: (i - j) * step, y: (i - j) * step, duration: 0.1, ease: "power2.out" }, ti);
      if (o.check) {
        const ck = c.querySelector(o.check);
        if (ck) tl.fromTo(ck, { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.24, ease: "back.out(3)" }, ti + (o.checkAt ?? 0.08));
      }
      setPos(c, { r: tilt });
    });
    const n = list.length;
    list.forEach((c, i) => setPos(c, { x: (n - 1 - i) * step, y: (n - 1 - i) * step }));
    return tl;
  };

  // ================= pages and scenes =================
  const SCROLL = new WeakMap();
  AR.scrollTo = function (tl, scroller, y, t, dur = 0.35, o = {}) {
    const el = one(scroller), cur = SCROLL.get(el) ?? 0;
    let to = typeof y === "number" ? y : rest(one(y), el).y - (o.offset ?? 0);
    if (o.clamp !== false) to = clamp(to, 0, Math.max(0, rest(el, el.parentElement).h - el.parentElement.clientHeight));
    const steps = o.steps ?? 0;
    if (!steps) tl.fromTo(el, { y: -cur }, { y: -to, duration: dur, ease: o.ease || "power2.inOut", immediateRender: false }, t);
    else for (let i = 0; i < steps; i++) {
      tl.fromTo(el, { y: -lerp(cur, to, i / steps) }, { y: -lerp(cur, to, (i + 1) / steps), duration: Math.min(0.14, dur / steps), ease: "power3.out", immediateRender: false }, t + (dur * i) / steps);
    }
    SCROLL.set(el, to);
    return tl;
  };
  const shuffled = (n, seed) => {
    const r = rnd(seed), a = [...Array(n).keys()];
    for (let i = n - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
    return a;
  };
  const POWER = new WeakMap(); // screens these helpers switched off
  AR.screensOff = function (tl, sel, t, o = {}) {
    const list = els(sel), order = shuffled(list.length, o.seed ?? 11), span = o.span ?? 0.17;
    order.forEach((idx, k) => {
      const el = list[idx], ti = t + (list.length > 1 ? (span * k) / (list.length - 1) : 0);
      if (o.crt) { tl.to(el, { scaleY: 0.04, duration: 0.05, ease: "power2.in" }, ti); tl.set(el, { opacity: 0 }, ti + 0.05); }
      else tl.set(el, { opacity: 0 }, ti);
      POWER.set(el, "off");
    });
    return tl;
  };
  AR.screensOn = function (tl, sel, t, o = {}) {
    const list = els(sel), order = shuffled(list.length, o.seed ?? 12), span = o.span ?? 0.17;
    order.forEach((idx, k) => {
      const el = list[idx], ti = t + (list.length > 1 ? (span * k) / (list.length - 1) : 0);
      // switched off earlier by screensOff: just switch on; otherwise it is dark from the first frame until ti
      if (POWER.get(el) === "off") tl.set(el, { opacity: 1, scaleY: 1 }, ti);
      else tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.001 }, ti);
      if (o.flicker !== false) { tl.set(el, { opacity: 0.35 }, ti + 0.034); tl.set(el, { opacity: 1 }, ti + 0.067); }
      POWER.set(el, "on");
    });
    return tl;
  };
  const DIM = new WeakMap();
  AR.dim = function (tl, sel, t, o = {}) {
    els(sel).forEach((el) => {
      const cur = DIM.get(el) ?? 1, to = o.to ?? 0.45;
      tl.fromTo(el, { filter: `brightness(${cur})` }, { filter: `brightness(${to})`, duration: o.dur ?? 0.15, ease: "power2.out", immediateRender: false }, t);
      DIM.set(el, to);
    });
    return tl;
  };

  // ================= reactions =================
  // pixel glyphs (# = colour) on a 10-wide grid; bubbles are 12x13 art pixels with the tail at the bottom left
  const EMO = {
    "!": { c: "#e5483b", m: ["....##....", "....##....", "....##....", "....##....", "..........", "....##...."] },
    "?": { c: "#e5483b", m: ["...####...", "..##..##..", "......##..", "....###...", "....##....", "..........", "....##...."] },
    "…": { c: "#1f1e1c", m: ["..........", "..........", "##..##..##", "##..##..##"], dots: true },
    heart: { c: "#e5483b", m: ["..##..##..", ".########.", ".########.", "..######..", "...####...", "....##...."] },
    anger: { c: "#e5483b", o: "#161512", bare: true, m: [".##..##.", "##....##", "#......#", "........", "#......#", "##....##", ".##..##."] },
    sweat: { c: "#8fd3ff", o: "#2f6fb5", bare: true, m: ["..#..", ".###.", "#####", "#####", ".###."] },
  };
  function emoteSvg(kind) {
    const E = EMO[kind] || EMO[kind === "..." ? "…" : "!"];
    const W = E.bare ? E.m[0].length + 2 : 12, H = E.bare ? E.m.length + 2 : 13;
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, "shape-rendering": "crispEdges" });
    const px = (x, y, c, parent) => (parent || svg).appendChild(svgEl("rect", { x, y, width: 1, height: 1, fill: c }));
    if (!E.bare) {
      const K = "#161512", Wt = "#ffffff";
      for (let x = 2; x <= 9; x++) { px(x, 0, K); if (x < 3 || x > 4) px(x, 10, K); }
      for (let y = 2; y <= 8; y++) { px(0, y, K); px(11, y, K); }
      [[1, 1], [10, 1], [1, 9], [10, 9]].forEach(([x, y]) => px(x, y, K));
      svg.appendChild(svgEl("rect", { x: 2, y: 1, width: 8, height: 9, fill: Wt }));
      svg.appendChild(svgEl("rect", { x: 1, y: 2, width: 10, height: 7, fill: Wt }));
      px(3, 10, Wt); px(4, 10, Wt); px(2, 10, K); px(2, 11, K); px(3, 11, K); px(2, 12, K);
    }
    const ox = E.bare ? 1 : 1, oy = E.bare ? 1 : Math.round((10 - E.m.length) / 2) + 0;
    const groups = [];
    E.m.forEach((row, y) => [...row].forEach((ch, x) => {
      if (ch !== "#") return;
      let parent = svg;
      if (E.dots) {
        const gi = Math.floor(x / 4);
        groups[gi] = groups[gi] || svg.appendChild(svgEl("g"));
        parent = groups[gi];
      }
      if (E.o) [[-1, 0], [1, 0], [0, -1], [0, 1]].forEach(([dx, dy]) => {
        const nx = x + dx, ny = y + dy;
        if (!(E.m[ny] && E.m[ny][nx] === "#")) px(ox + nx, oy + ny, E.o, parent);
      });
      px(ox + x, oy + y, E.c, parent);
    }));
    if (kind === "sweat") px(ox + 1, oy + 2, "#ffffff");
    return { svg, W, H, groups, bare: !!E.bare };
  }
  AR.emote = function (tl, sprite, kind, t, o = {}) {
    els(sprite).forEach((sp) => {
      const { svg, W, H, groups, bare } = emoteSvg(kind);
      const w = sp.offsetWidth, h = sp.offsetHeight, u = Math.max(2, Math.round((o.size ?? w * 0.27) / 12));
      const box = document.createElement("div");
      const at = o.at || (kind === "sweat" ? [0.16, 0.22] : kind === "anger" ? [0.74, 0.06] : [0.66, 0.2]);
      Object.assign(box.style, {
        position: "absolute", width: W * u + "px", height: H * u + "px", pointerEvents: "none", zIndex: 5,
        left: at[0] * w + "px", top: at[1] * h - (bare ? 0 : H * u) + "px", transformOrigin: bare ? "50% 50%" : "15% 100%",
      });
      box.setAttribute("data-layout-ignore", "");
      svg.setAttribute("width", W * u);
      svg.setAttribute("height", H * u);
      box.appendChild(svg);
      sp.appendChild(box);
      const d = o.dur ?? 0.8;
      tl.fromTo(box, { scale: 0, opacity: 1 }, { scale: 1, duration: 0.14, ease: "back.out(3)" }, t);
      if (groups.length) groups.forEach((g, i) => tl.fromTo(g, { opacity: 0 }, { opacity: 1, duration: 0.01 }, t + 0.06 + i * 0.12));
      if (kind === "?") { tl.to(box, { rotation: -10, duration: 0.08 }, t + 0.14); tl.to(box, { rotation: 0, duration: 0.2, ease: "back.out(3)" }, t + 0.22); }
      if (kind === "heart") tl.to(box, { y: -3 * u, duration: d, ease: "power1.out" }, t + 0.1);
      if (kind === "anger") [0.18, 0.42].forEach((dt) => { tl.to(box, { scale: 1.25, duration: 0.06 }, t + dt); tl.to(box, { scale: 1, duration: 0.1 }, t + dt + 0.06); });
      if (kind === "sweat") tl.to(box, { y: 4 * u, duration: d, ease: "power1.in" }, t + 0.1);
      if (o.hold !== true) tl.to(box, { scale: 0, opacity: 0, duration: 0.1, ease: "power2.in" }, t + d);
    });
    return tl;
  };
  AR.blink = function (tl, eyes, t, o = {}) {
    const d = o.dur ?? 0.1;
    els(eyes).forEach((e) => {
      if (e.querySelector(':scope .pose[data-pose="blink"]')) { AR.pose(tl, e, "blink", t); AR.pose(tl, e, o.back ?? "idle", t + d); }
      else { tl.set(e, { scaleY: 0.12 }, t); tl.set(e, { scaleY: 1 }, t + d); }
    });
    return tl;
  };

  // ================= wipes, masks, light =================
  AR.wipeRide = function (tl, o, t, dur = 0.45, opt = {}) {
    const after = one(o.after), bar = one(o.bar), rider = one(o.rider), box = space(after), A = rest(after, box);
    const dir = opt.dir || "down", vert = dir === "down" || dir === "up", E = EASE(opt.ease, "power1.inOut");
    const edge = (p) => (dir === "down" || dir === "right" ? p : 1 - p);
    after.style.clipPath = WIPE[dir];
    varTween(tl, after, "--ar-p", edge(0), edge(1), t, dur, E);
    const move = (el, fn) => {
      const cur = pos(el), prop = vert ? "y" : "x", base = vert ? cur.y : cur.x;
      G().set(el, { [prop]: base + fn(0) });
      tl.fromTo(el, { [prop]: base + fn(0) }, { [prop]: base + fn(1), duration: dur, ease: E, immediateRender: false }, t);
      setPos(el, { [prop]: base + fn(1) });
    };
    let bt = 0;
    if (bar) {
      const sp = space(bar), a = rest(after, sp), b = rest(bar, sp);
      bt = vert ? b.h : b.w;
      move(bar, (p) => vert ? a.y + edge(p) * a.h - (b.y + b.h / 2) : a.x + edge(p) * a.w - (b.x + b.w / 2));
    }
    if (rider) {
      const sp = space(rider), a = rest(after, sp), r = rest(rider, sp);
      move(rider, (p) => vert ? a.y + edge(p) * a.h - bt / 2 - (r.y + r.h) + (opt.riderDy ?? 0)
        : a.x + edge(p) * a.w + (dir === "right" ? -bt / 2 - (r.x + r.w) : bt / 2 - r.x) + (opt.riderDx ?? 0));
    }
    return tl;
  };
  AR.povMask = function (tl, sel, t, o = {}) {
    const host = one(sel), W = host.clientWidth, H = host.clientHeight, kind = o.kind || "binoculars", id = "ar-pov-" + ++UID;
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, "data-layout-ignore": "" });
    Object.assign(svg.style, { position: "absolute", left: "0", top: "0", pointerEvents: "none", zIndex: o.z ?? 20 });
    const mask = svgEl("mask", { id, maskUnits: "userSpaceOnUse", x: 0, y: 0, width: W, height: H });
    mask.appendChild(svgEl("rect", { x: 0, y: 0, width: W, height: H, fill: "#fff" }));
    const holes = svgEl("g", { fill: "#000" });
    const cx = W / 2, cy = H / 2, deco = svgEl("g", { fill: "none", stroke: o.ring ?? "#000", "stroke-width": Math.max(2, W * 0.004) });
    if (kind === "keyhole") {
      const r = H * 0.2;
      holes.appendChild(svgEl("circle", { cx, cy: cy - H * 0.12, r }));
      holes.appendChild(svgEl("path", { d: `M ${cx - r * 0.45} ${cy - H * 0.06} L ${cx + r * 0.45} ${cy - H * 0.06} L ${cx + r * 0.95} ${cy + H * 0.36} L ${cx - r * 0.95} ${cy + H * 0.36} Z` }));
    } else if (kind === "scope") {
      const r = Math.min(W, H) * 0.46;
      holes.appendChild(svgEl("circle", { cx, cy, r }));
      deco.appendChild(svgEl("circle", { cx, cy, r: r * 0.985 }));
      deco.appendChild(svgEl("path", { d: `M ${cx - r} ${cy} H ${cx - r * 0.12} M ${cx + r * 0.12} ${cy} H ${cx + r} M ${cx} ${cy - r} V ${cy - r * 0.12} M ${cx} ${cy + r * 0.12} V ${cy + r}` }));
    } else {
      const r = o.r ?? Math.max(W * 0.29, H * 0.52);
      holes.appendChild(svgEl("circle", { cx: cx - W * 0.205, cy, r }));
      holes.appendChild(svgEl("circle", { cx: cx + W * 0.205, cy, r }));
    }
    mask.appendChild(holes);
    const defs = svgEl("defs");
    defs.appendChild(mask);
    svg.appendChild(defs);
    svg.appendChild(svgEl("rect", { x: 0, y: 0, width: W, height: H, fill: o.color ?? "#000", mask: `url(#${id})` }));
    if (kind === "scope") svg.appendChild(deco);
    host.appendChild(svg);
    if (t > 0) tl.fromTo(svg, { opacity: 0 }, { opacity: 1, duration: 0.001 }, t);
    if (o.dur) tl.fromTo(holes, { scale: 0.05, svgOrigin: `${cx} ${cy}` }, { scale: 1, svgOrigin: `${cx} ${cy}`, duration: o.dur, ease: "power3.out" }, t);
    return tl;
  };
  function pushPair(tl, out, inn, t, o, d0, e0, gap0) {
    const a = one(out), b = one(inn), dir = o.dir || "left", vert = dir === "up" || dir === "down", prop = vert ? "y" : "x";
    const R = rest(a, space(a)), D = o.dist ?? (vert ? R.h : R.w) + (o.gap ?? gap0), sgn = dir === "left" || dir === "up" ? -1 : 1;
    const d = o.dur ?? d0, E = o.ease || e0, ca = pos(a)[prop];
    if (a) tl.fromTo(a, { [prop]: ca }, { [prop]: ca + sgn * D, duration: d, ease: E, immediateRender: false }, t);
    if (b) tl.fromTo(b, { [prop]: -sgn * D }, { [prop]: 0, duration: d, ease: E }, t);
    if (a) setPos(a, { [prop]: ca + sgn * D });
    if (b) setPos(b, { [prop]: 0 });
    return tl;
  }
  AR.swipe = (tl, out, inn, t, o = {}) => pushPair(tl, out, inn, t, o, 0.12, "power3.out", 24);
  AR.pushSwap = (tl, out, inn, t, o = {}) => pushPair(tl, out, inn, t, o, 0.17, "power3.inOut", 0);
  AR.beam = function (tl, o, t, opt = {}) {
    const tgt = one(o.target), layer = opt.layer ? one(opt.layer) : space(tgt), id = "ar-beam-" + ++UID;
    const S = pointIn(o.from, layer, opt.fromAt), TB = rest(tgt, layer), at = opt.at || [0.5, 0.5];
    const C = [TB.x + TB.w * at[0], TB.y + TB.h * at[1]], r = opt.r ?? Math.min(TB.w, TB.h) * 0.42;
    const D = Math.hypot(C[0] - S[0], C[1] - S[1]), a = Math.atan2(C[1] - S[1], C[0] - S[0]);
    const hA = Math.asin(Math.min(0.99, r / D)), L = Math.sqrt(Math.max(1, D * D - r * r));
    const p1 = [S[0] + L * Math.cos(a - hA), S[1] + L * Math.sin(a - hA)], p2 = [S[0] + L * Math.cos(a + hA), S[1] + L * Math.sin(a + hA)];
    const W = layer.clientWidth, H = layer.clientHeight, col = opt.color ?? "255,240,170";
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, "data-layout-ignore": "" });
    Object.assign(svg.style, { position: "absolute", left: "0", top: "0", pointerEvents: "none", overflow: "visible", mixBlendMode: opt.blend ?? "screen", zIndex: opt.z ?? 6 });
    const grad = svgEl("linearGradient", { id, gradientUnits: "userSpaceOnUse", x1: S[0], y1: S[1], x2: C[0], y2: C[1] });
    grad.appendChild(svgEl("stop", { offset: "0", "stop-color": `rgb(${col})`, "stop-opacity": "0.75" }));
    grad.appendChild(svgEl("stop", { offset: "1", "stop-color": `rgb(${col})`, "stop-opacity": "0.3" }));
    const defs = svgEl("defs");
    defs.appendChild(grad);
    svg.appendChild(defs);
    svg.appendChild(svgEl("polygon", { points: `${S[0]},${S[1]} ${p1[0]},${p1[1]} ${p2[0]},${p2[1]}`, fill: `url(#${id})` }));
    svg.appendChild(svgEl("circle", { cx: C[0], cy: C[1], r, fill: `rgba(${col},0.42)` }));
    layer.appendChild(svg);
    tl.fromTo(svg, { opacity: 0 }, { opacity: 1, duration: 0.001 }, t);
    if (opt.flicker !== false) { tl.set(svg, { opacity: 0.3 }, t + 0.067); tl.set(svg, { opacity: 1 }, t + 0.1); }
    if (opt.off != null) tl.set(svg, { opacity: 0 }, opt.off);
    if (opt.xray) { // a second layer seen through the spot (the cargo behind a door)
      const xr = one(opt.xray), xb = rest(xr, layer), cx = C[0] - xb.x, cy = C[1] - xb.y;
      xr.style.clipPath = `circle(calc(var(--ar-r) * 1px) at ${cx.toFixed(2)}px ${cy.toFixed(2)}px)`;
      varTween(tl, xr, "--ar-r", 0, r, t + (opt.xrayAt ?? 0.3), 0.14, "power2.out");
    }
    return tl;
  };
  AR.lens = function (tl, o, t, opt = {}) {
    const lensEl = one(o.lens), hid = one(o.hidden), until = opt.until ?? t + 1;
    const off = "circle(0px at -9999px -9999px)";
    hid.style.clipPath = off;
    const samples = sampleTl(tl, t, until, opt.fps ?? 60, () => {
      const L = live(lensEl, hid);
      return [L.x + L.w / 2, L.y + L.h / 2, opt.r ?? (Math.min(L.w, L.h) / 2) * (opt.scale ?? 0.92)];
    });
    samples.forEach(([tt, [x, y, r]]) => tl.set(hid, { clipPath: `circle(${r.toFixed(2)}px at ${x.toFixed(2)}px ${y.toFixed(2)}px)` }, tt));
    if (opt.close !== false) tl.set(hid, { clipPath: off }, until + 1e-3);
    return tl;
  };

  // ================= particles =================
  AR.emit = function (tl, sel, t, dur, o = {}) {
    const tpl = one(sel), parent = tpl.parentElement, R = rest(tpl, parent), cx0 = R.x + R.w / 2, cy0 = R.y + R.h / 2;
    tpl.style.opacity = "0";
    const r = rnd(o.seed ?? 21), rate = o.rate ?? 30, n = Math.max(1, Math.round(rate * dur));
    const F = o.from != null ? pointIn(o.from, parent, o.fromAt) : [cx0, cy0];
    const to = o.to != null ? pointIn(o.to, parent, o.toAt) : null, cols = (o.stack && o.stack.cols) || 1;
    for (let i = 0; i < n; i++) {
      const el = tpl.cloneNode(true);
      el.removeAttribute("id");
      el.querySelectorAll("[id]").forEach((x) => x.removeAttribute("id"));
      el.setAttribute("data-layout-ignore", "");
      parent.appendChild(el);
      const tb = t + Math.max(0, (i + (r() - 0.5) * (o.jitter ?? 0.6)) / rate), life = (o.life ?? 0.6) * (0.85 + 0.3 * r());
      const sc = Array.isArray(o.scale) ? lerp(o.scale[0], o.scale[1], r()) : o.scale ?? 1;
      const x0 = F[0] - cx0 + (o.spreadX ?? 0) * (r() * 2 - 1), y0 = F[1] - cy0, spin = (o.spin ?? 0) * (r() * 2 - 1);
      tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.001 }, tb);
      tl.set(el, { scale: sc }, tb);
      let x1, y1, ya, ta;
      if (to) {
        let P = [to[0] + (o.scatter ?? 8) * (r() * 2 - 1), to[1]];
        if (o.stack) {
          const col = i % cols, row = Math.floor(i / cols);
          P = [to[0] + (col - (cols - 1) / 2) * (o.stack.dx ?? R.w * 1.05), to[1] - row * (o.stack.step ?? R.h * 0.28)];
        }
        x1 = P[0] - cx0; y1 = P[1] - cy0;
        ya = Math.min(y0, y1) - (o.h ?? 60);
        const a = Math.sqrt(y0 - ya), b = Math.sqrt(y1 - ya);
        ta = (life * a) / (a + b);
      } else {
        const ang = (((o.angle ?? -90) + (o.spread ?? 30) * (r() * 2 - 1)) * Math.PI) / 180, v = (o.speed ?? 500) * (0.75 + 0.5 * r());
        const vx = Math.cos(ang) * v, vy = Math.sin(ang) * v, g = o.gravity ?? 1400;
        x1 = x0 + vx * life;
        y1 = y0 + vy * life + 0.5 * g * life * life;
        const tap = g ? -vy / g : -1;
        if (tap > 0 && tap < life) { ta = tap; ya = y0 + vy * tap + 0.5 * g * tap * tap; }
        else {
          const A = vy * life, B = 0.5 * g * life * life, den = A + B;
          tl.fromTo(el, { y: y0 }, { y: y1, duration: life, ease: Math.abs(den) < 1e-6 ? "none" : (p) => (A * p + B * p * p) / den, immediateRender: false }, tb);
          ta = null;
        }
      }
      tl.fromTo(el, { x: x0 }, { x: x1, duration: life, ease: "none", immediateRender: false }, tb);
      if (ta != null) {
        tl.fromTo(el, { y: y0 }, { y: ya, duration: ta, ease: "power1.out", immediateRender: false }, tb);
        tl.fromTo(el, { y: ya }, { y: y1, duration: life - ta, ease: "power1.in", immediateRender: false }, tb + ta);
      }
      if (spin) tl.fromTo(el, { rotation: 0 }, { rotation: spin, duration: life, ease: "none", immediateRender: false }, tb);
      if (!(to && o.stack) && o.fade !== false) tl.to(el, { opacity: 0, duration: life * 0.35, ease: "power1.in" }, tb + life * 0.65);
    }
    return tl;
  };

  // ================= small gags =================
  AR.dealRows = function (tl, rows, t, o = {}) {
    els(rows).forEach((row, i) => {
      const ti = t + i * (o.gap ?? 0.1), d = o.dur ?? 0.14, op = o.ghost ?? 0.45, rot = (o.rot ?? -2.5) * (o.alternate && i % 2 ? -1 : 1);
      tl.fromTo(row, { opacity: 0 }, { opacity: 1, duration: d, ease: (p) => (p <= 0 ? 0 : op + (1 - op) * (1 - (1 - p) * (1 - p))) }, ti);
      tl.fromTo(row, { rotation: rot, x: o.dx ?? -18, y: o.dy ?? -10 }, { rotation: 0, x: 0, y: 0, duration: d, ease: "power2.out", immediateRender: false }, ti);
    });
    return tl;
  };
  AR.swing = function (tl, sel, t, o = {}) {
    els(sel).forEach((el) => {
      if (o.origin) el.style.transformOrigin = o.origin;
      const deg = o.deg ?? 22, d = o.dur ?? 1.1, w = (o.swings ?? 5) * Math.PI, k = o.damp ?? 3.2, base = pos(el).r;
      let peak = 0;
      for (let i = 1; i <= 200; i++) peak = Math.max(peak, Math.exp((-k * i) / 200) * Math.sin((w * i) / 200));
      tl.fromTo(el, { rotation: base }, { rotation: base + deg, duration: d, ease: (p) => (Math.exp(-k * p) * Math.sin(w * p)) / peak, immediateRender: false }, t);
    });
    return tl;
  };
  AR.grow = function (tl, sel, t, dur = 0.4, o = {}) {
    els(sel).forEach((el) => {
      el.style.transformOrigin = o.origin || "50% 100%";
      const f = o.from ?? 0;
      tl.fromTo(el, { scaleY: f, scaleX: o.fromX ?? Math.max(f, 0.35) }, { scaleY: 1, scaleX: 1, duration: dur, ease: o.steps ? `steps(${o.steps})` : o.ease || "back.out(1.5)" }, t);
    });
    if (o.cam) AR.frame(tl, o.cam, o.to ?? null, t + dur * (o.pullAt ?? 0.3), o.pullDur ?? 0.22, { ease: "power3.out", ...(o.frame || {}) });
    return tl;
  };
  const exitOffset = (el, dir, margin) => {
    const sp = space(el), F = rest(sceneRoot(el), sp), r = rest(el, sp), c = pos(el);
    const top = r.y + c.y, left = r.x + c.x;
    return dir === "up" ? [0, F.y - r.h - margin - top] : dir === "down" ? [0, F.y + F.h + margin - top]
      : dir === "left" ? [F.x - r.w - margin - left, 0] : [F.x + F.w + margin - left, 0];
  };
  AR.flyOut = function (tl, sel, tCut, o = {}) {
    els(sel).forEach((el) => {
      const c = pos(el), [dx, dy] = exitOffset(el, o.dir || "up", o.margin ?? 30), D = Math.hypot(dx, dy);
      const d = o.dur ?? (o.speed ? (2 * D) / o.speed : 0.1);
      tl.fromTo(el, { x: c.x, y: c.y, rotation: c.r }, { x: c.x + dx, y: c.y + dy, rotation: c.r + (o.spin ?? 0), duration: d, ease: "power2.in", immediateRender: false }, tCut - d);
      setPos(el, { x: c.x + dx, y: c.y + dy });
    });
    return tl;
  };
  AR.flyIn = function (tl, sel, t, o = {}) {
    els(sel).forEach((el) => {
      const c = pos(el), [dx, dy] = exitOffset(el, o.dir || "up", o.margin ?? 30), D = Math.hypot(dx, dy);
      const d = o.dur ?? (o.speed ? (2 * D) / o.speed : 0.12);
      tl.fromTo(el, { x: c.x + dx, y: c.y + dy, rotation: c.r + (o.spin ?? 0) }, { x: c.x, y: c.y, rotation: c.r, duration: d, ease: o.bounce ? "back.out(2.2)" : "power2.out" }, t);
    });
    return tl;
  };
  AR.tether = function (tl, a, b, t, dur, o = {}) {
    const A = one(a), B = one(b), layer = o.layer ? one(o.layer) : space(A);
    const W = layer.clientWidth, H = layer.clientHeight, wd = o.width ?? 6;
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, "data-layout-ignore": "" });
    Object.assign(svg.style, { position: "absolute", left: "0", top: "0", overflow: "visible", pointerEvents: "none", zIndex: o.z ?? "auto", opacity: "0" });
    const rope = svgEl("path", { fill: "none", stroke: o.color ?? "#8b5a2b", "stroke-width": wd, "stroke-linecap": "round" });
    const twist = svgEl("path", { fill: "none", stroke: o.light ?? "#c9935a", "stroke-width": wd * 0.45, "stroke-linecap": "round", "stroke-dasharray": `${wd * 0.5} ${wd * 1.1}` });
    svg.appendChild(rope);
    svg.appendChild(twist);
    // behind both anchors by default (just before whichever comes first in the layer)
    const kids = [A, B].map((e) => { let n = e; while (n && n.parentElement !== layer) n = n.parentElement; return n; }).filter(Boolean)
      .sort((x, y) => (x.compareDocumentPosition(y) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
    if (o.before) one(o.before).before(svg); else layer.insertBefore(svg, kids[0] || null);
    const t0 = o.start ?? t, t1 = o.until ?? t + dur + 0.8, at = o.at || [[0.5, 0.5], [0.5, 0.5]], sag = o.sag ?? 40;
    const sagAt = (tt) => {
      if (tt < t) return o.slack ?? sag;
      if (tt <= t + dur) return 0;
      const u = tt - t - dur;
      return sag * (1 - Math.exp(-7 * u) * Math.cos(11 * u));
    };
    const samples = sampleTl(tl, t0, t1, o.fps ?? 60, (tt) => {
      const pa = live(A, layer), pb = live(B, layer);
      return [pa.x + pa.w * at[0][0], pa.y + pa.h * at[0][1], pb.x + pb.w * at[1][0], pb.y + pb.h * at[1][1], sagAt(tt)];
    });
    tl.set(svg, { opacity: 1 }, t0);
    if (o.off != null) tl.set(svg, { opacity: 0 }, o.off);
    samples.forEach(([tt, [x1, y1, x2, y2, s]]) => {
      const d = `M ${x1.toFixed(1)} ${y1.toFixed(1)} Q ${((x1 + x2) / 2).toFixed(1)} ${((y1 + y2) / 2 + 2 * s).toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`;
      tl.set([rope, twist], { attr: { d } }, tt);
    });
    return tl;
  };
  AR.rip = function (tl, sel, t, o = {}) {
    const el = one(sel), r = rnd(o.seed ?? 4), n = o.teeth ?? 9, cur = pos(el);
    const tear = [];
    for (let k = 0; k <= n; k++) tear.push([50 + (k % 2 ? 1 : -1) * (3 + r() * 4), (100 * k) / n]);
    const pct = ([x, y]) => `${x.toFixed(2)}% ${y.toFixed(2)}%`;
    const left = `polygon(0% 0%, ${tear.map(pct).join(", ")}, 0% 100%)`;
    const right = `polygon(${tear.map(pct).join(", ")}, 100% 100%, 100% 0%)`;
    // the right half is a copy with every computed style inlined (its ids go, so id-based CSS would not reach it)
    const twin = el.cloneNode(true), src = [el, ...el.querySelectorAll("*")], dst = [twin, ...twin.querySelectorAll("*")];
    src.forEach((n, i) => {
      const cs = getComputedStyle(n), d = dst[i];
      for (let k = 0; k < cs.length; k++) if (cs[k] !== "visibility") d.style.setProperty(cs[k], cs.getPropertyValue(cs[k]));
      d.removeAttribute("id");
      d.style.transition = "none";
      d.style.animation = "none";
    });
    Object.assign(twin.style, { position: "absolute", left: el.offsetLeft + "px", top: el.offsetTop + "px", right: "auto", bottom: "auto", margin: "0",
      transform: "none", translate: "none", rotate: "none", scale: "none", clipPath: right, opacity: "0" });
    twin.setAttribute("data-layout-ignore", "");
    el.after(twin);
    tl.set(el, { clipPath: left }, t);
    tl.set(twin, { opacity: 1, x: cur.x, y: cur.y, rotation: cur.r, scale: cur.s }, t);
    const fall = o.fall ?? el.offsetHeight * 1.6, d = o.dur ?? 0.6, rot = o.rot ?? 20;
    [[el, -1], [twin, 1]].forEach(([e, s]) => {
      tl.to(e, { x: cur.x + s * 14, rotation: cur.r + s * 6, duration: 0.08, ease: "power2.out" }, t);
      tl.to(e, { x: cur.x + s * (o.spread ?? 60), y: cur.y + fall, rotation: cur.r + s * rot, duration: d, ease: "power2.in" }, t + 0.08);
      if (o.fade !== false) tl.to(e, { opacity: 0, duration: 0.12, ease: "none" }, t + 0.08 + d - 0.12);
    });
    return tl;
  };
  AR.ticks = function (tl, at, t, o = {}) {
    const layer = o.layer ? one(o.layer) : Array.isArray(at) ? document.body : space(one(at)), P = pointIn(at, layer, o.at);
    const len = o.len ?? 26, svg = svgEl("svg", { width: len * 4, height: len * 4, viewBox: `${-len * 2} ${-len * 2} ${len * 4} ${len * 4}`, "data-layout-ignore": "" });
    Object.assign(svg.style, { position: "absolute", left: P[0] - len * 2 + "px", top: P[1] - len * 2 + "px", pointerEvents: "none", overflow: "visible", zIndex: 8 });
    (o.angles || [-150, -110, -70]).forEach((deg) => {
      const a = (deg * Math.PI) / 180, x1 = Math.cos(a) * len * 0.55, y1 = Math.sin(a) * len * 0.55, x2 = Math.cos(a) * len * 1.25, y2 = Math.sin(a) * len * 1.25;
      svg.appendChild(svgEl("line", { x1, y1, x2, y2, stroke: o.outline ?? "#161512", "stroke-width": 9, "stroke-linecap": "square" }));
      svg.appendChild(svgEl("line", { x1, y1, x2, y2, stroke: o.color ?? "#ffffff", "stroke-width": 5, "stroke-linecap": "square" }));
    });
    layer.appendChild(svg);
    tl.fromTo(svg, { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.05, ease: "power2.out" }, t);
    tl.to(svg, { opacity: 0, duration: 0.06 }, t + (o.hold ?? 0.12));
    return tl;
  };
  AR.recoil = function (tl, sel, t, o = {}) {
    els(sel).forEach((el) => {
      const c = pos(el);
      tl.to(el, { x: c.x + (o.dx ?? 16), rotation: c.r + (o.rot ?? 14), duration: 0.06, ease: "power3.out" }, t);
      tl.to(el, { x: c.x, rotation: c.r, duration: o.dur ?? 0.42, ease: o.ease || "elastic.out(1.1, 0.42)" }, t + 0.06);
    });
    if (o.ticks) AR.ticks(tl, o.ticks, t, { layer: o.layer || space(one(sel)), at: o.tickAt });
    return tl;
  };
  AR.discard = function (tl, cards, t, o = {}) {
    const list = els(cards), r = rnd(o.seed ?? 9), gap = o.gap ?? 0.1, d = o.dur ?? 0.3;
    const keep = o.keep == null ? list[list.length - 1] : typeof o.keep === "number" ? list[o.keep] : one(o.keep);
    let k = 0;
    list.forEach((c) => {
      if (c === keep) return;
      const ti = t + k * gap, side = o.dir === "left" ? -1 : o.dir === "right" ? 1 : k % 2 ? -1 : 1, cur = pos(c);
      k++;
      tl.fromTo(c, { filter: "grayscale(0) brightness(1)" }, { filter: "grayscale(1) brightness(0.92)", duration: 0.05, ease: "none", immediateRender: false }, ti);
      tl.to(c, { x: cur.x + side * (o.dist ?? 900) * (0.9 + 0.3 * r()), y: cur.y + (o.drop ?? 160) * (0.4 + r()), rotation: cur.r + side * (25 + 25 * r()), duration: d, ease: "power2.in" }, ti + 0.05);
      tl.to(c, { opacity: 0, duration: 0.08, ease: "none" }, ti + 0.05 + d - 0.08);
    });
    return tl;
  };
  AR.insert = function (tl, item, t, o = {}) {
    const it = one(item), sp = space(it), R = rest(it, sp), cur = pos(it), dy = o.dy ?? R.h * 0.8, d = o.dur ?? 0.35, E = o.ease || "power2.in";
    tl.fromTo(it, { y: cur.y }, { y: cur.y + dy, duration: d, ease: E, immediateRender: false }, t);
    if (o.clipAt != null) { // a drawn-in occluder: hide what passes below the slot line (sp coordinates)
      const b0 = Math.max(0, R.y + R.h + cur.y - o.clipAt), b1 = Math.max(0, R.y + R.h + cur.y + dy - o.clipAt);
      const cut = "calc(100% - var(--ar-cut) * 1px)";
      it.style.clipPath = `polygon(-8px -8px, calc(100% + 8px) -8px, calc(100% + 8px) ${cut}, -8px ${cut})`;
      varTween(tl, it, "--ar-cut", b0 / cur.s, b1 / cur.s, t, d, E);
    }
    setPos(it, { y: cur.y + dy });
    els(o.rider).forEach((rd) => {
      const c = pos(rd);
      tl.fromTo(rd, { y: c.y }, { y: c.y + (o.riderDy ?? dy), duration: d, ease: E, immediateRender: false }, t);
      setPos(rd, { y: c.y + (o.riderDy ?? dy) });
    });
    return tl;
  };
})();
