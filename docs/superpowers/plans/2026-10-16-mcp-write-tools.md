# MCP write tools (ChatGPT manages the residence) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 8 admin write tools to the hosted MCP worker (approve/reject registrations, approve/reject room changes, create/edit/delete rooms, update tickets) with ChatGPT-side confirmations, DB-enforced invariants, two-phase audit logging, and a desktop off-switch — same connector, same URL, no new setup.

**Architecture:** Three additive Supabase migrations (room guard triggers with an embedded self-test; room ids in read outputs; write RPCs + settings + two-phase audit), then worker changes (two-phase audit trail, 8 new tools with MCP annotations, friendly write errors, updated instructions), prod verification via the extended acceptance script, then the desktop Settings toggle and docs. The Python local server and `web/` stay untouched.

**Tech Stack:** Cloudflare Workers (TypeScript, vitest 5.0.5, wrangler 4.151.0), `@modelcontextprotocol/server` 2.3.1 + `agents` 0.28.1 + zod 4.6.7, Supabase Postgres (migrations via `npx supabase db push`), Python stdlib scripts (`mcp\.venv`), PySide6 desktop (`desktop\.venv`).

**Spec:** `docs/superpowers/specs/2026-10-15-mcp-write-tools-design.md`

## Global Constraints

- Never print or commit secrets; never use the service-role key. Values live in `mcp/.env` and scripts read them without echoing.
- `web/` untouched. `desktop/` may change. **Nothing is committed until the admin approves** — every task's commit step is *deferred*: record the exact `git add` + message but do NOT run `git commit`.
- Tool names and args (exact): `approve_registration(student_id, room_id)`, `reject_registration(student_id, reason)`, `approve_room_change(request_id, room_id)`, `reject_room_change(request_id, reason)`, `create_room(block, floor, number, capacity, gender)`, `update_room(room_id, block?, floor?, number?, capacity?, gender?)`, `delete_room(room_id)`, `update_ticket(ticket_id, status, note?)`.
- Validation values: floor 0–15; capacity 1–8; gender `male|female`; rejection reason non-empty after trim; ticket status `in_progress|resolved`.
- Worker messages (exact): disabled = `Writing is currently disabled. Turn it on in the desktop app: Settings → Allow ChatGPT to change data.`; audit-required = `Could not record this action in the audit log, so nothing was changed. Try again.`
- Commands: DB from repo root (`npx supabase db push`); worker in `mcp-worker/` (`npm test`, `npm run typecheck`, `npx wrangler deploy`); Python probes with `& "mcp\.venv\Scripts\python.exe"`; desktop with `& "desktop\.venv\Scripts\python.exe"`. Windows PowerShell.
- Free tier only; no new secrets; deployed origin stays `https://residence-mcp.anes4tlm.workers.dev`.

## Review Focus

Inputs/conditions a real user will hit that no single task's happy path covers — each is pinned by the task named:

1. A write attempt while the off-switch is off → refused with the disabled message, nothing mutated (Task 5 tests; Task 6/7 prod probe).
2. A stale or hallucinated id (well-formed uuid, unknown record) → friendly "not found" text, no crash, no partial write (Task 3 probe; Task 5 tests).
3. The attempt-log call fails before a write → the write is refused, never executed unlogged (Task 4 + Task 5 tests).
4. A student assigned to a room concurrently → delete/capacity/gender guards still refuse at the DB level regardless of client (Task 1 self-test).
5. Duplicate `block`+`number` on create or rename → "already exists" message, no stack trace (Task 3 probe; Task 5 test).

---

### Task 1: Room invariant guards (migration A1)

**Files:**
- Create: `supabase/migrations/20261015233000_room_invariants.sql`

**Interfaces:**
- Consumes: existing `rooms`/`students` schema (`supabase/migrations/20261009222837_core_tables.sql`).
- Produces: trigger function `rooms_guard()` + triggers `rooms_guard_delete` (BEFORE DELETE) and `rooms_guard_update` (BEFORE UPDATE) on `rooms`. Message prefixes `Cannot delete room`, `Cannot set capacity below`, `Cannot change the gender` are consumed by Task 5's friendly-error mapping.

- [ ] **Step 1: Write the migration**

Header comment in the house style (purpose, design rules, rollback note). Contents:

