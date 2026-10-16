# RÉSIVO — rebrand, web redesign, desktop polish (design)

Date: 2026-10-16
Status: Draft — awaiting the admin's approval (brainstorming output; builder-checked 2026-10-16 — both findings resolved inside)
Related: `docs/stitch-designs/` (design reference), `docs/superpowers/specs/2026-10-15-mcp-write-tools-design.md` (previous project), `docs/mcp-handoff.md`

## Why

The system gets a real identity — **RÉSIVO** — and a presentation-ready look. The moment: the admin shows the project (school presentation). The web portal is seen first and must feel like a finished product, so it is redesigned from the provided Stitch mockups. The desktop console follows: real photo previews on maintenance tickets, a window that behaves at any size, and an About section crediting the creator.

## Goals

- Rename the product to RÉSIVO everywhere it names itself: desktop console, web portal, the hosted ChatGPT connector (worker renamed `resivo-mcp`), the local read-only MCP server, and the living docs. The provided logo (SVG + transparent PNG) replaces text branding.
- Redesign the web portal to the Stitch look and layout (`docs/stitch-designs`), keeping every real feature and dropping mock-only ones.
- Desktop console: maintenance photo preview becomes a proper viewer; the window becomes flexible (resizes/maximizes cleanly); Settings gains an About section (creator SEBAI ANES, GitHub, email).
- Everything keeps working: all existing tests green, the ChatGPT connector functional on the new URL after the admin's one-time URL edit, acceptance script green.

## Non-goals

- No new product features. Mockup-only features are dropped: billing & dining, laundry room status, community events, roommate matching, inspections.
- No database changes. The rename is code/docs only; the `maintenance-photos` bucket, `photo_path` column, and all RPCs stay untouched.
- No changes to web backend logic or student-facing behavior: auth, registration, uploads, room-change flow, maintenance submit — UI layer only.
- No unrelated MCP fixes (except the stale "read-only" wording corrections listed under A); no staff-account/roster work; no fee features.
- Historical dated docs (`docs/superpowers/plans/*` and older specs) and applied migration comments keep their old text.
- About goes in the desktop Settings page only (not the web).

## Anti-goals (failure conditions)

- Old branding still visible on a live surface (desktop/web/worker/connector/living docs) — outside the keep-list below.
- The ChatGPT connector left broken: the admin must end up with exact steps (edit URL in ChatGPT, Refresh, sign in if asked) and a verified worker on the new URL.
- A web flow broken by the restyle (login, register, dashboard, maintenance submit incl. photo, room change, profile).
- A desktop regression (live sync, approvals, room CRUD, ticket updates, writes off-switch, MCP health check) or a photo viewer that blocks the UI.
- Tests weakened/skipped/deleted to get green; secrets printed or committed.

## Constraints and standing facts

