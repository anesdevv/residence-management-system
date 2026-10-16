# RÉSIVO Rebrand + Web Redesign + Desktop Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the product to RÉSIVO on every surface, redesign the student web portal to the provided Stitch designs, and finish the desktop console (photo viewer, flexible window, sign-out, About).

**Architecture:** Three phases on one branch (`resivo-update`): (A) rebrand — worker → local server → desktop → docs; (B) web redesign — design tokens + a sidebar shell in the shared layout, then page-by-page restyles that keep every real flow; (C) desktop polish. A final sweep + verification task closes the branch. The ChatGPT connector keeps working on the old URL until the admin updates it after the new worker is live.

**Tech Stack:** Astro 7 + Tailwind v4 (CSS-first `@theme` tokens), PySide6 (Qt 6), Cloudflare Workers (TypeScript + vitest), Supabase (Postgres/Storage), Python (pytest).

**Spec:** `docs/superpowers/specs/2026-10-16-resivo-rebrand-and-polish-design.md` — read it; it is the authority for every decision below.

## Global Constraints

- Product name is exactly `RÉSIVO` (uppercase, with É). All files stay UTF-8; no mojibake anywhere.
- `Residence Tlemcen` must not appear in user-visible strings. Allow-list for the final sweep: historical dated docs under `docs/superpowers/` (older than this plan), applied `supabase/migrations/*` comments, the common noun "residence" ("university residence"), and the keep-list below.
- Keep-list (institutional context, unchanged): `DOU Tlemcen`, `Cité Universitaire`, `univ-tlemcen.dz`, `@students.residence.local`, seeded staff/student accounts, `Direction des Œuvres Universitaires`.
- New worker: name `resivo-mcp`, URL `https://resivo-mcp.anes4tlm.workers.dev/mcp`. The old worker `residence-mcp` stays deployed until the admin confirms ChatGPT works on the new URL.
- Never print or commit secrets (`mcp/.env`, `desktop/.env`); never use the service-role key.
- Tests are never weakened, skipped, or deleted to get green — fix the failure or the code.
- No DB changes; no changes to `web/src/pages/api/*`, `web/src/lib/*`, `web/src/middleware.ts` beyond what restyling requires — web is UI-layer only.
- Mock-only features stay out: billing & dining, laundry status, community events, roommate matching, inspections, fake statistics.
- The web runs locally only (`npm run dev`, default port 4321); only the worker deploys.
- Branch `resivo-update`; one commit per task; nothing pushed without the admin's word.
- Baselines before the work: worker `npm test` 212 pass + `npm run typecheck` clean; `mcp` pytest 97 pass; desktop pytest pass; web `npm run build` + `npm test` pass; acceptance `SUMMARY: 30 passed, 0 failed, 1 skipped`.

## Review Focus

- `É`/UTF-8 mojibake on any surface — tests pin exact strings (worker name, desktop titles, web titles).
- Web flows broken by the restyle: login, register, maintenance submit with photo, room change, profile save.
- Maintenance photo fetch blocking the UI or crashing on failure/slow network.
- Old name surviving somewhere user-visible (per-task greps + final sweep).
- Window resize breakage: overlap at minimum size, dead space maximized.

---

### Task 1: Worker rename → `resivo-mcp` + secrets + deploy + acceptance

**Files:**
- Modify: `mcp-worker/wrangler.jsonc` (name, PUBLIC_URL, stale comment), `mcp-worker/src/mcp.ts` (SERVER_NAME, SERVER_INSTRUCTIONS), `mcp-worker/src/oauth.ts` (page titles, stale "Read-only" subtitles), `mcp-worker/src/index.ts` (resource_name, stale comment ~line 39), `mcp-worker/package.json` (description), `mcp-worker/README.md` (endpoint), `mcp-worker/scripts/verify_remote.py` (docstrings + usage examples), `mcp-worker/test/mcp.test.ts` (name pins)
- Test: `mcp-worker/test/mcp.test.ts`

**Interfaces:**
- Produces: live endpoint `https://resivo-mcp.anes4tlm.workers.dev/mcp`; `SERVER_NAME = "RÉSIVO Admin"` — consumed by Task 3 (settings constant), Task 5 (docs), Task 16 (verification).

