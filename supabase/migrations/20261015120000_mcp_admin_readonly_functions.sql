-- ============================================================================
-- MCP admin tools (read-only) for the ChatGPT "Residence Tlemcen" connector.
-- Full documentation: mcp/README.md
--
-- Design rules (see docs/manual-test-mcp.md):
--   * security invoker -> the caller's RLS applies (admin users pass is_staff()
--     read policies on every table used here); no elevated privileges.
--   * stable           -> read-only by construction: no insert/update/delete.
--   * returns jsonb    -> shaped for the MCP server (mcp/server.py) and ChatGPT.
--   * every function raises 'admin only' (SQLSTATE 42501) unless the caller's
--     profiles.role is exactly 'admin' (reuses the existing auth_role() helper).
--   * free text (description, staff_note, reason, decision_note,
--     rejection_reason) is truncated to 500 chars in mcp/formatting.py.
--
-- Real table/column names (from migrations 20261009222455 .. 20261011112400):
--   profiles(role user_role: student|staff|admin)
--   staff(id, full_name)
--   students(id, card_id, first_name, last_name, birth_date, gender, phone,
--            email, university, faculty, study_level, wilaya,
--            status: pending|active|rejected, rejection_reason, room_id, created_at)
--   rooms(id, block, floor, number, capacity, gender)
--   maintenance_reports(id, student_id, category, description, photo_path,
--            status: pending|in_progress|resolved, staff_note, handled_by, created_at)
--   room_change_requests(id, student_id, current_room_id, preferred_room_id,
--            reason, status: pending|approved|rejected, decision_note, decided_at, created_at)
--   official_residents(card_id, first_name, last_name, birth_date, gender,
--            university, faculty)
--
-- Room label convention: "B-101" (block || '-' || number), matching the desktop UI.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- Shared guard: raises unless the caller is an administrator.
-- ----------------------------------------------------------------------------
create or replace function mcp_require_admin()
returns void
language plpgsql
stable
security invoker
set search_path = public, pg_temp
as $$
begin
  if auth_role() is distinct from 'admin' then
    raise exception 'admin only' using errcode = '42501';
  end if;
end $$;

comment on function mcp_require_admin() is
  'Raises "admin only" (SQLSTATE 42501) unless the caller''s profiles.role is exactly admin.';


-- ----------------------------------------------------------------------------
-- 1) Maintenance tickets with student and room details, newest first.
--    p_limit is capped to 1..100 (default 20).
--    Photo is returned as the storage path only (no signed URL).
-- ----------------------------------------------------------------------------
create or replace function mcp_list_tickets(p_status text default null, p_limit int default 20)
returns jsonb
language plpgsql
stable
security invoker
set search_path = public, pg_temp
as $$
declare
  v_limit int;
begin
  perform mcp_require_admin();

  if p_status is not null and p_status not in ('pending', 'in_progress', 'resolved') then
    raise exception 'invalid status: % (expected pending, in_progress or resolved)', p_status
      using errcode = '22023';
  end if;

  v_limit := least(greatest(coalesce(p_limit, 20), 1), 100);

  return coalesce((
    select jsonb_agg(item)
    from (
      select jsonb_build_object(
        'id', t.id,
        'category', t.category,
        'description', t.description,
        'photo_path', t.photo_path,
        'status', t.status,
        'staff_note', t.staff_note,
        'created_at', t.created_at,
        'handled_by', st.full_name,
        'student', jsonb_build_object(
          'full_name', s.first_name || ' ' || s.last_name,
          'card_id', s.card_id,
          'phone', s.phone
        ),
        'room', case
          when r.id is null then null
          else jsonb_build_object(
            'block', r.block, 'floor', r.floor, 'number', r.number,
            'label', r.block || '-' || r.number)
        end
      ) as item
      from maintenance_reports t
      left join students s on s.id = t.student_id
      left join rooms r on r.id = s.room_id
      left join staff st on st.id = t.handled_by
      where p_status is null or t.status = p_status::report_status
      order by t.created_at desc
      limit v_limit
    ) newest
  ), '[]'::jsonb);
end $$;

comment on function mcp_list_tickets(text, int) is
  'Admin-only read-only list of maintenance tickets (optionally filtered by status), newest first. Max 100 rows.';