- Windows dev machine. Web: Astro + Tailwind (`web/`). Desktop: PySide6 (`desktop/`). Worker: Cloudflare (`mcp-worker/`). Supabase project `kjqbnurycfjsuufibkac`, free tier. The web runs locally (no hosting exists); only the worker deploys. Never print/commit secrets (`mcp/.env`, `desktop/.env`); never use the service-role key.
- URLs: current `https://residence-mcp.anes4tlm.workers.dev/mcp` → new `https://resivo-mcp.anes4tlm.workers.dev/mcp` (worker name `resivo-mcp`).
- Logo assets provided (currently untracked, to be committed as part of this work): `docs/resivo_logo.svg`, `docs/resivo_logo_transparent.png` (transparent background; navy + teal + gold). Use the SVG on the web; the PNG in the desktop (PySide6 without QtSvg).
- Stitch reference: `docs/stitch-designs/screenshots/` (9 renders) + `docs/stitch-designs/code/` (9 Tailwind-CDN HTML exports — reference, not source). Tokens from the exports: background `#f8f9ff`, primary `#000b2b`, primary-container `#0f214a`, secondary-container `#fe932c`, secondary `#904d00`; fonts Plus Jakarta Sans (600–800, headings) + Inter (400–600, body); Material Symbols Outlined icons; radii ~8–12px. Amber accents get harmonized with the logo's gold.
- Web today: top-nav layout (`web/src/layouts/Layout.astro`); pages `index`, `login`, `register`, `dashboard/index`, `dashboard/maintenance`, `dashboard/room-change`, `dashboard/profile`; custom `Icon.astro` icon component; fonts already loaded; dark institutional top banner (DOU line) on desktop widths; favicon `/favicon.svg` + `/favicon.ico`.
- Desktop today: `main_window.py` opens 1180×760, sidebar fixed 230px; fixed-width panels: maintenance inspector 420px (photo label 380×180 fixed), pending detail 380px, room-changes detail 400px, staff-accounts form 380px; login window 440×520. Maintenance already loads photos (signed URL 300s → urllib → QPixmap, scaled 380×180) — the upgrade builds on this path.
- `settings.py` already hosts the MCP setup sections + the writes off-switch; `MCP_HOSTED_URL` (line 17) must point at the new URL.
- Worker tests pin the server name (`mcp-worker/test/mcp.test.ts`); update with the rename. Acceptance baseline: `verify_remote.py <url>` = 30 passed / 0 failed / 1 skipped.
- Fold into rename edits: stale "read-only" wording — comments (`mcp-worker/wrangler.jsonc:2`, `mcp-worker/src/index.ts:39`, `docs/mcp-handoff.md:16`) and the OAuth consent/error page subtitles (`mcp-worker/src/oauth.ts`, "Read-only MCP server") — all false since the write tools shipped, and the OAuth page is what the admin sees during re-auth.
- Work on a feature branch (`resivo-update`), commit per task; merging/pushing is the admin's call at the end.
- Execution: subagent-driven (fresh implementer + reviewer per task) — the admin asked for subagents.

## Decisions agreed with the admin (this session)

1. Rename to RÉSIVO on: desktop, web, ChatGPT connector (worker → `resivo-mcp`, new URL), local read-only MCP, living docs. Logo replaces text branding. Keep-list (institutional context): DOU Tlemcen / Cité Universitaire lines, `univ-tlemcen.dz` and `@students.residence.local` emails, seeded staff test accounts.
2. The admin edits the ChatGPT connector URL once after the redeploy (and signs in again if asked); no other setup changes.
3. Web redesign: Stitch look + layout; real features only; mock-only features removed; landing page (no mockup exists) restyled to match; separate login/register routes kept (styled like the mock's split screen).
4. Desktop: photo preview upgrade (click to open a full-size viewer), flexible window, About section in Settings (SEBAI ANES; github.com/anesdevv; anes4tlm@gmail.com).
5. Order: 1) rename + logo + About, 2) web redesign, 3) desktop photo preview + flexible window.

## The how

### A. Rename

Rule: "RÉSIVO" (always with the É) replaces the product name wherever it names itself; institutional context text stays.

"Residence Tlemcen" disappears from every user-visible string. Mixed institutional strings keep the institutional part and replace the product part — e.g. "Cité Universitaire — Residence Tlemcen" (desktop header `main_window.py:56`, web footer `Layout.astro:229`, `PRODUCT.md`) becomes RÉSIVO plus the Cité Universitaire / DOU context as separate elements. The institution is "Cité Universitaire" / "DOU Tlemcen"; the product is RÉSIVO. Sweep allow-list for the old name: historical dated docs under `docs/superpowers/`, applied migration comments, and the common noun "residence" (e.g. "university residence") — nothing else.

