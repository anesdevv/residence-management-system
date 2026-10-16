# Cloudflare Worker MCP Server — Implementation Plan

**Date:** 2026-10-15
**Status:** ✅ COMPLETED 2026-10-15 — see `docs/mcp-handoff.md` §Session 3 for the full evidence trail. Deviations from this plan as written: (1) consent flow calls `parseAuthRequest`/`completeAuthorization` directly (the `beginConsent`/`approveConsent` helpers set an always-Secure cookie that breaks plain-http local verification); (2) an admin **read** RPC `mcp_list_audit` was added (`supabase/migrations/20261015221500_mcp_audit_read.sql`) beyond the plan's "skip read RPC" note, for audit visibility + verification; (3) production rate limiting is eventually-consistent (per-PoP counters) — verified working via a paced probe (first 429 at request 167/43 s).
**Executor:** fresh-context subagents (subagent-driven development); every task below is self-contained.
**Reference implementation:** `mcp/` (local Python server) — its behavior is the parity source of truth.
**Related docs:** `docs/mcp-handoff.md`, `docs/manual-test-mcp.md`.

---

## 1. Goal

Replace the laptop-bound MCP server (Python + quick tunnel) with an **always-on Cloudflare Worker** at a permanent HTTPS URL, so the user connects ChatGPT **once** and never repeats local setup — including after reboots. The local Python server is kept as a developer/testing fallback. Behavior stays identical: 6 read-only admin tools, token-gated, rate-limited, audit trail.

## 2. Why the architecture includes OAuth (verified against live docs, 2026-10-15)

- OpenAI now expects **OAuth 2.1** for authenticated MCP servers — there is no static-bearer-token field for ChatGPT custom MCP servers (`developers.openai.com/apps-sdk/build/auth`, `developers.openai.com/plugins/deploy/connect-chatgpt`, MCP authz spec `2026-07-28`). So the Worker must be an OAuth provider.
- Cloudflare's current recipe: **stateless** MCP via `createMcpHandler` (from the `agents` package) + `McpServer` from **`@modelcontextprotocol/server`** (MCP SDK v2). `McpAgent` is deprecated — do not use it. (`developers.cloudflare.com/agents/model-context-protocol/...`)
- OAuth via **`@cloudflare/workers-oauth-provider`**, single-worker `OAuthProvider` shape; the user's existing `MCP_AUTH_TOKEN` becomes the password on our tiny consent page ("sign in" happens once; ChatGPT then holds refreshable OAuth tokens, never the raw secret).
- **Every API detail below is a fixed behavior**, but the exact function signatures/options of the three libraries must be taken from the **installed package READMEs/types** (these packages move fast; installed truth wins over plan snippets; behavior/interfaces in this plan must not change).

## 3. Fixed interfaces & decisions

| # | Decision |
|---|----------|
| D1 | Worker name `residence-mcp` → permanent URL `https://residence-mcp.<account-subdomain>.workers.dev`; MCP endpoint **`/mcp`**; public **`/health`** returns `{"status":"ok"}` |
| D2 | Secrets on the Worker: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `MCP_AUTH_TOKEN` — all pushed from `mcp/.env` **without ever echoing values**. Same token as the desktop app shows. |
| D3 | Vars (plain, non-secret): `PUBLIC_URL` = deployed origin (set after first deploy, then redeploy) |
| D4 | Bindings: `OAUTH_KV` (KV namespace), `RATE_LIMITER` (rate-limit binding, **best-effort** — if the free plan rejects it at deploy, remove binding + guard code, document the gap) |
| D5 | Auth = OAuth only on `/mcp` (single path, no static-bearer bypass). OAuth endpoints `/authorize`, `/token`, `/register` + discovery served/coordinated per the installed `workers-oauth-provider` docs. Minimal scopes (e.g. `mcp:read`) granted at consent. Enable Client-ID-Metadata-Document support if the installed version offers it (ChatGPT-compatible), plus DCR for MCP Inspector. |
| D6 | Consent page: GET `/authorize` renders a small self-contained HTML form (no secrets, `Cache-Control: no-store`); POST checks the pasted token against `MCP_AUTH_TOKEN` with a **constant-time compare**; success → `completeAuthorization` + redirect; wrong token → 401 re-render with "Wrong token"; Deny handled per library docs. Token missing in env ⇒ always deny (fail closed). |
| D7 | Audit: new table `public.mcp_audit_log` + security-definer RPC `mcp_log_audit(p_tool text, p_args jsonb)`; Worker **awaits** it before each tool runs, max 2 s timeout, **all failures swallowed** (never fail a tool call). Records tool + args + timestamp only — never results, never tokens. |
| D8 | Rate limit: 60 req/min per client IP on `/mcp` (pre-auth), key = `CF-Connecting-IP`. 429 `{"error":"rate limit exceeded"}`. |
| D9 | Do **not** run `git add`/`git commit` — the user has a pending commit decision. Leave all work in the working tree. |
| D10 | Secrets discipline: never print, log, echo, or write secret values anywhere except `.dev.vars` (gitignored) / `wrangler secret bulk` stdin/file-that-is-deleted-after. Report them only as names. |
| D11 | Do not touch `web/`. Desktop changes limited to `desktop/app/ui/pages/settings.py` (plus the URL constant). Do not modify `mcp/` code — only its README. |
| D12 | Free tier only. Windows PowerShell conventions: `curl.exe` (not `curl`), `& "path\to.exe"`, `;` instead of `&&`. |

