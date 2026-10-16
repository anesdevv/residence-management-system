-- ============================================================================
-- MCP write surface: settings off-switch, room/ticket write RPCs and the
-- two-phase audit outcome (plan A3).
-- Plan: docs/superpowers/plans/2026-10-16-mcp-write-tools.md
-- Spec: docs/superpowers/specs/2026-10-15-mcp-write-tools-design.md
--
-- Design rules:
--   * mcp_settings is a singleton row (id boolean primary key check (id)) that
--     holds the writes_enabled off-switch; one admin-only RLS policy for all
--     commands, and set_updated_at() keeps updated_at fresh.
--   * mcp_get_settings()/mcp_set_writes_enabled() expose the switch to the
--     desktop Settings page and the worker's write gate. A missing settings
--     row counts as enabled (the seeded default).
--   * mcp_create_room / mcp_update_room / mcp_delete_room / mcp_update_ticket
--     are security invoker (the admin's RLS applies, like the read tools) and
--     admin-gated via mcp_require_admin(); the guards from
--     20261015233000_room_invariants.sql enforce occupancy rules underneath.
--   * Validation messages are the contract the worker's friendly-error mapping
--     matches: 'block required', 'room number required', 'floor must be
--     between 0 and 15', 'capacity must be between 1 and 8', 'gender must be
--     male or female', 'room not found', 'ticket not found',
--     'invalid status: ... (expected in_progress or resolved)',
--     'enabled required' and 'Room <block>-<number> already exists.'.
--   * Two-phase audit: mcp_log_audit() returns the new row id; the caller then
--     fills the outcome with mcp_complete_audit() (ok + left(detail, 500)).
--     mcp_log_audit must be dropped and re-created because its return type
--     changes (void -> bigint); the drop removes its grants, so the
--     revoke/grant block is re-applied below.
--
-- Rollback (manual, if ever needed):
--   drop function if exists mcp_complete_audit(bigint, boolean, text);
--   drop function if exists mcp_update_ticket(uuid, text, text);
--   drop function if exists mcp_delete_room(uuid);
--   drop function if exists mcp_update_room(uuid, text, int, text, int, text);
--   drop function if exists mcp_create_room(text, int, text, int, text);
--   drop function if exists mcp_set_writes_enabled(boolean);
--   drop function if exists mcp_get_settings();
--   drop table if exists mcp_settings;
--   -- audit columns: drop ok/detail, then restore the void mcp_log_audit
--   -- from 20261015214000_mcp_audit_log.sql.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- Table: singleton settings row (the writes off-switch) + admin-only RLS.
-- ----------------------------------------------------------------------------
create table mcp_settings (
  id boolean primary key default true check (id),
  writes_enabled boolean not null default true,
  updated_at timestamptz not null default now(),
  updated_by uuid references profiles(id) on delete set null
);

alter table mcp_settings enable row level security;

create policy mcp_settings_admin on mcp_settings
  for all
  using (auth_role() = 'admin')
  with check (auth_role() = 'admin');

create trigger mcp_settings_set_updated_at before update on mcp_settings
  for each row execute function set_updated_at();

comment on table mcp_settings is
  'Singleton MCP settings row: the writes_enabled off-switch for the ChatGPT write tools. RLS: admin only.';

-- Seed the singleton enabled (the "missing row counts as enabled" default is
-- only a safety net; the row is the source of truth).
insert into mcp_settings (id) values (true);


-- ----------------------------------------------------------------------------
-- Settings RPCs: read + flip the off-switch (admin-gated, security invoker).
-- ----------------------------------------------------------------------------
create or replace function mcp_get_settings()
returns jsonb
language plpgsql
stable
security invoker
set search_path = public, pg_temp
as $$
declare
  v mcp_settings;
begin
  perform mcp_require_admin();

  select * into v from mcp_settings where id;

  if v is null then
    -- Missing row counts as enabled (the seeded default).
    return jsonb_build_object('writes_enabled', true, 'updated_at', null);
  end if;

  return jsonb_build_object('writes_enabled', v.writes_enabled, 'updated_at', v.updated_at);
end $$;

comment on function mcp_get_settings() is
  'Admin-only read of the MCP settings (writes_enabled off-switch + updated_at); a missing row counts as enabled.';


create or replace function mcp_set_writes_enabled(p_enabled boolean)
returns jsonb
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  v mcp_settings;
begin
  perform mcp_require_admin();

  if p_enabled is null then
    raise exception 'enabled required' using errcode = '22023';
  end if;

  update mcp_settings
     set writes_enabled = p_enabled,
         updated_by = auth.uid()
   where id
  returning * into v;

  if v is null then
    -- The seed should make this unreachable; keep the singleton usable anyway.
    insert into mcp_settings (id, writes_enabled, updated_by)
    values (true, p_enabled, auth.uid())
    returning * into v;
  end if;

  return jsonb_build_object('writes_enabled', v.writes_enabled, 'updated_at', v.updated_at);
end $$;

comment on function mcp_set_writes_enabled(boolean) is
  'Admin-only off-switch: sets writes_enabled (updated_by = auth.uid()) and returns the new settings.';


-- ----------------------------------------------------------------------------
-- Room write RPCs. Security invoker: the admin's RLS applies; the A1 guards
-- (20261015233000_room_invariants.sql) refuse occupied-room deletes, capacity
-- cuts below occupancy and gender flips on occupied rooms.
-- ----------------------------------------------------------------------------
create or replace function mcp_create_room(
  p_block text,
  p_floor int,
  p_number text,
  p_capacity int,
  p_gender text
)
returns jsonb
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  v_block text;
  v_number text;
  v_gender gender;
  r rooms;
begin
  perform mcp_require_admin();

  v_block := upper(trim(coalesce(p_block, '')));
  v_number := trim(coalesce(p_number, ''));

  if v_block = '' then
    raise exception 'block required' using errcode = '22023';
  end if;

  if v_number = '' then
    raise exception 'room number required' using errcode = '22023';
  end if;

  if p_floor is null or p_floor < 0 or p_floor > 15 then
    raise exception 'floor must be between 0 and 15' using errcode = '22023';
  end if;

  if p_capacity is null or p_capacity < 1 or p_capacity > 8 then
    raise exception 'capacity must be between 1 and 8' using errcode = '22023';
  end if;

  if lower(trim(coalesce(p_gender, ''))) not in ('male', 'female') then
    raise exception 'gender must be male or female' using errcode = '22023';
  end if;
  v_gender := lower(trim(p_gender))::gender;

  begin
    insert into rooms (block, floor, number, capacity, gender)
    values (v_block, p_floor, v_number, p_capacity, v_gender)
    returning * into r;
  exception when unique_violation then
    raise exception 'Room %-% already exists.', v_block, v_number
      using errcode = '23505';
  end;

  return to_jsonb(r);
end $$;

comment on function mcp_create_room(text, int, text, int, text) is
  'Admin-only room creation (block uppercased/trimmed; floor 0-15; capacity 1-8; gender male|female); duplicate block+number raises "Room <block>-<number> already exists.".';


create or replace function mcp_update_room(
  p_room uuid,
  p_block text default null,
  p_floor int default null,
  p_number text default null,
  p_capacity int default null,
  p_gender text default null
)
returns jsonb
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  r rooms;
  v_block text;
  v_number text;
  v_gender gender;
begin
  perform mcp_require_admin();

  select * into r from rooms where id = p_room for update;
  if r is null then
    raise exception 'room not found';
  end if;

  -- Provided fields are validated (a blank block/number is an error, not a
  -- skip); omitted fields (null) keep the current value.
  if p_block is not null then
    v_block := upper(trim(p_block));
    if v_block = '' then
      raise exception 'block required' using errcode = '22023';
    end if;
  end if;

  if p_number is not null then
    v_number := trim(p_number);
    if v_number = '' then
      raise exception 'room number required' using errcode = '22023';
    end if;
  end if;

  if p_floor is not null and (p_floor < 0 or p_floor > 15) then
    raise exception 'floor must be between 0 and 15' using errcode = '22023';
  end if;

  if p_capacity is not null and (p_capacity < 1 or p_capacity > 8) then
    raise exception 'capacity must be between 1 and 8' using errcode = '22023';
  end if;

  if p_gender is not null then
    if lower(trim(p_gender)) not in ('male', 'female') then
      raise exception 'gender must be male or female' using errcode = '22023';
    end if;
    v_gender := lower(trim(p_gender))::gender;
  end if;

  begin
    update rooms
       set block    = coalesce(v_block, r.block),
           floor    = coalesce(p_floor, r.floor),
           number   = coalesce(v_number, r.number),
           capacity = coalesce(p_capacity, r.capacity),
           gender   = coalesce(v_gender, r.gender)
     where id = p_room
    returning * into r;
  exception when unique_violation then
    raise exception 'Room %-% already exists.',
      coalesce(v_block, r.block), coalesce(v_number, r.number)
      using errcode = '23505';
  end;

  return to_jsonb(r);
end $$;

comment on function mcp_update_room(uuid, text, int, text, int, text) is
  'Admin-only partial room update; omitted fields stay unchanged, occupancy guards apply; duplicate block+number raises "Room <block>-<number> already exists.".';


create or replace function mcp_delete_room(p_room uuid)
returns jsonb
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  r rooms;
begin
  perform mcp_require_admin();

  -- The A1 delete guard refuses rooms with active residents.
  delete from rooms where id = p_room returning * into r;

  if r is null then
    raise exception 'room not found';
  end if;

  return jsonb_build_object('deleted', true, 'room', to_jsonb(r));
end $$;

comment on function mcp_delete_room(uuid) is
  'Admin-only room delete; returns {deleted: true, room: {...}}; the occupancy guard refuses rooms with active residents.';


-- ----------------------------------------------------------------------------
-- Ticket write RPC: mark in_progress/resolved, optional note (blank keeps the
-- existing note), handled_by = auth.uid().
-- ----------------------------------------------------------------------------
create or replace function mcp_update_ticket(p_ticket uuid, p_status text, p_note text default null)
returns jsonb
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  v_status text;
  t maintenance_reports;
begin
  perform mcp_require_admin();

  v_status := lower(trim(coalesce(p_status, '')));
  if v_status not in ('in_progress', 'resolved') then
    raise exception 'invalid status: % (expected in_progress or resolved)', p_status
      using errcode = '22023';
  end if;

  select * into t from maintenance_reports where id = p_ticket for update;
  if t is null then
    raise exception 'ticket not found';
  end if;

  update maintenance_reports
     set status = v_status::report_status,
         staff_note = coalesce(nullif(btrim(p_note), ''), staff_note),
         handled_by = auth.uid()
   where id = p_ticket
  returning * into t;

  return to_jsonb(t);
end $$;

comment on function mcp_update_ticket(uuid, text, text) is
  'Admin-only maintenance ticket update: status in_progress|resolved, optional note (blank keeps the existing note), handled_by = auth.uid().';


-- ----------------------------------------------------------------------------
-- Two-phase audit: attempt row (mcp_log_audit returns the new id) + outcome
-- (mcp_complete_audit fills ok + left(detail, 500)).
-- ----------------------------------------------------------------------------
alter table mcp_audit_log
  add column ok boolean,
  add column detail text;

-- Return type changes (void -> bigint), so drop and re-create. The drop also
-- removes the function's grants and comment: both are re-applied below.
drop function mcp_log_audit(text, jsonb);

create or replace function mcp_log_audit(p_tool text, p_args jsonb default '{}'::jsonb)
returns bigint
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_id bigint;
begin
  perform mcp_require_admin();

  insert into mcp_audit_log (tool, args)
  values (p_tool, coalesce(p_args, '{}'::jsonb))
  returning id into v_id;

  return v_id;
end $$;

comment on function mcp_log_audit(text, jsonb) is
  'Admin-only append of one MCP tool call to mcp_audit_log; returns the new row id for mcp_complete_audit().';


create or replace function mcp_complete_audit(p_id bigint, p_ok boolean, p_detail text default null)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  perform mcp_require_admin();

  update mcp_audit_log
     set ok = p_ok,
         detail = left(p_detail, 500)
   where id = p_id;

  if not found then
    raise exception 'audit row not found';
  end if;

  return;
end $$;

comment on function mcp_complete_audit(bigint, boolean, text) is
  'Admin-only completion of one audit row: fills ok and left(detail, 500); raises ''audit row not found'' for an unknown id.';


-- ----------------------------------------------------------------------------
-- mcp_list_audit: same signature, now also returns ok + detail (explicit
-- column list kept in sync).
-- ----------------------------------------------------------------------------
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
        select id, tool, args, ok, detail, created_at
        from mcp_audit_log
        order by id desc
        limit capped
      ) t
    ),
    '[]'::jsonb
  );