- Desktop: window titles (`main_window.py`, `login_window.py`), header brand block + subtitle, login screen brand, residents page subtitle, code comments; `settings.py` `MCP_HOSTED_URL` → new URL. Logo appears in the header/sidebar area, the login card, and the About section (PNG asset).
- Web: `Layout.astro` default title + brand block + footer; every page `<Layout title=…>`; login brand; favicon replaced with the RÉSIVO mark; logo placed per the new design (header/sidebar, login hero).
- Worker: `wrangler.jsonc` (`name` → `resivo-mcp`, `PUBLIC_URL` → new URL, stale comment fixed); `mcp.ts` (`SERVER_NAME` → `RÉSIVO Admin`; instructions keep their sentences with the name swapped); `oauth.ts` sign-in page titles; `index.ts` `resource_name`; `package.json` description; README; `verify_remote.py` docstrings/examples.
- Local MCP (`mcp/`): `server.py` name/instructions, module docstrings, `requirements.txt` + `.env.example` comments. Read tool descriptions/outputs stay identical to the worker (parity rule from the previous project); any shared string containing the name changes on both sides together.
- Living docs: `README.md`, `PRODUCT.md`, `DESIGN.md`, `docs/mcp-handoff.md`, `docs/manual-test-desktop.md`, `docs/manual-test-mcp.md`, `docs/manual-test-web.md`.
- Tests: update name pins (`mcp-worker/test/mcp.test.ts`); grep for other pins.
- Deploy sequence: deploy the renamed worker → acceptance green on the new URL → the admin edits the ChatGPT connector URL (user step) → after the admin confirms, delete the old `residence-mcp` worker as final cleanup.
- Sweep at the end: repo-wide grep for the old name; anything left must be on the allow-list (historical docs, migrations, keep-list strings).

### B. Web redesign

- Tokens/layout per Constraints. Sidebar shell for logged-in pages: logo top, Dashboard / Maintenance / Room Change / Profile with navy active pill, sign out at the bottom, slim top bar with the student's identity. Split-screen shell for login/register: form left, navy hero panel right. Landing page restyled in the same language (content stays, styling changes).
- The institutional DOU line stays visible but integrated into the new shell (e.g. sidebar footer / page footer) instead of the old dark banner.
- All seven pages restyled; every real feature preserved (forms, validation, uploads, signed-URL photos, statuses, empty/error states). Mock-only cards are removed entirely.
- Responsive: follow the mobile mockups (nav collapses; cards stack).
- UI-layer only: no changes to `web/src/pages/api/*`, supabase calls, or auth logic beyond what restyling requires.
- Verify in a real browser (chrome-devtools MCP): all pages at desktop + mobile widths; submit flows exercised.

### C. Desktop polish

- **C1. Maintenance photo preview**: keep the inline thumbnail in the Ticket Inspector; make it clickable → a full-size viewer dialog (image scaled to fit, zoom controls, close), reusing the existing dialog styling (`infocard.py` patterns). Handle loading / no-photo / failure states explicitly. Extend the smoke test to cover it.
- **C2. Flexible window**: sensible minimum main-window size; fixed-width panels become stretch/min-max so they scale; splitters proportional; tables fill space; login window resizes gracefully. Check at small / default / maximized sizes (smoke screenshots).
- **C3. About in Settings**: new section at the bottom of the Settings page — RÉSIVO logo, "Created by SEBAI ANES", GitHub link (clickable, opens the browser) to `https://github.com/anesdevv`, email `anes4tlm@gmail.com` (mailto link).

### D. Verification

- Web: build + browser pass per B; no console errors.
- Desktop: pytest + extended smoke (photo viewer, resize checks, About presence, rename spot checks) with screenshots.
- Worker: vitest + typecheck; deploy; `verify_remote.py` green on the new URL; OAuth page shows the new name.
- Rename sweep per A.
- Final admin check: ChatGPT URL edit + Refresh, one read + one write (manual checklist updated).

## Left to the builder

- Exact taglines/subtitle wording; which spots get the logo vs text; favicon generation approach; asset locations (web public dir, desktop assets).
- Icon strategy on web (reuse `Icon.astro` where equivalent vs Material Symbols).
- Exact minimum window size; which fixed widths become min/max.
- Photo viewer control details (must be zoomable; exact controls builder's choice).
- Landing-page restyle specifics.
- Smoke-test additions and screenshot points.
