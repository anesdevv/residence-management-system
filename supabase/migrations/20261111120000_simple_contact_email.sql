-- ============================================================================
-- Migration: 20261111120000_simple_contact_email.sql
-- Description:
--   1. Drops email-verification mirror trigger (trigger_sync_verified_email /
--      sync_verified_email_to_students) and verification helper (get_my_account_status).
--      Choice: students.email is now plain contact data only (never mirrored from
--      auth.users and never used to sign in, verify, or recover passwords), so keeping
--      an auth.users -> students.email mirror trigger would overwrite direct profile edits.
--   2. Ensures case-insensitive unique index on non-null, non-empty students.email.
--   3. Adds internal email normalization/validation helper (trim, lowercase, <= 254 chars,
--      valid format, rejects synthetic @students.residence.local).
--   4. Updates handle_new_user() to require and validate email for NEW student
--      registrations (while keeping staff creation untouched and keeping legacy
--      null-email rows working without a table-wide CHECK constraint) and preserves
--      single-gender residence rules from 20261110224500_single_gender_residence.sql.
--   5. Restores update_my_contact(p_phone, p_email) with server-side validation,
--      normalization, uniqueness check, and friendly error codes (email_invalid,
--      email_in_use, invalid_phone).
--   6. Adds simple student_has_email() helper for web gating of legacy null-email rows.
--
-- Idempotency:
--   Safe to run multiple times (DROP IF EXISTS, CREATE OR REPLACE, IF NOT EXISTS).
-- ============================================================================

-- 1. Remove verification-era mirror trigger & verification account-status helper
DROP TRIGGER IF EXISTS trigger_sync_verified_email ON auth.users;
DROP FUNCTION IF EXISTS public.sync_verified_email_to_students();
DROP FUNCTION IF EXISTS public.get_my_account_status();

-- 2. Case-insensitive unique index on non-null, non-empty contact emails
--    No table-wide NOT NULL or CHECK constraint is added so legacy students with
--    email IS NULL remain updatable by staff RPCs (approve_student, reject_student, delete_student).
CREATE UNIQUE INDEX IF NOT EXISTS idx_students_unique_lower_email
  ON public.students (lower(trim(email)))
  WHERE email IS NOT NULL AND trim(email) <> '';

COMMENT ON COLUMN public.students.email IS
  'Contact email only (required for new registrations, normalized lowercase, unique case-insensitively). Never used for authentication, verification, or password recovery.';

-- 3. Shared email normalization and format validation helper
CREATE OR REPLACE FUNCTION public.normalize_and_validate_contact_email(p_email text)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
SET search_path = public, pg_temp
AS $$
DECLARE
  v_clean text := lower(trim(coalesce(p_email, '')));
  v_domain text;
BEGIN
  IF v_clean = '' THEN
    RAISE EXCEPTION 'email_invalid: Please enter a valid contact email address.'
      USING ERRCODE = '22023';
  END IF;

  IF char_length(v_clean) > 254 THEN
    RAISE EXCEPTION 'email_invalid: Contact email must be 254 characters or fewer.'
      USING ERRCODE = '22023';
  END IF;

  IF v_clean ~ '\s' OR v_clean !~ '^[^\s@]+@[^\s@]+\.[^\s@]{2,}$' THEN
    RAISE EXCEPTION 'email_invalid: Please enter a valid contact email address.'
      USING ERRCODE = '22023';
  END IF;

  v_domain := split_part(v_clean, '@', 2);
  IF v_domain LIKE '%..%' OR v_domain LIKE '.%' OR v_domain LIKE '%.' THEN
    RAISE EXCEPTION 'email_invalid: Please enter a valid contact email address.'
      USING ERRCODE = '22023';
  END IF;

  IF v_clean LIKE '%@students.residence.local' THEN
    RAISE EXCEPTION 'email_invalid: Please enter a real personal or university email address.'
      USING ERRCODE = '22023';
  END IF;

  RETURN v_clean;
END;
$$;

REVOKE ALL ON FUNCTION public.normalize_and_validate_contact_email(text) FROM public, anon, authenticated;

-- 4. Update handle_new_user() trigger: require valid unique email on new student registrations
--    while preserving staff user creation (no card_id) and single-gender residence checks.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
  v_raw_email text;
  v_clean_email text;
  v_res_gender gender;
  v_constraint text;
