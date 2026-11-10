"""Contract and regression tests for explicit query projections.

Enforces:
1. Contract tests: each query projection includes all fields required by UI pages,
   live-sync workers, dialogs, CSV exports, and filtering.
2. Grep regression test: no wildcard selects (e.g. `select("*")`) exist in application
   code across desktop/app and web/src.
"""

from __future__ import annotations

import ast
import inspect
import re
import textwrap
from pathlib import Path
from typing import Any, Callable

import pytest


# -----------------------------------------------------------------------------
# Fixtures representing consumer requirements
# -----------------------------------------------------------------------------

@pytest.fixture
def pending_required_fields() -> set[str]:
    """Fields consumed by PendingPage, detail dialog, CSV export, and live sync."""
    return {
        "id",
        "card_id",
        "first_name",
        "last_name",
        "birth_date",
        "gender",
        "phone",
        "email",
        "university",
        "faculty",
        "study_level",
        "wilaya",
        "status",
        "rejection_reason",
        "room_id",
        "reviewed_by",
        "reviewed_at",
        "created_at",
    }


@pytest.fixture
def residents_required_fields() -> set[str]:
    """Fields consumed by ResidentsPage, table rows, and filters."""
    return {
        "id",
        "card_id",
        "first_name",
        "last_name",
        "birth_date",
        "gender",
        "phone",
        "email",
        "university",
        "faculty",
        "study_level",
        "wilaya",
        "status",
        "room_id",
        "created_at",
    }


@pytest.fixture
def maintenance_required_fields() -> set[str]:
    """Fields consumed by MaintenancePage, report cards, filters, and live sync."""
    return {
        "id",
        "student_id",
        "category",
        "description",
        "photo_path",
        "status",
        "staff_note",
        "created_at",
        "updated_at",
    }


@pytest.fixture
def room_changes_required_fields() -> set[str]:
    """Fields consumed by RoomChangesPage, table, status views, and live sync."""
    return {
        "id",
        "student_id",
        "current_room_id",
        "preferred_room_id",
        "reason",
        "status",
        "decision_note",
        "decided_by",
        "decided_at",
        "created_at",
        "updated_at",
    }


@pytest.fixture
def official_roster_required_fields() -> set[str]:
    """Fields consumed by OfficialListPage and official_lookup verification."""
    return {
        "card_id",
        "first_name",
        "last_name",
        "birth_date",
        "gender",
        "university",
        "faculty",
    }


@pytest.fixture
def rooms_required_fields() -> set[str]:
    """Fields consumed by RoomsPage and room allocation."""
    return {
        "id",
        "block",
        "floor",
        "number",
        "capacity",
    }