- [x] **Step 1: Update the pinned strings.**
  - `wrangler.jsonc`: `"name": "resivo-mcp"`; `PUBLIC_URL` → `"https://resivo-mcp.anes4tlm.workers.dev"`; comment → `// RÉSIVO admin MCP server (read + admin-confirmed write tools).` Keep `OAUTH_KV` (same namespace id) and all other settings unchanged.
  - `mcp.ts`: `SERVER_NAME = "RÉSIVO Admin"`; `SERVER_INSTRUCTIONS` → `"Administrator tools for RÉSIVO, the university residence management system. You can read data freely; when the administrator has enabled changes you can also approve or reject registrations and room-change requests, manage rooms, and update maintenance tickets. Before any change, show the user exactly what will change and get their explicit confirmation. All data comes from the live Supabase project; every call is logged."`
  - `oauth.ts`: titles → `RÉSIVO MCP` / `Sign in — RÉSIVO MCP`; `<h1>` → `RÉSIVO Admin`; every "Read-only MCP server" subtitle → `Administrator MCP server for the university residence`.
  - `index.ts`: `resource_name: "RÉSIVO Admin"`; fix the stale read-only comment.
  - `package.json`: description → `RÉSIVO admin MCP server (6 read + 8 admin-confirmed write tools) on Cloudflare Workers`.
  - `verify_remote.py` + `README.md`: replace old name/URL in docstrings, examples, endpoint lines.
- [x] **Step 2: Update test pins; run the suite.** `cd mcp-worker; npm test; npm run typecheck` → Expected: 212 pass, tsc clean.
- [x] **Step 3: Deploy.** `cd mcp-worker; npx wrangler deploy` → Expected: success, worker `resivo-mcp`.
- [x] **Step 4: Replicate the worker secrets onto the new worker.** Follow `docs/mcp-handoff.md` ("Worker secrets"): temp JSON built from `mcp/.env` with keys `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `MCP_AUTH_TOKEN`; `npx wrangler secret bulk <tempfile>`; delete the temp file; **never print values**.
- [x] **Step 5: Acceptance against the new URL** (repo root): `& "mcp\.venv\Scripts\python.exe" "mcp-worker\scripts\verify_remote.py" https://resivo-mcp.anes4tlm.workers.dev` → Expected: `SUMMARY: 30 passed, 0 failed, 1 skipped` (this run also exercises the OAuth pages end-to-end).
- [x] **Step 6: Stale-wording check.** `git grep -n "Read-only\|Residence Tlemcen\|residence-mcp" -- mcp-worker/` → matches only where intended (none in source; `verify_remote.py` examples updated).
- [x] **Step 7: Commit** — `feat(worker): rename to RÉSIVO (resivo-mcp), set secrets, redeploy`

### Task 2: Local read-only MCP rename

**Files:**
- Modify: `mcp/server.py` (module docstring, SERVER_NAME, instructions), `mcp/formatting.py` (docstring), `mcp/requirements.txt` (comment), `mcp/.env.example` (comment)
- Test: `mcp/tests/` (existing)

**Interfaces:** none new (name/instructions only).

- [x] **Step 1:** `server.py`: SERVER_NAME → `"RÉSIVO Admin"`; instructions → `"Read-only administrator tools for RÉSIVO, the university residence management system. ..."` (keep the remaining original sentences); docstring → `"""RÉSIVO admin MCP server (read-only)."""`
- [x] **Step 2:** update the remaining comments (`formatting.py`, `requirements.txt`, `.env.example`).
- [x] **Step 3: Parity check.** `git diff mcp/server.py` must not touch any tool-description block (the 6 read tool descriptions stay byte-identical to the worker); `git grep -n "Residence Tlemcen" -- mcp/` → no matches.
- [x] **Step 4: Run mcp tests** — `& "mcp\.venv\Scripts\python.exe" -m pytest mcp\tests` → 97 pass.
- [x] **Step 5: Commit** — `feat(mcp): rename local read-only server to RÉSIVO`

### Task 3: Desktop rename + logo + hosted URL

**Files:**
- Create: `desktop/app/ui/assets/resivo_logo.png` (copy of `docs/resivo_logo_transparent.png`)
- Modify: `desktop/app/ui/main_window.py` (title, brand block, logo), `desktop/app/ui/login_window.py` (title, brand, logo), `desktop/app/ui/pages/residents.py` (subtitle), `desktop/app/ui/theme.py` + `desktop/app/ui/infocard.py` (comments), `desktop/app/ui/pages/settings.py` (MCP_HOSTED_URL + any old-URL text)
- Test: smoke script (extend), desktop pytest

