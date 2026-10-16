-- ============================================================================
-- MCP audit log for the ChatGPT "Residence Tlemcen" connector (plan D7).
-- Full documentation: docs/superpowers/plans/2026-10-15-cloudflare-worker-mcp.md
--
-- Design rules:
--   * public.mcp_audit_log stores one row per MCP tool call: tool name, raw
--     arguments (jsonb) and timestamp. Never results, never tokens.
--   * RLS is enabled with NO policies: the table is reachable only through
--     the security-definer function below (and by the service role / SQL
--     editor, which bypass RLS as table owner).
--   * mcp_log_audit() must insert on behalf of the caller, so it is
--     security definer; it raises 'admin only' (SQLSTATE 42501) unless the
--     caller's profiles.role is exactly 'admin' -- exactly the same guard as
--     the read-only MCP functions (reuses mcp_require_admin()/auth_role()).
--   * The MCP server calls it before each tool run, max 2 s, and swallows
--     all failures (auditing must never fail a tool call).
-- ============================================================================


-- ----------------------------------------------------------------------------
-- Table: append-only audit trail. service role / definer function only.
-- ----------------------------------------------------------------------------
create table mcp_audit_log (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  tool text not null,
  args jsonb not null default '{}'::jsonb
);

alter table mcp_audit_log enable row level security;
-- Intentionally NO policies: anon/authenticated get nothing here; the
-- definer function (owner) and the service role bypass RLS.

comment on table mcp_audit_log is
  'Append-only audit trail of MCP admin tool calls (tool name + arguments + timestamp). RLS enabled with no policies: write/read via mcp_log_audit() or service role only.';


-- ----------------------------------------------------------------------------
-- RPC: append one audit row. Admin-only, exactly like the read-only MCP
-- functions (mcp_require_admin() raises 'admin only', SQLSTATE 42501).
-- ----------------------------------------------------------------------------
create or replace function mcp_log_audit(p_tool text, p_args jsonb default '{}'::jsonb)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  perform mcp_require_admin();

  insert into mcp_audit_log (tool, args)
  values (p_tool, coalesce(p_args, '{}'::jsonb));

  return;
end $$;

comment on function mcp_log_audit(text, jsonb) is
  'Admin-only append of one MCP tool call to mcp_audit_log (tool + args + timestamp).';


-- ----------------------------------------------------------------------------
-- Permissions: only authenticated users may execute; the admin check runs
-- inside the function, so non-admin roles get 'admin only'.
-- (Same pattern as 20261015120000_mcp_admin_readonly_functions.sql.)
-- ----------------------------------------------------------------------------
revoke execute on function
  mcp_log_audit(text, jsonb)
from public, anon;

grant execute on function
  mcp_log_audit(text, jsonb)
to authenticated;


-- ============================================================================
-- How to verify (SUPABASE_URL + SUPABASE_ANON_KEY from mcp/.env):
--   1. POST $SUPABASE_URL/auth/v1/token?grant_type=password  (apikey: anon,
--      body: admin email/password from mcp/.env) -> access_token.
--   2. POST $SUPABASE_URL/rest/v1/rpc/mcp_log_audit
--        -H "apikey: <anon>" -H "Authorization: Bearer <admin token>"
--        -H "Content-Type: application/json"
--        -d '{"p_tool":"verify_probe","p_args":{}}'      # expect 204
--   3. Row visible: select id, tool, created_at from mcp_audit_log
--      order by id desc limit 1;
--   4. Negative check: the same call without a token is rejected (no EXECUTE
--      for anon); a staff token returns
--      {"code":"42501","message":"admin only"}.
--
-- Rollback (manual, if ever needed):
--   drop function if exists mcp_log_audit(text, jsonb);
--   drop table if exists mcp_audit_log;
-- ============================================================================
