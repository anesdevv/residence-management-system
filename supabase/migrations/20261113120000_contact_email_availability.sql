-- ============================================================================
-- Migration: 20261113120000_contact_email_availability.sql
-- Description:
--   Adds a callable pre-flight check for student registration so the web app can
--   reject a duplicate contact email with a friendly message BEFORE calling
--   auth.signUp(). Supabase Auth replaces any exception raised by the
--   on_auth_user_created trigger with the opaque "Database error saving new user",
--   so the trigger's email_in_use error can never reach the registration form.
--
--   The trigger and unique index from 20261111120000_simple_contact_email.sql
--   remain the source of truth (defense in depth for races).
--
-- Idempotency:
--   Safe to run multiple times (CREATE OR REPLACE, REVOKE/GRANT only).
-- ============================================================================

CREATE OR REPLACE FUNCTION public.contact_email_available(p_email text)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_clean_email text;
BEGIN
  v_clean_email := public.normalize_and_validate_contact_email(p_email);

  RETURN NOT EXISTS (
    SELECT 1
    FROM public.students
    WHERE lower(trim(email)) = v_clean_email
  );
END;
$$;

COMMENT ON FUNCTION public.contact_email_available(text) IS
  'Returns true when the normalized contact email is not registered to any student. Used as a pre-flight check during signup.';

REVOKE ALL ON FUNCTION public.contact_email_available(text) FROM public, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.contact_email_available(text) TO anon, authenticated;

-- ============================================================================
-- ROLLBACK SQL (run manually only if reverting this migration)
-- ============================================================================
-- DROP FUNCTION IF EXISTS public.contact_email_available(text);
