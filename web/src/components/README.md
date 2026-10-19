# RÉSIVO web — component & class contract

This README is the interface every page agent codes against. It lists exactly
what `web/src/styles/*.css`, `Icon.astro` and `BrandMark.astro` provide.

The stylesheet imports are fixed (Tailwind's `@import` must be first so its
layers are declared before we add to them):

```css
@import "tailwindcss";
@import "./tokens.css";
@import "./fonts.css";
```

> **Rule of the house:** no raw hex, no inline `font-size`/`px` values, no
> Google Fonts, no emoji, no bitmap icons. Use the token utilities and the
> classes below. If a value is missing, add it to `tokens.css` — never inline it.

---

## 1. Tailwind token utilities

Values live in `web/src/styles/tokens.css`; `global.css` maps them with
`@theme inline` so these utilities resolve through `var()`. Use them with the
`bg-` / `text-` / `border-` / `ring-` prefixes (`border-ok-line`, `bg-surface`…).

### Colours

| Group | Utility names (`bg-<name>`, `text-<name>`, `border-<name>`) |
|---|---|
| Surfaces & neutrals | `canvas` `surface` `subtle` `line` `line-strong` |
| Text | `ink` `ink-2` `muted` `on-dark` `on-dark-2` |
| Brand | `navy-900` `navy-800` `navy-700` `teal-600` `teal-500` `green-500` `gold-500` `gold-300` |
| Status — ink / bg / border | `ok` `ok-bg` `ok-line` · `pending` `pending-bg` `pending-line` · `review` `review-bg` `review-line` · `progress` `progress-bg` `progress-line` · `danger` `danger-bg` `danger-line` |

Gold is an accent, never text on white; `gold-300` text only on navy.

### Text scale (size + line-height + weight in one utility)

`text-display` 32/40 · `text-h1` 24/32 · `text-h2` 18/26 · `text-h3` 15/22 ·
`text-body` 14/22 · `text-small` 12/18 · `text-overline` 11/16 (+0.08em, use with
`uppercase` or the `.overline` class). Each utility sets size + line-height +
weight (plus tracking for `display`/`overline`); heading elements render in
Outfit and body/UI text in Inter via the base layer.

### Fonts, radii, elevation, spacing

- `font-display` (Outfit), `font-sans` (Inter) — body is already Inter 14/22.
- `rounded-input` (8) · `rounded-card` (12) · `rounded-hero` (20) · `rounded-pill`
- `shadow-e1` (cards at rest) · `shadow-e2` (dialogs, popovers, toasts)
- Spacing uses Tailwind's numeric scale; the DESIGN.md values are
  **1 = 4px · 2 = 8 · 3 = 12 · 4 = 16 · 6 = 24 · 8 = 32 · 12 = 48**.
  Stick to those seven steps for layout gaps/padding.

---

## 2. Authored classes (`@layer components` in `global.css`)

### Buttons

```html
<button class="btn btn-primary">Approve</button>
<button class="btn btn-secondary btn-sm">Cancel</button>
<button class="btn btn-gradient">Register as student</button>
```

| Class | Purpose |
|---|---|
| `.btn` | base: inline-flex, gap 8px, min-height **44px**, radius 8, 14/600, focus ring, transition. Works on `<button>`, `<a>` and `<label>`. |
| `.btn-sm` | 36px min-height, 12/600, tighter padding |
| `.btn-icon` | square 44px icon-only control (`.btn-icon.btn-sm` = 36px) |
| `.btn-primary` | navy-800, hover navy-700 — default action |
| `.btn-accent` | teal-600, darkens on hover — links/confirmations |
| `.btn-secondary` | white + strong border + secondary ink, hover subtle — cancel/neutral |
| `.btn-danger` | danger ink on white with danger border — destructive (non-final) |
| `.btn-danger-solid` | solid danger — the final confirm in a destructive dialog only |
| `.btn-gradient` | the 135° brand gradient — **landing-hero primary CTA only** |
| `.btn-ghost` | transparent, hover subtle — low-emphasis actions |

Disabled: set `disabled` (or `aria-disabled="true"` on an `<a>`) → subtle bg,
muted text, `cursor: not-allowed`. **A disabled action always gets an
explanatory tooltip** (`title` + `aria-describedby` copy).

### Form controls

```html
<label class="label" for="phone">Phone</label>
<input id="phone" class="input" aria-invalid="false" />
<p class="field-hint">Algerian mobile, 10 digits.</p>
<p class="field-error"><Icon name="alert-circle" size={14} /> Number is invalid.</p>
```

| Class | Behaviour |
|---|---|
| `.input` `.textarea` `.select` | 44px min-height, 1px `line`, radius 8, teal 2px focus ring, invalid = danger border + danger-bg tint, disabled = subtle + muted |
| `.textarea` | min-height 96px, vertical resize |
| `.label` | 12/600 `ink-2` |
| `.field-hint` | 12/400 `muted` |
| `.field-error` | 12/500 `danger` + gap 6px for the alert icon |

### Cards & headings

| Class | Behaviour |
|---|---|
| `.card` | white surface, 1px `line`, radius 12, `shadow-e1` — add padding with `p-4`/`p-6` |
| `.card-flat` | same card without the shadow |
| `.hero-card` | radius 20 for hero containers (gradient only on the landing/resident pass) |
| `.card-title` | Outfit 18/26 600 — the card heading |
| `.overline` | 11/600 uppercase +0.08em, `muted` — labels, table headers, section eyebrows |

### Status badges (colour + icon + label, never colour alone)

```html
<span class="badge badge-ok"><Icon name="check-circle" size={13} /> Approved</span>
```