BEGIN
  INSERT INTO public.profiles (id, role)
  VALUES (NEW.id, 'student')
  ON CONFLICT (id) DO NOTHING;

  IF NEW.raw_user_meta_data ? 'card_id' THEN
    SELECT residence_gender INTO v_res_gender
    FROM public.residence_settings
    WHERE id = 1;

    IF v_res_gender IS NULL THEN
      RAISE EXCEPTION 'Registration is not open yet';
    END IF;

    v_raw_email := COALESCE(
      NULLIF(trim(NEW.raw_user_meta_data->>'email'), ''),
      CASE
        WHEN NEW.email IS NOT NULL AND lower(trim(NEW.email)) NOT LIKE '%@students.residence.local'
          THEN NEW.email
        ELSE NULL
      END
    );

    IF v_raw_email IS NULL OR trim(v_raw_email) = '' THEN
      RAISE EXCEPTION 'email_required: A contact email address is required.'
        USING ERRCODE = '22023';
    END IF;

    v_clean_email := public.normalize_and_validate_contact_email(v_raw_email);

    IF EXISTS (
      SELECT 1
      FROM public.students
      WHERE lower(trim(email)) = v_clean_email
        AND id <> NEW.id
    ) THEN
      RAISE EXCEPTION 'email_in_use: This email address is already registered to another student.'
        USING ERRCODE = '23505';
    END IF;

    BEGIN
      INSERT INTO public.students (
        id, card_id, first_name, last_name, birth_date, gender, phone, email,
        university, faculty, study_level, wilaya
      ) VALUES (
        NEW.id,
        trim(NEW.raw_user_meta_data->>'card_id'),
        trim(NEW.raw_user_meta_data->>'first_name'),
        trim(NEW.raw_user_meta_data->>'last_name'),
        (NEW.raw_user_meta_data->>'birth_date')::date,
        v_res_gender,
        trim(NEW.raw_user_meta_data->>'phone'),
        v_clean_email,
        trim(NEW.raw_user_meta_data->>'university'),
        trim(NEW.raw_user_meta_data->>'faculty'),
        (NEW.raw_user_meta_data->>'study_level')::study_level,
        trim(NEW.raw_user_meta_data->>'wilaya')
      )
      ON CONFLICT (id) DO UPDATE SET
        card_id = EXCLUDED.card_id,
        first_name = EXCLUDED.first_name,
        last_name = EXCLUDED.last_name,
        birth_date = EXCLUDED.birth_date,
        -- Preserve historical students.gender on upsert
        phone = EXCLUDED.phone,
        email = EXCLUDED.email,
        university = EXCLUDED.university,
        faculty = EXCLUDED.faculty,
        study_level = EXCLUDED.study_level,
        wilaya = EXCLUDED.wilaya;
    EXCEPTION WHEN unique_violation THEN
      GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
      IF v_constraint = 'idx_students_unique_lower_email' THEN
        RAISE EXCEPTION 'email_in_use: This email address is already registered to another student.'
          USING ERRCODE = '23505';
      END IF;
      RAISE;
    END;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();

-- 5. Restore update_my_contact(p_phone, p_email) with server-side validation & friendly errors
CREATE OR REPLACE FUNCTION public.update_my_contact(p_phone text, p_email text DEFAULT NULL)
RETURNS public.students
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_uid uuid := auth.uid();
  v_phone text;
  v_clean_email text;
  v_constraint text;
  s public.students;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'not authenticated' USING ERRCODE = '42501';
  END IF;

  IF p_phone IS NOT NULL THEN
    v_phone := trim(p_phone);
    IF v_phone !~ '^[0-9+\s]{6,}$' THEN
      RAISE EXCEPTION 'invalid_phone: Please enter a valid phone number.'
        USING ERRCODE = '22023';
    END IF;
  END IF;

  IF p_email IS NOT NULL THEN
    v_clean_email := public.normalize_and_validate_contact_email(p_email);

    IF EXISTS (
      SELECT 1
      FROM public.students
      WHERE lower(trim(email)) = v_clean_email
        AND id <> v_uid
    ) THEN
      RAISE EXCEPTION 'email_in_use: This email address is already in use by another student.'
        USING ERRCODE = '23505';
    END IF;
  END IF;

  BEGIN
    UPDATE public.students
    SET phone = COALESCE(v_phone, phone),
        email = CASE WHEN p_email IS NULL THEN email ELSE v_clean_email END
    WHERE id = v_uid
    RETURNING * INTO s;
  EXCEPTION WHEN unique_violation THEN
    GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
    IF v_constraint = 'idx_students_unique_lower_email' THEN
      RAISE EXCEPTION 'email_in_use: This email address is already in use by another student.'
        USING ERRCODE = '23505';
    END IF;
    RAISE;
  END;

  IF s IS NULL THEN
    RAISE EXCEPTION 'student not found';
  END IF;

  RETURN s;
END;
$$;

REVOKE ALL ON FUNCTION public.update_my_contact(text, text) FROM public, anon;
GRANT EXECUTE ON FUNCTION public.update_my_contact(text, text) TO authenticated;

-- 6. Simple check: whether the current authenticated student has a non-empty contact email
CREATE OR REPLACE FUNCTION public.student_has_email()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.students
    WHERE id = auth.uid()
      AND email IS NOT NULL
      AND trim(email) <> ''
  );
$$;

COMMENT ON FUNCTION public.student_has_email() IS
  'Returns true when the current user has a student record with a non-empty contact email.';

REVOKE ALL ON FUNCTION public.student_has_email() FROM public, anon;
GRANT EXECUTE ON FUNCTION public.student_has_email() TO authenticated;

-- ============================================================================
-- ROLLBACK SQL (run manually only if reverting this migration)
-- ============================================================================
-- DROP FUNCTION IF EXISTS public.student_has_email();
-- DROP FUNCTION IF EXISTS public.normalize_and_validate_contact_email(text);
-- -- Then re-apply handle_new_user() from 20261110224500_single_gender_residence.sql
-- -- and sync_verified_email_to_students(), update_my_contact(), get_my_account_status()
-- -- from 20261109120000_verified_student_email_and_mirror_triggers.sql.