### Tool parity table (from `mcp/server.py` — exact)

| Tool | MCP args | SQL fn | SQL params | Empty-message entity / status / block |
|---|---|---|---|---|
| `list_maintenance_tickets` | `status?` (pending\|in_progress\|resolved), `limit=20` | `mcp_list_tickets` | `p_status`, `p_limit` | tickets / status / — |
| `list_room_change_requests` | `status?` (pending\|approved\|rejected), `limit=20` | `mcp_list_room_changes` | `p_status`, `p_limit` | room_changes / status / — |
| `list_pending_registrations` | `limit=20` | `mcp_list_pending_registrations` | `p_limit` | registrations / — / — |
| `search_students` | `query` (required), `limit=10` | `mcp_search_students` | `p_query`, `p_limit` | students / — / — |
| `list_rooms` | `block?`, `only_available=false` | `mcp_list_rooms` | `p_block`, `p_only_available` | rooms / — / block |
| `get_summary` | — | `mcp_summary` | — | — (non-empty expected) |

Tool descriptions: copy verbatim from `mcp/server.py` (lines ~246–328). Server name `Residence Tlemcen Admin` + the same `instructions` text.

### Formatting/behavior parity (from `mcp/formatting.py` — exact)

- `MAX_FREE_TEXT=500`; free-text fields: `description, staff_note, reason, decision_note, rejection_reason`; truncate adds `...`, result ≤ 500.
- `cap_limit`: default 20 (search_students 10), max 100, min 1; non-numeric (and booleans) → error "limit must be a number" → tool returns `Invalid request: limit must be a number`.
- `validate_status`: strip/lower; `-` and spaces → `_`; invalid → `invalid status 'x': expected one of ...` → `Invalid request: ...`.
- Empty messages: `No pending maintenance tickets found.` / `No in-progress ...` style — port `empty_message()` verbatim (labels: tickets="maintenance tickets", room_changes="room change requests", registrations="pending registrations", students="students matching your search", rooms="rooms").
- Results: recursively truncate free-text fields, then compact JSON (`ensure_ascii=False`, no spaces ≈ `JSON.stringify`). No data → `No data returned.`.
- Errors (`friendly_error`): "admin only"/"permission denied" → `Permission denied: this tool requires an administrator account (profiles.role = 'admin').`; "invalid status"/"query required" → `Invalid request: {msg}`; jwt/token/session/auth markers → `The server could not authenticate with Supabase. Check ADMIN_EMAIL / ADMIN_PASSWORD in mcp/.env.`; else `Error talking to Supabase: {msg}` (whitespace-collapsed, ≤300 chars).
- Supabase session: password grant with anon key; cache token in module scope; renew early (~45 min); retry once on auth error (relogin) and once on transient 5xx/network error; JWT/anon key never logged.
- `search_students` with blank query → `Invalid request: query is required (a name, card ID or room label such as 'B-101').`

## 4. Files (new / changed)