`.badge` + `.badge-ok` / `-pending` / `-review` / `-progress` / `-danger` /
`-neutral` (ink/bg/border straight from the status table). `.pill-gold-on-navy`
is the gold-on-navy counter pill — dark surfaces only.

### Data table

```html
<div class="table-wrap">
  <table class="table">
    <thead><tr><th>Ticket</th><th class="num">Days open</th></tr></thead>
    <tbody><tr aria-selected="true">…</tr></tbody>
  </table>
</div>
```

- `.table-wrap` — surface card, radius 12, 1px `line`, `position: relative`,
  horizontal scroll on mobile. Add a `max-height` utility when you want the
  sticky header to engage inside the scroll region.
- `.table` — full width, no gridlines, sticky `subtle` overline header (40px),
  44px rows, hairline row separators, hover = `subtle`
  (`[aria-selected="true"]` / `.is-selected` = selection tint with navy-800 ink).
- `.num` — right-aligned tabular figures for numeric cells.

### Segmented control

`.seg` (subtle track, radius 8) wrapping `.seg-item` buttons; mark the active
one with `aria-pressed="true"` (white surface + navy-800 ink + hairline).
Items are 44px tall.

### Feedback & decoration

| Class | Behaviour |
|---|---|
| `.skeleton` | pulse placeholder block; size with `h-*`/`w-*` |
| `.divider` | 1px `line` rule |
| `.gradient-top-line` | 3px brand gradient strip (shell top edge) |
| `.live-dot` | 8px dot; `--connected` (teal, pulsing) · `--reconnecting` (gold) · `--offline` (danger) — always pair with a text label |
| `.toast` | fixed bottom-right desktop / above the mobile tab bar, surface + `shadow-e2` + fade-slide in |
| `.visually-hidden` | screen-reader-only |
| `.link` | teal-600 inline link, underline on hover |

### Base helpers

`.tnum` tabular figures (IDs, room numbers, counts, dates) · `.measure` 70ch
paragraph cap · `.pb-safe` iOS home-indicator padding.

---

## 3. `Icon.astro`

```astro
import Icon from '../components/Icon.astro';
<Icon name="wrench" size={20} class="text-teal-600" />
<Icon name="id-card" size={18} title="Student card ID" />
```

- Props: `name`, `size` (default 20), `class`, `title`. With `title` the SVG
  gets `<title>` + `role="img"`; without it, `aria-hidden="true"`.
- 24px grid, stroke 1.75, round caps/joins, `currentColor`, no fills.
- Canonical names:
  `alert-circle, alert-triangle, arrow-left, arrow-left-right, arrow-right,
  bed, bell, building, calendar, check, check-circle, chevron-down,
  chevron-left, chevron-right, chevron-up, clock, copy, dashboard, door,
  download, droplet, edit, external-link, eye, file-spreadsheet, file-text,
  filter, hammer, home, id-card, image, info, key, lock, log-in, log-out,
  mail, map-pin, maximize, menu, moon, phone, plus, qr, refresh, search,
  settings, shield, shield-check, spinner, sun, trash, upload, user,
  user-check, users, wifi, wrench, x, x-circle, zap, zoom-in, zoom-out`.
- Legacy aliases: `swap`→`arrow-left-right`, `logout`→`log-out`,
  `login`→`log-in`, `crest`→`shield-check`, `badge`→`id-card`,
  `camera`→`image`, `chevron`→`chevron-right`, `plumbing`→`droplet`,
  `electrical`→`zap`, `furniture`→`hammer`, `internet`→`wifi`.
- Unknown name renders `dashboard` plus a console warning in dev — the build
  never fails. New glyphs go in `Icon.astro` **and** in this list.
- `spinner` has no baked animation: add `class="animate-spin"`.

## 4. `BrandMark.astro`

```astro
<BrandMark variant="mark" size={40} />                         <!-- header -->
<BrandMark variant="logo" tone="white" size={96} alt="RÉSIVO" /> <!-- hero -->
```

| Prop | Values | Notes |
|---|---|---|
| `variant` | `'mark'` (default) · `'logo'` | mark = R + building; logo = stacked |
| `tone` | `'brand'` (default) · `'white'` | white only on navy/gradient |
| `size` | number | rendered **height** in px; width follows the intrinsic ratio (mark 645×599, logo 1029×892) so there is no layout shift |
| `class` | string | e.g. `h-10 w-auto` |
| `alt` | string | defaults to `''` (decorative); set it when the logo stands alone |

Images load eagerly with `decoding="async"` — no layout-blocking scripts.

---

## 5. Rules

1. **Mobile-first.** Bottom tab bar on mobile, top nav on desktop. Touch
   targets ≥ 44px (`.btn`, `.input`, `.seg-item` already comply).
2. **Focus is sacred.** Never remove focus indicators or add `outline: none`
   without a replacement; the global `:focus-visible` is 2px teal at 2px offset.
3. **Reduced motion** is honoured globally — don't add JS animation, and never
   animate table rows during a live-sync redraw.
4. **Status = colour + icon + text label.** Use `.badge-*` with an `Icon` and a
   sentence-case label; never colour alone.
5. **Gradient & gold** only where DESIGN.md §1 allows: landing/login hero,
   resident pass, shell top line, landing primary CTA. Never on cards, tables
   or ordinary buttons.
6. **Sentence case** everywhere; uppercase only for `.overline`/table headers.
   No emoji, no stock imagery. Max paragraph width `.measure`.
7. **No layout shift:** every `<img>` gets `width`/`height`; reserve space for
   async content with `.skeleton`.
8. Empty states, loading skeletons and offline/error banners on every page —
   never leave a blank area.
9. Keep this file in sync when a class, token or icon name changes.
