# Web, social and device UI (`ui-web.css`, `ui-web.js`)

Real products rebuilt at about 2x desktop scale for the 1280x630 card: Chrome, GitHub, iPhone lock screen and
notifications, the App Store, Instagram, data tables, news, search, Slack, Gmail, Google Calendar, Meet, the
Meta Ad Library, Google Sheets and receipts, and the phone and growth UI (iOS alerts, home screen and app launch,
sheets, sign-up walls, paywalls, the tap). Every class starts with `.wb-`. The working demo of every component is
`work/kit-web/` (render `out/demo.mp4`, contact sheets `out/sheet_0N.jpg`); copy markup from its
`compositions/` rather than writing it from scratch. Phone, growth and map demos: `work/kit-phone/` (wide, tall,
full; `out/<name>.mp4`, `out/sheet_0N.jpg`; frame-adaptive scenes in `scenes/`, refreshed by `remount.py`).

- **Icons:** `<i data-i="name"></i>`. Names: back fwd reload x plus minus check tune star star-f heart heart-f
  puzzle kebab more-h search eye fork issue pr actions code folder file book law link history comment send repost
  bookmark camera music play check-c verified grid reels tagged signal wifi battery flashlight archive menu
  chev-d chev-u chev-l chev-r caret mic video cc emoji present hand phone-x info info-f people chat shapes lock
  attach image trash pen font undo redo print paint percent copy sort arrow-r expand calendar folder-move cloud
  apps help gear task fx bold italic strike meta fb ig msgr adbox ig-logo gmail cal31 sheets apple google
  mail-f branch terminal desktop zip loc.
- **Image slots:** `<img class="wb-avatar|wb-logo|wb-favicon|wb-appicon|wb-thumb|wb-shot" src="assets/...">`.
  Fill them with real images from `tools/source.py`. Until then, give the img `data-ph="kind:text"` and no `src`:
  `person:<name>` (portrait), `avatar:<name>` (initials), `logo:<brand>` (claude, stripe, shopify, gmail, github,
  slack, instagram, meta, microsoft, google, calendly; any other name gets a letter mark), `thumb:<seed>` (a
  pixel landscape for posts, ads, wallpapers), `shot:landing` / `shot:pricing` (a 1280 px page). Placeholders
  are for drafts: the finished beat shows the real thing.
- `AR.names()` also runs `AR.webInit()`, which fills icons and placeholders; scenes need no extra line.
- Phone UI is sized in iOS points, `calc(N * var(--pt))`: `.wb-phone` derives `--pt` from its `--pw`; a bare
  `.wb-lock` takes `--pt` from its own style (2 px fills a card). `.wb-scr` is a full-screen layer in the
  `.wb-screen` (393 × 852 pt); `--brand` colours buttons, plans and switches. A phone in a 2:1 card: frame a strip
  of it with `AR.wbBand` rather than the whole phone; a tall card or full screen frames the whole phone, then
  pushes onto the alert or sheet.

## Components

