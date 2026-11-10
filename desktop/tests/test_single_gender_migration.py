"""Static & SQL contract tests for Phase 1 single-gender residence migration."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase" / "migrations" / "20261110224500_single_gender_residence.sql"
SEED = ROOT / "supabase" / "seed.sql"


def _active_sql(text: str) -> str:
    """Return SQL lines outside the trailing ROLLBACK SQL comment block."""
    marker = "-- ROLLBACK SQL"
    if marker in text:
        text = text.split(marker, 1)[0]
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("--"):
            lines.append(line)
    return "\n".join(lines)


def _extract_function_body(sql: str, fn_name: str) -> str:
    pattern = re.compile(
        rf"create\s+or\s+replace\s+function\s+public\.{re.escape(fn_name)}\b.*?as\s+\$\$(.*?)\$\$;",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(sql)
    assert match is not None, f"Function public.{fn_name} not found in migration"
    return match.group(1)


def test_migration_exists_and_is_idempotent() -> None:
    assert MIGRATION.exists(), "Phase 1 migration file is missing"
    raw = MIGRATION.read_text(encoding="utf-8")
    active = _active_sql(raw)

    assert "CREATE TABLE IF NOT EXISTS public.residence_settings" in active
    assert "CREATE TABLE IF NOT EXISTS public.residence_settings_audit" in active
    assert "ON CONFLICT (id) DO NOTHING" in active
    assert "DROP TRIGGER IF EXISTS trg_residence_settings_updated_at" in active
    assert "DROP TRIGGER IF EXISTS trg_students_set_residence_gender" in active
    assert "DROP TRIGGER IF EXISTS trg_blocks_set_residence_gender" in active
    assert "DROP TRIGGER IF EXISTS rooms_a_set_residence_gender" in active
    assert "DROP TRIGGER IF EXISTS rooms_a_sync_gender ON public.rooms" in active
    assert "DROP POLICY IF EXISTS residence_settings_auth_select" in active
    assert "DROP POLICY IF EXISTS residence_settings_audit_admin_select" in active


def test_retained_columns_not_dropped_and_rollback_present() -> None:
    raw = MIGRATION.read_text(encoding="utf-8")
    active = _active_sql(raw)

    assert not re.search(r"\bDROP\s+COLUMN\b", active, re.IGNORECASE)
    assert "COMMENT ON COLUMN public.students.gender" in active
    assert "COMMENT ON COLUMN public.rooms.gender" in active
    assert "COMMENT ON COLUMN public.official_residents.gender" in active
    assert "COMMENT ON COLUMN public.blocks.gender" in active
    assert "-- ROLLBACK SQL" in raw
    assert "DROP TABLE IF EXISTS public.residence_settings" in raw
    assert "DROP TABLE IF EXISTS public.residence_settings_audit" in raw


def test_rls_and_security_definer_search_path() -> None:
    active = _active_sql(MIGRATION.read_text(encoding="utf-8"))

    assert "id integer PRIMARY KEY DEFAULT 1 CHECK (id = 1)" in active
    assert "ALTER TABLE public.residence_settings ENABLE ROW LEVEL SECURITY" in active
    assert "ALTER TABLE public.residence_settings_audit ENABLE ROW LEVEL SECURITY" in active
    assert "REVOKE ALL ON public.residence_settings FROM public, anon, authenticated" in active
    assert "GRANT SELECT ON public.residence_settings TO authenticated" in active
    assert "REVOKE ALL ON public.residence_settings_audit FROM public, anon, authenticated" in active
    assert "GRANT SELECT ON public.residence_settings_audit TO authenticated" in active
    assert "GRANT EXECUTE ON FUNCTION public.get_residence_public() TO anon, authenticated" in active

    for fn in (
        "get_residence_gender_change_impact",
        "set_residence_gender",
        "set_residence_name",
        "get_residence_settings_admin",
    ):
        header_match = re.search(
            rf"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\.{fn}\b.*?AS\s+\$\$",
            active,
            re.IGNORECASE | re.DOTALL,
        )
        assert header_match is not None, f"Missing header for {fn}"
        header = header_match.group(0)
        assert "SECURITY DEFINER" in header
        assert "SET search_path = public, auth, pg_temp" in header
        body = _extract_function_body(active, fn)
        assert "auth_role() IS DISTINCT FROM 'admin'" in body


def test_impact_and_set_residence_gender_contracts() -> None:
    active = _active_sql(MIGRATION.read_text(encoding="utf-8"))

    impact_body = _extract_function_body(active, "get_residence_gender_change_impact")
    for key in (
        "'current_gender'",
        "'new_gender'",
        "'students_total'",
        "'students_pending'",
        "'students_active'",
        "'students_rejected'",
        "'students_with_room'",
        "'students_of_other_gender'",
        "'rooms_total'",
        "'rooms_of_other_gender'",
        "'open_room_change_requests'",
        "'needs_confirmation'",
    ):
        assert key in impact_body

    assert "v_students_total > 0 OR v_students_with_room > 0" in impact_body

    setter_body = _extract_function_body(active, "set_residence_gender")
    assert "p_confirmation IS DISTINCT FROM 'CHANGE'" in setter_body
    assert "Confirmation required: type CHANGE" in setter_body
    assert "INSERT INTO public.residence_settings_audit" in setter_body
    # Never mutates students, rooms, blocks, requests, or tickets
    for forbidden in ("UPDATE public.students", "DELETE FROM public.students", "UPDATE public.rooms", "DELETE FROM public.rooms"):
        assert forbidden not in setter_body


def test_registration_and_allocation_rules() -> None:
    active = _active_sql(MIGRATION.read_text(encoding="utf-8"))

    new_user_body = _extract_function_body(active, "handle_new_user")
    assert "Registration is not open yet" in new_user_body
    assert "raw_user_meta_data->>'gender'" not in new_user_body

    student_trg_body = _extract_function_body(active, "students_set_residence_gender")
    assert "Registration is not open yet" in student_trg_body
    assert "NEW.gender := v_gender" in student_trg_body

    # Room insert trigger only runs BEFORE INSERT (never overwrites existing rooms on UPDATE)
    assert re.search(
        r"CREATE\s+TRIGGER\s+rooms_a_set_residence_gender\s+BEFORE\s+INSERT\s+ON\s+public\.rooms\b",
        active,
        re.IGNORECASE,
    )
    assert not re.search(
        r"BEFORE\s+INSERT\s+OR\s+UPDATE\s+ON\s+public\.rooms\b",
        active,
        re.IGNORECASE,
    )

    for fn in ("approve_student", "approve_room_change"):
        body = _extract_function_body(active, fn)
        assert "gender mismatch" not in body.lower()
        assert "r.gender <> s.gender" not in body
        assert "occ >= r.capacity" in body
        assert "FOR UPDATE" in body


def test_seed_is_single_gender_and_valid() -> None:
    seed_sql = SEED.read_text(encoding="utf-8")
    assert "insert into public.residence_settings" in seed_sql
    assert "'male'" in seed_sql
    assert "'female'" not in seed_sql
    assert "s0000000-" not in seed_sql
    assert "m0000000-" not in seed_sql
    assert "official_residents (\n  card_id, first_name, last_name" in seed_sql