```
mcp-worker/
  package.json  package-lock.json  tsconfig.json  wrangler.jsonc
  .dev.vars                     (gitignored — local dev secrets only)
  src/index.ts                  OAuthProvider wiring + top-level fetch (rate limit)
  src/oauth.ts                  public handler: /health + /authorize consent UI
  src/mcp.ts                    createMcpHandler factory + McpServer + 6 tools
  src/supabase.ts               admin session (login cache, rpc, retries)
  src/formatting.ts             ported pure helpers (Section 3)
  src/errors.ts                 friendlyError mapping
  src/audit.ts                  mcp_log_audit caller (2 s timeout, swallow)
  test/formatting.test.ts  test/supabase.test.ts  test/errors.test.ts   (vitest)
  scripts/verify_remote.py      end-to-end acceptance script (stdlib-only)
  README.md                     deploy/ops doc for this worker
supabase/migrations/<ts>_mcp_audit_log.sql
docs/superpowers/plans/2026-10-15-cloudflare-worker-mcp.md   (this plan)
desktop/app/ui/pages/settings.py            (hosted section first; local demoted)
mcp/README.md  README.md                    (update primary flow)
docs/manual-test-mcp.md  docs/mcp-handoff.md (update)
.gitignore                                  (+ .dev.vars)
```

## 5. Tasks

> Rule for every task: run its checks, report PASS/FAIL with output; never proceed on FAIL without fixing. Never print secrets.

### Task 0 — Scaffold & pin (`mcp-worker/`)
1. `mkdir mcp-worker`; `npm init -y`; install `agents`, `@modelcontextprotocol/server`, `@cloudflare/workers-oauth-provider`; dev deps `wrangler` (use existing 4.151.0), `typescript`, `vitest`. Pin exact resolved versions in package.json.
2. Read the installed READMEs/types of the three libs and note the exact API shapes being used (handler API, OAuthProvider options, consent helpers). **Adapt snippets to installed truth**; the behavior in §3 stays fixed.
3. Write `tsconfig.json` (workerd-friendly, strict), `wrangler.jsonc` (D1/D3/D4; `compatibility_date` ≥ 2026-10-01; compat flags only as required by installed docs, e.g. `nodejs_compat`, `global_fetch_strictly_public` if CIMD enabled), npm scripts: `dev`, `deploy`, `test` (`vitest run`), `typecheck` (`tsc --noEmit`).
4. Minimal stub `src/index.ts` (plain fetch → 404) so `npx wrangler deploy --dry-run` passes.
5. `.gitignore`: add line `.dev.vars`.
**Done when:** clean install; `npm run typecheck` OK; `npx wrangler deploy --dry-run` builds.

### Task 1 — Port formatting helpers (TDD)
`src/formatting.ts` + `test/formatting.test.ts`: `truncateText`, `truncateRecords`, `capLimit`, `validateStatus`, `emptyMessage`, `toCompactJson`, `tokenEquals` (constant-time: length check + `crypto.subtle.timingSafeEqual`), `RateLimiter` (sliding window, injectable `now`). Tests written from `mcp/formatting.py` cases incl. boundaries (len 500/501, bool limit rejected, numeric-string accepted, `'in progress'` → `in_progress`, invalid status message, all empty-message combos, rate limiter window math).
**Done when:** `npm test` green; `npm run typecheck` OK.

### Task 2 — Supabase admin session (`src/supabase.ts`, `src/errors.ts`)
REST (fetch): login `POST {SUPABASE_URL}/auth/v1/token?grant_type=password` (apikey: anon); RPC `POST {SUPABASE_URL}/rest/v1/rpc/{fn}` (apikey + Bearer admin token). Module-scope token cache with expiry (renew at 45 min); retry once on 401 (relogin) and once on 5xx/network (500 ms). `friendlyError()` per §3. Unit tests with mocked `fetch`: cache reuse, renewal, 401 retry, transient retry, error-message mapping.
**Done when:** `npm test` green; `npm run typecheck` OK.

### Task 3 — Tools + MCP handler (`src/mcp.ts`, `src/audit.ts`)
`buildMcpServer(deps)` registering the 6 tools (schemas per §3, descriptions verbatim; `status` as optional string with allowed-values descriptions + runtime validation; `limit` integer); each handler: audit → validate → rpc → format (mirror `call_admin_rpc`); audit helper calls the `mcp_log_audit` RPC awaited with `AbortSignal.timeout(2000)`, failures swallowed. Export the `createMcpHandler` factory per installed docs.
**Done when:** `npm run typecheck` OK; `npx wrangler dev` boots with the stub `/mcp` wired (auth-less smoke only — full verification lands with Task 6/5).

