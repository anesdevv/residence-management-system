-- Restrict inserting maintenance reports and room-change requests to active students only.

drop policy if exists maint_self_insert on maintenance_reports;
create policy maint_self_insert on maintenance_reports for insert
  with check (
    student_id = auth.uid()
    and status = 'pending'
    and exists (
      select 1 from students s
      where s.id = auth.uid() and s.status = 'active'
    )
  );

drop policy if exists rcr_self_insert on room_change_requests;
create policy rcr_self_insert on room_change_requests for insert
  with check (
    student_id = auth.uid()
    and status = 'pending'
    and exists (
      select 1 from students s
      where s.id = auth.uid() and s.status = 'active' and s.room_id is not null
    )
  );