**Interfaces:**
- Consumes: the new URL from Task 1.
- Produces: `desktop/app/ui/assets/resivo_logo.png` — used by Task 4.

Pinned strings:
- `main_window.py`: window title `"RÉSIVO Staff Console [LIVE MODE]"`; header title label `"RÉSIVO"`; subtitle `"Cité Universitaire • Dormitory Operations & Facility Management Console"`.
- `login_window.py`: window title `"Staff Login — RÉSIVO"`; brand label `"RÉSIVO"`; footer `"Direction des Œuvres Universitaires • Tlemcen"` unchanged.
- `residents.py`: `"Official record of all active students currently accommodated in the Cité Universitaire."`
- `settings.py`: `MCP_HOSTED_URL = "https://resivo-mcp.anes4tlm.workers.dev/mcp"` + every other old-URL occurrence in the file.

- [x] **Step 1:** copy the logo; load it via `Path(__file__).parent / "assets" / "resivo_logo.png"`; place it in the main header brand area (≈28–36px tall, replacing the crest icon) and in the login card (≈80–96px, replacing the crest icon).
- [x] **Step 2:** apply the pinned strings + comments; `git grep -n "Residence Tlemcen" -- desktop/` → no matches.
- [x] **Step 3:** update/extend the smoke script (`C:\Users\Admin\AppData\Local\Temp\opencode\settings_smoke.py`): window title contains `RÉSIVO`; header label `RÉSIVO`; login window title; logo pixmap loads (not null); settings URL == new URL. Run it → all pass; screenshot to `C:\Users\Admin\AppData\Local\Temp\opencode\shots\`.
- [x] **Step 4:** `& "desktop\.venv\Scripts\python.exe" -m pytest desktop\tests` → pass.
- [x] **Step 5: Commit** — `feat(desktop): RÉSIVO branding, logo, and new hosted URL`

### Task 4: About section in Settings

**Files:**
- Modify: `desktop/app/ui/pages/settings.py` (new About section at the bottom of `_build_content`)

**Interfaces:**
- Consumes: `desktop/app/ui/assets/resivo_logo.png` (Task 3).

- [x] **Step 1:** add the About card: logo (≈96px), heading `About RÉSIVO`, line `Created by SEBAI ANES`, clickable `GitHub: github.com/anesdevv` → `QDesktopServices.openUrl("https://github.com/anesdevv")`, clickable `Email: anes4tlm@gmail.com` → `QDesktopServices.openUrl("mailto:anes4tlm@gmail.com")`; styling matches existing section cards.
- [x] **Step 2:** extend the smoke: About labels present; link targets are the exact URLs above (assert strings; don't open anything).
- [x] **Step 3:** run smoke + pytest → pass; screenshot.
- [x] **Step 4: Commit** — `feat(desktop): About section with creator credit and links`

### Task 5: Living docs rename

**Files:** `README.md`, `PRODUCT.md`, `DESIGN.md`, `docs/mcp-handoff.md`, `docs/manual-test-desktop.md`, `docs/manual-test-mcp.md`, `docs/manual-test-web.md`

- [x] **Step 1:** apply the rename rules: `README.md` title → `# RÉSIVO — University Residence Management System (Tlemcen)`; endpoint lines → new URL; `PRODUCT.md`: institution = `Cité Universitaire` / DOU Tlemcen, product = RÉSIVO; `DESIGN.md`: name line + references; `mcp-handoff.md`: name/URL + fix the stale read-only line; manual-test files: new URL/name; `manual-test-mcp.md` gains the ChatGPT reconnection step (edit connector URL → Refresh → sign in).
- [x] **Step 2:** `git grep -in "residence tlemcen" -- README.md PRODUCT.md DESIGN.md docs/mcp-handoff.md docs/manual-test-*.md` → no matches.
- [x] **Step 3: Commit** — `docs: rename to RÉSIVO across living docs`

### Task 6: Web design foundation + dashboard shell

**Files:**
- Modify: `web/src/styles/global.css` (tokens), `web/src/layouts/Layout.astro` (three chromes), `web/public/` (logo + favicon)
- Create: `web/src/components/DashboardShell.astro`
- Test: `web` build + browser check

**Interfaces:**
- Produces (consumed by Tasks 7–12): Tailwind v4 `@theme` tokens — `canvas #f8f9ff`, `surface #ffffff`, `navy #000b2b`, `navy-2 #0f214a`, `amber #fe932c`, `amber-ink #904d00`, `ink #0b1c30`, `muted #45464f`, `line #c5c6d0`; `DashboardShell.astro` (props: `title: string`, `activeNav: 'dashboard'|'maintenance'|'room-change'|'profile'`; default slot); `/resivo-logo.svg`; new favicon.