@pytest.fixture
def blocks_required_fields() -> set[str]:
    """Fields consumed by ManageBlocksDialog and RoomsPage."""
    return {
        "id",
        "name",
    }


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def extract_table_selects(target: Callable[..., Any]) -> list[tuple[str | None, str]]:
    """Extract (table_name, select_argument) pairs in source line order."""
    src = textwrap.dedent(inspect.getsource(target))
    tree = ast.parse(src)
    calls: list[tuple[int, str | None, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "select"
            and node.args
        ):
            table_name = None
            val = node.func.value
            if (
                isinstance(val, ast.Call)
                and isinstance(val.func, ast.Attribute)
                and val.func.attr == "table"
                and val.args
            ):
                try:
                    table_name = ast.literal_eval(val.args[0])
                except Exception:
                    pass
            try:
                arg = ast.literal_eval(node.args[0])
                if isinstance(arg, str):
                    calls.append((node.lineno, table_name, arg))
            except Exception:
                pass
    calls.sort(key=lambda x: x[0])
    return [(tbl, arg) for _, tbl, arg in calls]


def parse_projection_fields(projection_str: str) -> set[str]:
    """Extract top-level column names from a PostgREST select projection."""
    cleaned = re.sub(r"\s+", " ", projection_str).strip()
    # Remove nested relations like rooms(...) or students(...)
    top_level = re.sub(r"\w+\([^)]*\)", "", cleaned)
    parts = [part.strip() for part in top_level.split(",") if part.strip()]
    return set(parts)


# -----------------------------------------------------------------------------
# Contract Tests
# -----------------------------------------------------------------------------

def test_pending_projections_contract(pending_required_fields):
    from desktop.app.ui.pages.pending import PendingPage
    from desktop.app.ui.live_sync import LiveSyncWorker

    pending_calls = extract_table_selects(PendingPage._fetch_snapshot)
    assert pending_calls, "PendingPage._fetch_snapshot must call .select()"
    p_fields = parse_projection_fields(pending_calls[0][1])
    assert pending_required_fields.issubset(p_fields), (
        f"Missing fields in PendingPage projection: {pending_required_fields - p_fields}"
    )

    sync_calls = extract_table_selects(LiveSyncWorker._step)
    # The first query in LiveSyncWorker is pending students
    students_sync = [arg for tbl, arg in sync_calls if tbl == "students" and arg != "id"]
    assert students_sync, "LiveSyncWorker must have explicit select for students"
    s_fields = parse_projection_fields(students_sync[0])
    assert pending_required_fields.issubset(s_fields), (
        f"Missing fields in LiveSyncWorker students projection: {pending_required_fields - s_fields}"
    )


def test_residents_projections_contract(residents_required_fields):
    from desktop.app.ui.pages.residents import ResidentsPage

    calls = extract_table_selects(ResidentsPage._fetch_residents)
    assert calls, "ResidentsPage._fetch_residents must call .select()"
    fields = parse_projection_fields(calls[0][1])
    assert residents_required_fields.issubset(fields), (
        f"Missing fields in ResidentsPage projection: {residents_required_fields - fields}"
    )
    assert "rooms(block, number, floor)" in calls[0][1]


def test_maintenance_projections_contract(maintenance_required_fields):
    from desktop.app.ui.pages.maintenance import MaintenancePage
    from desktop.app.ui.live_sync import LiveSyncWorker

    maint_calls = extract_table_selects(MaintenancePage._fetch_rows)
    assert maint_calls, "MaintenancePage._fetch_rows must call .select()"
    m_fields = parse_projection_fields(maint_calls[0][1])
    assert maintenance_required_fields.issubset(m_fields)
    assert "students(first_name, last_name, card_id)" in maint_calls[0][1]

    sync_calls = extract_table_selects(LiveSyncWorker._step)
    maint_sync = [arg for tbl, arg in sync_calls if tbl == "maintenance_reports"]
    assert maint_sync, "LiveSyncWorker must query maintenance_reports"
    s_fields = parse_projection_fields(maint_sync[0])
    assert maintenance_required_fields.issubset(s_fields)
    assert "students(first_name, last_name, card_id)" in maint_sync[0]


def test_room_changes_projections_contract(room_changes_required_fields):
    from desktop.app.ui.pages.room_changes import RoomChangesPage
    from desktop.app.ui.live_sync import LiveSyncWorker

    rc_calls = extract_table_selects(RoomChangesPage._fetch_requests)
    assert rc_calls, "RoomChangesPage._fetch_requests must call .select()"
    r_fields = parse_projection_fields(rc_calls[0][1])
    assert room_changes_required_fields.issubset(r_fields)
    assert "students(first_name, last_name, gender, card_id)" in rc_calls[0][1]
    assert "staff(full_name)" in rc_calls[0][1]

    sync_calls = extract_table_selects(LiveSyncWorker._step)
    rc_sync = [arg for tbl, arg in sync_calls if tbl == "room_change_requests"]
    assert rc_sync, "LiveSyncWorker must query room_change_requests"
    s_fields = parse_projection_fields(rc_sync[0])
    assert room_changes_required_fields.issubset(s_fields)
    assert "students(first_name, last_name, gender, card_id)" in rc_sync[0]
    assert "staff(full_name)" in rc_sync[0]


def test_official_roster_projections_contract(official_roster_required_fields):
    from desktop.app.ui.pages.official_list import OfficialListPage
    from desktop.app.client import official_lookup

    off_calls = extract_table_selects(OfficialListPage._fetch_roster)
    assert off_calls, "OfficialListPage._fetch_roster must call .select()"
    o_fields = parse_projection_fields(off_calls[0][1])
    assert official_roster_required_fields.issubset(o_fields)

    lookup_calls = extract_table_selects(official_lookup)
    assert lookup_calls, "official_lookup must call .select()"
    l_fields = parse_projection_fields(lookup_calls[0][1])
    assert official_roster_required_fields.issubset(l_fields)


def test_rooms_and_blocks_projections_contract(rooms_required_fields, blocks_required_fields):
    from desktop.app.ui.pages.rooms import RoomsPage, ManageBlocksDialog

    r_calls = extract_table_selects(RoomsPage._fetch_snapshot)
    rooms_queries = [arg for tbl, arg in r_calls if tbl == "rooms"]
    blocks_queries = [arg for tbl, arg in r_calls if tbl == "blocks"]
    assert rooms_queries, "RoomsPage._fetch_snapshot must query rooms"
    assert blocks_queries, "RoomsPage._fetch_snapshot must query blocks"

    r_fields = parse_projection_fields(rooms_queries[0])
    assert rooms_required_fields.issubset(r_fields)

    rb_fields = parse_projection_fields(blocks_queries[0])
    assert blocks_required_fields.issubset(rb_fields)

    b_calls = extract_table_selects(ManageBlocksDialog._fetch_blocks)
    assert b_calls, "ManageBlocksDialog._fetch_blocks must call .select()"
    b_fields = parse_projection_fields(b_calls[0][1])
    assert blocks_required_fields.issubset(b_fields)


# -----------------------------------------------------------------------------
# Regression Grep Test: No Wildcard Selects in App Code
# -----------------------------------------------------------------------------

def test_no_wildcard_select_in_desktop_or_web():
    """Grep-style regression test ensuring NO select('*') or select('*,...') remains."""
    repo_root = Path(__file__).resolve().parent.parent.parent

    # Check desktop/app
    desktop_app_dir = repo_root / "desktop" / "app"
    violations: list[str] = []

    wildcard_pattern = re.compile(r'\.select\(\s*[\'"][^"\']*\*[^"\']*[\'"]\s*\)')

    for py_file in desktop_app_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        matches = wildcard_pattern.findall(content)
        if matches:
            violations.append(f"{py_file.relative_to(repo_root)}: {matches}")

    # Check web/src
    web_src_dir = repo_root / "web" / "src"
    if web_src_dir.exists():
        for file_path in web_src_dir.rglob("*"):
            if file_path.suffix in {".ts", ".astro", ".js"}:
                content = file_path.read_text(encoding="utf-8")
                matches = wildcard_pattern.findall(content)
                if matches:
                    violations.append(f"{file_path.relative_to(repo_root)}: {matches}")

    assert not violations, (
        "Wildcard queries (select('*')) were found in application code:\n"
        + "\n".join(violations)
    )
