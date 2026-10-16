# Hosted MCP server (Cloudflare Worker)

Always-on, permanent-URL replacement for the local Python MCP server in `mcp/`. It serves
the same six read-only admin tools, deployed on Cloudflare Workers.

- **MCP endpoint:** `https://residence-mcp.anes4tlm.workers.dev/mcp`
- **Health (public):** `https://residence-mcp.anes4tlm.workers.dev/health` → `{"status":"ok"}`

## What it is

- **OAuth 2.1 provider** (`@cloudflare/workers-oauth-provider`) in front of `/mcp`.
  ChatGPT (and the MCP Inspector, via dynamic client registration) register as OAuth
  clients. The one-time consent page asks for the same `MCP_AUTH_TOKEN` the desktop app
  shows — pasted once, never again: ChatGPT then holds its own refreshable tokens, so the
  raw shared secret never leaves this machine.
- **Stateless MCP handler** — `createMcpHandler` (from `agents`) + `McpServer` (from
  `@modelcontextprotocol/server`) exposing the 6 read-only tools with the same
  schemas/descriptions as the local server.
- **Supabase REST as admin** — the Worker signs in with `ADMIN_EMAIL`/`ADMIN_PASSWORD`
  using the anon key (RLS stays on) and calls the same `mcp_*` SQL functions as the local
  server. Admin session cached in module scope, renewed early, one retry on auth error.
- **Audit RPC** — before each tool runs, the Worker awaits `mcp_log_audit` (2 s timeout,
  all failures swallowed) which writes tool + arguments to `public.mcp_audit_log` — never
  results, never tokens.
- **Rate limit** — 60 requests/min per client IP on `/mcp` (best-effort free-plan
  binding; the limiter is eventually consistent).

## Commands

All commands run from `mcp-worker/`:

```powershell
npm install

# Local dev server (default http://localhost:8788)
npx wrangler dev --var PUBLIC_URL:http://localhost:8788
# On this Windows box add --ip ::1: localhost resolves IPv6 first and wrangler
# otherwise stalls with the default IPv4-only listener.
npx wrangler dev --var PUBLIC_URL:http://localhost:8788 --ip ::1

npm test           # vitest unit tests
npm run typecheck  # tsc --noEmit

npx wrangler deploy
```

## Secrets

Secrets live only on the Worker; values are pushed from `mcp/.env` via
`wrangler secret bulk` using a **temporary JSON file that is never committed** (and is
deleted right after the upload; it is the only place values ever touch disk — they are
never printed). The five names:

`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `MCP_AUTH_TOKEN`

```powershell
# 1. Build mcp-worker\secrets.tmp.json from mcp\.env with a small script that copies the
#    5 keys above (no values are echoed anywhere), e.g. the Task 7 helper pattern.
# 2. Push:
npx wrangler secret bulk secrets.tmp.json
# 3. Shred the temp file:
Remove-Item secrets.tmp.json
# 4. Confirm names only:
npx wrangler secret list
```

`PUBLIC_URL` is a plain var in `wrangler.jsonc` (the deployed origin), not a secret.

**Rotate a single secret** (the CLI prompts for the new value; updates the deployed
Worker in place):

```powershell
npx wrangler secret put MCP_AUTH_TOKEN
```

If you rotate `MCP_AUTH_TOKEN`, the desktop app picks it up automatically (same
`mcp/.env`), but existing ChatGPT OAuth grants keep working until they expire — nothing
to reconnect.

## Verify

End-to-end acceptance script (stdlib-only; reads the consent token from `mcp/.env`,
never prints it):

```powershell
& "mcp\.venv\Scripts\python.exe" "mcp-worker\scripts\verify_remote.py" https://residence-mcp.anes4tlm.workers.dev
```

It checks: `/health` 200, `/mcp` without auth → 401, the full OAuth dance (discovery →
client registration → consent page → token exchange with PKCE), `initialize` +
`tools/list` → exactly 6 tools, all 6 tools called with real data, invalid-arg messages,
refresh-token grant, and a rate-limit probe (429 or explicit SKIP). Exit code 0 = all
green. Optional flags: `--token TOKEN` (instead of reading `mcp/.env`) and
`--timeout SECONDS`.

## Free tier notes

- Workers free plan: 100k requests/day, paid-plan features not required. The `OAUTH_KV`
  namespace and the rate-limit binding sit inside their free quotas for this use.
- The rate limiter is best-effort: under rapid sequential calls it can be eventually
  consistent (the verify script reports SKIP/429 accordingly). Auth and audit are always
  enforced.
- Nothing to run and nothing to keep open: after a reboot there is nothing to do, and
  ChatGPT works even when this PC is off.

## After a tool change

1. `npm test` and `npm run typecheck`
2. `npx wrangler deploy`
3. In ChatGPT: use **Refresh** on the connection so it reloads the tool list (no
   re-login needed; same in the MCP Inspector).

## Related

- Local Python server (development/testing, bearer token): [`../mcp/README.md`](../mcp/README.md)
- Manual checklist: [`../docs/manual-test-mcp.md`](../docs/manual-test-mcp.md)
