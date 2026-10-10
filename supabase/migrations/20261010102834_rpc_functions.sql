create or replace function approve_student(p_student uuid, p_room uuid)
returns students language plpgsql security definer set search_path = public as $$
declare s students; r rooms; occ int;
begin
  if not is_staff() then raise exception 'not authorized'; end if;
  select * into s from students where id = p_student for update;
  if s is null then raise exception 'student not found'; end if;
  select * into r from rooms where id = p_room;
  if r is null then raise exception 'room not found'; end if;
  if r.gender <> s.gender then raise exception 'gender mismatch'; end if;
  select count(*) into occ from students
    where room_id = p_room and status = 'active' and id <> p_student;
  if occ >= r.capacity then raise exception 'room full'; end if;
  update students set status = 'active', room_id = p_room, rejection_reason = null,
    reviewed_by = auth.uid(), reviewed_at = now()
  where id = p_student returning * into s;
  return s;
end; $$;

create or replace function reject_student(p_student uuid, p_reason text)
returns students language plpgsql security definer set search_path = public as $$
declare s students;
begin
  if not is_staff() then raise exception 'not authorized'; end if;
  if p_reason is null or length(trim(p_reason)) = 0 then raise exception 'reason required'; end if;
  update students set status = 'rejected', rejection_reason = p_reason, room_id = null,
    reviewed_by = auth.uid(), reviewed_at = now()
  where id = p_student returning * into s;
  if s is null then raise exception 'student not found'; end if;
  return s;
end; $$;

create or replace function approve_room_change(p_request uuid, p_room uuid)
returns room_change_requests language plpgsql security definer set search_path = public as $$
declare req room_change_requests; s students; r rooms; occ int;
begin
  if not is_staff() then raise exception 'not authorized'; end if;
  select * into req from room_change_requests where id = p_request and status = 'pending' for update;
  if req is null then raise exception 'pending request not found'; end if;
  select * into s from students where id = req.student_id;
  select * into r from rooms where id = p_room;
  if r is null then raise exception 'room not found'; end if;
  if r.gender <> s.gender then raise exception 'gender mismatch'; end if;
  select count(*) into occ from students
    where room_id = p_room and status = 'active' and id <> s.id;
  if occ >= r.capacity then raise exception 'room full'; end if;
  update students set room_id = p_room where id = s.id;
  update room_change_requests set status = 'approved', decided_by = auth.uid(),
    decided_at = now(), decision_note = null
  where id = p_request returning * into req;
  return req;
end; $$;

create or replace function reject_room_change(p_request uuid, p_reason text)
returns room_change_requests language plpgsql security definer set search_path = public as $$
declare req room_change_requests;
begin
  if not is_staff() then raise exception 'not authorized'; end if;
  if p_reason is null or length(trim(p_reason)) = 0 then raise exception 'reason required'; end if;
  update room_change_requests set status = 'rejected', decision_note = p_reason,
    decided_by = auth.uid(), decided_at = now()
  where id = p_request and status = 'pending' returning * into req;
  if req is null then raise exception 'pending request not found'; end if;
  return req;
end; $$;

create or replace function update_my_contact(p_phone text, p_email text)
returns students language plpgsql security definer set search_path = public as $$
declare s students;
begin
  update students set phone = p_phone, email = nullif(p_email, '')
  where id = auth.uid() returning * into s;
  if s is null then raise exception 'student not found'; end if;
  return s;
end; $$;

create or replace function import_official_residents(p_rows jsonb)
returns int language plpgsql security definer set search_path = public as $$
declare n int;
begin
  if coalesce(auth_role()::text, '') <> 'admin' then raise exception 'admin only'; end if;
  insert into official_residents (card_id, first_name, last_name, birth_date, gender, university, faculty)
  select x->>'card_id', x->>'first_name', x->>'last_name',
         nullif(x->>'birth_date','')::date,
         nullif(x->>'gender','')::gender,
         x->>'university', x->>'faculty'
  from jsonb_array_elements(p_rows) as x
  on conflict (card_id) do update set
    first_name = excluded.first_name, last_name = excluded.last_name,
    birth_date = excluded.birth_date, gender = excluded.gender,
    university = excluded.university, faculty = excluded.faculty;
  get diagnostics n = row_count;
  return n;
end; $$;

grant execute on function
  approve_student(uuid, uuid),
  reject_student(uuid, text),
  approve_room_change(uuid, uuid),
  reject_room_change(uuid, text),
  update_my_contact(text, text),
  import_official_residents(jsonb)
to authenticated;