### Task 4 — Audit table migration (DB)
1. Read `supabase/migrations/20261015120000_mcp_admin_readonly_functions.sql`; mirror its conventions (admin check via existing `auth_role()` helper, grants, style).
2. New migration `supabase/migrations/<YYYYMMDDHHMMSS>_mcp_audit_log.sql`: `mcp_audit_log(id identity pk, created_at timestamptz default now(), tool text not null, args jsonb not null default '{}')`; RLS enabled, **no policies**; `mcp_log_audit(p_tool text, p_args jsonb default '{}')` `security definer` `set search_path=public`, admin-gated (`admin only` otherwise), insert + `return void`; grant execute to authenticated.
3. Apply via Supabase MCP tooling (same as earlier migrations).
4. Verify: (a) insert succeeds with a real admin login (tiny python snippet using `mcp/.venv`, never printing secrets); (b) row visible via service-role SQL read; (c) anon/service-role call without admin JWT is rejected ("admin only").
**Done when:** migration applied; all three checks PASS with printed evidence (tool name + row id only).

### Task 5 — Worker entry: OAuth + consent UI (`src/index.ts`, `src/oauth.ts`)
Follow the **installed** `workers-oauth-provider` README + `docs/consent-page.md` + `docs/mcp-discovery.md` + `docs/authorization-server.md`:
1. `OAuthProvider` with `apiRoute:"/mcp"`, `apiHandler` = the Task-3 handler, `defaultHandler` = Task-5 handler, `authorizeEndpoint:"/authorize"`, token/register endpoints per docs; minimal scopes; `clientIdMetadataDocumentEnabled` + DCR as supported; `resourceMetadata` = `PUBLIC_URL` + `/mcp`.
2. `src/oauth.ts`: `/health` (public JSON) → consent flow per D6 (small styled HTML, dark-friendly; form field for the access token; no caching; fail-closed).
3. Top-level `fetch`: rate-limit `/mcp` per D8 (guard `env.RATE_LIMITER?.`; 429 JSON) → delegate to the provider.
4. Create KV namespace `npx wrangler kv namespace create OAUTH_KV`; put id in `wrangler.jsonc`; attempt `[[ratelimits]]` binding (free plan); if deploy rejects it → remove binding, keep guard path, note it.
5. Local dev: generate `.dev.vars` with the 5 secrets read from `mcp/.env` **without echoing**; `npx wrangler dev`; MCP Inspector quick-OAuth against `http://localhost:8788/mcp` lists 6 tools and a real call returns data.
**Done when:** Inspector PASS locally + `/health` 200 + `/mcp` unauthenticated → 401 with metadata challenge.

### Task 6 — Acceptance script (`scripts/verify_remote.py`)
Python **stdlib-only** (urllib), reads `mcp/.env` for the token (never prints it), takes `BASE_URL`. Discovery-driven (uses 401 challenge/well-known metadata; never hardcodes OAuth paths). Steps, each printing `PASS ...`:
1. `/health` 200 → `{"status":"ok"}`.
2. `/mcp` no auth → 401.
3. Full OAuth: discovery → client registration (DCR) → GET `/authorize` form → POST token → redirect code → token exchange (PKCE) → access + refresh tokens.
4. `initialize` + `tools/list` → exactly 6 expected names; call all 6 with real args → non-empty results (spot-check `get_summary` looks like JSON); invalid status → `Invalid request:` text; blank query → `Invalid request: query is required (...)`.
5. Refresh-token grant → new access token works.
6. Rate limit probe (60+ rapid calls) → 429 or `SKIP (not enabled)`.
Exit non-zero on any FAIL. **Done when:** `py_compile` clean; runnable against a URL (full run in Task 7).

