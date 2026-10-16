# MCP manual test checklist

Two interchangeable servers expose the same six read-only admin tools:

- **Hosted Cloudflare Worker** (primary) — what ChatGPT connects to:
  `https://residence-mcp.anes4tlm.workers.dev/mcp` (health: same origin, `/health`).
- **Local Python server** (development/testing only) — bearer-token clients such as the
  MCP Inspector. ChatGPT itself requires the hosted server.

Seeded demo accounts (`scripts/seed.py`): admin `admin@residence.test` / `Admin1234!`,
staff `staff@residence.test` / `Staff1234!`, student
`20230001@students.residence.local` / `Student1234!`.

## A. Hosted server (primary — ChatGPT)

- [ ] 1. Health check: `curl.exe -s https://residence-mcp.anes4tlm.workers.dev/health` → `{"status":"ok"}` (no login required).
- [ ] 2. Connect in ChatGPT (needs a plan with custom MCP servers — Plus/Pro): `chatgpt.com/plugins` → “+” → *Add custom MCP server* → name + description → Connection: paste `https://residence-mcp.anes4tlm.workers.dev/mcp` (the `/mcp` path is required) → a login page opens **once** → paste the token from the desktop app (Settings → Developer mode → Copy) → *Allow* → *“I understand and want to continue”* → *“Create as a plugin”*.
- [ ] 3. “How many pending registrations are there?” → matches the desktop Registrations page.
- [ ] 4. “Show me the pending maintenance tickets” → matches the desktop Maintenance page (pending = status `pending`).
- [ ] 5. Spot-check more: “Any pending room change requests?” and “Which student is in room B-101?” → match the desktop Room Changes / Students pages.
- [ ] 6. Metadata refresh flow: after a tool change + `npx wrangler deploy`, use **Refresh** on the connection in ChatGPT → the new tool list appears; no re-login, no reconnect.
- [ ] 7. After reboot: nothing to do — the Worker is always on, ChatGPT holds its own OAuth tokens, and there is no local terminal or tunnel to restart.
- [ ] 8. (Optional evidence) Every call appears in `public.mcp_audit_log` (tool + arguments + timestamp; never results, never tokens). Full automated check: `& "mcp\.venv\Scripts\python.exe" "mcp-worker\scripts\verify_remote.py" https://residence-mcp.anes4tlm.workers.dev` → all PASS.

## B. Local server (development/testing only)

Start it with `& "mcp\.venv\Scripts\python.exe" "mcp\server.py"` from the repo root (with
`mcp\.env` filled in). Clients must send `Authorization: Bearer <MCP_AUTH_TOKEN>` — this
works with the MCP Inspector and other bearer-capable tools, **not** with ChatGPT.

- [ ] 1. MCP Inspector connects (transport Streamable HTTP, URL `http://localhost:8000/mcp`, header `Authorization: Bearer <MCP_AUTH_TOKEN>`) and lists exactly 6 tools with the expected names and descriptions: `list_maintenance_tickets`, `list_room_change_requests`, `list_pending_registrations`, `search_students`, `list_rooms`, `get_summary`.
- [ ] 2. No token → HTTP 401; wrong token → HTTP 401 (`curl.exe -i http://127.0.0.1:8000/mcp` without a header, then with a bad `Authorization: Bearer ...` header).
- [ ] 3. Non-admin login (staff or student) → every tool call fails with an `admin only` permission error (point `ADMIN_EMAIL`/`ADMIN_PASSWORD` in `mcp/.env` at that account and restart; the SQL functions raise `admin only`, SQLSTATE 42501, and the server reports "Permission denied: this tool requires an administrator account").
- [ ] 4. “Are there any open maintenance tickets?” → numbers match the desktop Maintenance page (open = status not `resolved`).
- [ ] 5. “Any pending room change requests?” → matches the desktop Room Changes page (pending only).
- [ ] 6. “Who is waiting for approval?” → matches the desktop pending registrations, including the "on official list" match info.
- [ ] 7. Search returns the right person by name and by card ID; "Which student is in room B-101?" returns that room's resident.
- [ ] 8. Summary numbers match the desktop Overview (pending registrations, active students, room capacity/occupancy, open tickets).
- [ ] 9. Every tool call appears in `mcp/audit.log` with timestamp/tool/arguments and no results.

Notes: `/mcp` is rate-limited to 60 requests/minute per IP on both servers (over the limit
→ HTTP 429); free text fields (`description`, `staff_note`, `reason`, `decision_note`,
`rejection_reason`) are truncated to 500 characters; both servers are read-only — no tool
can change any data.
