/* arcade kit motion helpers.
   Every helper adds seekable tweens to a paused GSAP timeline at scene-local seconds. Nothing reads the
   clock or runs a callback, so any frame renders on its own (the HyperFrames contract).
   Usage inside a scene script:  AR.pop(tl, "#card", 0.2);  AR.walk(tl, "#hero", 0.5, 0.8, { x: "+=300" });

   One rule when writing your own tweens: fromTo() paints its "from" state from frame 0. That is right for
   entrances (opacity 0 before it appears) and wrong for effects that start visible (a flash, a squash).
   For those, tl.set() the start state at the moment, then tl.to() away from it, as flash() does. */
(function () {
  const all = (sel, root) => {
    if (typeof sel !== "string") return sel && sel.length !== undefined ? Array.from(sel) : [sel];
    return Array.from((root || document).querySelectorAll(sel));
  };
  const rnd = (seed) => () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  const AR = {
    rnd,

    // ---------- entrances and exits ----------
    pop(tl, sel, t, o = {}) {
      return tl.fromTo(sel, { scale: o.from ?? 0.5, opacity: o.fade === false ? 1 : 0 },
        { scale: 1, opacity: 1, duration: o.dur ?? 0.34, ease: o.ease ?? "back.out(2.4)" }, t);
    },
    settle(tl, sel, t, o = {}) {
      // the cut-in for a beat's main surface: fully visible and finished on its first frame. By default it does
      // not move (Jake's cuts land locked); pass from/dy for the rare card that should settle in (a page card
      // scaling up into place when the layout changes)
      if (o.from === undefined && o.dy === undefined) return tl.set(sel, { scale: 1, y: 0, opacity: 1 }, t);
      return tl.fromTo(sel, { scale: o.from ?? 1, y: o.dy ?? 0 },
        { scale: 1, y: 0, duration: o.dur ?? 0.16, ease: o.ease ?? "power3.out" }, t);
    },
    drop(tl, sel, t, o = {}) {
      return tl.fromTo(sel, { y: o.dy ?? -1100, opacity: 1 }, { y: 0, duration: o.dur ?? 0.6, ease: "bounce.out" }, t);
    },
    slide(tl, sel, t, o = {}) {
      const d = o.dist ?? 1300, dir = o.from ?? "left";
      const from = { opacity: 0, x: dir === "left" ? -d : dir === "right" ? d : 0, y: dir === "top" ? -d : dir === "bottom" ? d : 0 };
      return tl.fromTo(sel, from, { opacity: 1, x: 0, y: 0, duration: o.dur ?? 0.45, ease: o.ease ?? "expo.out" }, t);
    },
    out(tl, sel, t, o = {}) {
      const kind = o.kind ?? "shrink";
      const to = kind === "fade" ? { opacity: 0 } : kind === "down" ? { y: 300, opacity: 0 } : { scale: 0.6, opacity: 0 };
      return tl.to(sel, { ...to, duration: o.dur ?? 0.16, ease: "power3.in" }, t);
    },
    stagger(tl, sel, t, o = {}) {
      return tl.fromTo(sel, { scale: o.from ?? 0.6, opacity: 0, y: o.y ?? 0 },
        { scale: 1, opacity: 1, y: 0, duration: o.dur ?? 0.3, ease: o.ease ?? "back.out(2)", stagger: o.gap ?? 0.09 }, t);
    },

    // ---------- sprites (.sprite > img.pose[data-pose]) ----------
    pose(tl, sprite, name, t) {
      all(sprite).forEach((sp) => sp.querySelectorAll(".pose").forEach((img) =>
        tl.set(img, { opacity: img.dataset.pose === name ? 1 : 0 }, t)));
      return tl;
    },
    poses(tl, sprite, keys) {
      keys.forEach(([t, name]) => AR.pose(tl, sprite, name, t));
      return tl;
    },
    walk(tl, sprite, t, dur, o = {}) {
      const fps = o.fps ?? 8, a = o.a ?? "walk_a", b = o.b ?? "walk_b";
      const n = Math.max(1, Math.floor(dur * fps));
      for (let i = 0; i < n; i++) AR.pose(tl, sprite, i % 2 ? b : a, t + i / fps);
      AR.pose(tl, sprite, o.end ?? "idle", t + dur);
      if (o.x !== undefined || o.y !== undefined) {
        tl.to(sprite, { x: o.x ?? "+=0", y: o.y ?? "+=0", duration: dur, ease: `steps(${n})` }, t);
      }
      return tl;
    },
    hop(tl, sel, t, o = {}) {
      // absolute: lands back on o.base (0 = where its CSS put it), even if a drop is still settling
      const h = o.h ?? 90, d = o.dur ?? 0.36, base = o.base ?? 0;
      tl.to(sel, { y: base - h, duration: d * 0.45, ease: "power2.out" }, t);
      tl.to(sel, { y: base, duration: d * 0.55, ease: "power2.in" }, t + d * 0.45);
      tl.set(sel, { scaleY: 0.82, scaleX: 1.14 }, t + d);
      return tl.to(sel, { scaleY: 1, scaleX: 1, duration: 0.2, ease: "back.out(3)" }, t + d);
    },
    bob(tl, sel, t, dur, o = {}) {
      // stepped idle life for characters only; never on UI or titles
      const fps = o.fps ?? 3, amp = o.amp ?? 8, n = Math.floor(dur * fps);
      for (let i = 0; i < n; i++) tl.set(sel, { y: i % 2 ? -amp : 0 }, t + i / fps);
      return tl;
    },
    lunge(tl, sel, t, o = {}) {
      const dx = o.dx ?? 220;
      tl.to(sel, { x: `-=${dx * 0.18}`, duration: 0.12, ease: "power2.out" }, t);
      return tl.to(sel, { x: `+=${dx * 1.18}`, duration: 0.14, ease: "power4.in" }, t + 0.12);
    },
    knockback(tl, sel, t, o = {}) {
      const dx = o.dx ?? 160;
      tl.to(sel, { x: `+=${dx}`, rotation: o.rot ?? 12, duration: 0.22, ease: "power3.out" }, t);
      return tl.to(sel, { rotation: 0, duration: 0.3, ease: "power2.inOut" }, t + 0.3);
    },

    // ---------- impact ----------
    shake(tl, sel, t, o = {}) {
      const amp = o.amp ?? 16, n = o.n ?? 7, step = (o.dur ?? 0.32) / n, r = rnd(o.seed ?? 7);
      for (let i = 0; i < n; i++) {
        const k = 1 - i / n;
        tl.to(sel, { x: (r() * 2 - 1) * amp * k, y: (r() * 2 - 1) * amp * k, duration: step, ease: "none" }, t + i * step);
      }
      return tl.to(sel, { x: 0, y: 0, duration: step, ease: "none" }, t + n * step);
    },
    flash(tl, sel, t, o = {}) {
      tl.set(sel, { opacity: o.peak ?? 0.85 }, t);
      return tl.to(sel, { opacity: 0, duration: o.dur ?? 0.16, ease: "power2.out" }, t);
    },
    burst(tl, sel, t, o = {}) {
      const s = o.scale ?? 1.2;
      tl.set(sel, { scale: 0.2, opacity: 1, rotation: 0 }, t);
      tl.to(sel, { scale: s, rotation: 25, duration: 0.18, ease: "power4.out" }, t);
      return tl.to(sel, { opacity: 0, scale: s * 1.15, duration: 0.2, ease: "power2.in" }, t + (o.hold ?? 0.22));
    },
    stamp(tl, sel, t, o = {}) {
      // lands at t + dur: for a word right after a cut, shorten dur rather than starting before the scene
      return tl.fromTo(sel, { scale: o.from ?? 2.8, opacity: 0, rotation: o.rot ?? -14 },
        { scale: 1, opacity: 1, rotation: o.rot ?? -14, duration: o.dur ?? 0.16, ease: "power4.in" }, t);
    },

    // ---------- camera: tween a wrapper inside the clip, never the timed clip ----------
    push(tl, sel, t, dur, o = {}) {
      return tl.fromTo(sel, { scale: o.from ?? 1, x: o.fromX ?? 0, y: o.fromY ?? 0 },
        { scale: o.to ?? 1.12, x: o.x ?? 0, y: o.y ?? 0, duration: dur, ease: o.ease ?? "power1.inOut" }, t);
    },
    punch(tl, sel, t, o = {}) {
      tl.to(sel, { scale: o.to ?? 1.18, duration: 0.07, ease: "power4.out" }, t);
      return tl.to(sel, { scale: o.settle ?? 1.08, duration: 0.35, ease: "power2.out" }, t + 0.07);
    },

    // ---------- text ----------
    names(root) {
      // fills every [data-name="key"] with window.NAMES[key] and every [data-fact="key"] with window.FACTS[key]
      // (both in assets/names.js), so a guessed name or a running-example number is a one-line change;
      // type(), words() and split() run it first
      const N = window.NAMES || {}, F = window.FACTS || {};
      all("[data-name], [data-fact]", root).forEach((el) => {
        const key = el.dataset.name ?? el.dataset.fact, src = el.dataset.name !== undefined ? N : F;
        if (el.dataset.named || !(key in src)) return;
        el.textContent = src[key];
        el.dataset.named = "1";
      });
    },

    // ---------- screens inside generated plates ----------
    mountScreen(sel, quad, o = {}) {
      // puts a live HTML element onto a screen drawn into a plate: quad is the screen's corners from
      // `sprites.py screen` (top-left, top-right, bottom-right, bottom-left, in plate pixels); o.scale and
      // o.dx/o.dy map plate pixels to the scene (the plate's displayed scale and offset). The element keeps its
      // own width and height (its design size) and is warped onto the quad with a CSS homography, so an angled
      // monitor gets an angled screen. Set once at build time; animate the element's children, not it.
      const s = o.scale ?? 1, dx = o.dx ?? 0, dy = o.dy ?? 0;
      all(sel).forEach((el) => {
        const w = el.offsetWidth, h = el.offsetHeight;
        const dst = quad.map(([x, y]) => [x * s + dx, y * s + dy]);
        const src = [[0, 0], [w, 0], [w, h], [0, h]];
        const A = [], b = [];
        src.forEach(([x, y], i) => {
          const [u, v] = dst[i];
          A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.push(u);
          A.push([0, 0, 0, x, y, 1, -v * x, -v * y]); b.push(v);
        });
        for (let c = 0; c < 8; c++) { // Gaussian elimination with partial pivoting
          let p = c;
          for (let r = c + 1; r < 8; r++) if (Math.abs(A[r][c]) > Math.abs(A[p][c])) p = r;
          [A[c], A[p]] = [A[p], A[c]]; [b[c], b[p]] = [b[p], b[c]];
          for (let r = c + 1; r < 8; r++) {
            const f = A[r][c] / A[c][c];
            for (let k = c; k < 8; k++) A[r][k] -= f * A[c][k];
            b[r] -= f * b[c];
          }
        }
        const H = new Array(8);
        for (let r = 7; r >= 0; r--) {
          let acc = b[r];
          for (let k = r + 1; k < 8; k++) acc -= A[r][k] * H[k];
          H[r] = acc / A[r][r];
        }
        const [a1, a2, a3, b1, b2, b3, c1, c2] = H;
        Object.assign(el.style, { position: "absolute", left: "0px", top: "0px", transformOrigin: "0 0",
          transform: `matrix3d(${a1},${b1},0,${c1},${a2},${b2},0,${c2},0,0,1,0,${a3},${b3},0,1)` });
      });
    },
    split(sel) {
      AR.names();
      all(sel).forEach((el) => {
        if (el.dataset.split) return;
        el.dataset.split = "1";
        const text = el.textContent;
        el.textContent = "";
        text.split(/(\s+)/).forEach((w) => {
          if (!w) return;
          if (/^\s+$/.test(w)) { el.appendChild(document.createTextNode(w)); return; }
          const word = document.createElement("span");
          word.style.whiteSpace = "nowrap";
          [...w].forEach((c) => {
            const s = document.createElement("span");
            s.className = "ch";
            s.textContent = c;
            word.appendChild(s);
          });
          el.appendChild(word);
        });
      });
    },
    type(tl, sel, t, o = {}) {
      AR.split(sel);
      const chars = all(sel).flatMap((el) => Array.from(el.querySelectorAll(".ch")));
      return tl.fromTo(chars, { opacity: 0 }, { opacity: 1, duration: 0.001, ease: "none", stagger: 1 / (o.cps ?? 32) }, t);
    },
    typeDur(sel, cps = 32) {
      AR.split(sel);
      return all(sel).reduce((n, el) => n + el.querySelectorAll(".ch").length, 0) / cps;
    },
    words(tl, sel, t, o = {}) {
      // words land one by one; pass o.times (scene seconds, one per unit) to land them on the speech.
      // A nested element (a highlighted phrase, a link) stays whole and lands as one unit. One with its own
      // entrance (class q, or data-own) is left alone for that entrance.
      AR.names();
      const el = all(sel)[0];
      if (!el.dataset.words) {
        el.dataset.words = "1";
        Array.from(el.childNodes).forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            if (!node.matches(".q, [data-own]")) node.classList.add("w");
            return;
          }
          const frag = document.createDocumentFragment();
          node.textContent.split(/(\s+)/).forEach((p) => {
            if (!p) return;
            if (/^\s+$/.test(p)) { frag.appendChild(document.createTextNode(p)); return; }
            const s = document.createElement("span");
            s.className = "w";
            s.style.display = "inline-block";
            s.textContent = p;
            frag.appendChild(s);
          });
          node.replaceWith(frag);
        });
      }
      Array.from(el.querySelectorAll(".w")).forEach((w, i) => tl.fromTo(w, { opacity: 0, y: 18 },
        { opacity: 1, y: 0, duration: 0.14, ease: "power3.out" }, o.times ? o.times[i] : t + i * (o.gap ?? 0.12)));
      return tl;
    },
    count(tl, sel, t, dur, o = {}) {
      return tl.fromTo(sel, { textContent: o.from ?? 0 },
        { textContent: o.to, duration: dur, ease: o.ease ?? "power2.out", snap: { textContent: o.step ?? 1 } }, t);
    },

    // ---------- bars, marks, cursors ----------
    bar(tl, sel, t, dur, o = {}) {
      return tl.fromTo(sel, { scaleX: o.from ?? 1 }, { scaleX: o.to ?? 0, duration: dur, ease: o.ease ?? "power2.out" }, t);
    },
    steppedBar(tl, sel, t, dur, o = {}) {
      return tl.fromTo(sel, { scaleX: o.from ?? 0 }, { scaleX: o.to ?? 1, duration: dur, ease: `steps(${o.steps ?? 10})` }, t);
    },
    sweep(tl, sel, t, dur = 0.35) {
      return tl.fromTo(sel, { backgroundSize: "0% 100%" }, { backgroundSize: "100% 100%", duration: dur, ease: "power2.inOut" }, t);
    },
    marker(tl, sel, t, dur = 0.35) {
      return tl.fromTo(sel, { backgroundSize: "0% 45%" }, { backgroundSize: "100% 45%", duration: dur, ease: "power2.inOut" }, t);
    },
    draw(tl, sel, t, dur = 0.4) {
      // an SVG path with pathLength="1" and style="stroke-dasharray:1"; hidden until it starts drawing, or a
      // round line cap leaves a dot where the line will begin
      tl.set(sel, { opacity: 0 }, 0);
      tl.set(sel, { opacity: 1 }, t);
      return tl.fromTo(sel, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: dur, ease: "power2.inOut" }, t);
    },
    strike(tl, sel, t, dur = 0.22) {
      // .strike is hidden until struck, so rows that are never struck show no line
      tl.set(sel, { opacity: 1 }, t);
      return tl.fromTo(sel, { scaleX: 0 }, { scaleX: 1, duration: dur, ease: "power2.inOut" }, t);
    },
    cursor(tl, sel, t, dur, x, y, o = {}) {
      return tl.to(sel, { x, y, duration: dur, ease: o.ease ?? "power3.inOut" }, t);
    },
    click(tl, sel, t) {
      tl.to(sel, { scale: 0.8, duration: 0.07, ease: "power2.out" }, t);
      return tl.to(sel, { scale: 1, duration: 0.14, ease: "back.out(3)" }, t + 0.07);
    },
    press(tl, sel, t) {
      tl.to(sel, { scale: 0.92, duration: 0.07, ease: "power2.out" }, t);
      return tl.to(sel, { scale: 1, duration: 0.18, ease: "back.out(3)" }, t + 0.07);
    },
    scatter(tl, sel, t, o = {}) {
      // pieces burst out fast and slow down, then fade over the last 40%
      const r = rnd(o.seed ?? 3), spread = o.spread ?? 650, d = o.dur ?? 0.7;
      all(sel).forEach((el, i) => {
        const ang = (r() * 2 - 1) * Math.PI, t0 = t + i * 0.02;
        tl.to(el, {
          x: Math.cos(ang) * spread * (0.6 + r() * 0.6), y: Math.sin(ang) * spread * 0.6 + 500 * r(),
          rotation: (r() * 2 - 1) * 70, duration: d, ease: "power3.out",
        }, t0);
        if (o.fade !== false) tl.to(el, { opacity: 0, duration: d * 0.4, ease: "power1.in" }, t0 + d * 0.6);
      });
      return tl;
    },
    swap(tl, outSel, inSel, t) {
      tl.to(outSel, { opacity: 0, filter: "blur(8px)", duration: 0.14, ease: "power2.in" }, t);
      return tl.fromTo(inSel, { opacity: 0, filter: "blur(8px)" }, { opacity: 1, filter: "blur(0px)", duration: 0.14, ease: "power2.out" }, t + 0.1);
    },
  };
  window.AR = AR;
})();