- [x] **Step 1:** add the token set to `global.css` (keep the already-loaded fonts; body background → `canvas`).
- [x] **Step 2:** assets: copy `docs/resivo_logo.svg` → `web/public/resivo-logo.svg`; `favicon.svg` → the RÉSIVO mark; regenerate `favicon.ico` from the PNG (use Pillow in `mcp\.venv`, install if missing).
- [x] **Step 3:** `Layout.astro` renders by `activeNav`: public (`home`) → restyled institutional banner + header (logo + RÉSIVO + nav) + footer; auth (`login`, `register`) → minimal chrome; dashboard (`dashboard`, `maintenance`, `room-change`, `profile`) → `DashboardShell`: sidebar (logo top, nav items with navy active pill, Sign out → `/logout` at the bottom) + slim top bar with the student's identity + content slot. Page usage (`<Layout title activeNav>`) stays unchanged. Keep the DOU institutional line visible in the shell/footer.
- [x] **Step 4:** browser check (dev server + login as the seeded student from `docs/manual-test-web.md`): shell renders on a dashboard page, nav works, logo shows, mobile width collapses per `docs/stitch-designs/screenshots/mobile_*.png`; no console errors. `cd web; npm run build` → passes.
- [x] **Step 5: Commit** — `feat(web): RÉSIVO design foundation and dashboard shell`

### Task 7: Login + Register redesign

**Files:** `web/src/pages/login.astro`, `web/src/pages/register.astro`

**Interfaces:** consumes Task 6 tokens/logo/shell.

- [x] **Step 1:** restyle both as the split screen: left = white card with the existing form; right = navy hero panel — RÉSIVO logo, tagline, 3–4 real feature bullets (room assignment & transfers, maintenance triage with photos, secure resident portal, Cité Universitaire • Tlemcen). No fake statistics. Titles: `Resident Sign In — RÉSIVO` / `Resident Registration — RÉSIVO`.
- [x] **Step 2:** keep every field, validation rule, error state, and form action untouched (login → `/api/login`, register → `/api/register`).
- [x] **Step 3:** browser check at desktop + mobile widths: login end-to-end with the seeded student; register shows validation states; no console errors.
- [x] **Step 4: Commit** — `feat(web): redesign login and register pages`

### Task 8: Landing page redesign

**Files:** `web/src/pages/index.astro`

- [x] **Step 1:** title → `RÉSIVO — Official Student Housing Portal`; restyle the existing sections (hero, features, how-it-works, CTA) in the tokens; logo in header/hero; keep institutional lines; keep all links.
- [x] **Step 2:** browser check desktop + mobile; no console errors.
- [x] **Step 3: Commit** — `feat(web): redesign landing page`

### Task 9: Dashboard redesign

**Files:** `web/src/pages/dashboard/index.astro`

- [x] **Step 1:** title → `Dashboard — RÉSIVO`; restyle per the Stitch dashboard: welcome header, status chips, room overview, maintenance overview, quick actions — real data only; drop mock-only cards; keep every link and flow.
- [x] **Step 2:** browser check: real data renders; no console errors.
- [x] **Step 3: Commit** — `feat(web): redesign student dashboard`

### Task 10: Maintenance redesign

**Files:** `web/src/pages/dashboard/maintenance.astro`

- [ ] **Step 1:** title → `Maintenance Requests — RÉSIVO`; request cards with photo thumbnails (existing signed URLs), status badges; restyle the upload form; keep submit + validation + empty/error states.
- [ ] **Step 2:** browser check incl. one submit with a photo (a test row is acceptable); no console errors.
- [ ] **Step 3: Commit** — `feat(web): redesign maintenance page`

### Task 11: Room-change redesign

**Files:** `web/src/pages/dashboard/room-change.astro`

- [ ] **Step 1:** title → `Room Transfer Portal — RÉSIVO`; restyle current-room card + request form (real fields only) + status display; keep the submit flow.
- [ ] **Step 2:** browser check; no console errors.
- [ ] **Step 3: Commit** — `feat(web): redesign room change page`

### Task 12: Profile redesign

**Files:** `web/src/pages/dashboard/profile.astro`

