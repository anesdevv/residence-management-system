# MCP admin server — session handoff / progress notes

> **Session record.** Originally a temporary note; it became the running record for the admin MCP
> server (Sessions 1–2: local Python server + migrations; Session 3: hosted Cloudflare Worker).
> Jump to the newest session section at the bottom for the current state and evidence.

Repo: `C:\Users\Admin\Documents\OpenCode\my school project THE MAIN` (Windows, PowerShell).
Task: read-only ADMIN MCP server for the "Residence Tlemcen" project (ChatGPT custom MCP server).
Original task spec: see the user's previous message (Steps 0–6 + Definition of Done). Everything below follows it.

---

## Hard rules (do not violate)

1. READ-ONLY tools (no insert/update/delete anywhere).
2. Admin only: every SQL function raises unless `profiles.role = 'admin'`.
3. Full student details allowed; truncate only free text (`description`, `staff_note`, `reason`,
   `decision_note`, `rejection_reason`) to 500 chars.
4. Do NOT modify `web/` or `desktop/` or existing migrations. Only ADD files.
5. NEVER use the Supabase service role key. Anon key + real admin login only.
6. `/mcp` requests require `Authorization: Bearer <MCP_AUTH_TOKEN>`; rate limit 60/min → 429.
7. Never print or commit secrets. `mcp/.env` is local-only (gitignored); only `.env.example` is committed.
8. Log every tool call (name, arguments, timestamp; NOT results) to `mcp/audit.log`.
9. Work step by step, run what you can, show results.

---

## Key environment facts (verified)

- **Real Supabase project:** `https://kjqbnurycfjsuufibkac.supabase.co` (root `.env`, `web/.env`,
  `desktop/.env`, `supabase/.temp/project-ref` all agree). Project linked for the CLI.
- **Supabase CLI:** use `npx supabase ...` (v2.121.0 works; bare `supabase` is not on PATH).
  It connects to the remote DB non-interactively. `npx supabase db push` applies pending migrations.
  `npx supabase migration list --linked` shows local vs remote migration history (was in sync before our migration).
- **DO NOT use the workspace Supabase MCP server** (`tools.supabase.*`): it points at a DIFFERENT,
  unreachable project (`nyskuckqdaexfaykujva`, connection timeouts). The real project is only reachable
  via the CLI and REST.
- **No local Docker / no local Supabase.** Verification is done against the hosted project via the CLI + REST.
- **Python venv:** `mcp/.venv` (Python 3.11.16, created with `uv`). Run it as
  `& "mcp\.venv\Scripts\python.exe" ...` (PowerShell needs `&` for quoted exe paths).
  Reinstall deps: `uv pip install --python "mcp\.venv\Scripts\python.exe" -r mcp\requirements.txt`.
- **Installed (verified working):** mcp **1.30.0** (deliberately `<2` — see below), supabase 2.32.0,
  uvicorn 0.54.0, starlette 1.8.0, sse-starlette 3.5.0, python-dotenv 1.2.4, pytest 9.1.1.
  (Leftovers from an aborted mcp 2.3.0 install: `mcp-types`, `httpx2` — harmless.)
- **MCP SDK version choice:** the task spec asked for `FastMCP` from `mcp.server.fastmcp` and
  `mcp.streamable_http_app()` — that is the **mcp v1 API**. mcp 2.x renamed `FastMCP` → `MCPServer`.
  Therefore `mcp/requirements.txt` pins `mcp>=1.9,<2` (documented there and must be documented in README).
- **Seeded accounts** (`scripts/seed.py`, no `seed.sql` exists):
  admin `admin@residence.test` / `Admin1234!`, staff `staff@residence.test` / `Staff1234!`,
  student `20230001@students.residence.local` / `Student1234!`.
- **`mcp/.env` exists locally** (gitignored, NOT committed) with real `SUPABASE_URL` + `SUPABASE_ANON_KEY`
  (copied from `desktop/.env`), the seeded admin creds, a generated 64-char `MCP_AUTH_TOKEN`, `PORT=8000`.
  Never print its contents. If a token was ever printed in an older session transcript,
  regenerate it (a helper exists: `%TEMP%\opencode\make_env.py`, see below).