1. `rooms_guard()` — `returns trigger language plpgsql`:
   - `tg_op = 'DELETE'`: count `students` with `room_id = old.id AND status = 'active'`; if `> 0` raise `Cannot delete room %-%: % active resident(s) are still assigned.` (block, number, count); `return old`.
   - `tg_op = 'UPDATE'`: same count for `new.id`; if `new.capacity < count` raise `Cannot set capacity below the % active resident(s) already assigned.`; if `new.gender <> old.gender and count > 0` raise `Cannot change the gender of an occupied room.`; `return new`.
2. Two triggers calling it (names above).
3. An embedded `DO` block self-test that runs at push time and `raise exception`-s if any expectation fails (transaction rolls everything back). Skeleton — fill in the `auth.users` columns from the live schema if the push complains (the push fails atomically; iterate until green):

```sql
do $$
declare
  v_user uuid := gen_random_uuid();
  v_room uuid;
  v_num text := 'SELFTEST-' || substr(md5(random()::text), 1, 8);
  v_ok boolean;
begin
  -- Scratch user; handle_new_user() then creates its profile + student row.
  insert into auth.users (id, instance_id, aud, role, email, encrypted_password,
                          email_confirmed_at, raw_app_meta_data, raw_user_meta_data)
  values (v_user, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
          v_num || '@selftest.local', crypt('x', gen_salt('bf')), now(),
          '{"provider":"email","providers":["email"]}'::jsonb,
          jsonb_build_object('card_id', v_num, 'first_name', 'Self', 'last_name', 'Test',
                             'birth_date', '2000-01-01', 'gender', 'male', 'phone', '0000000000',
                             'university', 'T', 'faculty', 'T', 'study_level', 'L1', 'wilaya', 'T'));
  insert into rooms (block, floor, number, capacity, gender)
  values ('SELFTEST', 0, v_num, 1, 'male') returning id into v_room;
  update students set status = 'active', room_id = v_room where id = v_user;

  v_ok := false;
  begin delete from rooms where id = v_room; exception when others then v_ok := true; end;
  if not v_ok then raise exception 'SELFTEST: deleting an occupied room was NOT blocked'; end if;

  -- Match the guard's own message: with capacity 1, a plain CHECK would also fire.
  v_ok := false;
  begin update rooms set capacity = 0 where id = v_room;
  exception when others then v_ok := sqlerrm like 'Cannot set capacity below%'; end;
  if not v_ok then raise exception 'SELFTEST: capacity below occupancy was NOT blocked'; end if;

  v_ok := false;
  begin update rooms set gender = 'female' where id = v_room; exception when others then v_ok := true; end;
  if not v_ok then raise exception 'SELFTEST: gender change on an occupied room was NOT blocked'; end if;

  -- Unassign (cascades profile + student), then the now-empty room must delete cleanly.
  delete from auth.users where id = v_user;
  delete from rooms where id = v_room;
  if exists (select 1 from rooms where id = v_room) then
    raise exception 'SELFTEST: empty room delete did not work';
  end if;
end $$;
```

- [ ] **Step 2: Apply and verify**

Run (repo root): `npx supabase db push`
Expected: `Applying migration 20261015233000_room_invariants.sql` then `Finished supabase db push.` — a guard bug makes the push FAIL loudly (that is the test).

- [ ] **Step 3: Deferred commit**

`git add supabase/migrations/20261015233000_room_invariants.sql`
Message: `feat(db): guard rooms against deleting occupied rooms, capacity cuts and gender flips`

---

### Task 2: Read outputs expose room ids (migration A2)

**Files:**
- Create: `supabase/migrations/20261015233500_mcp_room_ids.sql`
- Read first: `supabase/migrations/20261015120000_mcp_admin_readonly_functions.sql`

**Interfaces:**
- Consumes: the four read functions' current bodies (copy them verbatim).
- Produces: same function signatures, but every embedded room object now carries `"id"` — consumed by Task 5 tool descriptions, Task 6's `room ids in list_rooms` check, and the ChatGPT model (it copies ids from read output into write args).

- [ ] **Step 1: Write the migration**

`create or replace` these four functions, bodies copied verbatim from `20261015120000_mcp_admin_readonly_functions.sql` with one added key each:

- `mcp_list_rooms(text, boolean)` — item object: add `'id', r.id,` (first key).
- `mcp_list_tickets(text, int)` — `room` object: add `'id', r.id,`.
- `mcp_list_room_changes(text, int)` — `current_room`: `'id', cr.id,`; `preferred_room`: `'id', pr.id,`.
- `mcp_search_students(text, int)` — `room` object: add `'id', r.id,`.

