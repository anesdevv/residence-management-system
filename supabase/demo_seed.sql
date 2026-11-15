-- ============================================================================
-- RÉSIVO Demo Seed Data (presentation dataset)
-- ============================================================================
-- Creates fictional accounts only. No real names, emails, or phone numbers.
--
-- Contents:
--   1. 4 extra female rooms in Block B (B-102, B-103, B-201, B-202)
--   2. 12 students: "Test Student 1" .. "Test Student 12"
--        - 7 active and assigned to rooms
--        - 4 pending approval
--        - 1 rejected with a reason
--   3. 8 maintenance tickets (pending / in_progress / resolved)
--   4. 5 room-change requests (pending / approved / rejected)
--
-- Login for any demo student:
--   Web:     card ID 90000001 .. 90000012
--   Desktop: email 90000001@students.residence.local .. (same card prefix)
--   Password: Test1234!
--
-- Safe to re-run: every row uses a deterministic ID and upserts.
-- Run with:
--   npx supabase db query --db-url "<db-url>" --yes --file supabase/demo_seed.sql
--
-- Cleanup (uncomment to remove the whole demo dataset):
--   delete from auth.users where id in (
--     'e0000000-0000-0000-0000-000000000001',
--     'e0000000-0000-0000-0000-000000000002',
--     'e0000000-0000-0000-0000-000000000003',
--     'e0000000-0000-0000-0000-000000000004',
--     'e0000000-0000-0000-0000-000000000005',
--     'e0000000-0000-0000-0000-000000000006',
--     'e0000000-0000-0000-0000-000000000007',
--     'e0000000-0000-0000-0000-000000000008',
--     'e0000000-0000-0000-0000-000000000009',
--     'e0000000-0000-0000-0000-000000000010',
--     'e0000000-0000-0000-0000-000000000011',
--     'e0000000-0000-0000-0000-000000000012'
--   );
--   delete from public.rooms
--   where id in (
--     'd1000000-0000-0000-0000-000000000001',
--     'd1000000-0000-0000-0000-000000000002',
--     'd1000000-0000-0000-0000-000000000003',
--     'd1000000-0000-0000-0000-000000000004'
--   );
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Extra female rooms in Block B
-- ----------------------------------------------------------------------------
INSERT INTO public.rooms (id, block, floor, number, capacity, gender)
VALUES
  ('d1000000-0000-0000-0000-000000000001', 'B', 1, '102', 2, 'female'),
  ('d1000000-0000-0000-0000-000000000002', 'B', 1, '103', 2, 'female'),
  ('d1000000-0000-0000-0000-000000000003', 'B', 2, '201', 2, 'female'),
  ('d1000000-0000-0000-0000-000000000004', 'B', 2, '202', 2, 'female')
ON CONFLICT (block, number) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 2. Demo students, their auth users and identities
-- ----------------------------------------------------------------------------
DO $$
DECLARE
  v_password text := extensions.crypt('Test1234!', extensions.gen_salt('bf'));
  v_staff uuid;
  rec record;