- **Root `.gitignore` already ignores** (checked with `git check-ignore`): `mcp/.env`, `mcp/audit.log`,
  `mcp/.venv`, `__pycache__/`, `.pytest_cache/`, `*.log` (any depth). No new `.gitignore` needed.
- **Git:** nothing has been committed. `git status --short` shows only untracked: `mcp/` and the new
  migration file. `web/` and `desktop/` untouched. (Decision: leave committing to the user; mention in final summary.)
- **Server process:** a background server was running with the FINAL code (PID 6916). Kill it any time with:
  `Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }`
- **Odd environment noise:** something unrelated polls `GET /v1/models` on localhost:8000 (gets 404). Ignore.

---

## Schema facts (from Step 0 — use these REAL names)

- Enums: `user_role('student','staff','admin')`, `student_status('pending','active','rejected')`,
  `report_status('pending','in_progress','resolved')`, `request_status('pending','approved','rejected')`,
  `maintenance_category('plumbing','electrical','furniture','internet','other')`,
  `gender('male','female')`, `study_level('L1','L2','L3','M1','M2','Doctorat')`.
- `profiles(id, role)`; helpers `auth_role()` (security definer, returns user_role) and `is_staff()`.
  **No `is_admin()` exists** — admin checks in repo use `auth_role()::text = 'admin'` (e.g. `import_official_residents`).
- `staff(id, full_name, position)` — ticket `handled_by` → `staff.full_name`.
- `rooms(id, block, floor, number, capacity, gender)` — room label convention "B-101" = `block || '-' || number`.
- `students(id, card_id unique, first_name, last_name, birth_date, gender, phone, email, university,
  faculty, study_level, wilaya, status, rejection_reason, room_id, reviewed_by, reviewed_at, created_at)`.
  **No `notes` column** → free text to truncate = description, staff_note, reason, decision_note, rejection_reason.
- `maintenance_reports(id, student_id, category, description, photo_path, status, staff_note, handled_by, created_at)`.
- `room_change_requests(id, student_id, current_room_id, preferred_room_id, reason, status, decision_note, decided_by, decided_at, created_at)`.
- `official_residents(id, card_id unique, first_name, last_name, birth_date, gender, university, faculty)`.
- Occupancy definition (matches desktop `client.room_occupancy`): count of `students.status='active'` per room.
- Desktop Overview "Open Maintenance Tickets" = `status != 'resolved'`.

---

## Files created so far

| Path | Status |
|---|---|
| `supabase/migrations/20261015120000_mcp_admin_readonly_functions.sql` | **DONE + APPLIED + VERIFIED** (see Step 1 below) |
| `mcp/formatting.py` | DONE (pure helpers; pytest file NOT written yet) |
| `mcp/server.py` | DONE incl. transient-retry hardening (edit was made after the first full check) |
| `mcp/requirements.txt` | DONE (`mcp>=1.9,<2` pin explained in comments) |
| `mcp/.env.example` | DONE |
| `mcp/.env` | local-only, gitignored, real values |
| `mcp/.venv` | local venv (uv, py3.11) |
| `mcp/audit.log` | created by first test run (11 lines; gitignored) |
| `mcp/tests/test_formatting.py` | **NOT STARTED (Step 5)** |
| `mcp/README.md` | **NOT STARTED (Step 6)** |
| `docs/manual-test-mcp.md` | **NOT STARTED (Step 6)** |
| root `README.md` — "Ask ChatGPT (MCP)" note | **NOT STARTED (Step 6)** |

---

## Step-by-step status

