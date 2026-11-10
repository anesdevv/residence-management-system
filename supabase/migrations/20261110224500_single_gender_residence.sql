-- ============================================================================
-- Migration: 20261110224500_single_gender_residence.sql
-- Description:
--   Replace mixed-gender blocks / per-room gender enforcement with one
--   residence-wide setting (`public.residence_settings.residence_gender`),
--   audit logging (`public.residence_settings_audit`), admin RPCs, public
--   pre-login RPC (`get_residence_public`), and trigger/RPC updates.
--
-- Compatibility / Retained Columns (DO NOT DROP):
--   * public.students.gender            - Kept for compatibility and warning-only
--                                         mismatch badges; new registrations fill
--                                         it automatically from residence_settings.
--                                         Existing rows keep their stored gender.
--   * public.rooms.gender               - Kept for compatibility; new rooms get
--                                         residence_settings.residence_gender on
--                                         INSERT only. Existing rooms keep their
--                                         stored gender and are never mutated.
--   * public.blocks.gender              - Made nullable; new blocks get
--                                         residence_gender when set.
--   * public.official_residents.gender  - Optional informational column used only
--                                         for non-blocking warning badges in UI.
--
-- Backfill Guidance (DO NOT auto-set residence_gender):
--   This migration creates the singleton row with residence_gender = NULL.
--   If an existing database has rooms/students of ONLY one gender, an admin
--   should set residence_gender to that single value via Settings / the first-time
--   setup prompt. If existing students or rooms are mixed, choosing a residence
--   type leaves all existing records intact; staff should then review any
--   students and rooms flagged as belonging to the other gender.
--
-- Idempotency:
--   Safe to run multiple times (IF NOT EXISTS, CREATE OR REPLACE, DROP IF EXISTS).
-- ============================================================================

-- 1. Singleton residence settings table (D1)
CREATE TABLE IF NOT EXISTS public.residence_settings (
  id integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  residence_name text NOT NULL DEFAULT 'Cité Universitaire · Tlemcen',
  residence_gender gender NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL
);

COMMENT ON TABLE public.residence_settings IS
  'Singleton configuration row (id = 1) holding residence name and single-gender residence_gender setting. Readable by authenticated users; mutated only via admin SECURITY DEFINER RPCs.';

COMMENT ON COLUMN public.students.gender IS
  'Retained for backward compatibility and non-blocking mismatch warnings. Populated automatically on INSERT from residence_settings.residence_gender; historical rows retain their stored value.';
COMMENT ON COLUMN public.rooms.gender IS
  'Retained for backward compatibility. Populated on INSERT from residence_settings.residence_gender; existing rows retain their stored value and no longer gate room allocation.';
COMMENT ON COLUMN public.official_residents.gender IS
  'Optional informational field from admissions roster; triggers non-blocking mismatch warnings only.';
COMMENT ON COLUMN public.blocks.gender IS
  'Retained nullable for backward compatibility; no longer drives room or student gender checks.';

INSERT INTO public.residence_settings (id)
VALUES (1)
ON CONFLICT (id) DO NOTHING;

DROP TRIGGER IF EXISTS trg_residence_settings_updated_at ON public.residence_settings;
CREATE TRIGGER trg_residence_settings_updated_at
  BEFORE UPDATE ON public.residence_settings
  FOR EACH ROW
  EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.residence_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS residence_settings_auth_select ON public.residence_settings;
CREATE POLICY residence_settings_auth_select
  ON public.residence_settings
  FOR SELECT
  TO authenticated
  USING (true);

REVOKE ALL ON public.residence_settings FROM public, anon, authenticated;
GRANT SELECT ON public.residence_settings TO authenticated;