Keep each function's `comment on` statement. Grants persist (same signatures). No other output changes.

- [ ] **Step 2: Apply**

Run: `npx supabase db push` → Expected: migration applied, push finished.

- [ ] **Step 3: Probe the live DB**

Write `%TEMP%\opencode\verify_room_ids.py` (stdlib; parse `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` from `mcp/.env` without printing values; password-grant login; POST `/rest/v1/rpc/...` as admin). Calls: `mcp_list_rooms {}`, `mcp_search_students {"p_query":"a"}`, `mcp_list_tickets {"p_limit":5}`, `mcp_list_room_changes {"p_limit":5}`. Assert: every non-null room object has an `id` matching a uuid regex; print `PASS room ids in read outputs`.

Run: `& "mcp\.venv\Scripts\python.exe" "%TEMP%\opencode\verify_room_ids.py"`
Expected: PASS (rooms exist in prod; if a list is empty it is skipped).

- [ ] **Step 4: Deferred commit**

`git add supabase/migrations/20261015233500_mcp_room_ids.sql`
Message: `feat(db): expose room ids in the MCP read outputs`

---

### Task 3: Write RPCs, settings and two-phase audit (migration A3)

**Files:**
- Create: `supabase/migrations/20261015234000_mcp_write_functions.sql`
- Create: `mcp-worker/scripts/verify_db_write.py`

**Interfaces:**
- Consumes: `mcp_require_admin()` (existing), `auth_role()`, `set_updated_at()`, `rooms`/`students`/`maintenance_reports` tables, Task 1's guard triggers.
- Produces (exact signatures, all `security invoker` unless noted, all admin-gated via `perform mcp_require_admin()`, all `set search_path = public, pg_temp`):
  - `mcp_get_settings() returns jsonb` — stable; `{writes_enabled, updated_at}`; missing row → `{"writes_enabled": true, ...}`.
  - `mcp_set_writes_enabled(p_enabled boolean) returns jsonb` — updates the row (`updated_by = auth.uid()`), returns the new settings.
  - `mcp_create_room(p_block text, p_floor int, p_number text, p_capacity int, p_gender text) returns jsonb`
  - `mcp_update_room(p_room uuid, p_block text default null, p_floor int default null, p_number text default null, p_capacity int default null, p_gender text default null) returns jsonb`
  - `mcp_delete_room(p_room uuid) returns jsonb` — `{deleted: true, room: {...}}`
  - `mcp_update_ticket(p_ticket uuid, p_status text, p_note text default null) returns jsonb`
  - `mcp_log_audit(p_tool text, p_args jsonb default '{}'::jsonb) returns bigint` (security definer, like today) — returns the new row id.
  - `mcp_complete_audit(p_id bigint, p_ok boolean, p_detail text default null) returns void` (security definer) — fills `ok` + `left(detail, 500)`; raises `audit row not found` if the id is missing.
  - `mcp_list_audit(p_limit int default 20) returns jsonb` — now also returns `ok`, `detail` (keep the explicit-columns select updated).
  - New `mcp_settings` table + single seeded row + `mcp_settings_admin` RLS policy (all commands, `auth_role() = 'admin'`) + `set_updated_at()` trigger.

- [ ] **Step 1: Write the migration**

Pinned messages/rules (write bodies from spec §A3):

| Function | Rules → messages |
|---|---|
| create_room | blank block → `block required`; blank number → `room number required`; floor outside 0–15 → `floor must be between 0 and 15`; capacity outside 1–8 → `capacity must be between 1 and 8`; gender not male/female (case-insensitive trim) → `gender must be male or female`; insert with `upper(trim(block))`, `trim(number)`; catch `unique_violation` → `room %-% already exists` (upper block, trimmed number); return `to_jsonb(row)` |
| update_room | `select ... for update`; missing → `room not found`; same field validations for provided fields only (blank block/number are errors, not skips); update with `coalesce(...)` over provided fields; catch `unique_violation` → `room %-% already exists` using the effective block/number; return `to_jsonb(row)` |
| delete_room | missing → `room not found`; `delete ... returning *` (Task 1 trigger refuses occupied rooms); return `jsonb_build_object('deleted', true, 'room', to_jsonb(row))` |
| update_ticket | normalize status (trim/lower); not `in_progress`/`resolved` → `invalid status: % (expected in_progress or resolved)`; `select ... for update`; missing → `ticket not found`; set `status`, `staff_note = coalesce(nullif(btrim(p_note), ''), staff_note)`, `handled_by = auth.uid()`; return `to_jsonb(row)` |
| set_writes_enabled | `p_enabled` null → `enabled required`; update singleton row; return settings jsonb |

