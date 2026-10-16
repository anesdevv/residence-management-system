# MCP manual test checklist

Two servers expose the admin tools:

- **Hosted Cloudflare Worker** (primary) — what ChatGPT connects to:
  `https://residence-mcp.anes4tlm.workers.dev/mcp` (health: same origin, `/health`).
  14 tools: 6 read-only + 8 admin-confirmed write tools (writes can be switched off in the
  desktop Settings).
- **Local Python server** (development/testing only) — bearer-token clients such as the
  MCP Inspector. ChatGPT itself requires the hosted server. Six read-only tools by design.

Seeded demo accounts (`scripts/seed.py`): admin `admin@residence.test` / `Admin1234!`,
staff `staff@residence.test` / `Staff1234!`, student
`20230001@students.residence.local` / `Student1234!`.

## A. Hosted server (primary — ChatGPT)

- [ ] 1. Health check: `curl.exe -s https://residence-mcp.anes4tlm.workers.dev/health` → `{"status":"ok"}` (no login required).
- [ ] 2. Connect in ChatGPT (needs a plan with custom MCP servers — Plus/Pro): `chatgpt.com/plugins` → “+” → *Add custom MCP server* → name + description → Connection: paste `https://residence-mcp.anes4tlm.workers.dev/mcp` (the `/mcp` path is required) → a login page opens **once** → paste the token from the desktop app (Settings → Developer mode → Copy) → *Allow* → *“I understand and want to continue”* → *“Create as a plugin”*.
- [ ] 3. “How many pending registrations are there?” → matches the desktop Registrations page.
- [ ] 4. “Show me the pending maintenance tickets” → matches the desktop Maintenance page (pending = status `pending`).
- [ ] 5. Spot-check more: “Any pending room change requests?” and “Which student is in room B-101?” → match the desktop Room Changes / Students pages.
- [ ] 6. Metadata refresh flow: after any worker redeploy, the only step in ChatGPT is **Refresh** on the connection → the new tool list appears (14 tools); no re-login, no reconnect.
- [ ] 7. After reboot: nothing to do — the Worker is always on, ChatGPT holds its own OAuth tokens, and there is no local terminal or tunnel to restart.
- [ ] 8. (Optional evidence) Every call appears in `public.mcp_audit_log` (tool + arguments + timestamp; never results, never tokens). Full automated check: `& "mcp\.venv\Scripts\python.exe" "mcp-worker\scripts\verify_remote.py" https://residence-mcp.anes4tlm.workers.dev` → `SUMMARY: 30 passed, 0 failed, 1 skipped` (the single skip is the rate-limit probe — the same behavior as the read-only era).
- [ ] 9. Write checklist (ChatGPT asks for explicit confirmation before every change). Create a test room: “create a test room 999 in block Z with 2 places” → ChatGPT shows what will change and asks you to confirm → the room (Z-999, capacity 2) appears in the desktop Rooms page.
- [ ] 10. Edit then delete it: “change room Z-999 to 3 places” → confirm → capacity 3 in the desktop; then “delete that test room” → confirm → it disappears from the desktop Rooms page.
- [ ] 11. Approve/reject a registration: pick a pending registration, ask ChatGPT to approve it into a room with a free place and matching gender, and reject another one with a reason → confirm each → the desktop Registrations page reflects both.
- [ ] 12. Approve/reject a room change request the same way → the desktop Room Changes page reflects the decision.
- [ ] 13. Update a maintenance ticket: ask ChatGPT to mark a ticket `in_progress` with a note (optionally later `resolved`) → confirm → the desktop Maintenance page shows the new status and note. This is the only write path the automated acceptance script does not exercise — check it by hand.
- [ ] 14. Off-switch + audit: desktop Settings → turn “Allow ChatGPT to change data” off → ask for a write (e.g. “create a test room”) → it is refused with “Writing is currently disabled. Turn it on in the desktop app: Settings → Allow ChatGPT to change data.” → turn the switch back on. The successful writes show `ok: true` in `public.mcp_audit_log`; the refused attempt shows `ok: false` with the reason in `detail`.

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
`rejection_reason`) are truncated to 500 characters; the **hosted worker** can change data
when the admin enables it in the desktop Settings (every change is confirmed in ChatGPT
first, logged in `mcp_audit_log`, and still subject to the DB rules); the **local Python
server stays read-only by design** — no tool can change any data.
