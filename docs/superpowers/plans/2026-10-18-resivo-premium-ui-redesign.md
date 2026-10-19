# RÉSIVO — Premium UI redesign (visual layer only)

Date: 2026-10-18 · Executor: agent, phase by phase (user explicitly asked to continue without stopping).

## Baseline (measured before any edit)

| Surface | Command | Result |
|---|---|---|
| Desktop | `.venv/Scripts/python.exe -m pytest desktop/tests -q` | **23 passed** (task said 19/19; working tree has 23) |
| Web | `npm test` (in `web/`) | **10 passed** (1 file) |

Note: root `tests/` (RLS/RPC integration) cannot run here — needs a live Supabase project + `supabase` package in the global interpreter. `pytest.ini` testpaths includes them, so always run `pytest desktop/tests`.

## Inventory (Step 0)

### Desktop — `desktop/app/ui/` (PySide6 6.12 in `.venv`, Python 3.11)

| File | Role | Styling today |
|---|---|---|
| `main_window.py` | Shell: top institutional header, 230px sidebar (`QListWidget#sidebarNav`), `QStackedWidget` pages, `QStatusBar`, `LiveSyncWorker` | mixed: global QSS + ~6 inline `setStyleSheet` |
| `login_window.py` | Login window (min 380x480), prefilled seeded staff creds, inline error label | inline styles |
| `live_sync.py` | 2s `QThread` poller → `sync_tick(dict)` / `alert_event(str)` | none |
| `photo_viewer.py` | `ClickablePhotoLabel`, `PhotoFetchWorker` (QThread, 15s timeout, stop()), `PhotoViewerDialog` (fit/zoom 25–400%, keyboard) | own `PHOTO_VIEWER_QSS` |
| `icons.py` | `SVG_CATALOG` + `get_pixmap/get_icon(name, size, color)` (QSvgRenderer recolor) | n/a |
| `infocard.py` | `StudentInfoCardDialog`, `RoomInfoCardDialog`, `section_header`, `kpi_block` (read-only info modals) | many inline hex |
| `pages/overview.py` | KPI `StatCard`s + counts via `_count()` | inline hex |
| `pages/pending.py` | 4 filter buttons (`btn_pending/approved/rejected/all`), `table` (QTableWidget), `detail_text` (QPlainTextEdit), approve/reject/delete, room-allocation modal | inline hex |
| `pages/residents.py` | residents table + search + count badge | inline hex |
| `pages/rooms.py` | rooms table, `RoomSetupDialog` (add/edit/delete) | inline hex |
| `pages/maintenance.py` | 4-stage lifecycle filters, `photo_label`, `PhotoViewerDialog`, status buttons, delete | inline hex |
| `pages/room_changes.py` | current→target room, approve/reject/delete | inline hex |
| `pages/official_list.py` | CSV/Excel import card + preview table | inline hex |
| `pages/staff_accounts.py` | admin-only table + create form (`full_name` QLineEdit) | inline hex |
| `pages/settings.py` | dev/MCP settings, `McpHealthWorker`, in `QScrollArea` | inline hex |

Navigation: `QListWidget#sidebarNav` rows ↔ `QStackedWidget` index; role gating = `current_role(client)`, admin-only items appended conditionally (`Staff accounts`). Live UI: `QStatusBar` message + nav item text badges (`Pending accounts (n)`) + `alert_event` toast text with 🔔. Confirm dialogs: `QMessageBox`.

### Web — `web/src/`

| File | Role | Styling today |
|---|---|---|
| `layouts/Layout.astro` | 3 chrome variants: public header+footer, auth header, dashboard (`DashboardShell`) | Tailwind utilities, Google-Fonts CDN (Inter + Plus Jakarta Sans) |
| `components/DashboardShell.astro` | top nav on desktop + bottom tab bar on mobile | Tailwind |
| `components/Icon.astro` | inline SVG icon component (names: dashboard, wrench, swap, building, clock, check-circle, x-circle, lock, user, logout, file-text, chevron-right, phone, mail) | inline SVG, stroke 1.8 |
| `styles/global.css` | `@theme` tokens (`canvas/surface/navy/amber/ink/muted/line`), base layer | Tailwind v4 |
| `pages/index.astro` | landing | Tailwind |
| `pages/login.astro` | login card | Tailwind |
| `pages/register.astro` | 4-section registration form | Tailwind |
| `pages/dashboard/index.astro` | status hero + services + activity | Tailwind |
| `pages/dashboard/maintenance.astro` | tickets + create form + photo upload | Tailwind |
| `pages/dashboard/room-change.astro` | transfer form (locked for non-active) | Tailwind |
| `pages/dashboard/profile.astro` | read-only vs editable fields | Tailwind |
| `pages/api/*` | server endpoints — **do not touch** | n/a |

## Constraints locked by tests (must keep working)

