-- Migration: 20261109120000_verified_student_email_and_mirror_triggers.sql
-- Description:
-- 1. Enforces case-insensitive uniqueness on verified student emails (partial index on non-null/non-empty).
-- 2. Updates handle_new_user() to accept real email from auth.users and defer students.email until verified.
-- 3. Creates sync_verified_email_to_students() trigger on auth.users (after insert/update of email, email_confirmed_at)
--    so public.students.email is strictly mirrored from the confirmed auth email (single source of truth).
-- 4. Neutralizes direct email overwrites in update_my_contact(phone, email) while preserving phone updates and RPC signature.
-- 5. Adds get_my_account_status() helper for the web client to check verification and synthetic-domain status safely.
--
-- Rollback SQL (execute if reverting):
--   DROP FUNCTION IF EXISTS public.get_my_account_status();
--   DROP TRIGGER IF EXISTS trigger_sync_verified_email ON auth.users;
--   DROP FUNCTION IF EXISTS public.sync_verified_email_to_students();
--   DROP INDEX IF EXISTS public.idx_students_unique_lower_email;
--   -- Revert update_my_contact and handle_new_user to previous definitions if needed.

-- 1. Case-insensitive unique index on non-null, non-empty student emails
CREATE UNIQUE INDEX IF NOT EXISTS idx_students_unique_lower_email
  ON public.students (lower(trim(email)))
  WHERE email IS NOT NULL AND trim(email) <> '';

-- 2. Mirror trigger: sync confirmed real email from auth.users to public.students
CREATE OR REPLACE FUNCTION public.sync_verified_email_to_students()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
BEGIN
  -- Mirror to public.students only when the email is confirmed and NOT synthetic
  IF NEW.email_confirmed_at IS NOT NULL
     AND NEW.email IS NOT NULL
     AND NEW.email NOT LIKE '%@students.residence.local' THEN
    UPDATE public.students
    SET email = lower(trim(NEW.email))
    WHERE id = NEW.id
      AND (email IS NULL OR email <> lower(trim(NEW.email)));
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trigger_sync_verified_email ON auth.users;
CREATE TRIGGER trigger_sync_verified_email
  AFTER INSERT OR UPDATE OF email, email_confirmed_at ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.sync_verified_email_to_students();

-- 3. Update handle_new_user() trigger for profile & student record creation
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
  v_raw_email text;
  v_clean_email text;
BEGIN
  INSERT INTO public.profiles (id, role)
  VALUES (NEW.id, 'student')
  ON CONFLICT (id) DO NOTHING;

  IF NEW.raw_user_meta_data ? 'card_id' THEN
    v_raw_email := COALESCE(NULLIF(NEW.raw_user_meta_data->>'email', ''), NEW.email);
    IF v_raw_email IS NOT NULL AND v_raw_email NOT LIKE '%@students.residence.local' THEN
      v_clean_email := lower(trim(v_raw_email));
    ELSE
      v_clean_email := NULL;
    END IF;

    INSERT INTO public.students (
      id, card_id, first_name, last_name, birth_date, gender, phone, email,
      university, faculty, study_level, wilaya
    ) VALUES (
      NEW.id,
      trim(NEW.raw_user_meta_data->>'card_id'),
      trim(NEW.raw_user_meta_data->>'first_name'),
      trim(NEW.raw_user_meta_data->>'last_name'),
      (NEW.raw_user_meta_data->>'birth_date')::date,
      (NEW.raw_user_meta_data->>'gender')::gender,
      trim(NEW.raw_user_meta_data->>'phone'),
      -- Email in students table is populated only if auth user is confirmed; otherwise filled by sync trigger
      CASE
        WHEN NEW.email_confirmed_at IS NOT NULL THEN v_clean_email
        ELSE NULL
      END,
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
      gender = EXCLUDED.gender,
      phone = EXCLUDED.phone,
      university = EXCLUDED.university,
      faculty = EXCLUDED.faculty,
      study_level = EXCLUDED.study_level,
      wilaya = EXCLUDED.wilaya;
  END IF;

  RETURN NEW;
END;
$$;

-- Ensure on_auth_user_created trigger exists
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();

-- 4. Neutralize direct email updates in update_my_contact, keep phone updates
CREATE OR REPLACE FUNCTION public.update_my_contact(p_phone text, p_email text = null)
RETURNS public.students
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  s public.students;
BEGIN
  -- D2: students.email is exclusively mirrored from verified auth.users.
  -- The p_email argument is kept for backward compatibility with existing callers,
  -- but direct writes to students.email are ignored.
  UPDATE public.students
  SET phone = trim(p_phone)
  WHERE id = auth.uid()
  RETURNING * INTO s;

  IF s IS NULL THEN
    RAISE EXCEPTION 'student not found';
  END IF;

  RETURN s;
END;
$$;

-- 5. Helper function for web client: get_my_account_status()
CREATE OR REPLACE FUNCTION public.get_my_account_status()
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
  v_uid uuid := auth.uid();
  v_email text;
  v_confirmed_at timestamptz;
  v_role user_role;
  v_is_synthetic boolean := false;
  v_is_confirmed boolean := false;
  v_needs_real_email boolean := false;
  v_student_card_id text;
  v_student_status student_status;
  v_local_part text;
  v_domain_part text;
  v_masked_email text := null;
BEGIN
  IF v_uid IS NULL THEN
    RETURN jsonb_build_object(
      'authenticated', false,
      'needs_real_email', false
    );
  END IF;

  SELECT role INTO v_role FROM public.profiles WHERE id = v_uid;
  SELECT email, email_confirmed_at INTO v_email, v_confirmed_at FROM auth.users WHERE id = v_uid;
  SELECT card_id, status INTO v_student_card_id, v_student_status FROM public.students WHERE id = v_uid;

  IF v_email IS NOT NULL THEN
    v_is_synthetic := (v_email LIKE '%@students.residence.local');
    v_is_confirmed := (v_confirmed_at IS NOT NULL);

    IF NOT v_is_synthetic THEN
      v_local_part := split_part(v_email, '@', 1);
      v_domain_part := split_part(v_email, '@', 2);
      IF length(v_local_part) <= 2 THEN
        v_masked_email := substr(v_local_part, 1, 1) || '***@' || v_domain_part;
      ELSE
        v_masked_email := substr(v_local_part, 1, 1) || '***' || substr(v_local_part, length(v_local_part), 1) || '@' || v_domain_part;
      END IF;
    END IF;
  END IF;

  -- Staff and admin accounts are created by admins with verified emails; they never need student email completion
  IF v_role IN ('staff', 'admin') THEN
    v_needs_real_email := false;
  ELSE
    -- Students require a confirmed non-synthetic email
    v_needs_real_email := (v_is_synthetic OR NOT v_is_confirmed OR v_email IS NULL);
  END IF;

  RETURN jsonb_build_object(
    'authenticated', true,
    'user_id', v_uid,
    'role', v_role,
    'email', CASE WHEN v_is_synthetic THEN NULL ELSE v_email END,
    'masked_email', v_masked_email,
    'is_confirmed', v_is_confirmed,
    'is_synthetic', v_is_synthetic,
    'needs_real_email', v_needs_real_email,
    'card_id', v_student_card_id,
    'student_status', v_student_status
  );
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_my_account_status() TO authenticated, anon;
