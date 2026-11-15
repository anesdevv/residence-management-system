/* ui-claude.js: helpers for the Claude product UI kit (ui-claude.css). Extends window.AR.
   Every helper takes the timeline first, AR.thing(tl, sel, t, opts), adds seekable tweens at scene seconds and
   returns the timeline. Nothing reads the clock or runs a callback; state changes are tl.set() calls on
   attributes (data-k, data-c, data-on, data-state, data-f) that the CSS draws, so any frame renders on its own.
   Scenes call AR.names() then AR.clIcons() first; every helper here also calls AR.clIcons(). */
(function () {
  const AR = (window.AR = window.AR || {});
  const all = (sel, root) => {
    if (!sel) return [];
    if (typeof sel !== "string") return sel.length !== undefined ? Array.from(sel) : [sel];
    return Array.from((root || document).querySelectorAll(sel));
  };
  const one = (sel, root) => all(sel, root)[0];
  const rnd = AR.rnd || ((seed) => () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  });
  const names = () => { if (AR.names) AR.names(); };
  // an element's untransformed layout position on the page (offset chain + offset parents' borders)
  const layoutPos = (el) => {
    let x = 0, y = 0, e = el;
    while (e) {
      x += e.offsetLeft; y += e.offsetTop;
      const p = e.offsetParent;
      if (p) { x += p.clientLeft; y += p.clientTop; }
      e = p;
    }
    return { x, y };
  };
  const initAttr = (el, name, v) => { if (!el.hasAttribute(name)) el.setAttribute(name, v); };

  // ---------- icons: inline SVG, stroke = currentColor ----------
  const S = (body, w = 2) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
  const F = (body, vb = "0 0 24 24") => `<svg viewBox="${vb}" fill="currentColor" stroke="none">${body}</svg>`;
  const ICONS = {
    plus: S('<path d="M12 5v14M5 12h14"/>'),
    "chev-down": S('<path d="m6 9 6 6 6-6"/>', 2.2),
    "chev-right": S('<path d="m9 6 6 6-6 6"/>', 2.2),
    up: S('<path d="M12 19.5V5M5.5 11.5 12 5l6.5 6.5"/>', 2.6),
    mic: S('<rect x="9" y="3" width="6" height="11.5" rx="3"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3"/>'),
    wave: S('<path d="M4 10v4M8 7v10M12 4.5v15M16 7v10M20 10v4"/>'),
    sidebar: S('<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9.5 4v16"/>', 1.8),
    panel: S('<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M14.5 4v16"/>', 1.8),
    comment: S('<path d="M4.5 5.5h15v10.5h-9.5l-4 3.5v-3.5h-1.5z"/>', 1.8),
    expand: S('<path d="M14.5 4h5.5v5.5M9.5 20H4v-5.5M20 4l-6.5 6.5M4 20l6.5-6.5"/>', 1.8),
    close: S('<path d="M6 6l12 12M18 6 6 18"/>', 1.9),
    doc: S('<path d="M7 3h7.5L19 7.5V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3.5V8h4.5M9.5 13h5M9.5 16.5h5"/>', 1.8),
    lock: S('<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/>', 2),
    calendar: S('<rect x="4" y="5" width="16" height="15.5" rx="2.2"/><path d="M4 10h16M8.5 3v4M15.5 3v4"/>', 1.8),
    clock: S('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>', 1.8),
    copy: S('<rect x="8.5" y="8.5" width="12" height="12" rx="2"/><path d="M15.5 8.5V5A1.5 1.5 0 0 0 14 3.5H5A1.5 1.5 0 0 0 3.5 5v9A1.5 1.5 0 0 0 5 15.5h3.5"/>', 1.8),
    "thumb-up": S('<path d="M7.5 10.5v9.5h-3v-9.5zM7.5 10.5 11 3.5c1.6 0 2.6 1.2 2.3 2.8l-.7 3.4h5.6c1.3 0 2.2 1.2 1.9 2.4l-1.6 6.3a2 2 0 0 1-1.9 1.6H7.5"/>', 1.7),
    "thumb-down": S('<path d="M7.5 13.5V4h-3v9.5zM7.5 13.5 11 20.5c1.6 0 2.6-1.2 2.3-2.8l-.7-3.4h5.6c1.3 0 2.2-1.2 1.9-2.4l-1.6-6.3A2 2 0 0 0 16.6 4H7.5"/>', 1.7),
    pencil: S('<path d="M4.5 19.5h4l10-10-4-4-10 10zM13 7l4 4"/>', 1.8),
    cap: S('<path d="M2.5 9.5 12 5l9.5 4.5L12 14z"/><path d="M6.5 11.6V16c0 1.4 2.5 3 5.5 3s5.5-1.6 5.5-3v-4.4"/>', 1.8),
    code: S('<path d="m8.5 7-5 5 5 5M15.5 7l5 5-5 5"/>', 1.9),
    cup: S('<path d="M4.5 9.5h11v4.5a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5z"/><path d="M15.5 10.5h1.5a2.5 2.5 0 0 1 0 5h-1.5M8 3.5v2.5M12 3.5v2.5"/>', 1.8),
    bulb: S('<path d="M9.5 18h5M10.5 21h3M12 3a6 6 0 0 0-3.6 10.8c.8.6 1.1 1.4 1.1 2.2h5c0-.8.3-1.6 1.1-2.2A6 6 0 0 0 12 3z"/>', 1.8),
    search: S('<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>', 1.9),
    globe: S('<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.4 2.4 3.4 5.3 3.4 8.5s-1 6.1-3.4 8.5c-2.4-2.4-3.4-5.3-3.4-8.5S9.6 5.9 12 3.5z"/>', 1.6),
    check: S('<path d="m5 12.5 4.5 4.5L19 7.5"/>', 2.6),
    "check-c": S('<circle cx="12" cy="12" r="8.5"/><path d="m8.3 12.2 2.6 2.6 5-5.2"/>', 1.8),
    gear: S('<circle cx="12" cy="12" r="3"/><path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M5.5 18.5l1.7-1.7M16.8 7.2l1.7-1.7"/><circle cx="12" cy="12" r="6.5"/>', 1.7),
    chart: S('<path d="M4 4v16h16M8.5 16v-4M12.5 16V8M16.5 16v-6"/>', 1.8),
    table: S('<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M9.5 9.5v10"/>', 1.8),
    image: S('<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="m4 18 5.5-5 4 3.5 2.5-2 4 3.5"/>', 1.8),
    checks: S('<path d="m3.5 6.5 1.8 1.8 3-3.3M3.5 13.5l1.8 1.8 3-3.3M11.5 7h9M11.5 14h9M11.5 19.5h9"/>', 1.8),
    text: S('<path d="M5 6.5v-2h14v2M12 4.5v15M9 19.5h6"/>', 1.9),
    shapes: S('<circle cx="8" cy="8" r="4.5"/><rect x="11.5" y="11.5" width="9" height="9" rx="1.5"/>', 1.8),
    download: S('<path d="M12 4v11M7 10.5l5 5 5-5M4.5 19.5h15"/>', 1.8),
    play: S('<path d="M7.5 5v14l11-7z"/>', 1.8),
    more: F('<circle cx="5.5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="18.5" cy="12" r="1.6"/>'),
    enter: S('<path d="M19 5v6a3 3 0 0 1-3 3H5.5M9.5 10l-4 4 4 4"/>', 2),
    sprout: S('<path d="M12 20.5v-8.5M12 12c0-4-3-6-7.5-6 0 4 3 6 7.5 6zM12 14.5c0-3.5 2.5-5.5 7-5.5 0 3.5-3 5.5-7 5.5z"/>', 1.8),
    grid: S('<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>', 1.8),
    folder: S('<path d="M3.5 7a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>', 1.8),
    chats: S('<path d="M4 5.5h12.5v8.5h-7l-3.5 3v-3H4zM16.5 9H20v8.5h-2v2.5l-3-2.5h-4.5V14"/>', 1.7),
    star: F('<path d="m12 3 2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 16.8l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8z"/>'),
    prev: F('<path d="M6 5h2.4v14H6zM9.5 12 19 5.5v13z"/>'),
    next: F('<path d="M15.6 5H18v14h-2.4zM14.5 12 5 5.5v13z"/>'),
    pause: F('<rect x="6.5" y="5" width="4" height="14" rx="1"/><rect x="13.5" y="5" width="4" height="14" rx="1"/>'),
    branch: S('<circle cx="6.5" cy="6" r="2"/><circle cx="6.5" cy="18" r="2"/><circle cx="17.5" cy="8" r="2"/><path d="M6.5 8v8M17.5 10c0 4-11 2.5-11 6"/>', 1.8),
    terminal: S('<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="m7 9.5 3 2.5-3 2.5M12.5 15h4.5"/>', 1.8),
    cursor: '<svg viewBox="0 0 28 36"><path d="M3 2.5v25.2l6.3-5.9 4.3 9.8 4.6-2-4.3-9.6h8.7z" fill="#111" stroke="#fff" stroke-width="2" stroke-linejoin="round"/></svg>',
  };
  // the coral starburst (chat "working" mark, greeting, title prefix)
  const SPARK = (() => {
    const r = rnd(5);
    let d = "";
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2 + (r() - 0.5) * 0.16 - Math.PI / 2;
      const r1 = 9.2 + r() * 2.2;
      d += `M${(12 + Math.cos(a) * 2.2).toFixed(2)} ${(12 + Math.sin(a) * 2.2).toFixed(2)}L${(12 + Math.cos(a) * r1).toFixed(2)} ${(12 + Math.sin(a) * r1).toFixed(2)}`;
    }
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.35" stroke-linecap="round"><path d="${d}"/></svg>`;
  })();
  // Claude Code's spinner glyph frames: · ✢ ✳ ✶ ✻ ✽
  const spokes = (n, r0, r1, w, rot = 0) => {
    let d = "";
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + rot;
      d += `M${(12 + Math.cos(a) * r0).toFixed(2)} ${(12 + Math.sin(a) * r0).toFixed(2)}L${(12 + Math.cos(a) * r1).toFixed(2)} ${(12 + Math.sin(a) * r1).toFixed(2)}`;
    }
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round"><path d="${d}"/></svg>`;
  };
  const GLYPHS = [
    '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="2.6"/></svg>',
    spokes(4, 0, 7.5, 4.2, Math.PI / 4),
    spokes(8, 0, 9.5, 2.5),
    spokes(6, 0, 10, 3, -Math.PI / 2),
    spokes(8, 1.5, 10, 3.5, Math.PI / 8),
    spokes(8, 0, 10.5, 4.4),
  ];
  // the pixel Claude critter: 12 x 8 grid, body 8 wide, side nubs, square eyes, four legs
  const CRITTER = '<svg viewBox="0 0 12 8" shape-rendering="crispEdges"><path fill="currentColor" d="M2 0h8v6H2zM0 2h2v2H0zM10 2h2v2h-2zM2 6h1v2H2zM4 6h1v2H4zM7 6h1v2H7zM9 6h1v2H9z"/><path fill="#161512" d="M3 1h1v1H3zM8 1h1v1H8z"/></svg>';

  // ---------- text splitting that keeps markup (bold, the slash command, a [data-name] span) ----------
  function splitInto(el, cls, unit) {
    const walk = (node) => {
      Array.from(node.childNodes).forEach((n) => {
        if (n.nodeType === 3) {
          const parts = unit === "char" ? Array.from(n.textContent) : n.textContent.split(/(\s+)/);
          const frag = document.createDocumentFragment();
          parts.forEach((p) => {
            if (!p) return;
            if (unit !== "char" && /^\s+$/.test(p)) { frag.appendChild(document.createTextNode(p)); return; }
            const s = document.createElement("span");
            s.className = cls;
            s.textContent = p;
            frag.appendChild(s);
          });
          n.replaceWith(frag);
        } else if (n.nodeType === 1) {
          if (n.matches(".q, [data-own], svg, img, br, .cl-uline, .cl-ph")) return;
          if (n.matches("[data-unit]")) { n.classList.add(cls); return; }
          walk(n);
        }
      });
    };
    walk(el);
  }
  const words = (el) => {
    if (!el.dataset.clw) { names(); el.dataset.clw = "1"; splitInto(el, "cl-w", "word"); }
    return Array.from(el.querySelectorAll(".cl-w"));
  };
  const chars = (el) => {
    if (!el.dataset.clc) { names(); el.dataset.clc = "1"; splitInto(el, "cl-ch", "char"); }
    return Array.from(el.querySelectorAll(".cl-ch"));
  };
  // counters: explicit sets (no onUpdate), keeping the written format: "$1,250", "22.04%", "8.4"
  const fmtOf = (s) => {
    const m = String(s).match(/^(\D*?)(-?[\d,]*\.?\d+)(.*)$/);
    if (!m) return { pre: "", dec: 0, comma: false, suf: "" };
    const num = m[2];
    return { pre: m[1], dec: num.includes(".") ? num.split(".")[1].length : 0, comma: num.includes(","), suf: m[3], v: parseFloat(num.replace(/,/g, "")) };
  };
  const fmtNum = (v, f) => {
    let s = v.toFixed(f.dec);
    if (f.comma) { const [a, b] = s.split("."); s = a.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + (b ? "." + b : ""); }
    return f.pre + s + f.suf;
  };
  const easeOut = (x) => 1 - (1 - x) * (1 - x);
  function countSets(tl, el, t, dur, a, b, fmt, fps = 18, ease = easeOut) {
    const n = Math.max(1, Math.round(dur * fps));
    el.textContent = fmt(a);
    for (let i = 1; i <= n; i++) tl.set(el, { textContent: fmt(a + (b - a) * ease(i / n)) }, t + (i / n) * dur);
  }

  Object.assign(AR, {
    // ---------- setup ----------
    clIcon: (name) => ICONS[name] || "",
    clIcons(root) {
      // draws every icon, logo, spark, spinner glyph, checkbox tick and strike line once (idempotent)
      const r = root || document;
      all("[data-cl-icon]", r).forEach((el) => {
        if (el.dataset.clDone) return;
        el.dataset.clDone = "1";
        el.innerHTML = ICONS[el.dataset.clIcon] || "";
      });
      all(".cl-logo", r).forEach((el) => { if (!el.firstElementChild) el.innerHTML = CRITTER; });
      all(".cl-spark", r).forEach((el) => { if (!el.firstElementChild) el.innerHTML = SPARK; });
      all(".cl-glyph", r).forEach((el) => { if (!el.firstElementChild) { el.innerHTML = GLYPHS.join(""); initAttr(el, "data-f", "2"); } });
      all(".cl-cb, .cl-box", r).forEach((el) => { if (!el.querySelector("svg")) el.insertAdjacentHTML("beforeend", ICONS.check); });
      all(".cl-tt, .cl-dt", r).forEach((el) => { if (!el.querySelector(".cl-x")) el.insertAdjacentHTML("beforeend", '<i class="cl-x"></i>'); });
      all(".cl-ul", r).forEach((el) => { if (!el.querySelector(".cl-uline")) el.insertAdjacentHTML("beforeend", '<i class="cl-uline"></i>'); });
      all(".cl-switch", r).forEach((el) => { if (!el.querySelector("i")) el.insertAdjacentHTML("beforeend", "<i></i>"); });
      all(".cl-cursor", r).forEach((el) => { if (!el.firstElementChild) el.innerHTML = ICONS.cursor; });
    },

    clAim(cursorSel, targetSel, o = {}) {
      // the x, y to hand AR.cursor so a .cl-cursor's tip lands on a target (its centre, or o.ax / o.ay as
      // fractions of its box). Layout positions from offset chains: independent of where the runtime stacks
      // the scene's host on the page and of any transform at build time (a button mid-pop, a camera wrapper).
      // A target inside a wrapper that has moved by the click (a scroll, a push) needs that move added.
      AR.clIcons();
      const c = one(cursorSel), tg = one(targetSel);
      const cp = layoutPos(c), tp = layoutPos(tg);
      const k = c.offsetWidth / 28; // the cursor drawing's tip sits at (3, 2.5) of 28 x 36
      return { x: Math.round(tp.x + tg.offsetWidth * (o.ax ?? 0.5) - (cp.x + 3 * k)),
               y: Math.round(tp.y + tg.offsetHeight * (o.ay ?? 0.55) - (cp.y + 2.5 * k)) };
    },

    // ---------- chat and doc text ----------
    stream(tl, sel, t, o = {}) {
      // LLM streaming: words arrive at ~wps per second (with a little seeded jitter), each lands grey (its own
      // colour at o.grey alpha) and darkens over o.fade s, so the newest few words read as a grey tail.
      // o.times: one scene time per word. Nested markup (<b>, a .cl-ul phrase) is kept and split inside.
      // o.tag: "Claude" adds the collaborator caret + name tag riding the newest word (o.tagOff hides it).
      AR.clIcons();
      const wps = o.wps ?? 14, grey = o.grey ?? 0.4, fade = o.fade ?? 0.24, jit = o.jitter ?? 0.3, r = rnd(o.seed ?? 11);
      let at = t, k = 0, prev = null;
      all(sel).forEach((el) => words(el).forEach((w) => {
        const ti = o.times ? o.times[k] : at;
        // the grey is the word's own colour at low alpha (not opacity), so the cursor tag on it stays solid
        const [cr, cg, cb, ca = 1] = (getComputedStyle(w).color.match(/[\d.]+/g) || [31, 30, 28]).map(Number);
        tl.fromTo(w, { opacity: 0 }, { opacity: 1, duration: 0.001, ease: "none" }, ti);
        tl.fromTo(w, { color: `rgba(${cr},${cg},${cb},${ca * grey})` },
          { color: `rgba(${cr},${cg},${cb},${ca})`, duration: fade, ease: "power1.in" }, ti);
        if (o.tag) {
          initAttr(w, "data-c", "");
          tl.set(w, { attr: { "data-c": o.tag } }, ti);
          if (prev) tl.set(prev, { attr: { "data-c": "" } }, ti);
        }
        prev = w; k++;
        at = ti + (1 + (r() * 2 - 1) * jit) / wps;
      }));
      if (o.tag && prev && o.tagOff !== undefined) tl.set(prev, { attr: { "data-c": "" } }, o.tagOff);
      return tl;
    },
    streamDur(sel, wps = 14) {
      return all(sel).reduce((n, el) => n + words(el).length, 0) / wps;
    },

    composer(tl, sel, t, text, o = {}) {
      // types into a composer's .cl-field (or the field itself; keeps nested markup such as .cl-slash) with a
      // caret, hides the .cl-ph placeholder on the first key and lights the send button (.cl-send; a .cl-voice
      // in the same .cl-sendslot swaps out). text = null types what the HTML already holds.
      // o.cps (default 30), o.focus (when the caret appears; default t), o.blur (caret off).
      AR.clIcons();
      const box = one(sel);
      const field = box.matches(".cl-field") ? box : box.querySelector(".cl-field") || box;
      let txt = field.querySelector(".cl-text");
      if (!txt) { txt = document.createElement("span"); txt.className = "cl-text"; field.appendChild(txt); }
      if (text !== null && text !== undefined) { txt.textContent = text; delete txt.dataset.clc; }
      const cs = chars(txt);
      const cps = o.cps ?? 30, ph = field.querySelector(".cl-ph");
      initAttr(field, "data-k", "0");
      cs.forEach((c) => initAttr(c, "data-k", "0"));
      tl.set(field, { attr: { "data-k": "1" } }, o.focus ?? Math.max(0, t - 0.001));
      cs.forEach((c, i) => {
        const ti = t + i / cps;
        tl.fromTo(c, { opacity: 0 }, { opacity: 1, duration: 0.001, ease: "none" }, ti);
        tl.set(c, { attr: { "data-k": "1" } }, ti);
        tl.set(i ? cs[i - 1] : field, { attr: { "data-k": "0" } }, ti);
        if (i === 0 && ph) tl.set(ph, { opacity: 0 }, ti);
      });
      if (o.blur !== undefined && cs.length) tl.set(cs[cs.length - 1], { attr: { "data-k": "0" } }, o.blur);
      const send = box.querySelector(".cl-send"), voice = box.querySelector(".cl-voice");
      if (send && o.send !== false) {
        if (voice) {
          tl.to(voice, { opacity: 0, duration: 0.08 }, t);
          tl.fromTo(send, { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.2, ease: "back.out(2.5)" }, t);
        } else tl.fromTo(send, { opacity: 0.4 }, { opacity: 1, duration: 0.12 }, t);
      }
      return tl;
    },
    composerDur(sel, text, cps = 30) {
      if (text !== null && text !== undefined) return text.length / cps;
      const box = one(sel), txt = box.querySelector(".cl-text") || box;
      return txt.textContent.length / cps;
    },

    // ---------- Claude Code terminal ----------
    termLines(tl, sel, t, o = {}) {
      // reveals terminal lines in order (o.gap apart, a line's data-dt overrides its delay, o.times sets all)
      // and scrolls the .cl-scroll content up inside .cl-term-body whenever a line lands below the fold
      AR.clIcons();
      const lines = all(sel);
      if (!lines.length) return tl;
      const scroller = lines[0].closest(".cl-scroll"), view = scroller && scroller.parentElement;
      const pad = o.pad ?? 18;
      if (scroller && scroller._clScroll === undefined) { scroller._clScroll = 0; scroller.setAttribute("data-layout-allow-occlusion", ""); }
      let at = t;
      lines.forEach((ln, i) => {
        if (i > 0) at += ln.dataset.dt !== undefined ? +ln.dataset.dt : (o.gap ?? 0.12);
        const ti = o.times ? o.times[i] : at;
        tl.fromTo(ln, { opacity: 0 }, { opacity: 1, duration: o.fade ?? 0.05, ease: "none" }, ti);
        if (scroller && o.scroll !== false) {
          let top = 0, e = ln;
          while (e && e !== scroller) { top += e.offsetTop; e = e.offsetParent; }
          const need = top + ln.offsetHeight + pad - view.clientHeight;
          if (need > scroller._clScroll + 1) {
            tl.to(scroller, { y: -need, duration: o.sdur ?? 0.16, ease: "power2.out" }, ti);
            scroller._clScroll = need;
          }
        }
      });
      return tl;
    },
    clScroll(tl, sel, t, y, o = {}) {
      // scrolls a .cl-scroll (terminal) or a .cl-flow / .cl-doc (chat, doc) to y px from its top, continuing
      // from wherever AR.termLines left it (they share the position). y can be an element inside it: its top
      // lands o.offset px (default 16) below the view's top. For generic pages use motion.js's AR.scrollTo.
      const el = one(sel);
      let to = y;
      if (typeof y !== "number") {
        let top = 0, e = one(y);
        while (e && e !== el) { top += e.offsetTop; e = e.offsetParent; }
        to = top - (o.offset ?? 16);
      }
      to = Math.max(0, to);
      el._clScroll = to;
      el.setAttribute("data-layout-allow-occlusion", "");
      return tl.to(el, { y: -to, duration: o.dur ?? 0.3, ease: o.ease ?? "power2.inOut" }, t);
    },
    status(tl, sel, t, dur, o = {}) {
      // spinner glyph cycles (o.fps, default 8) while .cl-secs ticks o.secs [from, to] and .cl-tok counts
      // o.tokens [from, to] (thousands, one decimal, as Claude Code shows "↓ 1.8k tokens"). At t + dur the line
      // stops and greys out (o.stop: false keeps it running coral)
      AR.clIcons();
      const el = one(sel);
      const g = el.querySelector(".cl-glyph"), fps = o.fps ?? 8, seq = [0, 1, 2, 3, 4, 5, 4, 3, 2, 1];
      if (g) {
        initAttr(g, "data-f", "0");
        const n = Math.ceil(dur * fps);
        for (let i = 0; i <= n; i++) tl.set(g, { attr: { "data-f": String(seq[i % seq.length]) } }, t + i / fps);
      }
      const secs = el.querySelector(".cl-secs"), tok = el.querySelector(".cl-tok");
      if (secs && o.secs) {
        const [a, b] = o.secs;
        secs.textContent = String(a);
        for (let s = a + 1; s <= b; s++) tl.set(secs, { textContent: String(s) }, t + ((s - a) / (b - a)) * dur);
      }
      if (tok && o.tokens) countSets(tl, tok, t, dur, o.tokens[0], o.tokens[1], (v) => v.toFixed(1), 12, (x) => x);
      if (o.stop !== false) { initAttr(el, "data-done", "0"); tl.set(el, { attr: { "data-done": "1" } }, t + dur); }
      return tl;
    },
    checklist(tl, sel, t, o = {}) {
      // terminal todos (.cl-todo): row i turns done (green tick, grey strike) at t + i * gap and the next row
      // turns active (bold, coral square). Doc checklist (.cl-check): unticked rows tick in order and the
      // .cl-ready counter ("<b>N</b> of M ready") counts up, turning green with a tick at M of M.
      AR.clIcons();
      const root = one(sel);
      const rows = root.matches(".cl-todo, .cl-check") ? all(sel) : all(".cl-todo, .cl-check", root);
      const gap = o.gap ?? 0.14;
      if (!rows.length) return tl;
      if (rows[0].matches(".cl-todo")) {
        // rows already marked data-state="done" in the HTML stay done; the rest tick in order
        const todo = rows.filter((r) => r.getAttribute("data-state") !== "done");
        todo.forEach((r) => initAttr(r, "data-state", ""));
        todo.forEach((r, i) => {
          const ti = o.times ? o.times[i] : t + i * gap;
          tl.set(r, { attr: { "data-state": "done" } }, ti);
          const x = r.querySelector(".cl-x");
          if (x) tl.fromTo(x, { scaleX: 0 }, { scaleX: 1, duration: 0.12, ease: "power2.out" }, ti);
          if (o.active !== false && todo[i + 1]) tl.set(todo[i + 1], { attr: { "data-state": "active" } }, ti);
        });
        return tl;
      }
      const list = rows[0].closest(".cl-checks") || root;
      const ready = list.querySelector(".cl-ready"), num = ready && ready.querySelector("b");
      rows.forEach((r) => initAttr(r, "data-on", "0"));
      if (ready) initAttr(ready, "data-done", "0");
      let done = rows.filter((r) => r.getAttribute("data-on") === "1").length;
      if (num) num.textContent = String(done);
      rows.filter((r) => r.getAttribute("data-on") !== "1").forEach((r, i) => {
        const ti = o.times ? o.times[i] : t + i * gap;
        tl.set(r, { attr: { "data-on": "1" } }, ti);
        const box = r.querySelector(".cl-box");
        if (box) { tl.set(box, { scale: 0.78 }, ti); tl.to(box, { scale: 1, duration: 0.2, ease: "back.out(3)" }, ti); }
        done++;
        if (num) tl.set(num, { textContent: String(done) }, ti);
        if (ready && done === rows.length) tl.set(ready, { attr: { "data-done": "1" } }, ti + 0.06);
      });
      return tl;
    },
    clBars(tl, sel, t, o = {}) {
      // bars (terminal .cl-bars or a doc .cl-hchart): every .cl-bar (data-v value) grows to data-v / max of
      // o.len px while its <em> label counts up in its own format ("22.04%"). max = o.max or the largest
      // data-v; len = o.len, else the chart's .cl-axis width (so max lands on the axis end), else 330
      const bars = all(sel).flatMap((el) => (el.matches(".cl-bar") ? [el] : all(".cl-bar", el)));
      if (!bars.length) return tl;
      const max = o.max ?? Math.max(...bars.map((b) => +b.dataset.v));
      const axis = bars[0].parentElement.querySelector(":scope > .cl-axis");
      const len = o.len ?? (axis ? axis.clientWidth : 330), dur = o.dur ?? 0.45;
      bars.forEach((b, i) => {
        const ti = t + i * (o.gap ?? 0.07), fill = b.querySelector("i"), em = b.querySelector("em");
        tl.fromTo(fill, { width: 0 }, { width: (+b.dataset.v / max) * len, duration: dur, ease: "power2.out" }, ti);
        if (em) { const f = fmtOf(em.textContent); countSets(tl, em, ti, dur, 0, f.v, (v) => fmtNum(v, f)); }
      });
      return tl;
    },

    // ---------- chat parts ----------
    clSpark(tl, sel, t, dur, o = {}) {
      // the coral starburst turns while Claude works (o.turns, default a quarter turn per second)
      AR.clIcons();
      const svgs = all(sel).map((el) => el.querySelector("svg") || el);
      return tl.fromTo(svgs, { rotation: 0, transformOrigin: "50% 50%" },
        { rotation: (o.turns ?? dur * 0.25) * 360, duration: dur, ease: "none" }, t);
    },
    clSteps(tl, sel, t, o = {}) {
      // tool-step rail: each .cl-step fades up in order (o.gap, o.times); a .cl-rail inside a step draws down
      // from the step above as it lands
      AR.clIcons();
      const root = one(sel);
      const steps = root.matches(".cl-step") ? all(sel) : all(".cl-step", root);
      steps.forEach((s, i) => {
        const ti = o.times ? o.times[i] : t + i * (o.gap ?? 0.3);
        tl.fromTo(s, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.22, ease: "power2.out" }, ti);
        const rail = s.querySelector(":scope > .cl-rail");
        if (rail) tl.fromTo(rail, { scaleY: 0 }, { scaleY: 1, duration: 0.2, ease: "power1.out" }, ti);
      });
      return tl;
    },
    clRows(tl, sel, t, o = {}) {
      // table or list rows populate one by one (Jake's rate: 0.07 s apart). Table rows (<tr>) only fade:
      // transforms on table rows are unreliable, so they never get one.
      all(sel).forEach((el, i) => {
        const from = el.tagName === "TR" ? { opacity: 0 } : { opacity: 0, y: o.dy ?? 10 };
        const to = el.tagName === "TR" ? { opacity: 1 } : { opacity: 1, y: 0 };
        tl.fromTo(el, from, { ...to, duration: o.dur ?? 0.2, ease: "power2.out" }, t + i * (o.gap ?? 0.07));
      });
      return tl;
    },
    clToggle(tl, sel, t, o = {}) {
      // a .cl-switch (or a chip holding one) flips on: knob slides, track turns blue; .cl-off/.cl-on labels swap
      AR.clIcons();
      all(sel).forEach((el) => {
        const sw = el.matches(".cl-switch") ? el : el.querySelector(".cl-switch");
        const knob = sw.querySelector("i");
        const travel = sw.clientWidth - knob.offsetWidth - 2 * knob.offsetLeft;
        tl.to(knob, { x: travel, duration: 0.22, ease: "power3.inOut" }, t);
        tl.to(sw, { backgroundColor: o.color ?? "#3b7ee6", duration: 0.18, ease: "none" }, t);
        const on = el.querySelector(".cl-on"), off = el.querySelector(".cl-off");
        if (off) tl.to(off, { opacity: 0, duration: 0.06 }, t + 0.12);
        if (on) tl.fromTo(on, { opacity: 0 }, { opacity: 1, duration: 0.1 }, t + 0.12);
      });
      return tl;
    },
    clUnderline(tl, sel, t, dur = 0.32) {
      // the green underline draws under a .cl-ul phrase
      AR.clIcons();
      return tl.fromTo(all(sel).map((el) => el.querySelector(".cl-uline") || el), { scaleX: 0 },
        { scaleX: 1, duration: dur, ease: "power2.inOut" }, t);
    },
    clSplit(tl, sel, t, o = {}) {
      // opens the split view: the chat column narrows to o.to (default "37%") as the artifact pane comes in
      // from the right. o.dur 0 cuts straight to it. Lay the app out as .cl-app.cl-split with style
      // "--cl-chat-w: 100%" so the pane starts off-screen.
      const app = one(sel), pane = app.querySelector(":scope > .cl-pane");
      const to = o.to ?? "37%", dur = o.dur ?? 0.32;
      if (pane) tl.fromTo(pane, { opacity: 0 }, { opacity: 1, duration: Math.min(dur, 0.12) || 0.001, ease: "none" }, t);
      if (!dur) return tl.set(app, { "--cl-chat-w": to }, t);
      return tl.to(app, { "--cl-chat-w": to, duration: dur, ease: o.ease ?? "power3.inOut" }, t);
    },
    clFocus(tl, sel, t, o = {}) {
      // split view -> the doc alone: the chat column slides out left, the pane widens to the whole window,
      // its header and toolbar leave, and the .cl-doc scales to o.scale (default 1.45) at offset o.x, o.y px.
      // Sizes are read when the move starts, so a density cut before it (font-size set) is accounted for.
      const app = one(sel);
      const chat = app.querySelector(":scope > .cl-main"), pane = app.querySelector(":scope > .cl-pane");
      const doc = pane.querySelector(".cl-doc"), body = pane.querySelector(".cl-pane-body");
      const dur = o.dur ?? 0.5, ease = o.ease ?? "power3.inOut";
      const bars = all(".cl-pane-top, .cl-pane-tools", pane);
      const lift = () => bars.reduce((h, b) => h + b.offsetHeight, 0);
      if (doc && !doc.style.width) doc.style.width = doc.offsetWidth + "px"; // the doc keeps its line breaks
      if (chat) tl.to(chat, { x: () => -chat.offsetWidth, duration: dur, ease }, t);
      tl.to(pane, { left: 0, width: () => app.clientWidth, duration: dur, ease }, t);
      if (bars.length) tl.to(bars, { y: () => -lift(), opacity: 0, duration: dur * 0.8, ease }, t);
      if (body) tl.to(body, { marginTop: () => -lift(), duration: dur, ease }, t); // the body grows into the freed space
      if (doc) tl.to(doc, { scale: o.scale ?? 1.45, x: o.x ?? 0, y: o.y ?? 0, duration: dur, ease }, t);
      return tl;
    },

    // ---------- dialogs, slides, usage, dashboard ----------
    clAllow(tl, sel, t, o = {}) {
      // the Allow once button (or Deny with o.deny) presses, the dialog folds away, o.result fades up in its place
      // (put the dialog and the result in a .cl-swapstack so they share one spot)
      const dlg = one(sel), btn = dlg.querySelector(o.deny ? ".cl-deny" : ".cl-allow");
      if (btn) {
        tl.to(btn, { scale: 0.95, duration: 0.07, ease: "power2.out" }, t);
        tl.to(btn, { scale: 1, duration: 0.16, ease: "back.out(3)" }, t + 0.07);
      }
      tl.to(dlg, { opacity: 0, scale: 0.97, y: -8, duration: 0.16, ease: "power2.in" }, t + (o.hold ?? 0.16));
      if (o.result) tl.fromTo(o.result, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.24, ease: "power3.out" }, t + (o.hold ?? 0.16) + 0.1);
      return tl;
    },
    clSlide(tl, sel, t, i, o = {}) {
      // slides editor: the main slide cuts to .cl-slide i and the blue selection ring jumps to thumbnail
      // o.thumb (default i). The first call also places the ring on the .cl-thumb.on.
      AR.clIcons();
      const root = one(sel), th = o.thumb ?? i;
      const slides = all(".cl-slide", root), thumbs = all(".cl-thumb", root), ring = root.querySelector(".cl-thumb-ring");
      slides.forEach((s, k) => tl.set(s, { opacity: k === i ? 1 : 0 }, t));
      if (ring && thumbs[th]) {
        if (!ring.dataset.clBase) {
          const on = Math.max(0, thumbs.findIndex((x) => x.classList.contains("on")));
          ring.dataset.clBase = String(thumbs[on].offsetLeft);
          Object.assign(ring.style, { left: thumbs[on].offsetLeft + "px", top: thumbs[on].offsetTop + "px" });
        }
        tl.to(ring, { x: thumbs[th].offsetLeft - +ring.dataset.clBase, duration: o.dur ?? 0.1, ease: "power3.out" }, t);
      }
      if (o.punch !== false && slides[i]) {
        tl.set(slides[i].parentElement, { scale: 1.025 }, t);
        tl.to(slides[i].parentElement, { scale: 1, duration: 0.22, ease: "power2.out" }, t);
      }
      return tl;
    },
    clUsage(tl, sel, t, dur = 0.8, o = {}) {
      // usage meters (.cl-meter data-from data-to, in %): the blue bar fills and its .cl-pct counts
      const meters = all(sel).flatMap((el) => (el.matches(".cl-meter") ? [el] : all(".cl-meter", el)));
      meters.forEach((m, i) => {
        const ti = t + i * (o.gap ?? 0.12), a = +(m.dataset.from ?? 0), b = +m.dataset.to;
        tl.fromTo(m.querySelector(".cl-track i"), { scaleX: a / 100 }, { scaleX: b / 100, duration: dur, ease: "power2.out" }, ti);
        const pct = m.querySelector(".cl-pct");
        if (pct) countSets(tl, pct, ti, dur, a, b, (v) => String(Math.round(v)));
      });
      return tl;
    },
    clTab(tl, sel, t, i) {
      // a .cl-tabs strip switches to tab i: its label lights, its .cl-tabpane shows (an instant cut, as the app does)
      const root = one(sel);
      all(".cl-tab", root).forEach((tb, k) => {
        initAttr(tb, "data-on", tb.classList.contains("on") ? "1" : "0");
        tl.set(tb, { attr: { "data-on": k === i ? "1" : "0" } }, t);
      });
      all(".cl-tabpane", root).forEach((p, k) => tl.set(p, { opacity: k === i ? 1 : 0 }, t));
      return tl;
    },
    clTodo(tl, sel, t) {
      // a dashboard to-do (.cl-dtodo) checks: green box with a tick, the text strikes and greys, and the
      // list's .cl-dfoot recounts ("2 open · 2 done"). Call in time order.
      AR.clIcons();
      const row = one(sel);
      initAttr(row, "data-on", "0");
      tl.set(row, { attr: { "data-on": "1" } }, t);
      const box = row.querySelector(".cl-box"), x = row.querySelector(".cl-x");
      if (box) { tl.set(box, { scale: 0.78 }, t); tl.to(box, { scale: 1, duration: 0.2, ease: "back.out(3)" }, t); }
      if (x) tl.fromTo(x, { scaleX: 0 }, { scaleX: 1, duration: 0.18, ease: "power2.out" }, t + 0.02);
      const list = row.parentElement, foot = list.querySelector(".cl-dfoot");
      if (foot) {
        const rows = all(".cl-dtodo", list);
        if (list._clDone === undefined) list._clDone = rows.filter((r) => r.getAttribute("data-on") === "1").length;
        list._clDone++;
        tl.set(foot, { textContent: `${rows.length - list._clDone} open · ${list._clDone} done` }, t);
      }
      return tl;
    },
    clReply(tl, sel, t, o = {}) {
      // a dashboard message's Reply button presses and its .cl-dreply field opens under it (rows below move
      // down) with a focus ring; o.text types into it from t + 0.3
      AR.clIcons();
      const row = one(sel), btn = row.querySelector(".cl-dbtn"), rep = row.querySelector(".cl-dreply");
      if (btn) {
        tl.to(btn, { scale: 0.92, duration: 0.07, ease: "power2.out" }, t);
        tl.to(btn, { scale: 1, duration: 0.18, ease: "back.out(3)" }, t + 0.07);
      }
      if (rep) {
        const h = o.h ?? 52;
        tl.fromTo(rep, { height: 0, opacity: 0, marginTop: 0 }, { height: h, opacity: 1, marginTop: 8, duration: 0.22, ease: "power2.out" }, t + 0.06);
        if (o.text) AR.composer(tl, rep, t + 0.32, o.text, { cps: o.cps ?? 28, send: false });
        else if (rep.querySelector(".cl-field")) {
          const f = rep.querySelector(".cl-field");
          initAttr(f, "data-k", "0");
          tl.set(f, { attr: { "data-k": "1" } }, t + 0.2);
        }
      }
      return tl;
    },
  });
})();