Audit changes: `alter table mcp_audit_log add column ok boolean, add column detail text;` then `drop function mcp_log_audit(text, jsonb);` and re-create (return type change) returning the new id, then re-apply its revoke/grant (drop removes grants); `create or replace mcp_list_audit` with `ok, detail` added to the select list.

Grants (revoke `public, anon`; grant `authenticated`) for every function above.

- [ ] **Step 2: Apply**

Run: `npx supabase db push` → Expected: migration applied, push finished.

- [ ] **Step 3: Write `mcp-worker/scripts/verify_db_write.py`**

Stdlib-only, same env resolution as Task 2 (values never printed). Login as admin, then probe and print `PASS`/`FAIL` per check + summary (non-zero exit on any FAIL):

1. `mcp_get_settings` → `writes_enabled` true.
2. `mcp_set_writes_enabled {"p_enabled": false}` → false; set back to true → true.
3. `mcp_create_room` scratch (`block "ZZT"`, `number "DBTEST-<random>"`, `floor 9`, `capacity 2`, `gender "male"`) → row with `id`.
4. Duplicate create → error message contains `already exists`.
5. `mcp_update_room {"p_room": <id>, "p_capacity": 3}` → `capacity` 3.
6. `mcp_delete_room` → `deleted` true; repeat → `room not found`.
7. `mcp_update_ticket` with a random uuid → `ticket not found`.
8. `reject_student` random uuid + `"   "` reason → `reason required`.
9. `mcp_log_audit {"p_tool": "verify_db_probe", "p_args": {}}` → numeric id; `mcp_complete_audit {"p_id": <id>, "p_ok": true, "p_detail": "probe"}` → 204; `mcp_list_audit {"p_limit": 5}` → newest row has `ok: true`, `detail: "probe"`.

- [ ] **Step 4: Run it**

Run: `& "mcp\.venv\Scripts\python.exe" "mcp-worker\scripts\verify_db_write.py"`
Expected: every line PASS, summary `0 failed`.

- [ ] **Step 5: Deferred commit**

`git add supabase/migrations/20261015234000_mcp_write_functions.sql mcp-worker/scripts/verify_db_write.py`
Message: `feat(db): MCP write RPCs, writes off-switch and two-phase audit outcome`

---

### Task 4: Worker — two-phase audit trail

**Files:**
- Modify: `mcp-worker/src/audit.ts`
- Modify: `mcp-worker/src/mcp.ts` (type + 6 read handlers only)
- Modify: `mcp-worker/test/mcp.test.ts`

**Interfaces:**
- Consumes: `RpcCall` (unchanged).
- Produces: `AuditTrail { begin(tool, args): Promise<number | null>; complete(id: number | null, ok: boolean, detail: string): Promise<void> }` and `createAuditLogger(rpc): AuditTrail`; `ToolDeps.audit` becomes `AuditTrail` (update the stale doc comment at `mcp.ts` line ~39 — "awaited before each tool runs" no longer describes `begin`). Task 5 builds on both. `AUDIT_TIMEOUT_MS = 2000` stays.

- [ ] **Step 1: Update the audit tests first (red)**

In `mcp-worker/test/mcp.test.ts`:
- `makeDeps()` now uses `const audit = { begin: vi.fn(async (_tool, _args) => 1), complete: vi.fn(async (_id, _ok, _detail) => {}) };` and `deps = { audit, rpc }`.
- Existing read-handler expectations change from `audit(...)` to `audit.begin(...)` (same args) — e.g. `expect(audit.begin).toHaveBeenCalledExactlyOnceWith("list_maintenance_tickets", { status: null, limit: 20 })`.
- Replace the `createAuditLogger` block: `begin` → calls `mcp_log_audit` with `{p_tool, p_args}` + timeout signal and returns the resolved number; returns `null` when rpc resolves `null` or throws; `complete` → calls `mcp_complete_audit` with `{p_id, p_ok, p_detail}` + timeout signal; does nothing (rpc not called) when id is `null`; swallows throws.

Run: `npm test` (in `mcp-worker/`) → Expected: FAIL (`begin is not a function` / type errors).

- [ ] **Step 2: Implement `audit.ts`**

