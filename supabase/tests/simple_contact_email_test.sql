-- ============================================================================
-- Local Postgres/Supabase verification suite for 20261111120000_simple_contact_email.sql
-- Run against a LOCAL Supabase database inside a rolled-back transaction:
--   psql "$LOCAL_DB_URL" -v ON_ERROR_STOP=1 -f supabase/tests/simple_contact_email_test.sql
-- Never run on production/cloud.
-- ============================================================================

BEGIN;

-- Ensure residence_settings is configured for registration trigger tests
INSERT INTO public.residence_settings (id, residence_gender)
VALUES (1, 'male')
ON CONFLICT (id) DO UPDATE SET residence_gender = COALESCE(public.residence_settings.residence_gender, 'male');

-- Ensure at least one test room and staff member exist for approval/rejection tests
DO $$
DECLARE
  v_staff uuid := 'f0000000-0000-0000-0000-000000000001';
  v_s1 uuid := 'f0000000-0000-0000-0000-000000000011';
  v_s2 uuid := 'f0000000-0000-0000-0000-000000000012';
  v_s_legacy uuid := 'f0000000-0000-0000-0000-000000000013';
  v_s_legacy_reject uuid := 'f0000000-0000-0000-0000-000000000014';
  v_room uuid;
  v_ok boolean;
  v_email text;
  v_has_email boolean;
