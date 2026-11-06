-- Migration: 20261104171500_fix_triggers_and_room_change_index.sql
-- Description:
-- 1. Fix trigger execution order between block gender sync and room occupancy guards,
--    ensuring occupied rooms cannot have their gender changed via block reassignment.
-- 2. Add partial unique index to prevent duplicate pending room change requests.

-- 1. Update sync_room_gender_from_block with explicit active resident check
create or replace function sync_room_gender_from_block()
returns trigger language plpgsql as $$
declare
  b_gender gender;
  v_active int;
begin
  select gender into b_gender from blocks where name = new.block;
  if b_gender is not null then
    if tg_op = 'UPDATE' and b_gender <> old.gender then
      select count(*) into v_active from students where room_id = old.id and status = 'active';
      if v_active > 0 then
        raise exception 'Cannot change the gender of an occupied room.';
      end if;
    end if;
    new.gender := b_gender;
  end if;
  return new;
end;
$$;

-- Drop legacy trigger name (which sorted after rooms_guard_update alphabetically)
drop trigger if exists trigger_sync_room_gender on rooms;
drop trigger if exists rooms_a_sync_gender on rooms;

-- Create trigger with name starting with 'rooms_a' so it runs before 'rooms_guard_update' ('rooms_g')
create trigger rooms_a_sync_gender before insert or update on rooms
  for each row execute function sync_room_gender_from_block();

-- 2. Prevent concurrent duplicate pending room change petitions
create unique index if not exists idx_one_pending_room_change
  on room_change_requests(student_id)
  where status = 'pending';