Replace `AuditLog` with `AuditTrail`; `begin` wraps `mcp_log_audit` in try/catch (2 s signal), coerces the body to a number (accept number or numeric string) or `null`; `complete` no-ops on `null` id and swallows all failures.

- [ ] **Step 3: Adapt `mcp.ts` reads**

`ToolDeps.audit: AuditTrail`; every `await deps.audit(...)` becomes `await deps.audit.begin(...)`. No other change.

- [ ] **Step 4: Green**

Run: `npm test` → all pass. Run: `npm run typecheck` → clean.

- [ ] **Step 5: Deferred commit**

`git add mcp-worker/src/audit.ts mcp-worker/src/mcp.ts mcp-worker/test/mcp.test.ts`
Message: `feat(worker): two-phase audit trail (begin + complete)`

---

### Task 5: Worker — 8 write tools, annotations, instructions, friendly errors

**Files:**
- Modify: `mcp-worker/src/mcp.ts`
- Modify: `mcp-worker/src/errors.ts`
- Modify: `mcp-worker/test/mcp.test.ts`
- Modify: `mcp-worker/test/errors.test.ts`

**Interfaces:**
- Consumes: Task 4's `AuditTrail`; Task 3's RPCs; Task 2's room ids.
- Produces: the 14-tool surface (Global Constraints names/args); constants `WRITING_DISABLED_MESSAGE` and `AUDIT_REQUIRED_MESSAGE`; new `SERVER_INSTRUCTIONS`; `friendlyError` handling for write messages. Task 6 asserts all of these over the wire.

- [ ] **Step 1: Extend `errors.ts` (+ tests, red first)**

After the existing mappings, add a write-marker map (message → returned text; matching is lowercase-substring, first match wins):

- `reason required` → `A rejection reason is required.`
- `gender mismatch` → `That room's gender does not match the student's.`
- `room full` → `That room has no free places.`
- `student not found` → `Student not found (the id may be stale — re-check with list_pending_registrations or search_students).`
- `room not found` → `Room not found (the id may be stale — re-check with list_rooms).`
- `pending request not found` → `No pending room-change request with that id (it may already be decided — re-check with list_room_change_requests).`
- `ticket not found` → `Maintenance ticket not found (re-check with list_maintenance_tickets).`
- Pass through as-is (they are already user-ready): `cannot delete room`, `cannot set capacity`, `cannot change the gender`, `already exists`.

Add one `errors.test.ts` case per family. Run `npm test` → red.

- [ ] **Step 2: `mcp.ts` — annotations on the 6 reads**

Add to each existing `registerTool` config: `annotations: { readOnlyHint: true, openWorldHint: true }`. (Names/descriptions/handlers unchanged.) If `tsc` rejects the field name, check the installed SDK's `ToolAnnotations` type and adapt — the wire format must be the MCP camelCase hints.

- [ ] **Step 3: `mcp.ts` — write flow + 8 tools**

Add helpers:

- `getWritesEnabled(deps): Promise<boolean | null>` — rpc `mcp_get_settings`; parse `writes_enabled` (missing row → `true`); any error → `null` (fail closed).
- `runWrite(deps, tool, args, execute, describe)`:
  1. gate: `null` → return `Writing could not be verified right now, so nothing was changed. Try again.` (audit best-effort `begin`+`complete(false)`); `false` → return `WRITING_DISABLED_MESSAGE` (audit best-effort with `ok=false`).
  2. `const id = await deps.audit.begin(tool, args)`; `id === null` → return `AUDIT_REQUIRED_MESSAGE` (no rpc call).
  3. `await execute()`; success → `deps.audit.complete(id, true, describe(row))`, return `toCompactJson(truncateRecords(row))` (null/empty → `No data returned.`); error → `const text = friendlyError(error)`, `deps.audit.complete(id, false, text)`, return `text`.

Register the 8 tools (names/args per Global Constraints) with `annotations: { readOnlyHint: false, openWorldHint: true }` plus `destructiveHint: true` only for `reject_registration`, `reject_room_change`, `delete_room`. Zod schemas: `z.string()` for ids (validated as uuid by SQL: unknown ids surface as friendly "not found"), `z.number().int()` for floor/capacity, `z.string()` for enums with in-handler "Invalid request: ..." checks (matching the read-tool style — keeps probes text-based):

