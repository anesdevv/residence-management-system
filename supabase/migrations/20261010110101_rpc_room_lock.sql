create or replace function approve_student(p_student uuid, p_room uuid)
returns students language plpgsql security definer set search_path = public as $$
declare s students; r rooms; occ int;
begin
  if not is_staff() then raise exception 'not authorized'; end if;
  select * into s from students where id = p_student for update;
  if s is null then raise exception 'student not found'; end if;
  select * into r from rooms where id = p_room for update;
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

create or replace function approve_room_change(p_request uuid, p_room uuid)
returns room_change_requests language plpgsql security definer set search_path = public as $$
declare req room_change_requests; s students; r rooms; occ int;
begin
  if not is_staff() then raise exception 'not authorized'; end if;
  select * into req from room_change_requests where id = p_request and status = 'pending' for update;
  if req is null then raise exception 'pending request not found'; end if;
  select * into s from students where id = req.student_id;
  select * into r from rooms where id = p_room for update;
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