-- 2. Audit log table for residence gender changes (D2)
CREATE TABLE IF NOT EXISTS public.residence_settings_audit (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  changed_at timestamptz NOT NULL DEFAULT now(),
  changed_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  old_gender gender NULL,
  new_gender gender NOT NULL,
  impact jsonb NOT NULL DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.residence_settings_audit IS
  'Immutable admin-readable audit log of residence_gender changes written exclusively by set_residence_gender().';

CREATE INDEX IF NOT EXISTS idx_residence_settings_audit_changed_at
  ON public.residence_settings_audit (changed_at DESC);

ALTER TABLE public.residence_settings_audit ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS residence_settings_audit_admin_select ON public.residence_settings_audit;
CREATE POLICY residence_settings_audit_admin_select
  ON public.residence_settings_audit
  FOR SELECT
  TO authenticated
  USING (public.auth_role() = 'admin');

REVOKE ALL ON public.residence_settings_audit FROM public, anon, authenticated;
GRANT SELECT ON public.residence_settings_audit TO authenticated;

-- 3. Public pre-login RPC for web registration header (D3)
CREATE OR REPLACE FUNCTION public.get_residence_public()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  SELECT jsonb_build_object(
    'residence_name', COALESCE(
      (SELECT residence_name FROM public.residence_settings WHERE id = 1),
      'Cité Universitaire · Tlemcen'
    ),
    'residence_gender', (
      SELECT residence_gender::text FROM public.residence_settings WHERE id = 1
    )
  );
$$;

COMMENT ON FUNCTION public.get_residence_public() IS
  'Returns non-PII residence display name and configured residence_gender for public registration and staff portals.';

REVOKE ALL ON FUNCTION public.get_residence_public() FROM public;
GRANT EXECUTE ON FUNCTION public.get_residence_public() TO anon, authenticated;

-- 4. Admin read-only impact preview RPC (D2)
CREATE OR REPLACE FUNCTION public.get_residence_gender_change_impact(p_new_gender text)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
  v_new_gender text := lower(trim(coalesce(p_new_gender, '')));
  v_current_gender text;
  v_students_total bigint := 0;
  v_students_pending bigint := 0;
  v_students_active bigint := 0;
  v_students_rejected bigint := 0;
  v_students_with_room bigint := 0;
  v_students_of_other_gender bigint := 0;
  v_rooms_total bigint := 0;
  v_rooms_of_other_gender bigint := 0;
  v_open_room_change_requests bigint := 0;
  v_needs_confirmation boolean := false;
BEGIN
  IF public.auth_role() IS DISTINCT FROM 'admin' THEN
    RAISE EXCEPTION 'admin only' USING ERRCODE = '42501';
  END IF;

  IF v_new_gender NOT IN ('male', 'female') THEN
    RAISE EXCEPTION 'Residence gender must be male or female' USING ERRCODE = '22023';
  END IF;

  SELECT residence_gender::text INTO v_current_gender
  FROM public.residence_settings
  WHERE id = 1;

  SELECT
    count(*),
    count(*) FILTER (WHERE status = 'pending'),
    count(*) FILTER (WHERE status = 'active'),
    count(*) FILTER (WHERE status = 'rejected'),
    count(*) FILTER (WHERE room_id IS NOT NULL),
    count(*) FILTER (WHERE gender::text <> v_new_gender)
  INTO
    v_students_total,
    v_students_pending,
    v_students_active,
    v_students_rejected,
    v_students_with_room,
    v_students_of_other_gender
  FROM public.students;

  SELECT
    count(*),
    count(*) FILTER (WHERE gender::text <> v_new_gender)
  INTO
    v_rooms_total,
    v_rooms_of_other_gender
  FROM public.rooms;

  SELECT count(*) INTO v_open_room_change_requests
  FROM public.room_change_requests
  WHERE status = 'pending';

  v_needs_confirmation := (v_students_total > 0 OR v_students_with_room > 0);

  RETURN jsonb_build_object(
    'current_gender', v_current_gender,
    'new_gender', v_new_gender,
    'students_total', coalesce(v_students_total, 0),
    'students_pending', coalesce(v_students_pending, 0),
    'students_active', coalesce(v_students_active, 0),
    'students_rejected', coalesce(v_students_rejected, 0),
    'students_with_room', coalesce(v_students_with_room, 0),
    'students_of_other_gender', coalesce(v_students_of_other_gender, 0),
    'rooms_total', coalesce(v_rooms_total, 0),
    'rooms_of_other_gender', coalesce(v_rooms_of_other_gender, 0),
    'open_room_change_requests', coalesce(v_open_room_change_requests, 0),
    'needs_confirmation', v_needs_confirmation
  );
END;
$$;

COMMENT ON FUNCTION public.get_residence_gender_change_impact(text) IS
  'Admin-only read-only preview of existing student and room counts before setting or changing residence_gender.';

REVOKE ALL ON FUNCTION public.get_residence_gender_change_impact(text) FROM public, anon;
GRANT EXECUTE ON FUNCTION public.get_residence_gender_change_impact(text) TO authenticated;

-- 5. Admin RPC to set/change residence_gender with confirmation & audit (D2)
CREATE OR REPLACE FUNCTION public.set_residence_gender(
  p_gender text,
  p_confirmation text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
  v_new_gender text := lower(trim(coalesce(p_gender, '')));
  v_settings public.residence_settings;
  v_old_gender gender;
  v_impact jsonb;
  v_needs_confirmation boolean;
  v_updated_at timestamptz;
BEGIN
  IF public.auth_role() IS DISTINCT FROM 'admin' THEN
    RAISE EXCEPTION 'admin only' USING ERRCODE = '42501';
  END IF;

  IF v_new_gender NOT IN ('male', 'female') THEN
    RAISE EXCEPTION 'Residence gender must be male or female' USING ERRCODE = '22023';
  END IF;

  INSERT INTO public.residence_settings (id)
  VALUES (1)
  ON CONFLICT (id) DO NOTHING;

  SELECT * INTO v_settings
  FROM public.residence_settings
  WHERE id = 1
  FOR UPDATE;

  v_old_gender := v_settings.residence_gender;
  v_impact := public.get_residence_gender_change_impact(v_new_gender);
  v_needs_confirmation := coalesce((v_impact->>'needs_confirmation')::boolean, false);

  IF v_needs_confirmation AND p_confirmation IS DISTINCT FROM 'CHANGE' THEN
    RAISE EXCEPTION
      'Confirmation required: type CHANGE to set residence type to %. Counts: % students (% pending, % active, % rejected), % assigned rooms, % rooms total, % students of other gender.',
      v_new_gender,
      (v_impact->>'students_total'),
      (v_impact->>'students_pending'),
      (v_impact->>'students_active'),
      (v_impact->>'students_rejected'),
      (v_impact->>'students_with_room'),
      (v_impact->>'rooms_total'),
      (v_impact->>'students_of_other_gender')
      USING ERRCODE = '22023';
  END IF;

  UPDATE public.residence_settings
  SET residence_gender = v_new_gender::gender,
      updated_by = auth.uid(),
      updated_at = now()
  WHERE id = 1
  RETURNING updated_at INTO v_updated_at;

  INSERT INTO public.residence_settings_audit (
    changed_by,
    old_gender,
    new_gender,
    impact
  ) VALUES (
    auth.uid(),
    v_old_gender,
    v_new_gender::gender,
    v_impact
  );

  RETURN jsonb_build_object(
    'residence_name', v_settings.residence_name,
    'residence_gender', v_new_gender,
    'old_gender', v_old_gender::text,
    'updated_at', v_updated_at,
    'updated_by', auth.uid(),
    'impact', v_impact
  );
END;
$$;

COMMENT ON FUNCTION public.set_residence_gender(text, text) IS
  'Admin-only mutation of residence_settings.residence_gender. Requires exact CHANGE confirmation when existing students or room assignments exist. Writes audit log without modifying existing students or rooms.';

REVOKE ALL ON FUNCTION public.set_residence_gender(text, text) FROM public, anon;
GRANT EXECUTE ON FUNCTION public.set_residence_gender(text, text) TO authenticated;

-- 6. Admin helper RPCs for residence_name & settings/audit display (Desktop Settings)
CREATE OR REPLACE FUNCTION public.set_residence_name(p_name text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
  v_name text := trim(coalesce(p_name, ''));
  v_row public.residence_settings;
BEGIN
  IF public.auth_role() IS DISTINCT FROM 'admin' THEN
    RAISE EXCEPTION 'admin only' USING ERRCODE = '42501';
  END IF;

  IF v_name = '' THEN
    RAISE EXCEPTION 'Residence name is required' USING ERRCODE = '22023';
  END IF;

  IF char_length(v_name) > 120 THEN
    RAISE EXCEPTION 'Residence name must be 120 characters or fewer' USING ERRCODE = '22023';
  END IF;

  INSERT INTO public.residence_settings (id)
  VALUES (1)
  ON CONFLICT (id) DO NOTHING;

  UPDATE public.residence_settings
  SET residence_name = v_name,
      updated_by = auth.uid(),
      updated_at = now()
  WHERE id = 1
  RETURNING * INTO v_row;

  RETURN jsonb_build_object(
    'residence_name', v_row.residence_name,
    'residence_gender', v_row.residence_gender::text,
    'updated_at', v_row.updated_at,
    'updated_by', v_row.updated_by
  );
END;
$$;

COMMENT ON FUNCTION public.set_residence_name(text) IS
  'Admin-only update of residence_settings.residence_name without mutating residence_gender.';

REVOKE ALL ON FUNCTION public.set_residence_name(text) FROM public, anon;
GRANT EXECUTE ON FUNCTION public.set_residence_name(text) TO authenticated;

CREATE OR REPLACE FUNCTION public.get_residence_settings_admin()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
  SELECT CASE
    WHEN public.auth_role() IS DISTINCT FROM 'admin' THEN NULL
    ELSE (
      SELECT jsonb_build_object(
        'residence_name', rs.residence_name,
        'residence_gender', rs.residence_gender::text,
        'updated_at', rs.updated_at,
        'updated_by', rs.updated_by,
        'last_changed_at', la.changed_at,
        'last_changed_by', la.changed_by,
        'last_changed_by_name', st.full_name,
        'last_old_gender', la.old_gender::text,
        'last_new_gender', la.new_gender::text
      )
      FROM public.residence_settings rs
      LEFT JOIN LATERAL (
        SELECT a.changed_at, a.changed_by, a.old_gender, a.new_gender
        FROM public.residence_settings_audit a
        ORDER BY a.changed_at DESC, a.id DESC
        LIMIT 1
      ) la ON true
      LEFT JOIN public.staff st ON st.id = la.changed_by
      WHERE rs.id = 1
    )
  END;
$$;

COMMENT ON FUNCTION public.get_residence_settings_admin() IS
  'Admin-only read of residence_settings alongside latest audit change metadata.';

REVOKE ALL ON FUNCTION public.get_residence_settings_admin() FROM public, anon;
GRANT EXECUTE ON FUNCTION public.get_residence_settings_admin() TO authenticated;

-- 7. Registration triggers: derive student gender automatically & block when unset (D4)
CREATE OR REPLACE FUNCTION public.students_set_residence_gender()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_gender gender;
BEGIN
  SELECT residence_gender INTO v_gender
  FROM public.residence_settings
  WHERE id = 1;

  IF v_gender IS NULL THEN
    RAISE EXCEPTION 'Registration is not open yet';
  END IF;

  NEW.gender := v_gender;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_students_set_residence_gender ON public.students;
CREATE TRIGGER trg_students_set_residence_gender
  BEFORE INSERT ON public.students
  FOR EACH ROW
  EXECUTE FUNCTION public.students_set_residence_gender();

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
      v_res_gender,
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
      -- Preserve historical students.gender on profile sync/upsert
      phone = EXCLUDED.phone,
      university = EXCLUDED.university,
      faculty = EXCLUDED.faculty,
      study_level = EXCLUDED.study_level,
      wilaya = EXCLUDED.wilaya;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();

-- 8. Room & Block insert triggers (compatibility only; never rewrite on UPDATE) (D5)
ALTER TABLE public.blocks ALTER COLUMN gender DROP NOT NULL;

CREATE OR REPLACE FUNCTION public.blocks_set_residence_gender()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_gender gender;
BEGIN
  SELECT residence_gender INTO v_gender
  FROM public.residence_settings
  WHERE id = 1;

  IF v_gender IS NOT NULL THEN
    NEW.gender := v_gender;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_blocks_set_residence_gender ON public.blocks;
CREATE TRIGGER trg_blocks_set_residence_gender
  BEFORE INSERT ON public.blocks
  FOR EACH ROW
  EXECUTE FUNCTION public.blocks_set_residence_gender();

DROP TRIGGER IF EXISTS trigger_sync_room_gender ON public.rooms;
DROP TRIGGER IF EXISTS rooms_a_sync_gender ON public.rooms;

CREATE OR REPLACE FUNCTION public.rooms_set_residence_gender()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_gender gender;
BEGIN
  SELECT residence_gender INTO v_gender
  FROM public.residence_settings
  WHERE id = 1;

  IF v_gender IS NOT NULL THEN
    NEW.gender := v_gender;
  ELSIF NEW.gender IS NULL THEN
    RAISE EXCEPTION 'The residence type has not been set. Ask an administrator.';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS rooms_a_set_residence_gender ON public.rooms;
CREATE TRIGGER rooms_a_set_residence_gender
  BEFORE INSERT ON public.rooms
  FOR EACH ROW
  EXECUTE FUNCTION public.rooms_set_residence_gender();

-- 9. Allocation RPCs without per-room gender checks (capacity & locks preserved) (D5)
CREATE OR REPLACE FUNCTION public.approve_student(p_student uuid, p_room uuid)
RETURNS public.students
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
  s public.students;
  r public.rooms;
  occ int;
BEGIN
  IF NOT public.is_staff() THEN
    RAISE EXCEPTION 'not authorized';
  END IF;

  SELECT * INTO s FROM public.students WHERE id = p_student FOR UPDATE;
  IF s IS NULL THEN
    RAISE EXCEPTION 'student not found';
  END IF;

  SELECT * INTO r FROM public.rooms WHERE id = p_room FOR UPDATE;
  IF r IS NULL THEN
    RAISE EXCEPTION 'room not found';
  END IF;

  SELECT count(*) INTO occ
  FROM public.students
  WHERE room_id = p_room AND status = 'active' AND id <> p_student;

  IF occ >= r.capacity THEN
    RAISE EXCEPTION 'room full';
  END IF;

  UPDATE public.students
  SET status = 'active',
      room_id = p_room,
      rejection_reason = null,
      reviewed_by = auth.uid(),
      reviewed_at = now()
  WHERE id = p_student
  RETURNING * INTO s;

  RETURN s;
END;
$$;

CREATE OR REPLACE FUNCTION public.approve_room_change(p_request uuid, p_room uuid)
RETURNS public.room_change_requests
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
  req public.room_change_requests;
  s public.students;
  r public.rooms;
  occ int;
BEGIN
  IF NOT public.is_staff() THEN
    RAISE EXCEPTION 'not authorized';
  END IF;

  SELECT * INTO req
  FROM public.room_change_requests
  WHERE id = p_request AND status = 'pending'
  FOR UPDATE;
  IF req IS NULL THEN
    RAISE EXCEPTION 'pending request not found';
  END IF;

  SELECT * INTO s FROM public.students WHERE id = req.student_id;

  SELECT * INTO r FROM public.rooms WHERE id = p_room FOR UPDATE;
  IF r IS NULL THEN
    RAISE EXCEPTION 'room not found';
  END IF;

  SELECT count(*) INTO occ
  FROM public.students
  WHERE room_id = p_room AND status = 'active' AND id <> s.id;

  IF occ >= r.capacity THEN
    RAISE EXCEPTION 'room full';
  END IF;

  UPDATE public.students
  SET room_id = p_room
  WHERE id = s.id;

  UPDATE public.room_change_requests
  SET status = 'approved',
      decided_by = auth.uid(),
      decided_at = now(),
      decision_note = null
  WHERE id = p_request
  RETURNING * INTO req;

  RETURN req;
END;
$$;

-- 10. Non-mutating migration diagnostic notice (inspects existing data only)
DO $$
DECLARE
  v_student_genders int;
  v_room_genders int;
  v_sole_student gender;
  v_sole_room gender;
BEGIN
  SELECT count(DISTINCT gender), min(gender::text)::gender
  INTO v_student_genders, v_sole_student
  FROM public.students;

  SELECT count(DISTINCT gender), min(gender::text)::gender
  INTO v_room_genders, v_sole_room
  FROM public.rooms;

  IF v_student_genders = 0 AND v_room_genders = 0 THEN
    RAISE NOTICE 'Single-gender migration: database has no students or rooms yet; administrator should select residence_gender on first launch.';
  ELSIF v_student_genders <= 1 AND v_room_genders <= 1
        AND COALESCE(v_sole_student, v_sole_room) IS NOT DISTINCT FROM COALESCE(v_sole_room, v_sole_student) THEN
    RAISE NOTICE 'Single-gender migration: all existing records share gender "%". Suggested setting (not auto-applied): %.',
      COALESCE(v_sole_student, v_sole_room),
      COALESCE(v_sole_student, v_sole_room);
  ELSE
    RAISE NOTICE 'Single-gender migration: existing data contains mixed genders. After setting residence_gender, administrators should review students and rooms flagged with the other gender.';
  END IF;
END;
$$;

-- ============================================================================
-- ROLLBACK SQL (run manually only if reverting this migration)
-- ============================================================================
-- -- 1. Restore gender checks in approve_student & approve_room_change
-- CREATE OR REPLACE FUNCTION public.approve_student(p_student uuid, p_room uuid)
-- RETURNS public.students LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
-- DECLARE s public.students; r public.rooms; occ int;
-- BEGIN
--   IF NOT is_staff() THEN RAISE EXCEPTION 'not authorized'; END IF;
--   SELECT * INTO s FROM students WHERE id = p_student FOR UPDATE;
--   IF s IS NULL THEN RAISE EXCEPTION 'student not found'; END IF;
--   SELECT * INTO r FROM rooms WHERE id = p_room FOR UPDATE;
--   IF r IS NULL THEN RAISE EXCEPTION 'room not found'; END IF;
--   IF r.gender <> s.gender THEN RAISE EXCEPTION 'gender mismatch'; END IF;
--   SELECT count(*) INTO occ FROM students WHERE room_id = p_room AND status = 'active' AND id <> p_student;
--   IF occ >= r.capacity THEN RAISE EXCEPTION 'room full'; END IF;
--   UPDATE students SET status = 'active', room_id = p_room, rejection_reason = null,
--     reviewed_by = auth.uid(), reviewed_at = now()
--   WHERE id = p_student RETURNING * INTO s;
--   RETURN s;
-- END; $$;
--
-- CREATE OR REPLACE FUNCTION public.approve_room_change(p_request uuid, p_room uuid)
-- RETURNS public.room_change_requests LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
-- DECLARE req public.room_change_requests; s public.students; r public.rooms; occ int;
-- BEGIN
--   IF NOT is_staff() THEN RAISE EXCEPTION 'not authorized'; END IF;
--   SELECT * INTO req FROM room_change_requests WHERE id = p_request AND status = 'pending' FOR UPDATE;
--   IF req IS NULL THEN RAISE EXCEPTION 'pending request not found'; END IF;
--   SELECT * INTO s FROM students WHERE id = req.student_id;
--   SELECT * INTO r FROM rooms WHERE id = p_room FOR UPDATE;
--   IF r IS NULL THEN RAISE EXCEPTION 'room not found'; END IF;
--   IF r.gender <> s.gender THEN RAISE EXCEPTION 'gender mismatch'; END IF;
--   SELECT count(*) INTO occ FROM students WHERE room_id = p_room AND status = 'active' AND id <> s.id;
--   IF occ >= r.capacity THEN RAISE EXCEPTION 'room full'; END IF;
--   UPDATE students SET room_id = p_room WHERE id = s.id;
--   UPDATE room_change_requests SET status = 'approved', decided_by = auth.uid(),
--     decided_at = now(), decision_note = null
--   WHERE id = p_request RETURNING * INTO req;
--   RETURN req;
-- END; $$;
--
-- -- 2. Restore handle_new_user() reading raw_user_meta_data->>'gender' and drop student/block/room triggers
-- DROP TRIGGER IF EXISTS trg_students_set_residence_gender ON public.students;
-- DROP FUNCTION IF EXISTS public.students_set_residence_gender();
-- DROP TRIGGER IF EXISTS trg_blocks_set_residence_gender ON public.blocks;
-- DROP FUNCTION IF EXISTS public.blocks_set_residence_gender();
-- DROP TRIGGER IF EXISTS rooms_a_set_residence_gender ON public.rooms;
-- DROP FUNCTION IF EXISTS public.rooms_set_residence_gender();
-- CREATE TRIGGER rooms_a_sync_gender BEFORE INSERT OR UPDATE ON public.rooms
--   FOR EACH ROW EXECUTE FUNCTION public.sync_room_gender_from_block();
-- -- Re-apply handle_new_user() from 20261109120000_verified_student_email_and_mirror_triggers.sql
-- -- Optionally backfill NULL blocks.gender before re-enabling NOT NULL:
-- -- UPDATE public.blocks SET gender = 'male' WHERE gender IS NULL;
-- -- ALTER TABLE public.blocks ALTER COLUMN gender SET NOT NULL;
--
-- -- 3. Drop new RPCs and settings tables
-- DROP FUNCTION IF EXISTS public.get_residence_settings_admin();
-- DROP FUNCTION IF EXISTS public.set_residence_name(text);
-- DROP FUNCTION IF EXISTS public.set_residence_gender(text, text);
-- DROP FUNCTION IF EXISTS public.get_residence_gender_change_impact(text);
-- DROP FUNCTION IF EXISTS public.get_residence_public();
-- DROP TABLE IF EXISTS public.residence_settings_audit;
-- DROP TABLE IF EXISTS public.residence_settings;