BEGIN
  SELECT id INTO v_staff FROM public.staff ORDER BY created_at LIMIT 1;

  FOR rec IN
    SELECT *
    FROM (VALUES
      (1,  'e0000000-0000-0000-0000-000000000001'::uuid, '90000001', 'active',   '101', 'L1'),
      (2,  'e0000000-0000-0000-0000-000000000002'::uuid, '90000002', 'active',   '102', 'L2'),
      (3,  'e0000000-0000-0000-0000-000000000003'::uuid, '90000003', 'active',   '102', 'L3'),
      (4,  'e0000000-0000-0000-0000-000000000004'::uuid, '90000004', 'active',   '103', 'M1'),
      (5,  'e0000000-0000-0000-0000-000000000005'::uuid, '90000005', 'active',   '103', 'M1'),
      (6,  'e0000000-0000-0000-0000-000000000006'::uuid, '90000006', 'active',   '201', 'M2'),
      (7,  'e0000000-0000-0000-0000-000000000007'::uuid, '90000007', 'active',   '202', 'L2'),
      (8,  'e0000000-0000-0000-0000-000000000008'::uuid, '90000008', 'pending',  NULL,  'L1'),
      (9,  'e0000000-0000-0000-0000-000000000009'::uuid, '90000009', 'pending',  NULL,  'L3'),
      (10, 'e0000000-0000-0000-0000-000000000010'::uuid, '90000010', 'pending',  NULL,  'M1'),
      (11, 'e0000000-0000-0000-0000-000000000011'::uuid, '90000011', 'pending',  NULL,  'Doctorat'),
      (12, 'e0000000-0000-0000-0000-000000000012'::uuid, '90000012', 'rejected', NULL,  'L2')
    ) AS t(n, id, card_id, status, room_number, study_level)
  LOOP
    -- Auth user. The on_auth_user_created trigger creates profiles + students.
    INSERT INTO auth.users (
      id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
      raw_app_meta_data, raw_user_meta_data,
      confirmation_token, recovery_token, email_change, email_change_token_new,
      email_change_token_current, phone_change, phone_change_token, reauthentication_token,
      created_at, updated_at
    ) VALUES (
      rec.id,
      '00000000-0000-0000-0000-000000000000',
      'authenticated',
      'authenticated',
      rec.card_id || '@students.residence.local',
      v_password,
      now(),
      '{"provider":"email","providers":["email"]}'::jsonb,
      jsonb_build_object(
        'card_id', rec.card_id,
        'first_name', 'Test',
        'last_name', 'Student ' || rec.n,
        'birth_date', to_char(date '2002-01-01' + (rec.n * 7), 'YYYY-MM-DD'),
        'phone', '0550' || lpad(rec.n::text, 6, '0'),
        'email', 'test.student' || rec.n || '@example.com',
        'university', 'Test University of Tlemcen',
        'faculty', 'Test Faculty of Science',
        'study_level', rec.study_level,
        'wilaya', 'Tlemcen'
      ),
      '', '', '', '', '', '', '', '',
      now() - (rec.n || ' days')::interval,
      now() - (rec.n || ' days')::interval
    )
    ON CONFLICT (id) DO UPDATE SET
      email = EXCLUDED.email,
      encrypted_password = EXCLUDED.encrypted_password,
      email_confirmed_at = EXCLUDED.email_confirmed_at,
      raw_user_meta_data = EXCLUDED.raw_user_meta_data,
      confirmation_token = '',
      recovery_token = '',
      email_change = '',
      email_change_token_new = '',
      email_change_token_current = '',
      phone_change = '',
      phone_change_token = '',
      reauthentication_token = '',
      updated_at = now();

    -- Password sign-in identity (needed by GoTrue for email/password login).
    INSERT INTO auth.identities (
      id, user_id, provider_id, provider, identity_data, created_at, updated_at
    ) VALUES (
      rec.id,
      rec.id,
      rec.id::text,
      'email',
      jsonb_build_object(
        'sub', rec.id::text,
        'email', rec.card_id || '@students.residence.local',
        'email_verified', true,
        'phone_verified', false
      ),
      now(),
      now()
    )
    ON CONFLICT (id) DO UPDATE SET
      identity_data = EXCLUDED.identity_data,
      updated_at = now();

    -- The trigger already created the student row; set the demo fields.
    UPDATE public.students
    SET
      first_name = 'Test',
      last_name = 'Student ' || rec.n,
      birth_date = date '2002-01-01' + (rec.n * 7),
      phone = '0550' || lpad(rec.n::text, 6, '0'),
      email = 'test.student' || rec.n || '@example.com',
      university = 'Test University of Tlemcen',
      faculty = 'Test Faculty of Science',
      study_level = rec.study_level::study_level,
      wilaya = 'Tlemcen',
      status = rec.status::student_status,
      room_id = CASE
        WHEN rec.room_number IS NULL THEN NULL
        ELSE (SELECT id FROM public.rooms WHERE block = 'B' AND number = rec.room_number)
      END,
      reviewed_by = CASE WHEN rec.status <> 'pending' THEN v_staff ELSE NULL END,
      reviewed_at = CASE WHEN rec.status <> 'pending' THEN now() - interval '1 day' ELSE NULL END,
      rejection_reason = CASE
        WHEN rec.status = 'rejected' THEN 'Incomplete enrollment certificate.'
        ELSE NULL
      END,
      created_at = now() - (rec.n || ' days')::interval
    WHERE id = rec.id;
  END LOOP;
END $$;

