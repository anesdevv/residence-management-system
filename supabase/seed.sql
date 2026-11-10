-- ============================================================================
-- RÉSIVO Local Development Seed Data (Single-Gender Mode)
-- ============================================================================
-- Contains:
-- 1. Residence-wide settings (single-gender 'male')
-- 2. Residential blocks (A and B) and dorm rooms
-- 3. Official university admissions roster records for cross-verification
-- 4. Staff & Administrator accounts (real emails, confirmed)
-- 5. Active & Pending student accounts (single-gender 'male')
-- 6. Legacy student account with synthetic @students.residence.local email
--    for testing the legacy migration /account/add-email gating flow
-- 7. Sample maintenance reports
-- ============================================================================

create extension if not exists "pgcrypto";

-- 1. Single-Gender Residence Setting
insert into public.residence_settings (id, residence_name, residence_gender)
values (1, 'Cité Universitaire · Tlemcen', 'male')
on conflict (id) do update
  set residence_name = excluded.residence_name,
      residence_gender = excluded.residence_gender;

-- 2. Blocks & Rooms
insert into public.blocks (name, gender, description)
values
  ('A', 'male', 'Residence Block A'),
  ('B', 'male', 'Residence Block B')
on conflict (name) do update
  set gender = excluded.gender,
      description = excluded.description;

insert into public.rooms (id, block, floor, number, capacity, gender)
values
  ('11111111-0000-0000-0000-000000000001', 'A', 1, '101', 2, 'male'),
  ('11111111-0000-0000-0000-000000000002', 'A', 1, '102', 2, 'male'),
  ('11111111-0000-0000-0000-000000000003', 'A', 1, '103', 2, 'male'),
  ('22222222-0000-0000-0000-000000000001', 'B', 1, '101', 2, 'male'),
  ('22222222-0000-0000-0000-000000000002', 'B', 1, '102', 2, 'male'),
  ('22222222-0000-0000-0000-000000000003', 'B', 1, '103', 2, 'male')
on conflict (block, number) do nothing;

-- 3. Official Admissions Roster Records
insert into public.official_residents (
  card_id, first_name, last_name, birth_date, gender, university, faculty
)
values
  ('202338012345', 'Karim', 'Benali', '2003-04-12', 'male', 'Université Abou Bekr Belkaïd', 'Faculté des Sciences'),
  ('202338067890', 'Bilal', 'Mansouri', '2004-09-20', 'male', 'Université Abou Bekr Belkaïd', 'Faculté de Technologie'),
  ('202338099111', 'Yacine', 'Amrani', '2002-11-05', 'male', 'Université Abou Bekr Belkaïd', 'Faculté des Sciences Économiques'),
  ('202138099888', 'Tariq', 'Meghazi', '2001-01-15', 'male', 'Université Abou Bekr Belkaïd', 'Faculté de Médecine')
on conflict (card_id) do nothing;

-- 4. Staff & Administrator Accounts
-- Passwords: 'Staff1234!'
do $$
declare
  admin_id uuid := 'a0000000-0000-0000-0000-000000000001';
  staff_id uuid := 'a0000000-0000-0000-0000-000000000002';
  pw_hash text := crypt('Staff1234!', gen_salt('bf'));
begin
  -- Admin
  insert into auth.users (
    id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at
  ) values (
    admin_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
    'admin@residence.test', pw_hash, now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"full_name":"Residence Director","role":"admin"}'::jsonb,
    now(), now()
  ) on conflict (id) do update set email = excluded.email;

  insert into public.profiles (id, role)
  values (admin_id, 'admin')
  on conflict (id) do update set role = 'admin';

  insert into public.staff (id, full_name, position)
  values (admin_id, 'Residence Director', 'Chief Housing Administrator')
  on conflict (id) do nothing;

  -- Staff
  insert into auth.users (
    id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at
  ) values (
    staff_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
    'staff@residence.test', pw_hash, now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"full_name":"Front Desk Officer","role":"staff"}'::jsonb,
    now(), now()
  ) on conflict (id) do update set email = excluded.email;

  insert into public.profiles (id, role)
  values (staff_id, 'staff')
  on conflict (id) do update set role = 'staff';

  insert into public.staff (id, full_name, position)
  values (staff_id, 'Front Desk Officer', 'Student Admissions Officer')
  on conflict (id) do nothing;
