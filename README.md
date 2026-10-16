# University Residence Management System (Tlemcen)

Backend: Supabase (Postgres + Auth + Storage).
Websites/clients: `web/` (Astro, students), `desktop/` (PySide6, staff).

## Backend setup
1. `npx supabase login` 
2. `npx supabase link --project-ref <your-ref>` 
3. `npx supabase db push`          # apply migrations
4. Copy `.env.example` to `.env` and fill in real keys (never commit `.env`).
5. Seed: `python scripts/seed.py`  # needs SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
6. Tests: `pip install -r tests/requirements.txt` then `python -m pytest tests -v`

## Ask ChatGPT (MCP)
Admins can ask ChatGPT about maintenance tickets, room changes, pending approvals,
students and rooms through a read-only MCP server. The primary path is the **hosted
Cloudflare Worker** at `https://residence-mcp.anes4tlm.workers.dev/mcp` — connect it once
in ChatGPT (`chatgpt.com/plugins` → “+” → *Add custom MCP server*; requires an
MCP-capable plan such as Plus/Pro) and it works even when your PC is off. Deploy/ops:
[`mcp-worker/README.md`](mcp-worker/README.md). The local Python server in `mcp/` is kept
as a development/testing fallback (MCP Inspector and other bearer-token clients — ChatGPT
itself requires the hosted server): [`mcp/README.md`](mcp/README.md). The assistant is
admin-only and read-only — it can look at data, but nothing can be modified.

