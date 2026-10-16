-- ============================================================================
-- MCP read outputs expose room ids (plan A2).
-- Plan: docs/superpowers/plans/2026-10-16-mcp-write-tools.md
-- Spec: docs/superpowers/specs/2026-10-15-mcp-write-tools-design.md
--
-- Purpose:
--   * Every embedded room object in the four read functions below now carries
--     its rooms.id uuid, so the ChatGPT model can copy a room id straight from
--     a read output into the write tools' room_id arguments.
--   * Bodies are copied verbatim from
--     20261015120000_mcp_admin_readonly_functions.sql; the only change is the
--     added 'id' key in each room object (and, in mcp_list_rooms, the item
--     object). No other output changes.
--   * Same signatures -> create or replace keeps the existing revoke/grant
--     from 20261015120000_mcp_admin_readonly_functions.sql.
--
-- Rollback (manual, if ever needed): re-run the original definitions from
-- 20261015120000_mcp_admin_readonly_functions.sql (they omit the 'id' keys).
-- ============================================================================


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
            'id', r.id,
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
            'id', cr.id,
            'block', cr.block, 'floor', cr.floor, 'number', cr.number,
            'label', cr.block || '-' || cr.number)
        end,
        'preferred_room', case
          when pr.id is null then null
          else jsonb_build_object(
            'id', pr.id,
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
-- 3) Search students by name, card ID or room label (case-insensitive, partial).
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
            'id', r.id,
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
-- 4) Rooms with capacity, occupancy and free places.
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
          'id', r.id,
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
