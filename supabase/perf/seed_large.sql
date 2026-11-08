-- ============================================================================
-- RÉSIVO Local Performance Testing Large Seed
-- (NOT A MIGRATION — FOR LOCAL PERFORMANCE TESTING & BENCHMARKING ONLY)
--
-- Volume:
--   - 20 Blocks (A..T)
--   - 5,000 Rooms (250 rooms per block, capacity 1..3, gender matched to block)
--   - 20,000 Students (auth.users, profiles, students: pending/active/rejected)
--   - 50,000 Maintenance Reports (plumbing, electrical, furniture, etc.)
--   - 5,000 Official Admissions Roster Records
--   - 5,000 Room Change Requests
-- ============================================================================

do $$
declare
  b_idx int;
  b_char text;
  b_gender gender;
begin
  -- 1. Seed Blocks (20 blocks)
  for b_idx in 1..20 loop
    b_char := chr(64 + b_idx); -- 'A'..'T'
    b_gender := case when (b_idx % 2 = 1) then 'male'::gender else 'female'::gender end;
    insert into public.blocks (name, gender, description)
    values (
      b_char,
      b_gender,
      'Residential Block ' || b_char || ' for ' || b_gender::text || ' students'
    )
    on conflict (name) do nothing;
  end loop;

  -- 2. Seed Rooms (5,000 rooms across blocks A..T)
  insert into public.rooms (block, floor, number, capacity, gender)
  select
    chr(65 + (i % 20)) as block,
    (i % 5) as floor,
    lpad((100 + (i % 250))::text, 3, '0') as number,
    1 + (i % 3) as capacity,
    case when ((i % 20) % 2 = 0) then 'male'::gender else 'female'::gender end as gender
  from generate_series(1, 5000) as s(i)
  on conflict (block, number) do nothing;

  -- 3. Seed Profiles & Students (20,000 records)
  -- Note: In local Supabase Postgres, auth.users must exist for cascade FK
  insert into auth.users (id, email, raw_user_meta_data)
  select
    gen_random_uuid(),
    'student' || i || '@university.edu',
    jsonb_build_object('full_name', 'Student ' || i)
  from generate_series(1, 20000) as s(i)
  on conflict do nothing;

  insert into public.profiles (id, role)
  select u.id, 'student'::user_role
  from auth.users u
  where u.email like 'student%@university.edu'
  on conflict (id) do nothing;

  insert into public.students (
    id,
    card_id,
    first_name,
    last_name,
    birth_date,
    gender,
    phone,
    email,
    university,
    faculty,
    study_level,
    wilaya,
    status,
    rejection_reason,
    created_at
  )
  select
    p.id,
    'CARD-' || lpad(row_number() over ()::text, 7, '0'),
    'StudentFirst' || row_number() over (),
    'StudentLast' || row_number() over (),
    ('2000-01-01'::date + ((row_number() over () % 1500) || ' days')::interval)::date,
    case when (row_number() over () % 2 = 1) then 'male'::gender else 'female'::gender end,
    '0550' || lpad((row_number() over () % 1000000)::text, 6, '0'),
    'student' || row_number() over () || '@university.edu',
    'University of Tlemcen',
    case (row_number() over () % 4)
      when 0 then 'Computer Science'
      when 1 then 'Medicine'
      when 2 then 'Law'
      else 'Economics'
    end,
    case (row_number() over () % 6)
      when 0 then 'L1'::study_level
      when 1 then 'L2'::study_level
      when 2 then 'L3'::study_level
      when 3 then 'M1'::study_level
      when 4 then 'M2'::study_level
      else 'Doctorat'::study_level
    end,
    'Tlemcen',
    case (row_number() over () % 5)
      when 0 then 'pending'::student_status
      when 1 then 'rejected'::student_status
      else 'active'::student_status
    end,
    case when (row_number() over () % 5 = 1) then 'Did not meet residence distance requirements or missing residency certificate documentation.' else null end,
    now() - ((row_number() over () % 90) || ' days')::interval
  from public.profiles p
  where p.role = 'student'
  on conflict (card_id) do nothing;

  -- 4. Seed Official Admissions Roster (5,000 records)
  insert into public.official_residents (
    card_id,
    first_name,
    last_name,
    birth_date,
    gender,
    university,
    faculty
  )
  select
    'CARD-' || lpad(i::text, 7, '0'),
    'OfficialFirst' || i,
    'OfficialLast' || i,
    ('2000-01-01'::date + ((i % 1500) || ' days')::interval)::date,
    case when (i % 2 = 1) then 'male'::gender else 'female'::gender end,
    'University of Tlemcen',
    case (i % 4)
      when 0 then 'Computer Science'
      when 1 then 'Medicine'
      when 2 then 'Law'
      else 'Economics'
    end
  from generate_series(1, 5000) as s(i)
  on conflict (card_id) do nothing;

  -- 5. Seed Maintenance Reports (50,000 reports)
  insert into public.maintenance_reports (
    student_id,
    category,
    description,
    photo_path,
    status,
    staff_note,
    created_at
  )
  select
    s.id,
    case (i % 5)
      when 0 then 'plumbing'::maintenance_category
      when 1 then 'electrical'::maintenance_category
      when 2 then 'furniture'::maintenance_category
      when 3 then 'internet'::maintenance_category
      else 'other'::maintenance_category
    end,
    'Detailed fault description number ' || i || ': Resident reports continuous water dripping from the sink tap and bathroom pipe joints needing technician inspection.',
    case when (i % 3 = 0) then 'faults/photo_' || i || '.jpg' else null end,
    case (i % 4)
      when 0 then 'pending'::report_status
      when 1 then 'in_progress'::report_status
      else 'resolved'::report_status
    end,
    case when (i % 2 = 0) then 'Staff dispatch note: Technician assigned to inspect and replace gaskets during morning shift on floor.' else null end,
    now() - ((i % 180) || ' days')::interval
  from generate_series(1, 50000) as g(i)
  join (
    select id, row_number() over () as rn from public.students where status = 'active' limit 10000
  ) s on s.rn = (1 + (i % 10000));

  -- 6. Seed Room Change Requests (5,000 requests)
  insert into public.room_change_requests (
    student_id,
    reason,
    status,
    decision_note,
    created_at
  )
  select
    s.id,
    'Transfer request ' || i || ': Requesting room transfer to floor 2 to be closer to study group and medical facilities.',
    case (i % 3)
      when 0 then 'pending'::request_status
      when 1 then 'approved'::request_status
      else 'rejected'::request_status
    end,
    case when (i % 3 = 2) then 'Rejection desk note: Preferred room block currently at maximum bed capacity for academic term.' else null end,
    now() - ((i % 60) || ' days')::interval
  from generate_series(1, 5000) as g(i)
  join (
    select id, row_number() over () as rn from public.students where status = 'active' limit 5000
  ) s on s.rn = (1 + (i % 5000));

end $$;
