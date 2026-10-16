-- ============================================================================
-- Room invariant guards (plan A1).
-- Plan: docs/superpowers/plans/2026-10-16-mcp-write-tools.md
-- Spec: docs/superpowers/specs/2026-10-15-mcp-write-tools-design.md
--
-- Purpose:
--   * Turn the desktop app's UI-only room rules into real database rules:
--       - a room with active residents cannot be deleted;
--       - its capacity cannot drop below the active resident count;
--       - the gender of an occupied room cannot change.
--   * The MCP write tools (mcp_delete_room / mcp_update_room) rely on these
--     triggers, and the worker's friendly-error mapping matches the message
--     prefixes 'Cannot delete room', 'Cannot set capacity below' and
--     'Cannot change the gender'. Do not reword the raises without updating
--     that mapping.
--
-- Design rules:
--   * One trigger function rooms_guard() shared by two triggers:
--     rooms_guard_delete (BEFORE DELETE) and rooms_guard_update (BEFORE UPDATE).
--     "Occupied" means: a students row with room_id = the room and
--     status = 'active'.
--   * The guards raise plain exceptions (no custom SQLSTATE): the message text
--     is the contract. rooms.capacity also has a CHECK (capacity > 0); the
--     BEFORE UPDATE guard runs first, so callers see the guard's message.
--   * The embedded DO block is a self-test: it runs at db push time inside the
--     migration transaction, proves each guard fires (and that an empty room
--     still deletes), then rolls everything back. If a guard ever stops firing,
--     db push fails loudly.
--
-- Rollback (manual, if ever needed):
--   drop trigger if exists rooms_guard_delete on rooms;
--   drop trigger if exists rooms_guard_update on rooms;
--   drop function if exists rooms_guard();
-- ============================================================================


-- ----------------------------------------------------------------------------
-- Guard function: refuses room deletes/updates that would strand active
-- residents or break the room's occupancy invariants.
-- ----------------------------------------------------------------------------
create or replace function rooms_guard()
returns trigger language plpgsql as $$
declare
  v_active int;
begin
  if tg_op = 'DELETE' then
    select count(*) into v_active
    from students
    where room_id = old.id and status = 'active';

    if v_active > 0 then
      raise exception 'Cannot delete room %-%: % active resident(s) are still assigned.',
        old.block, old.number, v_active;
    end if;

    return old;
  end if;

  -- tg_op = 'UPDATE' (this function is only attached to delete/update)
  select count(*) into v_active
  from students
  where room_id = new.id and status = 'active';

  if new.capacity < v_active then
    raise exception 'Cannot set capacity below the % active resident(s) already assigned.',
      v_active;
  end if;

  if new.gender <> old.gender and v_active > 0 then
    raise exception 'Cannot change the gender of an occupied room.';
  end if;

  return new;
end $$;


-- ----------------------------------------------------------------------------
-- Triggers.
-- ----------------------------------------------------------------------------
create trigger rooms_guard_delete before delete on rooms
  for each row execute function rooms_guard();
create trigger rooms_guard_update before update on rooms
  for each row execute function rooms_guard();


-- ============================================================================
-- Self-test (runs once, at db push time, inside the migration transaction).
-- Scratch data only; the transaction rolls it back either way.
-- ============================================================================
do $$
declare
  v_user uuid := gen_random_uuid();
  v_room uuid;
  v_num text := 'SELFTEST-' || substr(md5(random()::text), 1, 8);
  v_ok boolean;
begin
  -- Scratch user; handle_new_user() then creates its profile + student row.
  insert into auth.users (id, instance_id, aud, role, email, encrypted_password,
                          email_confirmed_at, raw_app_meta_data, raw_user_meta_data)
  values (v_user, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
          v_num || '@selftest.local', crypt('x', gen_salt('bf')), now(),
          '{"provider":"email","providers":["email"]}'::jsonb,
          jsonb_build_object('card_id', v_num, 'first_name', 'Self', 'last_name', 'Test',
                             'birth_date', '2000-01-01', 'gender', 'male', 'phone', '0000000000',
                             'university', 'T', 'faculty', 'T', 'study_level', 'L1', 'wilaya', 'T'));
  insert into rooms (block, floor, number, capacity, gender)
  values ('SELFTEST', 0, v_num, 1, 'male') returning id into v_room;
  update students set status = 'active', room_id = v_room where id = v_user;

  -- 1. Deleting an occupied room must be blocked.
  v_ok := false;
  begin delete from rooms where id = v_room; exception when others then v_ok := true; end;
  if not v_ok then raise exception 'SELFTEST: deleting an occupied room was NOT blocked'; end if;

  -- 2. Capacity below occupancy must be blocked. Match the guard's own message:
  --    with capacity 1, the table CHECK (capacity > 0) would also fire at 0.
  v_ok := false;
  begin update rooms set capacity = 0 where id = v_room;
  exception when others then v_ok := sqlerrm like 'Cannot set capacity below%'; end;
  if not v_ok then raise exception 'SELFTEST: capacity below occupancy was NOT blocked'; end if;

  -- 3. Gender change on an occupied room must be blocked.
  v_ok := false;
  begin update rooms set gender = 'female' where id = v_room; exception when others then v_ok := true; end;
  if not v_ok then raise exception 'SELFTEST: gender change on an occupied room was NOT blocked'; end if;

  -- Unassign (cascades profile + student), then the now-empty room must delete cleanly.
  delete from auth.users where id = v_user;
  delete from rooms where id = v_room;
  if exists (select 1 from rooms where id = v_room) then
    raise exception 'SELFTEST: empty room delete did not work';
  end if;
end $$;
