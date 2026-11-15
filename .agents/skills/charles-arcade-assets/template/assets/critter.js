/* critter.js: the code-drawn Claude critter (@opusjake's mascot), its props, states, actions and bubbles.
   Extends window.AR; load after arcade.js (and motion.js). Every timeline helper takes the timeline first and a
   scene time in seconds, and only adds tweens and sets, so any frame renders on its own.

   The critter is a 12 x 8 grid of art pixels (u px each, from the element's --u): body 8x6, eyes 1x1 at body
   columns 1 and 6, 2x2 side nubs on rows 2-3, four 1x2 legs, no outline, no shading, a soft ground ellipse.
     <div class="critter" id="b01-crit" style="left:200px; top:300px; --u:16px"></div>
     AR.critter("#b01-crit", { hold: "magnifier", wear: ["coat", "fedora"] });
     AR.crit.eyes(tl, "#b01-crit", 0.4, "happy");  AR.hop(tl, "#b01-crit", 0.4);
   AR.hop / AR.bob / AR.drop / AR.walk / AR.pose / AR.poses / AR.blink aimed at a .critter move its body and keep
   its ground shadow on the floor (the shadow shrinks under a hop). They are wrapped, not replaced: any target that
   is not a rendered critter goes to the untouched original with the same arguments (AR.<name>.__orig), so sprites
   and every other element get exactly the tweens they always did. AR.pop / AR.out / AR.stagger and camera moves
   take a critter whole, ground and props included. Props live in assets/cast/props (copy of cast/props).

   A second shape shares the box and every helper: the pal (AR.critter(el, {shape: "pal"}), or data-shape="pal"), a
   round bun on two feet with oval eyes, a mouth, blush and stubby mitts, the neutral host for topics that are not
   about Claude. Wearables drawn for the critter's grid are fitted onto its anatomy per slot (SHAPES.pal.fit). */
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
  const rnd = AR.rnd || ((seed) => () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  });
  const div = (cls) => { const d = document.createElement("div"); if (cls) d.className = cls; return d; };
  const svgEl = (tag, attrs) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    return e;
  };
  const gridSVG = (cls) => svgEl("svg", { viewBox: "0 0 12 8", preserveAspectRatio: "none", class: cls || "" });
  const rect = (parent, r, fill) => {
    const e = svgEl("rect", { x: r[0], y: r[1], width: r[2], height: r[3] });
    if (fill) e.style.fill = fill;
    parent.appendChild(e);
    return e;
  };
  const group = (parent, data, on) => {
    const g = svgEl("g");
    for (const k in data || {}) g.setAttribute("data-" + k, data[k]);
    if (on !== undefined) g.style.opacity = on ? 1 : 0;
    parent.appendChild(g);
    return g;
  };
  const mirror = (r) => [12 - r[0] - r[2], r[1], r[2], r[3]];
  const isCrit = (el) => !!(el && el._crit);
  const crits = (sel) => all(sel).map((el) => (el._crit ? el : el.classList && el.classList.contains("critter") ? (render(el, {}), el) : null)).filter(Boolean);

  // ---------- palette ----------
  const COLORS = {
    coral: "#D87454", teal: "#2E9E93", purple: "#8D6FD1", blue: "#4A80D8", green: "#5AA65A", gold: "#DDA63A",
    pink: "#E07A9C", grey: "#8F8A83", gray: "#8F8A83", black: "#34312D", white: "#EFE9E1", navy: "#3F4F94", red: "#D9473A",
  };

  // ---------- the grid ----------
  // one side of the body (the right; the left mirrors it): the arm, the bare hand cell a sleeve leaves showing,
  // the sleeve, a cuff line, and the grip point a held prop hangs from
  const SIDES = {
    rest:  { arm: [[9.75, 2, 2.25, 2]], sleeve: [[9.75, 2, 1.25, 2]], cuff: [10.75, 2, 0.25, 2], grip: [11, 3] },
    raise: { arm: [[9.75, 2, 2.25, 2], [11, 0, 1, 2]], sleeve: [[9.75, 2, 2.25, 2], [11, 1, 1, 1]], cuff: [11, 1, 1, 0.25], grip: [11.5, 0.5] },
    reach: { arm: [[9.75, 2, 2.25, 2], [12, 2, 1, 1]], sleeve: [[9.75, 2, 2.25, 2]], cuff: [11.75, 2, 0.25, 2], grip: [12.5, 2.5] },
    waveb: { arm: [[9.75, 2, 1.25, 2], [11, 1, 1, 2], [12, 0, 1, 2]], sleeve: [[9.75, 2, 1.25, 2], [11, 1, 1, 2], [12, 1, 1, 1]], cuff: [12, 1, 1, 0.25], grip: [12.5, 0.5] },
    low:   { arm: [[9.75, 3, 1.25, 2], [10, 4, 1, 1.5]], sleeve: [[9.75, 3, 1.25, 1.5]], cuff: [10, 4.25, 1, 0.25], grip: [10.5, 5] },
  };
  // arm states: [right side, left side]
  const ARMS = {
    down: ["rest", "rest"], up: ["raise", "raise"], point: ["reach", "rest"], "point-left": ["rest", "reach"],
    wave: ["raise", "rest"], wave2: ["waveb", "rest"], out: ["reach", "reach"], "hold-up": ["raise", "rest"],
    "hold-up-left": ["rest", "raise"], limp: ["low", "low"],
  };
  const eyePair = (l) => [...l, ...l.map((r) => [r[0] + 5, r[1], r[2], r[3]])];
  const EYES = {
    normal: eyePair([[3, 1, 1, 1]]),
    closed: eyePair([[3, 1.375, 1, 0.25]]),
    happy: eyePair([[3.25, 1.125, 0.5, 0.25], [3, 1.375, 0.25, 0.5], [3.75, 1.375, 0.25, 0.5]]),
    x: eyePair([[3, 1, 0.25, 0.25], [3.75, 1, 0.25, 0.25], [3.25, 1.25, 0.5, 0.5], [3, 1.75, 0.25, 0.25], [3.75, 1.75, 0.25, 0.25]]),
    wide: eyePair([[2.875, 0.75, 1.25, 1.5]]),
    "look-left": eyePair([[2.5, 1, 1, 1]]),
    "look-right": eyePair([[3.5, 1, 1, 1]]),
    "look-up": eyePair([[3, 0.5, 1, 1]]),
    "look-down": eyePair([[3, 1.5, 1, 1]]),
    sad: [[3, 1.5, 1, 0.75], [3.5, 1.25, 0.5, 0.25], [8, 1.5, 1, 0.75], [8, 1.25, 0.5, 0.25]],
    angry: [[3, 1.25, 1, 0.75], [3, 1, 0.5, 0.25], [8, 1.25, 1, 0.75], [8.5, 1, 0.5, 0.25]],
    squeeze: [[3, 1, 0.5, 0.25], [3.5, 1.25, 0.5, 0.25], [3.5, 1.5, 0.5, 0.25], [3, 1.75, 0.5, 0.25],
              [8.5, 1, 0.5, 0.25], [8, 1.25, 0.5, 0.25], [8, 1.5, 0.5, 0.25], [8.5, 1.75, 0.5, 0.25]],
  };
  const LEGS = {
    stand: [[2, 5.75, 1, 2.25], [4, 5.75, 1, 2.25], [7, 5.75, 1, 2.25], [9, 5.75, 1, 2.25]],
    a: [[2, 5.75, 1, 1.5], [4, 5.75, 1, 2.25], [7, 5.75, 1, 1.5], [9, 5.75, 1, 2.25]],
    b: [[2, 5.75, 1, 2.25], [4, 5.75, 1, 1.5], [7, 5.75, 1, 2.25], [9, 5.75, 1, 1.5]],
    tuck: [[2, 5.75, 1, 1.25], [4, 5.75, 1, 1.25], [7, 5.75, 1, 1.25], [9, 5.75, 1, 1.25]],
  };

  // ---------- the pal (shape: "pal"): the neutral host for topics that are not about Claude ----------
  // Same 12 x 8 box, feet on its bottom edge, so every helper, prop and wearable works on it. A round bun (x 1.5-10.5,
  // y 0-7, rows 0.5 tall: [y, x0, x1]) on two little feet; oval eyes with a glint low on the face, a small mouth that
  // changes with the eyes, blush, a soft shine and a shaded rim; stubby arms with round mitts instead of side nubs.
  const PAL_ROWS = [[0, 4, 8], [0.5, 3, 9], [1, 2.5, 9.5], [1.5, 2, 10], [2, 1.5, 10.5], [2.5, 1.5, 10.5], [3, 1.5, 10.5],
    [3.5, 1.5, 10.5], [4, 1.5, 10.5], [4.5, 1.5, 10.5], [5, 2, 10], [5.5, 2.5, 9.5], [6, 3, 9], [6.5, 4, 8]];
  const PAL_SHINE = [[3.5, 0.75, 1.25, 0.5], [3, 1.25, 0.5, 0.75]];
  const PAL_RIM = [[1.5, 4.5, 0.5, 0.5], [10, 4.5, 0.5, 0.5], [2, 5, 0.5, 0.5], [9.5, 5, 0.5, 0.5], [2.5, 5.5, 0.5, 0.5],
    [9, 5.5, 0.5, 0.5], [3, 6, 1, 0.5], [8, 6, 1, 0.5], [4, 6.5, 4, 0.5]];
  const PAL_BLUSH = [[2.25, 3.25, 1, 0.5], [8.75, 3.25, 1, 0.5]];
  const mitt = (x, y, w = 1, h = 1) => [[x, y + 0.25, w, h - 0.5], [x + 0.25, y, w - 0.5, h]];
  // the right side (the left mirrors it): arm segments, the mitt, the sleeve a coat draws over the arm, its cuff, the grip
  const PSIDES = {
    rest:  { arm: [], mitt: [10, 4.375, 1, 1], sleeve: [], cuff: null, grip: [10.55, 4.95] },
    raise: { arm: [[9.75, 2.5, 1.25, 1], [10.5, 1.5, 1, 1.25]], mitt: [10.75, 0.5, 1, 1],
             sleeve: [[9.75, 2.5, 1.25, 1], [10.5, 1.625, 1, 1.125]], cuff: [10.625, 1.5, 1.125, 0.25], grip: [11.25, 1] },
    reach: { arm: [[9.75, 3.125, 1.75, 1]], mitt: [11.25, 3.0, 1.125, 1.25], sleeve: [[9.75, 3.125, 1.5, 1]], cuff: [11.125, 3.125, 0.25, 1], grip: [11.8, 3.6] },
    waveb: { arm: [[9.75, 2.5, 1.25, 1], [10.75, 1.75, 1, 1.25]], mitt: [11.5, 0.875, 1, 1],
             sleeve: [[9.75, 2.5, 1.25, 1], [10.75, 1.875, 0.875, 1.125]], cuff: [11.5, 1.75, 0.5, 0.375], grip: [12, 1.375] },
    low:   { arm: [], mitt: [9.625, 5.5, 1, 1], sleeve: [], cuff: null, grip: [10.15, 6] },
  };
  const foot = (x, y) => [[x, y, 2, 1], [x + 0.25, y + 1, 1.5, 0.25]];
  const PLEGS = {
    stand: [...foot(3.25, 6.75), ...foot(6.75, 6.75)],
    a: [...foot(3, 6.25), ...foot(6.75, 6.75)],
    b: [...foot(3.25, 6.75), ...foot(7, 6.25)],
    tuck: [...foot(3.5, 6.25), ...foot(6.5, 6.25)],
  };
  // eyes: [x, y, w, h, colour?] (no colour: the eye colour). Each state carries its mouth (and brows when it has them)
  const pe = (fn) => [...fn(3.5, "l"), ...fn(7.5, "r")];
  const oval = (x, y, w = 1, h = 1.5) => [[x, y + 0.25, w, h - 0.5], [x + 0.25, y, w - 0.5, h]];
  const GL = "#FFFFFF";
  const MOUTH = {
    smile: [[5.5, 3.5, 0.25, 0.25], [5.75, 3.75, 0.5, 0.25], [6.25, 3.5, 0.25, 0.25]],
    grin: [[5.25, 3.5, 1.5, 0.25], [5.5, 3.75, 1, 0.25], [5.75, 4, 0.5, 0.125]],
    o: [[5.75, 3.5, 0.5, 0.75], [5.625, 3.625, 0.75, 0.5]],
    frown: [[5.5, 3.75, 0.25, 0.25], [5.75, 3.5, 0.5, 0.25], [6.25, 3.75, 0.25, 0.25]],
    flat: [[5.5, 3.625, 1, 0.25]],
  };
  const PEYES = {
    normal: [...pe((x) => [...oval(x, 1.75), [x + 0.25, 2, 0.25, 0.25, GL]]), ...MOUTH.smile],
    closed: [...pe((x) => [[x, 2.5, 1, 0.25]]), ...MOUTH.smile],
    happy: [...pe((x) => [[x, 2.5, 0.25, 0.5], [x + 0.25, 2.25, 0.5, 0.25], [x + 0.75, 2.5, 0.25, 0.5]]), ...MOUTH.grin],
    x: [...pe((x) => [[x, 2, 0.25, 0.25], [x + 0.75, 2, 0.25, 0.25], [x + 0.25, 2.25, 0.5, 0.5], [x, 2.75, 0.25, 0.25], [x + 0.75, 2.75, 0.25, 0.25]]), ...MOUTH.o],
    wide: [...pe((x) => [...oval(x - 0.125, 1.5, 1.25, 2), [x + 0.125, 1.75, 0.375, 0.375, GL]]), ...MOUTH.o],
    "look-left": [...pe((x) => [...oval(x - 0.375, 1.75), [x - 0.125, 2, 0.25, 0.25, GL]]), ...MOUTH.smile],
    "look-right": [...pe((x) => [...oval(x + 0.375, 1.75), [x + 0.625, 2, 0.25, 0.25, GL]]), ...MOUTH.smile],
    "look-up": [...pe((x) => [...oval(x, 1.375), [x + 0.25, 1.625, 0.25, 0.25, GL]]), ...MOUTH.smile],
    "look-down": [...pe((x) => [...oval(x, 2.125), [x + 0.25, 2.375, 0.25, 0.25, GL]]), ...MOUTH.smile],
    sad: [...pe((x, s) => [[x, 2.25, 1, 0.75], [x + 0.25, 3, 0.5, 0.25],
      ...(s === "l" ? [[x + 0.5, 1.5, 0.5, 0.25], [x, 1.75, 0.5, 0.25]] : [[x, 1.5, 0.5, 0.25], [x + 0.5, 1.75, 0.5, 0.25]])]), ...MOUTH.frown],
    angry: [...pe((x, s) => [[x, 2.25, 1, 0.75], [x + 0.25, 3, 0.5, 0.25],
      ...(s === "l" ? [[x, 1.5, 0.5, 0.25], [x + 0.5, 1.75, 0.5, 0.25]] : [[x + 0.5, 1.5, 0.5, 0.25], [x, 1.75, 0.5, 0.25]])]), ...MOUTH.flat],
    squeeze: [...pe((x, s) => (s === "l"
      ? [[x, 2, 0.5, 0.25], [x + 0.5, 2.25, 0.5, 0.25], [x + 0.5, 2.5, 0.5, 0.25], [x, 2.75, 0.5, 0.25]]
      : [[x + 0.5, 2, 0.5, 0.25], [x, 2.25, 0.5, 0.25], [x, 2.5, 0.5, 0.25], [x + 0.5, 2.75, 0.5, 0.25]])), ...MOUTH.flat],
  };
  // where the shape's anatomy is, and how a wearable drawn for the critter's grid is fitted onto it, per slot:
  // x' = cx + sx (x - cx) + dx, y' = cy + sy (y - cy) + dy; body wear is also clipped to the torso (y >= clip)
  const SHAPES = {
    critter: { name: "critter", SIDES, EYES, LEGS, eye: [6, 1.5], mouth: [6, 2.3], front: 3.2, sweat: [10.4, 0.2], fit: {} },
    pal: {
      name: "pal", SIDES: PSIDES, EYES: PEYES, LEGS: PLEGS, rows: PAL_ROWS, eye: [6, 2.5], mouth: [6, 3.7], front: 4.4, sweat: [9.6, 0.5],
      fit: {
        head: { sx: 0.9, dy: 0.5 }, ears: { dy: 1.25 }, face: { sx: 0.8, sy: 1.4, cx: 6, cy: 1.5, dy: 1 },
        body: { dy: 2.1, clip: 4.1 }, neck: { dy: 2.1 }, back: { dy: 2 },
      },
    },
  };
  const fitOf = (G, slot) => Object.assign({ sx: 1, sy: 1, cx: 6, cy: 0, dx: 0, dy: 0 }, (G.fit || {})[slot] || {});
  const fitPt = (G, slot, p) => { const f = fitOf(G, slot); return [f.cx + f.sx * (p[0] - f.cx) + f.dx, f.cy + f.sy * (p[1] - f.cy) + f.dy]; };
  const fitSVG = (f) => `translate(${f.cx + f.dx} ${f.cy + f.dy}) scale(${f.sx} ${f.sy}) translate(${-f.cx} ${-f.cy})`;
  // a stair-stepped outline of [y, x0, x1] rows (0.5 tall) as one path: no seams between rows at any size
  const rowsPath = (rows, h = 0.5) => {
    const pts = [];
    rows.forEach(([y, , x1]) => pts.push([x1, y], [x1, y + h]));
    rows.slice().reverse().forEach(([y, x0]) => pts.push([x0, y + h], [x0, y]));
    return "M" + pts.map((p) => p.join(" ")).join(" L") + " Z";
  };
  // the torso below y0 as a CSS polygon in % of the 12 x 8 box (clips body wear to the round body)
  const torsoClip = (rows, y0, h = 0.5) => {
    const rs = rows.filter(([y]) => y + h > y0).map(([y, x0, x1]) => [Math.max(y, y0), x0, x1, y + h]);
    const P = (x, y) => `${(x / 12 * 100).toFixed(3)}% ${(y / 8 * 100).toFixed(3)}%`, pts = [];
    rs.forEach(([y, , x1, y1]) => pts.push(P(x1, y), P(x1, y1)));
    rs.slice().reverse().forEach(([y, x0, , y1]) => pts.push(P(x0, y1), P(x0, y)));
    return `polygon(${pts.join(", ")})`;
  };

  // ---------- code-drawn wearables (fit the grid exactly, recolour, stay crisp in a close-up) ----------
  // parts get an outline, details do not; sleeves follow the arm state; colours are keys into `colors`
  const CODE = {
    coat: {
      slot: "body", sleeves: true,
      colors: { main: "#C79A5B", dark: "#9C7440", light: "#DDB679", line: "#5E4325", belt: "#6E4E2B", gold: "#E6B94A", shirt: "#F2EEE6", tie: "#3A2C22" },
      parts: [[2, 2, 8, 4, "main"], [2, 0.875, 1.125, 1.5, "main"], [8.875, 0.875, 1.125, 1.5, "main"]],
      details: [
        [2.25, 1, 0.25, 1.25, "light"], [9.5, 1, 0.25, 1.25, "dark"],
        [5, 2, 2, 0.5, "shirt"], [5.25, 2.5, 1.5, 0.5, "shirt"], [5.5, 3, 1, 0.5, "shirt"], [5.875, 2.125, 0.25, 1.375, "tie"],
        [4.75, 2, 0.25, 0.5, "dark"], [5, 2.5, 0.25, 0.5, "dark"], [5.25, 3, 0.25, 0.5, "dark"],
        [7, 2, 0.25, 0.5, "dark"], [6.75, 2.5, 0.25, 0.5, "dark"], [6.5, 3, 0.25, 0.5, "dark"],
        [2, 4.25, 8, 0.5, "belt"], [5.625, 4.125, 0.75, 0.75, "gold"], [5.875, 4.375, 0.25, 0.25, "belt"],
        [4.125, 3.375, 0.25, 0.25, "line"], [7.625, 3.375, 0.25, 0.25, "line"],
        [5.875, 4.75, 0.25, 1.25, "dark"], [2.75, 5.125, 1.25, 0.25, "dark"], [8, 5.125, 1.25, 0.25, "dark"],
        [2.25, 2.25, 0.25, 1.75, "light"],
      ],
    },
    suit: {
      slot: "body", sleeves: true,
      colors: { main: "#24222B", dark: "#121116", light: "#3D3A47", line: "#0B0A0E", shirt: "#F2EEE6", gold: "#E8B526", goldDark: "#B8861A" },
      parts: [[2, 2, 8, 4, "main"]],
      details: [
        [5, 2, 2, 0.5, "shirt"], [5.25, 2.5, 1.5, 0.5, "shirt"], [5.5, 3, 1, 0.5, "shirt"],
        [5.75, 2.125, 0.5, 0.5, "gold"], [5.875, 2.625, 0.25, 1.125, "gold"], [5.75, 3.5, 0.5, 0.25, "goldDark"],
        [4.75, 2, 0.25, 0.5, "light"], [5, 2.5, 0.25, 0.5, "light"], [5.25, 3, 0.25, 0.5, "light"],
        [7, 2, 0.25, 0.5, "light"], [6.75, 2.5, 0.25, 0.5, "light"], [6.5, 3, 0.25, 0.5, "light"],
        [7.5, 2.875, 0.625, 0.25, "gold"], [5.875, 4.25, 0.25, 0.25, "light"], [5.875, 5, 0.25, 0.25, "light"],
        [2.25, 2.25, 0.25, 3.5, "light"],
      ],
    },
    vest: {
      slot: "body", sleeves: false,
      colors: { main: "#8D9096", dark: "#6C6F75", light: "#A9ACB2", line: "#4B4D52", skin: "var(--crit-color)" },
      parts: [[2, 2.25, 8, 3.75, "main"]],
      details: [
        [5.25, 2.25, 1.5, 0.5, "skin"], [5.5, 2.75, 1, 0.5, "skin"], [5.75, 3.25, 0.5, 0.25, "skin"],
        [5.875, 3.75, 0.25, 0.25, "dark"], [5.875, 4.5, 0.25, 0.25, "dark"], [5.875, 5.25, 0.25, 0.25, "dark"],
        [2.75, 4.5, 1.25, 0.25, "dark"], [8, 4.5, 1.25, 0.25, "dark"], [2.25, 2.5, 0.25, 3.25, "light"],
      ],
    },
    shirt: {
      slot: "body", sleeves: true,
      colors: { main: "#BCD3EF", dark: "#8FAFD8", light: "#D6E4F6", line: "#6E8DB8", stripe: "#A9C3E6", strap: "#C9302C", gold: "#E2B84F", collar: "#FFFFFF", tie: "#E9B640", dot: "#8A5A1E" },
      parts: [[2, 2, 8, 3.25, "main"]],
      details: [
        [2.75, 2, 0.125, 3.25, "stripe"], [4.75, 2, 0.125, 3.25, "stripe"], [7.125, 2, 0.125, 3.25, "stripe"], [9.125, 2, 0.125, 3.25, "stripe"],
        [3.5, 2, 0.5, 3.25, "strap"], [8, 2, 0.5, 3.25, "strap"], [3.5, 5, 0.5, 0.25, "gold"], [8, 5, 0.5, 0.25, "gold"],
        [4.875, 2, 0.875, 0.375, "collar"], [6.25, 2, 0.875, 0.375, "collar"],
        [5.75, 2, 0.5, 0.375, "tie"], [5.625, 2.375, 0.75, 2.25, "tie"], [5.75, 4.625, 0.5, 0.25, "tie"],
        [5.875, 2.75, 0.25, 0.25, "dot"], [6.125, 3.5, 0.125, 0.125, "dot"], [5.75, 4, 0.25, 0.25, "dot"],
      ],
    },
    sunglasses: {
      slot: "face", colors: { frame: "#161512", glint: "#FFFFFF" },
      parts: [],
      details: [
        [2.25, 0.75, 7.5, 0.375, "frame"], [2.5, 1.125, 2, 0.5, "frame"], [2.75, 1.625, 1.5, 0.25, "frame"],
        [7.5, 1.125, 2, 0.5, "frame"], [7.75, 1.625, 1.5, 0.25, "frame"], [1.75, 0.75, 0.5, 0.25, "frame"], [9.75, 0.75, 0.5, 0.25, "frame"],
        [2.75, 1.125, 0.25, 0.25, "glint"], [3, 1.375, 0.25, 0.25, "glint"], [7.75, 1.125, 0.25, 0.25, "glint"], [8, 1.375, 0.25, 0.25, "glint"],
      ],
    },
    goldshades: {
      slot: "face", colors: { gold: "#E3B341", goldDark: "#A97A22", lens: "#161512", glint: "#FFFFFF" },
      parts: [],
      details: [
        [2.125, 0.625, 2.75, 1.5, "goldDark"], [7.125, 0.625, 2.75, 1.5, "goldDark"], [2.375, 2.0, 2.25, 0.375, "goldDark"], [7.375, 2.0, 2.25, 0.375, "goldDark"],
        [2.25, 0.75, 2.5, 1.25, "gold"], [7.25, 0.75, 2.5, 1.25, "gold"], [2.5, 2.0, 2, 0.25, "gold"], [7.5, 2.0, 2, 0.25, "gold"],
        [2.5, 1.0, 2, 0.875, "lens"], [2.75, 1.875, 1.5, 0.25, "lens"], [7.5, 1.0, 2, 0.875, "lens"], [7.75, 1.875, 1.5, 0.25, "lens"],
        [4.875, 0.875, 2.25, 0.25, "gold"], [4.875, 1.25, 2.25, 0.125, "goldDark"], [1.625, 0.75, 0.5, 0.25, "gold"], [9.875, 0.75, 0.5, 0.25, "gold"],
        [2.75, 1.125, 0.375, 0.25, "glint"], [7.75, 1.125, 0.375, 0.25, "glint"],
      ],
    },
    glasses: {
      slot: "face", colors: { frame: "#3B2F2A", lens: "rgba(255,255,255,0.28)" },
      parts: [],
      details: [
        [2.625, 0.75, 1.75, 1.5, "lens"], [7.625, 0.75, 1.75, 1.5, "lens"],
        [2.5, 0.625, 2, 0.25, "frame"], [2.5, 2.125, 2, 0.25, "frame"], [2.5, 0.625, 0.25, 1.75, "frame"], [4.25, 0.625, 0.25, 1.75, "frame"],
        [7.5, 0.625, 2, 0.25, "frame"], [7.5, 2.125, 2, 0.25, "frame"], [7.5, 0.625, 0.25, 1.75, "frame"], [9.25, 0.625, 0.25, 1.75, "frame"],
        [4.5, 1.125, 3, 0.25, "frame"], [1.875, 0.75, 0.625, 0.25, "frame"], [9.5, 0.75, 0.625, 0.25, "frame"],
      ],
    },
    goggles: {
      slot: "head", colors: { strap: "#6B4A2B", brass: "#C9963A", brassDark: "#8A6224", lens: "#4FB6B0", glint: "#E6FFFB", line: "#3A2814" },
      parts: [[1.75, -0.125, 8.5, 0.5, "strap"], [2.5, -0.875, 2, 1.75, "brass"], [7.5, -0.875, 2, 1.75, "brass"]],
      details: [
        [2.875, -0.5, 1.25, 1, "lens"], [7.875, -0.5, 1.25, 1, "lens"], [3, -0.375, 0.375, 0.25, "glint"], [8, -0.375, 0.375, 0.25, "glint"],
        [2.5, 0.625, 2, 0.25, "brassDark"], [7.5, 0.625, 2, 0.25, "brassDark"], [4.5, 0, 3, 0.25, "brassDark"],
      ],
    },
    visor: {
      slot: "head", colors: { band: "#3E9A55", brim: "rgba(70, 190, 105, 0.72)", dark: "#2C6E3C", line: "#1F4A29" },
      parts: [[1.75, -0.375, 8.5, 0.625, "band"]],
      details: [[1.5, 0.25, 9, 0.5, "brim"], [1.75, 0.25, 8.5, 0.125, "dark"], [2, -0.25, 8, 0.125, "dark"]],
    },
    headset: {
      slot: "ears", colors: { band: "#25232B", cup: "#2F2D36", light: "#4A4756", r: "#FF5A5A", o: "#FFB13B", y: "#FFE45C", g: "#5BE07A", b: "#4FA8FF", v: "#A66BFF", mic: "#25232B" },
      parts: [[2, -1.25, 8, 0.625, "band"], [1.5, -0.75, 0.75, 1, "band"], [9.75, -0.75, 0.75, 1, "band"],
              [1.25, 0.25, 1.25, 2, "cup"], [9.5, 0.25, 1.25, 2, "cup"]],
      details: [
        [2.5, -1.25, 1.25, 0.25, "r"], [3.75, -1.25, 1.25, 0.25, "o"], [5, -1.25, 1, 0.25, "y"], [6, -1.25, 1, 0.25, "g"], [7, -1.25, 1.25, 0.25, "b"], [8.25, -1.25, 1.25, 0.25, "v"],
        [1.25, 0.5, 0.25, 1.5, "b"], [10.5, 0.5, 0.25, 1.5, "v"], [1.75, 0.5, 0.5, 0.25, "light"], [9.75, 0.5, 0.5, 0.25, "light"],
        [1.75, 2.25, 0.25, 0.75, "mic"], [2, 2.75, 1.25, 0.25, "mic"], [3.25, 2.625, 0.5, 0.5, "mic"],
      ],
    },
    earpiece: {
      slot: "ears", colors: { gray: "#8C8A92", dark: "#55535A", line: "#2A292E" },
      parts: [[1.375, 0.875, 0.75, 1, "gray"]],
      details: [[1.625, 1.875, 0.25, 0.75, "dark"], [1.875, 2.5, 0.25, 0.75, "dark"], [1.5, 1, 0.25, 0.25, "dark"]],
    },
    // hats are drawn wide and flat to sit on the square head like Jake's; the brim stops just above the eyes
    fedora: {
      slot: "head", colors: { main: "#8B5A3C", dark: "#5E3B26", light: "#A87452", band: "#2B211C", line: "#2E1D12" },
      parts: [[0.75, 0.25, 10.5, 0.75, "main"], [3, -2.125, 6, 2.375, "main"], [3.5, -2.5, 5, 0.5, "main"]],
      details: [[3, -0.5, 6, 0.625, "band"], [3.25, -1.875, 0.5, 1.25, "light"], [5.5, -2.5, 1, 0.5, "dark"],
                [0.75, 0.25, 10.5, 0.25, "light"], [0.75, 0.75, 10.5, 0.25, "dark"], [8.5, -1.875, 0.5, 1.25, "dark"]],
    },
    hardhat: {
      slot: "head", colors: { main: "#F2C12E", dark: "#C8951B", light: "#FFE07A", line: "#5E430D", lamp: "#FFF4C2", lampRim: "#9A7A2A" },
      parts: [[2.25, -1.75, 7.5, 2, "main"], [3.25, -2.375, 5.5, 0.75, "main"], [1.25, 0.25, 9.5, 0.75, "main"]],
      details: [[5.5, -2.375, 1, 2.625, "light"], [3, -1.5, 0.5, 1.25, "light"], [1.25, 0.75, 9.5, 0.25, "dark"],
                [8.75, -1.5, 0.5, 1.5, "dark"], [5.25, -1.375, 1.5, 1.125, "lampRim"], [5.5, -1.125, 1, 0.625, "lamp"]],
    },
    "hardhat-white": {
      slot: "head", colors: { main: "#F4F2EE", dark: "#C9C6BF", light: "#FFFFFF", line: "#5F5B55" },
      parts: [[2.25, -1.75, 7.5, 2, "main"], [3.25, -2.375, 5.5, 0.75, "main"], [1.25, 0.25, 9.5, 0.75, "main"]],
      details: [[5.5, -2.375, 1, 2.625, "light"], [1.25, 0.75, 9.5, 0.25, "dark"], [8.75, -1.5, 0.5, 1.5, "dark"], [6.5, -2.125, 0.25, 2.375, "dark"]],
    },
    cap: {
      slot: "head", colors: { main: "#2E3F7A", dark: "#1F2B57", light: "#4A5FA3", line: "#121935", badge: "#E3B341" },
      parts: [[2.25, -1.5, 7.5, 1.75, "main"], [3, -2, 6, 0.625, "main"], [8.5, -0.125, 3.5, 0.625, "main"]],
      details: [[5.75, -2.25, 0.5, 0.375, "dark"], [5.875, -1.875, 0.25, 2.125, "dark"], [3, -1.25, 0.5, 1, "light"],
                [8.5, 0.25, 3.5, 0.25, "dark"], [6.75, -1.125, 1.125, 0.75, "badge"], [2.25, 0, 7.5, 0.25, "dark"]],
    },
    beret: {
      slot: "head", colors: { main: "#2B2A30", light: "#45434D", dark: "#18171C", line: "#0D0C10" },
      parts: [[1.75, -1, 9, 1.375, "main"], [2.5, -1.625, 7.5, 0.75, "main"], [5.75, -2.125, 0.625, 0.625, "main"]],
      details: [[3, -1.375, 1.75, 0.375, "light"], [2.25, 0.125, 8, 0.25, "dark"], [9.5, -0.75, 0.75, 0.75, "dark"]],
    },
    crown: {
      slot: "head", colors: { main: "#EDB937", dark: "#B98617", light: "#FFE27A", line: "#5E3F08", ruby: "#D9473A", sapphire: "#4A80D8" },
      parts: [[2.75, -1, 6.5, 1.375, "main"], [2.75, -2.25, 1, 1.5, "main"], [5.5, -2.75, 1, 2, "main"], [8.25, -2.25, 1, 1.5, "main"],
              [4.125, -1.75, 0.75, 1, "main"], [7.125, -1.75, 0.75, 1, "main"]],
      details: [[5.625, -0.75, 0.75, 0.75, "ruby"], [3.5, -0.625, 0.5, 0.5, "sapphire"], [8, -0.625, 0.5, 0.5, "sapphire"],
                [2.75, 0.125, 6.5, 0.25, "dark"], [3, -0.75, 0.25, 0.75, "light"], [2.875, -2.25, 0.5, 0.25, "light"],
                [5.625, -2.75, 0.5, 0.25, "light"], [8.375, -2.25, 0.5, 0.25, "light"]],
    },
    // the referee's striped shirt: black and white stripes, a black V collar, black cuffs
    refshirt: {
      slot: "body", sleeves: true,
      colors: { main: "#F7F5F0", dark: "#1C1B1F", light: "#FFFFFF", line: "#1C1B1F", stripe: "#1C1B1F", collar: "#1C1B1F" },
      parts: [[2, 2, 8, 4, "main"]],
      details: [
        [2.25, 2, 0.5, 4, "stripe"], [3.25, 2, 0.5, 4, "stripe"], [4.25, 2, 0.5, 4, "stripe"], [5.25, 2, 0.5, 4, "stripe"],
        [6.25, 2, 0.5, 4, "stripe"], [7.25, 2, 0.5, 4, "stripe"], [8.25, 2, 0.5, 4, "stripe"], [9.25, 2, 0.5, 4, "stripe"],
        [4.5, 2, 3, 0.375, "collar"], [5, 2.375, 2, 0.375, "collar"], [5.5, 2.75, 1, 0.375, "collar"], [5.75, 2.375, 0.5, 0.375, "light"],
      ],
    },
    // two little horns (a monster, a villain, "the enemy" played by a pal or a critter)
    horns: {
      slot: "head", colors: { main: "#F3E9D2", dark: "#C9B48F", line: "#3A2E22" },
      parts: [[2.75, -0.75, 1.25, 1, "main"], [3, -1.375, 0.75, 0.75, "main"], [3.125, -1.875, 0.5, 0.625, "main"],
              [8, -0.75, 1.25, 1, "main"], [8.25, -1.375, 0.75, 0.75, "main"], [8.375, -1.875, 0.5, 0.625, "main"]],
      details: [[3.5, -0.75, 0.5, 1, "dark"], [3.5, -1.375, 0.25, 0.75, "dark"], [8.75, -0.75, 0.5, 1, "dark"], [8.75, -1.375, 0.25, 0.75, "dark"]],
    },
  };

  /* PROPS:start (generated from cast/props/props.json; see that file for the fields) */
  const PROPS = {"magnifier":{"file":"magnifier.png","size":[522,522],"slot":"hand","w":4.0,"grip":[0.13,0.86],"tip":[0.66,0.31]},"binoculars":{"file":"binoculars.png","size":[522,381],"slot":"hand","w":3.6,"grip":[0.25,0.92]},"clipboard":{"file":"clipboard.png","size":[382,522],"slot":"hand","w":3.6,"grip":[0.15,0.8],"flip":false},"flashlight":{"file":"flashlight.png","size":[551,239],"slot":"hand","w":5.0,"grip":[0.22,0.55],"tip":[1.0,0.5]},"newspaper":{"file":"newspaper.png","size":[522,453],"slot":"hand","w":4.2,"grip":[0.15,0.88],"flip":false},"briefcase":{"file":"briefcase.png","size":[551,494],"slot":"hand","w":3.8,"grip":[0.5,0.05]},"phone":{"file":"phone.png","size":[183,578],"slot":"hand","w":1.9,"grip":[0.45,0.5],"rot":-12},"hammer":{"file":"hammer.png","size":[394,763],"slot":"hand","w":2.6,"grip":[0.52,0.8]},"wrench":{"file":"wrench.png","size":[254,775],"slot":"hand","w":1.6,"grip":[0.5,0.78],"rot":10},"shovel":{"file":"shovel.png","size":[254,800],"slot":"hand","w":1.9,"grip":[0.5,0.3],"tip":[0.5,1.0]},"blueprint":{"file":"blueprint.png","size":[584,425],"slot":"hand","w":4.4,"grip":[0.12,0.85],"flip":false},"pencil":{"file":"pencil.png","size":[130,723],"slot":"hand","w":1.6,"grip":[0.5,0.62],"tip":[0.5,0.0]},"roller":{"file":"roller.png","size":[522,584],"slot":"hand","w":3.8,"grip":[0.62,0.92]},"moneybag":{"file":"moneybag.png","size":[421,525],"slot":"hand","w":3.4,"grip":[0.35,0.7]},"coin":{"file":"coin.png","size":[372,354],"slot":"hand","w":2.0,"grip":[0.3,0.8]},"bill":{"file":"bill.png","size":[549,270],"slot":"hand","w":4.2,"grip":[0.1,0.75],"flip":false},"calculator":{"file":"calculator.png","size":[338,457],"slot":"hand","w":2.8,"grip":[0.2,0.85],"flip":false},"chartboard":{"file":"chartboard.png","size":[464,338],"slot":"hand","w":4.6,"grip":[0.12,0.88],"flip":false,"rot":4},"stopwatch":{"file":"stopwatch.png","size":[390,448],"slot":"hand","w":3.0,"grip":[0.25,0.9]},"scales":{"file":"scales.png","size":[474,423],"slot":"hand","w":3.8,"grip":[0.5,0.95]},"folder":{"file":"folder.png","size":[509,508],"slot":"hand","w":3.2,"grip":[0.15,0.85],"flip":false},"chartscroll":{"file":"chartscroll.png","size":[467,557],"slot":"hand","w":3.4,"grip":[0.15,0.95],"flip":false},"filebox":{"file":"filebox.png","size":[534,491],"slot":"hand","w":4.0,"grip":[0.2,0.6]},"scroll":{"file":"scroll.png","size":[525,525],"slot":"hand","w":3.6,"grip":[0.2,0.85],"flip":false},"quill":{"file":"quill.png","size":[508,559],"slot":"hand","w":3.2,"grip":[0.38,0.62],"tip":[0.06,0.97]},"pen":{"file":"pen.png","size":[559,559],"slot":"hand","w":3.2,"grip":[0.42,0.58],"tip":[0.07,0.96]},"labelgun":{"file":"labelgun.png","size":[542,525],"slot":"hand","w":3.4,"grip":[0.62,0.9]},"laptop":{"file":"laptop.png","size":[559,474],"slot":"hand","w":4.2,"grip":[0.2,0.95],"flip":false},"whistle":{"file":"whistle.png","size":[479,451],"slot":"hand","w":2.6,"grip":[0.3,0.4],"tip":[0.04,0.53],"out":[0.8,0.3]},"megaphone":{"file":"megaphone.png","size":[464,394],"slot":"hand","w":3.8,"grip":[0.32,0.8]},"trophy":{"file":"trophy.png","size":[464,479],"slot":"hand","w":3.2,"grip":[0.5,0.95]},"target":{"file":"target.png","size":[451,452],"slot":"hand","w":3.2,"grip":[0.2,0.9]},"rocket":{"file":"rocket.png","size":[437,452],"slot":"hand","w":3.2,"grip":[0.38,0.62]},"bell":{"file":"bell.png","size":[436,366],"slot":"hand","w":3.0,"grip":[0.4,0.95]},"brush":{"file":"brush.png","size":[409,397],"slot":"hand","w":3.0,"grip":[0.62,0.38],"tip":[0.03,0.97]},"wateringcan":{"file":"wateringcan.png","size":[467,310],"slot":"hand","w":4.0,"grip":[0.1,0.35],"tip":[0.99,0.12]},"sapling":{"file":"sapling.png","size":[257,429],"slot":"hand","w":2.2,"grip":[0.4,0.9]},"shoppingbag":{"file":"shoppingbag.png","size":[339,429],"slot":"hand","w":2.8,"grip":[0.5,0.05]},"map":{"file":"map.png","size":[464,376],"slot":"hand","w":4.0,"grip":[0.12,0.8],"flip":false},"pushpin":{"file":"pushpin.png","size":[228,401],"slot":"hand","w":1.1,"grip":[0.5,0.45],"tip":[0.5,1.0]},"bugnet":{"file":"bugnet.png","size":[373,610],"slot":"hand","w":3.6,"grip":[0.38,0.92],"tip":[0.35,0.25]},"shield":{"file":"shield.png","size":[475,542],"slot":"hand","w":3.0,"grip":[0.35,0.6]},"sword":{"file":"sword.png","size":[220,576],"slot":"hand","w":1.5,"grip":[0.5,0.86]},"clock":{"file":"clock.png","size":[474,576],"slot":"hand","w":3.2,"grip":[0.3,0.9]},"mug":{"file":"mug.png","size":[474,474],"slot":"hand","w":2.6,"grip":[0.85,0.5]},"marker":{"file":"marker.png","size":[474,475],"slot":"hand","w":2.8,"grip":[0.62,0.38],"tip":[0.03,0.97]},"headphones":{"file":"headphones.png","size":[508,559],"slot":"hand","w":4.4,"grip":[0.5,0.1]},"hat-fedora":{"file":"hat-fedora.png","size":[550,313],"slot":"hand","w":4.4,"grip":[0.5,0.9]},"hat-hard":{"file":"hat-hard.png","size":[559,495],"slot":"hand","w":4.4,"grip":[0.5,0.9]},"hat-hard-white":{"file":"hat-hard-white.png","size":[559,495],"slot":"hand","w":4.4,"grip":[0.5,0.9]},"hat-cap":{"file":"hat-cap.png","size":[479,338],"slot":"hand","w":4.4,"grip":[0.5,0.9]},"hat-beret":{"file":"hat-beret.png","size":[437,226],"slot":"hand","w":4.4,"grip":[0.5,0.9]},"hat-crown":{"file":"hat-crown.png","size":[493,352],"slot":"hand","w":4.4,"grip":[0.5,0.9]},"easel":{"file":"easel.png","size":[291,466],"slot":"ground","w":5.0,"anchor":[0.5,1.0],"at":[14.2,8],"canvas":[0.07,0.15,0.86,0.39]},"badge":{"file":"badge.png","size":[457,440],"slot":"body","w":2.2,"anchor":[0.5,0.0],"at":[7.7,2.2]},"camera":{"file":"camera.png","size":[513,592],"slot":"hand","w":3.6,"grip":[0.25,0.92],"flip":false,"tip":[0.81,0.07],"lens":[0.49,0.43]},"trashcan":{"file":"trashcan.png","size":[532,532],"slot":"ground","w":7.5,"anchor":[0.36,1.0],"at":[16.4,8],"grip":[0.36,0.06],"mouth":[0.38,0.12]},"paintbucket":{"file":"paintbucket.png","size":[493,572],"slot":"hand","w":4.2,"grip":[0.5,0.05],"anchor":[0.5,1.0]},"paintchips":{"file":"paintchips.png","size":[734,502],"slot":"hand","w":4.4,"grip":[0.55,0.86]},"stopsign":{"file":"stopsign.png","size":[486,592],"slot":"hand","w":3.4,"grip":[0.49,0.93],"label":[0.12,0.17,0.76,0.42],"text":"STOP"},"paperplane":{"file":"paperplane.png","size":[510,344],"slot":"hand","w":3.8,"grip":[0.4,0.62],"tip":[0.98,0.04]},"envelope":{"file":"envelope.png","size":[492,354],"slot":"hand","w":3.2,"grip":[0.12,0.8],"flip":false},"redcard":{"file":"redcard.png","size":[354,511],"slot":"hand","w":1.9,"grip":[0.5,0.9],"rot":-8,"flip":false},"yellowcard":{"file":"yellowcard.png","size":[354,511],"slot":"hand","w":1.9,"grip":[0.5,0.9],"rot":-8,"flip":false}};
  /* PROPS:end */

  // where a worn image prop's anchor goes on the critter grid, per slot
  const CROWD = ["npc-hoodie", "npc-coffee", "npc-office", "npc-raincoat", "npc-elder", "npc-kid", "npc-shopper", "npc-gamer"];
  const SLOT_AT = { head: [6, 0.95], ears: [6, 1.6], face: [6, 1.5], body: [6, 2], back: [6, 3], ground: [14, 8], neck: [6, 2.1] };
  const Z = { back: 1, ground: 1, body: 3, face: 4, ears: 5, neck: 5, head: 6 };

  // ---------- rendering ----------
  function readU(el, o) {
    if (o.u) el.style.setProperty("--u", o.u + "px");
    let u = parseFloat(getComputedStyle(el).getPropertyValue("--u"));
    if (!u) {
      const w = parseFloat(el.style.width);
      u = w ? w / 12 : 16;
      el.style.setProperty("--u", u + "px");
    }
    return u;
  }
  const listOpt = (v) => (v == null || v === "" ? [] : Array.isArray(v) ? v : String(v).split(/[,\s]+/).filter(Boolean));

  function bodySVG(arms, eyes, G = SHAPES.critter) {
    if (G.name === "pal") return palSVG(arms, eyes, G);
    const svg = gridSVG("crit-svg");
    const fill = "var(--crit-color)";
    const gA = group(svg, { part: "arms" });
    for (const name in ARMS) {
      const [rs, ls] = ARMS[name];
      const g = group(gA, { arms: name }, name === arms);
      SIDES[rs].arm.forEach((r) => rect(g, r, fill));
      SIDES[ls].arm.forEach((r) => rect(g, mirror(r), fill));
    }
    const gL = group(svg, { part: "legs" });
    for (const name in LEGS) {
      const g = group(gL, { legs: name }, name === "stand");
      LEGS[name].forEach((r) => rect(g, r, fill));
    }
    rect(svg, [2, 0, 8, 6], fill).setAttribute("class", "crit-torso");
    const gE = group(svg, { part: "eyes" });
    for (const name in EYES) {
      const g = group(gE, { eyes: name }, name === eyes);
      EYES[name].forEach((r) => rect(g, r, "var(--crit-eye)"));
    }
    return svg;
  }
  // the pal: feet behind the bun, the bun (one path), its shine, rim shade and blush, the arms over its edge, the face
  function palSVG(arms, eyes, G) {
    const svg = gridSVG("crit-svg");
    const fill = "var(--crit-color)";
    const gL = group(svg, { part: "legs" });
    for (const name in G.LEGS) {
      const g = group(gL, { legs: name }, name === "stand");
      G.LEGS[name].forEach((r) => rect(g, r, "var(--crit-shade)"));
    }
    const bun = svgEl("path", { d: rowsPath(G.rows), class: "crit-torso" });
    bun.style.fill = fill;
    svg.appendChild(bun);
    const gS = group(svg, { part: "shade" });
    PAL_RIM.forEach((r) => rect(gS, r, "var(--crit-shade)"));
    PAL_SHINE.forEach((r) => rect(gS, r, "var(--crit-shine)"));
    PAL_BLUSH.forEach((r) => rect(gS, r, "var(--crit-blush)"));
    const gA = group(svg, { part: "arms" });
    for (const name in ARMS) {
      const [rs, ls] = ARMS[name];
      const g = group(gA, { arms: name }, name === arms);
      [[G.SIDES[rs], (r) => r], [G.SIDES[ls], mirror]].forEach(([s, m]) => {
        s.arm.forEach((r) => rect(g, m(r), fill));
        mitt(...s.mitt).forEach((r) => rect(g, m(r), fill));
        rect(g, m([s.mitt[0] + 0.25, s.mitt[1] + s.mitt[3] - 0.25, s.mitt[2] - 0.5, 0.25]), "var(--crit-shade)");
      });
    }
    const gE = group(svg, { part: "eyes" });
    for (const name in G.EYES) {
      const g = group(gE, { eyes: name }, name === eyes);
      G.EYES[name].forEach((r) => rect(g, r, r[4] || "var(--crit-eye)"));
    }
    return svg;
  }

  function render(el, o = {}) {
    const ds = el.dataset;
    o = Object.assign({ color: ds.color, eyes: ds.eyes, arms: ds.arms, hold: ds.hold, wear: ds.wear, role: ds.role,
      ground: ds.ground === "false" ? false : undefined, holdLeft: ds.holdLeft, shape: ds.shape }, o);
    el.classList.add("critter");
    const G = SHAPES[o.shape] || SHAPES.critter;
    el.dataset.shape = G.name;
    const u = readU(el, o);
    el.innerHTML = "";
    const color = COLORS[o.color] || o.color;
    if (color) el.style.setProperty("--crit-color", color);
    if (o.eye) el.style.setProperty("--crit-eye", o.eye);
    const ground = div("crit-ground");
    if (o.ground === false) ground.style.opacity = 0;
    el.appendChild(ground);
    const mud = div("crit-mud");
    el.appendChild(mud);
    const body = div("crit-body");
    el.appendChild(body);
    const arms = ARMS[o.arms] ? o.arms : "down", eyes = G.EYES[o.eyes] ? o.eyes : "normal";
    body.appendChild(bodySVG(arms, eyes, G));
    const hands = {};
    ["r", "l"].forEach((side) => {
      const h = div("crit-hand");
      h.dataset.hand = side;
      body.appendChild(h);
      hands[side] = h;
    });
    const fx = div("crit-fx");
    body.appendChild(fx);
    el._crit = { u, el, body, ground, mud, hands, fx, G, shape: G.name, items: {}, keys: { eyes: [[-1, eyes]], arms: [[-1, arms]] }, says: [], noGround: o.ground === false };
    placeHands(el, arms);
    if (o.role) AR.crit.role(el, o.role);
    const pair = (p, base) => (Array.isArray(p) ? [p[0], Object.assign({}, base, p[1])] : [p, base]);
    listOpt(o.wear).forEach((p) => AR.crit.wear(el, ...pair(p, {})));
    listOpt(o.hold).forEach((p, i) => AR.crit.hold(el, ...pair(p, { hand: i ? "left" : "right" })));
    listOpt(o.holdLeft).forEach((p) => AR.crit.hold(el, ...pair(p, { hand: "left" })));
    return el;
  }

  // where a hand is (grid units) in an arm state, for this critter's shape
  const gripOf = (c, state, side) => {
    const S = (c && c.G ? c.G : SHAPES.critter).SIDES;
    const s = S[ARMS[state][side === "r" ? 0 : 1]];
    return side === "r" ? s.grip : [12 - s.grip[0], s.grip[1]];
  };
  function placeHands(el, state) {
    const c = el._crit;
    ["r", "l"].forEach((side) => {
      const g = gripOf(c, state, side);
      gsap.set(c.hands[side], { x: g[0] * c.u, y: g[1] * c.u });
    });
  }
  const stateAt = (keys, t) => {
    let best = keys[0];
    keys.forEach((k) => { if (k[0] <= t + 1e-6 && k[0] >= best[0]) best = k; });
    return best[1];
  };

  // switch every [data-<kind>] group of a critter (body and wearables) to `name` at t
  function setState(tl, el, kind, name, t) {
    el.querySelectorAll(`[data-${kind}]`).forEach((g) => tl.set(g, { opacity: g.getAttribute(`data-${kind}`) === name ? 1 : 0 }, t));
    if (el._crit.keys[kind]) el._crit.keys[kind].push([t, name]);
  }

  // ---------- wearables and props ----------
  function propDef(prop, o) {
    if (Array.isArray(prop)) prop = prop[0];
    if (typeof prop === "object") {
      if (!prop.size && !prop.parts) { console.warn("critter: a custom prop needs size [w, h] and src"); return null; }
      return Object.assign({ name: prop.name || "custom" }, prop);
    }
    if (CODE[prop]) return Object.assign({ name: prop, code: true }, CODE[prop]);
    const d = PROPS[prop];
    if (!d) { console.warn(`critter: no prop named "${prop}"`); return null; }
    return Object.assign({ name: prop }, d);
  }

  // a code wearable as SVG. On the critter: one svg, drawn as always. On another shape: the parts and details fitted
  // to that shape's anatomy for the item's slot (and a torso clip for body wear), plus the sleeves as a second svg drawn
  // on the shape's own arms
  function codeSVG(def, colors, G = SHAPES.critter) {
    const C = (k) => colors[k] || k;
    const pad = 0.125, line = C("line") !== "line" ? C("line") : null;
    const outline = (r, parent) => line && rect(parent, [r[0] - pad, r[1] - pad, r[2] + 2 * pad, r[3] + 2 * pad], line);
    const sleeves = (parent) => {
      const sg = group(parent, { part: "sleeves" });
      for (const name in ARMS) {
        const g = group(sg, { arms: name }, false);
        const [rs, ls] = ARMS[name];
        [[G.SIDES[rs], (r) => r], [G.SIDES[ls], mirror]].forEach(([s, m]) => {
          s.sleeve.forEach((r) => outline(m(r), g));
          s.sleeve.forEach((r) => rect(g, m(r), C("main")));
          if (s.cuff) rect(g, m(s.cuff), C("dark"));
        });
      }
    };
    const svg = gridSVG("crit-code");
    if (G.name === "critter") {
      def.parts.forEach((r) => outline(r, svg));
      if (def.sleeves) sleeves(svg);
      def.parts.forEach((r) => rect(svg, r, C(r[4])));
      def.details.forEach((r) => rect(svg, r, C(r[4])));
      return { svg };
    }
    const f = fitOf(G, def.slot), g = group(svg, {});
    g.setAttribute("transform", fitSVG(f));
    def.parts.forEach((r) => outline(r, g));
    def.parts.forEach((r) => rect(g, r, C(r[4])));
    def.details.forEach((r) => rect(g, r, C(r[4])));
    let sl = null;
    if (def.sleeves) { sl = gridSVG("crit-code crit-sleeves"); sleeves(sl); }
    return { svg, sleeves: sl, clip: f.clip != null && G.rows ? torsoClip(G.rows, f.clip) : null };
  }
  // text on a prop's blank face (the stop sign): def.label is its box [x, y, w, h] in fractions of the image
  function propLabel(def, W, H, o, mirrored) {
    const text = o.text ?? def.text;
    if (!def.label || text == null || text === "") return null;
    const [lx, ly, lw, lh] = def.label, x = mirrored ? 1 - lx - lw : lx;
    const d = div("crit-label");
    d.textContent = text;
    const fs = Math.min(lh * H * 0.78, (lw * W) / Math.max(1, String(text).length * 0.66));
    Object.assign(d.style, { left: x * W + "px", top: ly * H + "px", width: lw * W + "px", height: lh * H + "px",
      fontSize: fs + "px", color: o.textColor || def.textColor || "#fff" });
    return d;
  }

  function attach(el, prop, o = {}) {
    const c = el._crit || render(el, {})._crit;
    const def = propDef(prop, o);
    if (!def) return null;
    const name = o.as || def.name;
    if (c.items[name]) return c.items[name];
    const u = c.u;
    const slot = o.slot || (o.mode === "hold" ? "hand" : def.slot === "hand" && o.mode === "wear" ? "hand" : def.slot || "head");
    const rec = { name, def, slot, el };
    if (def.code) {
      const box = div("crit-worn crit-codewear");
      box.dataset.prop = name;
      box.dataset.slot = def.slot;
      Object.assign(box.style, { left: "0px", top: "0px", width: 12 * u + "px", height: 8 * u + "px" });
      const move = div("crit-move");
      const out = codeSVG(def, Object.assign({}, def.colors, o.colors || {}), c.G);
      if (out.clip) {
        const clip = div("crit-clip");
        clip.style.clipPath = out.clip;
        clip.appendChild(out.svg);
        move.appendChild(clip);
      } else move.appendChild(out.svg);
      if (out.sleeves) move.appendChild(out.sleeves);
      box.appendChild(move);
      c.body.appendChild(box);
      // sleeves start on the critter's current arm state
      const now = stateAt(c.keys.arms, 0);
      move.querySelectorAll("[data-arms]").forEach((g) => (g.style.opacity = g.getAttribute("data-arms") === now ? 1 : 0));
      const top = fitPt(c.G, def.slot, [6, Math.min(0, ...def.parts.concat(def.details).map((r) => r[1]))])[1];
      Object.assign(rec, { root: box, move, slot: def.slot, top });
    } else if (slot === "hand") {
      const side = String(o.hand || def.hand || "right")[0] === "l" ? "l" : "r";
      const W = (o.w || def.w || 3) * u, H = W * def.size[1] / def.size[0];
      const item = div("crit-item");
      item.dataset.prop = name;
      const grip = div("crit-grip");
      const img = document.createElement("img");
      img.src = def.src || PROP_DIR + def.file;
      img.alt = "";
      let gx = def.grip ? def.grip[0] : 0.5, gy = def.grip ? def.grip[1] : 0.5, rot = o.rot ?? def.rot ?? 0;
      if (side === "l") {
        gx = 1 - gx;
        rot = -rot;
        if (def.flip !== false) img.style.transform = "scaleX(-1)";
      }
      Object.assign(img.style, { width: W + "px", height: H + "px", left: -gx * W + "px", top: -gy * H + "px" });
      grip.style.left = (o.dx || 0) * u + "px";
      grip.style.top = (o.dy || 0) * u + "px";
      gsap.set(grip, { rotation: rot });
      grip.appendChild(img);
      const lab = propLabel(def, W, H, o, side === "l" && def.flip !== false);
      if (lab) { lab.style.left = parseFloat(lab.style.left) - gx * W + "px"; lab.style.top = parseFloat(lab.style.top) - gy * H + "px"; grip.appendChild(lab); }
      item.appendChild(grip);
      c.hands[side].appendChild(item);
      Object.assign(rec, { root: item, move: item, grip, img, side, W, H, gx, gy, rot });
    } else {
      const W = (o.w || def.w || 4) * u, H = W * def.size[1] / def.size[0];
      const at = o.at || fitPt(c.G, slot, def.at || SLOT_AT[slot] || SLOT_AT.head);
      const anchor = def.anchor || [0.5, 1];
      const box = div("crit-worn");
      box.dataset.prop = name;
      box.dataset.slot = slot;
      Object.assign(box.style, {
        left: at[0] * u - anchor[0] * W + (o.dx || 0) * u + "px", top: at[1] * u - anchor[1] * H + (o.dy || 0) * u + "px",
        width: W + "px", height: H + "px", zIndex: Z[slot] || 6,
      });
      const move = div("crit-move");
      const img = document.createElement("img");
      img.src = def.src || PROP_DIR + def.file;
      img.alt = "";
      if (o.flip) img.style.transform = "scaleX(-1)";
      move.appendChild(img);
      const lab = propLabel(def, W, H, o, !!o.flip);
      if (lab) move.appendChild(lab);
      box.appendChild(move);
      (slot === "ground" ? el : c.body).appendChild(box);
      if (def.rot || o.rot) gsap.set(move, { rotation: o.rot ?? def.rot, transformOrigin: "50% 100%" });
      Object.assign(rec, { root: box, move, img, W, H, top: (at[1] * u - anchor[1] * H) / u });
    }
    c.items[name] = rec;
    return rec;
  }

  // the scene top of an element, for drops that start above the frame
  function sceneTop(el) {
    let y = 0, n = el;
    while (n && !(n.hasAttribute && n.hasAttribute("data-composition-id"))) { y += n.offsetTop || 0; n = n.offsetParent; }
    return y;
  }
  function rectIn(el, root) {
    let x = 0, y = 0, n = el;
    while (n && n !== root) { x += n.offsetLeft || 0; y += n.offsetTop || 0; n = n.offsetParent; }
    if (n !== root && root) { const r = rectIn(root, null); x -= r.x; y -= r.y; }
    return { x, y, w: el.offsetWidth, h: el.offsetHeight };
  }

  // ---------- states ----------
  const C = {
    COLORS, ARMS, EYES, SIDES, LEGS, CODE, PROPS, SHAPES,

    /** switch the eyes: normal happy closed x wide look-left look-right look-up look-down sad angry squeeze */
    eyes(tl, sel, t, kind) {
      crits(sel).forEach((el) => setState(tl, el, "eyes", EYES[kind] ? kind : "normal", t));
      return tl;
    },
    /** a blink: closed for o.dur (0.1 s), then back to the eyes it had at t */
    blink(tl, sel, t, o = {}) {
      crits(sel).forEach((el) => {
        const back = o.back || stateAt(el._crit.keys.eyes, t);
        if (!/normal|look/.test(back) && !o.back) return;
        setState(tl, el, "eyes", "closed", t);
        setState(tl, el, "eyes", back, t + (o.dur ?? 0.1));
      });
      return tl;
    },
    /** switch the arms: down up point point-left wave out hold-up limp. "wave" waves for o.dur (0.9 s) and ends on
     *  o.end ("down"); held props follow the hand */
    arms(tl, sel, t, kind, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit;
        const go = (name, at) => {
          setState(tl, el, "arms", name, at);
          ["r", "l"].forEach((side) => {
            const g = gripOf(c, name, side);
            tl.set(c.hands[side], { x: g[0] * c.u, y: g[1] * c.u }, at);
          });
        };
        if (kind === "wave") {
          const fps = o.fps ?? 6, n = Math.max(2, Math.round((o.dur ?? 0.9) * fps));
          for (let i = 0; i < n; i++) go(i % 2 ? "wave2" : "wave", t + i / fps);
          go(o.end || "down", t + n / fps);
        } else go(ARMS[kind] ? kind : "down", t);
      });
      return tl;
    },
    /** recolour on the timeline (a name from AR.crit.COLORS or any CSS colour) */
    color(tl, sel, t, color) {
      crits(sel).forEach((el) => tl.set(el, { "--crit-color": COLORS[color] || color }, t));
      return tl;
    },
    /** leg-swap walk while moving the whole critter (ground included) by o.x / o.y; eyes look the way it walks */
    walk(tl, sel, t, dur, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, fps = o.fps ?? 8, n = Math.max(1, Math.floor(dur * fps));
        for (let i = 0; i < n; i++) setState(tl, el, "legs", i % 2 ? "b" : "a", t + i / fps);
        setState(tl, el, "legs", "stand", t + dur);
        if (o.x !== undefined || o.y !== undefined) {
          tl.to(el, { x: o.x ?? "+=0", y: o.y ?? "+=0", duration: dur, ease: o.ease ?? "none" }, t);
          for (let i = 0; i < n; i++) tl.set(c.body, { y: i % 2 ? -0.25 * c.u : 0 }, t + i / fps);
          tl.set(c.body, { y: 0 }, t + dur);
        }
        const dx = typeof o.x === "number" ? o.x : typeof o.x === "string" ? parseFloat(o.x.replace("=", "")) * (o.x.startsWith("-") ? -1 : 1) : 0;
        if (o.look !== false && dx) {
          const before = stateAt(c.keys.eyes, t);
          setState(tl, el, "eyes", dx > 0 ? "look-right" : "look-left", t);
          setState(tl, el, "eyes", before, t + dur);
        }
      });
      return tl;
    },
    /** sprite-pose names on a critter: idle cheer sad point think shock talk jump walk_a walk_b fight_* */
    pose(tl, sel, t, name) {
      const P = {
        idle: ["down", "normal", "stand"], cheer: ["up", "happy"], sad: ["limp", "sad"], point: ["point", "normal"],
        think: ["down", "look-up"], shock: ["down", "wide"], talk: ["point", "normal"], jump: ["up", "happy", "tuck"],
        walk_a: [null, null, "a"], walk_b: [null, null, "b"], fight_ready: ["down", "angry"], fight_attack: ["point", "angry"],
        fight_hurt: ["down", "squeeze"], fight_victory: ["up", "happy"],
      }[name] || ["down", "normal", "stand"];
      if (P[0]) C.arms(tl, sel, t, P[0]);
      if (P[1]) C.eyes(tl, sel, t, P[1]);
      crits(sel).forEach((el) => setState(tl, el, "legs", P[2] || "stand", t));
      return tl;
    },

    // ---------- props ----------
    /** put a prop in a hand (static setup): AR.crit.hold("#b01-crit", "magnifier", {hand: "left", rot, w, dx, dy}) */
    hold(sel, prop, o = {}) {
      return crits(sel).map((el) => attach(el, prop, Object.assign({}, o, { mode: "hold" })))[0];
    },
    /** put a wearable on (static setup): a code-drawn coat suit vest shirt sunglasses goldshades glasses goggles
     *  visor headset earpiece, or a library hat (fedora hardhat cap crown beret ...) or any prop with {slot, at} */
    wear(sel, prop, o = {}) {
      return crits(sel).map((el) => attach(el, prop, Object.assign({}, o, { mode: "wear" })))[0];
    },
    /** a role: its wearables and props in one call (AR.crit.ROLES lists them) */
    role(sel, name, o = {}) {
      const r = ROLES[name];
      if (!r) { console.warn(`critter: no role "${name}"`); return; }
      crits(sel).forEach((el) => {
        if (r.color && !o.keepColor) el.style.setProperty("--crit-color", COLORS[r.color] || r.color);
        (r.wear || []).forEach((p) => (Array.isArray(p) ? C.wear(el, p[0], p[1] || {}) : C.wear(el, p)));
        (r.hold || []).forEach((p, i) => C.hold(el, Array.isArray(p) ? p[0] : p, Object.assign({ hand: i ? "left" : "right" }, Array.isArray(p) ? p[1] : {})));
      });
    },
    /** costume drop on the word: the prop falls onto the critter and lands at t with a squash. Head and ear items
     *  get an anticipation squash and a stretch up into them. A prop taken off with unwear() drops back on.
     *  o: {hand, dur (0.24), from (fall px), rot, stretch, squash} */
    dress(tl, sel, prop, t, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u;
        const def = propDef(prop, o);
        if (!def) return;
        let rec = c.items[o.as || def.name];
        const fresh = !rec;
        if (fresh) {
          rec = attach(el, prop, Object.assign({}, o, { mode: def.slot === "hand" || o.hand ? "hold" : "wear" }));
          rec.move.style.opacity = 0;
        }
        const dur = o.dur ?? 0.24, t0 = Math.max(0, t - dur);
        if (fresh || !rec.off) {
          const fall = o.from ?? Math.max(10 * u, sceneTop(el) + 9 * u);
          tl.set(rec.move, { opacity: 1 }, t0);
          tl.fromTo(rec.move, { y: -fall, rotation: o.rot ?? -10 }, { y: 0, rotation: 0, duration: t - t0, ease: "power2.in", immediateRender: false }, t0);
        } else {
          tl.to(rec.move, { x: 0, y: 0, rotation: 0, opacity: 1, duration: t - t0, ease: "power2.in" }, t0);
        }
        rec.off = false;
        const b = c.body;
        const stretch = o.stretch ?? (rec.slot === "head" || rec.slot === "ears" || rec.slot === "face");
        if (stretch && t - t0 > 0.12) {
          tl.to(b, { scaleY: 0.86, scaleX: 1.1, duration: (t - t0) * 0.45, ease: "power2.out" }, t0);
          tl.to(b, { scaleY: 1.12, scaleX: 0.92, duration: (t - t0) * 0.55, ease: "power2.in" }, t0 + (t - t0) * 0.45);
        }
        if (o.squash !== false) {
          tl.set(b, { scaleY: 0.8, scaleX: 1.16 }, t);
          tl.to(b, { scaleY: 1, scaleX: 1, duration: 0.26, ease: "back.out(3)" }, t);
        }
      });
      return tl;
    },
    /** a worn or held item flies off: o.to up (default) / left / right / down, o.dist (u, 7), o.spin (deg), o.fade */
    unwear(tl, sel, prop, t, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, rec = c.items[prop];
        if (!rec) return;
        const dur = o.dur ?? 0.32, d = (o.dist ?? 7) * u, to = o.to || "up";
        const x = to === "left" ? -d : to === "right" ? d : (o.dx ?? 0.4) * u;
        const y = to === "down" ? 0.4 * d : to === "up" ? -d : -0.5 * d;
        tl.to(rec.move, { x, y, rotation: o.spin ?? (to === "left" ? -24 : 14), duration: dur, ease: "power3.out" }, t);
        if (o.fade) tl.to(rec.move, { opacity: 0, duration: dur * 0.4, ease: "power1.in" }, t + dur * 0.6);
        tl.set(c.body, { scaleY: 1.08, scaleX: 0.95 }, t);
        tl.to(c.body, { scaleY: 1, scaleX: 1, duration: 0.2, ease: "back.out(3)" }, t);
        rec.off = true;
      });
      return tl;
    },
    /** a held prop falls to the floor beside the critter and lies there (a KO'd sword, a dropped phone) */
    letgo(tl, sel, prop, t, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, rec = prop ? c.items[prop] : Object.values(c.items).find((r) => r.slot === "hand");
        if (!rec || rec.slot !== "hand") return;
        const g = gripOf(c, stateAt(c.keys.arms, t), rec.side);
        const floor = (8 - g[1]) * u - Math.min(rec.W, rec.H) * 0.25;
        const dx = (rec.side === "r" ? 1 : -1) * (o.dx ?? 1.2) * u;
        tl.to(rec.move, { x: dx, duration: 0.4, ease: "power1.out" }, t);
        tl.to(rec.move, { y: floor, duration: 0.4, ease: "bounce.out" }, t);
        tl.to(rec.move, { rotation: (rec.side === "r" ? 1 : -1) * (o.rot ?? 96), duration: 0.32, ease: "power2.in" }, t);
        rec.off = true;
      });
      return tl;
    },
    /** a held prop pops into the hand (it was hidden until t) */
    give(tl, sel, prop, t, o = {}) {
      crits(sel).forEach((el) => {
        const rec = el._crit.items[prop] || attach(el, prop, Object.assign({}, o, { mode: "hold" }));
        if (!rec) return;
        tl.fromTo(rec.move, { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.24, ease: "back.out(2.6)" }, t);
      });
      return tl;
    },
  };

  // ---------- roles seen in @opusjake's reels ----------
  const ROLES = {
    detective: { wear: ["coat", "fedora"], hold: ["magnifier", "clipboard"] },
    scout: { wear: ["coat", "fedora"], hold: ["binoculars"] },
    spy: { wear: ["sunglasses"], hold: ["binoculars"] },
    closer: { wear: ["suit", "goldshades", "earpiece"], hold: [["pen", { rot: 180 }]] },
    trader: { wear: ["shirt"], hold: ["phone"] },
    analyst: { hold: ["magnifier", "chartboard"] },
    builder: { wear: ["hardhat"], hold: ["hammer"] },
    architect: { wear: ["hardhat-white"], hold: ["blueprint"] },
    designer: { wear: ["beret"], hold: ["brush"] },
    painter: { wear: ["beret"], hold: ["roller"] },
    qa: { hold: ["bugnet"] },
    engineer: { hold: ["wrench"] },
    accountant: { wear: ["visor"], hold: ["calculator"] },
    banker: { wear: ["suit"], hold: ["moneybag"] },
    planner: { hold: ["chartscroll", "folder"] },
    coach: { wear: ["cap"], hold: ["stopwatch", "whistle"] },
    researcher: { wear: ["glasses"], hold: ["scroll"] },
    writer: { hold: ["quill", "scroll"] },
    marketer: { hold: ["megaphone"] },
    champion: { wear: ["crown"], hold: ["trophy"] },
    knight: { hold: ["sword", "shield"] },
    guard: { hold: ["shield"] },
    launcher: { hold: ["rocket"] },
    shopper: { hold: ["shoppingbag"] },
    navigator: { hold: ["map", "pushpin"] },
    judge: { hold: ["scales"] },
    labeler: { hold: ["labelgun"] },
    timekeeper: { wear: ["goggles"], hold: ["clock"] },
    newsie: { hold: ["newspaper"] },
    operator: { wear: ["headset"] },
    support: { wear: ["headset"], hold: ["phone"] },
    barista: { hold: ["mug"] },
    developer: { hold: ["laptop"] },
    gardener: { hold: ["wateringcan", "sapling"] },
    digger: { wear: ["hardhat"], hold: ["shovel"] },
    drafter: { hold: ["pencil"] },
    mascot: { wear: ["vest", "badge"], hold: ["sapling"] },
    filer: { hold: ["filebox"] },
    king: { wear: ["crown"] },
    receptionist: { hold: ["bell"] },
    lawyer: { wear: ["suit"], hold: ["briefcase"] },
    referee: { wear: ["refshirt"], hold: ["whistle"] },
    photographer: { wear: [["cap", { colors: { main: "#2B2A30", dark: "#18171C", light: "#45434D", badge: "#D9473A" } }]], hold: ["camera"] },
    colorist: { wear: ["beret"], hold: ["paintchips"] },
    courier: { wear: ["cap"], hold: ["envelope"] },
    monster: { color: "purple", wear: ["horns"] },
  };
  C.ROLES = ROLES;

  // ---------- poses and actions ----------
  const heldRec = (c, names) => {
    for (const n of [].concat(names)) if (c.items[n] && c.items[n].slot === "hand") return c.items[n];
    return Object.values(c.items).find((r) => r.slot === "hand");
  };
  // a held prop's working end (lens, nib, spout, tip) relative to the hand, at grip rotation rotDeg
  const tipOff = (rec, rotDeg) => {
    const tip = rec.def.tip || [0.5, 0.5], tx = rec.side === "l" ? 1 - tip[0] : tip[0];
    const lx = (tx - rec.gx) * rec.W, ly = (tip[1] - rec.gy) * rec.H, a = (rotDeg ?? rec.rot ?? 0) * Math.PI / 180;
    return [lx * Math.cos(a) - ly * Math.sin(a), lx * Math.sin(a) + ly * Math.cos(a)];
  };
  Object.assign(C, {
    /** idle life: seeded blinks every 1.3-2.4 s and a stepped bob (o.bob false to keep it still) */
    alive(tl, sel, t, dur, o = {}) {
      crits(sel).forEach((el, i) => {
        const r = rnd((o.seed ?? 11) + i * 31);
        let k = t + 0.35 + r() * 0.9;
        while (k < t + dur - 0.15) { C.blink(tl, el, k); k += 1.3 + r() * 1.1; }
        if (o.bob !== false) {
          const fps = o.fps ?? 2.5, amp = (o.amp ?? 0.25) * el._crit.u, off = r() / fps;
          const n = Math.floor((dur - off) * fps);
          for (let j = 0; j < n; j++) tl.set(el._crit.body, { y: j % 2 ? -amp : 0 }, t + off + j / fps);
          tl.set(el._crit.body, { y: 0 }, t + off + n / fps);
        }
      });
      return tl;
    },
    /** hauling a rope: leans back with squeezed eyes and the arm out, tugging in steps (o.n tugs) */
    pull(tl, sel, t, dur, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, dir = o.dir === "left" ? -1 : 1, n = o.n ?? Math.max(2, Math.round(dur / 0.22));
        const eyesBefore = stateAt(c.keys.eyes, t), armsBefore = stateAt(c.keys.arms, t);
        C.arms(tl, el, t, dir > 0 ? "point" : "point-left");
        C.eyes(tl, el, t, "squeeze");
        tl.to(c.body, { rotation: -14 * dir, duration: 0.1, ease: "power2.out" }, t);
        for (let i = 0; i < n; i++) {
          const k = t + 0.1 + i * (dur - 0.1) / n;
          tl.to(c.body, { rotation: -8 * dir, duration: 0.06, ease: "power2.out" }, k);
          tl.to(c.body, { rotation: -15 * dir, duration: 0.1, ease: "power2.in" }, k + 0.06);
          setState(tl, el, "legs", i % 2 ? "b" : "a", k);
        }
        tl.to(el, { x: `-=${(o.slide ?? 0.6) * u * dir}`, duration: dur, ease: "steps(" + n + ")" }, t);
        if (!o.hold) {
          tl.to(c.body, { rotation: 0, duration: 0.18, ease: "back.out(2)" }, t + dur);
          setState(tl, el, "legs", "stand", t + dur);
          C.eyes(tl, el, t + dur, eyesBefore);
          C.arms(tl, el, t + dur, armsBefore);
        }
      });
      return tl;
    },
    /** shield block: the shield swings in front, the critter crouches with squeezed eyes and is pushed back */
    block(tl, sel, t, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, rec = heldRec(c, ["shield"]), dur = o.dur ?? 0.55;
        const before = stateAt(c.keys.eyes, t);
        if (rec) {
          const g = gripOf(c, stateAt(c.keys.arms, t), rec.side), front = rec.side === "r" ? 8.2 : 3.8;
          const cx = (0.5 - rec.gx) * rec.W, cy = (0.5 - rec.gy) * rec.H;
          tl.to(rec.move, { x: (front - g[0]) * u - cx, y: (c.G.front - g[1]) * u - cy, duration: 0.08, ease: "power3.out" }, t);
          tl.to(rec.move, { x: 0, y: 0, duration: 0.2, ease: "power2.inOut" }, t + dur);
        }
        C.eyes(tl, el, t, "squeeze");
        C.eyes(tl, el, t + dur, before);
        tl.to(c.body, { scaleY: 0.88, scaleX: 1.08, duration: 0.08, ease: "power2.out" }, t);
        tl.to(c.body, { scaleY: 1, scaleX: 1, duration: 0.22, ease: "back.out(2.5)" }, t + dur);
        tl.to(el, { x: `-=${(o.push ?? 0.8) * u}`, duration: 0.18, ease: "power3.out" }, t + 0.04);
      });
      return tl;
    },
    /** KO: X eyes, knocked back with a tilt, the held prop (a sword) drops to the floor */
    ko(tl, sel, t, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, dir = o.dir === "left" ? 1 : -1;
        C.eyes(tl, el, t, "x");
        C.arms(tl, el, t, "limp");
        tl.to(el, { x: `+=${dir * (o.dx ?? 1.2) * u}`, duration: 0.22, ease: "power3.out" }, t);
        tl.to(c.body, { rotation: dir * 18, duration: 0.12, ease: "power2.out" }, t);
        tl.to(c.body, { rotation: dir * 9, duration: 0.3, ease: "bounce.out" }, t + 0.12);
        tl.set(c.body, { scaleY: 0.86, scaleX: 1.1 }, t + 0.2);
        tl.to(c.body, { scaleY: 1, scaleX: 1, duration: 0.25, ease: "back.out(2)" }, t + 0.2);
        Object.values(c.items).filter((r) => r.slot === "hand").forEach((r) => C.letgo(tl, el, r.name, t + 0.04, o));
        if (o.stars !== false) C.emote(tl, el, t + 0.1, "stars", { dur: o.starDur ?? 0.9 });
      });
      return tl;
    },
    /** victory: arms (and whatever it holds) up, happy eyes, a hop */
    victory(tl, sel, t, o = {}) {
      crits(sel).forEach((el) => {
        C.arms(tl, el, t, o.arms || "up");
        C.eyes(tl, el, t, "happy");
        AR.hop(tl, el, t, { h: (o.h ?? 1.6) * el._crit.u, dur: 0.34 });
        Object.values(el._crit.items).filter((r) => r.slot === "hand").forEach((r) =>
          tl.to(r.grip, { rotation: r.side === "r" ? -12 : 12, duration: 0.16, ease: "back.out(3)" }, t));
      });
      return tl;
    },
    /** sinking in mud: a puddle spreads, the critter sinks o.depth (0.7 of its height) clipped at the ground line,
     *  arms flailing, eyes wide then sad, a sweat drop */
    sink(tl, sel, t, dur, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, d = (o.depth ?? 0.7) * 8 * u;
        tl.fromTo(c.mud, { opacity: 0, scaleX: 0.3 }, { opacity: 1, scaleX: 1, duration: 0.25, ease: "power2.out" }, t);
        tl.to(c.ground, { opacity: 0, duration: 0.15 }, t);
        tl.fromTo(c.body, { clipPath: "inset(-300% -300% 0px -300%)" },
          { clipPath: `inset(-300% -300% ${d}px -300%)`, y: d, duration: dur, ease: o.ease ?? "power1.in", immediateRender: false }, t);
        C.eyes(tl, el, t, "wide");
        C.eyes(tl, el, t + Math.min(0.5, dur * 0.5), "sad");
        const fps = 5, n = Math.max(2, Math.floor(dur * fps));
        for (let i = 0; i < n; i++) C.arms(tl, el, t + i / fps, i % 2 ? "up" : "out");
        C.emote(tl, el, t + 0.1, "sweat", { dur: Math.min(1, dur) });
      });
      return tl;
    },

    // --- prop actions: each uses the prop it holds (attached if missing) ---
    /** dig with a shovel: o.n thrusts, dirt flying up behind */
    dig(tl, sel, t, dur, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, rec = c.items.shovel || attach(el, "shovel", { mode: "hold" }), r = rnd(o.seed ?? 5);
        const n = o.n ?? Math.max(1, Math.round(dur / 0.42)), step = dur / n;
        for (let i = 0; i < n; i++) {
          const k = t + i * step;
          tl.to(rec.move, { y: 0.9 * u, rotation: 0, duration: step * 0.35, ease: "power3.in" }, k);
          tl.set(c.body, { scaleY: 0.9, scaleX: 1.06 }, k + step * 0.35);
          tl.to(c.body, { scaleY: 1, scaleX: 1, duration: step * 0.4, ease: "back.out(2)" }, k + step * 0.35);
          tl.to(rec.move, { y: -0.3 * u, rotation: -28, duration: step * 0.35, ease: "power2.out" }, k + step * 0.45);
          tl.to(rec.move, { y: 0, rotation: 0, duration: step * 0.2, ease: "power1.inOut" }, k + step * 0.8);
          bits(tl, c, k + step * 0.5, { n: 5, color: o.color || "#7A5232", x: 12.3, y: 7.6, dx: 2.5, up: 2.6, r });
        }
      });
      return tl;
    },
    /** water with a watering can: it tilts and drops fall from the spout */
    water(tl, sel, t, dur, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, rec = c.items.wateringcan || attach(el, "wateringcan", { mode: "hold" }), r = rnd(o.seed ?? 9);
        const tilt = rec.rot + (rec.side === "r" ? 32 : -32);
        tl.to(rec.grip, { rotation: tilt, duration: 0.18, ease: "power2.out" }, t);
        tl.to(rec.grip, { rotation: rec.rot, duration: 0.2, ease: "power2.inOut" }, t + dur);
        const g = gripOf(c, stateAt(c.keys.arms, t), rec.side), off = tipOff(rec, tilt);
        const sx = g[0] + off[0] / u, sy = g[1] + off[1] / u;
        const n = Math.max(4, Math.round(dur * 14));
        for (let i = 0; i < n; i++) {
          const k = t + 0.15 + i * (dur - 0.2) / n;
          const d = div("crit-bit");
          d.style.background = o.color || "#69B7E8";
          c.fx.appendChild(d);
          tl.set(d, { x: (sx + (r() - 0.5) * 0.4) * u, y: sy * u, opacity: 1 }, k);
          tl.to(d, { y: (sy + 2.4 + r()) * u, duration: 0.3, ease: "power2.in" }, k);
          tl.set(d, { opacity: 0 }, k + 0.3);
        }
      });
      return tl;
    },
    /** raise binoculars to the eyes, scan left and right, lower them */
    lookout(tl, sel, t, dur, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, rec = c.items.binoculars || attach(el, "binoculars", { mode: "hold" });
        const before = stateAt(c.keys.arms, t);
        C.arms(tl, el, t, "up");
        // centre the binoculars on the eyes from the raised hand
        const g2 = gripOf(c, "up", rec.side), E = c.G.eye;
        const tx2 = (E[0] - g2[0]) * u - (0.5 - rec.gx) * rec.W, ty2 = (E[1] - g2[1]) * u - (0.5 - rec.gy) * rec.H;
        tl.fromTo(rec.move, { x: tx2, y: ty2 + 1.5 * u }, { x: tx2, y: ty2, duration: 0.16, ease: "back.out(2)", immediateRender: false }, t);
        const scan = (o.scan ?? 0.6) * u;
        tl.to(rec.move, { x: tx2 - scan, duration: dur * 0.3, ease: "sine.inOut" }, t + 0.2);
        tl.to(rec.move, { x: tx2 + scan, duration: dur * 0.35, ease: "sine.inOut" }, t + 0.2 + dur * 0.3);
        tl.to(c.body, { x: -scan * 0.5, duration: dur * 0.3, ease: "sine.inOut" }, t + 0.2);
        tl.to(c.body, { x: scan * 0.5, duration: dur * 0.35, ease: "sine.inOut" }, t + 0.2 + dur * 0.3);
        tl.to(c.body, { x: 0, duration: 0.15 }, t + dur);
        tl.to(rec.move, { x: 0, y: 0, duration: 0.18, ease: "power2.inOut" }, t + dur);
        C.arms(tl, el, t + dur, before);
      });
      return tl;
    },
    /** sweep a magnifier side to side across o.dx u (3), the lens leading */
    sweep(tl, sel, t, dur, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, rec = c.items[o.prop || "magnifier"] || attach(el, o.prop || "magnifier", { mode: "hold" });
        const dx = (o.dx ?? 3) * u, n = o.n ?? 2;
        for (let i = 0; i < n; i++) {
          const k = t + i * dur / n, s = i % 2 ? -1 : 1;
          tl.to(rec.move, { x: s * dx * 0.5, y: -0.4 * u, duration: dur / n * 0.5, ease: "sine.inOut" }, k);
          tl.to(rec.move, { x: s * dx, y: 0, duration: dur / n * 0.5, ease: "sine.inOut" }, k + dur / n * 0.5);
          tl.to(rec.grip, { rotation: (rec.rot || 0) + s * 12, duration: dur / n, ease: "sine.inOut" }, k);
        }
        tl.to(rec.move, { x: 0, y: 0, duration: 0.2, ease: "power2.inOut" }, t + dur);
        tl.to(rec.grip, { rotation: rec.rot || 0, duration: 0.2 }, t + dur);
      });
      return tl;
    },
    /** paint at an easel: the brush dabs at the canvas and colour dabs appear on it.
     *  o.easel: the easel element (or one is placed beside the critter), o.colors */
    paint(tl, sel, t, dur, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, r = rnd(o.seed ?? 4);
        const brush = c.items.brush || attach(el, "brush", { mode: "hold" });
        const easel = c.items.easel || attach(el, "easel", { mode: "wear", slot: "ground" });
        const canvas = easel.def.canvas || [0.1, 0.1, 0.8, 0.5];
        const ex = parseFloat(easel.root.style.left), ey = parseFloat(easel.root.style.top);
        const cols = o.colors || ["#E8574A", "#F2B33D", "#4A80D8", "#5AA65A"];
        const n = o.n ?? Math.max(3, Math.round(dur / 0.16));
        C.arms(tl, el, t, "point");
        const g2 = gripOf(c, "point", brush.side), tip = tipOff(brush);
        for (let i = 0; i < n; i++) {
          const k = t + 0.05 + i * (dur - 0.1) / n;
          const px = ex + (canvas[0] + r() * canvas[2]) * easel.W, py = ey + (canvas[1] + r() * canvas[3]) * easel.H;
          tl.to(brush.move, { x: px - g2[0] * u - tip[0], y: py - g2[1] * u - tip[1], duration: 0.07, ease: "power2.out" }, k);
          const dab = div("crit-bit");
          Object.assign(dab.style, { position: "absolute", left: 0, top: 0, background: cols[i % cols.length], width: 0.6 * u + "px", height: 0.45 * u + "px", zIndex: 2 });
          easel.root.appendChild(dab);   // on the canvas, in the easel's own box
          tl.set(dab, { x: px - ex - 0.3 * u, y: py - ey - 0.2 * u, opacity: 1 }, k + 0.07);
        }
        tl.to(brush.move, { x: 0, y: 0, duration: 0.18 }, t + dur);
        C.arms(tl, el, t + dur, "down");
      });
      return tl;
    },
    /** a pen flourish: the pen loops through a signature while its ink line draws (o.prop pen or quill or marker) */
    flourish(tl, sel, t, dur, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, name = o.prop || "pen";
        const rec = c.items[name] || attach(el, name, { mode: "hold" });
        const g = gripOf(c, stateAt(c.keys.arms, t), rec.side);
        const [tipx, tipy] = tipOff(rec);
        // a signature: two loops and a tail, in u, starting at the critter's lower right
        const ox = (o.x ?? 12.5), oy = (o.y ?? 6.5);
        const pts = [[0, 0], [0.6, -1.2], [1.1, -0.2], [0.7, 0.3], [1.6, -1.1], [2.1, 0], [1.8, 0.35], [2.8, -0.8], [3.2, 0.1], [4.4, -0.3]];
        const d = "M" + pts.map((p) => ((ox + p[0]) * u).toFixed(1) + " " + ((oy + p[1]) * u).toFixed(1)).join(" L");
        const s = svgEl("svg", { class: "crit-ink", width: 1, height: 1 });
        Object.assign(s.style, { position: "absolute", left: 0, top: 0, overflow: "visible", zIndex: 1 });
        const path = svgEl("path", { d, pathLength: 1, fill: "none", stroke: o.ink || "#1E2B6E", "stroke-width": Math.max(2, 0.22 * u), "stroke-linecap": "round", "stroke-linejoin": "round" });
        path.style.strokeDasharray = 1;
        path.style.strokeDashoffset = 1;
        s.appendChild(path);
        el.appendChild(s);
        tl.set(path, { opacity: 0 }, 0);
        tl.set(path, { opacity: 1 }, t);
        tl.fromTo(path, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: dur, ease: "none" }, t);
        const keyframes = pts.map((p) => ({ x: (ox + p[0] - g[0]) * u - tipx, y: (oy + p[1] - g[1]) * u - tipy, duration: dur / pts.length, ease: "none" }));
        tl.to(rec.move, { keyframes }, t);
        tl.to(rec.move, { x: 0, y: 0, duration: 0.2, ease: "power2.inOut" }, t + dur + 0.05);
      });
      return tl;
    },
    /** flip a coin: tossed up spinning (o.h u high), eyes following, caught */
    flip(tl, sel, t, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, rec = c.items.coin || attach(el, "coin", { mode: "hold" });
        const h = (o.h ?? 6) * u, dur = o.dur ?? 0.7, spins = o.spins ?? 6;
        const before = stateAt(c.keys.eyes, t);
        tl.to(rec.move, { y: -h, duration: dur / 2, ease: "power2.out" }, t);
        tl.to(rec.move, { y: 0, duration: dur / 2, ease: "power2.in" }, t + dur / 2);
        for (let i = 0; i < spins; i++) tl.set(rec.move, { scaleY: [1, 0.4, -1, 0.4][i % 4] }, t + i * dur / spins);
        tl.set(rec.move, { scaleY: 1 }, t + dur);
        C.eyes(tl, el, t, "look-up");
        C.eyes(tl, el, t + dur, before);
        tl.set(c.body, { scaleY: 0.9, scaleX: 1.06 }, t + dur);
        tl.to(c.body, { scaleY: 1, scaleX: 1, duration: 0.2, ease: "back.out(3)" }, t + dur);
      });
      return tl;
    },
    /** trace with a giant pencil: the critter rides the pencil tip along an SVG path (pathLength="1") as it draws.
     *  path: a <path> in the same coordinate space as the critter's parent */
    trace(tl, sel, t, dur, o = {}) {
      const path = all(o.path)[0];
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, rec = c.items.pencil || attach(el, "pencil", { mode: "hold", rot: o.rot ?? 200 });
        if (!path) return;
        const len = path.getTotalLength(), n = o.steps ?? 24;
        const g = gripOf(c, stateAt(c.keys.arms, t), rec.side), off = tipOff(rec);
        const tipX = g[0] * u + off[0], tipY = g[1] * u + off[1];
        const left = el.offsetLeft, top = el.offsetTop;
        const keyframes = [];
        for (let i = 0; i <= n; i++) {
          const p = path.getPointAtLength(len * i / n);
          keyframes.push({ x: p.x - left - tipX, y: p.y - top - tipY, duration: i ? dur / n : 0, ease: "none" });
        }
        tl.set(el, { x: keyframes[0].x, y: keyframes[0].y }, t);
        tl.to(el, { keyframes: keyframes.slice(1) }, t);
        tl.set(path, { opacity: 0 }, 0);
        tl.set(path, { opacity: 1 }, t);
        tl.fromTo(path, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: dur, ease: "none" }, t);
        const fps = 8, m = Math.floor(dur * fps);
        for (let i = 0; i < m; i++) setState(tl, el, "legs", i % 2 ? "b" : "a", t + i / fps);
        setState(tl, el, "legs", "stand", t + dur);
      });
      return tl;
    },
    /** swing a held tool (a hammer, the sword): wind up, strike down at t + 0.12, o.n times */
    swing(tl, sel, t, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, rec = heldRec(c, [o.prop, "hammer", "sword", "wrench"].filter(Boolean));
        if (!rec) return;
        const n = o.n ?? 1, s = rec.side === "r" ? 1 : -1, base = rec.rot || 0;
        for (let i = 0; i < n; i++) {
          const k = t + i * 0.3;
          tl.to(rec.grip, { rotation: base - 40 * s, duration: 0.12, ease: "power2.out" }, k);
          tl.to(rec.grip, { rotation: base + 70 * s, duration: 0.08, ease: "power4.in" }, k + 0.12);
          tl.to(rec.grip, { rotation: base, duration: 0.14, ease: "power2.out" }, k + 0.22);
          tl.set(c.body, { scaleY: 0.92, scaleX: 1.05 }, k + 0.2);
          tl.to(c.body, { scaleY: 1, scaleX: 1, duration: 0.16, ease: "back.out(2)" }, k + 0.2);
        }
      });
      return tl;
    },
    /** blow a whistle: it comes up to the mouth just before t, the cheeks puff with squeezed eyes and sound lines burst
     *  from it o.n times (2) over dur; then it goes back. o: {prop (whistle), n, color (the lines, ink), lines (true)} */
    blow(tl, sel, t, dur = 0.5, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, name = o.prop || "whistle";
        const rec = c.items[name] || attach(el, name, { mode: "hold" });
        if (!rec || rec.slot !== "hand") return;
        const arms = stateAt(c.keys.arms, t), eyes = stateAt(c.keys.eyes, t), g = gripOf(c, arms, rec.side);
        const rot = rec.side === "r" ? -8 : 8, [tx, ty] = tipOff(rec, rot), M = c.G.mouth;
        const x = (M[0] - g[0]) * u - tx, y = (M[1] - g[1]) * u - ty;
        tl.to(rec.move, { x, y, duration: 0.09, ease: "power3.out" }, t - 0.09);
        tl.to(rec.grip, { rotation: rot, duration: 0.09 }, t - 0.09);
        C.eyes(tl, el, t, "squeeze");
        const n = o.n ?? 2, step = dur / n;
        for (let i = 0; i < n; i++) {
          const k = t + i * step;
          tl.set(c.body, { scaleX: 1.07, scaleY: 0.94 }, k);
          tl.to(c.body, { scaleX: 1, scaleY: 1, duration: Math.min(0.18, step), ease: "power2.out" }, k);
          if (o.lines !== false) {
            // three pixel strokes fanning out past the whistle's far end (o.out: that point in the image, [0.8, 0.3])
            const out = o.out || rec.def.out || [0.8, 0.3], ox = rec.side === "l" ? 1 - out[0] : out[0];
            const far = [g[0] * u + x + (ox - rec.gx) * rec.W, g[1] * u + y + (out[1] - rec.gy) * rec.H];
            [-32, 0, 32].forEach((a, j) => {
              const d = div("crit-bit crit-blow");
              Object.assign(d.style, { width: 0.9 * u + "px", height: 0.3 * u + "px", background: o.color || "var(--ink, #1f1e1c)" });
              c.fx.appendChild(d);
              const s = rec.side === "r" ? 1 : -1, rad = (a * Math.PI) / 180;
              const x0 = far[0] + s * Math.cos(rad) * 0.4 * u, y0 = far[1] + Math.sin(rad) * 0.9 * u;
              tl.set(d, { x: x0, y: y0, rotation: s * a, opacity: 1, transformOrigin: "0% 50%" }, k + 0.01 * j);
              tl.to(d, { x: x0 + s * Math.cos(rad) * 0.7 * u, y: y0 + Math.sin(rad) * 0.7 * u, duration: Math.min(0.16, step * 0.8), ease: "power2.out" }, k + 0.01 * j);
              tl.set(d, { opacity: 0 }, k + Math.min(0.18, step * 0.85));
            });
          }
        }
        C.eyes(tl, el, t + dur, eyes);
        tl.to(rec.move, { x: 0, y: 0, duration: 0.14, ease: "power2.inOut" }, t + dur);
        tl.to(rec.grip, { rotation: rec.rot || 0, duration: 0.14 }, t + dur);
      });
      return tl;
    },
    /** take a photo: the camera comes up to the eyes, the flash bursts at t (and o.flash, a full-frame .flash element,
     *  flashes the scene), then it comes down after o.hold (0.35). o: {prop (camera), flash, peak (0.85)} */
    photo(tl, sel, t, o = {}) {
      crits(sel).forEach((el) => {
        const c = el._crit, u = c.u, name = o.prop || "camera";
        const rec = c.items[name] || attach(el, name, { mode: "hold" });
        if (!rec || rec.slot !== "hand") return;
        const arms = stateAt(c.keys.arms, t), g = gripOf(c, arms, rec.side), E = c.G.eye;
        const lens = rec.def.lens || [0.5, 0.45], lx = rec.side === "l" ? 1 - lens[0] : lens[0];
        const x = (E[0] - g[0]) * u - (lx - rec.gx) * rec.W, y = (E[1] - g[1]) * u - (lens[1] - rec.gy) * rec.H;
        const hold = o.hold ?? 0.35;
        tl.to(rec.move, { x, y, duration: 0.1, ease: "power3.out" }, t - 0.12);
        tl.to(rec.grip, { rotation: 0, duration: 0.1 }, t - 0.12);
        // the burst: a white pixel star at the flash
        const tip = rec.def.tip || [0.8, 0.1], fx = rec.side === "l" ? 1 - tip[0] : tip[0];
        const star = svgEl("svg", { viewBox: "0 0 5 5", class: "crit-emote crit-flashstar" });
        [[2, 0, 1, 5], [0, 2, 5, 1], [1, 1, 3, 3]].forEach((r) => rect(star, r, "#FFFFFF"));
        const sz = 2.2 * u;
        Object.assign(star.style, { width: sz + "px", height: sz + "px", left: g[0] * u + x + (fx - rec.gx) * rec.W - sz / 2 + "px", top: g[1] * u + y + (tip[1] - rec.gy) * rec.H - sz / 2 + "px" });
        c.fx.appendChild(star);
        tl.fromTo(star, { opacity: 0, scale: 0.2, rotation: 0 }, { opacity: 1, scale: 1.3, rotation: 45, duration: 0.08, ease: "power3.out" }, t);
        tl.to(star, { opacity: 0, scale: 0.6, duration: 0.12 }, t + 0.1);
        if (o.flash) AR.flash(tl, o.flash, t, { peak: o.peak ?? 0.85, dur: 0.2 });
        tl.set(c.body, { scaleY: 0.95, scaleX: 1.04 }, t);
        tl.to(c.body, { scaleY: 1, scaleX: 1, duration: 0.16, ease: "back.out(2)" }, t);
        if (hold >= 0) {
          tl.to(rec.move, { x: 0, y: 0, duration: 0.14, ease: "power2.inOut" }, t + hold);
          tl.to(rec.grip, { rotation: rec.rot || 0, duration: 0.14 }, t + hold);
        }
      });
      return tl;
    },
  });

  // fx bits: dust, dirt, sparks (tiny squares that fly and fade)
  function bits(tl, c, t, o) {
    const u = c.u, r = o.r || rnd(o.seed ?? 3);
    for (let i = 0; i < (o.n ?? 6); i++) {
      const d = div("crit-bit");
      d.style.background = o.color || "#C9BBA8";
      c.fx.appendChild(d);
      const x0 = o.x * u, y0 = o.y * u, dx = (r() - 0.3) * o.dx * u, up = (0.5 + r()) * o.up * u;
      tl.set(d, { x: x0, y: y0, opacity: 1 }, t);
      tl.to(d, { x: x0 + dx, duration: 0.42, ease: "none" }, t);
      tl.to(d, { y: y0 - up, duration: 0.2, ease: "power2.out" }, t);
      tl.to(d, { y: y0, duration: 0.22, ease: "power2.in" }, t + 0.2);
      tl.set(d, { opacity: 0 }, t + 0.42);
    }
  }
  C.bits = (tl, sel, t, o = {}) => { crits(sel).forEach((el) => bits(tl, el._crit, t, Object.assign({ x: 6, y: 7.8, dx: 6, up: 1.5 }, o))); return tl; };

  // ---------- emotes ----------
  const EMOTE = {
    "!": { w: 2, h: 7, color: "#D9473A", cells: [[0, 0, 2, 4.5], [0, 5.25, 2, 1.75]] },
    "?": { w: 5, h: 7, color: "#2B2A28", cells: [[1, 0, 3, 1], [0, 1, 1, 1.5], [4, 1, 1, 2], [3, 3, 1, 1], [2, 3.5, 1, 1.5], [2, 5.75, 1, 1.25]] },
    sweat: { w: 3, h: 4, color: "#69B7E8", cells: [[1, 0, 1, 1], [0, 1, 3, 2], [1, 3, 1, 1]], glint: [[0.4, 1.3, 0.6, 0.6]] },
    heart: { w: 7, h: 6, color: "#E2483D", cells: [[1, 0, 2, 1], [4, 0, 2, 1], [0, 1, 7, 2], [1, 3, 5, 1], [2, 4, 3, 1], [3, 5, 1, 1]], glint: [[1, 1, 1, 1]] },
    spark: { w: 5, h: 5, color: "#F2C230", cells: [[2, 0, 1, 5], [0, 2, 5, 1], [1, 1, 3, 3]] },
    stars: { w: 9, h: 3, color: "#F2C230", cells: [[0, 1, 3, 1], [1, 0, 1, 3], [6, 1, 3, 1], [7, 0, 1, 3]] },
    anger: { w: 5, h: 5, color: "#D9473A", cells: [[0, 0, 2, 1], [0, 0, 1, 2], [3, 0, 2, 1], [4, 0, 1, 2], [0, 3, 1, 2], [0, 4, 2, 1], [4, 3, 1, 2], [3, 4, 2, 1]] },
  };
  C.EMOTE = EMOTE;   // the glyphs, for cast.js (generated characters emote the same way)
  /** an emote over the head: "!" "?" sweat heart spark stars anger; o.dur (0.6), o.at [x, y] in u */
  C.emote = function (tl, sel, t, kind, o = {}) {
    const E = EMOTE[kind] || EMOTE["!"];
    crits(sel).forEach((el) => {
      const c = el._crit, u = c.u, cell = Math.max(3, Math.round(u * (o.scale ?? 0.36)));
      const s = svgEl("svg", { viewBox: `0 0 ${E.w} ${E.h}`, width: E.w * cell, height: E.h * cell, class: "crit-emote" });
      E.cells.forEach((r) => rect(s, r, E.color));
      (E.glint || []).forEach((r) => rect(s, r, "#FFFFFF"));
      const at = o.at || (kind === "sweat" ? c.G.sweat : kind === "stars" ? [6 - E.w * cell / u / 2, -1.6] : [9.2, -E.h * cell / u - 0.6]);
      Object.assign(s.style, { left: at[0] * u + "px", top: at[1] * u + "px" });
      c.fx.appendChild(s);
      const dur = o.dur ?? 0.6;
      tl.fromTo(s, { opacity: 0, scale: 0.3, y: 0 }, { opacity: 1, scale: 1, duration: 0.14, ease: "back.out(3)" }, t);
      if (kind === "sweat") tl.to(s, { y: 0.8 * u, duration: dur, ease: "power1.in" }, t + 0.1);
      else if (kind === "stars") tl.to(s, { rotation: 0, x: 0.4 * u, duration: dur, ease: "steps(4)" }, t);
      else tl.to(s, { y: -0.4 * u, duration: 0.12, ease: "power2.out", yoyo: true, repeat: 1 }, t + 0.14);
      tl.to(s, { opacity: 0, duration: 0.12 }, t + dur);
    });
    return tl;
  };

  // ---------- speech bubbles ----------
  function bubble(el, o) {
    const c = el._crit, u = c.u;
    const wrap = div("crit-say");
    const box = div("crit-say-box pxt");
    if (o.size) box.style.fontSize = o.size + "px";
    if (o.maxWidth) box.style.maxWidth = o.maxWidth + "px";
    wrap.appendChild(box);
    const tail = svgEl("svg", { viewBox: "0 0 5 3", class: "crit-say-tail" });
    const ink = "var(--ink, #1f1e1c)";
    [[0, 0, 1, 1], [4, 0, 1, 1], [1, 1, 1, 1], [3, 1, 1, 1], [2, 2, 1, 1]].forEach((r) => rect(tail, r, ink));
    [[1, 0, 3, 1], [2, 1, 1, 1]].forEach((r) => rect(tail, r, "#fff"));
    tail.setAttribute("shape-rendering", "crispEdges");
    wrap.appendChild(tail);
    const head = Object.values(c.items).reduce((m, r) => (/head|ears|face/.test(r.slot) ? Math.min(m, r.top || 0) : m), 0);
    const side = o.side || "right";
    const ax = o.x ?? (side === "left" ? 4.2 : side === "center" ? 6 : 7.8);
    const ay = o.y ?? Math.min(-0.5, head - 0.6);
    Object.assign(wrap.style, { left: ax * u + "px", top: ay * u + "px" });
    box.style.transform = `translateX(${side === "left" ? -84 : side === "center" ? -50 : -16}%)`;
    el.appendChild(wrap);
    return { wrap, box };
  }
  function sayOut(tl, c, b, t) {
    tl.to(b, { opacity: 0, scale: 0.7, duration: 0.1, ease: "power2.in" }, t);
  }
  /** a tailed pixel speech bubble over the critter, mixed-case pixel text.
   *  o: {dur (stays until the next say if left out), side right/left/center, size (px, 32), typing (s of "..." first),
   *      x, y (tail tip in u), maxWidth} */
  C.say = function (tl, sel, t, text, o = {}) {
    crits(sel).forEach((el) => {
      const c = el._crit;
      let t1 = t;
      if (o.typing) { C.typing(tl, el, t, o.typing, Object.assign({}, o, { _chain: true })); t1 = t + o.typing; }
      const { wrap, box } = bubble(el, o);
      box.textContent = text;
      if (AR.names) AR.names(box);
      const prev = c.says[c.says.length - 1];
      if (prev && prev.end == null && prev.start < t1) { sayOut(tl, c, prev.el, t1); prev.end = t1; }
      tl.fromTo(wrap, { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.16, ease: "back.out(2.6)" }, t1);
      const end = o.dur != null ? t1 + o.dur : null;
      if (end != null) sayOut(tl, c, wrap, end);
      c.says.push({ el: wrap, start: t1, end });
    });
    return tl;
  };
  /** a "..." typing bubble for dur seconds (the dots pulse in turn) */
  C.typing = function (tl, sel, t, dur, o = {}) {
    crits(sel).forEach((el) => {
      const c = el._crit;
      const { wrap, box } = bubble(el, o);
      box.classList.add("crit-dots-box");
      const dots = div("crit-dots");
      for (let i = 0; i < 3; i++) dots.appendChild(document.createElement("i"));
      box.appendChild(dots);
      const prev = c.says[c.says.length - 1];
      if (prev && prev.end == null && prev.start < t) { sayOut(tl, c, prev.el, t); prev.end = t; }
      tl.fromTo(wrap, { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.14, ease: "back.out(2.6)" }, t);
      const ds = Array.from(dots.children), fps = 7, n = Math.floor(dur * fps);
      for (let i = 0; i < n; i++) ds.forEach((d, j) => tl.set(d, { opacity: j === i % 3 ? 1 : 0.25 }, t + i / fps));
      if (o._chain) tl.set(wrap, { opacity: 0 }, t + dur);
      else sayOut(tl, c, wrap, t + dur);
      c.says.push({ el: wrap, start: t, end: t + dur });
    });
    return tl;
  };

  // ---------- staging ----------
  /** make a critter inside parent with its feet centre at (x, y) px: AR.crit.make(parent, {id, x, y, u, ...opts}) */
  C.make = function (parent, o = {}) {
    const p = all(parent)[0];
    const el = div("critter");
    if (o.id) el.id = o.id;
    const u = o.u || 16;
    el.style.setProperty("--u", u + "px");
    el.style.left = (o.x ?? 0) - 6 * u + "px";
    el.style.top = (o.y ?? 0) - 8 * u + "px";
    if (o.className) el.className += " " + o.className;
    p.appendChild(el);
    render(el, o);
    return el;
  };
  /** the same critter at several sizes standing on one baseline (model tiers): returns the critters, biggest first.
   *  o: {x (left px), y (baseline px), sizes [u...], gap (px), ...critter options} */
  C.lineup = function (parent, o = {}) {
    const sizes = o.sizes || [26, 19, 13, 9];
    let x = o.x ?? 0;
    return sizes.map((u, i) => {
      const el = C.make(parent, Object.assign({}, o, { id: o.id ? `${o.id}-${i}` : undefined, u, x: x + 6 * u, y: o.y ?? 0 }));
      x += 12 * u + (o.gap ?? 24);
      return el;
    });
  };
  /** stand a critter on a card's edge: o.edge bottom (default) or top, o.at (0-1 along the edge, or px), o.peek
   *  (0-1 of its height hidden below the edge line, clipped, for peeking up over a card's bottom edge) */
  C.perch = function (sel, cardSel, o = {}) {
    const card = all(cardSel)[0];
    crits(sel).forEach((el) => {
      const u = el._crit.u, parent = el.offsetParent || el.parentElement;
      const r = rectIn(card, parent);
      const at = o.at ?? 0.12, x = r.x + (at <= 1 ? at * r.w : at);
      const y = r.y + (o.edge === "top" ? 0 : r.h) - (o.inset ?? 0);
      const peek = (o.peek ?? 0) * 8 * u;
      el.style.left = x - 6 * u + "px";
      el.style.top = y - 8 * u + peek + "px";
      if (peek) el.style.clipPath = `inset(-400% -400% ${peek}px -400%)`;
    });
  };
  /** keep cast members pinned to the same spot of a UI while its camera wrapper moves, without scaling them: they
   *  live outside camSel (the same parent) and slide so their feet stay on the card edge as it scales.
   *  from/to: {scale, x, y} of the camera; set o.cam false when another helper already moves the camera */
  C.follow = function (tl, castSel, camSel, t, dur, o = {}) {
    const cam = all(camSel)[0];
    if (!cam) return tl;
    const from = Object.assign({ scale: 1, x: 0, y: 0 }, o.from || {}), to = Object.assign({ scale: 1, x: 0, y: 0 }, o.to || {});
    const cs = getComputedStyle(cam), [ox, oy] = cs.transformOrigin.split(" ").map(parseFloat);
    const cr = rectIn(cam, cam.offsetParent), Ox = cr.x + ox, Oy = cr.y + oy;
    const ease = o.ease ?? "power2.inOut";
    if (o.cam !== false) tl.fromTo(cam, { scale: from.scale, x: from.x, y: from.y }, { scale: to.scale, x: to.x, y: to.y, duration: dur, ease }, t);
    all(castSel).forEach((el) => {
      const r = rectIn(el, cam.offsetParent), px = r.x + r.w / 2, py = r.y + r.h;
      const d = (s) => ({ x: (s.scale - 1) * (px - Ox) + s.x, y: (s.scale - 1) * (py - Oy) + s.y });
      const a = d(from), b = d(to);
      tl.fromTo(el, { x: a.x, y: a.y }, { x: b.x, y: b.y, duration: dur, ease, immediateRender: o.immediate ?? true }, t);
    });
    return tl;
  };
  /** camera pull-back (or push) on a UI with the cast pinned to it, unscaled: AR.crit.pin(tl, "#b03-cast .critter",
   *  "#b03-cam", 0.3, 0.5, {to: 0.7}) */
  C.pin = function (tl, castSel, camSel, t, dur, o = {}) {
    return C.follow(tl, castSel, camSel, t, dur, {
      from: { scale: o.from ?? 1, x: o.fromX ?? 0, y: o.fromY ?? 0 }, to: { scale: o.to ?? 0.72, x: o.x ?? 0, y: o.y ?? 0 }, ease: o.ease,
    });
  };
  /** a crowd of chibi NPCs (cast/props/crowd) standing on a baseline: returns their boxes, ready for AR.pop, AR.bob or
   *  motion.js's AR.emote(tl, npcs, "?", t). o: {x, y (baseline), w (row width), h (px tall, 120), n, seed, rows (1-2)}.
   *  The crowd lives in its own layer (.crit-crowd, returned as npcs.layer) that keeps its rows and paddles in order
   *  inside it, so anything added to the parent after the crowd (an alert, a card) sits in front of it */
  C.crowd = function (parent, o = {}) {
    const host = all(parent)[0], r = rnd(o.seed ?? 8), names = o.names || CROWD.slice();
    const p = div("crit-crowd");
    host.appendChild(p);
    for (let i = names.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [names[i], names[j]] = [names[j], names[i]]; }
    const n = o.n ?? names.length, rows = o.rows ?? 1, h = o.h ?? 120, w = o.w ?? n * h * 0.62;
    const out = Array.from({ length: n }, (_, i) => {
      const back = rows > 1 && i % 2, k = back ? 0.84 : 1, hh = h * k, ww = hh * 422 / 673;
      const per = rows > 1 ? Math.ceil(n / 2) : n, col = rows > 1 ? Math.floor(i / 2) : i;
      const cx = (o.x ?? 0) + (per > 1 ? (col + (back ? 0.5 : 0)) * (w / per) : w / 2) + (r() - 0.5) * h * 0.12;
      const box = div("crit-npc");
      if (o.id) box.id = `${o.id}-${i}`;
      Object.assign(box.style, { left: cx - ww / 2 + "px", top: (o.y ?? 0) - hh - (back ? h * 0.1 : 0) + "px", width: ww + "px", height: hh + "px", zIndex: back ? 2 : 4 });
      const img = document.createElement("img");
      img.src = PROP_DIR + "crowd/" + names[i % names.length] + ".png";
      img.alt = "";
      box.appendChild(img);
      p.appendChild(box);
      return box;
    });
    out.layer = p;
    return out;
  };

  // ---------- crowd signs: paddles held up over the crowd's heads ----------
  const signFace = (content, bh, color) => {
    const f = div("crit-sign-face");
    if (content && typeof content === "object" && content.img) {
      const im = document.createElement("img");
      im.src = content.img;
      im.alt = "";
      f.appendChild(im);
    } else if (content === "X" || (content && content.x)) {
      f.innerHTML = `<svg viewBox="0 0 10 10"><path d="M2 2 L8 8 M8 2 L2 8" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round"/></svg>`;
    } else {
      const txt = String(content ?? "");
      f.textContent = txt;
      f.style.fontSize = bh * (txt.length <= 2 ? 0.66 : txt.length <= 4 ? 0.44 : 0.3) + "px";
      f.style.color = color;
    }
    return f;
  };
  /** paddles behind the heads of crowd members (the boxes AR.crit.crowd returns), hidden until AR.crit.raise. Returns
   *  the signs, left to right. o: {text ("AI"; an array gives one per person; "X" draws a red X; {img: src} a logo),
   *  back (the other face, for AR.crit.turnSigns), color (border and text, #D42C32), bg (#fff), w (board width as a
   *  share of the person's height, 0.46), tilt (degrees of random lean, 5), seed, id} */
  C.signs = function (npcs, o = {}) {
    const r = rnd(o.seed ?? 4), color = o.color || "#D42C32";
    const pick = (v, i) => (Array.isArray(v) ? v[i % v.length] : v);
    const list = all(npcs).slice().sort((a, b) => a.offsetLeft - b.offsetLeft), cxs = list.map((n) => n.offsetLeft + n.offsetWidth / 2);
    return list.map((n, i) => {
      // a board as wide as o.w of the person's height, but never wider than the gap to the next person
      const near = Math.min(i ? cxs[i] - cxs[i - 1] : Infinity, i < cxs.length - 1 ? cxs[i + 1] - cxs[i] : Infinity);
      const h = n.offsetHeight, bw = Math.min((o.w ?? 0.46) * h, near * 0.94), bh = Math.min(bw * 0.62, 0.3 * h), stick = 0.4 * h, bd = Math.max(3, Math.round(h * 0.022));
      const s = div("crit-sign");
      if (o.id) s.id = `${o.id}-${i}`;
      const cx = n.offsetLeft + n.offsetWidth / 2 + (r() - 0.5) * h * 0.06;
      Object.assign(s.style, { left: cx - bw / 2 + "px", top: n.offsetTop - bh * 0.96 + "px", width: bw + "px", height: bh + stick + "px",
        zIndex: (parseInt(n.style.zIndex, 10) || 2) - 1 });
      const st = div("crit-sign-stick");
      Object.assign(st.style, { left: bw / 2 - bd * 1.6 + "px", top: bh - bd + "px", width: bd * 3.2 + "px", height: stick + "px", borderWidth: bd * 0.7 + "px" });
      const board = div("crit-sign-board");
      Object.assign(board.style, { width: bw + "px", height: bh + "px", borderWidth: bd + "px", borderColor: pick(o.colors, i) || color,
        background: o.bg || "#fff", borderRadius: bd * 2.2 + "px", boxShadow: `0 ${bd}px 0 rgba(0,0,0,.18)` });
      const front = signFace(pick(o.text ?? "AI", i), bh, pick(o.colors, i) || color);
      board.appendChild(front);
      let back = null;
      if (o.back !== undefined) {
        back = signFace(pick(o.back, i), bh, o.backColor || pick(o.colors, i) || color);
        back.style.opacity = 0;
        board.appendChild(back);
      }
      s.appendChild(st);
      s.appendChild(board);
      n.parentElement.insertBefore(s, n);
      gsap.set(s, { rotation: (r() - 0.5) * 2 * (o.tilt ?? 5), transformOrigin: "50% 100%" });
      s._sign = { board, front, back, bh, stick, npc: n };
      return s;
    });
  };
  /** the signs go up one by one from t, o.gap (0.045) apart, in their left-to-right order (o.order: an index list) */
  C.raise = function (tl, signs, t, o = {}) {
    const list = all(signs), order = o.order || list.map((_, i) => i);
    order.forEach((idx, k) => {
      const s = list[idx];
      if (!s) return;
      const S = s._sign || { bh: s.offsetHeight * 0.6, stick: s.offsetHeight * 0.4 };
      tl.fromTo(s, { y: S.bh + S.stick * 0.6, opacity: 0 }, { y: 0, opacity: 1, duration: o.dur ?? 0.16, ease: "back.out(2.2)" }, t + k * (o.gap ?? 0.045));
    });
    return tl;
  };
  /** everyone pumps their sign: o.n pumps (dur / 0.26) of o.amp px (a quarter of the board), the boards wag; o.npcs
   *  (the crowd) hop on each pump */
  C.pump = function (tl, signs, t, dur, o = {}) {
    const list = all(signs), n = o.n ?? Math.max(1, Math.round(dur / 0.26)), step = dur / n;
    list.forEach((s, i) => {
      const amp = o.amp ?? (s._sign ? s._sign.bh * 0.45 : 30), off = (i % 3) * 0.02;
      for (let k = 0; k < n; k++) {
        const tk = t + k * step + off;
        tl.to(s, { y: -amp, duration: step * 0.4, ease: "power2.out" }, tk);
        tl.to(s, { y: 0, duration: step * 0.5, ease: "power2.in" }, tk + step * 0.4);
        tl.to(s._sign ? s._sign.board : s, { rotation: (k + i) % 2 ? 7 : -7, duration: step * 0.9, ease: "sine.inOut" }, tk);
      }
      tl.to(s._sign ? s._sign.board : s, { rotation: 0, duration: 0.12 }, t + dur + off);
    });
    if (o.npcs) all(o.npcs).forEach((p, i) => { for (let k = 0; k < n; k++) AR.hop(tl, p, t + k * step + (i % 2) * 0.03, { h: o.hop ?? 18, dur: Math.min(0.24, step * 0.9) }); });
    return tl;
  };
  /** every sign flips over to its back face (o.gap 0.03 apart): the crowd changes its verdict */
  C.turnSigns = function (tl, signs, t, o = {}) {
    all(signs).forEach((s, i) => {
      const S = s._sign;
      if (!S || !S.back) return;
      const k = t + i * (o.gap ?? 0.03);
      tl.to(S.board, { scaleX: 0, duration: 0.06, ease: "power2.in" }, k);
      tl.set(S.front, { opacity: 0 }, k + 0.06);
      tl.set(S.back, { opacity: 1 }, k + 0.06);
      tl.to(S.board, { scaleX: 1, duration: 0.1, ease: "back.out(2)" }, k + 0.06);
    });
    return tl;
  };
  /** a library prop standing on its own in a scene (a trash can on the floor, a stop sign that slams down, the camera on
   *  a tripod): its anchor (def.anchor, else the bottom centre) at (x, y). Returns the element, ready for AR.drop,
   *  AR.stamp, AR.toss. o: {x, y, w (px) or u (16) for the library width, anchor, text (on a labelled prop), flip, id} */
  C.put = function (parent, name, o = {}) {
    const p = all(parent)[0], def = propDef(name, o);
    if (!p || !def || def.code) return null;
    const W = o.w ?? (o.u || 16) * (def.w || 3), H = (W * def.size[1]) / def.size[0], A = o.anchor || def.anchor || [0.5, 1];
    const d = div("crit-thing");
    if (o.id) d.id = o.id;
    d.dataset.prop = def.name;
    Object.assign(d.style, { left: (o.x ?? 0) - A[0] * W + "px", top: (o.y ?? 0) - A[1] * H + "px", width: W + "px", height: H + "px" });
    const img = document.createElement("img");
    img.src = def.src || PROP_DIR + def.file;
    img.alt = "";
    if (o.flip) img.style.transform = "scaleX(-1)";
    d.appendChild(img);
    const lab = propLabel(def, W, H, o, !!o.flip);
    if (lab) d.appendChild(lab);
    p.appendChild(d);
    return d;
  };
  /** where a critter's hand is, in its parent's coordinates (for ropes and cords) */
  C.handAt = function (sel, side = "right", arms = "down") {
    const el = crits(sel)[0], c = el._crit, g = gripOf(c, arms, side[0] === "l" ? "l" : "r");
    return { x: el.offsetLeft + g[0] * c.u, y: el.offsetTop + g[1] * c.u };
  };
  /** register a prop for this page: AR.crit.prop("scroll2", {src: "assets/art/x.png", size: [w, h], w: 3, grip: [.5, .9]}) */
  C.prop = function (name, def) { PROPS[name] = def; return def; };
  C.propDef = propDef;       // for cast.js: the same props on generated characters
  C.propLabel = propLabel;

  AR.crit = C;
  /** render the critter into each matching element: AR.critter(sel, {color, eyes, arms, hold, wear, role, ground, u}) */
  AR.critter = function (sel, o = {}) {
    const els = all(sel).map((el) => render(el, o));
    return els[0];
  };

  // ---------- the core helpers learn about critters, and only about critters ----------
  // AR.hop / bob / drop / walk / pose / poses (arcade.js) and AR.blink (motion.js) are wrapped: a target that is not a
  // rendered critter goes to the untouched original with the very same arguments, so sprites, UI and every other
  // element get exactly the tweens they always got. A critter's body moves instead (its ground shadow stays on the
  // floor). The originals stay reachable as AR.<name>.__orig. The critter versions are also AR.crit.hop/bob/drop.
  const CRIT = {
    hop(orig, tl, el, t, o = {}) {
      const c = el._crit, d = o.dur ?? 0.36;
      orig.call(AR, tl, c.body, t, o);
      setState(tl, el, "legs", "tuck", t + d * 0.15);
      setState(tl, el, "legs", "stand", t + d * 0.85);
      if (c.noGround) return;
      tl.to(c.ground, { scaleX: 0.72, scaleY: 0.8, opacity: 0.7, duration: d * 0.45, ease: "power2.out" }, t);
      tl.to(c.ground, { scaleX: 1, scaleY: 1, opacity: 1, duration: d * 0.55, ease: "power2.in" }, t + d * 0.45);
    },
    bob: (orig, tl, el, t, dur, o) => orig.call(AR, tl, el._crit.body, t, dur, o),
    drop(orig, tl, el, t, o = {}) {
      const c = el._crit, d = o.dur ?? 0.6;
      orig.call(AR, tl, c.body, t, o);
      if (!c.noGround) tl.fromTo(c.ground, { scaleX: 0.2, opacity: 0 }, { scaleX: 1, opacity: 1, duration: d * 0.36, ease: "power2.in" }, t);
    },
    walk: (orig, tl, el, t, dur, o = {}) => C.walk(tl, el, t, dur, o),
    blink: (orig, tl, el, t, o = {}) => C.blink(tl, el, t, o),
    pose: (orig, tl, el, name, t) => C.pose(tl, el, t, name),
    poses: (orig, tl, el, keys) => keys.forEach(([t, name]) => C.pose(tl, el, t, name)),
  };
  const redirect = (name) => {
    const orig = AR[name];
    if (typeof orig !== "function" || orig.__orig) return;
    const wrapped = function (tl, sel, ...rest) {
      let els;
      try { els = all(sel); } catch (e) { return orig.call(this, tl, sel, ...rest); }
      const cs = els.filter(isCrit);
      if (!cs.length) return orig.call(this, tl, sel, ...rest);
      const others = els.filter((e) => !isCrit(e));
      if (others.length) orig.call(this, tl, others, ...rest);
      cs.forEach((el) => CRIT[name](orig, tl, el, ...rest));
      return tl;
    };
    wrapped.__orig = orig;
    AR[name] = wrapped;
  };
  Object.keys(CRIT).forEach(redirect);
  // the critter versions by name, for scenes that want them explicitly
  ["hop", "bob", "drop"].forEach((name) => {
    C[name] = (tl, sel, ...rest) => {
      const orig = (AR[name] && AR[name].__orig) || AR[name];
      crits(sel).forEach((el) => CRIT[name](orig, tl, el, ...rest));
      return tl;
    };
  });
})();