-- ----------------------------------------------------------------------------
-- 3. Maintenance tickets
-- ----------------------------------------------------------------------------
INSERT INTO public.maintenance_reports (
  id, student_id, category, description, status, staff_note, handled_by, created_at
)
VALUES
  (
    'd3000000-0000-0000-0000-000000000001',
    'e0000000-0000-0000-0000-000000000001',
    'plumbing',
    'Shower drain is clogged and water pools in the bathroom.',
    'pending', NULL, NULL, now() - interval '1 day'
  ),
  (
    'd3000000-0000-0000-0000-000000000002',
    'e0000000-0000-0000-0000-000000000002',
    'electricity',
    'Two power outlets next to the study desk stopped working.',
    'in_progress',
    'Electrician scheduled for tomorrow morning.',
    (SELECT id FROM public.staff ORDER BY created_at LIMIT 1),
    now() - interval '3 days'
  ),
  (
    'd3000000-0000-0000-0000-000000000003',
    'e0000000-0000-0000-0000-000000000003',
    'carpentry',
    'Wardrobe door hinge is broken and the door does not close.',
    'pending', NULL, NULL, now() - interval '2 days'
  ),
  (
    'd3000000-0000-0000-0000-000000000004',
    'e0000000-0000-0000-0000-000000000004',
    'others',
    'Wi-Fi signal is very weak on the second floor.',
    'resolved',
    'Router restarted and access point repositioned.',
    (SELECT id FROM public.staff ORDER BY created_at LIMIT 1),
    now() - interval '6 days'
  ),
  (
    'd3000000-0000-0000-0000-000000000005',
    'e0000000-0000-0000-0000-000000000005',
    'carpentry',
    'Desk drawer rail is loose and the drawer falls out.',
    'in_progress',
    'Carpenter ordered a replacement rail.',
    (SELECT id FROM public.staff ORDER BY created_at LIMIT 1),
    now() - interval '4 days'
  ),
  (
    'd3000000-0000-0000-0000-000000000006',
    'e0000000-0000-0000-0000-000000000006',
    'plumbing',
    'Tap in the shared kitchen keeps dripping.',
    'resolved',
    'Washer replaced; leak fixed.',
    (SELECT id FROM public.staff ORDER BY created_at LIMIT 1),
    now() - interval '10 days'
  ),
  (
    'd3000000-0000-0000-0000-000000000007',
    'e0000000-0000-0000-0000-000000000007',
    'others',
    'Requesting an extra mattress pad for the bed.',
    'pending', NULL, NULL, now() - interval '1 day'
  ),
  (
    'd3000000-0000-0000-0000-000000000008',
    'e0000000-0000-0000-0000-000000000002',
    'others',
    'Ethernet wall port has no connection.',
    'in_progress',
    'Network team is checking the switch port.',
    (SELECT id FROM public.staff ORDER BY created_at LIMIT 1),
    now() - interval '5 days'
  )
ON CONFLICT (id) DO UPDATE SET
  student_id = EXCLUDED.student_id,
  category = EXCLUDED.category,
  description = EXCLUDED.description,
  status = EXCLUDED.status,
  staff_note = EXCLUDED.staff_note,
  handled_by = EXCLUDED.handled_by,
  created_at = EXCLUDED.created_at;

-- ----------------------------------------------------------------------------
-- 4. Room-change requests
-- ----------------------------------------------------------------------------
INSERT INTO public.room_change_requests (
  id, student_id, current_room_id, preferred_room_id, reason, status,
  decision_note, decided_by, decided_at, created_at
)
VALUES
  (
    'd4000000-0000-0000-0000-000000000001',
    'e0000000-0000-0000-0000-000000000002',
    (SELECT id FROM public.rooms WHERE block = 'B' AND number = '102'),
    (SELECT id FROM public.rooms WHERE block = 'B' AND number = '202'),
    'Would like to live closer to my study group.',
    'pending', NULL, NULL, NULL, now() - interval '2 days'
  ),
  (
    'd4000000-0000-0000-0000-000000000002',
    'e0000000-0000-0000-0000-000000000003',
    (SELECT id FROM public.rooms WHERE block = 'B' AND number = '102'),
    (SELECT id FROM public.rooms WHERE block = 'B' AND number = '201'),
    'Requesting a quieter room away from the entrance.',
    'pending', NULL, NULL, NULL, now() - interval '3 days'
  ),
  (
    'd4000000-0000-0000-0000-000000000003',
    'e0000000-0000-0000-0000-000000000004',
    (SELECT id FROM public.rooms WHERE block = 'B' AND number = '103'),
    (SELECT id FROM public.rooms WHERE block = 'B' AND number = '101'),
    'Ground-floor room would help with a temporary knee injury.',
    'pending', NULL, NULL, NULL, now() - interval '1 day'
  ),
  (
    'd4000000-0000-0000-0000-000000000004',
    'e0000000-0000-0000-0000-000000000005',
    (SELECT id FROM public.rooms WHERE block = 'B' AND number = '201'),
    (SELECT id FROM public.rooms WHERE block = 'B' AND number = '103'),
    'Prefers a room on a lower floor.',
    'approved',
    'Approved; moved to B-103.',
    (SELECT id FROM public.staff ORDER BY created_at LIMIT 1),
    now() - interval '1 day',
    now() - interval '6 days'
  ),
  (
    'd4000000-0000-0000-0000-000000000005',
    'e0000000-0000-0000-0000-000000000006',
    (SELECT id FROM public.rooms WHERE block = 'B' AND number = '201'),
    (SELECT id FROM public.rooms WHERE block = 'B' AND number = '202'),
    'Wants a room with more natural light.',
    'rejected',
    'No vacancy available at this time.',
    (SELECT id FROM public.staff ORDER BY created_at LIMIT 1),
    now() - interval '2 days',
    now() - interval '8 days'
  )
ON CONFLICT (id) DO UPDATE SET
  student_id = EXCLUDED.student_id,
  current_room_id = EXCLUDED.current_room_id,
  preferred_room_id = EXCLUDED.preferred_room_id,
  reason = EXCLUDED.reason,
  status = EXCLUDED.status,
  decision_note = EXCLUDED.decision_note,
  decided_by = EXCLUDED.decided_by,
  decided_at = EXCLUDED.decided_at,
  created_at = EXCLUDED.created_at;


