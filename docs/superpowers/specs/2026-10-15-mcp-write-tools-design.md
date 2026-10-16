# MCP write tools — ChatGPT can manage the residence (design)

Date: 2026-10-15
Status: Draft — awaiting the admin's approval (brainstorming output; builder-checked 2026-10-15, the three findings are resolved inside)
Related: `docs/superpowers/plans/2026-10-15-cloudflare-worker-mcp.md` (read-only MCP — shipped and live), `docs/mcp-handoff.md`

## Why

The hosted connector (`https://residence-mcp.anes4tlm.workers.dev/mcp`) already lets ChatGPT **read** residence data. The admin now wants ChatGPT to **act**: approve/reject registrations, create/edit/delete rooms, "basically everything you can do in the app".

The moment this is for: the admin is away from the laptop and something needs doing — a registration arrives, a room must be added. Instead of opening the desktop console, they talk to ChatGPT on their phone: "any new registrations?" → "approve the two that look fine, reject the one missing documents" → "create room 305 with 3 places".

## Goals

- ChatGPT gains the desktop admin's write actions: approve/reject a registration, approve/reject a room-change request, create/edit/delete a room, move a maintenance ticket to `in_progress`/`resolved`.
- Safety: ChatGPT confirms every change with the admin before it happens; every write is logged (what, when, result); the app's business rules are enforced server-side so they cannot be skipped; a one-step off-switch makes ChatGPT read-only again.
- No new user setup: same connector, same token; after a redeploy the admin only taps **Refresh** on the connection in ChatGPT.

## Non-goals

- Creating staff accounts (passwords would travel through chat) — excluded.
- Bulk import of the official-residents Excel/CSV roster — skipped for now (clunky via chat; the RPC exists and stays desktop-only).
- Editing or deleting students; moving students outside the room-change flow; fees (no such feature exists).
- Write parity for the local Python server (`mcp/`) — it stays read-only, a dev/testing fallback.
- Any change to `web/` (untouched), to the OAuth flow, or to the public URL.

## Anti-goals (failure conditions)

- A change happens without the admin having approved it in that ChatGPT conversation.
- The DB accepts a write that violates app invariants: deleting an occupied room, dropping capacity below occupancy, flipping the gender of an occupied room.
- A write happens without an attempt row in the audit trail (pre-logging is fail-closed; only the outcome is best-effort).
- Secrets printed or committed; the service-role key used anywhere.
- Existing read tools (or the local server) break.

## Constraints and standing facts

- Cloudflare Worker (`mcp-worker/`, deployed), Supabase project `kjqbnurycfjsuufibkac`, free tier.
- The Worker authenticates to Supabase as the seeded admin (`ADMIN_EMAIL`/`ADMIN_PASSWORD` secrets); that admin has a `staff` row, which the write RPCs require (`reviewed_by`/`decided_by`/`handled_by` FKs point at `staff(id)`).
- Repo rule from earlier sessions: never print or commit secrets; `web/` untouched; `desktop/` may change; **nothing is committed until the admin decides**.
- ChatGPT custom MCP servers: OAuth only; tools without `readOnlyHint` are treated as **write actions** and require user confirmation (OpenAI dev-mode behavior, help.openai.com "Developer mode and MCP apps in ChatGPT"). Dev mode must be ON in the chat for custom tools.

## Decisions agreed with the admin (this session)

1. Scope = full admin parity **minus** staff accounts and roster import (table presented and approved 2026-10-15).
2. ChatGPT asks for confirmation before each change; every action logged; app rules enforced server-side; off-switch to read-only (all promised in chat).
3. Same connector/setup; only a Refresh after redeploy.

## The how

### A. Database — three new migrations

**A1. `20261015233000_room_invariants.sql` — make the app's UI checks real DB rules**

Today "cannot delete an occupied room" and "capacity ≥ occupancy" and "gender locked while occupied" live only in the desktop UI (`desktop/app/ui/pages/rooms.py:66-70,291-296`); the DB would silently accept all three (FKs are `ON DELETE SET NULL`). Guard them with triggers:

- `rooms_guard_delete` (BEFORE DELETE on `rooms`): count `students` with `room_id = old.id AND status = 'active'`; if > 0 raise `Cannot delete room <block>-<number>: <n> active resident(s) are still assigned.`
- `rooms_guard_update` (BEFORE UPDATE on `rooms`): if `new.capacity <` that count → raise `Cannot set capacity below the <n> active resident(s) already assigned.`; if `new.gender <> old.gender` and count > 0 → raise `Cannot change the gender of an occupied room.`