end $$;

comment on function mcp_list_audit(int) is
  'Admin-only read of the newest MCP audit rows (newest first, max 100) including the two-phase outcome (ok + detail).';


-- ----------------------------------------------------------------------------
-- Permissions: only authenticated users may execute; the admin check runs
-- inside every function, so non-admin roles get 'admin only'.
-- (mcp_log_audit lost its grants in the drop above: re-applied here.)
-- ----------------------------------------------------------------------------
revoke execute on function
  mcp_get_settings(),
  mcp_set_writes_enabled(boolean),
  mcp_create_room(text, int, text, int, text),
  mcp_update_room(uuid, text, int, text, int, text),
  mcp_delete_room(uuid),
  mcp_update_ticket(uuid, text, text),
  mcp_log_audit(text, jsonb),
  mcp_complete_audit(bigint, boolean, text),
  mcp_list_audit(int)
from public, anon;

grant execute on function
  mcp_get_settings(),
  mcp_set_writes_enabled(boolean),
  mcp_create_room(text, int, text, int, text),
  mcp_update_room(uuid, text, int, text, int, text),
  mcp_delete_room(uuid),
  mcp_update_ticket(uuid, text, text),
  mcp_log_audit(text, jsonb),
  mcp_complete_audit(bigint, boolean, text),
  mcp_list_audit(int)
to authenticated;


-- ============================================================================
-- How to verify (SUPABASE_URL + SUPABASE_ANON_KEY from mcp/.env):
--   Run: & "mcp\.venv\Scripts\python.exe" "mcp-worker\scripts\verify_db_write.py"
--   (admin password grant; exercises settings, scratch-room lifecycle,
--   negative probes and the two-phase audit; always restores the off-switch).
--
-- Rollback (manual, if ever needed):
--   see the header block.
-- ============================================================================
