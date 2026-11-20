export const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x);
export const mix = (a, b, x) => a + (b - a) * x;
export const ramp = (t, a, b) => clamp((t - a) / (b - a));

export const easeOut = (x) => 1 - Math.pow(1 - clamp(x), 3);
export const easeOut5 = (x) => 1 - Math.pow(1 - clamp(x), 5);
export const easeIn = (x) => Math.pow(clamp(x), 3);
export const easeInOut = (x) => {
  x = clamp(x);
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
};
/* a short rise then a slow fall, for pulses */
export const bell = (t, at, len) => {
  const x = clamp((t - at) / len);
  if (x <= 0 || x >= 1) return 0;
  return Math.sin(x * Math.PI) ** 1.6;
};

export const set = (el, o) => {
  for (const k in o) el.style[k] = o[k];
};

export const seeded = (seed = 1) => {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
};

export const isVertical = () => window.innerHeight > window.innerWidth;