end $$;

-- 5. Student Accounts (all single-gender 'male'; gender populated automatically)
-- Passwords: 'Password123!'
do $$
declare
  s1_id uuid := 'c0000000-0000-0000-0000-000000000001';
  s2_id uuid := 'c0000000-0000-0000-0000-000000000002';
  s3_id uuid := 'c0000000-0000-0000-0000-000000000003';
  s4_id uuid := 'c0000000-0000-0000-0000-000000000004';
  pw_hash text := crypt('Password123!', gen_salt('bf'));
begin
  -- S1: Karim Benali (Active resident with real confirmed email)
  insert into auth.users (
    id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at
  ) values (
    s1_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
    'karim.benali@univ-tlemcen.dz', pw_hash, now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"card_id":"202338012345","first_name":"Karim","last_name":"Benali","birth_date":"2003-04-12","phone":"0555123456","university":"Université Abou Bekr Belkaïd","faculty":"Faculté des Sciences","study_level":"L3","wilaya":"Tlemcen"}'::jsonb,
    now(), now()
  ) on conflict (id) do update set email = excluded.email;

  update public.students
  set status = 'active', room_id = '11111111-0000-0000-0000-000000000001'
  where id = s1_id;

  -- S2: Bilal Mansouri (Pending applicant with real confirmed email)
  insert into auth.users (
    id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at
  ) values (
    s2_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
    'bilal.mansouri@univ-tlemcen.dz', pw_hash, now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"card_id":"202338067890","first_name":"Bilal","last_name":"Mansouri","birth_date":"2004-09-20","phone":"0666987654","university":"Université Abou Bekr Belkaïd","faculty":"Faculté de Technologie","study_level":"L2","wilaya":"Oran"}'::jsonb,
    now(), now()
  ) on conflict (id) do update set email = excluded.email;

  update public.students
  set status = 'pending', room_id = null
  where id = s2_id;

  -- S3: Yacine Amrani (Active resident with real confirmed email)
  insert into auth.users (
    id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at
  ) values (
    s3_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
    'yacine.amrani@univ-tlemcen.dz', pw_hash, now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"card_id":"202338099111","first_name":"Yacine","last_name":"Amrani","birth_date":"2002-11-05","phone":"0777112233","university":"Université Abou Bekr Belkaïd","faculty":"Faculté des Sciences Économiques","study_level":"M1","wilaya":"Sidi Bel Abbès"}'::jsonb,
    now(), now()
  ) on conflict (id) do update set email = excluded.email;

  update public.students
  set status = 'active', room_id = '11111111-0000-0000-0000-000000000002'
  where id = s3_id;

  -- S4: Tariq Meghazi (LEGACY FAKE EMAIL USER FOR TESTING /account/add-email)
  insert into auth.users (
    id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at
  ) values (
    s4_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
    '202138099888@students.residence.local', pw_hash, now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"card_id":"202138099888","first_name":"Tariq","last_name":"Meghazi","birth_date":"2001-01-15","phone":"0555334455","university":"Université Abou Bekr Belkaïd","faculty":"Faculté de Médecine","study_level":"Doctorat","wilaya":"Mostaganem"}'::jsonb,
    now(), now()
  ) on conflict (id) do update set email = excluded.email;

  update public.students
  set status = 'active', room_id = '11111111-0000-0000-0000-000000000003', email = null
  where id = s4_id;
end $$;

-- 6. Sample Maintenance Reports
insert into public.maintenance_reports (id, student_id, category, description, status, created_at)
values
  (
    'd0000000-0000-0000-0000-000000000001',
    'c0000000-0000-0000-0000-000000000001',
    'plumbing',
    'Bathroom faucet leak: continuous water dripping in bathroom sink basin.',
    'pending',
    now() - interval '2 days'
  ),
  (
    'd0000000-0000-0000-0000-000000000002',
    'c0000000-0000-0000-0000-000000000003',
    'electrical',
    'Desk socket outlet unpowered: main study desk electrical socket has no current.',
    'in_progress',
    now() - interval '5 days'
  )
on conflict (id) do nothing;