- `PendingPage`: `btn_pending/btn_approved/btn_rejected/btn_all`, `filter_mode`, `table` (col0 = card id, col3 contains "Pending"/"Approved"/"Rejected"), `delete_btn` + tooltip "Pending applications cannot be deleted", `approve_btn` (+ "already approved" tooltip), `reject_btn.text()` == "Edit Rejection Reason", `detail_text` containing "REJECTION REASON (Desk Inquiry Reference)", `apply_live_data` must not wipe filter/search.
- `MaintenancePage`: `rows`, `table`, `show_detail()`, `on_photo_clicked()`, `photo_label.text()` == "No photo attached by resident" when none, `_photo_fetch_failed`, `_current_pixmap`, `_current_photo_url`, `delete_btn`.
- `detail_text.parentWidget()` = panel frame → min/max: maintenance 360/520, pending 340/460, room changes 340/480.
- `StaffAccountsPage`: `full_name` inside a `QFrame` ancestor with min 340 / max 460 → the create form card must stay a `QFrame` with those sizes.
- `MainWindow`: min 980x640, `QPushButton#signOutButton` text "Sign out", `_shutdown_workers()` (3s bounded), `LiveSyncWorker.start` patchable, pages instantiated by name from `main_window` module namespace.
- `LoginWindow`: min 380x480.
- `PhotoViewerDialog`: `full_pixmap`, `is_fit_mode`, `zoom_in/zoom_out/set_fit_mode`, `btn_fit`, `zoom_label`, `status_label` ("200 × 150"), `scale_factor`, `MIN_SCALE`/`MAX_SCALE`, `worker`, `_on_full_loaded`.

## Assumptions (stated, not asked)