- [ ] **Step 1:** title → `Resident Profile — RÉSIVO`; restyle identity card + form (real fields only); keep the save flow + validation.
- [ ] **Step 2:** browser check incl. a save; no console errors.
- [ ] **Step 3: Commit** — `feat(web): redesign profile page`

### Task 13: Maintenance photo viewer (desktop)

**Files:**
- Modify: `desktop/app/ui/pages/maintenance.py`
- Create: `desktop/app/ui/photo_viewer.py`

**Interfaces:**
- Produces: `PhotoViewerDialog(parent, initial_pixmap: QPixmap | None, image_url: str | None)` — shows the thumbnail instantly; if `image_url`, fetches bytes on a background `QThread` and swaps in the full-size image; zoom controls (fit / − / +, 25%–400%) + Close. Also `PhotoFetchWorker(QThread)` with `loaded = Signal(bytes)` / `failed = Signal(str)` for the inspector.

- [ ] **Step 1:** make the inspector thumbnail load async (no main-thread `urlopen`); explicit loading / no-photo / failed states; selection changes ignore stale results.
- [ ] **Step 2:** clicking the thumbnail opens `PhotoViewerDialog`; wire zoom + close; never block the main thread.
- [ ] **Step 3:** extend the smoke: click opens the viewer; zoom changes scale; no-photo ticket → message; failed fetch → message with no hang; screenshots.
- [ ] **Step 4:** pytest + smoke pass.
- [ ] **Step 5: Commit** — `feat(desktop): maintenance photo viewer with async loading`

### Task 14: Flexible window

**Files:** `desktop/app/ui/main_window.py`, `desktop/app/ui/pages/maintenance.py`, `desktop/app/ui/pages/pending.py`, `desktop/app/ui/pages/room_changes.py`, `desktop/app/ui/pages/staff_accounts.py`, `desktop/app/ui/login_window.py`

- [ ] **Step 1:** convert fixed widths to min/max + stretch: maintenance inspector 420 → min 360 / max 520; pending detail 380 → min 340 / max 460; room-changes detail 400 → min 340 / max 480; staff form 380 → min 340 / max 460. Keep splitter stretch factors.
- [ ] **Step 2:** `MainWindow.setMinimumSize(980, 640)`; `LoginWindow.setMinimumSize(380, 480)`.
- [ ] **Step 3:** smoke: resize to minimum, default, and maximized — assert the inspector stays visible and the table grows at max; screenshots at all three sizes for review.
- [ ] **Step 4:** pytest + smoke pass.
- [ ] **Step 5: Commit** — `feat(desktop): flexible window layout`

### Task 15: Sign-out button

**Files:** `desktop/app/ui/main_window.py`

- [ ] **Step 1:** extract `_shutdown_workers()` (stop sync + health workers with the existing bounded waits; used by `closeEvent` and sign-out).
- [ ] **Step 2:** add a `Sign out` button (objectName `signOutButton`) at the bottom of the sidebar; click → `_shutdown_workers()`, `client.auth.sign_out()` (guarded), open a fresh `LoginWindow`, close self.
- [ ] **Step 3:** smoke: button exists; click → login window visible, main window closed, `sync_worker.isRunning()` is False; screenshot.
- [ ] **Step 4:** pytest + smoke pass.
- [ ] **Step 5: Commit** — `feat(desktop): sign out button`

### Task 16: Rename sweep + final verification + handover

- [ ] **Step 1: Sweep.** `git grep -in "residence tlemcen"` and `git grep -in "residence-mcp"` → matches only in allow-listed files (historical dated docs under `docs/superpowers/`, `supabase/migrations/*` comments). Anything else → fix.
- [ ] **Step 2: Full suites.** Worker `npm test` + `npm run typecheck`; mcp pytest; desktop pytest + smoke; web `npm run build` + `npm test`; acceptance vs the new URL once more → all baselines met.
- [ ] **Step 3: Browser pass** of all 7 pages at desktop + mobile widths (dev server): login, dashboard, maintenance submit + photo, room change, profile save, logout.
- [ ] **Step 4: Handover content confirmed** in `docs/manual-test-mcp.md`: edit the connector URL in ChatGPT → Refresh → sign in → one read + one write test.
- [ ] **Step 5: Commit** — `chore: RÉSIVO rename sweep and final verification`
- [ ] **Step 6 (after the admin confirms ChatGPT on the new URL):** delete the old worker (`npx wrangler delete --name residence-mcp` from `mcp-worker/`; verify with `npx wrangler deployments list`). Then, per the admin's call: merge `resivo-update` → `main` locally and push.
