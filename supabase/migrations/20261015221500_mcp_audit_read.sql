-- ============================================================================
-- MCP audit log — admin read helper (addition to plan §Task 4; the write side
-- shipped in 20261015214000_mcp_audit_log.sql).
--
-- Purpose:
--   * Gives the admin a supported way to inspect the audit trail (REST RPC /
--     app / SQL editor) without service-role access.
--   * Used to verify that the deployed Cloudflare Worker really records one
--     row per tool call.
--
-- Semantics: newest first, `p_limit` clamped to [1, 100] (default 20).
-- Admin-only, exactly like the other mcp_* functions (mcp_require_admin()).
-- ============================================================================


create or replace function mcp_list_audit(p_limit int default 20)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  capped int;
begin
  perform mcp_require_admin();

  capped := greatest(1, least(coalesce(p_limit, 20), 100));

  return coalesce(
    (
      select jsonb_agg(row_to_json(t) order by t.id desc)
      from (
        select id, tool, args, created_at
        from mcp_audit_log
        order by id desc
        limit capped
      ) t
    ),
    '[]'::jsonb
  );
end $$;

comment on function mcp_list_audit(int) is
  'Admin-only read of the newest MCP audit rows (newest first, max 100).';


-- ----------------------------------------------------------------------------
-- Permissions: same pattern as the rest of the mcp_* surface.
-- ----------------------------------------------------------------------------
revoke execute on function
  mcp_list_audit(int)
from public, anon;

grant execute on function
  mcp_list_audit(int)
to authenticated;


-- ============================================================================
-- How to verify (SUPABASE_URL + SUPABASE_ANON_KEY from mcp/.env):
--   1. POST $SUPABASE_URL/auth/v1/token?grant_type=password -> admin JWT.
--   2. POST $SUPABASE_URL/rest/v1/rpc/mcp_list_audit {"p_limit": 20}
--      -H "apikey: <anon>" -H "Authorization: Bearer <admin JWT>" -> JSON array.
--   3. Same call with a staff JWT -> {"code":"42501","message":"admin only"}.
--
-- Rollback (manual, if ever needed):
--   drop function if exists mcp_list_audit(int);
-- ============================================================================
