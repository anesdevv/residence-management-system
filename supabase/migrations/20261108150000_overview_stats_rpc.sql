-- Migration: 20261108150000_overview_stats_rpc.sql
-- Description: Consolidated overview statistics RPC returning all dashboard KPIs in a single round trip.
-- Security: security invoker (respects caller privileges and RLS).
-- Staff/Admin Check: enforces caller authorization.
-- Rollback SQL provided in docs/performance.md and documented below.

create or replace function public.overview_stats()
returns jsonb
language plpgsql
stable
security invoker
set search_path = public, pg_temp
as $$
declare
  v_pending bigint;
  v_reports bigint;
  v_requests bigint;
  v_occupancy bigint;
begin
  if not is_staff() then
    raise exception 'not authorized';
  end if;

  -- 1. Pending student applications
  select count(*) into v_pending
  from students
  where status = 'pending';

  -- 2. Open / unresolved maintenance tickets
  select count(*) into v_reports
  from maintenance_reports
  where status <> 'resolved';

  -- 3. Pending room change requests
  select count(*) into v_requests
  from room_change_requests
  where status = 'pending';

  -- 4. Occupied bed count across the residence
  select count(*) into v_occupancy
  from students
  where status = 'active' and room_id is not null;

  return jsonb_build_object(
    'pending', coalesce(v_pending, 0),
    'reports', coalesce(v_reports, 0),
    'requests', coalesce(v_requests, 0),
    'occupancy', coalesce(v_occupancy, 0)
  );
end;
$$;

comment on function public.overview_stats() is
  'Returns consolidated KPI counters (pending students, open maintenance reports, pending transfers, occupied beds) for the staff dashboard in a single database round trip.';

grant execute on function public.overview_stats() to authenticated;