-- ----------------------------------------------------------------------------
-- 2) Room change requests with student, current and preferred room.
--    "current_room" is the student's live room (room_change_requests stores a
--    snapshot in current_room_id; the live value matches it while pending and
--    stays correct after approval/rejection).
-- ----------------------------------------------------------------------------
create or replace function mcp_list_room_changes(p_status text default null, p_limit int default 20)
returns jsonb
language plpgsql
stable
security invoker
set search_path = public, pg_temp
as $$
declare
  v_limit int;
begin
  perform mcp_require_admin();

  if p_status is not null and p_status not in ('pending', 'approved', 'rejected') then
    raise exception 'invalid status: % (expected pending, approved or rejected)', p_status
      using errcode = '22023';
  end if;

  v_limit := least(greatest(coalesce(p_limit, 20), 1), 100);

  return coalesce((
    select jsonb_agg(item)
    from (
      select jsonb_build_object(
        'id', rc.id,
        'student', jsonb_build_object(
          'full_name', s.first_name || ' ' || s.last_name,
          'card_id', s.card_id
        ),
        'reason', rc.reason,
        'status', rc.status,
        'decision_note', rc.decision_note,
        'created_at', rc.created_at,
        'decided_at', rc.decided_at,
        'current_room', case
          when cr.id is null then null
          else jsonb_build_object(
            'block', cr.block, 'floor', cr.floor, 'number', cr.number,
            'label', cr.block || '-' || cr.number)
        end,
        'preferred_room', case
          when pr.id is null then null
          else jsonb_build_object(
            'block', pr.block, 'floor', pr.floor, 'number', pr.number,
            'label', pr.block || '-' || pr.number)
        end
      ) as item
      from room_change_requests rc
      left join students s on s.id = rc.student_id
      left join rooms cr on cr.id = s.room_id
      left join rooms pr on pr.id = rc.preferred_room_id
      where p_status is null or rc.status = p_status::request_status
      order by rc.created_at desc
      limit v_limit
    ) newest
  ), '[]'::jsonb);
end $$;

comment on function mcp_list_room_changes(text, int) is
  'Admin-only read-only list of room change requests (optionally filtered by status), newest first. Max 100 rows.';


-- ----------------------------------------------------------------------------
-- 3) Pending registrations with all submitted fields plus official-list match.
--    official_list_match = card_id exists in official_residents
--    official_name_match = card_id exists AND first/last name match (case-insensitive)
-- ----------------------------------------------------------------------------
create or replace function mcp_list_pending_registrations(p_limit int default 20)
returns jsonb
language plpgsql
stable
security invoker
set search_path = public, pg_temp
as $$
declare
  v_limit int;
begin
  perform mcp_require_admin();

  v_limit := least(greatest(coalesce(p_limit, 20), 1), 100);

  return coalesce((
    select jsonb_agg(item)
    from (
      select jsonb_build_object(
        'id', s.id,
        'card_id', s.card_id,
        'full_name', s.first_name || ' ' || s.last_name,
        'first_name', s.first_name,
        'last_name', s.last_name,
        'birth_date', s.birth_date,
        'gender', s.gender,
        'phone', s.phone,
        'email', s.email,
        'university', s.university,
        'faculty', s.faculty,
        'study_level', s.study_level,
        'wilaya', s.wilaya,
        'created_at', s.created_at,
        'official_list_match', (o.card_id is not null),
        'official_name_match', (
          o.card_id is not null
          and lower(trim(o.first_name)) = lower(trim(s.first_name))
          and lower(trim(o.last_name)) = lower(trim(s.last_name))
        ),
        'official_record', case
          when o.card_id is null then null
          else jsonb_build_object(
            'first_name', o.first_name,
            'last_name', o.last_name,
            'birth_date', o.birth_date,
            'gender', o.gender,
            'university', o.university,
            'faculty', o.faculty)
        end
      ) as item
      from students s
      left join official_residents o on o.card_id = s.card_id
      where s.status = 'pending'
      order by s.created_at desc
      limit v_limit
    ) waiting
  ), '[]'::jsonb);
end $$;

comment on function mcp_list_pending_registrations(int) is
  'Admin-only read-only list of students waiting for approval, with official residents list match. Max 100 rows.';