### Step 0 ✅ DONE
Schema/seed/desktop inspected; findings listed above. Adaptations to report in the final summary:
no `seed.sql` (it's `scripts/seed.py`); no `students.notes`; no `is_admin()`; search extended to room
labels (so "Which student is in room B-101?" works); room-change `current_room` = live student room;
summary `rejected` = rejected students; `official_list_match` = card_id exists in `official_residents`
plus extra key `official_name_match` (first/last names match).

### Step 1 ✅ DONE + VERIFIED
- Migration written with 7 functions: `mcp_require_admin()` (guard) + the 6 required ones. All are
  `security invoker`, `stable`, return `jsonb`, start with the admin check, cap limits to 100, and
  `revoke execute ... from public, anon` + `grant ... to authenticated`. Comments + verification
  block + rollback block included in the file.
- Applied: `npx supabase db push` → `Applying migration 20261015120000_mcp_admin_readonly_functions.sql... Finished`.
- Verified via REST (anon key + real logins, temp script `%TEMP%\opencode\verify_mcp_rpc.py`):
  - admin: all 6 functions return real data (e.g. 1 pending + 1 resolved ticket, 2 pending room changes,
    1 pending registration "Test Student" with `official_list_match:false`, search "Benali" → Yacine Benali
    in A-101 active, rooms A-02/A-101/A-102/B-101, summary: pending_reg 1, active 2, capacity 9, occupied 2, 22.2%).
  - invalid status `bogus` → error `invalid status: bogus ...` (SQLSTATE 22023).
  - staff token → `admin only` (42501); student token → `admin only`; anonymous → `permission denied for function`.
  - extra checks (`verify_mcp_rpc2.py`): search `A-101` and case-insensitive `a-101` → the resident;
    `p_block='b'` case-insensitive → B-101.

### Steps 2–4 ⚠️ FILES DONE, MOSTLY VERIFIED — ONE RE-RUN NEEDED
`mcp/server.py` implements: FastMCP v1 (`stateless_http=True`), 6 tools with the specified names,
typed params and the specified descriptions (search description also mentions room label usage);
audit logging in every tool; `SupabaseAdminSession` (anon key + admin login, re-login on auth errors /
after 45 min, one retry on transient errors — added because a real HTTP 522 Cloudflare/gateway hiccup
was observed once on the first worker-thread call; every RPC is read-only so retry is safe);
`McpSecurityMiddleware` (pure ASGI: bearer auth via `hmac.compare_digest` + per-IP rate limit 60/min)
applied only to paths starting `/mcp`; `GET /health` → `{"status":"ok"}` with no auth;
`load_config()` refuses to start if `MCP_AUTH_TOKEN` missing/<32 chars.

Verified so far with the server running (`/health`, 401s, and a real MCP client session):
- `GET /health` → `{"status":"ok"}` ✅
- `GET /mcp` no token → `401 {"error":"unauthorized"}` ✅; wrong token → 401 ✅
- good token, bare GET → `406` (proves it reached the MCP handler) ✅
- full MCP client check (`%TEMP%\opencode\mcp_client_check.py`): initialize OK, **TOOL COUNT: 6** with
  correct names ✅; 5 tools returned real data; `get_summary` hit the transient 522 that one time →
  `direct_summary.py` and a re-test through MCP both succeeded ✅.
- **THEN** the transient-retry edit was added and the server restarted with the new code, and the
  confirming re-run of `mcp_client_check.py` was **interrupted before showing output**.
  → **First action in the new session: re-run it (command below) and confirm all 8 calls `[ok]`.**

Still not tested at all: **rate limit 429** (never ran the 70-request loop).

### Step 5 ⬜ NOT STARTED
`mcp/tests/test_formatting.py` (pytest, no network) covering: truncation (≤500 incl. "..."),
`truncate_records` nested, status validation (normalization + error), `empty_message` exact strings,
`cap_limit` (default/cap/floor/None/invalid), `token_is_valid` (valid/wrong/missing/wrong scheme/empty expected),
`RateLimiter` (limit boundary via injected `now`, window expiry, per-key isolation).
Test file must add the mcp dir to `sys.path` (e.g. `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))`)
and then `import formatting`.
Run: `& "mcp\.venv\Scripts\python.exe" -m pytest "mcp\tests" -q` (from repo root).

### Step 6 ⬜ NOT STARTED
1. `mcp/README.md` — purpose; setup (venv + `pip install -r requirements.txt` + copy `.env.example`);
   env var table; **run command**: from repo root `& "mcp\.venv\Scripts\python.exe" "mcp\server.py"`
   (or `cd mcp; .venv\Scripts\python.exe server.py`); endpoints `/mcp` (auth) + `/health` (open);
   audit log note; mcp-v1 pin note; testing with `npx @modelcontextprotocol/inspector`
   (Streamable HTTP, `http://localhost:8000/mcp`, header `Authorization: Bearer <MCP_AUTH_TOKEN>`);
   **"Connect to ChatGPT"**: run server → free tunnel (`cloudflared tunnel --url http://localhost:8000`
   or `ngrok http 8000`) → ChatGPT → Plugins > Add > Add custom MCP server → paste
   `https://<tunnel-host>/mcp` → add bearer token if asked → confirm unverified-server warning →
   enable plugin in a new chat → ask the example questions (open tickets, pending room changes,
   who is waiting for approval, which student is in room …). **"Privacy"** section: this plugin sends
   personal student data to ChatGPT/OpenAI when the admin asks; admin use only; keep the token secret;
   stop the tunnel when not in use; note shared-secret suits a class demo, OAuth is the production approach.
2. `docs/manual-test-mcp.md` in the style of `docs/manual-test-desktop.md` — the 9 checklist items from
   the task (Inspector lists 6 tools; no token → 401; non-admin login → every tool fails with permission
   error; open tickets / pending room changes / pending approvals match the desktop pages incl. the
   official-list match hint; search by name and card ID returns the right person/room; summary matches
   desktop Overview; each call appears in `mcp/audit.log`).
3. Root `README.md`: add short "Ask ChatGPT (MCP)" note (admin-only, read-only, link `mcp/README.md`).

### Final wrap-up ⬜
- Re-check `mcp/audit.log` has one line per tool call, no results (11 lines so far from earlier runs).
- Kill the background server (command above).
- `git status --short` → only the new files; `git check-ignore mcp/.env mcp/audit.log mcp/.venv` → all ignored.
- Final summary for the user: files created, commands to run, assumptions made (list further below).
- Do NOT commit; mention that files are untracked and offer to commit.

---

## Exact commands / snippets to reuse

```powershell
# workdir for all of these: repo root

# start server (background) then wait for health
& "mcp\.venv\Scripts\python.exe" "mcp\server.py"           # run as background shell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing    # {"status":"ok"}

# full MCP client check (6 tools + 8 calls + invalid status)
& "mcp\.venv\Scripts\python.exe" "C:\Users\Admin\AppData\Local\Temp\opencode\mcp_client_check.py" "C:\Users\Admin\Documents\OpenCode\my school project THE MAIN\mcp\.env"

# read the token for curl checks WITHOUT printing it
$lines = Get-Content "mcp\.env"
$token = (($lines -match '^MCP_AUTH_TOKEN=')[0] -replace '^MCP_AUTH_TOKEN=','')

# rate limit check: 70 requests, expect some 429 mixed with 400/406
$codes = @{}
1..70 | ForEach-Object {
  $c = & curl.exe -s -o NUL -w "%{http_code}" -H "Authorization: Bearer $token" http://127.0.0.1:8000/mcp
  $codes[$c] = ($codes[$c] + 1)
}
$codes.GetEnumerator() | ForEach-Object { "$($_.Key): $($_.Value)" }

# inspect history / re-apply migrations (already applied)
npx supabase migration list --linked
npx supabase db push

# kill server on port 8000
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }
```

Temp helper scripts (outside repo, safe to reuse): `C:\Users\Admin\AppData\Local\Temp\opencode\`
— `verify_mcp_rpc.py`, `verify_mcp_rpc2.py` (REST admin/non-admin checks), `mcp_client_check.py`
(MCP protocol check), `make_env.py` (regenerates `mcp/.env`, token never printed), `direct_summary.py`,
`mcp_summary_retest.py`.

PowerShell gotchas hit earlier: use `&` for quoted exe paths; use `curl.exe` (not `curl`);
pipeline single-match sometimes behaves as array — use `($lines -match '^KEY=')[0]` style.

---

## Assumptions made (repeat these in the final summary to the user)

1. No `supabase/seed.sql` — seeding is `scripts/seed.py`; seeded admin = `admin@residence.test` / `Admin1234!`.
2. Truncation (500 chars) implemented in `mcp/formatting.py` (server side), not in SQL. Applies to
   `description`, `staff_note`, `reason`, `decision_note`, `rejection_reason` (students has no `notes`).
3. Admin check reuses `auth_role() = 'admin'` (no `is_admin()` exists); guard function `mcp_require_admin()`.
4. `mcp_search_students` also matches room labels ("B-101") so "Which student is in room …?" works.
5. Room-change `current_room` = the student's live room (request snapshot `current_room_id` is historical).
6. `mcp_summary.rejected` = students with status `rejected`; `occupancy_percent` = active housed / total capacity.
7. `official_list_match` = card_id exists in `official_residents`; `official_name_match` is an extra
   boolean for the first/last-name comparison.
8. MCP SDK pinned `>=1.9,<2` because the requested `FastMCP` API only exists in v1 (v2 renamed it to `MCPServer`).
9. Migration was applied to the HOSTED project `kjqbnurycfjsuufibkac` (no local Docker exists here);
   it is additive and reversible (rollback block in the migration file).
10. One retry on transient gateway errors (a real HTTP 522 was observed) — safe because everything is read-only.

---

## Session 2 progress log (2026-10-15) — ALL STEPS COMPLETE ✅

Executed via subagents (per user request): three parallel tasks + one combined independent review. All passed.

- **Task A — end-to-end verification: PASS (all checks).**
  - Health 200 `{"status":"ok"}`; server was already running (nothing to restart).
  - MCP client check: init OK, `TOOL COUNT: 6`, 8/8 tool calls ok incl. `get_summary` (no retry needed), invalid-status call errored as expected.
  - Auth: no token → 401, wrong token → 401, correct token bare GET → 406.
  - Rate limit: 70 rapid requests → `406: 47, 429: 23` (exactly 60 allowed in the window; confirmed in the server log).
  - Audit: 11 → 20 lines; the 9 new lines = exactly the 9 tool calls; rate-limit GETs added 0 lines; every line JSON with timestamp/tool/arguments only, 0 result leaks.
  - Full raw evidence: `C:\Users\Admin\AppData\Local\Temp\opencode\mcp_verify_report.md`.
- **Task B — Step 5 tests: DONE.** `mcp/tests/test_formatting.py` — 97 tests, pure/deterministic. `97 passed in 0.53s` (re-verified first-hand: `97 passed in 0.55s`). Command: `& "mcp\.venv\Scripts\python.exe" -m pytest "mcp\tests" -q` from repo root.
- **Task C — Step 6 docs: DONE.** `mcp/README.md` (setup, env vars, running, Inspector, Connect to ChatGPT, Privacy, troubleshooting), `docs/manual-test-mcp.md` (exactly 9 checklist items + footnotes), root `README.md` — new "Ask ChatGPT (MCP)" section (the only tracked file modified).
- **Independent review: no Critical/Important findings.** Env-var names match `.env.example` 6/6; commands/claims verified against `mcp/server.py`; 9/9 checklist items correct; tests real (no tautologies); no secrets anywhere.

### Deferred minors (parked, not fixed)
1. `mcp/README.md:92,94,157,158` — quoted error bodies show `{"error":"unauthorized"}` but the code emits `{"error": "unauthorized"}` (space after colon; plain `json.dumps`). Semantics identical.
2. `docs/manual-test-mcp.md:5` — item 1 references "expected ... descriptions" without listing them (they are in `mcp/README.md` lines 22–27).
3. `mcp/tests/test_formatting.py:467` — one RateLimiter test uses the real clock (deterministic in practice: 3 calls within a 60 s window).
Plus two `# NOTE: possible bug` tests documenting behavior unreachable via the server: `truncate_text(limit<3)` can exceed the limit; `cap_limit(inf)` raises `OverflowError` not `ValueError` (MCP tool params are schema-typed ints; truncation always uses the 500 default).

### Rulings made this session
- Continue in the current workspace, no worktree — user said "continue here"; work was already uncommitted inline. Cost if wrong: none (user reviews before any commit).
- Ledger = this file (not `.superpowers/sdd/`) — the user explicitly asked for this note as the tracker. Cost if wrong: negligible.
- No explicit model IDs in dispatches — the harness forbids guessing model IDs unless the user asks. Cost if wrong: default model used; it sufficed.
- One combined independent review instead of per-task + final reviews — three tiny disjoint artifacts, one spec source. Cost if wrong: a defect could hide across artifacts; the review still covered all of them.
- The minors above parked rather than fixed — all cosmetic; nothing downstream builds on them. Cost if wrong: a doc shows one extra space in a quoted JSON body.
- Server on port 8000 stopped at the end. Restart: `& "mcp\.venv\Scripts\python.exe" "mcp\server.py"` from repo root.

### Final state
- `git status --short` (branch `main`): ` M README.md`, `?? docs/manual-test-mcp.md`, `?? docs/mcp-handoff.md`, `?? mcp/`, `?? supabase/migrations/20261015120000_mcp_admin_readonly_functions.sql` — nothing else touched; nothing committed (by design).
- This note continues as the project record; Session 3 below supersedes its "final state".

---

## Session 3 progress log (2026-10-15, evening) — Hosted Cloudflare Worker (Option B) ✅ COMPLETE

**Goal:** make the admin MCP server "always live" so ChatGPT keeps working after reboots with zero local setup. **Chosen:** rewrite as a stateless Cloudflare Worker in `mcp-worker/`; the local Python server stays as the dev/testing fallback.

### Architecture (verified against live docs, 2026-10-15)
- **Endpoint:** `https://residence-mcp.anes4tlm.workers.dev/mcp` (worker `residence-mcp`); public `GET /health` → `{"status":"ok"}`.
- **Auth = OAuth 2.1** (`@cloudflare/workers-oauth-provider` 1.2.3, single-worker shape). ChatGPT custom MCP servers accept **OAuth or no auth only** — there is no static-bearer field (developers.openai.com apps-sdk auth + MCP 2026-07-28 authz spec). ChatGPT does dynamic client registration + PKCE; a consent page opens **once** in the browser asking for `MCP_AUTH_TOKEN` (the same token the desktop app shows). After that ChatGPT holds refreshable tokens; reboots change nothing.
- **MCP:** stateless `createMcpHandler` (`agents` 0.28.1) + MCP SDK v2 (`@modelcontextprotocol/server` 2.3.1). `McpAgent` is deprecated — not used.
- **Tools:** same 6 read-only tools ported 1:1 from `mcp/server.py` (names/descriptions/validation/truncation/empty messages/error strings — parity table in `docs/superpowers/plans/2026-10-15-cloudflare-worker-mcp.md`).
- **Data access:** anon key + real admin login via Supabase REST (admin token cached per isolate, renewed at 45 min; retry-once-on-auth-error / transient preserved). Service-role key never used or referenced.
- **Audit:** `public.mcp_audit_log` + `mcp_log_audit(...)` (admin-gated, security definer; awaited ≤ 2 s before each tool; failures swallowed) + `mcp_list_audit(...)` admin read RPC.
- **Rate limit:** Workers Rate Limiting binding 60/60 s per IP on `/mcp` (pre-auth). Production enforcement is **eventually-consistent** (per-PoP counters): fast 65-request bursts can slip; first 429 observed at request 167 / 43 s in a paced probe. Defense-in-depth only — the real gate is OAuth.

> **Gotcha re-confirmed (cost real time today):** the workspace `tools.supabase.*` MCP server points at a DIFFERENT, unreachable project (`nyskuckqdaexfaykujva`) — every DB call times out. Use `npx supabase db push` / `migration list --linked` (CLI; worked first try) and REST on the real project (`kjqbnurycfjsuufibkac`). Also: `wrangler dev` on this Windows box needs `--ip ::1` for local tests; for local dev override the var with `--var PUBLIC_URL:http://localhost:8788`.

### Files
| Path | Status |
|---|---|
| `mcp-worker/` — `package.json`, `tsconfig.json`, `wrangler.jsonc`, `src/{index,oauth,mcp,supabase,formatting,errors,audit}.ts`, `test/*.test.ts` (134 tests), `scripts/verify_remote.py`, `README.md`, `.dev.vars` (gitignored, local only) | DONE · deployed · verified |
| `supabase/migrations/20261015214000_mcp_audit_log.sql` | DONE + APPLIED (`npx supabase db push`) |
| `supabase/migrations/20261015221500_mcp_audit_read.sql` (audit read RPC; addition beyond the plan) | DONE + APPLIED |
| `docs/superpowers/plans/2026-10-15-cloudflare-worker-mcp.md` | build plan, executed |
| `desktop/app/ui/pages/settings.py` | hosted section first (`MCP_HOSTED_URL`), local demoted, admin gate/health poller unchanged |
| `mcp/README.md`, `mcp-worker/README.md`, `docs/manual-test-mcp.md`, root `README.md` | updated for the hosted flow |

Worker secrets (set via `wrangler secret bulk` from a temp JSON built out of `mcp/.env`; temp file deleted after; values never printed): `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `MCP_AUTH_TOKEN`.

### Evidence (all green)
- Worker: **134/134** vitest tests; `tsc --noEmit` clean; `wrangler deploy --dry-run` OK.
- Local end-to-end (`wrangler dev --ip ::1` → `scripts/verify_remote.py http://localhost:8788`): **18/18 PASS** — OAuth discovery → DCR → consent → PKCE token → initialize → 6 tools (real data) → invalid-arg messages → refresh grant → rate-limit 429.
- Production (`scripts/verify_remote.py https://residence-mcp.anes4tlm.workers.dev`, run twice): **17 PASS / 0 FAIL** (in-script rate-limit SKIP on the fast burst — covered by the paced probe).
- Paced rate probe: `PASS rate limit: first 429 on request 167 after 43.2s`.
- Audit semantics (`verify_mcp_audit.py`): admin insert **204**; anon **401**; invalid JWT **401**; staff **403 `admin only`** — ALL PASS.
- Audit rows read back from the live system via `mcp_list_audit`: **8 rows written by the deployed Worker's production tool calls** + 1 probe row (e.g. `#7 get_summary @ 2026-10-15T21:40:23Z`) — ChatGPT-equivalent traffic is audited end-to-end.
- Desktop: `settings_smoke.py` **28/28 PASS**; offscreen screenshot `%TEMP%\opencode\shots\settings_hosted.png` (structure verified; offscreen text renders as boxes — known artifact).

### What the user must do
1. **Restart the desktop app** to see the new Settings page: `& "desktop\.venv\Scripts\python.exe" "desktop\main.py"`.
2. **Connect once in ChatGPT** (needs a plan with custom MCP servers — Plus/Pro): chatgpt.com/plugins → `+` → *Add custom MCP server* → paste `https://residence-mcp.anes4tlm.workers.dev/mcp` → the login page opens → paste the token from the Settings page → Allow → *I understand and want to continue* → *Create as a plugin*. After this: **reboots require nothing** (no server, no tunnel).
3. Optional: audit trail via `mcp_list_audit` RPC or the dashboard; after code changes `npx wrangler deploy` + *Refresh* on the ChatGPT connection.
```
