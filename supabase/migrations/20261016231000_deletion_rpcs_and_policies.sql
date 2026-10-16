-- ============================================================================
-- Deletion RPCs and RLS Policies (Idempotent)
-- ============================================================================

-- RLS delete policies
drop policy if exists students_staff_delete on students;
create policy students_staff_delete on students for delete using (is_staff() and status in ('active', 'rejected'));

drop policy if exists profiles_staff_delete on profiles;
create policy profiles_staff_delete on profiles for delete using (is_staff() and role = 'student');

drop policy if exists profiles_admin_delete on profiles;
create policy profiles_admin_delete on profiles for delete using (auth_role() = 'admin');

drop policy if exists staff_admin_delete on staff;
create policy staff_admin_delete on staff for delete using (auth_role() = 'admin');

-- RPC: delete_student
create or replace function delete_student(p_student uuid)
returns void
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_student students;
begin
  if not is_staff() then
    raise exception 'not authorized';
  end if;

  select * into v_student from students where id = p_student for update;
  if v_student is null then
    raise exception 'student not found';
  end if;

  if v_student.status = 'pending' then
    raise exception 'cannot delete pending application; approve or reject first';
  end if;

  -- Clean up room change requests and maintenance reports
  delete from room_change_requests where student_id = p_student;
  delete from maintenance_reports where student_id = p_student;

  -- Unassign room
  update students set room_id = null where id = p_student;

  -- Delete student, profile, and auth user
  delete from students where id = p_student;
  delete from profiles where id = p_student;
  delete from auth.users where id = p_student;
end;
$$;

revoke execute on function delete_student(uuid) from public, anon;
grant execute on function delete_student(uuid) to authenticated;

-- RPC: delete_staff
create or replace function delete_staff(p_staff uuid)
returns void
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
begin
  if auth_role() is distinct from 'admin' then
    raise exception 'admin authorization required';
  end if;

  if p_staff = auth.uid() then
    raise exception 'cannot delete your own staff account';
  end if;

  delete from staff where id = p_staff;
  delete from profiles where id = p_staff;
  delete from auth.users where id = p_staff;
end;
$$;

revoke execute on function delete_staff(uuid) from public, anon;
grant execute on function delete_staff(uuid) to authenticated;