### Task 7 — Deploy + secrets + live verification
1. `npx wrangler deploy` → capture URL (if no workers.dev subdomain exists: register via dashboard — **ask the user for the one click**, or API if possible).
2. Set `PUBLIC_URL` in `wrangler.jsonc` vars → redeploy.
3. Push the 5 secrets: build a temp JSON from `mcp/.env` via PowerShell (never echoed), `npx wrangler secret bulk <file>` (check `wrangler secret --help` for exact syntax), delete temp file; `wrangler secret list` shows names only.
4. Run `verify_remote.py https://residence-mcp.<sub>.workers.dev` → everything PASS (keep output as evidence). Extra: one `wrangler tail` capture during a call; confirm audit rows in `mcp_audit_log` via SQL read.
**Done when:** all §6 evidence green against production.

### Task 8 — Docs & desktop Settings page
1. `desktop/app/ui/pages/settings.py`: new first section "Hosted server (always on, recommended)" with the permanent URL constant + Copy button + rewritten ChatGPT steps at the **current** flow: `chatgpt.com/plugins` → `+` → *Add custom MCP server* → paste URL → authentication: a login page opens once → paste the token (from the existing token row) → Allow → *I understand* → *Create as a plugin*. Keep the Plus/Pro note. Demote current tunnel steps into a secondary "Run it locally (developer/testing)" area, with a note: local server uses bearer auth and is for MCP Inspector/testing — ChatGPT requires the hosted server.
2. `mcp/README.md`: hosted-first; local = dev tool; correct the obsolete "paste bearer into ChatGPT" claims (bearer only works for Inspector/other clients).
3. New `mcp-worker/README.md` (per Task 0/6/7 reality: deploy, secrets **by name**, verify script, redeploy, free-tier notes, what to do after code changes).
4. `docs/manual-test-mcp.md`: add hosted checklist (add connector, one-time sign-in, real question e.g. "how many pending registrations are there?", metadata refresh after tool changes, "after reboot: nothing to do").
5. Root `README.md`: MCP section points at the hosted worker; local = optional.
6. Verify: run the desktop app (`& "desktop\.venv\Scripts\python.exe" "desktop\main.py"`), offscreen screenshot of the Settings page (reuse the earlier harness pattern), confirm no layout/Copy regressions. Re-run existing desktop smoke checks if a runner exists.
**Done when:** screenshot PASS + smoke checks PASS + docs updated.

### Task 9 — Final acceptance & wrap-up
1. Fresh `verify_remote.py` output against production (all PASS).
2. `docs/mcp-handoff.md`: update architecture, URL, evidence, and the "after reboot: nothing to do" answer.
3. Final summary to user: what they must do (connect once in ChatGPT; restart the desktop app to see new Settings text), and open offers (commit decision; cosmetic minors: Copy no-op on empty URL box, dev-mode checkbox glyph).

## 6. Acceptance evidence (the definition of done)

- `verify_remote.py` production run: health PASS, 401 PASS, OAuth dance PASS, 6 tools listed PASS, 6/6 real results PASS, invalid-arg messages PASS, refresh PASS, rate-limit PASS-or-explicit-SKIP; audit rows present PASS.
- No secret value ever appears in any output/log/diff (grep the diff for the token prefix before finishing).
- Desktop Settings screenshot shows the hosted section; local section demoted; app still runs.
- Docs updated as listed; `docs/mcp-handoff.md` carries the evidence.

## 7. Manual steps reserved for the user (cannot be automated)

1. If Cloudflare asks for a workers.dev subdomain: one click in the dashboard (we will ask when it comes up).
2. In ChatGPT: add the connector once, paste the token on the login page that opens. (Requires a plan that supports custom MCP servers — Plus/Pro.)
3. Restart the desktop app after Task 8 to see the new Settings page.

## 8. Risks & fallbacks

- **Rate-limit binding unavailable / paid-only** → remove binding, keep code guard, document SKIP in evidence (auth + audit still enforced).
- **Library API drift vs fetched docs** → installed READMEs/types are authoritative; behavior fixed by §3.
- **workers.dev subdomain unregistered** → dashboard one-click (user) or API; blocked only on that click.
- **ChatGPT plan limitation** → surfaced in Settings text; the Worker still works with other MCP clients (Inspector, mcp-remote).
- **Audit latency** (+1 Supabase roundtrip per call, bounded 2 s) → acceptable; can be made fire-and-forget via `ctx.waitUntil` later if it ever matters.