1. **Brand asset path**: the spec says `desktop/assets/brand/` + `web/public/brand/`; those folders don't exist. The real source `docs/resivo_logo_transparent.png` (= `desktop/app/ui/assets/resivo_logo.png`, 1254x1254 RGBA, verified alpha + brand palette) is copied to both expected folders by `tools/prepare_brand_assets.py`. Nothing invented, nothing stopped.
2. **Paths**: keep the existing module paths (`desktop/app/ui/...`) instead of the spec's `desktop/ui/...` — tests import the real paths.
3. **Fonts**: OFL static TTFs (Outfit 500/600/700, Inter 400/500/600) downloaded from `google/fonts` into `desktop/assets/fonts/` (+ licences) and self-hosted for web. No CDN.
4. Root `DESIGN.md` becomes a pointer to the rewritten `docs/DESIGN.md`.
5. Bug found in uncommitted work: `main_window.on_live_sync_tick` referenced undefined `payload` → `NameError` on every tick. Fixed to `data` (keeps the author's intent: live active-residents KPI).

## Phases

1. **Foundation** — brand assets, fonts, `desktop/app/ui/theme.py` (tokens + global QSS + font loader), web `tokens.css` + `global.css` + font-face, `docs/DESIGN.md`.
2. **Components** — `desktop/app/ui/icons.py` (full set) + `desktop/app/ui/components.py`; web components; `/styleguide` page.
3. **Desktop console** — shell, login, all pages, all modals.
4. **Web portal** — landing, register, login, dashboard, maintenance, room change, profile, resident pass.
5. **Quality pass** — a11y/contrast, consistency, screenshots, README + manual-test checklists, final test run.

Test gate after every phase: `pytest desktop/tests -q` + `npm test`.

## Ownership map (parallel work — one writer per file)

| Owner | Files |
|---|---|
| A (assets/fonts) | `tools/prepare_brand_assets.py`, `desktop/assets/**`, `web/public/brand/**`, `web/public/fonts/**`, `web/public/favicon.*`, `web/public/resivo-logo.svg` |
| B (desktop foundation) | `desktop/app/ui/theme.py`, `desktop/app/ui/icons.py`, `desktop/app/ui/components.py` |
| C (web foundation) | `web/src/styles/tokens.css`, `web/src/styles/fonts.css`, `web/src/styles/global.css`, `web/src/components/**`, `web/src/layouts/Layout.astro`, `web/src/pages/styleguide.astro` |
| D1 | `desktop/app/ui/main_window.py`, `desktop/app/ui/login_window.py` |
| D2 | `desktop/app/ui/pages/overview.py`, `pages/residents.py`, `pages/pending.py` |
| D3 | `desktop/app/ui/pages/rooms.py`, `pages/official_list.py`, `pages/staff_accounts.py`, `pages/settings.py` |
| D4 | `desktop/app/ui/pages/maintenance.py`, `pages/room_changes.py`, `desktop/app/ui/photo_viewer.py`, `desktop/app/ui/infocard.py` |
| W1 | `web/src/pages/index.astro`, `login.astro`, `register.astro` |
| W2 | `web/src/pages/dashboard/index.astro` |
| W3 | `web/src/pages/dashboard/maintenance.astro`, `room-change.astro`, `profile.astro` |
| main agent | `docs/**`, `README.md`, screenshots, verification, final report |

Test gate for every owner: `$env:QT_QPA_PLATFORM="offscreen"; & .venv/Scripts/python.exe -m pytest desktop/tests -q` (desktop) and `npm test` in `web/`.

## Phase 3 page requirements (from the user's spec)

- **Overview**: greeting, row of StatCards (pending applications, open tickets, pending transfers, occupancy %), occupancy by block with `RoomOccupancyBar`, "Needs attention" list, recent live events. Real data only — no invented metrics.
- **PendingPage**: SegmentedControl (Pending / Approved / Rejected / All) + SearchField in the toolbar; master-detail: table left (card ID, name, university, status pill, roster badge), DetailPanel right (identity block, RosterMatchBadge, submitted-data key-values, actions). Rejected applicant shows a prominent "REJECTION REASON (Desk Inquiry Reference)" record block in the rejected tint with the reason + reviewed date/time (this exact string must remain inside `detail_text`). Delete disabled + tooltip for pending. Room allocation modal: room list with RoomOccupancyBar, gender-block rule as a banner, full/mismatched rooms disabled with a reason.
- **Residents / Rooms** (add/edit/delete; occupancy column as a bar): same table language.
- **MaintenancePage**: Stepper with the 4 stages in the detail panel, category icon, photo thumbnail with a hover zoom cue, status actions, staff notes field. PhotoViewerDialog: dark scrim, centred image, floating toolbar (fit, zoom in/out, percentage, close), keyboard shortcuts in tooltips.
- **RoomChangesPage**: current room › target room visual, motive text, approve/reject actions.
- **OfficialListPage**: drag-and-drop style import card, preview table, result summary banner.
- **StaffAccountsPage**: table + create dialog; self-selected row shows the disabled delete with tooltip plus an InlineBanner explaining why.
- Empty states, loading skeletons, offline/error banners on every page. Window min 980x640; resizing must never crush controls (proper size policies).

## Phase 4 page requirements (from the user's spec)

- **Landing**: brand-gradient hero with the white logo, headline, short value text, Register + Log in buttons, "How it works" 4 steps (Register › Verification › Room assigned › Live in residence), trust footer `Direction des Œuvres Universitaires · Cité Universitaire · Tlemcen`.
- **Register**: multi-section form (Identity, Academic, Contact, Security) with inline validation messages, password strength meter, card-ID helper text.
- **Login**: centred card on canvas with logo.
- **Dashboard**: status hero card that changes by state (pending = amber, active = green, rejected = red with reason); **digital resident pass** for active students (block, floor, room, student name, card ID, barcode/QR block) — the one place the full brand gradient + gold shine; maintenance tickets with category icons, stage Stepper and photo upload dropzone with preview; room-change form with locked banner for non-active students; profile with read-only fields vs editable phone/email. Bottom tab bar on mobile, top nav on desktop. Touch targets ≥ 44px.
- Lighthouse targets: Accessibility ≥ 95, no layout shift, fast LCP (self-hosted fonts, optimised images, no layout-blocking scripts).

## Reference commands

- Desktop app (offscreen smoke): `$env:QT_QPA_PLATFORM="offscreen"; & .venv/Scripts/python.exe -c "..."` — the venv has PySide6, supabase, pytest.
- System python (`python`) has Pillow (brand assets) but no PySide6.
- Screenshots: `tools/capture_desktop_screenshots.py` → `docs/screenshots/desktop/`.

---

## Completion & Verification Status (2026-10-19)

All 5 phases of the RÉSIVO Premium UI Redesign are **100% complete, audited, and verified**:

| Phase | Description | Status | Verification |
|---|---|---|---|
| **Phase 1: Foundation** | Brand assets, fonts, `theme.py` (tokens/QSS/fonts), web `tokens.css` + `global.css`, `docs/DESIGN.md`, pointer in root `DESIGN.md` | **Completed** | Full WCAG AA tokens, zero external CDN dependencies, self-hosted Outfit & Inter fonts. |
| **Phase 2: Components** | Vector `icons.py` & `Icon.astro`, universal components (`StatusPill`, `Card`, `PageHeader`, `Stepper`, `EmptyState`, `InlineBanner`, `KeyValue`, `ResidentPass`) | **Completed** | Strict zero-emoji policy, authored Lucide SVGs, exact contract parity. |
| **Phase 3: Desktop Console** | Shell, split Login window, all pages (`overview`, `pending`, `residents`, `rooms`, `maintenance`, `room_changes`, `official_list`, `staff_accounts`, `settings`), and modals | **Completed** | All 23 Pytest tests pass in offscreen mode. All panel widths (340–520px) and window minimums (980×640) locked and preserved. |
| **Phase 4: Web Portal** | Landing (`/`), Login (`/login`), Register (`/register`), Dashboard (`/dashboard`), Maintenance (`/dashboard/maintenance`), Room Change (`/dashboard/room-change`), Profile (`/dashboard/profile`), Styleguide (`/styleguide`) | **Completed** | Full build passed (`npm run build` / Astro SSR), 10/10 Vitest validation tests passed, touch targets ≥ 40px/44px, semantic ARIA roles. |
| **Phase 5: Quality Pass** | Accessibility audit, test engineer verification, multi-axis code review, offscreen desktop screenshots, web screenshots, updated documentation | **Completed** | Audited by specialized subagents (Code Reviewer, Web Performance/A11y Auditor, QA Test Engineer). |

