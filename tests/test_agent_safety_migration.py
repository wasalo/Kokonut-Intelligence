"""Regression coverage for worker lifecycle migration role classification."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/598_agent_safety_superuser_session_guard.sql"


def test_superuser_membership_does_not_activate_worker_lifecycle_guard() -> None:
    sql = MIGRATION.read_text()

    assert "current_user = 'kokonut_worker_execution'" in sql
    assert "session_role.rolname = session_user" in sql
    assert "AND session_role.rolsuper" in sql
    assert "AND pg_catalog.pg_has_role(" in sql
    assert "NEW.status IN ('verified', 'published')" in sql


def test_worker_lifecycle_migration_keeps_existing_trigger_attachments() -> None:
    sql = MIGRATION.read_text()

    assert "CREATE OR REPLACE FUNCTION public.assert_agent_safety()" in sql
    assert "CREATE TRIGGER" not in sql
    assert "DROP TRIGGER" not in sql