- `reject_registration` / `reject_room_change`: blank/whitespace reason → `Invalid request: a rejection reason is required (so the student knows why).`
- `create_room` / `update_room`: floor outside 0–15 → `Invalid request: floor must be between 0 and 15.`; capacity outside 1–8 → `Invalid request: capacity must be between 1 and 8.`; gender not male/female → `Invalid request: gender must be male or female.`
- `update_ticket`: status not in_progress/resolved → `Invalid request: status must be in_progress or resolved.`

RPC mapping: `approve_registration` → `approve_student {p_student, p_room}`; `reject_registration` → `reject_student {p_student, p_reason}`; `approve_room_change` → `approve_room_change {p_request, p_room}`; `reject_room_change` → `reject_room_change {p_request, p_reason}`; `create_room` → `mcp_create_room {p_block, p_floor, p_number, p_capacity, p_gender}`; `update_room` → `mcp_update_room {p_room, p_block, p_floor, p_number, p_capacity, p_gender}` (nulls for omitted); `delete_room` → `mcp_delete_room {p_room}`; `update_ticket` → `mcp_update_ticket {p_ticket, p_status, p_note}`.

Descriptions — each states the action, `This changes data: show the user ... and get their explicit confirmation before calling`, where ids come from, and the key validation:

- `approve_registration`: "...assign the student to a room. Get student_id from list_pending_registrations and room_id from list_rooms (gender must match, room needs a free place)."
- `reject_registration`: "...a reason is required. Get student_id from list_pending_registrations."
- `approve_room_change`: "...moves the student to the given room. Get request_id from list_room_change_requests and room_id from list_rooms."
- `reject_room_change`: "...a reason is required. Get request_id from list_room_change_requests."
- `create_room`: "...block is uppercased; floor 0–15; capacity 1–8; gender male or female; block+number must not already exist."
- `update_room`: "...omitted fields stay unchanged; capacity cannot go below current occupancy; gender cannot change while residents are assigned. Get room_id from list_rooms."
- `delete_room`: "...permanent; refused while active residents are assigned. Get room_id from list_rooms."
- `update_ticket`: "...mark it in_progress (technician dispatched) or resolved (closed), optional note. Get ticket_id from list_maintenance_tickets."

Update `SERVER_INSTRUCTIONS` to: `"Administrator tools for the Residence Tlemcen university residence. You can read data freely; when the administrator has enabled changes you can also approve or reject registrations and room-change requests, manage rooms, and update maintenance tickets. Before any change, show the user exactly what will change and get their explicit confirmation. All data comes from the live Supabase project; every call is logged."` (Reads stay char-for-char with Python; this text deliberately diverges.)

- [ ] **Step 4: Tests (red first, then green)**

`captureTools` must capture `config.annotations`. Update: the "6 tools" test → 14 tools (first 6 descriptions still verbatim); new annotation assertions (reads `readOnlyHint true`; writes `false`; `destructiveHint true` exactly on the 3); `SERVER_INSTRUCTIONS` expectation → new text. Add per-tool cases:

- success: correct rpc name + params; `begin` called with (tool, args); `complete(id, true, detail)`; result JSON parses.
- gate off: disabled message returned; write rpc NOT called; `complete(id, false, ...)` called.
- gate read error: refusal message; write rpc NOT called.
- `begin` → `null`: `AUDIT_REQUIRED_MESSAGE`; write rpc NOT called.
- rpc error: friendly text; `complete(id, false, <text>)`.
- validation: blank reason / floor 16 / capacity 9 / gender "x" / status "done" → `Invalid request: ...` texts, write rpc NOT called.

Run: `npm test` → green; `npm run typecheck` → clean.

- [ ] **Step 5: Deferred commit**

`git add mcp-worker/src/mcp.ts mcp-worker/src/errors.ts mcp-worker/test/mcp.test.ts mcp-worker/test/errors.test.ts`
Message: `feat(worker): 8 admin write tools with annotations, gate and audit outcomes`

---

### Task 6: Extend `verify_remote.py`

**Files:**
- Modify: `mcp-worker/scripts/verify_remote.py`

**Interfaces:**
- Consumes: the deployed 14-tool surface (Task 5), `mcp/.env` admin creds (for direct REST probes), `MCP_AUTH_TOKEN` (existing).
- Produces: the acceptance script Task 7 runs as the prod gate.

- [ ] **Step 1: Extend the script**

