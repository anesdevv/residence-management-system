-- Migration: 20261108140000_fk_and_covering_indexes.sql
-- Description: Indexes for unindexed foreign keys and rooms multi-column sorting.
-- Idempotent: uses CREATE INDEX IF NOT EXISTS.
-- Rollback script provided in docs/performance.md and documented below.

-- 1. Index for foreign key students.room_id
-- Serves: Unconditional foreign key constraint on delete set null and room resident joins.
create index if not exists idx_students_room_id
  on students (room_id);

-- 2. Index for foreign key students.reviewed_by
-- Serves: ON DELETE SET NULL cascade on staff(id) deletion and application reviewer queries.
create index if not exists idx_students_reviewed_by
  on students (reviewed_by);

-- 3. Index for foreign key maintenance_reports.handled_by
-- Serves: ON DELETE SET NULL cascade on staff(id) deletion and ticket handler attribution joins.
create index if not exists idx_maintenance_reports_handled_by
  on maintenance_reports (handled_by);

-- 4. Index for foreign key room_change_requests.decided_by
-- Serves: ON DELETE SET NULL cascade on staff(id) deletion and desk inquiry decision note attribution.
create index if not exists idx_room_change_requests_decided_by
  on room_change_requests (decided_by);

-- 5. Non-unique composite index on rooms for block, floor, and number sorting
-- Serves: Desktop RoomsPage tree view and queries ordering by block, floor, and room number.
create index if not exists idx_rooms_block_floor_number
  on rooms (block, floor, number);
