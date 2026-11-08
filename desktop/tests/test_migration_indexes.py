"""Tests for performance indexes migration and idempotency."""

from pathlib import Path
import re
import sqlite3

MIGRATION_PATH = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "20261108140000_fk_and_covering_indexes.sql"


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file(), f"Migration file missing at {MIGRATION_PATH}"


def test_migration_contract_rules():
    content = MIGRATION_PATH.read_text(encoding="utf-8")

    # Rule 1: No CONCURRENTLY
    assert "concurrently" not in content.lower(), "Migrations must not use CONCURRENTLY inside transactions"

    # Rule 2: Uses CREATE INDEX IF NOT EXISTS
    index_statements = re.findall(
        r"create\s+index\s+if\s+not\s+exists\s+([a-zA-Z0-9_]+)\s+on\s+([a-zA-Z0-9_]+)\s*\(([^)]+)\)",
        content,
        re.IGNORECASE,
    )
    assert len(index_statements) == 5, f"Expected 5 indexes, found {len(index_statements)}"

    index_names = [stmt[0] for stmt in index_statements]
    assert "idx_students_room_id" in index_names
    assert "idx_students_reviewed_by" in index_names
    assert "idx_maintenance_reports_handled_by" in index_names
    assert "idx_room_change_requests_decided_by" in index_names
    assert "idx_rooms_block_floor_number" in index_names

    # Rule 3: Each index must have a comment above it explaining which query it serves
    lines = content.splitlines()
    for idx_name in index_names:
        line_idx = next(i for i, line in enumerate(lines) if idx_name in line)
        preceding = "\n".join(lines[max(0, line_idx - 5):line_idx])
        assert "--" in preceding and "serves" in preceding.lower(), (
            f"Index {idx_name} must have a preceding SQL comment explaining which query it serves"
        )


def test_migration_idempotent_execution_sqlite():
    """Verify that the DDL statements execute cleanly twice without error."""
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()

    # Create dummy base tables
    cur.execute("CREATE TABLE students (id TEXT PRIMARY KEY, room_id TEXT, reviewed_by TEXT)")
    cur.execute("CREATE TABLE maintenance_reports (id TEXT PRIMARY KEY, handled_by TEXT)")
    cur.execute("CREATE TABLE room_change_requests (id TEXT PRIMARY KEY, decided_by TEXT)")
    cur.execute("CREATE TABLE rooms (id TEXT PRIMARY KEY, block TEXT, floor INTEGER, number TEXT)")

    content = MIGRATION_PATH.read_text(encoding="utf-8")
    statements = [
        s.strip()
        for s in content.split(";")
        if s.strip() and not s.strip().startswith("--")
    ]

    # First pass
    for stmt in statements:
        # SQLite compatible execution
        cur.execute(stmt)

    # Second pass (idempotency check)
    for stmt in statements:
        cur.execute(stmt)

    # Rollback execution check
    rollback_sql = """
    DROP INDEX IF EXISTS idx_students_room_id;
    DROP INDEX IF EXISTS idx_students_reviewed_by;
    DROP INDEX IF EXISTS idx_maintenance_reports_handled_by;
    DROP INDEX IF EXISTS idx_room_change_requests_decided_by;
    DROP INDEX IF EXISTS idx_rooms_block_floor_number;
    """
    for drop_stmt in rollback_sql.strip().split(";"):
        if drop_stmt.strip():
            cur.execute(drop_stmt.strip())

    conn.close()