- `EXPECTED_TOOLS` → the 14 names (6 reads + the 8 writes, Global Constraints order).
- `TOOL_CALLS` unchanged (reads only). Add new check functions:
  - **`tool annotations`** — from `tools/list`, every read has `annotations.readOnlyHint` true; every write false; `destructiveHint` true exactly on `reject_registration`, `reject_room_change`, `delete_room`.
  - **`room ids in list_rooms`** — parse `list_rooms` text; every item has an `id` matching a uuid regex (skip if the list is empty).
  - **`write round-trip`** (self-cleaning, block `ZZT`, number `MCP-<rand>`): `create_room` (floor 9, capacity 2, male) → JSON with `id`; duplicate create → text contains `already exists`; `update_room` capacity 3 → JSON `capacity` 3; `list_rooms {block:"ZZT"}` contains the number with `id`; `delete_room` → `deleted` true; list again → absent.
  - **`write negative probes`** — `reject_registration` (random uuid, reason `"   "`) → starts `Invalid request:`; `delete_room` (random uuid) → contains `Room not found`.
  - **`write gate`** — via direct REST as admin (`mcp_set_writes_enabled false`): `create_room` → starts `Writing is currently disabled.`; re-enable (`true`) and read back `mcp_get_settings` → true. Always re-enable even if a probe fails.
  - **`audit outcomes`** — direct REST `mcp_list_audit {p_limit: 20}` → contains the round-trip tool names with `ok: true` and at least one `ok: false` row from the gate probe.
- New stdlib helpers: `load_env()` (parse `mcp/.env` keys `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`; never print values), `admin_token(env)`, `admin_rpc(env, fn, params)` (reuse the existing `Client`). Insert the new checks in `main` **before** `check_rate_limit` (rate-limit window).

- [ ] **Step 2: Red run against current prod**

Run: `& "mcp\.venv\Scripts\python.exe" "mcp-worker\scripts\verify_remote.py" https://residence-mcp.anes4tlm.workers.dev`
Expected: existing checks PASS; new tool-list/annotation/write checks FAIL (old deploy). Exit non-zero — that is the red state proving the checks bite.

- [ ] **Step 3: Deferred commit**

`git add mcp-worker/scripts/verify_remote.py`
Message: `test(worker): extend prod acceptance with write tools, gate and audit checks`

---

### Task 7: Deploy and verify in production

**Files:** none (deploy only)

**Interfaces:**
- Consumes: Tasks 4–6.
- Produces: the deployed Worker + a fully green acceptance run (the evidence Task 9 records).

- [ ] **Step 1: Pre-flight**

In `mcp-worker/`: `npm test` → all pass; `npm run typecheck` → clean; `npx wrangler deploy --dry-run` → succeeds.

- [ ] **Step 2: Deploy**

Run: `npx wrangler deploy` → note the new version id.

- [ ] **Step 3: Prod acceptance**

Run: `& "mcp\.venv\Scripts\python.exe" "mcp-worker\scripts\verify_remote.py" https://residence-mcp.anes4tlm.workers.dev`
Expected: every line PASS, `SUMMARY: <N> passed, 0 failed, 0 skipped` (rate-limit may SKIP — it did before; anything else must be PASS).

- [ ] **Step 4: Stability re-run**

Run the same command once more → same summary. Record both summaries + the deploy version id as evidence.

- [ ] **Step 5: No commit** (nothing changed on disk in this task)

---

### Task 8: Desktop Settings off-switch

**Files:**
- Modify: `desktop/app/ui/pages/settings.py`
- Modify: `%TEMP%\opencode\settings_smoke.py` (session helper, not in the repo)

**Interfaces:**
- Consumes: `mcp_get_settings` / `mcp_set_writes_enabled` (Task 3) via the page's existing `self.client`; existing role gating.
- Produces: `self.writes_checkbox` ("Allow ChatGPT to change data") + `_on_writes_toggled()` + load-in-`reload()`. Visible for admins without Developer mode.

- [ ] **Step 1: Add the checkbox**

In `SettingsPage.__init__` (ADVANCED SETTINGS card, after `self.enable_note`): create `self.writes_checkbox = QCheckBox("Allow ChatGPT to change data")` with `CHECKBOX_QSS`, connect `toggled` → `self._on_writes_toggled`; add `self.writes_note = QLabel("ChatGPT asks you to confirm every change first. Turn this off to make ChatGPT read-only again.")` with `MUTED_QSS`. In the role-gating block (around lines 177–183): `self.writes_checkbox.setVisible(self.role == "admin")` and same for `writes_note`; also `self.writes_checkbox.setEnabled(False)` until loaded. Add `self._writes_loading = False` state.

- [ ] **Step 2: Behavior**

