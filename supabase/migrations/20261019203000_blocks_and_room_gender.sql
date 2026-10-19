-- ============================================================================
-- Residential Blocks and Automatic Room Gender Synchronization
-- ============================================================================

create table if not exists blocks (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  gender gender not null,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Trigger for updated_at
drop trigger if exists blocks_set_updated_at on blocks;
create trigger blocks_set_updated_at before update on blocks
  for each row execute function set_updated_at();

-- RLS policies
alter table blocks enable row level security;

drop policy if exists blocks_auth_select on blocks;
create policy blocks_auth_select on blocks for select using (auth.role() = 'authenticated');

drop policy if exists blocks_staff_write on blocks;
create policy blocks_staff_write on blocks for all using (is_staff()) with check (is_staff());

-- Populate existing blocks from current rooms table
insert into blocks (name, gender)
select distinct block, gender from rooms
on conflict (name) do update set gender = excluded.gender;

-- Automatically synchronize room gender to match block gender on insert or update
create or replace function sync_room_gender_from_block()
returns trigger language plpgsql as $$
declare
  b_gender gender;
begin
  select gender into b_gender from blocks where name = new.block;
  if b_gender is not null then
    new.gender := b_gender;
  end if;
  return new;
end;
$$;

drop trigger if exists trigger_sync_room_gender on rooms;
create trigger trigger_sync_room_gender before insert or update on rooms
  for each row execute function sync_room_gender_from_block();