-- ----------------------------------------------------------------------------
-- 4) Search students by name, card ID or room label (case-insensitive, partial).
--    Room label search e.g. "B-101" answers "which student is in room B-101?".
-- ----------------------------------------------------------------------------
create or replace function mcp_search_students(p_query text, p_limit int default 10)
returns jsonb
language plpgsql
stable
security invoker
set search_path = public, pg_temp
as $$
declare
  v_query text;
  v_like text;
  v_limit int;
begin
  perform mcp_require_admin();

  v_query := trim(coalesce(p_query, ''));
  if v_query = '' then
    raise exception 'query required' using errcode = '22023';
  end if;

  v_like := '%' || v_query || '%';
  v_limit := least(greatest(coalesce(p_limit, 10), 1), 100);

  return coalesce((
    select jsonb_agg(item)
    from (
      select jsonb_build_object(
        'id', s.id,
        'card_id', s.card_id,
        'full_name', s.first_name || ' ' || s.last_name,
        'first_name', s.first_name,
        'last_name', s.last_name,
        'birth_date', s.birth_date,
        'gender', s.gender,
        'phone', s.phone,
        'email', s.email,
        'university', s.university,
        'faculty', s.faculty,
        'study_level', s.study_level,
        'wilaya', s.wilaya,
        'status', s.status,
        'rejection_reason', s.rejection_reason,
        'created_at', s.created_at,
        'room', case
          when r.id is null then null
          else jsonb_build_object(
            'block', r.block, 'floor', r.floor, 'number', r.number,
            'label', r.block || '-' || r.number)
        end
      ) as item
      from students s
      left join rooms r on r.id = s.room_id
      where (s.first_name || ' ' || s.last_name) ilike v_like
         or (s.last_name || ' ' || s.first_name) ilike v_like
         or s.card_id ilike v_like
         or (r.block || '-' || r.number) ilike v_like
      order by s.last_name, s.first_name, s.card_id
      limit v_limit
    ) found
  ), '[]'::jsonb);
end $$;

comment on function mcp_search_students(text, int) is
  'Admin-only read-only student search by name, card ID or room label ("B-101"), case-insensitive partial. Max 100 rows.';


-- ----------------------------------------------------------------------------
-- 5) Rooms with capacity, occupancy and free places.
--    occupied = number of active students currently assigned to the room
--    (same definition as the desktop app). p_only_available keeps rooms with
--    free_places > 0.
-- ----------------------------------------------------------------------------
create or replace function mcp_list_rooms(p_block text default null, p_only_available boolean default false)
returns jsonb
language plpgsql
stable
security invoker
set search_path = public, pg_temp
as $$
begin
  perform mcp_require_admin();

  return coalesce((
    select jsonb_agg(item order by block, floor, number)
    from (
      select
        r.block, r.floor, r.number,
        jsonb_build_object(
          'block', r.block,
          'floor', r.floor,
          'number', r.number,
          'label', r.block || '-' || r.number,
          'capacity', r.capacity,
          'gender', r.gender,
          'occupied', coalesce(occ.n, 0),
          'free_places', r.capacity - coalesce(occ.n, 0)
        ) as item
      from rooms r
      left join (
        select room_id, count(*)::int as n
        from students
        where status = 'active' and room_id is not null
        group by room_id
      ) occ on occ.room_id = r.id
      where (p_block is null or upper(r.block) = upper(trim(p_block)))
        and (not coalesce(p_only_available, false) or coalesce(occ.n, 0) < r.capacity)
    ) availability
  ), '[]'::jsonb);
end $$;

comment on function mcp_list_rooms(text, boolean) is
  'Admin-only read-only room list with capacity, occupancy and free places; optional block filter and only-available filter.';


-- ----------------------------------------------------------------------------
-- 6) Overall summary: registrations, tickets, room changes, occupancy.
--    "rejected" counts students with status 'rejected'.
--    occupancy_percent = (active housed students / total capacity) * 100.
-- ----------------------------------------------------------------------------
create or replace function mcp_summary()
returns jsonb
language plpgsql
stable
security invoker
set search_path = public, pg_temp
as $$
declare
  v_capacity int;
  v_occupied int;