| Component | HTML | Notes |
|---|---|---|
| Chrome window | `.wb-browser[.wb-dark]` > `.wb-tabs` (`.wb-lights`, `.wb-tab.wb-on` > `.wb-fav` img + title + x icon, more `.wb-tab`, `.wb-newtab`) + `.wb-bar` (back/fwd/reload, `.wb-omni` > tune + `.wb-url` + star, puzzle, `img.wb-prof`, kebab) + `.wb-view` > `.wb-page.wb-on` > `.wb-scroll` > `img.wb-shot` or rebuilt HTML | 110 px of chrome, 520 px of page. Per-page titles and URLs go in a `.wb-swap`, each tagged `data-page="<page id>"` |
| hotspot / link | `span.wb-hot` (left/top/width/height in capture px, inside `.wb-scroll`) or `a.wb-link` | gets the hover underline; set `color` to the link's colour |
| macOS cursor | `div.wb-cursor` (left/top, `data-layout-ignore`; `.wb-big` for 1.3x) | arrow and pointing hand; the element itself is the hotspot. Keep it in the same wrapper as the page it points at |
| GitHub repo | `.wb-gh` > `.wb-gh-head` (avatar, `.wb-gh-owner`/`.wb-gh-repo`, `.wb-gh-pub`, `.wb-gh-acts` > `.wb-gh-btn` with icon, label, `em` count) + `.wb-gh-tabs` (`span.wb-on`) + `.wb-gh-main` > `.wb-gh-files` (`.wb-gh-commit`, `.wb-gh-row` > folder or `file.wb-file` icon, `.wb-gh-name`, `.wb-gh-msg`, `.wb-gh-time`) + `.wb-gh-about` (h4, p, `.wb-gh-site`, `.wb-gh-topics` spans, `.wb-gh-meta` spans) | a real capture (`source.py page`) is often better |
| About card | `.wb-gh-card` > `.wb-gh-head` + `.wb-gh-card-acts` + `hr` + `.wb-gh-about` | compact, larger text |
| FREE pill / "16 days" badge | `.wb-free` / `.wb-days` (check-c icon + text), `data-layout-allow-overlap` | stamp it as github-repo does |
| iPhone | `.wb-phone[.wb-dark-ti]` (style `--pw`) > `.wb-screen` > content + `.wb-status[.wb-light]` (time, signal, wifi, battery) + `.wb-island` + `.wb-homebar[.wb-light]` | any size; in a card use `--pw` 600-700 and let the frame crop it |
| lock screen | `.wb-lock` > `img.wb-wall` (optional; a CSS gradient otherwise) + `.wb-lock-date` + `.wb-lock-time` + `.wb-notifs[.wb-stack]` + `.wb-lock-btns` | |
| notification | `.wb-notif[.wb-light]` > `img.wb-appicon` + `.wb-n-main` > `.wb-n-top` (`b.wb-n-app`, `.wb-n-time`) + `.wb-n-title` + `.wb-n-text` (+ `.wb-n-sub`) | frosted material |
| App Store | `.wb-as` (style `--tint`) > `.wb-as-top` (`.wb-as-back`, `.wb-as-app` > appicon + b name, span subtitle, em Get) + `.wb-as-info` (columns of `small`, `b`, `.wb-stars` or text; `b.wb-as-award` has laurels) | inside `.wb-screen` |
| review cards | `.wb-reviews` (font-size sets the scale, `--rw` the card width) > `.wb-rv-track` > `.wb-review` > `.wb-rv-head` (b, date) + `.wb-rv-sub` (`.wb-stars` with `.wb-on`, user) + `p` (… `<a>more</a>`) | |
| Instagram profile | `.wb-ig` > `.wb-ig-top` > `.wb-ig-word`; `.wb-ig-scroll` > `.wb-ig-head` (`.wb-ig-ring` > avatar, `.wb-ig-name` + verified icon + `.wb-ig-btn[.wb-blue]`, `.wb-ig-counts`, `.wb-ig-bio`) + `.wb-ig-hl` + `.wb-ig-tabs` + `.wb-ig-grid` (`--cols` 3, `--tile-ar` 3/4) > `.wb-ig-tile` > `img.wb-thumb` + `.wb-ig-views` (+ `.wb-ig-pin`) | each tile gets a select overlay automatically |
| POSTS counter | `.wb-counter` > copy icon + `.wb-ct-label` + `b` > `.wb-ct-n` + "/738" + `i.wb-ct-done` (check) | |
| reel card / feed | `.wb-reel[.wb-mini]` (`--rw`, default 360) > `img.wb-thumb` or video, `.wb-reel-top`, `.wb-reel-acts` (`.wb-like` > heart + `heart-f.wb-liked` + em), `.wb-reel-meta`, `.wb-reel-views` (mini only), `.wb-heart-pop`; feed: `.wb-feed` (`--rw`) > `.wb-feed-track` > reels | |
| Insights | `.wb-insights` > `.wb-ins-head` (span, `b.wb-ins-num`) + `.wb-ins-pills` + `.wb-ins-chart` (label spans with `top`, `svg viewBox="0 0 1000 300" preserveAspectRatio="none"` > `path.wb-ins-line`, `i.wb-ins-tip`); `.wb-handle-chip` above | |
| data table | `.wb-table[.wb-dark][.wb-serif]` (`--cols`) > `.wb-thead` > `.wb-tr` > `.wb-th`; `.wb-tbody` > `.wb-tr` > `.wb-td` (`.wb-who` > img + `b.wb-name` + `.wb-sub`; `.wb-pill.wb-buy/.wb-sell/.wb-dem/.wb-rep`; `.wb-go`; `i.wb-hover`) | 92 px rows; `.wb-serif` is the SEC-filing look |
| row group / detail | `.wb-group` > `.wb-group-tag`; `.wb-detail` > `.wb-field` (span, b, `i.wb-mark`) | |
| news feed | `.wb-news` > `.wb-news-tabs` + `.wb-news-list` > `.wb-news-row` > thumb or logo + div (b headline, `.wb-news-meta` with `.wb-tick`, `.wb-prem`) | |
| search results | `.wb-serp` > `.wb-res` (`.wb-res-site` > `.wb-fav-c` + b + span; `a.wb-res-title.wb-link`; p); compact: `.wb-src` > favicon + span (em domain) | |
| Slack | `.wb-slack` > `.wb-sl-bar` (lights, `.wb-sl-search`) + `.wb-sl-chan` (b, `.wb-sl-tabs`) + `.wb-sl-msgs` > `.wb-sl-msg` (avatar, `.wb-sl-who` b + `.wb-sl-app` + time, p with `.wb-sl-at`/`.wb-sl-ch`, `.wb-sl-react`) | |
| Gmail mobile | `.wb-gm.wb-gm-m` > `.wb-gm-search` + `.wb-gm-label` + `.wb-gm-list` > `.wb-gm-row[.wb-unread]` (avatar; `.wb-gm-l1`, `.wb-gm-subj`, `.wb-gm-l3`, `.wb-gm-chip` with `--c`) + `.wb-snack` (`b.wb-snack-n`, em) + `.wb-gm-nav` | |
| Gmail compose | `.wb-gm.wb-gm-d` > `.wb-gm-top` + `.wb-gm-tools` + `.wb-gm-drow` + `.wb-compose` > `.wb-cp-head`, `.wb-cp-to` (`.wb-chip-p`, `.wb-cp-cc`), `.wb-cp-subj`, `.wb-cp-body` (`.wb-hl-on`, `.wb-hl` line, `.wb-caret`), `.wb-cp-foot` (`.wb-send`) | `AR.type` on a `.wb-hl` line types it in with the light-blue highlight |
| Gmail thread | `.wb-thread` > `.wb-th-track` > `.wb-th-subj` + `.wb-th-msg[.wb-th-open]` + `.wb-th-more` > span | |
| Calendar | `.wb-cal` (`--days`, `--h0`, `--hours`, `--hh`, `--gut`) > `.wb-cal-top` + `.wb-cal-days` (span > small + `b[.wb-today]`) + `.wb-cal-grid` > `.wb-cal-hr` (`--h`) + `.wb-ev` (`--d`, `--s`, `--e`, `--c`, `--col`; `.wb-short`) + `.wb-slot` | overlaps cascade like Google's |
| Meet | `.wb-meet` > `.wb-meet-tiles` > `.wb-tile.wb-tile-av` (`.wb-tile-ini` with `--c`, `.wb-tile-name`, `.wb-talk`) + `.wb-tile.wb-you` (any content, e.g. a pixel scene) + `.wb-meet-bar` (`.wb-meet-time`, `.wb-meet-btns`, `.wb-hang`, `.wb-meet-side`) | |
| Meta Ad Library | `.wb-ads` > `.wb-ads-top` + `.wb-ads-filters` (`.wb-sel-box`, `.wb-ads-q`) + `.wb-ads-adv` + `.wb-ads-tabs` + `.wb-ads-count` + `.wb-ads-grid` > `.wb-ad[.wb-big]` (`.wb-ad-st` > `.wb-active`, p lines, `.wb-ad-pl`, `.wb-ad-btn`, hr, `.wb-ad-who`, `.wb-ad-copy`, `.wb-ad-media` > thumb + `.wb-ad-play`, `.wb-ad-foot`) | `.wb-big` is the detail view |
| Sheets | `.wb-sheet` (`--cw`, `--rh`) > `.wb-sh-title` (icon, b, `.wb-sh-menu`) + `.wb-sh-tools` + `.wb-sh-fx` (`.wb-sh-name` > A + `.wb-sh-r`, fx, `.wb-sh-val`) + `.wb-sh-grid` > `.wb-sh-cols` + `.wb-sh-body` > `.wb-sh-row` (`.wb-sh-n` + cells) + `.wb-sh-sel`; `.wb-sh-tabs` | Arial cells |
| receipt | `.wb-receipt-wrap` > `.wb-receipt[.wb-top]` > `.wb-rc-brand`, `.wb-rc-cap`, `.wb-rc-line` (`.wb-old` struck price), `.wb-rc-sub`, `.wb-rc-item`, hr, `.wb-rc-total` | mono, zigzag edge |
| landing page with skins | `AR.wbLanding(el, {skin, id, brandColor, brand, links, top, badge, h1, sub, cta, ghost, art, fh, feats: [{emoji, title, text, shot}]})` builds `.wb-land.wb-<skin>` > `.wb-ld-nav` + `.wb-ld-hero` (`.wb-ld-badge`, `h1.wb-ld-h1`, `.wb-ld-sub`, `.wb-ld-ctas` > `.wb-ld-cta` + `.wb-ld-ghost`, `.wb-ld-art`) + `.wb-ld-feats` (`.wb-ld-fh`, `.wb-ld-grid` > `.wb-ld-card` > `.wb-ld-shot` + `.wb-ld-icon` + b + p) | 1280x880; the hero is one Chrome viewport. Skins: `slop` (indigo-violet gradient, glow, everything centred, pill badge, gradient headline, glass emoji cards), `brand` (one `--brand` colour on cream, still centred), `editorial` (left-aligned, big serif headline, eyebrow, real screenshot slots). Copy can differ per skin (`{slop, editorial}`). `art`/`shot` take an image path, `{img}`, HTML, `"dash"`/`"list"`/`"stamps"`/`"alert"` (built-in product mocks) or false. With `id`, parts get `<id>-h1` and so on. For a real site, capture it with `source.py page` instead |
| iOS alert | `.wb-sys` > `.wb-alert[data-alert][data-app][data-why]` | `notif` ("“X” Would Like to Send You Notifications", Don’t Allow / **Allow**), `att` ("Allow “X” to track your activity across other companies’ apps and websites?", Ask App Not to Track / Allow, stacked), `location` ("Allow “X” to use your location?", map with Precise: On, Allow Once / Allow While Using App / Don’t Allow), `custom` (`data-title`, `data-msg`, `data-btns="Cancel\|*OK"`, `*` = bold). `data-app` takes `@key`; `data-why` is the purpose string. AR.names() writes the exact wording and adds the dim. Hidden until `AR.wbAlert`; `.wb-on` shows it from the cut |
| home screen | `.wb-scr.wb-home` > [`img.wb-wall`] + `.wb-home-grid[data-fill="24"][data-seed]` > `.wb-app[data-at="9"]` > `img.wb-appicon` + `em` + `.wb-home-search` + `.wb-dock[data-fill="4"]` | `data-fill` pads with generic apps; `data-at` places yours. `img[data-ph="app:Name"]` draws an icon (phone, messages, safari, music, mail, photos, camera, settings, maps, weather, notes, calendar and clock look like the system apps) |
| app launch | `.wb-launch` > the app's first screen (`.wb-scr.wb-splash` with `--brand` > div > img + b, or any `.wb-scr`) | over the home screen, hidden until `AR.wbLaunch` |
| bottom sheet | `.wb-bs` > `.wb-bs-panel` > `img.wb-bs-icon` + `.wb-bs-title` + `.wb-bs-text` + `.wb-btn` + `.wb-btn.wb-ghost` | grabber and dim added by AR.names(); hidden until `AR.wbSheet`. A full-screen modal: panel `top:0; padding:0; border-radius:0`, `data-grab="0"` |
| buttons, switch | `.wb-btn` (`.wb-apple` + `<i data-i="apple">`, `.wb-google` + `<i data-i="google">`, `.wb-grey`, `.wb-ghost`, `.wb-round`), `.wb-switch[.wb-on]`, `.wb-swapt` (stacked lines, the first shown) | 52 pt buttons, 17 pt semibold, 51 × 31 pt switch |
| sign-up wall | `.wb-scr.wb-signup` > [`span.wb-su-skip`] + `img.wb-appicon.wb-su-icon` + `.wb-su-h` + `.wb-su-sub` + `.wb-su-btns` > three `.wb-btn` + `.wb-su-foot` + `.wb-su-legal` | leave out Skip for the wall with no way past; `.wb-su-or` is an "or" divider |
| paywall | `.wb-scr.wb-paywall` > `.wb-pw-hero` (img, or `img.wb-appicon` on a gradient) + `span.wb-pw-x[.wb-right][.wb-faint]` > `<i data-i="x">` + `.wb-pw-h` + `.wb-pw-feats` > spans + `.wb-pw-plans` > `.wb-plan[.wb-on]` (`em` tag, `i`, `div` > b + span, `strong` price) + `.wb-pw-trial` (`.wb-swapt` + `.wb-switch`) + `.wb-btn.wb-pw-cta` + `.wb-pw-note` + `.wb-pw-foot` | |
| tap indicator | made by `AR.wbTap` | the iOS touch dot: 44 pt grey with a white ring |
| GitHub Code button, clone menu | `.wb-gh-bar` > `.wb-gh-bbtn` + `.wb-gh-find` + `.wb-gh-code`; `.wb-gh-clone` > `.wb-gh-ctabs` + `.wb-gh-cbody` (`.wb-gh-ch`, `.wb-gh-proto`, `.wb-gh-url` > span + `.wb-gh-copy` > copy + `check.wb-ok`, `.wb-gh-hint`) + `.wb-gh-crow` | setup-flow positions the menu under the button |
| tip, URL chip | `.wb-tip`; `span.wb-urlchip` > `<i data-i="link">` + text (`.wb-fly` for the flying copy) | the chip is sized by its font-size |
| overworld map | built by `AR.questMap`: `.wb-qm` > island svg + route svg + `.wb-qm-node[.wb-qm-bad]` (`--qm`) > ring, disc, `.wb-qm-icon`, `b.wb-qm-num`, `.wb-qm-tag`, `.wb-qm-mark` (X) + `.wb-qm-mark.wb-qm-ok`; `b.wb-qm-big.px2` numeral; `.wb-qm-title` banner | icons: flag chest chest-open wall lock star bulb, an image path, or an emoji |
| design tool | `.wb-figma` (`--fg-scale`) > `.wb-fg-top` (`.wb-fg-logo`, `.wb-fg-tool[.wb-on]`, `.wb-fg-file`, `.wb-fg-share`) + `.wb-fg-canvas` > `.wb-fg-label` + `.wb-fg-frame` (the page at 1280 px); optional `.wb-fg-panels` with `.wb-fg-left` (`.wb-fg-layer[.wb-on]`) and `.wb-fg-right` (`.wb-fg-prop`) | a Figma-like editor; the helpers below draw inside the frame in page px |

