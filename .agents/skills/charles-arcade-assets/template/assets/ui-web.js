/* ui-web.js: web, social and device UI helpers for the arcade kit (classes in ui-web.css, all .wb-).
   Every helper takes the timeline first and a scene time in seconds, and is seek-safe: tweens only, no clock,
   no callbacks, no Math.random. Call helpers for one element in time order (each move starts where the last
   one ended). AR.webInit(root) fills <i data-i="name"> icons, img[data-ph] placeholders, empty .wb-cursor
   elements and the select overlays of .wb-ig-tile; AR.names() runs it too, so a scene that starts with
   AR.names() needs nothing else. */
(function () {
  const AR = (window.AR = window.AR || {});
  const all = (sel, root) => {
    if (!sel) return [];
    if (typeof sel !== "string") return sel.nodeType ? [sel] : Array.from(sel);
    return Array.from((root || document).querySelectorAll(sel));
  };
  const one = (sel, root) => all(sel, root)[0];
  const rnd = (seed) => () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const hash = (s) => { let h = 2166136261; for (const c of String(s)) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return h >>> 0; };
  const fmt = (v) => Math.round(+v).toLocaleString("en-US");

  // ---------- icons: <i data-i="name"></i> ----------
  const s = (d, w) => `<path class="s" d="${d}"${w ? ` stroke-width="${w}"` : ""}/>`;
  const f = (d) => `<path class="f" d="${d}"/>`;
  const HEART = "M12 20.6l-1.2-1.1C5.6 14.8 2.6 12.1 2.6 8.7A4.7 4.7 0 0 1 7.3 4c1.8 0 3.5.9 4.7 2.3C13.2 4.9 14.9 4 16.7 4a4.7 4.7 0 0 1 4.7 4.7c0 3.4-3 6.1-8.2 10.8z";
  const STAR = "M12 3.3l2.7 5.5 6 .9-4.35 4.25 1 6L12 17.1l-5.4 2.85 1-6L3.3 9.7l6-.9z";
  const badge = (() => { let d = ""; for (let i = 0; i < 32; i++) { const a = (i / 32) * Math.PI * 2, r = i % 2 ? 9.7 : 11.2; d += (i ? "L" : "M") + (12 + r * Math.sin(a)).toFixed(2) + " " + (12 - r * Math.cos(a)).toFixed(2); } return d + "z"; })();
  const ICONS = {
    back: s("M19 12H5M11.5 18.5L5 12l6.5-6.5"), fwd: s("M5 12h14M12.5 5.5L19 12l-6.5 6.5"),
    reload: s("M19.5 12a7.5 7.5 0 1 1-2.2-5.3") + f("M20.5 3.8v5.7h-5.7z"), x: s("M6 6l12 12M18 6L6 18"),
    plus: s("M12 5v14M5 12h14"), minus: s("M5 12h14"), check: s("M4.5 12.5l5 5 10-11", 2.6),
    tune: s("M4 8h8.5M16.5 8H20M4 16h3.5M11.5 16H20") + `<circle class="s" cx="14.5" cy="8" r="2"/><circle class="s" cx="9.5" cy="16" r="2"/>`,
    star: s(STAR, 1.8), "star-f": f(STAR), heart: s(HEART, 2), "heart-f": f(HEART),
    puzzle: s("M9.5 5a2.5 2.5 0 1 1 5 0v1.5H18V10h-1.5a2.5 2.5 0 1 0 0 5H18v3.5h-3.5V17a2.5 2.5 0 1 0-5 0v1.5H6V15h1.5a2.5 2.5 0 1 0 0-5H6V6.5h3.5z", 1.8),
    kebab: `<circle class="f" cx="12" cy="5" r="1.9"/><circle class="f" cx="12" cy="12" r="1.9"/><circle class="f" cx="12" cy="19" r="1.9"/>`,
    "more-h": `<circle class="f" cx="5" cy="12" r="1.9"/><circle class="f" cx="12" cy="12" r="1.9"/><circle class="f" cx="19" cy="12" r="1.9"/>`,
    search: `<circle class="s" cx="10.8" cy="10.8" r="6.3"/>` + s("M20 20l-4.6-4.6"),
    eye: s("M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z") + `<circle class="s" cx="12" cy="12" r="3"/>`,
    fork: `<circle class="s" cx="6" cy="5" r="2"/><circle class="s" cx="18" cy="5" r="2"/><circle class="s" cx="12" cy="19" r="2"/>` + s("M6 7v1.5A2.5 2.5 0 0 0 8.5 11h7A2.5 2.5 0 0 0 18 8.5V7M12 11v6"),
    issue: `<circle class="s" cx="12" cy="12" r="8.5"/><circle class="f" cx="12" cy="12" r="1.9"/>`,
    pr: `<circle class="s" cx="6" cy="6" r="2"/><circle class="s" cx="6" cy="18" r="2"/><circle class="s" cx="18" cy="18" r="2"/>` + s("M6 8v8M18 16V9.5a3 3 0 0 0-3-3h-4M13 3.8L10.5 6.5 13 9.2"),
    actions: `<circle class="s" cx="12" cy="12" r="8.5"/>` + f("M10 8.4v7.2l5.6-3.6z"), code: s("M8.5 7L3.5 12l5 5M15.5 7l5 5-5 5"),
    folder: f("M2.5 6.5a2 2 0 0 1 2-2h4.3l2.1 2.2h8.6a2 2 0 0 1 2 2v9.8a2 2 0 0 1-2 2h-15a2 2 0 0 1-2-2z"),
    file: s("M6.5 3h7l4 4v14h-11z") + s("M13.5 3v4h4"), book: s("M4 19V5.5A2.5 2.5 0 0 1 6.5 3H20v14H6.5A2.5 2.5 0 0 0 4 19.5 2.5 2.5 0 0 0 6.5 22H20"),
    law: s("M12 4v16M8 20h8M5 7h14M5 7l-3 6.2a3 3 0 0 0 6 0zM19 7l-3 6.2a3 3 0 0 0 6 0z", 1.7),
    link: s("M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"),
    history: s("M3.5 12a8.5 8.5 0 1 0 2.5-6M3.5 4v4h4M12 7.5V12l3 2"),
    comment: s("M20.4 16.9A9 9 0 1 0 17.1 20.4L21.5 21.5z"), send: s("M21.5 3L10.2 13.8M21.5 3l-6.9 18-4.4-7.2L3 9.6z"),
    repost: s("M17 3l3 3-3 3M20 6H8a4 4 0 0 0-4 4v1M7 21l-3-3 3-3M4 18h12a4 4 0 0 0 4-4v-1"), bookmark: s("M6 3.5h12v17l-6-4.5-6 4.5z"),
    camera: s("M3 8.5a2 2 0 0 1 2-2h2.5L9 4h6l1.5 2.5H19a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z") + `<circle class="s" cx="12" cy="13" r="3.8"/>`,
    music: s("M9 18V5.5l11-2V16") + `<circle class="s" cx="6.5" cy="18" r="2.5"/><circle class="s" cx="17.5" cy="16" r="2.5"/>`,
    play: f("M7 4.5v15l12.5-7.5z"),
    "check-c": `<circle class="f" cx="12" cy="12" r="10"/><path d="M7.4 12.3l3.1 3.1 6.2-6.4" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`,
    verified: f(badge) + `<path d="M8 12.2l2.7 2.7 5.4-5.6" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>`,
    grid: `<rect class="s" x="3.5" y="3.5" width="17" height="17" rx="1"/>` + s("M9.2 3.5v17M14.8 3.5v17M3.5 9.2h17M3.5 14.8h17"),
    reels: `<rect class="s" x="3.5" y="3.5" width="17" height="17" rx="4"/>` + s("M3.5 8.5h17M8.5 3.5l3 5M14 3.5l3 5") + f("M10.2 11.4v5.4l4.6-2.7z"),
    tagged: s("M4 4.5h16v13h-5l-3 3-3-3H4z") + `<circle class="s" cx="12" cy="9.5" r="2.2"/>` + s("M8 16c.6-1.8 2.1-2.8 4-2.8s3.4 1 4 2.8"),
    signal: `<rect class="f" x="2" y="15" width="3.6" height="5" rx="1"/><rect class="f" x="7.2" y="11.6" width="3.6" height="8.4" rx="1"/><rect class="f" x="12.4" y="8" width="3.6" height="12" rx="1"/><rect class="f" x="17.6" y="4.2" width="3.6" height="15.8" rx="1"/>`,
    wifi: f("M12 20.6l-3.6-3.9a5.1 5.1 0 0 1 7.2 0z") + `<path d="M5.7 13.4a8.9 8.9 0 0 1 12.6 0M2.4 10a13.6 13.6 0 0 1 19.2 0" fill="none" stroke="currentColor" stroke-width="2.7" stroke-linecap="round"/>`,
    battery: `<rect x="1.5" y="6.8" width="19" height="10.4" rx="3.2" fill="none" stroke="currentColor" stroke-opacity=".42" stroke-width="1.3"/><rect class="f" x="3.3" y="8.6" width="15.4" height="6.8" rx="1.7"/><path class="f" opacity=".45" d="M21.8 10.2v3.6c.8-.3 1.2-1 1.2-1.8s-.4-1.5-1.2-1.8z"/>`,
    flashlight: f("M8 2.5h8v3.3l-2 3.2V21.5h-4V9L8 5.8z"),
    archive: `<rect class="s" x="3" y="4" width="18" height="4.5" rx="1"/>` + s("M4.5 8.5v10A1.5 1.5 0 0 0 6 20h12a1.5 1.5 0 0 0 1.5-1.5v-10M10 12.5h4"),
    menu: s("M4 7h16M4 12h16M4 17h16"), "chev-d": s("M6.5 9.5l5.5 5.5 5.5-5.5"), "chev-u": s("M6.5 14.5L12 9l5.5 5.5"),
    "chev-l": s("M14.5 5.5L8 12l6.5 6.5"), "chev-r": s("M9.5 5.5L16 12l-6.5 6.5"), caret: f("M6.5 9.5h11L12 15.5z"),
    mic: `<rect class="s" x="9" y="3" width="6" height="11" rx="3"/>` + s("M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"),
    video: `<rect class="s" x="3" y="6.5" width="12.5" height="11" rx="2"/>` + s("M15.5 10.5l5.5-3v9l-5.5-3z"),
    cc: `<rect class="s" x="3" y="5.5" width="18" height="13" rx="2"/>` + s("M10.5 10.3a2.3 2.3 0 1 0 0 3.4M17 10.3a2.3 2.3 0 1 0 0 3.4"),
    emoji: `<circle class="s" cx="12" cy="12" r="8.5"/>` + s("M8.5 14.3a4 4 0 0 0 7 0") + `<circle class="f" cx="9" cy="10" r="1.1"/><circle class="f" cx="15" cy="10" r="1.1"/>`,
    present: `<rect class="s" x="3" y="4.5" width="18" height="13" rx="2"/>` + s("M12 14V8.6M9.3 11.2L12 8.5l2.7 2.7M8 21h8"),
    hand: s("M8 13V6.5a1.5 1.5 0 0 1 3 0V12M11 11V4.5a1.5 1.5 0 0 1 3 0V11M14 11V6a1.5 1.5 0 0 1 3 0v8a7 7 0 0 1-7 7h-.5a6 6 0 0 1-4.6-2.2L3.3 15.3a1.5 1.5 0 0 1 2.3-1.9L8 15.5"),
    "phone-x": f("M12 9.5c3.6 0 6.9 1 9.3 2.7.5.4.7 1 .5 1.6l-.8 2.2c-.2.6-.9.9-1.5.7l-3-1c-.5-.2-.8-.6-.8-1.1v-1.5c-1.2-.4-2.4-.6-3.7-.6s-2.5.2-3.7.6v1.5c0 .5-.3.9-.8 1.1l-3 1c-.6.2-1.3-.1-1.5-.7l-.8-2.2c-.2-.6 0-1.2.5-1.6C5.1 10.5 8.4 9.5 12 9.5z"),
    info: `<circle class="s" cx="12" cy="12" r="8.5"/>` + s("M12 11v5.5") + `<circle class="f" cx="12" cy="7.9" r="1.2"/>`,
    "info-f": `<circle class="f" cx="12" cy="12" r="9.5"/><path d="M12 11v5.6" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="7.8" r="1.3" fill="#fff"/>`,
    people: `<circle class="s" cx="9" cy="8" r="3.2"/>` + s("M3 19.5a6 6 0 0 1 12 0M16 4.8a3.2 3.2 0 0 1 0 6.4M18 13.6a6 6 0 0 1 3 5.9"),
    chat: s("M4 5h16v11H9l-5 4z"),
    shapes: `<circle class="s" cx="7.5" cy="7.5" r="3.5"/><rect class="s" x="13.5" y="4" width="7" height="7" rx="1"/>` + s("M7.5 13.5l4 7h-8z") + `<circle class="s" cx="17" cy="17" r="3.5"/>`,
    lock: `<rect class="s" x="5" y="10.5" width="14" height="10" rx="2"/>` + s("M8 10.5V7.5a4 4 0 0 1 8 0v3"),
    attach: s("M20 11.5l-8.2 8.2a5.2 5.2 0 0 1-7.4-7.4l8.6-8.6a3.5 3.5 0 0 1 5 5l-8.5 8.5a1.8 1.8 0 0 1-2.5-2.5l7.8-7.8"),
    image: `<rect class="s" x="3.5" y="3.5" width="17" height="17" rx="2"/><circle class="s" cx="9" cy="9" r="1.8"/>` + s("M20.5 15l-5-5L5 20.5"),
    trash: s("M4 6.5h16M9 6.5V4h6v2.5M6 6.5l1 14h10l1-14M10 10.5v6M14 10.5v6"),
    pen: s("M4 20l1-4.5L16.5 4a2.1 2.1 0 0 1 3 3L8 18.5zM14.5 6l3 3"), font: s("M6 18L11.3 5h1.4L18 18M8.2 13.5h7.6"),
    undo: s("M9 14L4 9l5-5M4 9h10.5a5.5 5.5 0 0 1 0 11H11"), redo: s("M15 14l5-5-5-5M20 9H9.5a5.5 5.5 0 0 0 0 11H13"),
    print: s("M7 8.5V3.5h10v5M7 17H4.5v-8h15v8H17M7 14h10v6.5H7z"),
    paint: `<rect class="s" x="5" y="3.5" width="13" height="5" rx="1"/>` + s("M18 6h2v5h-8v3M11 14h2v6.5h-2z"),
    percent: s("M19 5L5 19") + `<circle class="s" cx="7" cy="7" r="2.3"/><circle class="s" cx="17" cy="17" r="2.3"/>`,
    copy: `<rect class="s" x="8.5" y="8.5" width="12" height="12" rx="2"/>` + s("M15.5 8.5V5.5a2 2 0 0 0-2-2h-8a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h3"),
    sort: s("M8 4v16M4.5 16.5L8 20l3.5-3.5M16 20V4M12.5 7.5L16 4l3.5 3.5"), "arrow-r": s("M5 12h14M13 6l6 6-6 6"),
    expand: s("M14 4h6v6M20 4l-7 7M10 20H4v-6M4 20l7-7"),
    calendar: `<rect class="s" x="3.5" y="5" width="17" height="15.5" rx="2"/>` + s("M3.5 10h17M8 3v4M16 3v4"),
    "folder-move": s("M3.5 7a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v8.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2zM10 13.2h5M13 11l2.2 2.2L13 15.4"),
    cloud: s("M7 18.5a4.5 4.5 0 0 1-.6-9 6 6 0 0 1 11.5 1.5A3.8 3.8 0 0 1 17.5 18.5zM9.5 13.5l2 2 3.5-3.5"),
    apps: [5, 12, 19].map((y) => [5, 12, 19].map((x) => `<circle class="f" cx="${x}" cy="${y}" r="1.9"/>`).join("")).join(""),
    help: `<circle class="s" cx="12" cy="12" r="8.5"/>` + s("M9.6 9.5a2.5 2.5 0 1 1 3.4 2.3c-.7.3-1 .8-1 1.5v.4") + `<circle class="f" cx="12" cy="16.8" r="1.2"/>`,
    gear: `<circle class="s" cx="12" cy="12" r="3"/>` + s("M12 2.8v2.6M12 18.6v2.6M2.8 12h2.6M18.6 12h2.6M5.5 5.5l1.9 1.9M16.6 16.6l1.9 1.9M5.5 18.5l1.9-1.9M16.6 7.4l1.9-1.9"),
    task: `<circle class="s" cx="12" cy="12" r="8.5"/>` + s("M8.3 12.2l2.6 2.6 4.9-5"),
    fx: `<text x="3" y="17.5" font-size="15" font-style="italic" font-family="Georgia, serif" fill="currentColor">fx</text>`,
    bold: s("M7 5h6a3.5 3.5 0 0 1 0 7H7zM7 12h7a3.5 3.5 0 0 1 0 7H7z", 2.4), italic: s("M10 5h8M6 19h8M14.5 5l-5 14"),
    strike: s("M5 12h14M16 7.5C15.4 5.9 13.9 5 12 5c-2.5 0-4 1.4-4 3.1 0 1.2.8 2.2 2.6 2.9M8 16.5c.6 1.6 2.1 2.5 4 2.5 2.5 0 4-1.4 4-3.2"),
    meta: `<path d="M2.6 15.6c0-3.6 1.9-8 4.6-8 3.6 0 6.3 9.7 9.7 9.7 2.1 0 3.3-1.6 3.3-4.4 0-3-1.4-5.3-3.4-5.3-3.6 0-6.2 9.7-9.6 9.7-2.8 0-4.6-1.4-4.6-1.7z" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linejoin="round"/>`,
    fb: `<circle class="f" cx="12" cy="12" r="10"/><path d="M13.2 21v-7.2h2.3l.3-2.6h-2.6V9.6c0-.8.2-1.3 1.3-1.3h1.4V6c-.2 0-1.1-.1-2-.1-2 0-3.4 1.2-3.4 3.5v1.9H8.3v2.6h2.2V21z" fill="#fff"/>`,
    ig: `<rect class="s" x="3" y="3" width="18" height="18" rx="5"/><circle class="s" cx="12" cy="12" r="4.2"/><circle class="f" cx="17.3" cy="6.7" r="1.2"/>`,
    msgr: s("M12 3a9 8.6 0 0 0-5.6 15.3V21l2.7-1.5A9.6 9.6 0 0 0 12 20a9 8.6 0 0 0 0-17z") + s("M6.8 13.6l3.2-3.4 2.2 2.2 3.1-3.3-3.2 3.4-2.2-2.2z", 1.6),
    adbox: `<rect class="s" x="4" y="4" width="16" height="16" rx="2"/>` + s("M4 15h16"),
    "ig-logo": `<rect x="2.5" y="2.5" width="19" height="19" rx="5.5" fill="none" stroke="currentColor" stroke-width="2.2"/><circle cx="12" cy="12" r="4.4" fill="none" stroke="currentColor" stroke-width="2.2"/><circle cx="17.4" cy="6.6" r="1.4" fill="currentColor"/>`,
    gmail: `<path d="M3.6 20h3.3v-8.2L1.9 8v10.3c0 .9.8 1.7 1.7 1.7z" fill="#4285f4"/><path d="M17.1 20h3.3c.9 0 1.7-.8 1.7-1.7V8l-5 3.8z" fill="#34a853"/><path d="M17.1 5.2v6.6l5-3.8V6c0-1.9-2.2-3-3.7-1.9z" fill="#fbbc04"/><path d="M6.9 11.8V5.2L12 9l5.1-3.8v6.6L12 15.6z" fill="#ea4335"/><path d="M1.9 6v2l5 3.8V5.2L5.6 4.1C4.1 3 1.9 4.1 1.9 6z" fill="#c5221f"/>`,
    cal31: `<rect x="3" y="3" width="18" height="18" rx="2.5" fill="#fff" stroke="#4285f4" stroke-width="1.6"/><path d="M3 7.5h18" stroke="#4285f4" stroke-width="3"/><text x="12" y="18.2" font-size="9" font-weight="700" text-anchor="middle" font-family="Arial, sans-serif" fill="#4285f4">31</text>`,
    sheets: `<rect x="2.5" y="2.5" width="19" height="19" rx="4.5" fill="#1ea362"/><rect x="6.5" y="7" width="11" height="10" rx="1.2" fill="#fff"/><path d="M6.5 10.6h11M10.6 7v10" stroke="#1ea362" stroke-width="1.6"/>`,
  };
  const CURSOR =
    `<svg class="wb-arrow" viewBox="0 0 20 29"><path d="M2 2v21.6l5.1-4.9 3.2 7.6 3.6-1.5-3.1-7.4h6.9z" fill="#000" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>` +
    `<svg class="wb-hand" viewBox="0 0 26 28"><path d="M9.6 1.6c1.2 0 2.1.9 2.1 2.1v7.2c.4-.4 1-.6 1.6-.6 1.1 0 2 .8 2.1 1.9.4-.4 1-.6 1.6-.6 1.1 0 2 .8 2.1 1.9.4-.3.9-.4 1.4-.4 1.2 0 2.1.9 2.1 2.1v4.6c0 3.9-3.1 7-7 7h-2.6c-2.2 0-4.3-1-5.6-2.8L2 18.9c-.7-.9-.5-2.2.4-2.9.9-.7 2.1-.5 2.8.3l2.3 2.6V3.7c0-1.2.9-2.1 2.1-2.1z" fill="#fff" stroke="#000" stroke-width="1.3" stroke-linejoin="round"/><path d="M11.7 10.9v4.8M15.4 12.2v3.6M19.1 13.5v2.6" stroke="#000" stroke-width="1.1" stroke-linecap="round"/></svg>`;

  // ---------- placeholders: img[data-ph="kind:text"] until the real image is sourced ----------
  const uri = (svg) => "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  const FONT = `font-family="Helvetica Neue, Helvetica, Arial, sans-serif"`;
  const PAL = ["#e8710a", "#0b8043", "#7b61ff", "#d93025", "#1a73e8", "#b06000", "#12857a", "#a142f4", "#e52592", "#5f6368"];
  const initials = (t) => { const w = String(t).trim().split(/\s+/); return (w.length > 1 && t.length > 2 ? w[0][0] + w[w.length - 1][0] : String(t).slice(0, t.length <= 2 ? 2 : 1)).toUpperCase(); };
  const BRANDS = {
    stripe: ["#635bff", `<path d="M30 62l8-26h28l-8 26z" fill="#fff"/>`],
    shopify: ["#5e8e3e", `<path d="M33 40h30l-3 30H36z" fill="#fff"/><path d="M41 40c0-8 3-12 7-12s7 4 7 12" fill="none" stroke="#fff" stroke-width="4"/><text x="48" y="64" font-size="22" font-weight="800" text-anchor="middle" fill="#5e8e3e" ${FONT}>S</text>`],
    claude: ["#d97757", [0, 22.5, 45, 67.5, 90, 112.5, 135, 157.5].map((a) => `<rect x="45.5" y="22" width="5" height="52" rx="2.5" fill="#fff" transform="rotate(${a} 48 48)"/>`).join("")],
    gmail: ["#ffffff", `<g transform="translate(18 18) scale(2.5)">${ICONS.gmail}</g>`],
    github: ["#1f2328", `<circle cx="48" cy="46" r="21" fill="#fff"/><path d="M37 63c0-6 3-9 11-9s11 3 11 9z" fill="#fff"/><circle cx="41" cy="45" r="3" fill="#1f2328"/><circle cx="55" cy="45" r="3" fill="#1f2328"/>`],
    slack: ["#4a154b", `<text x="48" y="64" font-size="50" font-weight="800" text-anchor="middle" fill="#fff" ${FONT}>#</text>`],
    instagram: ["#d62976", `<rect x="26" y="26" width="44" height="44" rx="13" fill="none" stroke="#fff" stroke-width="5"/><circle cx="48" cy="48" r="10" fill="none" stroke="#fff" stroke-width="5"/>`],
    meta: ["#0866ff", `<g transform="translate(18 16) scale(2.5)" style="color:#fff">${ICONS.meta}</g>`],
    microsoft: ["#ffffff", `<rect x="24" y="24" width="22" height="22" fill="#f25022"/><rect x="50" y="24" width="22" height="22" fill="#7fba00"/><rect x="24" y="50" width="22" height="22" fill="#00a4ef"/><rect x="50" y="50" width="22" height="22" fill="#ffb900"/>`],
    google: ["#ffffff", `<text x="48" y="66" font-size="52" font-weight="700" text-anchor="middle" fill="#4285f4" ${FONT}>G</text>`],
    calendly: ["#006bff", `<circle cx="48" cy="48" r="20" fill="none" stroke="#fff" stroke-width="7" stroke-dasharray="100 26" transform="rotate(40 48 48)"/>`],
  };
  function avatarSVG(text) {
    const c = PAL[hash(text) % PAL.length];
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><rect width="96" height="96" fill="${c}"/><text x="48" y="48" dy=".36em" text-anchor="middle" font-size="${initials(text).length > 1 ? 38 : 46}" font-weight="500" fill="#fff" ${FONT}>${initials(text)}</text></svg>`;
  }
  function personSVG(text) {
    const r = rnd(hash(text)), bg = ["#c9d6e8", "#e8d5c9", "#d2e3d0", "#e3d0e6", "#e9e1c8", "#cfd8dc"][Math.floor(r() * 6)];
    const skin = ["#f1c7a5", "#d9a37e", "#a86f4c", "#7a4b32", "#f3d2b8"][Math.floor(r() * 5)], hair = ["#2b2118", "#5a3a22", "#a7a7a7", "#d9b26a", "#1d1d1d"][Math.floor(r() * 5)];
    const suit = ["#1f2a44", "#3c3c3c", "#6b1f2a", "#24476b", "#2f4f3a"][Math.floor(r() * 5)];
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><rect width="96" height="96" fill="${bg}"/><path d="M14 96c2-20 16-28 34-28s32 8 34 28z" fill="${suit}"/><path d="M41 66h14l-7 12z" fill="#fff"/><circle cx="48" cy="42" r="17" fill="${skin}"/><path d="M30 40c0-12 8-19 18-19s18 6 18 17c-4-6-10-8-18-8s-14 3-18 10z" fill="${hair}"/></svg>`;
  }
  function logoSVG(text) {
    const key = String(text).toLowerCase().replace(/[^a-z]/g, "");
    const b = BRANDS[key];
    if (b) return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><rect width="96" height="96" fill="${b[0]}"/>${b[1]}</svg>`;
    const c = PAL[hash(text) % PAL.length];
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><rect width="96" height="96" fill="${c}"/><text x="48" y="48" dy=".36em" text-anchor="middle" font-size="${initials(text).length > 1 ? 36 : 50}" font-weight="700" fill="#fff" ${FONT}>${initials(text)}</text></svg>`;
  }
  // a small pixel landscape (dusk, night, day, desert, forest): reads as "a photo" in grids and cards, on-style for arcade
  function thumbSVG(seed, W = 27, H = 36) {
    const r = rnd(hash("t" + seed));
    const P = [
      { sky: ["#1b1d4e", "#2d2f78", "#5a3d8f", "#b45a8c", "#f08a6a"], sun: "#ffd27a", far: "#3b2a5e", near: "#1d1530", win: "#ffcf6b" },
      { sky: ["#0b1026", "#141b3d", "#1d2a5c", "#27407a", "#33558f"], sun: "#f4f1d0", far: "#1a2448", near: "#0b1128", win: "#ffd36b" },
      { sky: ["#4fb8f5", "#6cc6f7", "#8fd4f9", "#b4e2fb", "#dcf2fd"], sun: "#fff3b0", far: "#73b27a", near: "#3d7d4a", win: "#e9f6ff" },
      { sky: ["#f2784b", "#f79a5c", "#fbb873", "#fdd39a", "#ffe9c4"], sun: "#fff7e0", far: "#c46b4f", near: "#7a3426", win: "#ffe3a3" },
      { sky: ["#0e2b2a", "#123d38", "#1a5a4d", "#2b7a5f", "#4f9e70"], sun: "#d9f99d", far: "#0f3d33", near: "#082019", win: "#d9f99d" },
    ][Math.floor(r() * 5)];
    let o = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" shape-rendering="crispEdges" preserveAspectRatio="xMidYMid slice">`;
    const band = Math.ceil((H * 0.62) / 5);
    P.sky.forEach((c, i) => (o += `<rect x="0" y="${i * band}" width="${W}" height="${band + 1}" fill="${c}"/>`));
    for (let i = 0; i < 7; i++) o += `<rect x="${Math.floor(r() * W)}" y="${Math.floor(r() * H * 0.35)}" width="1" height="1" fill="#fff" opacity="${(0.4 + r() * 0.5).toFixed(2)}"/>`;
    const sx = 3 + Math.floor(r() * (W - 9)), sy = 4 + Math.floor(r() * 6), sr = 2 + Math.floor(r() * 2);
    for (let y = -sr; y <= sr; y++) { const w = Math.round(Math.sqrt(sr * sr - y * y + 0.5)); o += `<rect x="${sx - w}" y="${sy + y}" width="${2 * w + 1}" height="1" fill="${P.sun}"/>`; }
    let h = Math.floor(H * 0.5);
    for (let x = 0; x < W; x++) { h += Math.floor(r() * 3) - 1; h = Math.max(Math.floor(H * 0.4), Math.min(Math.floor(H * 0.62), h)); o += `<rect x="${x}" y="${h}" width="1" height="${H - h}" fill="${P.far}"/>`; }
    for (let x = 0; x < W;) {
      const w = 2 + Math.floor(r() * 4), top = Math.floor(H * 0.55 + r() * H * 0.18);
      o += `<rect x="${x}" y="${top}" width="${w}" height="${H - top}" fill="${P.near}"/>`;
      for (let wy = top + 2; wy < H - 4; wy += 2) for (let wx = x + 1; wx < x + w - 1; wx += 2) if (r() > 0.55) o += `<rect x="${wx}" y="${wy}" width="1" height="1" fill="${P.win}"/>`;
      x += w;
    }
    o += `<rect x="0" y="${H - 4}" width="${W}" height="4" fill="${P.near}"/></svg>`;
    return o;
  }
  const NAV = (active) => `<rect width="1280" height="84" fill="#fff"/><rect x="48" y="24" width="36" height="36" rx="9" fill="#111"/><path d="M66 31l9 11-9 11-9-11z" fill="#ff6a3d"/>
    <text x="96" y="52" font-size="26" font-weight="700" fill="#111">Scout</text><g font-size="19" fill="#3f3f46"><text x="560" y="49">Product</text><text x="668" y="49">Docs</text>
    <text x="752" y="49"${active ? ` fill="#111" font-weight="600"` : ""}>Pricing</text><text x="852" y="49">Blog</text><text x="1006" y="49">Sign in</text></g>
    <rect x="1094" y="24" width="140" height="38" rx="19" fill="#111"/><text x="1164" y="49" font-size="17" font-weight="600" fill="#fff" text-anchor="middle">Get started</text><rect y="84" width="1280" height="1" fill="#ececec"/>`;
  const SHOTS = {
    landing: () => {
      let rows = "";
      const names = [["@badalee__", "#e52592", 0.92, "22.4M"], ["@zachking", "#1a73e8", 0.78, "18.1M"], ["@mrbeast", "#12857a", 0.64, "14.9M"], ["@opusjake", "#d97757", 0.5, "9.6M"], ["@khaby.lame", "#7b61ff", 0.41, "7.2M"]];
      names.forEach(([n, c, w, v], i) => {
        const y = 704 + i * 74;
        rows += `<text x="410" y="${y + 30}" font-size="18" fill="#a1a1aa">${i + 1}</text><circle cx="452" cy="${y + 24}" r="17" fill="${c}"/><text x="482" y="${y + 31}" font-size="19" font-weight="600" fill="#18181b">${n}</text>
          <rect x="640" y="${y + 15}" width="${Math.round(330 * w)}" height="18" rx="9" fill="#ffe1d6"/><rect x="640" y="${y + 15}" width="${Math.round(330 * w * 0.82)}" height="18" rx="9" fill="#ff7a45"/>
          <text x="1090" y="${y + 31}" font-size="19" font-weight="600" fill="#18181b" text-anchor="end">${v}</text><rect x="400" y="${y + 58}" width="700" height="1" fill="#ececec"/>`;
      });
      const feat = [["Hook finder", "Every opening line ranked by", "the views it earned."], ["Format map", "See which formats a creator", "repeats, and how often."], ["Weekly brief", "A one-page plan for your", "next ten posts."]];
      let fx = "";
      feat.forEach(([t, a, b], i) => { const x = 150 + i * 340; fx += `<rect x="${x}" y="1306" width="52" height="52" rx="13" fill="#fff1eb"/><circle cx="${x + 26}" cy="1332" r="10" fill="none" stroke="#ff5a1f" stroke-width="4"/><text x="${x}" y="1396" font-size="24" font-weight="700" fill="#18181b">${t}</text><text x="${x}" y="1428" font-size="18" fill="#71717a">${a}</text><text x="${x}" y="1452" font-size="18" fill="#71717a">${b}</text>`; });
      return `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="1500" viewBox="0 0 1280 1500" ${FONT}><rect width="1280" height="1500" fill="#fff"/>${NAV(false)}
        <rect x="474" y="136" width="332" height="38" rx="19" fill="#fff4ef" stroke="#ffd2bf"/><text x="640" y="161" font-size="17" fill="#c2410c" text-anchor="middle">New · Scout 2.0 reads Reels too →</text>
        <text x="640" y="262" font-size="74" font-weight="800" fill="#0b0b0f" text-anchor="middle" letter-spacing="-2">Find the hooks behind</text>
        <text x="640" y="346" font-size="74" font-weight="800" fill="#0b0b0f" text-anchor="middle" letter-spacing="-2">every viral post.</text>
        <text x="640" y="410" font-size="24" fill="#52525b" text-anchor="middle">Paste any creator's link. Scout studies their top posts</text>
        <text x="640" y="442" font-size="24" fill="#52525b" text-anchor="middle">and hands you the playbook in minutes.</text>
        <rect x="462" y="482" width="176" height="56" rx="28" fill="#ff5a1f"/><text x="550" y="517" font-size="20" font-weight="600" fill="#fff" text-anchor="middle">Try it free</text>
        <rect x="654" y="482" width="164" height="56" rx="28" fill="#fff" stroke="#d4d4d8" stroke-width="1.5"/><text x="736" y="517" font-size="20" font-weight="600" fill="#18181b" text-anchor="middle">Watch demo</text>
        <rect x="150" y="590" width="980" height="520" rx="18" fill="#fff" stroke="#e4e4e7" stroke-width="1.5"/><rect x="151" y="591" width="978" height="46" rx="17" fill="#fafafa"/>
        <circle cx="178" cy="614" r="6" fill="#ff5f57"/><circle cx="198" cy="614" r="6" fill="#febc2e"/><circle cx="218" cy="614" r="6" fill="#28c840"/><rect x="150" y="637" width="980" height="1" fill="#e4e4e7"/>
        <rect x="151" y="638" width="220" height="471" fill="#fafafa"/><rect x="370" y="638" width="1" height="471" fill="#e4e4e7"/>
        <g font-size="18" fill="#52525b"><rect x="166" y="660" width="190" height="36" rx="8" fill="#fff1eb"/><text x="182" y="684" fill="#c2410c" font-weight="600">Top hooks</text><text x="182" y="730">Creators</text><text x="182" y="772">Formats</text><text x="182" y="814">Weekly brief</text><text x="182" y="856">Settings</text></g>
        <text x="400" y="682" font-size="22" font-weight="700" fill="#18181b">Top hooks this week</text>${rows}
        <text x="640" y="1180" font-size="17" fill="#71717a" text-anchor="middle">Trusted by 4,000+ creators and teams</text>
        <g font-size="28" font-weight="800" fill="#b4b4bb" text-anchor="middle"><text x="250" y="1240">NORTHWIND</text><text x="450" y="1240">lumen</text><text x="640" y="1240">orbit/</text><text x="830" y="1240">PAPERCO</text><text x="1030" y="1240">kite</text></g>${fx}</svg>`;
    },
    pricing: () => {
      const plans = [["Starter", "$0", "For trying Scout on your own.", "Start free", ["10 lookups a month", "Top 20 posts per creator", "Hook finder", "Email support"]],
        ["Pro", "$12", "For creators posting every week.", "Get Pro", ["Unlimited lookups", "Every post, every format", "Weekly brief", "Export to Notion"]],
        ["Team", "$49", "For agencies and brands.", "Talk to us", ["Everything in Pro", "10 seats", "Shared boards", "Priority support"]]];
      let cards = "";
      plans.forEach(([n, p, d, cta, feats], i) => {
        const x = 110 + i * 360, hot = i === 1;
        cards += `<rect x="${x}" y="330" width="340" height="560" rx="20" fill="#fff" stroke="${hot ? "#ff5a1f" : "#e4e4e7"}" stroke-width="${hot ? 3 : 1.5}"/>${hot ? `<rect x="${x + 196}" y="352" width="124" height="30" rx="15" fill="#fff1eb"/><text x="${x + 258}" y="373" font-size="15" font-weight="700" fill="#c2410c" text-anchor="middle">Most popular</text>` : ""}
          <text x="${x + 30}" y="378" font-size="24" font-weight="700" fill="#18181b">${n}</text><text x="${x + 30}" y="470" font-size="76" font-weight="800" fill="#0b0b0f" letter-spacing="-2">${p}</text>
          <text x="${x + 30 + p.length * 42}" y="470" font-size="22" fill="#71717a">/mo</text><text x="${x + 30}" y="514" font-size="18" fill="#52525b">${d}</text>
          <rect x="${x + 30}" y="544" width="280" height="54" rx="27" fill="${hot ? "#ff5a1f" : "#fff"}" stroke="${hot ? "#ff5a1f" : "#d4d4d8"}" stroke-width="1.5"/><text x="${x + 170}" y="578" font-size="19" font-weight="600" fill="${hot ? "#fff" : "#18181b"}" text-anchor="middle">${cta}</text>`;
        feats.forEach((ft, k) => { const y = 650 + k * 52; cards += `<path d="M${x + 32} ${y - 6}l6 6 12-13" fill="none" stroke="#16a34a" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/><text x="${x + 62}" y="${y}" font-size="19" fill="#3f3f46">${ft}</text>`; });
      });
      const faq = [["Can I cancel anytime?", "Yes. Plans renew monthly and cancel in one click."], ["Is there a free trial of Pro?", "Every account starts with 14 days of Pro, no card needed."], ["Do you read private accounts?", "No. Scout only reads public posts."]];
      let fq = "";
      faq.forEach(([q, a], i) => { const y = 1030 + i * 110; fq += `<text x="260" y="${y}" font-size="24" font-weight="700" fill="#18181b">${q}</text><text x="260" y="${y + 36}" font-size="19" fill="#52525b">${a}</text><rect x="260" y="${y + 62}" width="760" height="1" fill="#ececec"/>`; });
      return `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="1400" viewBox="0 0 1280 1400" ${FONT}><rect width="1280" height="1400" fill="#fff"/>${NAV(true)}<rect x="752" y="56" width="62" height="2.5" fill="#111"/>
        <text x="640" y="206" font-size="64" font-weight="800" fill="#0b0b0f" text-anchor="middle" letter-spacing="-2">Simple, honest pricing</text>
        <text x="640" y="258" font-size="23" fill="#52525b" text-anchor="middle">Start free. Upgrade when Scout pays for itself.</text>${cards}
        <text x="640" y="968" font-size="40" font-weight="800" fill="#0b0b0f" text-anchor="middle" letter-spacing="-1">Questions</text>${fq}</svg>`;
    },
  };
  const PH = {
    avatar: (t) => avatarSVG(t || "A"), person: (t) => personSVG(t || "p"), logo: (t) => logoSVG(t || "A"),
    thumb: (t) => thumbSVG(t || "1"), wall: (t) => thumbSVG("w" + (t || "1"), 39, 85), shot: (t) => (SHOTS[t] || SHOTS.landing)(),
  };
  const SHOT_SIZE = { landing: [1280, 1500], pricing: [1280, 1400] };

  // ---------- layout measurement (ignores transforms, adds page scrolls logged by AR.pageTo) ----------
  function lpos(el) {
    if (el.offsetParent === undefined) { // an SVG element: measure its box against its HTML parent
      const host = el.closest("svg") ? el.closest("svg").parentElement : el.parentElement, [hx, hy] = lpos(host);
      const r = el.getBoundingClientRect(), hr = host.getBoundingClientRect(), k = hr.width ? host.offsetWidth / hr.width : 1;
      return [hx + host.clientLeft + (r.left - hr.left) * k, hy + host.clientTop + (r.top - hr.top) * k];
    }
    let x = el.offsetLeft, y = el.offsetTop, p = el.offsetParent;
    while (p) { x += p.offsetLeft + p.clientLeft; y += p.offsetTop + p.clientTop; p = p.offsetParent; }
    return [x, y];
  }
  function scrollAt(el, t) {
    let st = { x: 0, y: 0, s: 1 };
    for (const e of el._wbLog || []) {
      if (t >= e.t1) st = e.to;
      else if (t > e.t0) { const k = (t - e.t0) / (e.t1 - e.t0); st = { x: e.from.x + (e.to.x - e.from.x) * k, y: e.from.y + (e.to.y - e.from.y) * k, s: e.from.s + (e.to.s - e.from.s) * k }; }
    }
    return st;
  }
  // point (ax, ay fractions of el's box) in the padding-box coordinates of ref, at scene time t
  function pointIn(el, ref, t, ax = 0.5, ay = 0.5) {
    let [x, y] = lpos(el);
    const [w, h] = el.offsetWidth === undefined ? (() => { const r = el.getBoundingClientRect(), hr = el.closest("svg").parentElement, k = hr.offsetWidth / (hr.getBoundingClientRect().width || 1); return [r.width * k, r.height * k]; })() : [el.offsetWidth, el.offsetHeight];
    x += w * ax; y += h * ay;
    for (let n = el.parentElement; n && n !== ref && !n.contains(ref); n = n.parentElement) {
      if (!n._wbLog) continue;
      const [sx, sy] = lpos(n), st = scrollAt(n, t);
      x = sx + st.x + (x - sx) * st.s; y = sy + st.y + (y - sy) * st.s;
    }
    const [rx, ry] = lpos(ref);
    return [x - rx - ref.clientLeft, y - ry - ref.clientTop];
  }
  // chained tweens on one element: the first paints its from-state, later ones must not (GSAP)
  const chain = (tl, el, from, to, t) => {
    const first = !el._wbChained; el._wbChained = 1;
    return tl.fromTo(el, from, first ? to : { ...to, immediateRender: false }, t);
  };

  Object.assign(AR, {
    // ---------- setup ----------
    webInit(root) {
      all("[data-i]:not([data-wbi])", root).forEach((el) => {
        const svg = ICONS[el.dataset.i];
        el.dataset.wbi = "1";
        el.classList.add("wb-i");
        if (svg) el.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${svg}</svg>`;
      });
      all("img[data-ph]:not([src])", root).forEach((img) => {
        const [kind, ...rest] = img.dataset.ph.split(":");
        const text = rest.join(":");
        const gen = PH[kind] || PH.thumb;
        img.src = uri(gen(text));
        if (kind === "shot") { const [w, h] = SHOT_SIZE[text] || SHOT_SIZE.landing; img.width = w; img.height = h; }
      });
      all(".wb-cursor", root).forEach((c) => { if (!c.querySelector("svg")) c.innerHTML = CURSOR; });
      // stacked variants (tab titles, URLs per page) overlap by design: keep the layout check off them
      all(".wb-swap, .wb-notifs.wb-stack", root).forEach((w) => w.setAttribute("data-layout-allow-overlap", ""));
      all(".wb-ig-tile", root).forEach((tile) => {
        if (tile.querySelector(".wb-ig-sel")) return;
        const o = document.createElement("span");
        o.className = "wb-ig-sel";
        o.innerHTML = `<i class="wb-ig-check"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.6 4.6L19 7.5" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg></i>`;
        tile.appendChild(o);
      });
    },
    // a generated placeholder image as a data URI: AR.ph("person:Nancy Pelosi"), ("logo:stripe"), ("thumb:7"), ("shot:pricing")
    ph(spec) { const [kind, ...rest] = String(spec).split(":"); return uri((PH[kind] || PH.thumb)(rest.join(":"))); },

    // ---------- cursor, links, navigation ----------
    // moves the cursor's hotspot onto a target element (its centre, or ax/ay fractions of its box, plus dx/dy px),
    // or onto [x, y] in the cursor's parent. Measures the final layout and any AR.pageTo scroll at the arrival time.
    cursorTo(tl, cursor, target, t, dur = 0.5, o = {}) {
      const c = one(cursor), ref = c.offsetParent || c.parentElement;
      let x, y;
      if (Array.isArray(target)) [x, y] = target;
      else [x, y] = pointIn(one(target), ref, t + dur, o.ax ?? 0.5, o.ay ?? 0.5);
      x += (o.dx ?? 0) - c.offsetLeft; y += (o.dy ?? 0) - c.offsetTop;
      const prev = c._wbAt || { x: 0, y: 0 };
      c._wbAt = { x, y };
      return chain(tl, c, { x: prev.x, y: prev.y }, { x, y, duration: dur, ease: o.ease ?? "power3.inOut" }, t);
    },
    // switches the cursor between "arrow" and "hand" (pointing hand over links and buttons)
    cursorShape(tl, cursor, shape, t) {
      const c = one(cursor), a = c.querySelector(".wb-arrow"), h = c.querySelector(".wb-hand");
      const was = c._wbShape || "arrow";
      if (was === shape) return tl;
      c._wbShape = shape;
      const hand = shape === "hand";
      tl.fromTo(a, { opacity: hand ? 1 : 0 }, { opacity: hand ? 0 : 1, duration: 0.001, immediateRender: false }, t);
      return tl.fromTo(h, { opacity: hand ? 0 : 1 }, { opacity: hand ? 1 : 0, duration: 0.001, immediateRender: false }, t);
    },
    // hover: the link's underline appears at t (instantly, like a browser) and the cursor turns into a hand;
    // both reset at o.until. Works on .wb-link text and on .wb-hot boxes placed over a screenshot.
    hoverLink(tl, link, t, o = {}) {
      const el = one(link), th = o.thick ?? (el.classList.contains("wb-hot") ? 3 : 2);
      tl.fromTo(el, { backgroundSize: `0% ${th}px` }, { backgroundSize: `100% ${th}px`, duration: 0.001, immediateRender: false }, t);
      if (o.until) tl.fromTo(el, { backgroundSize: `100% ${th}px` }, { backgroundSize: `0% ${th}px`, duration: 0.001, immediateRender: false }, o.until);
      if (o.cursor) { AR.cursorShape(tl, o.cursor, "hand", t); if (o.until) AR.cursorShape(tl, o.cursor, "arrow", o.until); }
      return tl;
    },
    // a soft blue ring at the cursor's hotspot (a click you can see); the cursor itself presses with AR.click
    clickRing(tl, ring, cursor, t) {
      const r = one(ring), c = one(cursor), at = c._wbAt || { x: 0, y: 0 };
      tl.set(r, { left: c.offsetLeft + at.x, top: c.offsetTop + at.y }, t);
      tl.fromTo(r, { scale: 0.3, opacity: 0.9 }, { scale: 1.5, opacity: 0, duration: 0.38, ease: "power2.out", immediateRender: false }, t);
      return tl;
    },
    // navigation cut: the tab's favicon spins for o.load s (default 0.16), then the next page cuts in. Every element
    // tagged data-page="<from id>" (tab title, URL) hides and every data-page="<to id>" shows at the same moment.
    navigate(tl, fromPage, toPage, t, o = {}) {
      const a = one(fromPage), b = one(toPage), load = o.load ?? 0.16, br = a.closest(".wb-browser");
      const tc = t + load;
      if (br && load > 0) {
        const fav = br.querySelector(".wb-tab.wb-on .wb-fav");
        if (fav) {
          let sp = fav.querySelector(".wb-spin");
          if (!sp) { sp = document.createElement("i"); sp.className = "wb-spin"; fav.appendChild(sp); }
          const img = fav.querySelector("img, svg:not(.wb-spin)");
          tl.fromTo(sp, { opacity: 0, rotation: 0 }, { opacity: 1, duration: 0.001, immediateRender: false }, t);
          tl.to(sp, { rotation: 300, duration: load, ease: "none" }, t);
          tl.to(sp, { opacity: 0, duration: 0.001 }, tc);
          if (img) { tl.fromTo(img, { opacity: 1 }, { opacity: 0, duration: 0.001, immediateRender: false }, t); tl.to(img, { opacity: 1, duration: 0.001 }, tc); }
        }
      }
      tl.fromTo(a, { opacity: 1 }, { opacity: 0, duration: 0.001, immediateRender: false }, tc);
      tl.fromTo(b, { opacity: 0 }, { opacity: 1, duration: 0.001, immediateRender: false }, tc);
      const scope = br || document;
      if (a.id) all(`[data-page="${a.id}"]`, scope).forEach((e) => tl.fromTo(e, { opacity: 1 }, { opacity: 0, duration: 0.001, immediateRender: false }, tc));
      if (b.id) all(`[data-page="${b.id}"]`, scope).forEach((e) => tl.fromTo(e, { opacity: 0 }, { opacity: 1, duration: 0.001, immediateRender: false }, tc));
      return tl;
    },
    // scrolls and zooms a page (.wb-scroll, or any wrapper with transform-origin 0 0) inside its viewport.
    // o.y / o.x: page px to bring to the viewport's top-left; o.to: an element to bring to the top (o.pad px below
    // the edge, default 40); o.focus: an element to centre in the viewport; o.zoom: scale (default: keep);
    // o.dur (0.6; 0 = already there at t); o.steps: n jumps with holds, like a stepped scroll; o.ease.
    pageTo(tl, scroller, t, o = {}) {
      const el = one(scroller), view = o.view ? one(o.view) : el.parentElement;
      const log = el._wbLog || (el._wbLog = []);
      const prev = log.length ? log[log.length - 1].to : { x: 0, y: 0, s: 1 };
      const s = o.zoom ?? prev.s, vw = view.clientWidth, vh = view.clientHeight;
      const rel = (n) => { const [ex, ey] = lpos(n), [px, py] = lpos(el); return [ex - px, ey - py, n.offsetWidth, n.offsetHeight]; };
      let px = o.x ?? (prev.s ? -prev.x / prev.s : 0), py = o.y ?? (prev.s ? -prev.y / prev.s : 0);
      if (o.to) { const [, ey] = rel(one(o.to)); py = ey - (o.pad ?? 40) / s; if (o.x === undefined) px = 0; }
      if (o.focus) { const [ex, ey, ew, eh] = rel(one(o.focus)); px = ex + ew / 2 - vw / (2 * s); py = ey + eh / 2 - vh / (2 * s); }
      if (o.clamp !== false) {
        const cw = el.offsetWidth, ch = el.scrollHeight || el.offsetHeight;
        px = Math.max(0, Math.min(px, cw - vw / s)); py = Math.max(0, Math.min(py, Math.max(0, ch - vh / s)));
      }
      const to = { x: -px * s, y: -py * s, s };
      const dur = o.dur ?? 0.6, n = Math.max(1, o.steps ?? 1);
      for (let k = 1; k <= n; k++) {
        const a = k === 1 ? prev : { x: prev.x + ((to.x - prev.x) * (k - 1)) / n, y: prev.y + ((to.y - prev.y) * (k - 1)) / n, s: prev.s + ((to.s - prev.s) * (k - 1)) / n };
        const b = { x: prev.x + ((to.x - prev.x) * k) / n, y: prev.y + ((to.y - prev.y) * k) / n, s: prev.s + ((to.s - prev.s) * k) / n };
        const t0 = t + ((k - 1) * dur) / n, d = n > 1 ? (dur / n) * 0.62 : dur;
        chain(tl, el, { x: a.x, y: a.y, scale: a.s }, { x: b.x, y: b.y, scale: b.s, duration: d, ease: o.ease ?? (n > 1 ? "power2.inOut" : "power3.inOut") }, t0);
        log.push({ t0, t1: t0 + d, from: a, to: b });
      }
      return tl;
    },

    // ---------- live lists: rows and notifications push in ----------
    // a new row appears at its place in a list (a .wb-tbody, .wb-news-list, .wb-gm-list, .wb-sl-msgs or any column of
    // rows) and pushes every row below it down, with a highlight flash. Write the rows in their final order; call
    // it once per new row (several at the top: the newest is first in the HTML and inserted last).
    rowInsert(tl, list, row, t, o = {}) {
      return push(tl, list, row, t, { dur: 0.34, ease: "power3.out", ...o, kind: "row" });
    },
    // a notification slides down into a .wb-notifs stack. List mode (default): newest on top, the others pushed down
    // (write cards newest first). .wb-stack mode (or o.mode "stack"): the newest lands in front and older ones step
    // back as layers peeking below (write cards oldest first). o.buzz: an element to wiggle (the phone).
    notify(tl, stack, card, t, o = {}) {
      const box = one(stack);
      if (o.buzz) { const b = one(o.buzz); [0, 1, 2, 3, 4].forEach((i) => tl.to(b, { rotation: i === 4 ? 0 : i % 2 ? -1.6 : 1.6, duration: 0.045, ease: "none" }, t + i * 0.045)); }
      if (o.mode === "stack" || box.classList.contains("wb-stack")) return stackIn(tl, box, one(card), t, o);
      return push(tl, box, card, t, { dur: 0.42, ease: "power3.out", ...o, kind: "notif" });
    },
    // outlines a group of rows (first..last) with a .wb-group box (and its tag) that pops in at t
    rowGroup(tl, box, first, last, t, o = {}) {
      const g = one(box), a = one(first), b = one(last || first), ref = g.offsetParent;
      const [ax, ay] = pointIn(a, ref, t, 0, 0), [, by] = pointIn(b, ref, t, 0, 1), pad = o.pad ?? 6;
      Object.assign(g.style, { left: `${ax - pad + (o.inset ?? 10)}px`, top: `${ay - pad}px`, width: `${(o.width ?? a.offsetWidth - 2 * (o.inset ?? 10)) + 2 * pad}px`, height: `${by - ay + 2 * pad}px` });
      return tl.fromTo(g, { opacity: 0, scale: 1.04 }, { opacity: 1, scale: 1, duration: 0.16, ease: "power3.out" }, t);
    },

    // ---------- social ----------
    // select-all on a grid: each tile tints blue with a check, in order from t over o.dur (default 1 s), while the
    // counter (o.counter: a .wb-counter) counts from o.from (0) to o.to, then shows its check. o.order: tile order.
    selectGrid(tl, items, t, o = {}) {
      const tiles = all(items), dur = o.dur ?? 1, gap = o.gap ?? dur / Math.max(1, tiles.length);
      AR.webInit();
      tiles.forEach((tile, i) => {
        const sel = tile.querySelector(".wb-ig-sel"), chk = sel && sel.querySelector(".wb-ig-check"), ti = t + i * gap;
        if (!sel) return;
        tl.fromTo(sel, { opacity: 0 }, { opacity: 1, duration: 0.1, ease: "power1.out" }, ti);
        if (chk) tl.fromTo(chk, { scale: 0.2 }, { scale: 1, duration: 0.22, ease: "back.out(3)" }, ti);
      });
      if (o.counter) {
        const c = one(o.counter), n = c.querySelector(".wb-ct-n") || c, done = c.querySelector(".wb-ct-done");
        tl.fromTo(n, { textContent: o.from ?? 0 }, { textContent: o.to ?? tiles.length, duration: o.countDur ?? dur, ease: o.ease ?? "power1.in", snap: { textContent: 1 }, modifiers: { textContent: fmt } }, t);
        if (done) tl.fromTo(done, { opacity: 0, scale: 0.3 }, { opacity: 1, scale: 1, duration: 0.25, ease: "back.out(3)" }, t + (o.countDur ?? dur));
      }
      return tl;
    },
    // double-tap heart: pops big over the post, settles, floats up and fades; o.like: a .wb-like that turns red
    heart(tl, sel, t, o = {}) {
      const h = one(sel);
      tl.fromTo(h, { scale: 0, opacity: 1, rotation: -14, y: 0 }, { scale: 1.2, rotation: 0, duration: 0.17, ease: "back.out(2.2)" }, t);
      tl.to(h, { scale: 1, duration: 0.12, ease: "power2.out" }, t + 0.17);
      tl.to(h, { y: -(h.offsetHeight * 0.45), scale: 0.86, opacity: 0, duration: 0.3, ease: "power2.in" }, t + (o.hold ?? 0.62));
      if (o.like) {
        const lk = one(o.like), red = lk.querySelector(".wb-liked") || lk;
        tl.fromTo(red, { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.24, ease: "back.out(3)" }, t + 0.06);
      }
      return tl;
    },
    // a vertical feed (.wb-feed > .wb-feed-track > reels) swipes up o.n times (1), o.gap s apart (0.4)
    feedSwipe(tl, feed, t, o = {}) {
      const fd = one(feed), track = fd.querySelector(".wb-feed-track") || fd.firstElementChild, h = fd.clientHeight + (o.space ?? 0);
      const n = o.n ?? 1, gap = o.gap ?? 0.4, k0 = track._wbK || 0;
      for (let i = 0; i < n; i++) {
        chain(tl, track, { y: -(k0 + i) * h }, { y: -(k0 + i + 1) * h, duration: o.dur ?? 0.3, ease: o.ease ?? "power3.inOut" }, t + i * gap);
      }
      track._wbK = k0 + n;
      return tl;
    },
    // horizontal carousel (App Store reviews): the track slides so card o.to (index) sits at o.inset px from the left
    carousel(tl, track, t, o = {}) {
      const tr = one(track), card = tr.children[o.to ?? 1], x = -(card.offsetLeft - (o.inset ?? 0));
      const prev = tr._wbX ?? 0;
      tr._wbX = x;
      return chain(tl, tr, { x: prev }, { x, duration: o.dur ?? 0.42, ease: o.ease ?? "power3.inOut" }, t);
    },
    // Instagram Insights: the line draws, the number counts (o.from..o.to with commas) and o.rider (a dot or a
    // sprite; default the card's .wb-ins-tip) rides the tip, all over dur from t
    insights(tl, card, t, dur, o = {}) {
      const c = one(card), path = c.querySelector(".wb-ins-line"), num = c.querySelector(".wb-ins-num");
      const ease = o.ease ?? "power1.inOut";
      if (path) { // dash = the real length (pathLength="1" does not hold under preserveAspectRatio="none")
        const L = path.getTotalLength();
        path.style.strokeDasharray = `${L} ${L}`;
        tl.fromTo(path, { strokeDashoffset: L }, { strokeDashoffset: 0, duration: dur, ease }, t);
      }
      if (num && o.to !== undefined) tl.fromTo(num, { textContent: o.from ?? 0 }, { textContent: o.to, duration: dur, ease, snap: { textContent: 1 }, modifiers: { textContent: fmt } }, t);
      const rider = one(o.rider || c.querySelector(".wb-ins-tip"));
      if (path && rider) {
        const svg = path.ownerSVGElement, box = svg.parentElement, vb = svg.viewBox.baseVal, L = path.getTotalLength(), N = 40;
        const ref = rider.offsetParent, [sx, sy] = pointIn(box, ref, t, 0, 0); // the svg fills its HTML box
        const kx = box.clientWidth / vb.width, ky = box.clientHeight / vb.height;
        const ax = o.ax ?? 0.5, ay = o.ay ?? 0.5, xs = [], ys = [];
        for (let i = 0; i <= N; i++) {
          const p = path.getPointAtLength((L * i) / N);
          xs.push(sx + p.x * kx - rider.offsetLeft - rider.offsetWidth * ax + (o.dx ?? 0));
          ys.push(sy + p.y * ky - rider.offsetTop - rider.offsetHeight * ay + (o.dy ?? 0));
        }
        tl.fromTo(rider, { x: xs[0], y: ys[0] }, { keyframes: { x: xs, y: ys, easeEach: "none" }, duration: dur, ease }, t);
      }
      return tl;
    },

    // ---------- Google apps ----------
    // a snackbar slides up (Gmail "24 emails sent · Undo"); o.count {from, to, dur} counts its .wb-snack-n; o.out hides it
    snackbar(tl, sel, t, o = {}) {
      const sn = one(sel);
      tl.fromTo(sn, { yPercent: 130, opacity: 0 }, { yPercent: 0, opacity: 1, duration: 0.3, ease: "power3.out" }, t);
      const n = sn.querySelector(".wb-snack-n");
      if (n && o.count) tl.fromTo(n, { textContent: o.count.from ?? 1 }, { textContent: o.count.to, duration: o.count.dur ?? 0.8, ease: o.count.ease ?? "power1.inOut", snap: { textContent: 1 }, modifiers: { textContent: fmt } }, t + (o.count.delay ?? 0.05));
      if (o.out) tl.to(sn, { yPercent: 130, opacity: 0, duration: 0.22, ease: "power2.in" }, o.out);
      return tl;
    },
    // Calendar: a dashed slot (.wb-slot) appears at t, then the event (.wb-ev in the same place) books in at tb
    calBook(tl, slot, ev, t, tb, o = {}) {
      const sl = one(slot), e = one(ev);
      tl.fromTo(sl, { opacity: 0, scale: 0.9 }, { opacity: 1, scale: 1, duration: 0.18, ease: "back.out(2)" }, t);
      tl.to(sl, { opacity: 0, duration: 0.1 }, tb + 0.04);
      return tl.fromTo(e, { opacity: 0, scale: 0.94 }, { opacity: 1, scale: 1, duration: 0.2, ease: "back.out(2.4)" }, tb);
    },
    // Sheets: rows of a .wb-sheet fill one per o.gap s (2 frames) from t while the selection steps down column
    // o.col (0 = A); the name box (.wb-sh-r) and formula bar (.wb-sh-val) follow. o.rows: [first, last] row numbers.
    sheetFill(tl, sheet, t, o = {}) {
      const sh = one(sheet), body = sh.querySelector(".wb-sh-body"), rows = Array.from(body.querySelectorAll(".wb-sh-row"));
      const [r0, r1] = o.rows ?? [2, rows.length], gap = o.gap ?? 2 / 30, col = o.col ?? 0;
      const sel = body.querySelector(".wb-sh-sel"), name = sh.querySelector(".wb-sh-r"), val = sh.querySelector(".wb-sh-val");
      const cell = (r) => rows[r - 1].children[1 + col];
      const place = (r) => { const c = cell(r); return { left: c.offsetLeft - 1.5, top: c.offsetTop - 1.5, width: c.offsetWidth + 1.5, height: c.offsetHeight + 1.5 }; };
      const start = o.from ?? r0 - 1;
      if (sel && start >= 1) Object.assign(sel.style, Object.fromEntries(Object.entries(place(start)).map(([k, v]) => [k, `${v}px`])));
      const ON = { backgroundColor: "#d3e3fd", color: "#0b57d0" }, OFF = { backgroundColor: "#f8f9fa", color: "#444746" };
      const num = (r) => rows[r - 1].querySelector(".wb-sh-n");
      for (let r = r0; r <= r1; r++) {
        const ti = t + (r - r0) * gap, cells = Array.from(rows[r - 1].children).slice(1);
        tl.fromTo(cells, { opacity: 0 }, { opacity: 1, duration: 0.001 }, ti);
        if (sel) { const p = place(r), p0 = place(start); tl.set(sel, { y: p.top - p0.top }, ti); }
        if (name) tl.set(name, { textContent: String(r) }, ti);
        if (val) tl.set(val, { textContent: cell(r).textContent }, ti);
        const prevN = num(r === r0 ? start : r - 1), n = num(r);
        if (prevN && r === r0) tl.fromTo(prevN, ON, { ...OFF, duration: 0.001 }, ti);
        if (n) {
          tl.fromTo(n, OFF, { ...ON, duration: 0.001, immediateRender: false }, ti);
          if (r < r1) tl.fromTo(n, ON, { ...OFF, duration: 0.001, immediateRender: false }, ti + gap);
        }
      }
      return tl;
    },
  });

  // the list engine behind rowInsert and notify: every row's offset is a function of time, rebuilt on each call
  function push(tl, list, item, t, o) {
    const box = one(list), el = one(item);
    const reg = box._wbPush || (box._wbPush = { ins: [], sub: gsap.timeline() });
    if (!reg.added) { tl.add(reg.sub, 0); reg.added = 1; }
    reg.ins = reg.ins.filter((r) => r.el !== el).concat([{ el, t, o }]);
    reg.sub.clear();
    const kids = Array.from(box.children).filter((k) => getComputedStyle(k).position !== "absolute");
    const cs = getComputedStyle(box), gap = parseFloat(cs.rowGap) || 0;
    const slot = (k, i) => (kids[i + 1] ? kids[i + 1].offsetTop - k.offsetTop : k.offsetHeight + gap);
    const ins = new Map(reg.ins.map((r) => [r.el, r]));
    kids.forEach((k, i) => {
      const above = kids.slice(0, i).map((a, j) => ({ r: ins.get(a), h: slot(a, j) })).filter((x) => x.r).sort((a, b) => a.r.t - b.r.t);
      let y = -above.reduce((n, x) => n + x.h, 0), first = true;
      above.forEach(({ r, h }) => {
        reg.sub.fromTo(k, { y }, { y: y + h, duration: r.o.dur, ease: r.o.ease, immediateRender: first }, r.t);
        y += h; first = false;
      });
      const me = ins.get(k);
      if (!me) return;
      if (me.o.kind === "notif") {
        reg.sub.fromTo(k, { opacity: 0, yPercent: -55, scale: 0.97 }, { opacity: 1, yPercent: 0, scale: 1, duration: me.o.dur, ease: "power3.out" }, me.t);
      } else {
        reg.sub.fromTo(k, { opacity: 0 }, { opacity: 1, duration: 0.14, ease: "power1.out" }, me.t);
        if (me.o.flash !== false) {
          let fl = k.querySelector(":scope > .wb-rowflash");
          if (!fl) { fl = document.createElement("i"); fl.className = "wb-rowflash"; if (getComputedStyle(k).position === "static") k.style.position = "relative"; k.prepend(fl); }
          if (me.o.flash && typeof me.o.flash === "string") fl.style.background = me.o.flash;
          reg.sub.fromTo(fl, { opacity: 0 }, { opacity: 1, duration: 0.06 }, me.t);
          reg.sub.to(fl, { opacity: 0, duration: 0.7, ease: "power1.in" }, me.t + 0.35);
        }
      }
    });
    return tl;
  }
  function stackIn(tl, box, card, t, o) {
    const reg = box._wbStack || (box._wbStack = { ins: [], sub: gsap.timeline() });
    if (!reg.added) { tl.add(reg.sub, 0); reg.added = 1; }
    reg.ins = reg.ins.filter((r) => r.el !== card).concat([{ el: card, t, o }]);
    reg.sub.clear();
    const cards = Array.from(box.children), arr = new Map(reg.ins.map((r) => [r.el, r.t]));
    const when = (c, i) => (arr.has(c) ? arr.get(c) : -1000 + i);
    const order = cards.map((c, i) => ({ c, a: when(c, i) })).sort((a, b) => a.a - b.a);
    const peek = o.peek ?? Math.round(card.offsetHeight * 0.09);
    const state = (d) => (d === 0 ? { y: 0, scale: 1, opacity: 1 } : d === 1 ? { y: peek, scale: 0.94, opacity: 0.9 } : d === 2 ? { y: peek * 2, scale: 0.88, opacity: 0.7 } : { y: peek * 2, scale: 0.84, opacity: 0 });
    order.forEach(({ c, a }, i) => {
      c.style.zIndex = String(i + 1);
      const newer = order.slice(i + 1).map((x) => x.a);
      if (a > -100) reg.sub.fromTo(c, { opacity: 0, yPercent: -60, scale: 1 }, { opacity: 1, yPercent: 0, duration: 0.42, ease: "power3.out" }, a);
      let d = newer.filter((x) => x <= 0).length, first = a <= -100;
      newer.filter((x) => x > 0).forEach((tn) => {
        const from = state(d), to = state(d + 1);
        reg.sub.fromTo(c, from, { ...to, duration: 0.36, ease: "power3.out", immediateRender: first }, tn);
        d += 1; first = false;
      });
    });
    return tl;
  }

  // AR.names() is the first line of every scene: let it also run webInit, so icons and placeholders are always filled
  if (AR.names && !AR.names._wb) {
    const names = AR.names;
    AR.names = function (root) { const r = names.apply(this, arguments); AR.webInit(root); return r; };
    AR.names._wb = 1;
  }
})();