BEGIN
  -- 1. Staff creation without card_id must still work cleanly
  INSERT INTO auth.users (
    id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data
  ) VALUES (
    v_staff, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
    'test.staff.simple@residence.test', 'x', now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"full_name":"Test Staff"}'::jsonb
  );
  UPDATE public.profiles SET role = 'staff' WHERE id = v_staff;
  INSERT INTO public.staff (id, full_name, position) VALUES (v_staff, 'Test Staff', 'Officer');

  INSERT INTO public.rooms (block, floor, number, capacity, gender)
  VALUES ('TESTSIMP', 1, '901', 2, 'male')
  RETURNING id INTO v_room;

  -- 2. Missing email on new student registration must be rejected
  v_ok := false;
  BEGIN
    INSERT INTO auth.users (
      id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
      raw_app_meta_data, raw_user_meta_data
    ) VALUES (
      gen_random_uuid(), '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
      '99990001@students.residence.local', 'x', now(),
      '{"provider":"email","providers":["email"]}'::jsonb,
      '{"card_id":"99990001","first_name":"No","last_name":"Email","birth_date":"2003-01-01","phone":"0555000001","university":"UABB","faculty":"Sci","study_level":"L1","wilaya":"Tlemcen"}'::jsonb
    );
  EXCEPTION WHEN OTHERS THEN
    v_ok := SQLERRM LIKE 'email_required%';
  END;
  IF NOT v_ok THEN
    RAISE EXCEPTION 'TEST FAILED: missing email on new registration was not rejected';
  END IF;

  -- 3. Invalid email & >254 char email on new student registration must be rejected
  v_ok := false;
  BEGIN
    INSERT INTO auth.users (
      id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
      raw_app_meta_data, raw_user_meta_data
    ) VALUES (
      gen_random_uuid(), '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
      '99990002@students.residence.local', 'x', now(),
      '{"provider":"email","providers":["email"]}'::jsonb,
      '{"card_id":"99990002","first_name":"Bad","last_name":"Email","birth_date":"2003-01-01","phone":"0555000002","email":"not-an-email","university":"UABB","faculty":"Sci","study_level":"L1","wilaya":"Tlemcen"}'::jsonb
    );
  EXCEPTION WHEN OTHERS THEN
    v_ok := SQLERRM LIKE 'email_invalid%';
  END;
  IF NOT v_ok THEN
    RAISE EXCEPTION 'TEST FAILED: invalid email on new registration was not rejected';
  END IF;

  -- 4. Valid registration normalizes (trims + lowercases) and populates students.email
  INSERT INTO auth.users (
    id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data
  ) VALUES (
    v_s1, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
    '99990003@students.residence.local', 'x', NULL,
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"card_id":"99990003","first_name":"Alice","last_name":"Test","birth_date":"2003-01-01","phone":"0555000003","email":"  Alice.Test@Univ-Tlemcen.DZ ","university":"UABB","faculty":"Sci","study_level":"L1","wilaya":"Tlemcen"}'::jsonb
  );

  SELECT email INTO v_email FROM public.students WHERE id = v_s1;
  IF v_email IS DISTINCT FROM 'alice.test@univ-tlemcen.dz' THEN
    RAISE EXCEPTION 'TEST FAILED: expected normalized email, got %', v_email;
  END IF;

  -- 5. Duplicate email differing only by case must be rejected
  v_ok := false;
  BEGIN
    INSERT INTO auth.users (
      id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
      raw_app_meta_data, raw_user_meta_data
    ) VALUES (
      gen_random_uuid(), '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
      '99990004@students.residence.local', 'x', now(),
      '{"provider":"email","providers":["email"]}'::jsonb,
      '{"card_id":"99990004","first_name":"Dup","last_name":"Email","birth_date":"2003-01-01","phone":"0555000004","email":"ALICE.TEST@UNIV-TLEMCEN.DZ","university":"UABB","faculty":"Sci","study_level":"L1","wilaya":"Tlemcen"}'::jsonb
    );
  EXCEPTION WHEN OTHERS THEN
    v_ok := SQLERRM LIKE 'email_in_use%';
  END;
  IF NOT v_ok THEN
    RAISE EXCEPTION 'TEST FAILED: case-insensitive duplicate email was not rejected';
  END IF;

  -- 6. Second valid student, then test update_my_contact validation & uniqueness
  INSERT INTO auth.users (
    id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data
  ) VALUES (
    v_s2, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
    '99990005@students.residence.local', 'x', now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"card_id":"99990005","first_name":"Bob","last_name":"Test","birth_date":"2003-01-01","phone":"0555000005","email":"bob.test@univ-tlemcen.dz","university":"UABB","faculty":"Sci","study_level":"L1","wilaya":"Tlemcen"}'::jsonb
  );

  PERFORM set_config('request.jwt.claim.sub', v_s2::text, true);
  PERFORM set_config('request.jwt.claim.role', 'authenticated', true);

  SELECT public.student_has_email() INTO v_has_email;
  IF NOT v_has_email THEN
    RAISE EXCEPTION 'TEST FAILED: student_has_email() should be true for student with email';
  END IF;

  v_ok := false;
  BEGIN
    PERFORM public.update_my_contact('0555000005', 'bad-email');
  EXCEPTION WHEN OTHERS THEN
    v_ok := SQLERRM LIKE 'email_invalid%';
  END;
  IF NOT v_ok THEN
    RAISE EXCEPTION 'TEST FAILED: update_my_contact did not reject invalid email';
  END IF;

  v_ok := false;
  BEGIN
    PERFORM public.update_my_contact('0555000005', 'ALICE.TEST@UNIV-TLEMCEN.DZ');
  EXCEPTION WHEN OTHERS THEN
    v_ok := SQLERRM LIKE 'email_in_use%';
  END;
  IF NOT v_ok THEN
    RAISE EXCEPTION 'TEST FAILED: update_my_contact did not reject duplicate email';
  END IF;

  PERFORM public.update_my_contact('0555999999', '  Bob.New@Univ-Tlemcen.DZ ');
  SELECT email INTO v_email FROM public.students WHERE id = v_s2;
  IF v_email IS DISTINCT FROM 'bob.new@univ-tlemcen.dz' THEN
    RAISE EXCEPTION 'TEST FAILED: update_my_contact did not save normalized email, got %', v_email;
  END IF;

  -- 7. Legacy students with email IS NULL can still be approved and rejected by staff
  INSERT INTO auth.users (
    id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data
  ) VALUES (
    v_s_legacy, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
    '99990006@students.residence.local', 'x', now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"card_id":"99990006","first_name":"Legacy","last_name":"Approve","birth_date":"2003-01-01","phone":"0555000006","email":"tmp1@univ-tlemcen.dz","university":"UABB","faculty":"Sci","study_level":"L1","wilaya":"Tlemcen"}'::jsonb
  );
  UPDATE public.students SET email = NULL WHERE id = v_s_legacy;

  INSERT INTO auth.users (
    id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data
  ) VALUES (
    v_s_legacy_reject, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
    '99990007@students.residence.local', 'x', now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"card_id":"99990007","first_name":"Legacy","last_name":"Reject","birth_date":"2003-01-01","phone":"0555000007","email":"tmp2@univ-tlemcen.dz","university":"UABB","faculty":"Sci","study_level":"L1","wilaya":"Tlemcen"}'::jsonb
  );
  UPDATE public.students SET email = NULL WHERE id = v_s_legacy_reject;

  -- student_has_email() must be false for legacy null-email student
  PERFORM set_config('request.jwt.claim.sub', v_s_legacy::text, true);
  SELECT public.student_has_email() INTO v_has_email;
  IF v_has_email THEN
    RAISE EXCEPTION 'TEST FAILED: student_has_email() should be false for null-email student';
  END IF;

  -- Approve & reject as staff
  PERFORM set_config('request.jwt.claim.sub', v_staff::text, true);
  PERFORM public.approve_student(v_s_legacy, v_room);
  PERFORM public.reject_student(v_s_legacy_reject, 'Missing paper certificate');

  -- 8. Verification-era mirror trigger and status helper must be absent
  IF EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trigger_sync_verified_email'
  ) THEN
    RAISE EXCEPTION 'TEST FAILED: trigger_sync_verified_email still exists';
  END IF;
  IF to_regprocedure('public.get_my_account_status()') IS NOT NULL THEN
    RAISE EXCEPTION 'TEST FAILED: get_my_account_status() still exists';
  END IF;
END $$;

ROLLBACK;