begin
  perform mcp_require_admin();

  select coalesce(sum(capacity), 0)::int into v_capacity from rooms;
  select count(*)::int into v_occupied
    from students
   where status = 'active' and room_id is not null;

  return jsonb_build_object(
    'pending_registrations', (select count(*) from students where status = 'pending'),
    'active_residents', (select count(*) from students where status = 'active'),
    'rejected', (select count(*) from students where status = 'rejected'),
    'tickets_pending', (select count(*) from maintenance_reports where status = 'pending'),
    'tickets_in_progress', (select count(*) from maintenance_reports where status = 'in_progress'),
    'tickets_resolved', (select count(*) from maintenance_reports where status = 'resolved'),
    'room_changes_pending', (select count(*) from room_change_requests where status = 'pending'),
    'total_capacity', v_capacity,
    'total_occupied', v_occupied,
    'occupancy_percent', case
      when v_capacity > 0 then round(100.0 * v_occupied / v_capacity, 1)
      else null
    end,
    'blocks', coalesce((
      select jsonb_agg(jsonb_build_object(
        'block', x.block,
        'capacity', x.capacity,
        'occupied', x.occupied,
        'occupancy_percent', case
          when x.capacity > 0 then round(100.0 * x.occupied / x.capacity, 1)
          else null
        end
      ) order by x.block)
      from (
        select
          r.block,
          sum(r.capacity)::int as capacity,
          coalesce(sum(occ.n), 0)::int as occupied
        from rooms r
        left join (
          select room_id, count(*)::int as n
          from students
          where status = 'active' and room_id is not null
          group by room_id
        ) occ on occ.room_id = r.id
        group by r.block
      ) x
    ), '[]'::jsonb)
  );
end $$;

comment on function mcp_summary() is
  'Admin-only read-only overview: registrations, tickets, room changes and occupancy totals plus per-block occupancy.';


-- ----------------------------------------------------------------------------
-- Permissions: only authenticated users may execute; the admin check runs
-- inside every function, so non-admin roles get 'admin only'.
-- ----------------------------------------------------------------------------
revoke execute on function
  mcp_require_admin(),
  mcp_list_tickets(text, int),
  mcp_list_room_changes(text, int),
  mcp_list_pending_registrations(int),
  mcp_search_students(text, int),
  mcp_list_rooms(text, boolean),
  mcp_summary()
from public, anon;

grant execute on function
  mcp_require_admin(),
  mcp_list_tickets(text, int),
  mcp_list_room_changes(text, int),
  mcp_list_pending_registrations(int),
  mcp_search_students(text, int),
  mcp_list_rooms(text, boolean),
  mcp_summary()
to authenticated;


-- ============================================================================
-- How to verify with the seeded admin account (scripts/seed.py):
--   admin: admin@residence.test / Admin1234!
--   staff: staff@residence.test / Staff1234!   (must be refused)
--
-- Quick check in the SQL editor (runs as postgres, bypasses the auth check):
--   select mcp_summary();
--
-- REST check as the admin (SUPABASE_URL + SUPABASE_ANON_KEY from .env):
--   1. TOKEN=$(curl -s -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
--        -H "apikey: $SUPABASE_ANON_KEY" -H "Content-Type: application/json" \
--        -d '{"email":"admin@residence.test","password":"Admin1234!"}' | jq -r .access_token)
--   2. curl -s "$SUPABASE_URL/rest/v1/rpc/mcp_summary" \
--        -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $TOKEN" \
--        -H "Content-Type: application/json" -d '{}'
--   3. Repeat with:
--        mcp_list_tickets         '{"p_status":"pending","p_limit":5}'
--        mcp_list_room_changes    '{"p_status":"pending"}'
--        mcp_list_pending_registrations  '{"p_limit":5}'
--        mcp_search_students      '{"p_query":"Benali"}'
--        mcp_list_rooms           '{"p_block":"B","p_only_available":true}'
--   4. Negative check: same calls with a staff/student token return
--      {"code":"42501","message":"admin only"}.
--      Without any token they return a 401 from PostgREST.
--
-- Rollback (manual, if ever needed):
--   drop function if exists mcp_summary();
--   drop function if exists mcp_list_rooms(text, boolean);
--   drop function if exists mcp_search_students(text, int);
--   drop function if exists mcp_list_pending_registrations(int);
--   drop function if exists mcp_list_room_changes(text, int);
--   drop function if exists mcp_list_tickets(text, int);
--   drop function if exists mcp_require_admin();
-- ============================================================================
