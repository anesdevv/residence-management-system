-- ============================================================================
-- RÉSIVO Local Development Seed Data
-- ============================================================================
-- Contains:
-- 1. Residential blocks (A for boys, B for girls) and dorm rooms
-- 2. Official university admissions roster records for cross-verification
-- 3. Staff & Administrator accounts (real emails, confirmed)
-- 4. Active & Pending student accounts with verified realistic university emails
-- 5. Legacy student account with synthetic @students.residence.local email
--    for testing the legacy migration /add-email gating flow
-- ============================================================================

-- Extensions check
create extension if not exists "pgcrypto";

-- 1. Blocks & Rooms
insert into public.blocks (name, gender, description)
values
  ('A', 'male', 'Men''s Residence Block A'),
  ('B', 'female', 'Women''s Residence Block B')
on conflict (name) do update set gender = excluded.gender;

insert into public.rooms (id, block, floor, number, capacity, gender)
values
  ('11111111-0000-0000-0000-000000000001', 'A', 1, '101', 2, 'male'),
  ('11111111-0000-0000-0000-000000000002', 'A', 1, '102', 2, 'male'),
  ('11111111-0000-0000-0000-000000000003', 'A', 1, '103', 2, 'male'),
  ('22222222-0000-0000-0000-000000000001', 'B', 1, '101', 2, 'female'),
  ('22222222-0000-0000-0000-000000000002', 'B', 1, '102', 2, 'female'),
  ('22222222-0000-0000-0000-000000000003', 'B', 1, '103', 2, 'female')
on conflict (block, number) do nothing;

-- 2. Official Admissions Roster Records
insert into public.official_residents (card_id, full_name, faculty, wilaya)
values
  ('202338012345', 'Karim Benali', 'Faculté des Sciences', 'Tlemcen'),
  ('202338067890', 'Amina Mansouri', 'Faculté de Technologie', 'Oran'),
  ('202338099111', 'Yacine Amrani', 'Faculté des Sciences Économiques', 'Sidi Bel Abbès'),
  ('202138099888', 'Tariq Meghazi', 'Faculté de Médecine', 'Mostaganem')
on conflict (card_id) do nothing;

-- 3. Staff & Administrator Accounts
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

-- 4. Student Accounts
-- Passwords: 'Password123!'
do $$
declare
  s1_id uuid := 's0000000-0000-0000-0000-000000000001';
  s2_id uuid := 's0000000-0000-0000-0000-000000000002';
  s3_id uuid := 's0000000-0000-0000-0000-000000000003';
  s4_id uuid := 's0000000-0000-0000-0000-000000000004';
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
    '{"card_id":"202338012345","first_name":"Karim","last_name":"Benali"}'::jsonb,
    now(), now()
  ) on conflict (id) do update set email = excluded.email;

  insert into public.profiles (id, role) values (s1_id, 'student')
  on conflict (id) do nothing;

  insert into public.students (
    id, card_id, first_name, last_name, birth_date, gender, phone, email,
    university, faculty, study_level, wilaya, status, room_id
  ) values (
    s1_id, '202338012345', 'Karim', 'Benali', '2003-04-12', 'male', '0555123456',
    'karim.benali@univ-tlemcen.dz', 'Université Abou Bekr Belkaïd', 'Faculté des Sciences',
    'L3', 'Tlemcen', 'active', '11111111-0000-0000-0000-000000000001'
  ) on conflict (card_id) do update set email = excluded.email;

  -- S2: Amina Mansouri (Pending applicant with real confirmed email)
  insert into auth.users (
    id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at
  ) values (
    s2_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
    'amina.mansouri@univ-tlemcen.dz', pw_hash, now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"card_id":"202338067890","first_name":"Amina","last_name":"Mansouri"}'::jsonb,
    now(), now()
  ) on conflict (id) do update set email = excluded.email;

  insert into public.profiles (id, role) values (s2_id, 'student')
  on conflict (id) do nothing;

  insert into public.students (
    id, card_id, first_name, last_name, birth_date, gender, phone, email,
    university, faculty, study_level, wilaya, status, room_id
  ) values (
    s2_id, '202338067890', 'Amina', 'Mansouri', '2004-09-20', 'female', '0666987654',
    'amina.mansouri@univ-tlemcen.dz', 'Université Abou Bekr Belkaïd', 'Faculté de Technologie',
    'L2', 'Oran', 'pending', null
  ) on conflict (card_id) do update set email = excluded.email;

  -- S3: Yacine Amrani (Active resident with real confirmed email)
  insert into auth.users (
    id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at
  ) values (
    s3_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
    'yacine.amrani@univ-tlemcen.dz', pw_hash, now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"card_id":"202338099111","first_name":"Yacine","last_name":"Amrani"}'::jsonb,
    now(), now()
  ) on conflict (id) do update set email = excluded.email;

  insert into public.profiles (id, role) values (s3_id, 'student')
  on conflict (id) do nothing;

  insert into public.students (
    id, card_id, first_name, last_name, birth_date, gender, phone, email,
    university, faculty, study_level, wilaya, status, room_id
  ) values (
    s3_id, '202338099111', 'Yacine', 'Amrani', '2002-11-05', 'male', '0777112233',
    'yacine.amrani@univ-tlemcen.dz', 'Université Abou Bekr Belkaïd', 'Faculté des Sciences Économiques',
    'M1', 'Sidi Bel Abbès', 'active', '11111111-0000-0000-0000-000000000002'
  ) on conflict (card_id) do update set email = excluded.email;

  -- S4: Tariq Meghazi (LEGACY FAKE EMAIL USER FOR TESTING /account/add-email)
  insert into auth.users (
    id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at
  ) values (
    s4_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
    '202138099888@students.residence.local', pw_hash, now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"card_id":"202138099888","first_name":"Tariq","last_name":"Meghazi"}'::jsonb,
    now(), now()
  ) on conflict (id) do update set email = excluded.email;

  insert into public.profiles (id, role) values (s4_id, 'student')
  on conflict (id) do nothing;

  insert into public.students (
    id, card_id, first_name, last_name, birth_date, gender, phone, email,
    university, faculty, study_level, wilaya, status, room_id
  ) values (
    s4_id, '202138099888', 'Tariq', 'Meghazi', '2001-01-15', 'male', '0555334455',
    null, 'Université Abou Bekr Belkaïd', 'Faculté de Médecine',
    'Doctorat', 'Mostaganem', 'active', '11111111-0000-0000-0000-000000000003'
  ) on conflict (card_id) do nothing;
end $$;

-- 5. Sample Maintenance Reports
insert into public.maintenance_reports (id, student_id, room_id, category, title, description, status, created_at)
values
  (
    'm0000000-0000-0000-0000-000000000001',
    's0000000-0000-0000-0000-000000000001',
    '11111111-0000-0000-0000-000000000001',
    'plumbing',
    'Bathroom faucet leak',
    'Continuous water dripping in bathroom sink basin.',
    'pending',
    now() - interval '2 days'
  ),
  (
    'm0000000-0000-0000-0000-000000000002',
    's0000000-0000-0000-0000-000000000003',
    '11111111-0000-0000-0000-000000000002',
    'electrical',
    'Desk socket outlet unpowered',
    'Main study desk electrical socket has no current.',
    'in_progress',
    now() - interval '5 days'
  )
on conflict (id) do nothing;
