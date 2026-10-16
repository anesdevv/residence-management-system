# Admin MCP server (read-only)

A small [Model Context Protocol](https://modelcontextprotocol.io) server that lets an
**administrator** ask MCP clients (ChatGPT, the MCP Inspector) about the live residence
data: maintenance tickets, room change requests, pending registrations/approvals,
students and rooms.

It is strictly read-only: the six tools can only list and search — no tool can insert,
update or delete anything.

Two interchangeable backends serve the same six tools:

| | Hosted worker (recommended) | Local Python server |
|---|---|---|
| Where | Cloudflare Workers — always on, permanent URL | this PC, `http://localhost:8000` |
| Auth | OAuth 2.1 — sign in once at a browser login page | shared bearer token |
| ChatGPT | supported | **not supported** — ChatGPT custom MCP servers use OAuth (or no auth); there is no field for a static bearer token |
| Good for | everyday admin use from ChatGPT | development, the MCP Inspector, bearer-capable testing clients |

## Hosted server (recommended)

Permanent URL: `https://residence-mcp.anes4tlm.workers.dev/mcp`
Health (public): `https://residence-mcp.anes4tlm.workers.dev/health` → `{"status":"ok"}`.

Connect ChatGPT once:

1. **chatgpt.com/plugins → “+” → “Add custom MCP server”** (needs a ChatGPT plan that
   supports custom MCP servers — Plus/Pro).
2. Give it a name and description.
3. Connection: paste the URL above (it already includes `/mcp`).
4. A login page opens **once** — paste the token the desktop app shows
   (Settings → Developer mode → Copy), then *Allow*.
5. *“I understand and want to continue”* → *“Create as a plugin”*. Done.

After that ChatGPT holds its own refreshable tokens: no terminals, no tunnel, nothing to
do after a reboot. After a tool change (new deploy), use *Refresh* on the connection in
ChatGPT so it reloads the tool list.

Deploy, secrets, verification and operations: [`mcp-worker/README.md`](../mcp-worker/README.md).
The end-to-end acceptance script is `mcp-worker/scripts/verify_remote.py`.

## Local server (development/testing only)

Everything below describes the local Python server. It uses a **bearer token**
(`MCP_AUTH_TOKEN`) and works with the MCP Inspector and other bearer-capable clients.
**ChatGPT itself requires the hosted server above** — it accepts OAuth or no-auth for
custom MCP servers, not a static bearer token.

### Access control

- The server connects to Supabase with the **anon key plus a real admin login** — never the
  service role key — so RLS always applies.
- Every SQL function it calls starts with an admin check and raises `admin only`
  (SQLSTATE 42501) unless the signed-in account has `profiles.role = 'admin'`.
- Requests to `/mcp` additionally require the shared bearer token (`MCP_AUTH_TOKEN`).

### Tools

| Tool | What it does |
|---|---|
| `list_maintenance_tickets` | Maintenance tickets with student and room details. Optional `status`: `pending`, `in_progress` or `resolved` (omit for all). |
| `list_room_change_requests` | Room change requests with student, current room and preferred room. Optional `status`: `pending`, `approved` or `rejected`. |
| `list_pending_registrations` | Students waiting for account approval, with their submitted data and whether they match the official residents list. |
| `search_students` | Find a student by name or card ID; also accepts a room label like `B-101` to see who lives there. |
| `list_rooms` | Rooms with capacity, occupancy and free places; `only_available` finds rooms with space. |
| `get_summary` | Overview: registrations, tickets, room changes and occupancy, in total and per block. |

### Requirements

- Python 3.11 or newer.
- Network access to the Supabase project.
- A real admin account (`profiles.role = 'admin'`). The seed script (`scripts/seed.py`)
  creates `admin@residence.test` / `Admin1234!` for demos.

### Setup

From the `mcp/` folder:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env    # then edit .env and fill in every value
```

Generate the bearer token with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The code uses the MCP Python SDK **v1** API (`mcp.server.fastmcp.FastMCP` with
`streamable_http_app()`), which was renamed to `MCPServer` in SDK v2 — that is why
`requirements.txt` deliberately pins `mcp>=1.9,<2`.

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `SUPABASE_URL` | yes | URL of the existing Supabase project. |
| `SUPABASE_ANON_KEY` | yes | Anon/public key only — never the service role key (RLS must stay on). |
| `ADMIN_EMAIL` | yes | Administrator account the server signs in as. |
| `ADMIN_PASSWORD` | yes | Password for that account. |
| `MCP_AUTH_TOKEN` | yes | Shared secret clients must send as `Authorization: Bearer <MCP_AUTH_TOKEN>`; minimum 32 characters. The same token is the password on the hosted worker's OAuth consent page. |
| `PORT` | no | Local HTTP port (default `8000`). |

`.env` is gitignored and must never be committed; only `.env.example` (placeholder values)
belongs in the repository.

### Running

From the repository root:

```powershell
& "mcp\.venv\Scripts\python.exe" "mcp\server.py"
```

or from `mcp/`:

```powershell
.venv\Scripts\python.exe server.py
```

The server loads `.env` from its own folder, so it works from any working directory. It
refuses to start if a required variable is missing, or if `MCP_AUTH_TOKEN` is shorter than
32 characters.

Endpoints:

- `GET /health` — no authentication; returns `{"status":"ok"}`.
- `/mcp` — MCP streamable HTTP. Requires the header `Authorization: Bearer <MCP_AUTH_TOKEN>`;
  a missing or wrong token returns `401 {"error":"unauthorized"}`.

Rate limit: 60 requests per minute per IP; over the limit → `429 {"error":"rate limit exceeded"}`.

### Audit log

Every tool call appends one JSON line to `mcp/audit.log`:

```json
{"timestamp": "2026-10-15T12:34:56.789012+00:00", "tool": "get_summary", "arguments": {}}
```

Only the timestamp, tool name and arguments are written — never results, never tokens. The
file is created on the first tool call and is gitignored. (The hosted worker writes the
equivalent rows to the `mcp_audit_log` table instead.)

### Test locally with the MCP Inspector

Start the server, then:

```powershell
npx @modelcontextprotocol/inspector
```

In the Inspector UI choose transport **Streamable HTTP**, URL `http://localhost:8000/mcp`,
and add the custom header `Authorization: Bearer <MCP_AUTH_TOKEN>`, then connect. You
should see the 6 tools and be able to call them.

### Other bearer-capable clients

- Any custom MCP client that supports a static `Authorization: Bearer <MCP_AUTH_TOKEN>`
  header can talk to the local server directly, or through a tunnel
  (`wrangler tunnel quick-start http://localhost:8000`, `cloudflared tunnel --url
  http://localhost:8000`, or `ngrok http 8000`) if the client runs on another machine.
- **ChatGPT is not one of them.** ChatGPT custom MCP servers use OAuth (or no auth) —
  there is no bearer-token field. Use the hosted worker above for ChatGPT.

Example questions (work the same on the hosted server):

- “Are there any open maintenance tickets?”
- “Any pending room change requests?”
- “Who is waiting for approval?”
- “Which student is in room B-101?”

## Privacy

Every question and its results — including personal student data (names, card IDs, dates
of birth, phones, emails, rooms) — travel through the server you are using to the MCP
client (ChatGPT/OpenAI, the Inspector, …). The hosted worker additionally runs on
Cloudflare and logs tool name + arguments (never results) to the Supabase audit table.
Keep both servers for admin use only, keep the `MCP_AUTH_TOKEN` secret, and stop the local
server/tunnel when you are not using it. The hosted path authenticates via OAuth, so
ChatGPT never sees the raw shared secret.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `401 {"error":"unauthorized"}` | Missing or wrong `Authorization: Bearer <MCP_AUTH_TOKEN>` header (local server). |
| `429 {"error":"rate limit exceeded"}` | More than 60 requests in a minute from one IP — wait a minute and retry. |
| Server exits with `MCP_AUTH_TOKEN must be at least 32 characters` | Generate a longer token (command above) and put it in `mcp/.env`. |
| Server exits with `Missing required environment variables: ...` | Copy `.env.example` to `.env` and fill in the listed values. |
| "The server could not authenticate with Supabase" | Wrong `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `mcp/.env`. |
| One-off Supabase / gateway error | Transient network errors are retried once automatically; the server also re-logs in if its session expires. Retry if it keeps failing. |
| ChatGPT cannot connect to the local server | Expected — ChatGPT needs OAuth, which only the hosted worker provides. Connect the hosted URL instead. |

The end-to-end manual checklist is in [`docs/manual-test-mcp.md`](../docs/manual-test-mcp.md).
