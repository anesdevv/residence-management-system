alter table profiles enable row level security;
alter table staff enable row level security;
alter table rooms enable row level security;
alter table students enable row level security;
alter table maintenance_reports enable row level security;
alter table room_change_requests enable row level security;
alter table official_residents enable row level security;

-- profiles: self read, staff read all
create policy profiles_self_select on profiles for select using (id = auth.uid());
create policy profiles_staff_select on profiles for select using (is_staff());

-- staff: staff read all; self read
create policy staff_self_select on staff for select using (id = auth.uid());
create policy staff_staff_select on staff for select using (is_staff());

-- rooms: any authenticated user may read; staff manage
create policy rooms_auth_select on rooms for select using (auth.role() = 'authenticated');
create policy rooms_staff_write on rooms for all using (is_staff()) with check (is_staff());

-- students: self read, staff read/update all
create policy students_self_select on students for select using (id = auth.uid());
create policy students_staff_select on students for select using (is_staff());
create policy students_staff_update on students for update using (is_staff()) with check (is_staff());

-- maintenance_reports: student owns, staff manage
create policy maint_self_select on maintenance_reports for select using (student_id = auth.uid());
create policy maint_self_insert on maintenance_reports for insert
  with check (student_id = auth.uid() and status = 'pending');
create policy maint_staff_all on maintenance_reports for all using (is_staff()) with check (is_staff());

-- room_change_requests: student owns, staff manage
create policy rcr_self_select on room_change_requests for select using (student_id = auth.uid());
create policy rcr_self_insert on room_change_requests for insert
  with check (student_id = auth.uid() and status = 'pending');
create policy rcr_staff_all on room_change_requests for all using (is_staff()) with check (is_staff());

-- official_residents: staff (incl. admin) read; admin write
create policy official_staff_select on official_residents for select using (is_staff());
create policy official_admin_write on official_residents for all
  using (auth_role() = 'admin') with check (auth_role() = 'admin');