/* ---------- landing page skins and the design tool (ui-web.css: .wb-land, .wb-figma) ----------
   AR.wbLanding(el, o) builds a landing page; AR.wbSkin(tl, page, t, skin, o) switches its look on the word (slop, brand,
   editorial). Inside a design-tool frame (.wb-fg-frame, or any page element): AR.wbGuides draws guides, AR.wbGrid
   unrolls a column grid, AR.wbSelect puts a selection box with handles and a tag on elements, AR.wbResize drags a
   corner, AR.wbSnap snaps elements to the left margin. Overlays live inside the page, in page px, so they scale and
   move with it; AR.wbPoint converts a page point to another layer's px (to put a critter on a handle). Measurements
   are offset chains inside the scene (never page-relative rects), taken when the scene builds. */
(function () {
  const AR = (window.AR = window.AR || {});
  const all = (sel, root) => {
    if (!sel) return [];
    if (typeof sel !== "string") return sel.nodeType ? [sel] : Array.from(sel).flatMap((s) => all(s, root));
    return Array.from((root || document).querySelectorAll(sel));
  };
  const one = (sel, root) => all(sel, root)[0];
  const div = (cls, html) => { const d = document.createElement("div"); if (cls) d.className = cls; if (html != null) d.innerHTML = html; return d; };
  const SKINS = ["slop", "brand", "editorial"];

  // ---------- measuring ----------
  const gsapMoved = (n) => n && n._gsap && n._gsap.renderTransform && n.style && n.style.transform;
  const chainOf = (n) => { const out = []; for (; n && n.nodeType === 1; n = n.parentElement) out.push(n); return out; };
  function atRest(nodes, fn) {
    const saved = [];
    new Set(nodes.flatMap(chainOf)).forEach((n) => { if (gsapMoved(n)) { saved.push([n, n.style.transform]); n.style.transform = "none"; } });
    try { return fn(); } finally { saved.forEach(([n, v]) => { n.style.transform = v; }); }
  }
  // el's layout box in ref's px through the offset chain: CSS transforms ignored, but the moves these helpers gave it
  // (a snap, a resize) included, so a selection made after a snap lands on the snapped element
  const moved = (el, b) => { const m = el._wbMove; return m ? { x: b.x + m.x, y: b.y + m.y, w: b.w * m.s, h: b.h * m.s } : b; };
  function boxIn(el, ref) { return moved(el, layoutBox(el, ref)); }
  function layoutBox(el, ref) {
    let x = 0, y = 0, n = el;
    while (n && n !== ref) {
      x += n.offsetLeft || 0; y += n.offsetTop || 0;
      const p = n.offsetParent;
      if (p && p !== ref) { x += p.clientLeft || 0; y += p.clientTop || 0; }
      n = p;
    }
    if (n !== ref) { // ref is not on the offset chain: measure the two resting boxes against each other
      return atRest([el, ref], () => {
        const R = ref.getBoundingClientRect(), E = el.getBoundingClientRect(), k = R.width / (ref.offsetWidth || 1) || 1;
        return { x: (E.left - R.left) / k - ref.clientLeft, y: (E.top - R.top) / k - ref.clientTop, w: el.offsetWidth, h: el.offsetHeight };
      });
    }
    return { x, y, w: el.offsetWidth, h: el.offsetHeight };
  }
  const union = (list, ref) => {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    list.forEach((e) => { const b = boxIn(e, ref); x0 = Math.min(x0, b.x); y0 = Math.min(y0, b.y); x1 = Math.max(x1, b.x + b.w); y1 = Math.max(y1, b.y + b.h); });
    return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
  };
  const pageOf = (el) => el.closest(".wb-fg-frame") || el.closest(".wb-land") || el.offsetParent || el.parentElement;
  /** a point in a page's px -> px in another element (the layer a critter or a cursor lives in), across the frame's
   *  scale: AR.wbPoint("#b07-page", x, y, "#b07-cast"), or a point of an element in the page:
   *  AR.wbPoint("#b07-page", "#b07-h1", [1, 1], "#b07-cast") (its bottom-right corner, after any snap or resize) */
  AR.wbPoint = function (page, x, y, space) {
    const pg = one(page), sp = one(space);
    if (typeof x !== "number") { const b = boxIn(one(x), pg), a = y || [0.5, 0.5]; x = b.x + b.w * a[0]; y = b.y + b.h * a[1]; }
    return atRest([pg, sp], () => {
      const P = pg.getBoundingClientRect(), S = sp.getBoundingClientRect();
      const ks = S.width / (sp.offsetWidth || 1) || 1, kp = P.width / (pg.offsetWidth || 1) || 1;
      return [(P.left - S.left) / ks + (x * kp) / ks - sp.clientLeft, (P.top - S.top) / ks + (y * kp) / ks - sp.clientTop];
    });
  };

  // ---------- the landing page ----------
  const IMG = /^(assets\/|data:|https?:|\.{0,2}\/)|\.(png|jpe?g|webp|gif|svg)$/i;
  const MOCK = {
    dash: `<div class="wb-ld-mock"><div class="wb-ld-mock-bar"><i></i><i></i><i></i></div><div class="wb-ld-mock-side"><i></i><i></i><i></i><i></i><i></i></div>
      <div class="wb-ld-mock-main"><b>This week</b><small>Visits and rewards</small><div class="wb-ld-mock-kpis"><span>Visits<em>1,284</em></span><span>Rewards<em>96</em></span></div>
      <div class="wb-ld-mock-chart"><i style="height:42%"></i><i style="height:64%"></i><i style="height:50%"></i><i style="height:92%"></i><i style="height:72%"></i></div></div></div>`,
    list: `<div class="wb-ld-mock"><div class="wb-ld-mock-list"><div><i></i>Ana R.<em>23</em></div><div><i></i>Tom B.<em>17</em></div><div><i></i>Priya K.<em>12</em></div><div><i></i>Jo M.<em>8</em></div></div></div>`,
    stamps: `<div class="wb-ld-mock-stamps">${Array.from({ length: 10 }, (_, i) => `<i${i < 7 ? ' class="wb-on"' : ""}></i>`).join("")}</div>`,
    alert: `<div class="wb-ld-mock-alert"><div><i></i><div><b>Free latte unlocked</b><span>Show this at the till</span></div></div></div>`,
  };
  const slot = (v, fallback) => {
    if (v === false) return `<div class="wb-ld-shot-empty">product shot</div>`;
    if (v == null) return MOCK[fallback] || MOCK.dash;
    if (MOCK[v]) return MOCK[v];
    if (typeof v === "object" && v.img) return `<img class="wb-shot" src="${v.img}" alt="">`;
    if (typeof v === "string" && IMG.test(v.trim()) && !/^</.test(v.trim())) return `<img class="wb-shot" src="${v}" alt="">`;
    return String(v);
  };
  // a value per skin: a string (all skins) or {slop, editorial} (brand uses the slop copy)
  const per = (v) => (v != null && typeof v === "object" && !Array.isArray(v) && ("slop" in v || "editorial" in v)
    ? `<span class="wb-ld-s">${v.slop ?? ""}</span><span class="wb-ld-e">${v.editorial ?? ""}</span>` : v ?? "");
  const LANDING = {
    brand: "Mugshot", links: ["Features", "Pricing", "About"], top: "Get started",
    badge: { slop: "✨ Introducing Mugshot AI", editorial: "For independent cafés" },
    h1: { slop: 'Supercharge Your Café<br><span class="wb-ld-grad">With AI</span>', editorial: 'Loyalty cards your regulars <span class="wb-ld-hl">actually keep.</span>' },
    sub: { slop: "The all-in-one AI-powered platform to revolutionize your coffee shop.", editorial: "Stamp cards for small cafés. No app to download." },
    cta: { slop: "Get Started 🚀", editorial: "Start free →" }, ghost: { slop: "Learn More →", editorial: "See how it works" },
    fh: { slop: "Why Choose Mugshot?", editorial: "What your regulars see" },
    feats: [
      { emoji: "🚀", title: { slop: "Blazing Fast", editorial: "Their stamp card" }, text: "Lightning-fast performance that scales with you.", shot: "stamps" },
      { emoji: "✨", title: { slop: "AI-Powered", editorial: "Your regulars" }, text: "Smart insights powered by cutting-edge AI.", shot: "list" },
      { emoji: "⚡", title: { slop: "Seamless Setup", editorial: "Free-latte alerts" }, text: "Integrates seamlessly into your workflow.", shot: "alert" },
    ],
  };
  /** build a landing page into el: AR.wbLanding("#b03-page", {skin, id, brandColor, brand, links, top, badge, h1, sub, cta,
   *  ghost, art, fh, feats: [{emoji, title, text, shot}]}). Copy can differ per skin: {slop: "..", editorial: ".."}.
   *  art / shot: an image path, {img}, raw HTML, "dash" "list" "stamps" (built-in product mocks) or false (an empty
   *  dashed slot). With o.id the parts get ids: <id>-badge -h1 -sub -ctas -cta -art -fh -card0.. (else [data-ld]) */
  AR.wbLanding = function (sel, o = {}) {
    const el = one(sel), c = Object.assign({}, LANDING, o), id = o.id || (el.id ? el.id : "");
    SKINS.forEach((k) => el.classList.remove("wb-" + k));
    el.classList.add("wb-land", "wb-" + (o.skin || "slop"));
    if (o.brandColor) el.style.setProperty("--brand", o.brandColor);
    const at = (k) => (id ? ` id="${id}-${k}"` : "") + ` data-ld="${k}"`;
    const feats = (c.feats || []).map((f, i) => `<div class="wb-ld-card"${at("card" + i)}><div class="wb-ld-shot">${slot(f.shot, ["stamps", "list", "dash"][i % 3])}</div>
      <div class="wb-ld-icon">${f.emoji ?? ""}</div><b>${per(f.title)}</b><p>${per(f.text)}</p></div>`).join("");
    el.innerHTML = `<div class="wb-ld-nav"${at("nav")}><div class="wb-ld-logo"><i class="wb-ld-mark"></i><span>${c.brand}</span></div>
      <div class="wb-ld-links">${(c.links || []).map((l) => `<span>${l}</span>`).join("")}</div><span class="wb-ld-btn wb-ld-top">${per(c.top)}</span></div>
      <div class="wb-ld-hero"${at("hero")}><div class="wb-ld-badge"${at("badge")}>${per(c.badge)}</div><h1 class="wb-ld-h1"${at("h1")}>${per(c.h1)}</h1>
        <p class="wb-ld-sub"${at("sub")}>${per(c.sub)}</p>
        <div class="wb-ld-ctas"${at("ctas")}><span class="wb-ld-btn wb-ld-cta"${at("cta")}>${per(c.cta)}</span><span class="wb-ld-btn wb-ld-ghost">${per(c.ghost)}</span></div>
        <div class="wb-ld-art"${at("art")}>${slot(c.art, "dash")}</div></div>
      <div class="wb-ld-feats"${at("feats")}><h2 class="wb-ld-fh"${at("fh")}>${per(c.fh)}</h2><div class="wb-ld-grid">${feats}</div></div>`;
    if (AR.names) AR.names(el);
    return el;
  };
  /** switch a .wb-land to another skin at t: a copy of the page in the new skin lands on top of it (a hard cut, or a
   *  wipe with o.wipe "down"/"right"/"up"/"left" over o.dur 0.45, a bar and a rider riding its edge: o.bar, o.rider,
   *  as AR.wipeRide). Returns the copy: target its parts as #<id>-<skin> (every id gets -<skin>) */
  AR.wbSkin = function (tl, page, t, skin, o = {}) {
    const el = one(page), cp = el.cloneNode(true), sfx = "-" + skin;
    if (cp.id) cp.id += sfx;
    cp.querySelectorAll("[id]").forEach((n) => { n.id += sfx; });
    SKINS.forEach((k) => cp.classList.remove("wb-" + k));
    cp.classList.add("wb-" + skin);
    Object.assign(cp.style, { position: "absolute", left: el.offsetLeft + "px", top: el.offsetTop + "px", margin: "0", zIndex: (parseInt(getComputedStyle(el).zIndex, 10) || 0) + 1 });
    el.parentNode.insertBefore(cp, el.nextSibling);
    if (o.wipe && AR.wipeRide) AR.wipeRide(tl, { after: cp, bar: o.bar, rider: o.rider }, t, o.dur ?? 0.45, { dir: o.wipe, ease: o.ease, riderDx: o.riderDx, riderDy: o.riderDy });
    else tl.fromTo(cp, { opacity: 0 }, { opacity: 1, duration: o.fade ?? 0.001, ease: "none" }, t);
    return cp;
  };

  // ---------- the design tool ----------
  const deco = (e) => { e.setAttribute("data-layout-ignore", ""); return e; };   // overlays are tool chrome, not page text
  const chip = (pg, text, x, y, cls) => { const c = deco(div(cls || "wb-fg-chip", text)); Object.assign(c.style, { left: x + "px", top: y + "px" }); pg.appendChild(c); return c; };
  // a label just above a design-tool frame, in the canvas (unscaled), right-aligned at page x (or left-aligned with o.left)
  const frameChip = (pg, text, x, left) => {
    const fr = pg.classList.contains("wb-fg-frame") ? pg : null, host = fr ? fr.parentElement : pg;
    const m = fr ? (getComputedStyle(fr).transform.match(/matrix\(([^,]+)/) || [0, 1])[1] : 1, k = parseFloat(m) || 1;
    const c = chip(host, text, fr ? fr.offsetLeft + x * k : x, fr ? fr.offsetTop - 34 : 10);
    if (!left) c.style.transform = "translateX(-100%)";
    return c;
  };
  /** guides that draw across a page at t: vertical at o.x (default its centre), horizontal at o.y (o.both adds the
   *  middle). o: {dur 0.24, gap 0.06, width 3, color, label (a pink chip at the first guide's top), until (fade)} */
  AR.wbGuides = function (tl, page, t, o = {}) {
    const pg = one(page), W = pg.clientWidth, H = pg.clientHeight, w = o.width ?? 3, out = [];
    const xs = o.x != null ? [].concat(o.x) : o.y != null ? [] : [W / 2], ys = o.y != null ? [].concat(o.y) : o.both ? [H / 2] : [];
    const add = (vert, v, i) => {
      const g = deco(div("wb-fg-guide"));
      Object.assign(g.style, vert ? { left: v - w / 2 + "px", top: "0px", width: w + "px", height: H + "px", transformOrigin: "50% 0" }
        : { left: "0px", top: v - w / 2 + "px", width: W + "px", height: w + "px", transformOrigin: "0 50%" });
      if (o.color) g.style.background = o.color;
      pg.appendChild(g);
      tl.fromTo(g, vert ? { scaleY: 0 } : { scaleX: 0 }, { [vert ? "scaleY" : "scaleX"]: 1, duration: o.dur ?? 0.24, ease: "power2.out" }, t + i * (o.gap ?? 0.06));
      out.push(g);
    };
    xs.forEach((x, i) => add(true, x, i));
    ys.forEach((y, i) => add(false, y, xs.length + i));
    if (o.label && out[0]) {
      const c = chip(pg, o.label, (xs[0] ?? 0) + 10, 10);
      tl.fromTo(c, { opacity: 0 }, { opacity: 1, duration: 0.08 }, t + 0.1);
      out.push(c);
    }
    if (o.until != null) tl.to(out, { opacity: 0, duration: 0.15 }, o.until);
    return out;
  };
  /** a column layout grid unrolls down the page from t, column by column left to right over o.dur (0.36):
   *  o: {cols 12, margin 64, gutter 24, height, label ("12 columns" chip), color, until}. Returns the grid element;
   *  grid._grid.x(i) is column i's left edge and .span(a, b) the width from column a to b, in page px */
  AR.wbGrid = function (tl, page, t, o = {}) {
    const pg = one(page), cols = o.cols ?? 12, m = o.margin ?? 64, gut = o.gutter ?? 24, W = pg.clientWidth - 2 * m, H = o.height ?? pg.clientHeight;
    const g = deco(div("wb-fg-cols"));
    Object.assign(g.style, { left: m + "px", width: W + "px", height: H + "px", gridTemplateColumns: `repeat(${cols}, 1fr)`, columnGap: gut + "px" });
    for (let i = 0; i < cols; i++) { const c = document.createElement("i"); if (o.color) c.style.background = o.color; g.appendChild(c); }
    pg.appendChild(g);
    const each = o.each ?? 0.14, dur = Math.max(each, o.dur ?? 0.36);
    tl.fromTo(Array.from(g.children), { scaleY: 0 }, { scaleY: 1, duration: each, ease: "power2.out", stagger: (dur - each) / Math.max(1, cols - 1) }, t);
    const cw = (W - (cols - 1) * gut) / cols;
    g._grid = { cols, margin: m, gutter: gut, colW: cw, x: (i) => m + i * (cw + gut), span: (a, b) => (b - a + 1) * cw + (b - a) * gut };
    if (o.label) {
      const c = frameChip(pg, o.label === true ? `${cols} columns` : o.label, m + W);
      tl.fromTo(c, { opacity: 0 }, { opacity: 1, duration: 0.08 }, t + 0.06);
      if (o.until != null) tl.to(c, { opacity: 0, duration: 0.15 }, o.until);
    }
    if (o.until != null) tl.to(g, { opacity: 0, duration: 0.15 }, o.until);
    return g;
  };
  /** a selection box lands on t around the target (or the union of several): blue border, corner handles, a name tag
   *  above it. o: {label, size (true: "W × H" under it, or a string), pad 8, color, handles (false: a plain outline),
   *  each (true: one outline per element, o.gap 0.07 apart; returns them all), page, until}. Returns the box. */
  AR.wbSelect = function (tl, target, t, o = {}) {
    const els = all(target);
    if (!els.length) return null;
    const pg = o.page ? one(o.page) : pageOf(els[0]), pad = o.pad ?? 8;
    const make = (list, ti, plain) => {
      const B = union(list, pg), s = deco(div(plain ? "wb-fg-out" : "wb-fg-sel"));
      Object.assign(s.style, { left: B.x - pad + "px", top: B.y - pad + "px", width: B.w + 2 * pad + "px", height: B.h + 2 * pad + "px" });
      if (o.color) { s.style.borderColor = o.color; s.style.setProperty("--fg-blue", o.color); }
      if (!plain) for (let i = 0; i < 4; i++) s.appendChild(document.createElement("i"));
      if (o.label && !plain) s.appendChild(div("wb-fg-tag", o.label));
      if (o.size && !plain) s.appendChild(div("wb-fg-dim", o.size === true ? `${Math.round(B.w)} × ${Math.round(B.h)}` : o.size));
      pg.appendChild(s);
      tl.fromTo(s, { opacity: 0, scale: 1.03 }, { opacity: 1, scale: 1, duration: 0.1, ease: "power2.out" }, ti);
      if (o.until != null) tl.to(s, { opacity: 0, duration: 0.08 }, o.until);
      s._sel = { pg, x: B.x, y: B.y, w: B.w, h: B.h, pad, els: list };
      return s;
    };
    if (o.each) return els.map((e, i) => make([e], t + i * (o.gap ?? 0.07), o.handles !== true));
    return make(els, t, o.handles === false);
  };
  /** drag a corner: the target scales by o.to (1.5; or to o.w px wide) from the opposite corner over dur, ending at
   *  t + dur; the selection (o.sel, from AR.wbSelect) grows with it, o.rider (a critter or a .wb-cursor, in any layer)
   *  rides the handle, and o.push (the elements below) step down out of its way (o.shrink scales them too).
   *  o: {corner "br" (or "bl" "tr" "tl"), ease power2.inOut} */
  AR.wbResize = function (tl, target, t, dur = 0.4, o = {}) {
    const el = one(target), sel = o.sel ? one(o.sel) : null, pg = sel && sel._sel ? sel._sel.pg : pageOf(el);
    const b = boxIn(el, pg), k = o.to ?? (o.w ? o.w / b.w : 1.5), E = o.ease ?? "power2.inOut", cn = o.corner || "br";
    const ox = cn.includes("r") ? 0 : 100, oy = cn.includes("b") ? 0 : 100, m0 = el._wbMove || { x: 0, y: 0, s: 1 };
    tl.fromTo(el, { scale: m0.s, transformOrigin: `${ox}% ${oy}%` }, { scale: m0.s * k, transformOrigin: `${ox}% ${oy}%`, duration: dur, ease: E }, t);
    el._wbMove = { x: m0.x, y: m0.y, s: m0.s * k };
    const dw = b.w * (k - 1), dh = b.h * (k - 1);
    if (sel && sel._sel) {
      const S = sel._sel;
      tl.fromTo(sel, { width: S.w + 2 * S.pad, height: S.h + 2 * S.pad, x: 0, y: 0 },
        { width: S.w + dw + 2 * S.pad, height: S.h + dh + 2 * S.pad, x: ox ? -dw : 0, y: oy ? -dh : 0, duration: dur, ease: E }, t);
      const dim = sel.querySelector(".wb-fg-dim");
      if (dim && /×/.test(dim.textContent)) {
        const n = 12, ef = gsap.parseEase(E);
        for (let i = 1; i <= n; i++) tl.set(dim, { textContent: `${Math.round(S.w + dw * ef(i / n))} × ${Math.round(S.h + dh * ef(i / n))}` }, t + dur * i / n);
      }
    }
    if (o.rider) {
      const r = one(o.rider), sp = r.offsetParent || r.parentElement;
      const a = AR.wbPoint(pg, 0, 0, sp), c = AR.wbPoint(pg, dw, dh, sp), dx = (c[0] - a[0]) * (ox ? -1 : 1), dy = (c[1] - a[1]) * (oy ? -1 : 1);
      tl.fromTo(r, { x: o.fromX ?? 0, y: o.fromY ?? 0 }, { x: (o.fromX ?? 0) + dx, y: (o.fromY ?? 0) + dy, duration: dur, ease: E }, t);
    }
    // what sits below steps aside: o.push elements move down by the growth (o.shrink scales them, 0.86)
    all(o.push).forEach((p, i) => {
      const m = p._wbMove || { x: 0, y: 0, s: 1 }, s1 = m.s * (o.shrink ?? 1);
      tl.fromTo(p, { y: m.y, scale: m.s, transformOrigin: "0% 0%" }, { y: m.y + dh, scale: s1, transformOrigin: "0% 0%", duration: dur, ease: E }, t + i * 0.02);
      p._wbMove = { x: m.x, y: m.y + dh, s: s1 };
    });
    return tl;
  };
  /** snap elements to the left margin: they slide over o.dur (0.22) and land on t with a small overshoot, o.gap (0.012)
   *  apart; their text aligns left as they land; a pink snap guide flashes at the margin. o: {to (page x, 64), guide
   *  (true), page, rider (a critter that shoves them: it travels with o.with, default the widest element), align (true)} */
  AR.wbSnap = function (tl, targets, t, o = {}) {
    const els = all(targets);
    if (!els.length) return tl;
    const pg = o.page ? one(o.page) : pageOf(els[0]), X = typeof o.to === "number" ? o.to : o.margin ?? 64, dur = o.dur ?? 0.22;
    let first = null;
    const lead = o.with ? one(o.with) : els.slice().sort((a, b) => b.offsetWidth - a.offsetWidth)[0];
    els.forEach((el, i) => {
      const b = boxIn(el, pg), dx = X - b.x, ti = t + i * (o.gap ?? 0.012);
      if (el === lead) first = dx;
      const m0 = el._wbMove || { x: 0, y: 0, s: 1 };
      tl.fromTo(el, { x: m0.x }, { x: m0.x + dx * 1.04, duration: dur, ease: "power3.in" }, ti - dur);
      tl.to(el, { x: m0.x + dx, duration: 0.12, ease: "back.out(3)" }, ti);
      if (o.align !== false) tl.set(el, { textAlign: "left" }, ti);
      el._wbMove = { x: m0.x + dx, y: m0.y, s: m0.s };
    });
    if (o.guide !== false) {
      const g = deco(div("wb-fg-guide"));
      Object.assign(g.style, { left: X - 1.5 + "px", top: "0px", width: "3px", height: pg.clientHeight + "px", transformOrigin: "50% 0" });
      pg.appendChild(g);
      tl.fromTo(g, { scaleY: 0, opacity: 1 }, { scaleY: 1, duration: 0.12, ease: "power2.out" }, t);
      tl.to(g, { opacity: 0, duration: 0.2 }, t + (o.hold ?? 0.45));
    }
    if (o.rider && first) {
      const r = one(o.rider), sp = r.offsetParent || r.parentElement;
      const a = AR.wbPoint(pg, 0, 0, sp), c = AR.wbPoint(pg, first, 0, sp), d = c[0] - a[0];
      tl.fromTo(r, { x: 0 }, { x: d * 1.04, duration: dur, ease: "power3.in" }, t - dur);
      tl.to(r, { x: d, duration: 0.12, ease: "back.out(3)" }, t);
    }
    return tl;
  };
})();

/* ---------- phone and growth UI, the GitHub clone menu, the overworld map (ui-web.css: .wb-sys, .wb-home,
   .wb-launch, .wb-bs, .wb-signup, .wb-paywall, .wb-tap, .wb-gh-clone, .wb-urlchip, .wb-qm) ----------
   Builders run inside AR.webInit (so AR.names() runs them): .wb-alert[data-alert] gets the exact iOS wording,
   .wb-home-grid / .wb-dock[data-fill] get generic apps, img[data-ph="app:name"] gets an app icon, sheets get their
   grabber and dim, switches their knob, and the icons apple, google, mail-f, branch, terminal, desktop, zip, loc
   join <i data-i>. Phone helpers measure with offset chains inside the phone's .wb-screen, so they work in any
   scene and under any camera move; put the phone's screens, sheets and alerts in its .wb-screen. */
(function () {
  const AR = (window.AR = window.AR || {});
  const all = (sel, root) => {
    if (!sel) return [];
    if (typeof sel === "string") return Array.from((root || document).querySelectorAll(sel));
    if (sel.nodeType) return [sel];
    return Array.from(sel).flatMap((x) => all(x, root));   // a list of elements and/or selectors
  };
  const one = (sel, root) => all(sel, root)[0];
  const rnd = (seed) => () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const hash = (s) => { let h = 2166136261; for (const c of String(s)) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return h >>> 0; };
  const uri = (svg) => "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  // "@key" reads NAMES.key (assets/names.js); anything else is itself
  const nm = (v) => (typeof v === "string" && v[0] === "@" ? String((window.NAMES || {})[v.slice(1)] ?? v.slice(1)) : v);
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  // layout position from offset chains (transforms ignored); boxIn: el's border box in ref's padding-box px
  function lpos(e) {
    let x = e.offsetLeft, y = e.offsetTop, p = e.offsetParent;
    while (p) { x += p.offsetLeft + p.clientLeft; y += p.offsetTop + p.clientTop; p = p.offsetParent; }
    return [x, y];
  }
  function boxIn(e, ref) {
    const [x, y] = lpos(e), [rx, ry] = lpos(ref);
    return { x: x - rx - ref.clientLeft, y: y - ry - ref.clientTop, w: e.offsetWidth, h: e.offsetHeight };
  }
  const screenOf = (e) => e.closest(".wb-screen") || e.closest(".wb-scr") || e.offsetParent || e.parentElement;

  // ---------- icons ----------
  const APPLE = "M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701";
  const PICONS = {
    apple: `<svg viewBox="0 0 24 24" aria-hidden="true"><path class="f" d="${APPLE}"/></svg>`,
    google: `<svg viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>`,
    "mail-f": `<svg viewBox="0 0 24 24" aria-hidden="true"><rect class="f" x="2.5" y="4.5" width="19" height="15" rx="3"/><path d="M4 7.2l8 5.9 8-5.9" fill="none" stroke="var(--wb-mail-line, #fff)" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" opacity=".9"/></svg>`,
    branch: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle class="s" cx="6.5" cy="5.5" r="2.3"/><circle class="s" cx="6.5" cy="18.5" r="2.3"/><circle class="s" cx="17.5" cy="7.5" r="2.3"/><path class="s" d="M6.5 7.8v8.4M17.5 9.8c0 4-3.6 4.6-11 6.4"/></svg>`,
    terminal: `<svg viewBox="0 0 24 24" aria-hidden="true"><rect class="s" x="2.5" y="4" width="19" height="16" rx="2.5"/><path class="s" d="M6.5 9l3.3 3-3.3 3M12 15.5h5"/></svg>`,
    desktop: `<svg viewBox="0 0 24 24" aria-hidden="true"><rect class="s" x="2.5" y="4" width="19" height="12.5" rx="2"/><path class="s" d="M8.5 20.5h7M12 16.5v4"/></svg>`,
    zip: `<svg viewBox="0 0 24 24" aria-hidden="true"><path class="s" d="M6 2.8h8.2l4.3 4.3V21.2H6z"/><path class="s" d="M10.5 3v2M12.5 5v2M10.5 7v2M12.5 9v2M10.5 11v2"/><rect class="s" x="10" y="14.5" width="3.5" height="3.5" rx=".8"/></svg>`,
    loc: `<svg viewBox="0 0 24 24" aria-hidden="true"><path class="f" d="M20.8 3.2L3.6 10.4c-.8.3-.7 1.5.2 1.6l7.1.9.9 7.1c.1.9 1.3 1 1.6.2z"/></svg>`,
  };

  // ---------- app icons: img[data-ph="app:name"] (system apps get their look, any other name a generic app) ----------
  const W = "#fff";
  const G = {
    phone: `<path d="M8.4 3.6l2.3 3.9c.4.6.2 1.4-.4 1.8l-1.5 1c1.1 2.3 2.9 4.1 5.2 5.2l1-1.5c.4-.6 1.2-.8 1.8-.4l3.9 2.3c.6.4.8 1.2.4 1.8l-1.1 1.9c-.7 1.1-2 1.6-3.2 1.3C10.9 18.8 5.2 13.1 4 7.2c-.3-1.2.2-2.5 1.3-3.2l1.3-.8c.6-.4 1.4-.2 1.8.4z" fill="${W}"/>`,
    chat: `<path d="M12 4C7 4 3 7.3 3 11.4c0 2.3 1.3 4.4 3.3 5.8-.2 1.3-.8 2.5-1.8 3.4 2 0 3.7-.7 5-1.8.8.2 1.6.3 2.5.3 5 0 9-3.3 9-7.4S17 4 12 4z" fill="${W}"/>`,
    heart: `<path d="M12 20s-7.5-4.6-7.5-10.4A4.3 4.3 0 0 1 12 7a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z" fill="${W}"/>`,
    sun: `<circle cx="12" cy="12" r="4.6" fill="${W}"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9L7 7M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" stroke="${W}" stroke-width="2.2" stroke-linecap="round"/>`,
    moon: `<path d="M15.5 3.5a8.5 8.5 0 1 0 5 13.6A7 7 0 0 1 15.5 3.5z" fill="${W}"/>`,
    chart: `<path d="M4 19.5h16M7 16v-5M12 16V7M17 16v-8" stroke="${W}" stroke-width="2.8" stroke-linecap="round" fill="none"/>`,
    note: `<path d="M9 17.5V5.5l10-2v12" fill="none" stroke="${W}" stroke-width="2.4" stroke-linejoin="round"/><circle cx="6.6" cy="17.6" r="2.7" fill="${W}"/><circle cx="16.6" cy="15.6" r="2.7" fill="${W}"/>`,
    pin: `<path d="M12 22s7-7.1 7-12.2A7 7 0 0 0 5 9.8C5 14.9 12 22 12 22z" fill="${W}"/><circle cx="12" cy="9.8" r="2.6" fill="var(--c)"/>`,
    fork: `<path d="M7.5 3v7.5M5 3v5a2.5 2.5 0 0 0 5 0V3M7.5 10.5V21M16.5 3c-2.2 2-2.2 6.4 0 8.5V21" fill="none" stroke="${W}" stroke-width="2.3" stroke-linecap="round"/>`,
    book: `<path d="M4.5 4.5h6a2 2 0 0 1 2 2V20a2 2 0 0 0-2-2h-6zM19.5 4.5h-5a2 2 0 0 0-2 2V20a2 2 0 0 1 2-2h5z" fill="${W}"/>`,
    leaf: `<path d="M5 19c0-8.3 5.2-13.4 14-14 0 9.2-5.2 14-13 14z" fill="${W}"/><path d="M5.5 18.5l8-8" stroke="var(--c)" stroke-width="1.8"/>`,
    lift: `<path d="M3 9v6M6 7v10M18 7v10M21 9v6M6 12h12" stroke="${W}" stroke-width="2.6" stroke-linecap="round" fill="none"/>`,
    bolt: `<path d="M13.5 2L5 13.5h6L9.5 22 19 9.5h-6.2z" fill="${W}"/>`,
    cart: `<path d="M3 4h3l2 11h10l2-8H7" fill="none" stroke="${W}" stroke-width="2.3" stroke-linejoin="round" stroke-linecap="round"/><circle cx="9.5" cy="19" r="1.8" fill="${W}"/><circle cx="17" cy="19" r="1.8" fill="${W}"/>`,
    mail: `<rect x="2.8" y="5.2" width="18.4" height="13.6" rx="2.4" fill="${W}"/><path d="M4.2 7l7.8 6 7.8-6" fill="none" stroke="var(--c)" stroke-width="1.9"/>`,
    camera: `<path d="M3 8.5a2 2 0 0 1 2-2h2.6L9 4.2h6l1.4 2.3H19a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" fill="${W}"/><circle cx="12" cy="13" r="3.6" fill="var(--c)"/><circle cx="12" cy="13" r="2" fill="${W}"/>`,
    pencil: `<path d="M4 20l1.1-4.6L16.6 3.9a2.1 2.1 0 0 1 3 3L8.1 18.4zM14.6 5.9l3 3" fill="none" stroke="${W}" stroke-width="2.2" stroke-linejoin="round"/>`,
    check: `<path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="${W}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>`,
    plane: `<path d="M21 3L3 10.5l6.8 2.7L12.5 21z" fill="${W}"/>`,
    play: `<path d="M8 5v14l11-7z" fill="${W}"/>`,
    paw: `<circle cx="7" cy="9" r="2.1" fill="${W}"/><circle cx="11" cy="6.2" r="2.1" fill="${W}"/><circle cx="15.6" cy="7.4" r="2.1" fill="${W}"/><circle cx="18" cy="11.4" r="2" fill="${W}"/><path d="M12 11.5c-3 0-6 4-6 6.2 0 1.7 1.4 2.3 3 2.3 1.3 0 2-.6 3-.6s1.7.6 3 .6c1.6 0 3-.6 3-2.3 0-2.2-3-6.2-6-6.2z" fill="${W}"/>`,
    cup: `<path d="M5 8h11v6a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5z" fill="${W}"/><path d="M16 9.5h1.6a2.4 2.4 0 0 1 0 4.8H16" fill="none" stroke="${W}" stroke-width="2"/><path d="M8.5 3.5c-.8 1 .8 1.5 0 2.5M12 3.5c-.8 1 .8 1.5 0 2.5" stroke="${W}" stroke-width="1.6" stroke-linecap="round" fill="none"/>`,
    film: `<rect x="3.5" y="5" width="17" height="14" rx="2" fill="${W}"/><path d="M7.5 5v14M16.5 5v14M3.5 9.5h4M3.5 14.5h4M16.5 9.5h4M16.5 14.5h4" stroke="var(--c)" stroke-width="1.6"/>`,
    game: `<path d="M7 8h10a4 4 0 0 1 4 4.5l-.6 3.8a2.3 2.3 0 0 1-4 1.1L14.6 15H9.4l-1.8 2.4a2.3 2.3 0 0 1-4-1.1L3 12.5A4 4 0 0 1 7 8z" fill="${W}"/><path d="M7.5 10.6v3M6 12.1h3" stroke="var(--c)" stroke-width="1.6" stroke-linecap="round"/><circle cx="15.8" cy="11.2" r="1" fill="var(--c)"/><circle cx="17.6" cy="13" r="1" fill="var(--c)"/>`,
    gear: `<circle cx="12" cy="12" r="3.2" fill="none" stroke="${W}" stroke-width="2.4"/><path d="M12 2.5v3.2M12 18.3v3.2M2.5 12h3.2M18.3 12h3.2M5.3 5.3l2.2 2.2M16.5 16.5l2.2 2.2M5.3 18.7l2.2-2.2M16.5 7.5l2.2-2.2" stroke="${W}" stroke-width="2.6" stroke-linecap="round"/>`,
    cloud: `<path d="M7 18.5a4.5 4.5 0 0 1-.4-9 6 6 0 0 1 11.5 1.6 3.7 3.7 0 0 1-.6 7.4z" fill="${W}"/>`,
  };
  // [glyph, top colour, bottom colour]
  const SYS = {
    phone: ["phone", "#6ee36f", "#2fbf4a"], messages: ["chat", "#6ee36f", "#2fbf4a"], facetime: ["camera", "#6ee36f", "#2fbf4a"],
    mail: ["mail", "#3fb5ff", "#1a6ef0"], music: ["note", "#ff6b81", "#f9243f"], podcasts: ["note", "#c86df7", "#8b2ee0"],
    settings: ["gear", "#a1a1a6", "#636366"], camera: ["camera", "#b8b8bd", "#6f6f74"], weather: ["sun", "#4aa8ff", "#1f6ed8"],
    maps: ["pin", "#7fd36b", "#3ba3f0"], notes: ["pencil", "#ffd84d", "#f5b700"], clock: ["chart", "#3a3a3c", "#000000"],
    appstore: ["bolt", "#3fb5ff", "#1a6ef0"], "app store": ["bolt", "#3fb5ff", "#1a6ef0"], wallet: ["cart", "#3a3a3c", "#000000"],
  };
  const PALS = [["#ff8a80", "#f0435a"], ["#6cb4ff", "#2f6fe8"], ["#ffc06a", "#f58b1f"], ["#b28cff", "#7a4be6"], ["#5fd6a0", "#1f9e6b"],
    ["#ff9ad1", "#e54a9b"], ["#62d8f0", "#1a96c8"], ["#ffb37a", "#ee6b25"], ["#9aa8b8", "#5b6878"], ["#7fe0c8", "#14a38a"],
    ["#ff8f8f", "#d93636"], ["#8f9dff", "#4b4fe0"], ["#ffd36b", "#e6a10e"], ["#7cd0ff", "#1b86d6"]];
  const GENERIC = [["Fitly", "heart"], ["Chatter", "chat"], ["Sunny", "sun"], ["Dozy", "moon"], ["Budgy", "chart"], ["Tunely", "note"],
    ["Wander", "pin"], ["Cookit", "fork"], ["Readr", "book"], ["Leafy", "leaf"], ["Lift", "lift"], ["Zapp", "bolt"], ["Shoply", "cart"],
    ["Inboxy", "mail"], ["Snapz", "camera"], ["Notely", "pencil"], ["Tasky", "check"], ["Trippy", "plane"], ["Movo", "play"], ["Petly", "paw"],
    ["Brewly", "cup"], ["Flixy", "film"], ["Gamr", "game"], ["Cloudy", "cloud"]];
  const DOCK = ["phone", "safari", "messages", "music"];
  function appSVG(name) {
    const key = String(name).trim().toLowerCase();
    const open = (a, b) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient></defs><rect width="120" height="120" fill="url(#g)"/>`;
    if (key === "safari") return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#e6e6ea"/></linearGradient><linearGradient id="b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2ad1fb"/><stop offset="1" stop-color="#1a72f0"/></linearGradient></defs><rect width="120" height="120" fill="url(#g)"/><circle cx="60" cy="60" r="44" fill="url(#b)"/>${Array.from({ length: 24 }, (_, i) => `<rect x="59" y="19" width="2" height="${i % 6 ? 5 : 8}" fill="#fff" opacity=".85" transform="rotate(${i * 15} 60 60)"/>`).join("")}<path d="M60 60L83 37 66 66z" fill="#ff3b30"/><path d="M60 60L37 83 54 54z" fill="#fff"/></svg>`;
    if (key === "photos") { const C = ["#f9c430", "#f68a1e", "#ee4037", "#c43fa0", "#8e59d6", "#3f86f2", "#3fc2e8", "#6cc24a"]; return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><rect width="120" height="120" fill="#fff"/>${C.map((c, i) => `<ellipse cx="60" cy="38" rx="13" ry="22" fill="${c}" opacity=".88" transform="rotate(${i * 45} 60 60)"/>`).join("")}</svg>`; }
    if (key === "calendar") return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><rect width="120" height="120" fill="#fff"/><text x="60" y="36" font-size="19" font-weight="600" fill="#ff3b30" text-anchor="middle" font-family="Helvetica Neue, Arial, sans-serif">THURSDAY</text><text x="60" y="94" font-size="62" font-weight="300" fill="#000" text-anchor="middle" font-family="Helvetica Neue, Arial, sans-serif">30</text></svg>`;
    let glyph, a, b;
    if (SYS[key]) [glyph, a, b] = SYS[key];
    else {
      const gen = GENERIC.find(([n]) => n.toLowerCase() === key), h = hash(key), p = PALS[h % PALS.length];
      glyph = gen ? gen[1] : GENERIC[(h >>> 4) % GENERIC.length][1];
      [a, b] = p;
    }
    return open(a, b) + `<g transform="translate(24 24) scale(3)" style="--c:${b}">${G[glyph] || G.heart}</g></svg>`;
  }
  AR.wbAppIcon = (name) => uri(appSVG(nm(name)));
  const app = (name, dock) => {
    const s = el("span", "wb-app");
    s.innerHTML = `<img class="wb-appicon" alt="" src="${AR.wbAppIcon(name)}">${dock ? "" : `<em>${esc(name)}</em>`}`;
    return s;
  };

  // ---------- iOS alerts: the exact system wording ----------
  const ALERTS = {
    notif: (a) => ({ title: `“${a}” Would Like to Send You Notifications`, msg: "Notifications may include alerts, sounds, and icon badges. These can be configured in Settings.",
      btns: [["deny", "Don’t Allow"], ["allow", "Allow", "wb-pref"]] }),
    att: (a, why) => ({ title: `Allow “${a}” to track your activity across other companies’ apps and websites?`,
      msg: why || "Your data will be used to deliver personalized ads to you.", btns: [["deny", "Ask App Not to Track"], ["allow", "Allow"]], col: true }),
    location: (a, why) => ({ title: `Allow “${a}” to use your location?`, msg: why || `${a} uses your location to show what’s nearby.`, map: true,
      btns: [["once", "Allow Once"], ["allow", "Allow While Using App"], ["deny", "Don’t Allow"]], col: true }),
  };
  const MAP_SVG = `<svg viewBox="0 0 270 172" preserveAspectRatio="xMidYMid slice"><rect width="270" height="172" fill="#f1eee8"/>
    <path d="M0 118c40-6 62 6 96 30 14 10 18 24 18 24H0z" fill="#aad3f5"/><path d="M168 0h62c-4 22 6 40 28 50l12 6V0z" fill="#c9e7b2"/><rect x="128" y="104" width="44" height="34" rx="4" fill="#c9e7b2"/>
    <g fill="none" stroke-linecap="round"><g stroke="#ddd8cf" stroke-width="10"><path d="M-10 70H280M52 -10L84 182M150 -10L196 182M-10 24L280 40M230 -10L210 182"/></g>
    <g stroke="#fff" stroke-width="7"><path d="M-10 70H280M52 -10L84 182M150 -10L196 182M-10 24L280 40M230 -10L210 182"/></g>
    <path d="M-10 150C70 120 180 128 280 96" stroke="#f0c75e" stroke-width="12"/><path d="M-10 150C70 120 180 128 280 96" stroke="#fde293" stroke-width="8"/></g>
    <circle cx="135" cy="86" r="30" fill="#007aff" opacity=".14"/><circle cx="135" cy="86" r="10.5" fill="#fff"/><circle cx="135" cy="86" r="7.5" fill="#007aff"/></svg>`;
  function buildAlert(a) {
    if (a.dataset.built) return;
    a.dataset.built = "1";
    const kind = a.dataset.alert || "custom", name = nm(a.dataset.app || "@app"), why = a.dataset.why ? nm(a.dataset.why) : "";
    const spec = ALERTS[kind] ? ALERTS[kind](name, why) : {
      title: nm(a.dataset.title || ""), msg: nm(a.dataset.msg || ""), col: a.dataset.col === "1",
      btns: (a.dataset.btns || "Cancel|*OK").split("|").map((b) => { const pref = b[0] === "*", t = pref ? b.slice(1) : b; return [t.toLowerCase().replace(/[^a-z0-9]+/g, "-"), t, pref ? "wb-pref" : ""]; }),
    };
    const btns = spec.btns.map(([k, t, c]) => `<span class="wb-al-btn ${c || ""}" data-btn="${k}"><i class="wb-al-hi"></i><span>${esc(t)}</span></span>`).join("");
    a.innerHTML = `<div class="wb-al-body"><b class="wb-al-title">${esc(spec.title)}</b>${spec.msg ? `<span class="wb-al-msg">${esc(spec.msg)}</span>` : ""}</div>` +
      (spec.map ? `<div class="wb-al-map">${MAP_SVG}<span class="wb-al-precise">${PICONS.loc}Precise: On</span></div>` : "") +
      `<div class="wb-al-btns${spec.col || spec.btns.length > 2 ? " wb-col" : ""}">${btns}</div>`;
  }

  // ---------- the builders, run by AR.webInit (AR.names) ----------
  function phoneInit(root) {
    all("[data-i]:not([data-wbi])", root).forEach((e) => {
      const svg = PICONS[e.dataset.i];
      if (!svg) return;
      e.dataset.wbi = "1";
      e.classList.add("wb-i");
      e.innerHTML = svg;
    });
    all('img[data-ph^="app:"]:not([src])', root).forEach((img) => { img.src = AR.wbAppIcon(img.dataset.ph.slice(4)); });
    all(".wb-home-grid[data-fill], .wb-dock[data-fill]", root).forEach((g) => {
      if (g.dataset.filled) return;
      g.dataset.filled = "1";
      const dock = g.classList.contains("wb-dock"), own = Array.from(g.children), n = Math.max(own.length, +g.dataset.fill || 0);
      const r = rnd(hash("home" + (g.dataset.seed || g.id || ""))), order = GENERIC.map((x) => x[0]);
      for (let i = order.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [order[i], order[j]] = [order[j], order[i]]; }
      const list = [];
      for (let i = 0; list.length < n - own.length; i++) list.push(app(dock ? DOCK[i % DOCK.length] : order[i % order.length], dock));
      own.forEach((o, j) => { const at = o.dataset.at != null ? +o.dataset.at : list.length; list.splice(Math.min(at, list.length), 0, o); });
      g.textContent = "";
      list.forEach((x) => g.appendChild(x));
    });
    all(".wb-alert", root).forEach(buildAlert);
    all(".wb-sys", root).forEach((s) => {
      if (!s.querySelector(":scope > .wb-sys-dim")) { const d = el("i", "wb-sys-dim"); d.setAttribute("data-layout-ignore", ""); s.prepend(d); }
      s.setAttribute("data-layout-allow-overlap", "");
    });
    all(".wb-bs", root).forEach((s) => {
      if (!s.querySelector(":scope > .wb-bs-dim")) { const d = el("i", "wb-bs-dim"); d.setAttribute("data-layout-ignore", ""); s.prepend(d); }
      const p = s.querySelector(".wb-bs-panel");
      if (p && p.dataset.grab !== "0" && !p.querySelector(":scope > .wb-bs-grab")) p.prepend(el("i", "wb-bs-grab"));
      s.setAttribute("data-layout-allow-overlap", "");
    });
    all(".wb-launch, .wb-tip, .wb-urlchip.wb-fly, .wb-gh-clone", root).forEach((e) => e.setAttribute("data-layout-allow-overlap", ""));
    all(".wb-switch", root).forEach((s) => { if (!s.querySelector(":scope > i")) s.appendChild(el("i")); });
  }
  if (!AR.webInit || !AR.webInit._phone) {
    const init0 = AR.webInit;
    AR.webInit = function (root) { phoneInit(root); return init0 ? init0.apply(this, arguments) : undefined; };
    AR.webInit._phone = 1;
  }

  // ---------- the overworld map: pixel glyphs, island, route ----------
  const PX = {
    flag: { p: { K: "#1d1b2e", P: "#7b808a", G: "#3fbf4f", g: "#2c9a3a", Y: "#f7c531" }, m: ["..YY............", "..YY............", "..KK............",
      "..PKKKKKKKK.....", "..PGGGGGGGGKK...", "..PGGGGGGGGGGKK.", "..PGgGGGGGGGGGGK", "..PGggGGGGGGGKK.", "..PGGgggGGGKK...", "..PKKKKKKKK.....",
      "..P.............", "..P.............", "..P.............", "..P.............", ".KKK............", "KKKKK..........."] },
    chest: { p: { K: "#3a1d0a", B: "#c07a35", b: "#8d5220", Y: "#f2c12e" }, m: ["..KKKKKKKKKKKK..", ".KBBBBBBBBBBBBK.", "KBBbBBBBBBBBbBBK", "KBBbBBBBBBBBbBBK",
      "KYYYYYYYYYYYYYYK", "KYYYYYYKKYYYYYYK", "KBBbBBBYYBBBbBBK", "KBBbBBBYYBBBbBBK", "KBBbBBBBBBBBbBBK", "KBBbBBBBBBBBbBBK", "KYYYYYYYYYYYYYYK", "KKKKKKKKKKKKKKKK"] },
    "chest-open": { p: { K: "#3a1d0a", B: "#c07a35", b: "#8d5220", Y: "#f2c12e", O: "#ffd84a", w: "#fffbe0" }, m: ["..KKKKKKKKKKKK..", ".KBBBBBBBBBBBBK.",
      "KBBbBBBBBBBBbBBK", "KYYYYYYYYYYYYYYK", "KKKKKKKKKKKKKKKK", "KwOOwOOOwOOwOOwK", "KOOOOOOOOOOOOOOK", "KYYYYYYKKYYYYYYK", "KBBbBBBYYBBBbBBK", "KBBbBBBBBBBBbBBK",
      "KYYYYYYYYYYYYYYK", "KKKKKKKKKKKKKKKK"] },
    wall: { p: { K: "#4a1f14", R: "#d2603f", r: "#a8432a" }, m: ["KKKKKKKKKKKKKKKK", "KRRRRRRKRRRRRRRK", "KrrrrrrKrrrrrrrK", "KKKKKKKKKKKKKKKK", "KRRRKRRRRRRKRRRK",
      "KrrrKrrrrrrKrrrK", "KKKKKKKKKKKKKKKK", "KRRRRRRKRRRRRRRK", "KrrrrrrKrrrrrrrK", "KKKKKKKKKKKKKKKK", "KRRRKRRRRRRKRRRK", "KrrrKrrrrrrKrrrK", "KKKKKKKKKKKKKKKK"] },
    lock: { p: { K: "#2a2433", k: "#9aa0a8", Y: "#f2c12e", y: "#c99a1c" }, m: ["...KKKKKK...", "..KkkkkkkK..", ".KkK....KkK.", ".KkK....KkK.", ".KkK....KkK.",
      "KKKKKKKKKKKK", "KYYYYYYYYYYK", "KYYYYKKYYYYK", "KYYYYKKYYYYK", "KYYYYYKYYYYK", "KyyyyyyyyyyK", "KKKKKKKKKKKK"] },
    star: { p: { K: "#3a1d00", Y: "#f7c531", y: "#e0a514", w: "#fff6c4" }, m: [".....KK.....", "....KYYK....", "....KYYK....", "KKKKKwYYKKKK", "KYYYYwYYYYYK",
      ".KYYYYYYYYK.", "..KYYYYYYK..", "..KYYyyYYK..", ".KYYyKKyYYK.", ".KyyK..KyyK.", "KKKK....KKKK"] },
    bulb: { p: { K: "#3a2a00", Y: "#ffd84a", w: "#fffbe0", g: "#9aa0a8", G: "#c8ccd2" }, m: ["....KKKK....", "..KKYYYYKK..", ".KYYwYYYYYK.", ".KYwYYYYYYK.",
      "KYYYYYYYYYYK", "KYYYYYYYYYYK", ".KYYYYYYYYK.", ".KYYYYYYYYK.", "..KYYYYYYK..", "...KYYYYK...", "...KggggK...", "...KGGGGK...", "...KggggK...", "....KKKK...."] },
  };
  function pxSVG(name) {
    const P = PX[name];
    if (!P) return "";
    const w = P.m[0].length, h = P.m.length;
    let o = `<svg viewBox="0 0 ${w} ${h}" shape-rendering="crispEdges" preserveAspectRatio="xMidYMid meet">`;
    P.m.forEach((row, y) => { let x = 0; while (x < w) { const c = row[x]; let e = x; while (e < w && row[e] === c) e++; if (c !== ".") o += `<rect x="${x}" y="${y}" width="${e - x}" height="1" fill="${P.p[c]}"/>`; x = e; } });
    return o + "</svg>";
  }
  AR.questGlyph = pxSVG;
  const XMARK = `<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="46" fill="#d9473a" stroke="#1d1b2e" stroke-width="8"/><path d="M32 32 L68 68 M68 32 L32 68" stroke="#fff" stroke-width="13" stroke-linecap="square"/></svg>`;
  const OKMARK = `<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="46" fill="#2fa35b" stroke="#1d1b2e" stroke-width="8"/><path d="M28 52 L44 67 L73 35" fill="none" stroke="#fff" stroke-width="13" stroke-linecap="square" stroke-linejoin="miter"/></svg>`;
  // a smooth route through points (Catmull-Rom as cubic Beziers), and points sampled along it
  function curveSegs(pts, k = 0.5) {
    const segs = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      segs.push([p1, [p1[0] + ((p2[0] - p0[0]) * k) / 3, p1[1] + ((p2[1] - p0[1]) * k) / 3], [p2[0] - ((p3[0] - p1[0]) * k) / 3, p2[1] - ((p3[1] - p1[1]) * k) / 3], p2]);
    }
    return segs;
  }
  const curveD = (segs) => `M${segs[0][0][0]},${segs[0][0][1]}` + segs.map(([, a, b, c]) => ` C${a[0].toFixed(1)},${a[1].toFixed(1)} ${b[0].toFixed(1)},${b[1].toFixed(1)} ${c[0]},${c[1]}`).join("");
  const curvePts = (segs, n = 24) => segs.flatMap(([p0, p1, p2, p3]) => Array.from({ length: n }, (_, i) => {
    const t = i / n, u = 1 - t;
    return [u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0], u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]];
  }));
  // auto layout: a zig-zag from START to the goal, left to right in a wide frame, bottom to top in a tall one, with room
  // for the number badges above the nodes and the tags under them (40 px from the edges, `top` and `bottom` px kept clear)
  function layoutPts(Wd, Ht, n, top, size, bottom = 0) {
    const pts = [], up = size * 0.68, down = size * 0.92 + 40 + bottom;
    if (Wd / Ht >= 1.1) {
      const hi = top + up, lo = Ht - down, y0 = (hi + lo) / 2, x0 = Math.max(Wd * 0.1, size * 0.5 + 44), x1 = Wd - x0;
      pts.push([x0, y0]);
      for (let i = 0; i < n; i++) pts.push([x0 + ((x1 - x0) * (i + 1)) / (n + 1), n === 1 ? y0 : i % 2 ? hi : lo]);
      pts.push([x1, y0]);
    } else {
      const y1 = Ht - down, y2 = top + up, xl = Wd * 0.3, xr = Wd * 0.7;
      pts.push([Wd * 0.5, y1]);
      for (let i = 0; i < n; i++) pts.push([n === 1 ? Wd * 0.5 : i % 2 ? xr : xl, y1 + ((y2 - y1) * (i + 1)) / (n + 1)]);
      pts.push([Wd * 0.5, y2]);
    }
    return pts.map(([x, y]) => [Math.round(x), Math.round(y)]);
  }
  // the island: water, foam, a grass island with a dirt cliff on its south side, trees, rocks and flowers, all on a pixel grid
  function islandSVG(Wd, Ht, avoid, o) {
    const g = o.px ?? 8, cols = Math.ceil(Wd / g), rows = Math.ceil(Ht / g), r = rnd(hash("qm" + (o.seed ?? 1)));
    const mx = o.margin ?? Math.round(Math.min(Wd, Ht) * 0.06), ax = Wd / 2 - mx, ay = Ht / 2 - mx - g * 2;
    const ph = [r() * 6.3, r() * 6.3, r() * 6.3];
    const inside = (x, y) => {
      const u = (x - Wd / 2) / ax, v = (y - Ht / 2 + g) / ay, a = Math.atan2(v, u);
      const R = 1 + 0.045 * (Math.sin(3 * a + ph[0]) + 0.6 * Math.sin(5 * a + ph[1]) + 0.4 * Math.sin(9 * a + ph[2]));
      return Math.pow(Math.abs(u), 4) + Math.pow(Math.abs(v), 4) <= Math.pow(R, 4);
    };
    const L = [], at = (c, rr) => (c >= 0 && rr >= 0 && c < cols && rr < rows ? L[rr][c] : 0);
    for (let rr = 0; rr < rows; rr++) { L.push([]); for (let c = 0; c < cols; c++) L[rr].push(inside((c + 0.5) * g, (rr + 0.5) * g) ? 1 : 0); }
    const K = [];   // 1 grass, 2 rim, 3 cliff top, 4 cliff, 5 cliff foot, 6 foam
    for (let rr = 0; rr < rows; rr++) {
      K.push([]);
      for (let c = 0; c < cols; c++) {
        let k = 0;
        if (L[rr][c]) k = at(c - 1, rr) && at(c + 1, rr) && at(c, rr - 1) && at(c, rr + 1) ? 1 : 2;
        else if (at(c, rr - 1)) k = 3;
        else if (at(c, rr - 2)) k = 4;
        else if (at(c, rr - 3)) k = 5;
        K[rr].push(k);
      }
    }
    for (let rr = 0; rr < rows; rr++) for (let c = 0; c < cols; c++) {
      if (K[rr][c]) continue;
      const near = [[-1, 0], [1, 0], [0, -1], [0, 1]].some(([dx, dy]) => { const q = K[rr + dy] && K[rr + dy][c + dx]; return q && q !== 6; });
      if (near) K[rr][c] = 6;
    }
    const COL = { 1: "#7cc653", 2: "#4f9a37", 3: "#8a5a2f", 4: "#734a26", 5: "#5c3a1e", 6: "#a9dcff" };
    let o2 = `<svg class="wb-qm-world" width="${Wd}" height="${Ht}" viewBox="0 0 ${Wd} ${Ht}" shape-rendering="crispEdges" data-layout-ignore><rect width="${Wd}" height="${Ht}" fill="#3d7fd6"/>`;
    for (let i = 0; i < (cols * rows) / 90; i++) { const x = Math.floor(r() * cols), y = Math.floor(r() * rows); if (!K[y][x] && !(K[y][x + 1]) && !(K[y][x + 2])) o2 += `<rect x="${x * g}" y="${y * g}" width="${g * 3}" height="${g / 2}" fill="#79b6f2"/><rect x="${x * g + g}" y="${y * g - g / 2}" width="${g}" height="${g / 2}" fill="#79b6f2"/>`; }
    for (let rr = 0; rr < rows; rr++) {
      let c = 0;
      while (c < cols) { const k = K[rr][c]; let e = c; while (e < cols && K[rr][e] === k) e++; if (k) o2 += `<rect x="${c * g}" y="${rr * g}" width="${(e - c) * g}" height="${g}" fill="${COL[k]}"/>`; c = e; }
    }
    // grass texture: tufts and light specks
    for (let i = 0; i < (cols * rows) / 14; i++) {
      const x = Math.floor(r() * cols), y = Math.floor(r() * rows);
      if (K[y][x] !== 1) continue;
      o2 += r() < 0.55 ? `<rect x="${x * g + g / 4}" y="${y * g + g / 4}" width="${g / 2}" height="${g / 2}" fill="#69b545"/><rect x="${x * g + g * 0.75}" y="${y * g}" width="${g / 4}" height="${g / 2}" fill="#69b545"/>`
        : `<rect x="${x * g + g / 4}" y="${y * g + g / 4}" width="${g / 4}" height="${g / 4}" fill="#9fe070"/>`;
    }
    // trees, bushes, rocks, flowers: off the route and the nodes
    const TREE = { p: { K: "#1e3b23", G: "#3f9b46", g: "#7ed36b", d: "#2c6e33", T: "#7a4a24" }, m: [".....KKKK.....", "...KKGGGGKK...", "..KGGgGGGGGK..",
      ".KGGgGGGGGGGK.", ".KGGGGGGGgGGK.", "KGGGGGGGGGGGGK", "KGgGGGGGGGGGGK", "KGGGGGGgGGGGGK", ".KGGGGGGGGGGK.", ".KdGGGGGGGGdK.", "..KddGGGGddK..",
      "...KKddddKK...", ".....KTTK.....", ".....KTTK.....", "....KKTTKK...."] };
    const ROCK = { p: { K: "#3a3a44", R: "#a6a8b0", r: "#7d808a", w: "#d4d6dc" }, m: ["..KKKK..", ".KRwRRK.", "KRRRRrRK", "KRrRRRrK", ".KKKKKK."] };
    const BUSH = { p: { K: "#1e3b23", G: "#4fae4a", g: "#86d86c" }, m: [".KKK.KK.", "KGgGKGGK", "KGGGGGgK", ".KKKKKK."] };
    const spr = (S, x0, y0, u) => S.m.map((row, y) => { let s = ""; let x = 0; while (x < row.length) { const c = row[x]; let e = x; while (e < row.length && row[e] === c) e++; if (c !== ".") s += `<rect x="${x0 + x * u}" y="${y0 + y * u}" width="${(e - x) * u}" height="${u}" fill="${S.p[c]}"/>`; x = e; } return s; }).join("");
    const land = (x, y) => { const c = Math.floor(x / g), rr = Math.floor(y / g); return K[rr] && K[rr][c] === 1; };
    const clear = (x, y, rad) => avoid.every(([ax2, ay2, ar]) => Math.hypot(x - ax2, y - ay2) > ar + rad);
    const placed = [], u = o.tree ?? Math.max(3, Math.round(g / 2));
    const tries = Math.round((Wd * Ht) / 900);
    for (let i = 0; i < tries; i++) {
      const x = r() * Wd, y = r() * Ht, kind = r(), S = kind < 0.62 ? TREE : kind < 0.82 ? BUSH : ROCK;
      const w = S.m[0].length * u, h = S.m.length * u, rad = Math.max(w, h) * 0.55;
      if (!land(x - w / 2, y - h / 2) || !land(x + w / 2, y - h / 2) || !land(x - w / 2, y + h / 2) || !land(x + w / 2, y + h / 2)) continue;
      if (!clear(x, y, rad) || placed.some(([px2, py2, pr]) => Math.hypot(x - px2, y - py2) < (pr + rad) * 0.9)) continue;
      placed.push([x, y, rad, S, w, h]);
    }
    placed.sort((a2, b2) => a2[1] - b2[1]).forEach(([x, y, , S, w, h]) => {
      if (S === TREE) o2 += `<rect x="${Math.round(x - w * 0.36)}" y="${Math.round(y + h / 2 - u)}" width="${Math.round(w * 0.72)}" height="${u * 2}" fill="#2f6e2c" opacity=".35"/>`;
      o2 += spr(S, Math.round(x - w / 2), Math.round(y - h / 2), u);
    });
    for (let i = 0; i < (Wd * Ht) / 5000; i++) {
      const x = r() * Wd, y = r() * Ht;
      if (!land(x, y) || !clear(x, y, 8)) continue;
      const c = ["#ffffff", "#ffe066", "#ff8fb1"][Math.floor(r() * 3)];
      o2 += `<rect x="${Math.round(x)}" y="${Math.round(y)}" width="${u}" height="${u}" fill="${c}"/><rect x="${Math.round(x + u * 2)}" y="${Math.round(y + u)}" width="${u}" height="${u}" fill="${c}"/>`;
    }
    return o2 + "</svg>";
  }

  /* AR.questMap(parent, {id, w, h, nodes: [{icon, tag, bad, num}], start: {icon, tag}, goal: {icon, tag}, pts, size, top,
     bottom, bad, plate, seed, px, route: {under, dash}}) draws an overworld into parent: a pixel island (or `plate`, an
     image path), the dashed route START -> 1..N -> goal, and the nodes. pts: [[x, y], ...] for START, each node and the
     goal (default: a zig-zag, left to right in a wide parent, bottom to top in a tall one, between `top` px from the top
     and `bottom` px from the bottom, e.g. top 330 and bottom 470 keep a 1080x1920 route inside y 250-1450). icon: a pixel
     glyph (flag chest chest-open wall lock star bulb), an image path, or text (an emoji). Returns {el, nodes, pts, size}
     where nodes[0] is START, nodes[1..N] the steps and nodes[N+1] the goal. */
  AR.questMap = function (parent, cfg = {}) {
    const p = one(parent), Wd = cfg.w ?? p.offsetWidth, Ht = cfg.h ?? p.offsetHeight, id = cfg.id || (p.id ? p.id + "-map" : "qm");
    const list = cfg.nodes || [], n = list.length, top = cfg.top ?? 0;
    const size = cfg.size ?? Math.round(Wd / Ht >= 1.1 ? Math.min(140, Ht * 0.22) : Math.min(230, Wd * 0.17));
    const pts = cfg.pts || layoutPts(Wd, Ht, n, top, size, cfg.bottom ?? 0);
    const box = el("div", "wb-qm");
    box.id = id;
    Object.assign(box.style, { width: Wd + "px", height: Ht + "px" });
    const segs = curveSegs(pts), samples = curvePts(segs);
    const avoid = samples.map(([x, y]) => [x, y, size * 0.2 + 10]).concat(pts.map(([x, y]) => [x, y + size * 0.25, size * 0.8 + 20]));
    if (cfg.avoid) cfg.avoid.forEach((a) => avoid.push(a));
    if (cfg.plate) box.innerHTML = `<img class="wb-qm-world" src="${cfg.plate}" alt="" style="width:${Wd}px;height:${Ht}px;object-fit:cover;image-rendering:pixelated" data-layout-ignore>`;
    else if (cfg.world !== false) box.innerHTML = islandSVG(Wd, Ht, avoid, cfg);
    const R = cfg.route || {}, d = curveD(segs);
    box.insertAdjacentHTML("beforeend", `<svg class="wb-qm-route" width="${Wd}" height="${Ht}" viewBox="0 0 ${Wd} ${Ht}" data-layout-ignore>` +
      `<path d="${d}" fill="none" stroke="${R.under || "#2d4a1c"}" stroke-width="${size * 0.19}" stroke-linejoin="round" opacity=".5"/>` +
      `<path d="${d}" fill="none" stroke="${R.dash || "#fff4c9"}" stroke-width="${size * 0.093}" stroke-dasharray="${size * 0.13} ${size * 0.1}" stroke-linejoin="round"/></svg>`);
    const icon = (v) => {
      v = nm(v);
      if (!v) return "";
      if (PX[v]) return `<span class="wb-qm-icon">${pxSVG(v)}</span>`;
      if (/\.(png|jpe?g|webp|gif|svg)$/i.test(v) || /^(assets\/|data:)/.test(v)) return `<img class="wb-qm-icon" src="${v}" alt="">`;
      return `<span class="wb-qm-icon">${esc(v)}</span>`;
    };
    const specs = [Object.assign({ icon: "flag", tag: "START", key: "start" }, cfg.start || {})]
      .concat(list.map((s, i) => Object.assign({ num: i + 1, bad: cfg.bad !== false, key: "n" + (i + 1) }, s)))
      .concat([Object.assign({ icon: "chest", tag: "GOAL", key: "goal" }, cfg.goal || {})]);
    const nodes = specs.map((s, i) => {
      const nd = el("div", "wb-qm-node" + (s.bad ? " wb-qm-bad" : ""));
      nd.id = `${id}-${s.key}`;
      Object.assign(nd.style, { left: pts[i][0] + "px", top: pts[i][1] + "px", "--qm": size + "px" });
      nd.innerHTML = `<i class="wb-qm-ring" id="${nd.id}-ring"></i><i class="wb-qm-disc"></i>${icon(s.icon)}` +
        (s.num != null && s.num !== false ? `<b class="wb-qm-num" data-layout-allow-overlap>${esc(s.num)}</b>` : "") +
        (s.tag ? `<span class="wb-qm-tag">${esc(nm(s.tag))}</span>` : "") +
        `<i class="wb-qm-mark" id="${nd.id}-x">${XMARK}</i><i class="wb-qm-mark wb-qm-ok" id="${nd.id}-ok">${OKMARK}</i>`;
      if (s.open) nd.dataset.open = s.open;
      box.appendChild(nd);
      return nd;
    });
    p.appendChild(box);
    const map = { el: box, nodes, pts, size, id, n, segs };
    box._qm = map;
    return map;
  };
  const mapOf = (m) => (m && m.nodes ? m : one(m) && one(m)._qm);
  const standAt = (M, i) => [M.pts[i][0] - M.size * 0.05, M.pts[i][1] - M.size * 0.3];   // on the disc's upper half: the icon stays in view
  // where a player stands on node i ([x, y] of its feet, in the map's px)
  AR.questSpot = (map, i) => standAt(mapOf(map), i);
  // marks already on a node at the cut: AR.questSet(map, {crossed: [1, 2], fixed: [3]})
  AR.questSet = function (map, o = {}) {
    const M = mapOf(map);
    (o.crossed || []).forEach((i) => { M.nodes[i].querySelector(".wb-qm-mark:not(.wb-qm-ok)").style.opacity = 1; });
    (o.fixed || []).forEach((i) => { M.nodes[i].querySelector(".wb-qm-ok").style.opacity = 1; });
    (o.hidden || []).forEach((i) => { M.nodes[i].style.opacity = 0; });
    return M;
  };
  // stands a sprite or critter (any element whose feet are its bottom centre, in the map's parent) on node i
  AR.questStand = function (map, who, i, o = {}) {
    const M = mapOf(map), w = one(who), [x, y] = standAt(M, i);
    Object.assign(w.style, { left: x - w.offsetWidth / 2 + (o.dx ?? 0) + "px", top: y - w.offsetHeight + (o.dy ?? 0) + "px" });
    w._qmAt = i;
    return w;
  };
  // the player hops from the node it stands on onto node i, landing at t (an arc of o.h px, o.dur s)
  AR.questHop = function (tl, map, who, i, t, o = {}) {
    const M = mapOf(map), w = one(who), dur = o.dur ?? 0.28;
    if (!AR.toss) return tl;
    AR.toss(tl, w, t - dur, { to: standAt(M, i), anchor: [0.5, 1], h: o.h ?? M.size * 0.85, dur, squash: o.squash ?? true });
    w._qmAt = i;
    return tl;
  };
  // node i lights up: a gold ring flashes and the node bumps (o.off: when the ring goes)
  AR.questLight = function (tl, map, i, t, o = {}) {
    const M = mapOf(map), nd = M.nodes[i], ring = nd.querySelector(".wb-qm-ring");
    tl.fromTo(ring, { opacity: 1, scale: 0.7 }, { opacity: 1, scale: 1, duration: 0.18, ease: "back.out(2)", immediateRender: false }, t);
    if (o.off != null) tl.to(ring, { opacity: 0, duration: 0.15 }, o.off);
    tl.fromTo(nd, { scale: 1.16 }, { scale: 1, duration: 0.3, ease: "back.out(3)", immediateRender: false }, t);
    return tl;
  };
  // a red X ("x") or a green check ("ok") lands on node i at t; a check replaces the X
  AR.questMark = function (tl, map, i, kind, t, o = {}) {
    const M = mapOf(map), nd = M.nodes[i], ok = kind === "ok", m = nd.querySelector(ok ? ".wb-qm-ok" : ".wb-qm-mark:not(.wb-qm-ok)"), d = o.dur ?? 0.12;
    tl.fromTo(m, { opacity: 0, scale: o.from ?? 2.2, rotation: -12 }, { opacity: 1, scale: 1, rotation: 0, duration: d, ease: "power4.in", immediateRender: false }, t - d);
    tl.set(m, { scaleX: 1.15, scaleY: 0.86 }, t);
    tl.to(m, { scaleX: 1, scaleY: 1, duration: 0.18, ease: "back.out(3)" }, t);
    if (ok) { const x = nd.querySelector(".wb-qm-mark:not(.wb-qm-ok)"); tl.fromTo(x, { opacity: Number(x.style.opacity) || 1 }, { opacity: 0, duration: 0.001, immediateRender: false }, t - d); }
    return tl;
  };
  // node i is thrown onto the route from o.from ([x, y] in the map, default above it), landing at t
  AR.questDrop = function (tl, map, i, t, o = {}) {
    const M = mapOf(map), nd = M.nodes[i], dur = o.dur ?? 0.24;
    if (!AR.toss) return tl;
    return AR.toss(tl, nd, t - dur, { from: o.from || [M.pts[i][0], M.pts[i][1] - 400], to: M.pts[i], anchor: [0.5, 0.5], h: o.h ?? 140, dur, show: true, squash: true });
  };
  // the goal opens: its chest glyph swaps to the open one, the ring flashes, sparkles fly
  AR.questWin = function (tl, map, t, o = {}) {
    const M = mapOf(map), nd = M.nodes[M.nodes.length - 1], ic = nd.querySelector(".wb-qm-icon");
    if (ic && ic.tagName !== "IMG" && PX[nd.dataset.open || "chest-open"]) {
      const open = el("span", "wb-qm-icon", pxSVG(nd.dataset.open || "chest-open"));
      open.style.opacity = 0;
      ic.after(open);
      tl.fromTo(ic, { opacity: 1 }, { opacity: 0, duration: 0.001, immediateRender: false }, t);
      tl.fromTo(open, { opacity: 0 }, { opacity: 1, duration: 0.001, immediateRender: false }, t);
    }
    AR.questLight(tl, M, M.nodes.length - 1, t);
    const r = rnd(o.seed ?? 5), s = M.size, cols = ["#f7c531", "#ffffff", "#fff3b0", "#7cd0ff"];
    for (let k = 0; k < (o.n ?? 12); k++) {
      const b = el("i");
      b.setAttribute("data-layout-ignore", "");
      const sz = Math.round(s * (0.05 + r() * 0.04));
      Object.assign(b.style, { position: "absolute", left: s / 2 - sz / 2 + "px", top: s * 0.3 + "px", width: sz + "px", height: sz + "px", background: cols[k % 4], opacity: 0 });
      nd.appendChild(b);
      const a = -Math.PI / 2 + (r() - 0.5) * 2.4, v = s * (0.7 + r() * 0.8);
      tl.fromTo(b, { opacity: 1, x: 0, y: 0 }, { x: Math.cos(a) * v, y: Math.sin(a) * v, duration: 0.45, ease: "power2.out", immediateRender: false }, t + r() * 0.05);
      tl.to(b, { opacity: 0, duration: 0.15 }, t + 0.35 + r() * 0.1);
    }
    return tl;
  };

  // ---------- phone helpers ----------
  Object.assign(AR, {
    // a finger taps the phone: a grey dot with a white ring presses in at t (it lands 0.07 s before) and lifts after
    // o.hold (0.16) while a ring ripples out; the target presses in (o.press: false to skip). o.ax/o.ay: where on the
    // target (fractions), o.at: [x, y] in the screen instead, o.screen: the layer to draw in (its .wb-screen).
    wbTap(tl, target, t, o = {}) {
      const tg = one(target), scr = one(o.screen) || screenOf(tg);
      let x, y;
      if (Array.isArray(o.at)) [x, y] = o.at;
      else { const b = boxIn(tg, scr); x = b.x + b.w * (o.ax ?? 0.5) + (o.dx ?? 0); y = b.y + b.h * (o.ay ?? 0.5) + (o.dy ?? 0); }
      const ring = el("i", "wb-tap-ring"), dot = el("i", "wb-tap");
      [ring, dot].forEach((e) => { e.setAttribute("data-layout-ignore", ""); Object.assign(e.style, { left: x + "px", top: y + "px" }); scr.appendChild(e); });
      const hold = o.hold ?? 0.16;
      tl.fromTo(dot, { opacity: 0, scale: 1.5 }, { opacity: 1, scale: 1, duration: 0.07, ease: "power2.out", immediateRender: false }, t - 0.07);
      tl.to(dot, { scale: 0.84, duration: 0.05, ease: "power2.out" }, t);
      tl.to(dot, { opacity: 0, scale: 1.2, duration: 0.16, ease: "power2.out" }, t + hold);
      tl.fromTo(ring, { opacity: 0.95, scale: 0.6 }, { opacity: 0, scale: 2.2, duration: 0.42, ease: "power2.out", immediateRender: false }, t);
      if (o.press !== false && tg !== scr) {
        tl.to(tg, { scale: o.pressScale ?? 0.95, duration: 0.06, ease: "power2.out" }, t);
        tl.to(tg, { scale: 1, duration: 0.18, ease: "back.out(2.5)" }, t + 0.06);
      }
      return dot;
    },

    // the iOS alert in a .wb-sys layer pops in at t (scale 1.18 -> 1 and fade, 0.2 s; readable from t + 0.12) over a dim.
    // o.tap ("allow", "deny", "once" or an index) taps that button at o.at; the alert then fades away.
    wbAlert(tl, sys, t, o = {}) {
      const s = one(sys);
      phoneInit(s.parentElement || s);
      const al = s.querySelector(".wb-alert"), dim = s.querySelector(".wb-sys-dim");
      if (dim && o.dim !== false) tl.fromTo(dim, { opacity: 0 }, { opacity: 1, duration: 0.18, ease: "power1.out" }, t);
      tl.fromTo(al, { opacity: 0, scale: o.from ?? 1.18 }, { opacity: 1, scale: 1, duration: o.dur ?? 0.2, ease: "power2.out" }, t);
      if (o.tap != null) AR.wbAlertTap(tl, s, o.tap, o.at ?? t + 0.7, o);
      return tl;
    },
    // a finger taps one of the alert's buttons at t: it greys, then the alert fades out (o.hold s later) and the dim lifts
    wbAlertTap(tl, sys, which, t, o = {}) {
      const s = one(sys), al = s.querySelector(".wb-alert"), dim = s.querySelector(".wb-sys-dim"), btns = all(".wb-al-btn", s);
      const b = typeof which === "number" ? btns[which] : btns.find((x) => x.dataset.btn === which) || btns.find((x) => x.textContent.trim().toLowerCase() === String(which).toLowerCase()) || btns[btns.length - 1];
      const hi = b.querySelector(".wb-al-hi");
      if (o.finger !== false) AR.wbTap(tl, b, t, { press: false, screen: o.screen, hold: o.hold ?? 0.14 });
      if (hi) tl.fromTo(hi, { opacity: 0 }, { opacity: 1, duration: 0.04, immediateRender: false }, t - 0.02);
      if (o.out !== false) {
        const out = t + (o.hold ?? 0.14) + 0.04;
        tl.to(al, { opacity: 0, duration: 0.2, ease: "power1.in" }, out);
        if (dim) tl.to(dim, { opacity: 0, duration: 0.24, ease: "power1.out" }, out);
      }
      return b;
    },

    // the app opens out of its home screen icon: the finger taps the icon at t, and from t + 0.06 the .wb-launch layer
    // (the app's first screen) grows out of the icon's rounded square to the full screen in o.dur (0.42) while the home
    // screen zooms in behind it. icon: the .wb-app or its img; o.home: the home screen (default the .wb-home beside it).
    wbLaunch(tl, icon, layer, t, o = {}) {
      const ic = one(icon), img = ic.matches("img, .wb-ico") ? ic : ic.querySelector("img, .wb-ico") || ic;
      const L = one(layer), scr = L.offsetParent || L.parentElement, Wd = L.offsetWidth, Ht = L.offsetHeight;
      const lb = boxIn(L, scr), b = boxIn(img, scr), s0 = b.w / Wd, cx = b.x + b.w / 2 - lb.x, cy = b.y + b.h / 2 - lb.y;
      const v0 = Math.max(0, (Ht - b.h / s0) / 2), r0 = (parseFloat(getComputedStyle(img).borderTopLeftRadius) || b.w * 0.22) / s0;
      const tz = t + (o.delay ?? 0.06), dur = o.dur ?? 0.42, ease = o.ease ?? "power3.out";
      if (o.tap !== false) AR.wbTap(tl, img, t, { press: false, screen: scr, hold: 0.1 });
      tl.to(img, { scale: 0.9, duration: 0.07, ease: "power2.out" }, t - 0.03);
      gsap.set(L, { transformOrigin: "50% 50%" });
      // the window keeps rounded corners all the way, ending on the screen's own inner radius
      const scs = getComputedStyle(scr), r1 = Math.max(0, (parseFloat(scs.borderTopLeftRadius) || 0) - (scr.clientLeft || 0));
      tl.fromTo(L, { opacity: 1, x: cx - Wd / 2, y: cy - Ht / 2, scale: s0, "--wl-v": v0, "--wl-r": r0 },
        { opacity: 1, x: 0, y: 0, scale: 1, "--wl-v": 0, "--wl-r": r1, duration: dur, ease, immediateRender: false }, tz);
      const home = o.home === false ? null : one(o.home) || Array.from(scr.children).find((c) => c.classList.contains("wb-home"));
      if (home && home !== L) {
        const hb = boxIn(home, scr);
        gsap.set(home, { transformOrigin: `${b.x + b.w / 2 - hb.x}px ${b.y + b.h / 2 - hb.y}px` });
        tl.fromTo(home, { scale: 1 }, { scale: o.homeScale ?? 1.14, duration: dur, ease, immediateRender: false }, tz);
      }
      return tl;
    },

    // a bottom sheet slides up at t (o.dur 0.3) over a dim; o.out: when it slides back down
    wbSheet(tl, sheet, t, o = {}) {
      const s = one(sheet);
      phoneInit(s.parentElement || s);
      const panel = s.querySelector(".wb-bs-panel"), dim = s.querySelector(".wb-bs-dim"), dur = o.dur ?? 0.3;
      if (dim && o.dim !== false) tl.fromTo(dim, { opacity: 0 }, { opacity: 1, duration: dur, ease: "power1.out" }, t);
      tl.fromTo(panel, { opacity: 1, yPercent: 100 }, { opacity: 1, yPercent: 0, duration: dur, ease: o.ease ?? "power3.out", immediateRender: false }, t);
      if (o.out != null) {
        tl.to(panel, { yPercent: 100, duration: 0.24, ease: "power2.in" }, o.out);
        if (dim) tl.to(dim, { opacity: 0, duration: 0.24 }, o.out);
      }
      return tl;
    },

    // an iOS switch flips (o.on: true/false, default the other state): the knob slides and the track turns green;
    // o.swap: .wb-swapt labels that change with it (each shows its next line)
    wbToggle(tl, sw, t, o = {}) {
      const s = one(sw);
      if (!s.querySelector(":scope > i")) s.appendChild(el("i"));
      const k = s.querySelector(":scope > i"), was = s.classList.contains("wb-on"), on = o.on ?? !was, d = o.dur ?? 0.22;
      if (on !== was) {
        const travel = s.offsetWidth - k.offsetWidth - 2 * k.offsetTop, green = o.color ?? "#34c759", off = "#e9e9ea";
        tl.fromTo(k, { x: 0 }, { x: on ? travel : -travel, duration: d, ease: "power2.inOut", immediateRender: false }, t);
        tl.fromTo(s, { backgroundColor: on ? off : green }, { backgroundColor: on ? green : off, duration: d, ease: "power1.inOut", immediateRender: false }, t);
      }
      all(o.swap).forEach((x) => AR.wbSwapText(tl, x, t + d * 0.5));
      return tl;
    },
    // a .wb-swapt shows its next line at t (or line o.to); a cut, like an iOS label change
    wbSwapText(tl, sel, t, o = {}) {
      const x = one(sel), kids = Array.from(x.children), cur = x._wbSw ?? 0, nxt = o.to ?? Math.min(cur + 1, kids.length - 1);
      if (nxt === cur) return tl;
      tl.fromTo(kids[cur], { opacity: 1 }, { opacity: 0, duration: 0.001, immediateRender: false }, t);
      tl.fromTo(kids[nxt], { opacity: 0 }, { opacity: 1, duration: 0.001, immediateRender: false }, t);
      x._wbSw = nxt;
      return tl;
    },
    // a paywall plan (.wb-plan) is selected at t: its ring and tint move to it, it bumps
    wbPlan(tl, plan, t, o = {}) {
      const pl = one(plan), sibs = Array.from(pl.parentElement.children).filter((x) => x.classList.contains("wb-plan"));
      sibs.forEach((x) => {
        const base = (x.getAttribute("class") || "").split(/\s+/).filter((c) => c && c !== "wb-on").join(" ");
        tl.set(x, { attr: { class: x === pl ? base + " wb-on" : base } }, t);
      });
      if (o.bump !== false) tl.fromTo(pl, { scale: 1.04 }, { scale: 1, duration: 0.22, ease: "back.out(3)", immediateRender: false }, t);
      return tl;
    },
    // the price lands on its word: "count" (default) shows up at t - o.dur and rolls up from o.from (0) to land at t
    // (o.dur 0.3), keeping its format ($29.99/year, 1,250 coins); "pop" keeps it hidden until it pops in at t; "bump"
    // leaves it in place and bumps it at t. Every mode bumps the element (o.bump: false to skip).
    wbPrice(tl, sel, t, o = {}) {
      const box = one(sel);
      let tg = box;
      while (tg.children.length && !Array.from(tg.childNodes).some((c) => c.nodeType === 3 && /\d/.test(c.textContent))) {
        const next = Array.from(tg.children).find((c) => /\d/.test(c.textContent));
        if (!next) break;
        tg = next;
      }
      const mode = o.mode ?? "count", d = o.dur ?? 0.3;
      if (mode === "count") {
        const txt = tg.textContent, m = txt.match(/^([\s\S]*?)(\d[\d,]*(?:\.\d+)?)([\s\S]*)$/);
        if (m) {
          const pre = m[1], num = parseFloat(m[2].replace(/,/g, "")), dec = (m[2].split(".")[1] || "").length, post = m[3], from = o.from ?? 0;
          const f = (v) => pre + Number(v).toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec, useGrouping: m[2].includes(",") || num >= 10000 }) + post;
          const ease = gsap.parseEase(o.ease ?? "power2.out"), n = Math.max(2, Math.round(d * 30));
          tg.textContent = f(from);
          if (o.show !== true) tl.fromTo(box, { opacity: 0 }, { opacity: 1, duration: 0.001 }, t - d);
          for (let i = 1; i <= n; i++) tl.set(tg, { textContent: f(from + (num - from) * ease(i / n)) }, t - d + (d * i) / n);
          tl.set(tg, { textContent: txt }, t);
        }
      } else if (mode === "pop") {
        tl.fromTo(tg, { opacity: 0 }, { opacity: 1, duration: 0.001 }, t - 0.04);
      }
      if (o.bump !== false) tl.fromTo(box, { scale: o.scale ?? 1.18 }, { scale: 1, duration: 0.26, ease: "back.out(3)", immediateRender: false }, t);
      return tl;
    },

    // a camera target for a phone in a wide frame: an invisible band as wide as the phone (o.screen: the screen only)
    // and as tall as the targets (their union, plus o.pad px above and below). AR.frame(tl, cam, AR.wbBand(el), t, dur,
    // {fit: "width", pad: 0}) fills a 2:1 card with that strip of the phone instead of a narrow column of it.
    wbBand(targets, o = {}) {
      const list = all(targets), ph = list[0].closest(".wb-phone") || list[0].offsetParent, ref = o.screen ? list[0].closest(".wb-screen") || ph : ph;
      let y0 = Infinity, y1 = -Infinity;
      list.forEach((e) => { const b = boxIn(e, ph); y0 = Math.min(y0, b.y); y1 = Math.max(y1, b.y + b.h); });
      const r = boxIn(ref, ph), pad = o.pad ?? 12, band = el("i", "wb-band");
      band.setAttribute("data-layout-ignore", "");
      Object.assign(band.style, { position: "absolute", left: r.x + "px", width: r.w + "px", top: y0 - pad + "px", height: y1 - y0 + 2 * pad + "px", pointerEvents: "none" });
      ph.appendChild(band);
      return band;
    },
    // a dropdown or popover opens at t (fades and grows from its transform-origin, 0.14 s); o.button gets pressed with it
    // (o.pressed: the colour it keeps while open, e.g. "#1a7f37" for GitHub's Code button); o.out closes it
    wbMenu(tl, menu, t, o = {}) {
      const m = one(menu);
      tl.fromTo(m, { opacity: 0, scale: 0.96, y: -8 }, { opacity: 1, scale: 1, y: 0, duration: o.dur ?? 0.14, ease: "power2.out" }, t);
      if (o.button) {
        const b = one(o.button);
        tl.to(b, { scale: 0.95, duration: 0.05, ease: "power2.out" }, t - 0.05);
        tl.to(b, { scale: 1, duration: 0.16, ease: "back.out(3)" }, t);
        if (o.pressed) tl.fromTo(b, { backgroundColor: getComputedStyle(b).backgroundColor }, { backgroundColor: o.pressed, duration: 0.001, immediateRender: false }, t - 0.05);
      }
      if (o.out != null) tl.to(m, { opacity: 0, duration: 0.12 }, o.out);
      return tl;
    },
    // click-to-copy: the button presses, its copy icon turns into a green check and a "Copied!" tip pops over it at t,
    // fading o.hold (1.0) s later (false keeps it). o.text, o.tip (your own .wb-tip), o.parent (where the tip goes).
    wbCopied(tl, btn, t, o = {}) {
      const b = one(btn), copy = b.querySelector('[data-i="copy"]'), ok = b.querySelector(".wb-ok");
      if (copy && ok) {
        tl.fromTo(copy, { opacity: 1 }, { opacity: 0, duration: 0.001, immediateRender: false }, t);
        tl.fromTo(ok, { opacity: 0 }, { opacity: 1, duration: 0.001, immediateRender: false }, t);
      }
      tl.to(b, { scale: 0.9, duration: 0.05, ease: "power2.out" }, t - 0.04);
      tl.to(b, { scale: 1, duration: 0.16, ease: "back.out(3)" }, t + 0.01);
      let tip = o.tip ? one(o.tip) : null;
      if (!tip) {
        tip = el("span", "wb-tip");
        tip.textContent = o.text ?? "Copied!";
        tip.setAttribute("data-layout-allow-overlap", "");
        const host = one(o.parent) || b.offsetParent || b.parentElement;
        host.appendChild(tip);
        const bb = boxIn(b, host);
        Object.assign(tip.style, { left: Math.round(bb.x + bb.w / 2 - tip.offsetWidth / 2) + "px", top: Math.round(bb.y - tip.offsetHeight - 14) + "px" });
      }
      tl.fromTo(tip, { opacity: 0, scale: 0.7, y: 8 }, { opacity: 1, scale: 1, y: 0, duration: 0.14, ease: "back.out(2.6)", immediateRender: false }, t);
      if (o.hold !== false) tl.to(tip, { opacity: 0, duration: 0.18 }, t + (o.hold ?? 1.0));
      return tip;
    },
    // a chip (a span.wb-urlchip.wb-fly in a layer that holds both ends) lifts off `from` at o.lift (default t - 0.16),
    // rising o.rise px (its own height) so it clears the text under it, flies an arc of o.arc px and lands on `to` at
    // t + dur; then it hands over to `to` (your hidden copy of the chip in its final place, e.g. inside a composer),
    // which shows with a squash. The chip keeps its own size unless o.fit.
    wbChip(tl, chip, from, to, t, dur = 0.4, o = {}) {
      const c = one(chip), a = one(from), z = one(to), host = c.offsetParent || c.parentElement;
      const A = boxIn(a, host), B = boxIn(z, host), cw = c.offsetWidth, ch = c.offsetHeight;
      Object.assign(c.style, { left: Math.round(A.x + A.w / 2 - cw / 2) + "px", top: Math.round(A.y + A.h / 2 - ch / 2) + "px" });
      const dx = B.x + B.w / 2 - (A.x + A.w / 2), dy = B.y + B.h / 2 - (A.y + A.h / 2), s1 = o.fit ? B.w / cw : 1;
      const lift = o.lift ?? t - 0.16, y0 = -(o.rise ?? ch);
      tl.fromTo(c, { opacity: 0, scale: 0.8, y: 0 }, { opacity: 1, scale: 1.08, y: y0, duration: 0.16, ease: "back.out(2)", immediateRender: false }, lift);
      const ya = Math.min(y0, dy) - (o.arc ?? 110), ta = (dur * Math.sqrt(y0 - ya)) / (Math.sqrt(y0 - ya) + Math.sqrt(dy - ya));
      tl.fromTo(c, { x: 0 }, { x: dx, duration: dur, ease: "power1.inOut", immediateRender: false }, t);
      tl.fromTo(c, { y: y0 }, { y: ya, duration: ta, ease: "power1.out", immediateRender: false }, t);
      tl.fromTo(c, { y: ya }, { y: dy, duration: dur - ta, ease: "power1.in", immediateRender: false }, t + ta);
      tl.fromTo(c, { scale: 1.08 }, { scale: s1, duration: dur, ease: "power1.inOut", immediateRender: false }, t);
      tl.set(c, { opacity: 0 }, t + dur);
      if (o.handover !== false) {
        tl.fromTo(z, { opacity: 0 }, { opacity: 1, duration: 0.001 }, t + dur);
        tl.fromTo(z, { scaleX: 1.12, scaleY: 0.84 }, { scaleX: 1, scaleY: 1, duration: 0.22, ease: "back.out(3)", immediateRender: false }, t + dur);
      }
      return tl;
    },
  });
})();
