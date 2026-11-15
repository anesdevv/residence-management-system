/* cast.js: generated characters (tools/cast.py: Charles from a photo, a goo monster, a rival) as actors with the
   critter's helpers. Extends window.AR; load after critter.js. Every timeline helper takes the timeline first and a scene
   time in seconds and only adds tweens and sets, so any frame renders on its own.

   A cast lives in assets/cast/<name>/ (poses/*.png on one canvas, cast.json). cast.json's "anchors" (written by
   `cast.py measure`, and by new/add/pose) say where each pose's feet, head top, face and hands are, so an actor stands
   by its feet at (x, y), is h px tall in its reference pose (head top to feet), and every pose, prop and hat lines up:
     const me = AR.cast.make("#b03-cast", "charles", { id: "b03-me", x: 900, y: 590, h: 300, flip: true });
     AR.cast.hold(me, "megaphone");  AR.cast.wear(me, "crown");
     AR.cast.pose(tl, me, 0.4, "point");  AR.cast.say(tl, me, 0.5, "Comment GOD TIER");  AR.hop(tl, me, 1.1);
   cast.json is read once, when the scene builds (a synchronous read of a local file; nothing depends on time).
   AR.hop / bob / drop / walk / pose / poses / blink / emote aimed at an actor move its body and keep its ground shadow on
   the floor; every other target goes to the helper as it was (AR.<name>.__orig is the original). AR.crit.say, typing,
   emote, alive, victory, ko, swing, dress, unwear, give, letgo, walk, pose, hold, wear, role and perch take actors too,
   so a blueprint's host can be the critter, the pal or a cast.py character (AR.cast.host). AR.crit.eyes and arms do
   nothing to an actor (it has poses, not eyes); AR.cast.act does nothing to a critter. */
