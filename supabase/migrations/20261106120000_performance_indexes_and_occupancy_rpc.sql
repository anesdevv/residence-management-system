-- Migration: 20261106120000_performance_indexes_and_occupancy_rpc.sql
-- Description: Performance optimization indexes and server-side room occupancy RPC.
-- Idempotent: uses IF NOT EXISTS and CREATE OR REPLACE.
-- Rollback SQL provided in docs/performance.md.

-- 1. Index for students status filtering and reverse-chronological ordering (used by live sync & pending queue)
create index if not exists idx_students_status_created
  on students (status, created_at desc);

-- 2. Partial index on students room_id for active residents (used by room occupancy and room allocations)
create index if not exists idx_students_room_id_active
  on students (room_id)
  where status = 'active';

-- 3. Index for student maintenance reports lookup in web student portal
create index if not exists idx_maintenance_reports_student_id
  on maintenance_reports (student_id);

-- 4. Index for maintenance queue status filtering and live sync
create index if not exists idx_maintenance_reports_status_created
  on maintenance_reports (status, created_at desc);

-- 5. Index for room change requests student lookup in web student portal
create index if not exists idx_room_change_requests_student_id
  on room_change_requests (student_id);

-- 6. Index for room change requests status filtering and live sync
create index if not exists idx_room_change_requests_status_created
  on room_change_requests (status, created_at desc);

-- 7. Foreign key indexes on room change requests
create index if not exists idx_room_change_requests_current_room_id
  on room_change_requests (current_room_id);

create index if not exists idx_room_change_requests_preferred_room_id
  on room_change_requests (preferred_room_id);

-- 8. Composite index on rooms for gender-segregated floor/block lookups
create index if not exists idx_rooms_gender_block_number
  on rooms (gender, block, number);

-- 9. RPC function for server-side room occupancy aggregation
create or replace function get_room_occupancy()
returns table(room_id uuid, occupied bigint)
language sql
stable
security definer
set search_path = public
as $$
  select room_id, count(*) as occupied
  from students
  where status = 'active' and room_id is not null
  group by room_id;
$$;

comment on function get_room_occupancy() is
  'Returns active student occupancy per room for fast staff dashboard metrics.';

grant execute on function get_room_occupancy() to authenticated;