## Helpers

| Helper | Does |
|---|---|
| `AR.webInit(root)` / `AR.ph("kind:text")` | fill icons, placeholders, cursors and tile overlays / one placeholder as a data URI |
| `AR.cursorTo(tl, cursor, target, t, dur, {ax, ay, dx, dy, ease})` | glides the cursor's hotspot onto an element or `[x, y]`, measuring the final layout plus any `AR.pageTo` scroll at arrival. Call moves in time order. Ignores other transforms: keep the cursor in the same camera wrapper as its content |
| `AR.cursorShape(tl, cursor, "hand"/"arrow", t)` | swaps the pointer |
| `AR.hoverLink(tl, link, t, {cursor, until, thick})` | the underline appears at once and the cursor turns into a hand; both reset at `until`. `AR.click` presses |
| `AR.clickRing(tl, ring, cursor, t)` | optional blue ripple at the hotspot |
| `AR.navigate(tl, fromPage, toPage, t, {load})` | the favicon spins for `load` s, then the next page cuts in and every `data-page` title and URL swaps; `load: 0` is a plain cut between two layers |
| `AR.pageTo(tl, scroller, t, {y, x, to, pad, focus, zoom, dur, steps, ease})` | scrolls or zooms a page in its viewport: `to` brings an element to the top, `focus` centres it, `dur: 0` frames it at the cut, `steps: n` makes eased stepped scrolls |
| `AR.rowInsert(tl, list, row, t, {dur, flash})` | the row (already in place in the HTML) appears, the rows below are pushed down, it flashes |
| `AR.notify(tl, stack, card, t, {mode, buzz, peek})` | a notification slides down; list mode puts the newest first and pushes the rest down; `.wb-stack` or `mode: "stack"` keeps the oldest first with older cards peeking behind; `buzz` wiggles the phone |
| `AR.rowGroup(tl, box, first, last, t, {pad, inset})` | a red box with a tag around a group of rows |
| `AR.selectGrid(tl, tiles, t, {dur, counter, from, to, countDur})` | tiles get a blue tint and a check in order; the counter counts with commas, then shows its check |
| `AR.heart(tl, heartPop, t, {like, hold})` | double-tap heart pops, settles, floats up and fades; `like` turns the icon red |
| `AR.feedSwipe(tl, feed, t, {n, gap, dur})` / `AR.carousel(tl, track, t, {to, inset, dur})` | vertical reel swipes / horizontal card swipe |
| `AR.insights(tl, card, t, dur, {from, to, rider})` | the line draws, the number counts, a dot (or a sprite) rides the tip |
| `AR.snackbar(tl, snack, t, {count: {from, to, dur}, out})` | the snackbar slides up and its number counts |
| `AR.calBook(tl, slot, event, t, tBook)` | a dashed slot appears, then the event books into it |
| `AR.sheetFill(tl, sheet, t, {rows: [a, b], gap, col})` | rows fill about one per 2 frames while the selection, name box, formula bar and row header step down |
| `AR.wbSkin(tl, page, t, skin, {wipe, dur, bar, rider, fade})` | switches a `.wb-land` to another skin at t: a copy in the new skin lands on top, as a hard cut or a wipe (`"down"`/`"right"`/`"up"`/`"left"`, 0.45 s) with `bar` and `rider` on its edge, as in `AR.wipeRide`. Returns the copy; its ids end in `-<skin>` |
| `AR.wbGuides(tl, page, t, {x, y, both, dur, gap, width, color, label, until})` | pink guides draw across the page; vertical centre by default |
| `AR.wbGrid(tl, page, t, {cols, margin, gutter, dur, label, color, until})` | a 12-column grid unrolls column by column; `label: true` puts "12 columns" above the frame; `grid._grid.x(i)` / `.span(a, b)` give column edges |
| `AR.wbSelect(tl, targets, t, {label, size, pad, color, handles, each, gap, until, page})` | a blue selection box with corner handles and a name tag ("W × H" with `size`); `each: true` outlines every element on its own (pink with `color`), `gap` apart |
| `AR.wbResize(tl, target, t, dur, {to, w, sel, rider, corner, push, shrink, ease})` | drags a corner: the target scales from the opposite corner and the selection and its size label grow with it; `rider` (a critter or cursor) rides the handle; `push` elements step down out of the way |
| `AR.wbSnap(tl, targets, t, {to, gap, dur, guide, rider, with, align})` | elements slide to the left margin (64) and land on t with an overshoot, their text turning left-aligned; a snap guide flashes; `rider` shoves them, travelling with `with` (default the widest) |
| `AR.wbPoint(page, x, y, layer)` / `AR.wbPoint(page, el, [ax, ay], layer)` | a page point, or a point of an element after any snap or resize, in another layer's px (puts a critter on a handle). Snaps and resizes record their moves, so a later `wbSelect` or `wbPoint` measures the moved element |
| `AR.wbTap(tl, target, t, {ax, ay, dx, dy, at, hold, press, screen})` | a finger taps: the touch dot presses in at t (it shows 0.07 s before), lifts after `hold` (0.16) while a ring ripples out; the target presses (`press: false` to skip) |
| `AR.wbAlert(tl, sys, t, {from, dur, dim, tap, at})` / `AR.wbAlertTap(tl, sys, which, t, {hold, out, finger})` | the alert pops (1.18 → 1 in 0.2 s, readable from t + 0.12) over its dim / taps "allow", "deny", "once" or an index: the button greys, the alert fades, the dim lifts |
| `AR.wbLaunch(tl, icon, layer, t, {dur, delay, ease, home, homeScale, tap})` | taps the icon; from t + 0.06 the `.wb-launch` layer grows out of the icon's rounded square to full screen in `dur` (0.42) while the home screen zooms in behind |
| `AR.wbSheet(tl, sheet, t, {dur, dim, ease, out})` | slides up from t (0.3 s) over the dim; `out` slides it back down |
| `AR.wbToggle(tl, switch, t, {on, color, dur, swap})` / `AR.wbSwapText(tl, el, t, {to})` | the switch flips (knob slides, track turns green); `swap` lists `.wb-swapt` labels that change with it / a `.wb-swapt` cuts to its next line |
| `AR.wbPlan(tl, plan, t)` | selects a `.wb-plan`: ring and tint move to it, it bumps |
| `AR.wbPrice(tl, el, t, {mode, from, dur, ease, show, scale, bump})` | the price lands on its word. `count` (default): appears at t − dur and rolls up from `from` to land at t, keeping its format ($29.99/year). `pop`: hidden until t. `bump`: only bumps |
| `AR.wbBand(targets, {pad, screen})` | an invisible strip as wide as the phone and as tall as the targets; `AR.frame(tl, cam, AR.wbBand(el), t, dur, {fit: "contain", pad: 0})` fills a 2:1 card with that strip |
| `AR.wbMenu(tl, menu, t, {button, pressed, dur, out})` | a dropdown opens; `button` presses and keeps the `pressed` colour |
| `AR.wbCopied(tl, button, t, {text, hold, tip, parent})` | the copy icon turns into a green check and "Copied!" pops over it, fading after `hold` (1.0) s |
| `AR.wbChip(tl, chip, from, to, t, dur, {lift, rise, arc, fit, handover})` | the chip lifts off `from`, rising its own height, arcs onto `to` at t + dur, and hands over to the hidden chip there (shown with a squash) |
| `AR.wbAppIcon(name)` | an app icon as a data URI |
| `AR.questMap(parent, {id, w, h, nodes, start, goal, pts, size, top, bottom, bad, plate, seed})` | draws a pixel island (or `plate`), the dashed route START → nodes → goal laid out as a zig-zag (left to right when wide, bottom to top when tall, between `top` and `bottom`), and the nodes. Returns `{el, nodes, pts, size}` (nodes[0] is START) |
| `AR.questSet(map, {crossed, fixed, hidden})` / `AR.questStand(map, who, i)` / `AR.questSpot(map, i)` | the marks already on at the cut / stands a sprite or critter on node i / where its feet go |
| `AR.questHop(tl, map, who, i, t, {dur, h})` / `AR.questLight(tl, map, i, t)` / `AR.questMark(tl, map, i, "x" or "ok", t)` / `AR.questDrop(tl, map, i, t, {from})` / `AR.questWin(tl, map, t)` | hop onto node i, landing at t / gold ring and bump / an X or check lands (a check replaces the X) / the node is thrown onto the route / the chest bursts open |

## Blueprints (wide, 1280x630; all cut in finished and fill the frame)

| Blueprint | Moment |
|---|---|
| `browser-page` | a real page in Chrome: the cursor glides to a link, it underlines and turns to a hand, click, navigation cut, push onto a field |
| `github-repo` | the repo page complete on the cut; a green FREE pill stamps into the bottom-right corner with a page bump |
| `phone-notify` | an iPhone lock screen; three notifications slide in on their words and stack |
| `insta` | select-all on a profile grid while POSTS races to 738/738, then a cut to the clone's profile |
| `data-table` | rows insert live, a row is clicked, the detail page opens and scrolls to the field, a red box lands on it |
| `quest-map` | an overworld route from START to the goal through N numbered traps (also a tall-card version). Per beat: intro (traps thrown on, X marks cascade), hop ("number N": the player hops on, a giant N lands, push in), fix (every X flips to a check), goal (the chest opens) |
| `setup-flow` | the install beat (also a tall-card version): the repo page readable from the cut, Code → copy → "Copied!", the link flies as a chip into Claude's input, "install skill" types, send, "Skill installed" |

Small text: a whole phone at 282 px wide or the reel cards' action counts read as texture; push in (or use the
zoomed layouts) when the viewer must read them.
