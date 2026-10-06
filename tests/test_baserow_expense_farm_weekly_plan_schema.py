"""Contract tests for the owner-approved F002 farm/weekly-plan scope model."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "postgres"
MIGRATION = SCHEMA_DIR / "363_expense_farm_weekly_plan_scope.sql"
OVERRIDE_MIGRATION = SCHEMA_DIR / "365_expense_weekly_plan_scope_exception.sql"
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text()
ALLOWLIST = json.loads((ROOT / "docs/phase1-baserow-projection-allowlist.json").read_text())


def crosswalk_row(section: str, field: str) -> list[str]:
    block = CROSSWALK.split(f"### {section}", 1)[1].split("\n### ", 1)[0]
    for line in block.splitlines():
        if line.startswith("|") and f"`{field}`" in line:
            return [cell.strip() for cell in line.strip("|").split("|")]
    raise AssertionError(f"Missing crosswalk row: {section}.{field}")


def migration_sql() -> str:
    return MIGRATION.read_text() if MIGRATION.exists() else ""


def override_migration_sql() -> str:
    return OVERRIDE_MIGRATION.read_text() if OVERRIDE_MIGRATION.exists() else ""


class ExpenseFarmWeeklyPlanSchemaTests(unittest.TestCase):
    def test_migration_is_new_ordered_and_adds_typed_expense_fks(self):
        sql_files = [path for path in SCHEMA_DIR.glob("*.sql") if path.stem.split("_", 1)[0].isdigit()]
        versions = [path.stem.split("_", 1)[0] for path in sql_files]
        sql = migration_sql()

        self.assertTrue(MIGRATION.exists())
        self.assertEqual(len(versions), len(set(versions)))
        self.assertIn("ADD COLUMN IF NOT EXISTS farm_id UUID REFERENCES farm(id) ON DELETE RESTRICT", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS weekly_plan_id UUID REFERENCES weekly_plan(id) ON DELETE RESTRICT", sql)
        self.assertIn("idx_expense_event_farm_id", sql)
        self.assertIn("idx_expense_event_weekly_plan_id", sql)
        self.assertIn("BEGIN;", sql)
        self.assertIn("COMMIT;", sql)

    def test_expense_and_weekly_plan_writes_enforce_farm_and_location_scope(self):
        sql = migration_sql()
        for expected in (
            "validate_expense_event_farm_weekly_plan_scope",
            "trg_expense_event_farm_weekly_plan_scope",
            "farm_location_id IS DISTINCT FROM NEW.location_id",
            "plan_location_id IS DISTINCT FROM NEW.location_id",
            "plan_farm_id IS NOT NULL AND NEW.farm_id IS DISTINCT FROM plan_farm_id",
            "validate_weekly_plan_farm_scope",
            "trg_weekly_plan_farm_scope",
            "trg_farm_financial_scope",
            "BEFORE UPDATE OF location_id ON farm",
        ):
            self.assertIn(expected, sql)
        self.assertIn("NEW.farm_id IS DISTINCT FROM", sql)
        self.assertIn("weekly_plan_id = NEW.id", sql)

    def test_preexisting_weekly_plan_scope_is_validated_before_trigger_installation(self):
        sql = migration_sql()
        self.assertIn("weekly_plan_farm_location_mismatch", sql)
        self.assertIn("FROM weekly_plan wp", sql)
        self.assertIn("JOIN farm f ON f.id = wp.farm_id", sql)
        self.assertIn("wp.location_id IS DISTINCT FROM f.location_id", sql)

    def test_explicit_owner_approved_cross_farm_exception_still_requires_same_location(self):
        sql = override_migration_sql()
        self.assertTrue(OVERRIDE_MIGRATION.exists())
        self.assertIn("ADD COLUMN IF NOT EXISTS weekly_plan_scope_exception BOOLEAN NOT NULL DEFAULT FALSE", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS weekly_plan_scope_exception_reason TEXT", sql)
        self.assertIn("weekly_plan_scope_exception = TRUE", sql)
        self.assertIn("weekly_plan_scope_exception_reason", sql)
        self.assertIn("plan_location_id IS DISTINCT FROM NEW.location_id", sql)
        self.assertIn("NEW.weekly_plan_scope_exception", sql)
        self.assertIn("e.weekly_plan_scope_exception", sql)
        self.assertIn("different farms at the same location", sql.casefold())

    def test_crosswalk_allocates_relationships_but_keeps_import_out_of_scope(self):
        expense_section = "F002 — Expenses (table ID `317575`; 22 fields)"
        weekly_section = "Weekly Planning (table ID `415230`; 10 fields)"
        entity = crosswalk_row(expense_section, "Entity")
        self.assertIn("expense_event.farm_id", entity[2])
        self.assertIn("expense_event.location_id", entity[2])
        self.assertEqual(entity[3], "`RELATIONSHIP`")

        for section, field in ((expense_section, "Weekly Planning"), (weekly_section, "KKN-F002 - Expenses")):
            row = crosswalk_row(section, field)
            self.assertIn("expense_event.weekly_plan_id", row[2])
            self.assertEqual(row[3], "`RELATIONSHIP`")
            self.assertIn("49", row[4])
            self.assertIn("48", row[4])
            self.assertIn("scope_exception", row[4].casefold())
            self.assertIn("same location", row[4].casefold())

        source_table_ids = {str(spec["source_table_id"]) for spec in ALLOWLIST["target_tables"]}
        self.assertNotIn("317575", source_table_ids)
        self.assertNotIn("415230", source_table_ids)


if __name__ == "__main__":
    unittest.main()