Embedded **self-test** (a `DO` block that runs at `db push` time): create a scratch `auth.users` row (minimal columns; the `handle_new_user` trigger then creates its profile + student), set the scratch student `active` in a scratch room, then assert that all three forbidden operations raise and are caught, and that deleting the now-empty room succeeds; delete everything again. If any expected guard does **not** fire, `RAISE EXCEPTION` so the migration (and the `db push`) fails loudly. The migration transaction makes the whole thing all-or-nothing — no residue either way.

**A2. `20261015233500_mcp_room_ids.sql` — read outputs expose room ids**

The write tools take `room_id` uuids, but today no read tool returns room ids (`mcp_list_rooms` and every embedded room object carry only block/floor/number/label/capacity/gender/occupancy) — the flagship "approve the two that look fine" flow would be impossible. Fix: `create or replace` the affected read functions adding `"id"` to the room objects — `mcp_list_rooms` items and the nested room objects in `mcp_list_tickets`, `mcp_list_room_changes` (current/preferred) and `mcp_search_students`. The local Python server reads through the same SQL functions, so both surfaces stay identical (outputs change, parity preserved). No other read-output changes.

**A3. `20261015234000_mcp_write_functions.sql` — write surface, settings, audit outcome**

- `mcp_settings` table: singleton row (`id boolean primary key default true check (id)`), `writes_enabled boolean not null default true`, `updated_at`, `updated_by uuid`; seeded enabled. RLS: single policy `mcp_settings_admin` for all commands, `using (auth_role() = 'admin') with check (auth_role() = 'admin')`; reuse the existing `set_updated_at()` trigger.
- `mcp_get_settings() returns jsonb` (invoker, admin-gated via `mcp_require_admin()`): returns `{writes_enabled, updated_at}`.
- `mcp_set_writes_enabled(p_enabled boolean) returns jsonb` — the off-switch, admin-gated; returns the new settings.
- `mcp_create_room(p_block text, p_floor int, p_number text, p_capacity int, p_gender text) returns jsonb` — invoker, admin-gated. Mirrors `RoomSetupDialog` (`rooms.py:41-103`): block trimmed+uppercased non-empty; number non-empty; floor 0–15; capacity 1–8; gender `male|female`; catch `unique_violation` → `Room <block>-<number> already exists.`; returns the created row as jsonb.
- `mcp_update_room(p_room uuid, p_block text default null, p_floor int default null, p_number text default null, p_capacity int default null, p_gender text default null) returns jsonb` — partial update; same field validations; `room not found`; guards apply via A1 triggers; unique violation mapped; returns the updated row.
- `mcp_delete_room(p_room uuid) returns jsonb` — `room not found`; A1 trigger refuses occupied rooms; returns `{deleted: true, room: {...}}`.
- `mcp_update_ticket(p_ticket uuid, p_status text, p_note text default null) returns jsonb` — admin-gated; `p_status` normalized, must be `in_progress` or `resolved` (both allowed from any state, like the app's always-enabled buttons); note optional (blank keeps the existing note — parity with `maintenance.py:301`); sets `handled_by = auth.uid()`; `ticket not found`; returns the updated row.
- **Reused as-is** for decisions (exact app path, already validate): `approve_student`, `reject_student`, `approve_room_change`, `reject_room_change` (`20261010102834_rpc_functions.sql`, row-locked in `20261010110101_rpc_room_lock.sql`). They raise `reason required`, `gender mismatch`, `room full`, `student not found`, `room not found`, `pending request not found`.
- **Audit gains an outcome (two-phase)**: `mcp_audit_log` + `ok boolean`, `detail text`; `mcp_log_audit` re-created to return the new row id (`bigint`) — same params, drop + create because the return type changes, old callers just ignore the value; new `mcp_complete_audit(p_id bigint, p_ok boolean, p_detail text default null)` (admin-gated, definer) fills `ok`/`left(detail, 500)` on that row; `mcp_list_audit` updated to return `ok, detail` too (it selects explicit columns today).
- Grants: `revoke execute … from public, anon; grant execute … to authenticated` for every new/changed function (house pattern).

### B. Worker (`mcp-worker/`) — 14 tools, correct annotations, gate, audit outcomes

**B1. Annotations (all 14 tools).** ChatGPT treats tools without `readOnlyHint` as write actions. Reads currently have no annotations, so ChatGPT asks for confirmation even for reads — fix while here:
- 6 existing reads: `annotations: { readOnlyHint: true, openWorldHint: true }` (names/descriptions/handlers unchanged).
- 8 new writes: `readOnlyHint: false`, `openWorldHint: true`, and `destructiveHint: true` **only** for `reject_registration`, `reject_room_change`, `delete_room`.

**B2. New write tools** (names → backend):

| Tool | Args | Backend |
|---|---|---|
| `approve_registration` | `student_id`, `room_id` | `approve_student` |
| `reject_registration` | `student_id`, `reason` (non-empty) | `reject_student` |
| `approve_room_change` | `request_id`, `room_id` | `approve_room_change` |
| `reject_room_change` | `request_id`, `reason` (non-empty) | `reject_room_change` |
| `create_room` | `block`, `floor` 0–15, `number`, `capacity` 1–8, `gender` male\|female | `mcp_create_room` |
| `update_room` | `room_id` + optional `block`, `floor`, `number`, `capacity`, `gender` | `mcp_update_room` |
| `delete_room` | `room_id` | `mcp_delete_room` |
| `update_ticket` | `ticket_id`, `status` in_progress\|resolved, optional `note` | `mcp_update_ticket` |

Zod schemas mirror the SQL validations (uuid format for ids, ranges, enums) so obvious mistakes fail before the network. Every write description instructs the model to **show the user exactly what will change and get explicit confirmation before calling** (belt and suspenders on top of ChatGPT's own approval), and to fetch ids from the read tools (`list_pending_registrations`, `list_rooms`, …) rather than guessing — room ids come from `list_rooms` (A2).

**B3. Write-call flow** (shared helper in `mcp.ts`) — "no audit row, no write":
1. Read the gate: `mcp_get_settings()` (no caching — instant effect; read error → refuse, fail closed; a missing settings row counts as enabled, the seeded default). If disabled → return `Writing is currently disabled. Turn it on in the desktop app: Settings → Allow ChatGPT to change data.` (attempt row logged best-effort with `ok=false`).
2. Log the attempt: `mcp_log_audit(...)` must return a row id. If that fails, **refuse the write** — return `Could not record this action in the audit log, so nothing was changed. Try again.` (a change must never happen unlogged).
3. Execute the RPC. On error → `friendlyError()`, complete the row with `ok=false, detail=<message>`.
4. On success → complete the row with `ok=true, detail=<short outcome from the returned row>` (e.g. card id + new status, ticket status) and return the changed row as compact JSON (reuse `truncateRecords`).
5. Audit calls stay bounded (2 s); the attempt call is fail-closed for writes, the completion call is best-effort (a row stuck at `ok=null` means "outcome unknown" — visible, never silent). Reads keep today's audit-before semantics unchanged (`ok` stays null).

**B4. Friendly error text** (`errors.ts`): map the write-domain messages to clean sentences (occupied-room delete, capacity/gender guards, `reason required`, `gender mismatch`, `room full`, `* not found`, `already exists`); keep existing read mappings untouched.

**B5. Server instructions** (`SERVER_INSTRUCTIONS`): update to say the tools can also change data when the admin has enabled it, that every change must be confirmed with the user first, and that write actions may be disabled. This deliberately diverges from `mcp/server.py` (local stays read-only); the character-for-character parity commitment is re-scoped to the 6 read tools only.

### C. Desktop (`desktop/app/ui/pages/settings.py`)

- Add **"Allow ChatGPT to change data"** checkbox + hint ("ChatGPT asks you to confirm every change first. Turn this off to make ChatGPT read-only again.") in the ADVANCED SETTINGS card — **outside** the Developer-mode-gated content, so admins always see the off-switch (dev mode is session-only and would hide it). Loads via `mcp_get_settings`, saves via `mcp_set_writes_enabled` using the existing `client`; error → message box + revert. Admin-only, as today.
- Update the "read-only … never change it" copy (footer, `settings.py:313`) and the hosted-section hints to describe reads + confirmed, logged writes.

### D. Tests and verification

- **Migration self-tests** (A1) run inside `npx supabase db push` — the guards are proven or the push fails.
- **Worker vitest** (`mcp-worker/test/`): 14 tools registered with correct annotations; zod rejects bad args (capacity 0/9, floor 16, gender "x", empty reason, bad status/uuid); gate-off returns the disabled message and makes **no** write RPC call; success path calls the right RPC with the right params, logs the attempt first and completes it `ok=true` with detail; error path completes `ok=false`; attempt-log failure refuses the write; read outputs include room ids. Existing parity tests that pinned 6 tools / the old instructions text are updated (reads stay char-for-char with Python).
- **Prod acceptance** (`mcp-worker/scripts/verify_remote.py`, extended, run against the deployed URL): tool list = 14 + annotation checks + room ids present in read outputs; write round-trip on a scratch room (`block "ZZT"`, random number): create → update capacity → confirm in `list_rooms` → delete → confirm gone (self-cleaning); safe negative probes (blank rejection reason, unknown ids → friendly errors, duplicate room → `already exists`); gate probe: disable via `mcp_set_writes_enabled(false)` → write tool refused → re-enable → works; audit rows read back via `mcp_list_audit` with `ok` set. **No** destructive probe against real occupied rooms on prod — that case is proven by the migration self-test.
- **Desktop smoke**: existing 28 tests + the toggle (visible for admins without dev mode, saves/reverts, message on failure) + screenshot.
- Manual ChatGPT check by the admin after deploy (Refresh once): e.g. "create a test room 999 in block Z with 2 places" → confirm prompt → appears; "approve …" on a test registration.

### E. Documentation

- `mcp-worker/README.md` (tools table incl. writes, annotations, gate toggle, audit semantics, redeploy + Refresh), `mcp/README.md` (local = read-only fallback), `docs/manual-test-mcp.md` (write checklist + how to flip the switch), root `README.md` (feature wording), `desktop` Settings copy (above), `docs/mcp-handoff.md` (Session 4 record when shipped).

## Rollout

1. `npx supabase db push` (all three migrations; self-tests green).
2. Worker: `npm test` + `tsc` + `wrangler deploy --dry-run` → `npx wrangler deploy`.
3. `python mcp-worker/scripts/verify_remote.py https://residence-mcp.anes4tlm.workers.dev` → all checks pass.
4. Desktop smoke + screenshot.
5. Admin: restart the desktop app (the toggle is visible for admins right away), tap **Refresh** on the ChatGPT connection, try one approved change end-to-end.

**Rollback**: `npx wrangler rollback` restores the previous Worker version (reads unaffected either way); DB changes are additive (new table/columns/functions/triggers) and can be left or dropped by a later migration.

## This document's calls (decided here, listed for the admin to veto)

1. Off-switch = a checkbox in the desktop Settings backed by a Supabase row — instant, no redeploy, no new secrets.
2. The occupied-room rules become real database rules (triggers) — also closes the existing UI-only hole for the desktop app itself.
3. Writes are audited **two-phase**: an attempt row is required *before* execution (otherwise the write is refused), and `ok` + short detail are filled in after; reads keep a single attempt row with `ok` null.
4. Reads get `readOnlyHint` annotations too (stops ChatGPT asking to confirm harmless reads).
5. Local Python server stays read-only; char-for-char parity re-scoped to the 6 read tools.
6. `update_ticket` only allows the two transitions the app offers (`in_progress`, `resolved`); blank note keeps the previous note.
7. Prod verification uses self-cleaning scratch data only; the "cannot delete occupied room" case is proven by the migration self-test instead.
8. The read tools now expose room ids (A2) — a small, additive output change for both the worker and the local server; it is what makes room-targeting write tools usable.
9. The off-switch sits outside the Developer-mode gate (C) so it is always reachable for admins.

## Left to the builder (safe to decide while planning)

- Exact minimal `auth.users` insert column list for the self-test (verify against the live schema on first push; the push either succeeds or rolls back cleanly).
- Exact zod API details in the installed `@modelcontextprotocol/server` version (`.uuid()`, `annotations` field typing) — `tsc` will confirm.
- Wording of tool descriptions/instructions within the constraints above; exact friendly-error phrasings and per-tool `detail` strings.
- Test file organization and counts; ordering of tasks and commits (nothing is committed until the admin says so).