(function () {
  "use strict";
  const AR = (window.AR = window.AR || {});
  const NS = "http://www.w3.org/2000/svg";
  const PROP_DIR = "assets/cast/props/";

  const all = (sel, root) => {
    if (!sel) return [];
    if (typeof sel === "string") return Array.from((root || document).querySelectorAll(sel));
    if (sel.length !== undefined && !(sel instanceof Element)) return Array.from(sel).filter(Boolean);
    return [sel];
  };
  const div = (cls) => { const d = document.createElement("div"); if (cls) d.className = cls; return d; };
  const svgEl = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const k in attrs || {}) e.setAttribute(k, attrs[k]); return e; };
  const rect = (p, r, fill) => { const e = svgEl("rect", { x: r[0], y: r[1], width: r[2], height: r[3] }); e.style.fill = fill; p.appendChild(e); return e; };
  const listOpt = (v) => (v == null || v === "" ? [] : Array.isArray(v) ? v : String(v).split(/[,\s]+/).filter(Boolean));
  const isCast = (el) => !!(el && el._cast);
  const casts = (sel) => all(sel).filter(isCast);
  const stateAt = (keys, t) => {
    let best = keys[0];
    keys.forEach((k) => { if (k[0] <= t + 1e-6 && k[0] >= best[0]) best = k; });
    return best[1];
  };

  // ---------- data ----------
  const DATA = {};
  const dirOf = (who) => (String(who).includes("/") ? String(who).replace(/\/?$/, "/") : `assets/cast/${who}/`);
  function prep(d, dir) {
    const [W, H] = d.canvas, ref = d.ref || (d.poses.includes("idle") ? "idle" : d.poses[0]);
    if (!d.anchors) console.warn(`cast: ${dir}cast.json has no anchors: run .venv/bin/python skills/charles-arcade-assets/tools/cast.py measure ${dir.replace(/\/$/, "")}`);
    const height = d.height || d.body_px || H * 0.9, A = {};
    const guess = { feet: [W / 2, H - 2], head: [W / 2, H - 2 - height], face: [W / 2, H - 2 - height * 0.62],
      hand_r: [W * 0.76, H - 2 - height * 0.38], hand_l: [W * 0.24, H - 2 - height * 0.38], head_w: W * 0.6, scale: 1 };
    d.poses.forEach((p) => { A[p] = Object.assign({}, guess, (d.anchors || {})[p] || {}); });
    const F = A[ref].feet;
    return { dir, W, H, ref, poses: d.poses.slice(), A, height, type: d.type || "humanoid",
      box: d.box || [Math.max(0, F[0] - A[ref].head_w * 0.55), F[1] - height, Math.min(W, F[0] + A[ref].head_w * 0.55), F[1]],
      feetW: d.feet_w || A[ref].head_w * 0.6, headW: A[ref].head_w };
  }
  /** a cast's data (canvas, poses, anchors), read from assets/cast/<name>/cast.json once */
  function load(who) {
    const dir = dirOf(who);
    if (DATA[dir]) return DATA[dir];
    let d = null;
    try {
      const r = new XMLHttpRequest();
      r.open("GET", dir + "cast.json", false);
      r.send(null);
      if ((r.status === 200 || r.status === 0) && r.responseText) d = JSON.parse(r.responseText);
    } catch (e) { d = null; }
    if (!d) { console.warn(`cast: no ${dir}cast.json (make the character with tools/cast.py, or give its folder)`); return null; }
    return (DATA[dir] = prep(d, dir));
  }

  // ---------- geometry: a pose's canvas px -> the actor's box px (unmirrored; the flip layer mirrors) ----------
  const zoomOf = (c, name) => c.D.A[name].zoom || 1;
  const loc = (c, name, q) => {
    const a = c.D.A[name], z = c.k * zoomOf(c, name);
    return [c.fx + (q[0] - a.feet[0]) * z, c.fy + (q[1] - a.feet[1]) * z];
  };
  const poseAt = (c, t) => stateAt(c.keys.pose, t);
  const cu = (c) => c.h / 8;   // the critter's unit for an actor (a critter is 8u tall): options in u mean the same on both
  const flipAt = (c, t) => stateAt(c.keys.flip, t);
  const screenX = (c, x, t) => (flipAt(c, t) ? 2 * c.fx - x : x);
  const headOf = (c, name) => {
    const a = c.D.A[name];
    return { top: loc(c, name, a.head), face: loc(c, name, a.face), w: a.head_w * c.k * zoomOf(c, name) };
  };

  // poses by meaning, for casts that lack one (a creature has no point; an object no walk)
  const MEAN = {
    idle: ["idle"], cheer: ["cheer", "fight_victory", "jump", "bounce", "shine"], happy: ["cheer", "jump", "bounce", "shine"],
    victory: ["fight_victory", "cheer", "jump", "bounce", "shine"], jump: ["jump", "cheer", "bounce"],
    sad: ["sad", "hurt", "ko", "squash"], shock: ["shock", "fight_hurt", "hurt", "squash"], think: ["think"],
    point: ["point", "talk", "taunt"], talk: ["talk", "point", "taunt"], taunt: ["taunt", "point", "talk"],
    hurt: ["fight_hurt", "hurt", "shock", "squash", "sad"], ko: ["ko", "fight_hurt", "hurt", "sad", "squash"],
    attack: ["fight_attack", "point", "taunt", "talk"], ready: ["fight_ready"], walk_a: ["walk_a"], walk_b: ["walk_b"],
    bounce: ["bounce", "jump", "cheer"], squash: ["squash", "hurt"], shine: ["shine", "cheer"],
  };
  const pick = (c, name) => {
    if (!name) return null;
    if (c.imgs[name]) return name;
    for (const n of MEAN[name] || []) if (c.imgs[n]) return n;
    return null;
  };

  // ---------- making an actor ----------
  /** an actor in parent with its feet at (x, y), h px tall in its reference pose (head top to feet).
   *  o: {id, x, y, h (300), pose (the first pose), flip (true: mirrored, it faces left), face ("left": flip), poses (the
   *  pose names to load, default all), ground (false: no shadow), hold, wear, role, className, z} */
  function make(parent, who, o = {}) {
    const p = all(parent)[0], D = load(who);
    if (!p || !D) return null;
    const el = div("cast-actor" + (o.className ? " " + o.className : ""));
    if (o.id) el.id = o.id;
    el.dataset.cast = String(who);
    const h = o.h ?? 300, k = h / D.height, F = D.A[D.ref].feet, B = D.box;
    const bw = (B[2] - B[0]) * k, bh = (F[1] - B[1]) * k, fx = (F[0] - B[0]) * k, fy = bh;
    Object.assign(el.style, { left: (o.x ?? 0) - fx + "px", top: (o.y ?? 0) - fy + "px", width: bw + "px", height: bh + "px",
      transformOrigin: `${fx}px ${fy}px` });
    if (o.z != null) el.style.zIndex = o.z;
    const ground = div("cast-ground");
    const gw = Math.max(D.feetW * 1.3, D.headW * 0.5) * k, gh = Math.max(4, gw * 0.14);
    Object.assign(ground.style, { left: fx - gw / 2 + "px", top: fy - gh * 0.55 + "px", width: gw + "px", height: gh + "px" });
    if (o.ground === false) ground.style.opacity = 0;
    const body = div("cast-body"), flip = div("cast-flip"), fxl = div("cast-fx");
    body.style.transformOrigin = `${fx}px ${fy}px`;
    flip.style.transformOrigin = `${fx}px ${fy}px`;
    el.appendChild(ground);
    el.appendChild(body);
    body.appendChild(flip);
    body.appendChild(fxl);
    const c = { D, k, h, fx, fy, el, body, flip, fxl, ground, imgs: {}, hands: {}, items: {}, says: [],
      u: (D.headW * k) / 8, keys: { pose: [], flip: [] }, noGround: o.ground === false };
    el._cast = c;
    const want = listOpt(o.poses);
    const names = D.poses.filter((n) => !want.length || want.includes(n) || n === D.ref);
    names.forEach((name) => {
      const a = D.A[name], z = k * zoomOf(c, name), img = document.createElement("img");
      img.className = "cast-pose";
      img.dataset.pose = name;
      img.src = D.dir + "poses/" + name + ".png";
      img.alt = "";
      img.setAttribute("data-layout-ignore", "");
      Object.assign(img.style, { width: D.W * z + "px", height: D.H * z + "px", left: fx - a.feet[0] * z + "px", top: fy - a.feet[1] * z + "px" });
      flip.appendChild(img);
      c.imgs[name] = img;
    });
    ["l", "r"].forEach((side) => { const hd = div("cast-hand"); hd.dataset.hand = side; flip.appendChild(hd); c.hands[side] = hd; });
    c.worn = div("cast-worn");
    flip.appendChild(c.worn);
    const first = pick(c, o.pose) || D.ref;
    c.keys.pose.push([-1, first]);
    c.keys.flip.push([-1, !!(o.flip || o.face === "left")]);
    showPose(c, first, null);
    if (o.flip || o.face === "left") gsap.set(flip, { scaleX: -1 });
    p.appendChild(el);
    if (o.role) S.role(el, o.role);
    listOpt(o.wear).forEach((w) => (Array.isArray(w) ? S.wear(el, w[0], w[1] || {}) : S.wear(el, w)));
    listOpt(o.hold).forEach((w, i) => (Array.isArray(w) ? S.hold(el, w[0], Object.assign({ hand: i ? "l" : "r" }, w[1] || {}))
      : S.hold(el, w, { hand: i ? "l" : "r" })));
    return el;
  }

  // shows a pose: at build time (tl null) or at t; hands and worn items move to its anchors
  function showPose(c, name, tl, t) {
    const A = c.D.A[name], hr = loc(c, name, A.hand_r), hl = loc(c, name, A.hand_l), hd = headOf(c, name);
    const set = (target, v) => (tl ? tl.set(target, v, t) : gsap.set(target, v));
    Object.entries(c.imgs).forEach(([n, img]) => {
      if (tl) tl.set(img, { opacity: n === name ? 1 : 0 }, t);
      else img.style.opacity = n === name ? 1 : 0;
    });
    set(c.hands.r, { x: hr[0], y: hr[1] });
    set(c.hands.l, { x: hl[0], y: hl[1] });
    set(c.worn, { x: hd.top[0], y: hd.top[1] });
  }
  function setPose(tl, el, t, name) {
    const c = el._cast, p = pick(c, name);
    if (!p) return null;
    if (t <= 1e-4) {
      c.keys.pose[0] = [-1, p];
      showPose(c, p, null);
    } else {
      showPose(c, p, tl, t);
      c.keys.pose.push([t, p]);
    }
    return p;
  }

  // ---------- props and wearables ----------
  // code-drawn critter wearables that have a pixel twin in the props library
  const TWIN = { crown: "hat-crown", fedora: "hat-fedora", hardhat: "hat-hard", "hardhat-white": "hat-hard-white", cap: "hat-cap", beret: "hat-beret" };
  // how library hats sit on a head: w (u, a head is 8u wide), sink (u: how far below the head top the hat's bottom edge goes)
  const HATS = {
    "hat-crown": { w: 5.2, sink: 1.0 }, "hat-fedora": { w: 8.8, sink: 2.9 }, "hat-hard": { w: 7.8, sink: 3.0 },
    "hat-hard-white": { w: 7.8, sink: 3.0 }, "hat-cap": { w: 7.9, sink: 2.7 }, "hat-beret": { w: 7.4, sink: 1.9 },
  };
  function defOf(prop, o) {
    const C = AR.crit;
    let def = C && C.propDef ? C.propDef(prop, o) : null;
    if (!def) return null;
    if (def.code) {
      if (!TWIN[def.name]) return { skip: def.name };
      def = Object.assign(C.propDef(TWIN[def.name], o), { name: def.name, twin: TWIN[def.name] });
    }
    return def;
  }
  function attach(el, prop, o = {}) {
    const c = el._cast, def = defOf(prop, o);
    if (!def) return null;
    if (def.skip) return null;     // drawn on the critter's grid only (a coat, sunglasses): left off a generated character
    const name = o.as || def.name;
    if (c.items[name]) return c.items[name];
    const u = c.u, hat = HATS[def.twin || def.name] || {};
    const slot = o.slot || (o.mode === "hold" ? "hand" : def.slot === "hand" || !def.slot ? (o.mode === "wear" ? "head" : "hand") : def.slot);
    const rec = { name, def, slot, el };
    const src = def.src || PROP_DIR + def.file;
    if (slot === "hand") {
      const side = String(o.hand || def.hand || "r")[0] === "l" ? "l" : "r";
      const W = o.px ?? (o.w || def.w || 3) * u, H = (W * def.size[1]) / def.size[0];
      const item = div("cast-item"), grip = div("cast-grip"), img = document.createElement("img");
      item.dataset.prop = name;
      img.src = src;
      img.alt = "";
      let gx = def.grip ? def.grip[0] : 0.5, gy = def.grip ? def.grip[1] : 0.5, rot = o.rot ?? def.rot ?? 0;
      const mirrored = side === "l" && def.flip !== false;
      if (side === "l") { gx = 1 - gx; rot = -rot; if (def.flip !== false) img.style.transform = "scaleX(-1)"; }
      Object.assign(img.style, { width: W + "px", height: H + "px", left: -gx * W + "px", top: -gy * H + "px" });
      grip.style.left = (o.dx || 0) * u + "px";
      grip.style.top = (o.dy || 0) * u + "px";
      gsap.set(grip, { rotation: rot });
      grip.appendChild(img);
      const lab = AR.crit.propLabel ? AR.crit.propLabel(def, W, H, o, mirrored) : null;
      if (lab) { lab.style.left = parseFloat(lab.style.left) - gx * W + "px"; lab.style.top = parseFloat(lab.style.top) - gy * H + "px"; grip.appendChild(lab); }
      item.appendChild(grip);
      c.hands[side].appendChild(item);
      Object.assign(rec, { root: item, move: item, grip, img, side, W, H, gx, gy, rot });
    } else {
      // head (a hat on the head top), face, body (the chest), ground (beside the feet): placed on the reference pose
      const W = o.px ?? (o.w || hat.w || def.w || 4) * u, H = (W * def.size[1]) / def.size[0];
      const box = div("cast-worn"), move = div("cast-move"), img = document.createElement("img");
      box.dataset.prop = name;
      box.dataset.slot = slot;
      img.src = src;
      img.alt = "";
      if (o.flip) img.style.transform = "scaleX(-1)";
      move.appendChild(img);
      const lab = AR.crit.propLabel ? AR.crit.propLabel(def, W, H, o, !!o.flip) : null;
      if (lab) move.appendChild(lab);
      box.appendChild(move);
      const dx = (o.dx || 0) * u, dy = (o.dy || 0) * u;
      let left, top;
      if (slot === "head") {
        const sink = (o.sink ?? hat.sink ?? 1.2) * u;
        left = -W / 2 + dx;
        top = -H + sink + dy;
        Object.assign(move.style, { left: left + "px", top: top + "px", width: W + "px", height: H + "px" });
        c.worn.appendChild(box);
        rec.top = top;
      } else {
        const r = c.D.ref, A = c.D.A[r], an = def.anchor || [0.5, slot === "body" ? 0 : slot === "face" ? 0.5 : 1];
        const at = slot === "face" ? loc(c, r, A.face) : slot === "body" ? loc(c, r, [A.face[0], A.face[1] + (A.feet[1] - A.face[1]) * 0.36])
          : [c.fx + (o.at ? o.at[0] * u : 0.62 * c.D.headW * c.k), c.fy];
        left = at[0] - an[0] * W + dx;
        top = at[1] - an[1] * H + dy;
        Object.assign(move.style, { left: left + "px", top: top + "px", width: W + "px", height: H + "px" });
        box.style.zIndex = slot === "ground" ? 0 : 6;
        (slot === "ground" ? c.flip : c.flip).appendChild(box);
      }
      if (def.rot || o.rot) gsap.set(move, { rotation: o.rot ?? def.rot, transformOrigin: "50% 100%" });
      Object.assign(rec, { root: box, move, img, W, H });
    }
    c.items[name] = rec;
    return rec;
  }
  const heldRec = (c, names) => {
    for (const n of [].concat(names || []).filter(Boolean)) if (c.items[n] && c.items[n].slot === "hand") return c.items[n];
    return Object.values(c.items).find((r) => r.slot === "hand");
  };

  // ---------- bubbles and emotes (the critter's look) ----------
  function bubble(c, t, o) {
    const wrap = div("crit-say"), box = div("crit-say-box pxt");
    if (o.size) box.style.fontSize = o.size + "px";
    if (o.maxWidth) box.style.maxWidth = o.maxWidth + "px";
    wrap.appendChild(box);
    const tail = svgEl("svg", { viewBox: "0 0 5 3", class: "crit-say-tail" });
    const ink = "var(--ink, #1f1e1c)";
    [[0, 0, 1, 1], [4, 0, 1, 1], [1, 1, 1, 1], [3, 1, 1, 1], [2, 2, 1, 1]].forEach((r) => rect(tail, r, ink));
    [[1, 0, 3, 1], [2, 1, 1, 1]].forEach((r) => rect(tail, r, "#fff"));
    wrap.appendChild(tail);
    const pose = poseAt(c, t), hd = headOf(c, pose), side = o.side || "right";
    const hatTop = Object.values(c.items).reduce((m, r) => (r.slot === "head" && !r.off ? Math.min(m, hd.top[1] + r.top) : m), hd.top[1]);
    const hx = screenX(c, hd.top[0], t);
    const x = o.x ?? hx + (side === "left" ? -0.2 : side === "center" ? 0 : 0.2) * hd.w + (o.dx || 0);
    const y = o.y ?? Math.min(hd.top[1], hatTop) - 0.03 * c.h + (o.dy || 0);
    Object.assign(wrap.style, { left: x + "px", top: y + "px" });
    box.style.transform = `translateX(${side === "left" ? -84 : side === "center" ? -50 : -16}%)`;
    c.el.appendChild(wrap);
    return { wrap, box };
  }
  const sayOut = (tl, b, t) => tl.to(b, { opacity: 0, scale: 0.7, duration: 0.1, ease: "power2.in" }, t);
  function emoteAt(c, t, kind) {
    const pose = poseAt(c, t), hd = headOf(c, pose), x = screenX(c, hd.top[0], t), s = flipAt(c, t) ? -1 : 1;
    if (kind === "sweat") return [screenX(c, hd.face[0] + s * 0.42 * hd.w, t), hd.face[1] - 0.3 * hd.w];
    if (kind === "stars") return [x, hd.top[1] - 0.06 * hd.w];
    return [x + 0.36 * hd.w, hd.top[1] - 0.04 * hd.w];
  }

  // ---------- the helpers ----------
  const S = {
    /** the actor helpers' data (canvas, poses, anchors) for a cast name or folder */
    data: load,
    make,
    /** the host of a blueprint: "critter" or "pal" (critter.js) or a cast.py character's folder name ("charles").
     *  o: the critter's options (u, eyes, color, role, hold, wear) and the actor's (h, default 9.5u; face "left" turns
     *  a generated character to look left; pose) with id, x, y (the feet) */
    host(parent, who, o = {}) {
      who = who || "critter";
      if (who === "critter" || who === "pal") return AR.crit.make(parent, Object.assign({}, o, { shape: who }));
      return make(parent, who, Object.assign({}, o, { h: o.h ?? (o.u ? o.u * 9.5 : 300) }));
    },
    /** whether an element is a generated character's actor */
    isCast,
    /** whether an actor has a pose (or one with that meaning) */
    has(sel, name) { const el = casts(sel)[0]; return !!(el && pick(el._cast, name)); },
    /** switch the pose at t (a name, or a meaning the cast lacks a pose for: cheer jump sad shock point talk think hurt ko
     *  attack ready taunt...); held props and hats follow the new pose's anchors */
    pose(tl, sel, t, name) { casts(sel).forEach((el) => setPose(tl, el, t, name)); return tl; },
    poses(tl, sel, keys) { keys.forEach(([t, name]) => S.pose(tl, sel, t, name)); return tl; },
    /** a pose by meaning for a generated character; a critter or pal ignores it (it acts with eyes and arms) */
    act(tl, sel, t, what, o = {}) {
      casts(sel).forEach((el) => {
        const c = el._cast, before = poseAt(c, t);
        if (!setPose(tl, el, t, what)) return;
        if (o.dur) setPose(tl, el, t + o.dur, o.back || before);
      });
      return tl;
    },
    /** turn around at t (mirror); o: true faces left, false back; props turn with it, text does not */
    flip(tl, sel, t, on) {
      casts(sel).forEach((el) => {
        const c = el._cast, v = on === undefined ? !flipAt(c, t) : !!on;
        if (t <= 1e-4) { c.keys.flip[0] = [-1, v]; gsap.set(c.flip, { scaleX: v ? -1 : 1 }); }
        else { tl.set(c.flip, { scaleX: v ? -1 : 1 }, t); c.keys.flip.push([t, v]); }
      });
      return tl;
    },
    /** a library prop in a hand (static setup): hand "r" (the image's right) or "l", w (u: a head is 8u wide), rot, dx,
     *  dy, text (on a labelled prop) */
    hold(sel, prop, o = {}) { return casts(sel).map((el) => attach(el, prop, Object.assign({}, o, { mode: "hold" })))[0]; },
    /** a wearable on (static setup): a library hat (hat-crown, hat-fedora, hat-hard, hat-cap, hat-beret; the critter's
     *  crown, fedora, hardhat, cap and beret become them) on the head, or any image prop with {slot: head, face, body,
     *  ground}, w (u), sink (u: how far the hat comes down over the head), dx, dy. Clothes drawn on the critter's grid
     *  (coat, suit, sunglasses...) are left off a generated character */
    wear(sel, prop, o = {}) { return casts(sel).map((el) => attach(el, prop, Object.assign({}, o, { mode: "wear" })))[0]; },
    /** a costume from AR.crit.ROLES: its props in hand, its hats on the head (its clothes left off) */
    role(sel, name, o = {}) {
      const r = (AR.crit.ROLES || {})[name];
      if (!r) { console.warn(`cast: no role "${name}"`); return; }
      casts(sel).forEach((el) => {
        (r.wear || []).forEach((p) => (Array.isArray(p) ? S.wear(el, p[0], p[1] || {}) : S.wear(el, p)));
        (r.hold || []).forEach((p, i) => S.hold(el, Array.isArray(p) ? p[0] : p, Object.assign({ hand: i ? "l" : "r" }, Array.isArray(p) ? p[1] : {})));
      });
    },
    /** costume drop on the word: the item falls onto the head (or into the hand) and lands at t; the actor squashes.
     *  An item taken off with unwear() drops back on. o: {dur (0.24), from (px), rot, hand, slot, w} */
    dress(tl, sel, prop, t, o = {}) {
      casts(sel).forEach((el) => {
        const c = el._cast, def = defOf(prop, o);
        if (!def || def.skip) return;
        let rec = c.items[o.as || def.name];
        const fresh = !rec;
        if (fresh) {
          rec = attach(el, prop, Object.assign({}, o, { mode: def.slot === "hand" && (o.hand || o.slot === "hand") ? "hold" : "wear" }));
          if (!rec) return;
          rec.move.style.opacity = 0;
        }
        const dur = o.dur ?? 0.24, t0 = Math.max(0, t - dur);
        if (fresh || !rec.off) {
          const fall = o.from ?? Math.max(1.6 * c.h, 400);
          tl.set(rec.move, { opacity: 1 }, t0);
          tl.fromTo(rec.move, { y: -fall, rotation: o.rot ?? -10 }, { y: 0, rotation: 0, duration: t - t0, ease: "power2.in", immediateRender: false }, t0);
        } else {
          tl.to(rec.move, { x: 0, y: 0, rotation: 0, opacity: 1, duration: t - t0, ease: "power2.in" }, t0);
        }
        rec.off = false;
        if (o.squash !== false) {
          tl.set(c.body, { scaleY: 0.86, scaleX: 1.1 }, t);
          tl.to(c.body, { scaleY: 1, scaleX: 1, duration: 0.26, ease: "back.out(3)" }, t);
        }
      });
      return tl;
    },
    /** a worn or held item flies off: o.to up (default) / left / right / down, o.dist (u, 7), o.spin, o.fade */
    unwear(tl, sel, prop, t, o = {}) {
      casts(sel).forEach((el) => {
        const c = el._cast, rec = c.items[prop];
        if (!rec) return;
        const u = c.u, dur = o.dur ?? 0.32, d = (o.dist ?? 7) * u, to = o.to || "up";
        const x = to === "left" ? -d : to === "right" ? d : (o.dx ?? 0.4) * u, y = to === "down" ? 0.4 * d : to === "up" ? -d : -0.5 * d;
        tl.to(rec.move, { x, y, rotation: o.spin ?? (to === "left" ? -24 : 14), duration: dur, ease: "power3.out" }, t);
        if (o.fade) tl.to(rec.move, { opacity: 0, duration: dur * 0.4, ease: "power1.in" }, t + dur * 0.6);
        tl.set(c.body, { scaleY: 1.06, scaleX: 0.96 }, t);
        tl.to(c.body, { scaleY: 1, scaleX: 1, duration: 0.2, ease: "back.out(3)" }, t);
        rec.off = true;
      });
      return tl;
    },
    /** a held prop pops into the hand at t (hidden before) */
    give(tl, sel, prop, t, o = {}) {
      casts(sel).forEach((el) => {
        const rec = el._cast.items[prop] || attach(el, prop, Object.assign({}, o, { mode: "hold" }));
        if (rec) tl.fromTo(rec.move, { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.24, ease: "back.out(2.6)" }, t);
      });
      return tl;
    },
    /** a held prop drops to the floor beside the feet and lies there */
    letgo(tl, sel, prop, t, o = {}) {
      casts(sel).forEach((el) => {
        const c = el._cast, rec = prop ? c.items[prop] : heldRec(c);
        if (!rec || rec.slot !== "hand") return;
        const pose = poseAt(c, t), A = c.D.A[pose], hand = loc(c, pose, rec.side === "r" ? A.hand_r : A.hand_l);
        const floor = c.fy - hand[1] - Math.min(rec.W, rec.H) * 0.25, s = rec.side === "r" ? 1 : -1;
        tl.to(rec.move, { x: s * (o.dx ?? 1.2) * c.u, duration: 0.4, ease: "power1.out" }, t);
        tl.to(rec.move, { y: floor, duration: 0.4, ease: "bounce.out" }, t);
        tl.to(rec.move, { rotation: s * (o.rot ?? 96), duration: 0.32, ease: "power2.in" }, t);
        rec.off = true;
      });
      return tl;
    },
    /** swing a held tool (a hammer, a sword): wind up, strike down at t + 0.12, o.n times; the body squashes */
    swing(tl, sel, t, o = {}) {
      casts(sel).forEach((el) => {
        const c = el._cast, rec = heldRec(c, [o.prop, "hammer", "sword", "wrench"]);
        if (!rec) return;
        const n = o.n ?? 1, s = rec.side === "r" ? 1 : -1, base = rec.rot || 0;
        for (let i = 0; i < n; i++) {
          const k = t + i * 0.3;
          tl.to(rec.grip, { rotation: base - 40 * s, duration: 0.12, ease: "power2.out" }, k);
          tl.to(rec.grip, { rotation: base + 70 * s, duration: 0.08, ease: "power4.in" }, k + 0.12);
          tl.to(rec.grip, { rotation: base, duration: 0.14, ease: "power2.out" }, k + 0.22);
          tl.set(c.body, { scaleY: 0.94, scaleX: 1.04 }, k + 0.2);
          tl.to(c.body, { scaleY: 1, scaleX: 1, duration: 0.16, ease: "back.out(2)" }, k + 0.2);
        }
      });
      return tl;
    },
    /** victory: the cheer pose (or its nearest), a hop (o.h in u, 1.3: a critter is 8u tall), held props raised */
    victory(tl, sel, t, o = {}) {
      casts(sel).forEach((el) => {
        const c = el._cast;
        setPose(tl, el, t, o.pose || "victory");
        hop(tl, el, t, { h: (o.h ?? 1.3) * cu(c), dur: 0.34, pose: false });
        Object.values(c.items).filter((r) => r.slot === "hand").forEach((r) =>
          tl.to(r.grip, { rotation: (r.rot || 0) + (r.side === "r" ? -12 : 12), duration: 0.16, ease: "back.out(3)" }, t));
      });
      return tl;
    },
    /** hurt: the hurt pose (or its nearest), knocked back o.dx u (0.6), back to the pose before after o.dur (0.5; null stays) */
    hurt(tl, sel, t, o = {}) {
      casts(sel).forEach((el) => {
        const c = el._cast, before = poseAt(c, t), dir = o.dir === "left" ? 1 : -1;
        setPose(tl, el, t, "hurt");
        tl.to(el, { x: `+=${dir * (o.dx ?? 0.6) * cu(c)}`, duration: 0.14, ease: "power3.out" }, t);
        tl.set(c.body, { scaleY: 0.9, scaleX: 1.06 }, t);
        tl.to(c.body, { scaleY: 1, scaleX: 1, duration: 0.22, ease: "back.out(2.5)" }, t);
        if (o.dur !== null) setPose(tl, el, t + (o.dur ?? 0.5), before);
      });
      return tl;
    },
    /** knocked out: the ko pose (or hurt, sad), knocked back with a tilt, held props drop, stars */
    ko(tl, sel, t, o = {}) {
      casts(sel).forEach((el) => {
        const c = el._cast, dir = o.dir === "left" ? 1 : -1;
        setPose(tl, el, t, "ko");
        tl.to(el, { x: `+=${dir * (o.dx ?? 0.8) * cu(c)}`, duration: 0.22, ease: "power3.out" }, t);
        tl.to(c.body, { rotation: dir * 12, duration: 0.12, ease: "power2.out" }, t);
        tl.to(c.body, { rotation: dir * 6, duration: 0.3, ease: "bounce.out" }, t + 0.12);
        Object.values(c.items).filter((r) => r.slot === "hand").forEach((r) => S.letgo(tl, el, r.name, t + 0.04, o));
        if (o.stars !== false) S.emote(tl, el, t + 0.1, "stars", { dur: o.starDur ?? 0.9 });
      });
      return tl;
    },
    /** idle life: a stepped bob of o.amp u (0.1; a critter is 8u tall) at o.fps (2.5), and blinks when the cast has a
     *  "blink" pose; o.bob false: no bob */
    alive(tl, sel, t, dur, o = {}) {
      casts(sel).forEach((el, i) => {
        const c = el._cast, r = AR.rnd ? AR.rnd((o.seed ?? 11) + i * 31) : Math.random;
        if (c.imgs.blink) {
          let k = t + 0.35 + r() * 0.9;
          while (k < t + dur - 0.15) {
            const back = poseAt(c, k);
            if (back === c.D.ref) { setPose(tl, el, k, "blink"); setPose(tl, el, k + 0.1, back); }
            k += 1.3 + r() * 1.1;
          }
        }
        if (o.bob !== false) {
          const fps = o.fps ?? 2.5, amp = (o.amp ?? 0.1) * cu(c), off = r() / fps, n = Math.floor((dur - off) * fps);
          for (let j = 0; j < n; j++) tl.set(c.body, { y: j % 2 ? -amp : 0 }, t + off + j / fps);
          tl.set(c.body, { y: 0 }, t + off + Math.max(0, n) / fps);
        }
      });
      return tl;
    },
    /** walk: walk_a / walk_b swap while the whole actor (shadow included) moves by o.x / o.y; a cast without walk
     *  poses hops along. o: {x, y, fps (8), ease, end (the pose after), turn (true: face the way it walks)} */
    walk(tl, sel, t, dur, o = {}) {
      casts(sel).forEach((el) => {
        const c = el._cast, fps = o.fps ?? 8, n = Math.max(1, Math.floor(dur * fps)), before = poseAt(c, t);
        const a = pick(c, o.a || "walk_a"), b = pick(c, o.b || "walk_b");
        const dx = typeof o.x === "number" ? o.x : typeof o.x === "string" ? parseFloat(o.x.replace("=", "")) * (o.x.startsWith("-") ? -1 : 1) : 0;
        if (o.turn && dx) S.flip(tl, el, t, dx < 0);
        if (a && b) {
          for (let i = 0; i < n; i++) setPose(tl, el, t + i / fps, i % 2 ? b : a);
          for (let i = 0; i < n; i++) tl.set(c.body, { y: i % 2 ? -0.012 * c.h : 0 }, t + i / fps);
          tl.set(c.body, { y: 0 }, t + dur);
        } else {
          for (let i = 0; i < n; i += 2) hop(tl, el, t + i / fps, { h: 0.05 * c.h, dur: Math.min(0.3, 1.8 / fps), pose: false });
        }
        setPose(tl, el, t + dur, o.end || before);
        if (o.x !== undefined || o.y !== undefined) tl.to(el, { x: o.x ?? "+=0", y: o.y ?? "+=0", duration: dur, ease: o.ease ?? "none" }, t);
      });
      return tl;
    },
    /** a tailed pixel speech bubble over the head (above any hat), the critter's bubble. o: {dur (stays until the next
     *  say if left out), side right/left/center, size (px), typing (s of "..." first), dx, dy (px), x, y, maxWidth} */
    say(tl, sel, t, text, o = {}) {
      casts(sel).forEach((el) => {
        const c = el._cast;
        let t1 = t;
        if (o.typing) { S.typing(tl, el, t, o.typing, Object.assign({}, o, { _chain: true })); t1 = t + o.typing; }
        const { wrap, box } = bubble(c, t1, o);
        box.textContent = text;
        if (AR.names) AR.names(box);
        const prev = c.says[c.says.length - 1];
        if (prev && prev.end == null && prev.start < t1) { sayOut(tl, prev.el, t1); prev.end = t1; }
        tl.fromTo(wrap, { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.16, ease: "back.out(2.6)" }, t1);
        const end = o.dur != null ? t1 + o.dur : null;
        if (end != null) sayOut(tl, wrap, end);
        c.says.push({ el: wrap, start: t1, end });
      });
      return tl;
    },
    /** a "..." typing bubble for dur seconds */
    typing(tl, sel, t, dur, o = {}) {
      casts(sel).forEach((el) => {
        const c = el._cast, { wrap, box } = bubble(c, t, o);
        box.classList.add("crit-dots-box");
        const dots = div("crit-dots");
        for (let i = 0; i < 3; i++) dots.appendChild(document.createElement("i"));
        box.appendChild(dots);
        const prev = c.says[c.says.length - 1];
        if (prev && prev.end == null && prev.start < t) { sayOut(tl, prev.el, t); prev.end = t; }
        tl.fromTo(wrap, { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.14, ease: "back.out(2.6)" }, t);
        const ds = Array.from(dots.children), fps = 7, n = Math.floor(dur * fps);
        for (let i = 0; i < n; i++) ds.forEach((d, j) => tl.set(d, { opacity: j === i % 3 ? 1 : 0.25 }, t + i / fps));
        if (o._chain) tl.set(wrap, { opacity: 0 }, t + dur); else sayOut(tl, wrap, t + dur);
        c.says.push({ el: wrap, start: t, end: t + dur });
      });
      return tl;
    },
    /** a bare pixel glyph over the head: "!" "?" sweat heart spark stars anger (the critter's); o.dur (0.6), o.scale */
    emote(tl, sel, t, kind, o = {}) {
      const G = (AR.crit && AR.crit.EMOTE) || {}, E = G[kind] || G["!"];
      if (!E) return tl;
      casts(sel).forEach((el) => {
        const c = el._cast, cell = Math.max(3, Math.round(c.u * (o.scale ?? 0.36)));
        const s = svgEl("svg", { viewBox: `0 0 ${E.w} ${E.h}`, width: E.w * cell, height: E.h * cell, class: "crit-emote" });
        E.cells.forEach((r) => rect(s, r, E.color));
        (E.glint || []).forEach((r) => rect(s, r, "#FFFFFF"));
        const at = o.at || emoteAt(c, t, kind), w = E.w * cell, h = E.h * cell;
        Object.assign(s.style, { left: at[0] - (kind === "sweat" ? 0 : kind === "stars" ? w / 2 : 0) + "px", top: at[1] - (kind === "sweat" ? 0 : h) + "px" });
        c.fxl.appendChild(s);
        const dur = o.dur ?? 0.6;
        tl.fromTo(s, { opacity: 0, scale: 0.3, y: 0 }, { opacity: 1, scale: 1, duration: 0.14, ease: "back.out(3)" }, t);
        if (kind === "sweat") tl.to(s, { y: 0.8 * c.u, duration: dur, ease: "power1.in" }, t + 0.1);
        else if (kind === "stars") tl.to(s, { x: 0.4 * c.u, duration: dur, ease: "steps(4)" }, t);
        else tl.to(s, { y: -0.4 * c.u, duration: 0.12, ease: "power2.out", yoyo: true, repeat: 1 }, t + 0.14);
        tl.to(s, { opacity: 0, duration: 0.12 }, t + dur);
      });
      return tl;
    },
    /** stand on a card's edge: o.edge bottom (default) or top, o.at (0-1 along the edge, or px), o.inset (px) */
    perch(sel, cardSel, o = {}) {
      const card = all(cardSel)[0];
      casts(sel).forEach((el) => {
        const c = el._cast, parent = el.offsetParent || el.parentElement;
        let x = 0, y = 0, n = card;
        while (n && n !== parent) { x += n.offsetLeft || 0; y += n.offsetTop || 0; n = n.offsetParent; }
        const at = o.at ?? 0.12, px = x + (at <= 1 ? at * card.offsetWidth : at), py = y + (o.edge === "top" ? 0 : card.offsetHeight) - (o.inset ?? 0);
        el.style.left = px - c.fx + "px";
        el.style.top = py - c.fy + "px";
      });
    },
    /** where a hand is, in the actor's parent's px, in a pose (default: the one it starts in) */
    handAt(sel, side = "right", pose) {
      const el = casts(sel)[0], c = el._cast, p = pose ? pick(c, pose) : poseAt(c, 0), A = c.D.A[p];
      const q = loc(c, p, String(side)[0] === "l" ? A.hand_l : A.hand_r);
      return { x: el.offsetLeft + screenX(c, q[0], 0), y: el.offsetTop + q[1] };
    },
    /** the element of an item a host has on or in hand (critter or actor), to fade, hide or fly it */
    item(sel, name) {
      const el = all(sel)[0], rec = el && (el._cast || el._crit), r = rec && rec.items[name];
      return r ? r.move : null;
    },
    /** where a host's hand is (critter or actor), in its parent's px, in a pose (an actor) or arm state (a critter) */
    hand(sel, side = "right", state) {
      const el = all(sel)[0];
      if (!el) return null;
      if (el._cast) return S.handAt(el, side, state);
      return AR.crit.handAt(el, side, state || "down");
    },
    /** the items a host has on (critter or actor): [{name, slot, side}], props in hand first */
    items(sel) {
      const el = all(sel)[0], rec = el && (el._cast || el._crit);
      if (!rec) return [];
      return Object.values(rec.items).map((r) => ({ name: r.name, slot: r.slot, side: r.side })).sort((a, b) => (a.slot === "hand" ? -1 : 0) - (b.slot === "hand" ? -1 : 0));
    },
    /** take a photo: the held camera comes up to the face just before t, a white star bursts at its flash on t, and
     *  o.flash (a .flash element) flashes the scene; down after o.hold (0.35). o: {prop (camera), flash, peak (0.85)} */
    photo(tl, sel, t, o = {}) {
      casts(sel).forEach((el) => {
        const c = el._cast, name = o.prop || "camera", rec = c.items[name] || attach(el, name, { mode: "hold" });
        if (!rec || rec.slot !== "hand") return;
        const pose = poseAt(c, t), A = c.D.A[pose], hand = loc(c, pose, rec.side === "r" ? A.hand_r : A.hand_l);
        const face = loc(c, pose, A.face), lens = rec.def.lens || [0.5, 0.45], lx = rec.side === "l" ? 1 - lens[0] : lens[0];
        const x = face[0] - hand[0] - (lx - rec.gx) * rec.W + (rec.side === "r" ? 0.15 : -0.15) * c.D.headW * c.k;
        const y = face[1] - hand[1] - (lens[1] - rec.gy) * rec.H, hold = o.hold ?? 0.35;
        tl.to(rec.move, { x, y, duration: 0.1, ease: "power3.out" }, t - 0.12);
        tl.to(rec.grip, { rotation: 0, duration: 0.1 }, t - 0.12);
        const tip = rec.def.tip || [0.8, 0.1], fx = rec.side === "l" ? 1 - tip[0] : tip[0], sz = 2.2 * c.u;
        const px = hand[0] + x + (fx - rec.gx) * rec.W, py = hand[1] + y + (tip[1] - rec.gy) * rec.H;
        const star = svgEl("svg", { viewBox: "0 0 5 5", class: "crit-emote" });
        [[2, 0, 1, 5], [0, 2, 5, 1], [1, 1, 3, 3]].forEach((r) => rect(star, r, "#FFFFFF"));
        Object.assign(star.style, { width: sz + "px", height: sz + "px", left: screenX(c, px, t) - sz / 2 + "px", top: py - sz / 2 + "px" });
        c.fxl.appendChild(star);
        tl.fromTo(star, { opacity: 0, scale: 0.2, rotation: 0 }, { opacity: 1, scale: 1.3, rotation: 45, duration: 0.08, ease: "power3.out" }, t);
        tl.to(star, { opacity: 0, scale: 0.6, duration: 0.12 }, t + 0.1);
        if (o.flash) AR.flash(tl, o.flash, t, { peak: o.peak ?? 0.85, dur: 0.2 });
        tl.set(c.body, { scaleY: 0.96, scaleX: 1.03 }, t);
        tl.to(c.body, { scaleY: 1, scaleX: 1, duration: 0.16, ease: "back.out(2)" }, t);
        if (hold >= 0) {
          tl.to(rec.move, { x: 0, y: 0, duration: 0.14, ease: "power2.inOut" }, t + hold);
          tl.to(rec.grip, { rotation: rec.rot || 0, duration: 0.14 }, t + hold);
        }
      });
      return tl;
    },
    /** where the head top is (and its width), in the actor's parent's px */
    headAt(sel, pose) {
      const el = casts(sel)[0], c = el._cast, p = pose ? pick(c, pose) : poseAt(c, 0), hd = headOf(c, p);
      return { x: el.offsetLeft + screenX(c, hd.top[0], 0), y: el.offsetTop + hd.top[1], w: hd.w };
    },
  };

  // ---------- the body moves, the shadow stays on the floor ----------
  const orig = (name) => (AR[name] && AR[name].__orig) || AR[name];
  function hop(tl, el, t, o = {}) {
    const c = el._cast, d = o.dur ?? 0.36;
    orig("hop").call(AR, tl, c.body, t, o);
    if (o.pose !== false && c.imgs.jump && poseAt(c, t) === c.D.ref) {
      setPose(tl, el, t + d * 0.12, "jump");
      setPose(tl, el, t + d * 0.88, c.D.ref);
    }
    if (c.noGround) return;
    tl.to(c.ground, { scaleX: 0.72, scaleY: 0.8, opacity: 0.7, duration: d * 0.45, ease: "power2.out" }, t);
    tl.to(c.ground, { scaleX: 1, scaleY: 1, opacity: 1, duration: d * 0.55, ease: "power2.in" }, t + d * 0.45);
  }
  const CAST = {
    hop: (prev, tl, el, t, o = {}) => hop(tl, el, t, o),
    bob: (prev, tl, el, t, dur, o) => orig("bob").call(AR, tl, el._cast.body, t, dur, o),
    drop(prev, tl, el, t, o = {}) {
      const c = el._cast, d = o.dur ?? 0.6;
      orig("drop").call(AR, tl, c.body, t, o);
      if (!c.noGround) tl.fromTo(c.ground, { scaleX: 0.2, opacity: 0 }, { scaleX: 1, opacity: 1, duration: d * 0.36, ease: "power2.in" }, t);
    },
    walk: (prev, tl, el, t, dur, o = {}) => S.walk(tl, el, t, dur, o),
    pose: (prev, tl, el, name, t) => setPose(tl, el, t, name),
    poses: (prev, tl, el, keys) => keys.forEach(([t, name]) => setPose(tl, el, t, name)),
    blink(prev, tl, el, t, o = {}) {
      const c = el._cast;
      if (!c.imgs.blink) return;
      const back = poseAt(c, t);
      setPose(tl, el, t, "blink");
      setPose(tl, el, t + (o.dur ?? 0.1), o.back || back);
    },
    emote(prev, tl, el, kind, t, o = {}) {
      // motion.js's bubble emote, put over the head instead of over the box's corner
      const c = el._cast, hd = headOf(c, poseAt(c, t)), x = screenX(c, hd.top[0], t);
      const at = o.at || [(x + (kind === "sweat" ? -0.45 : 0.18) * hd.w) / el.offsetWidth, (hd.top[1] + (kind === "sweat" ? 0.3 : 0.02) * hd.w) / el.offsetHeight];
      return prev(tl, el, kind, t, Object.assign({ size: hd.w * 0.42 }, o, { at }));
    },
  };
  Object.keys(CAST).forEach((name) => {
    const prev = AR[name];
    if (typeof prev !== "function" || prev.__cast) return;
    const wrapped = function (tl, sel, ...rest) {
      let els;
      try { els = all(sel); } catch (e) { return prev.call(this, tl, sel, ...rest); }
      const cs = els.filter(isCast);
      if (!cs.length) return prev.call(this, tl, sel, ...rest);
      const others = els.filter((e) => !isCast(e));
      if (others.length) prev.call(this, tl, others, ...rest);
      cs.forEach((el) => CAST[name](prev, tl, el, ...rest));
      return tl;
    };
    wrapped.__orig = prev.__orig || prev;
    wrapped.__prev = prev;
    wrapped.__cast = true;
    AR[name] = wrapped;
  });
  S.hop = (tl, sel, t, o = {}) => { casts(sel).forEach((el) => hop(tl, el, t, o)); return tl; };
  S.bob = (tl, sel, t, dur, o) => { casts(sel).forEach((el) => CAST.bob(null, tl, el, t, dur, o)); return tl; };
  S.drop = (tl, sel, t, o) => { casts(sel).forEach((el) => CAST.drop(null, tl, el, t, o)); return tl; };

  // ---------- the critter's helpers take actors too ----------
  // only when an actor is among the targets: a critter, a pal or any other element gets the helper exactly as it was
  const C = AR.crit;
  if (C) {
    const via = (name, fn, at = 1) => {
      const prev = C[name];
      if (typeof prev !== "function" || prev.__cast) return;
      const wrapped = function (...args) {
        let els;
        try { els = all(args[at]); } catch (e) { return prev.apply(this, args); }
        const cs = els.filter(isCast);
        if (!cs.length) return prev.apply(this, args);
        const others = els.filter((e) => !isCast(e));
        let out;
        if (others.length) { const a2 = args.slice(); a2[at] = others; out = prev.apply(this, a2); }
        cs.forEach((el) => { const a2 = args.slice(); a2[at] = el; const r = fn.apply(this, a2); if (out === undefined) out = r; });
        return at === 0 ? out : args[0];
      };
      wrapped.__cast = true;
      wrapped.__prev = prev;
      C[name] = wrapped;
    };
    ["say", "typing", "emote", "alive", "victory", "ko", "swing", "dress", "unwear", "give", "letgo", "walk", "pose", "photo"].forEach((n) => via(n, S[n]));
    ["hold", "wear", "role", "perch", "handAt"].forEach((n) => via(n, S[n], 0));
  }

  /** a head tile of a character (a tier-list tile, a loot slot, a nameplate): its pose cropped to the head, which
   *  fills o.fill (0.9) of the box's width with its top o.top (0.07) down the box. o: {id, size or w and h (px), x, y,
   *  pose (the reference), fill, top, className}; returns the box (overflow hidden; style it as a tile) */
  S.portrait = function (parent, who, o = {}) {
    const p = all(parent)[0], D = load(who);
    if (!p || !D) return null;
    const W = o.w ?? o.size ?? 96, H = o.h ?? o.size ?? 96, pose = D.A[o.pose] ? o.pose : D.ref, a = D.A[pose];
    const box = div("cast-portrait" + (o.className ? " " + o.className : ""));
    if (o.id) box.id = o.id;
    Object.assign(box.style, { width: W + "px", height: H + "px" });
    if (o.x != null) Object.assign(box.style, { position: "absolute", left: o.x + "px", top: (o.y ?? 0) + "px" });
    const k = (W * (o.fill ?? 0.9)) / a.head_w, img = document.createElement("img");
    img.src = D.dir + "poses/" + pose + ".png";
    img.alt = "";
    Object.assign(img.style, { width: D.W * k + "px", height: D.H * k + "px", left: W / 2 - a.head[0] * k + "px", top: H * (o.top ?? 0.07) - a.head[1] * k + "px" });
    box.appendChild(img);
    p.appendChild(box);
    return box;
  };

  AR.cast = S;

  // ---------- the loot bar: an inventory of N slots the cast fills, one item per word ----------
  // It sits in any scene as a HUD: AR.loot.bar(parent, {n: 5, have: 2, items: [...]}) at a beat's start shows the slots
  // filled so far (keep `have` and `items` in FACTS so every beat and every size of one video agree), and
  // AR.loot.fill(tl, bar, t, {from}) flies the next item in on its word while the counter ticks.
  const pxOf = (el, root) => {
    let x = 0, y = 0, n = el;
    while (n && n !== root) { x += n.offsetLeft || 0; y += n.offsetTop || 0; n = n.offsetParent; }
    return [x, y];
  };
  const L = {
    /** the bar: a dark pixel panel with a label, N slots and a "k/N" counter, its top-left at (x, y) in parent px (or
     *  its top centre at x with center: true). o: {id, n (5), have (slots filled on the cut), items (the slot
     *  pictures in order: "src" or {src, pixel, text, bg}), label ("LOOT"; null for none), size (slot px, 76),
     *  count (true: the k/N counter), x, y, center, z} */
    bar(parent, o = {}) {
      const p = all(parent)[0], n = o.n ?? 5, size = o.size ?? 76, have = Math.max(0, Math.min(n, o.have ?? 0));
      const bar = div("loot-bar");
      if (o.id) bar.id = o.id;
      bar.style.setProperty("--k", size / 76);
      bar.setAttribute("data-layout-ignore", "");
      if (o.label !== null) { const lab = div("loot-label px"); lab.textContent = o.label ?? "LOOT"; bar.appendChild(lab); }
      const slots = [];
      for (let i = 0; i < n; i++) {
        const s = div("loot-slot"), it = (o.items || [])[i], d = typeof it === "string" ? { src: it } : it || {};
        if (o.id) s.id = `${o.id}-s${i + 1}`;
        if (d.bg) s.style.background = d.bg;
        let pic = null;
        if (d.src) {
          pic = document.createElement("img");
          pic.src = d.src;
          pic.alt = "";
          if (d.pixel) pic.className = "pixel";
        } else if (d.text) {
          pic = div("loot-text");
          pic.textContent = d.text;
        }
        if (pic) { pic.style.opacity = i < have ? 1 : 0; s.appendChild(pic); }
        s.appendChild(document.createElement("i"));
        bar.appendChild(s);
        slots.push(s);
      }
      let count = null;
      if (o.count !== false) {
        count = div("loot-count px");
        count.textContent = `${have}/${n}`;
        bar.appendChild(count);
      }
      p.appendChild(bar);
      if (o.z != null) bar.style.zIndex = o.z;
      const x = o.x ?? 0;
      Object.assign(bar.style, { left: (o.center ? x - bar.offsetWidth / 2 : x) + "px", top: (o.y ?? 0) + "px" });
      bar._loot = { n, have, k: have, slots, count };
      return bar;
    },
    /** slot i's (1-based; default the next one) gold ring blinks from t for dur s, then stays lit */
    call(tl, barSel, t, o = {}) {
      const bar = all(barSel)[0], B = bar && bar._loot;
      if (!B) return tl;
      const i = (o.slot ?? B.k + 1) - 1, ring = B.slots[i] && B.slots[i].querySelector("i");
      if (!ring) return tl;
      const dur = o.dur ?? 0.6, fps = 7, k = Math.max(1, Math.floor(dur * fps));
      for (let j = 0; j < k; j++) tl.set(ring, { opacity: j % 2 ? 0.15 : 1 }, t + j / fps);
      tl.set(ring, { opacity: o.stay === false ? 0 : 1 }, t + k / fps);
      return tl;
    },
    /** the next item lands in its slot at t: it flies there in an arc from o.from (an element of the scene, or [x, y]
     *  in the bar's parent px; without it the picture pops in big), the slot bumps and the counter ticks to k/N.
     *  o: {slot (1-based), from, dur (0.32), arc (px), scale (the size it starts at), complete (true: LOOT COMPLETE!
     *  when the last slot fills)} */
    fill(tl, barSel, t, o = {}) {
      const bar = all(barSel)[0], B = bar && bar._loot;
      if (!B) return tl;
      const i = (o.slot ?? B.k + 1) - 1, s = B.slots[i];
      if (!s) return tl;
      const pic = s.querySelector("img, .loot-text");
      const dur = o.dur ?? 0.32;
      if (pic) {
        if (o.from) {
          const root = bar.offsetParent || bar.parentElement, sp = pxOf(s, root);
          let fx, fy;
          if (Array.isArray(o.from)) [fx, fy] = o.from;
          else { const f = all(o.from)[0], fp = pxOf(f, root); fx = fp[0] + f.offsetWidth / 2; fy = fp[1] + f.offsetHeight / 2; }
          const dx = fx - (sp[0] + s.offsetWidth / 2), dy = fy - (sp[1] + s.offsetHeight / 2), up = o.arc ?? Math.max(60, Math.abs(dx) * 0.25);
          const t0 = Math.max(0, t - dur), s0 = o.scale ?? 2.2;
          tl.set(pic, { opacity: 1 }, t0);
          tl.fromTo(pic, { x: dx }, { x: 0, duration: t - t0, ease: "power1.in", immediateRender: false }, t0);
          tl.fromTo(pic, { y: dy }, { y: Math.min(dy, 0) - up, duration: (t - t0) * 0.45, ease: "power2.out", immediateRender: false }, t0);
          tl.to(pic, { y: 0, duration: (t - t0) * 0.55, ease: "power2.in" }, t0 + (t - t0) * 0.45);
          tl.fromTo(pic, { scale: s0, rotation: -12 }, { scale: 1, rotation: 0, duration: t - t0, ease: "power1.inOut", immediateRender: false }, t0);
        } else {
          tl.fromTo(pic, { opacity: 0, scale: o.scale ?? 2.4 }, { opacity: 1, scale: 1, duration: 0.2, ease: "back.out(2)" }, t - 0.06);
        }
      }
      tl.fromTo(s, { scale: 1 }, { scale: 1.22, duration: 0.07, ease: "power2.out", immediateRender: false }, t);
      tl.to(s, { scale: 1, duration: 0.2, ease: "back.out(3)" }, t + 0.07);
      const ring = s.querySelector("i");
      if (ring) { tl.set(ring, { opacity: 1 }, t); tl.to(ring, { opacity: 0, duration: 0.4 }, t + 0.35); }
      B.k = Math.max(B.k, i + 1);
      if (B.count) {
        tl.set(B.count, { textContent: `${B.k}/${B.n}` }, t);
        tl.fromTo(B.count, { scale: 1.35 }, { scale: 1, duration: 0.2, ease: "back.out(3)", immediateRender: false }, t);
      }
      if (B.k === B.n && o.complete !== false) L.complete(tl, bar, t + 0.18);
      return tl;
    },
    /** LOOT COMPLETE! pops over the bar and its border flashes gold. o: {text} */
    complete(tl, barSel, t, o = {}) {
      const bar = all(barSel)[0];
      if (!bar || !bar._loot) return tl;
      let done = bar.querySelector(".loot-done");
      if (!done) {
        done = div("loot-done px");
        done.textContent = o.text ?? "LOOT COMPLETE!";
        bar.appendChild(done);
        done.style.left = (bar.clientWidth - done.offsetWidth) / 2 + "px";
      }
      tl.fromTo(done, { opacity: 0, scale: 2.2, rotation: -6 }, { opacity: 1, scale: 1, rotation: -3, duration: 0.14, ease: "power4.in" }, t);
      tl.to(bar, { borderColor: "#f7c531", duration: 0.08 }, t + 0.14);
      tl.to(bar, { borderColor: "#ffffff", duration: 0.3 }, t + 0.5);
      return tl;
    },
  };
  AR.loot = L;
})();
