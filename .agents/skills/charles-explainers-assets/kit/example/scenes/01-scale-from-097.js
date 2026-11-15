/* Example: "Scale from 0.97" as a flip, from the motion-hacks reel's scene 1, with the agent making the change.
   A "Publish this page?" dialog opens once a second on the same 250 ms keyframes. Before, they start at scale 0, so
   it bursts out of a dot; after, at 0.97, so it fades in almost where it lands. The agent glides in from below,
   double-clicks the 0 (it selects in the agent's colour), and on the change word 0.97 morphs in under green. */
(() => {
  const { div, zoom, E, prog, lerp, agent, agentAt, fpx } = H$;
  const DW = 340, DH = 150, Z = 1.95;
  const IN = 0.25, SHOWN = 0.6;
  const OPENS = [0.7, 1.7, 2.7, 3.7, 4.5, 5.5, 6.5, 7.5, 8.5];

  H$.scene({
    code: {
      lang: 'css',
      select: true,
      lines: [
        '@keyframes enter {',
        '  from { opacity: 0; scale: {{0|0.97}} } }',
        '.dialog { animation: enter 250ms',
        '  cubic-bezier(0.32, 0.72, 0, 1) }',
      ],
    },
    stills: { before: 3.73, pick: 4.38, after: 5.53 },
    build(stage, area, ctx) {
      const T = ctx.T;
      const zb = zoom(stage, { w: DW, h: DH, z: Z, cy: area.mid });
      const dlg = div(zb, { w: DW, h: DH, style: { borderRadius: '16px', background: 'var(--card)', transformOrigin: '50% 50%',
        boxShadow: '0 0 0 1px rgb(16 18 24 / 0.06), 0 2px 4px rgb(16 18 24 / 0.05), 0 18px 44px -14px rgb(16 18 24 / 0.32)' } });
      div(dlg, { x: 22, y: 22, text: 'Publish this page?', style: { font: '600 17px/22px Inter', letterSpacing: '-0.015em', color: 'var(--ink)', whiteSpace: 'nowrap' } });
      div(dlg, { x: 22, y: 50, text: 'Anyone with the link can view it.', style: { font: '400 14px/20px Inter', color: 'var(--muted)', whiteSpace: 'nowrap' } });
      const btn = (x, w, label, primary) => div(dlg, { x, y: 92, w, h: 36, text: label, style: { borderRadius: '9px', textAlign: 'center', font: '600 14px/36px Inter', letterSpacing: '-0.005em',
        background: primary ? 'var(--accent)' : 'var(--card)', color: primary ? '#fff' : 'var(--ink)', boxShadow: primary ? 'none' : 'inset 0 0 0 1px var(--line)' } });
      btn(DW - 22 - 88, 88, 'Publish', true);
      btn(DW - 22 - 88 - 8 - 80, 80, 'Cancel', false);

      const ag = agent(ctx.panel);
      let to, from;
      return (t) => {
        let o = 0, s = 1;
        for (const t0 of OPENS) {
          if (t < t0 || t >= t0 + SHOWN) continue;
          const e = E.out(prog(t, t0, t0 + IN));
          s = lerp(t0 < T ? 0 : 0.97, 1, e);
          o = e;
        }
        dlg.style.opacity = o;
        dlg.style.scale = String(s);
        dlg.style.visibility = o > 0 ? 'visible' : 'hidden';

        // Aim at the old value's lower-left corner: the arrow sits off the digit, and 0.97 grows away from it.
        if (!to) {
          const b = ctx.block.slotBox(0);
          to = [b.x + fpx(3), b.y + b.h - fpx(6)];
          from = [to[0] + fpx(160), H$.BAND.bottom + fpx(20)];
        }
        const a = agentAt(t, { T, from, to, action: 'double', after: 'fade' });
        ag.set(a.x, a.y, a);
      };
    },
  });
})();