- `reload()` (admin only): rpc `mcp_get_settings`; `_writes_loading` guard while setting `setChecked(writes_enabled)` via `blockSignals`; success → enable the checkbox; failure → disabled + note text `Could not load this setting — check the connection.`
- `_on_writes_toggled(checked)`: ignore when `_writes_loading` or role != admin; rpc `mcp_set_writes_enabled {p_enabled: checked}`; on exception → revert with `blockSignals` + `QMessageBox.warning(self, "Settings", "Could not save the setting: ...")`; on success → keep state.

- [ ] **Step 3: Copy**

Footer (line ~313) → `"Admin-only. ChatGPT can read data, and — when you allow it here — make changes: it asks you to confirm every change first, and every action is logged. Full guides: mcp-worker/README.md (hosted) and mcp/README.md (local)."`

- [ ] **Step 4: Smoke test**

Read `%TEMP%\opencode\settings_smoke.py` and add checks in its style: (a) checkbox + note visible for admin with dev mode OFF; (b) hidden for staff; (c) initial state matches `mcp_get_settings`; (d) toggling off → read-back `false`, toggling on → read-back `true` (restore original at the end). Run: `& "desktop\.venv\Scripts\python.exe" "%TEMP%\opencode\settings_smoke.py"` → all PASS.

- [ ] **Step 5: Screenshot**

Run the hosted shots helper (`%TEMP%\opencode\settings_shots_hosted.py`, extended if needed) → `%TEMP%\opencode\shots\settings_writes.png` showing the new checkbox.

- [ ] **Step 6: Deferred commit**

`git add desktop/app/ui/pages/settings.py`
Message: `feat(desktop): ChatGPT write off-switch in Settings`

---

### Task 9: Documentation and handoff

**Files:**
- Modify: `mcp-worker/README.md`, `mcp/README.md`, `README.md`, `docs/manual-test-mcp.md`, `docs/mcp-handoff.md`, `mcp-worker/package.json`, `docs/superpowers/plans/2026-10-16-mcp-write-tools.md` (this file, status line)

**Interfaces:**
- Consumes: all shipped evidence (deploy version, verify summaries, smoke counts).
- Produces: the docs the admin reads next (how to flip the switch, how to test, what changed).

- [ ] **Step 1: `mcp-worker/README.md`** — intro "six read-only" → 14 tools (6 read + 8 write); add a "Write tools" section (names/args table, confirmation + gate behavior, exact messages, annotations, two-phase audit semantics); update Verify section with the new script summary expectations; keep secrets section untouched.

- [ ] **Step 2: `mcp/README.md`** — scope "strictly read-only" to the local server; hosted row now reads "read + admin-confirmed writes (14 tools)"; note the local server stays read-only by design; tools section gains one line pointing at `mcp-worker/README.md` for writes.

- [ ] **Step 3: Root `README.md`** — §"Ask ChatGPT (MCP)": read-only wording → "read-only by default; admin-confirmed changes can be enabled from the desktop Settings".

- [ ] **Step 4: `docs/manual-test-mcp.md`** — add to section A: Refresh after deploy picks up 14 tools; try "create a test room 999 in block Z with 2 places" → ChatGPT asks for confirmation → room appears in the desktop Rooms page; "delete that test room"; flip the off-switch in Settings → a write attempt is refused; audit row shows ok. Update the notes paragraph (both-servers-read-only → hosted can write when enabled; local stays read-only).

- [ ] **Step 5: `docs/mcp-handoff.md`** — append a "Session 4 — write tools" record: what shipped, evidence (migration self-tests, verify summaries ×2, smoke counts, screenshot path), the admin's remaining step (Refresh once in ChatGPT), and the still-uncommitted status.

- [ ] **Step 6: `mcp-worker/package.json`** — description → `Residence Tlemcen admin MCP server (6 read + 8 admin-confirmed write tools) on Cloudflare Workers`.

- [ ] **Step 7: Status line** — append `Status: COMPLETED (2026-10-16)` to the bottom of this plan file.

- [ ] **Step 8: Deferred commit**

`git add mcp-worker/README.md mcp/README.md README.md docs/manual-test-mcp.md docs/mcp-handoff.md mcp-worker/package.json docs/superpowers/plans/2026-10-16-mcp-write-tools.md docs/superpowers/specs/2026-10-15-mcp-write-tools-design.md`
Message: `docs: MCP write tools (READMEs, manual test checklist, handoff)`

Status: COMPLETED (2026-10-16)
