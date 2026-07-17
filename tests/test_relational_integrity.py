"""Focused source-level checks for operational ER integrity migration."""

from pathlib import Path


MIGRATION = Path("schemas/postgres/308_er_integrity_foundations.sql")


def test_operational_integrity_migration_covers_all_context_tables():
    sql = MIGRATION.read_text()
    for table in ("farm_activity", "harvest_event", "sales_event", "expense_event"):
        assert f"trg_{table}_operational_context" in sql
    assert "crop_cycle_location" not in sql
    assert "existing crop_cycle rows contain inconsistent location ownership" in sql


def test_migration_uses_deferred_constraint_triggers_and_does_not_edit_prior_files():
    sql = MIGRATION.read_text()
    assert sql.count("CREATE CONSTRAINT TRIGGER") >= 7
    assert "DEFERRABLE INITIALLY IMMEDIATE" in sql
    assert "CREATE OR REPLACE FUNCTION validate_operational_context" in sql


def test_trusted_pilot_seed_reconciliation_is_explicit():
    sql = MIGRATION.read_text()
    seed = Path("schemas/seeds/112_pilot_operational_context.sql").read_text()
    script = Path("scripts/seed-pilot.sh").read_text()
    assert "kokonut.seed_context" in sql
    assert "Pilot context reconciled to crop_cycle" in seed
    assert "apply_pilot_seed" in script
