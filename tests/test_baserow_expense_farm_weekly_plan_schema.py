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

    def test_weekly_planning_table_and_all_inverse_edges_are_owner_excluded(self):
        expense_section = "F002 — Expenses (table ID `317575`; 22 fields)"
        weekly_section = "Weekly Planning (table ID `415230`; 10 fields)"
        entity = crosswalk_row(expense_section, "Entity")
        self.assertIn("expense_event.farm_id", entity[2])
        self.assertIn("expense_event.location_id", entity[2])
        self.assertEqual(entity[3], "`RELATIONSHIP`")

        expense_link = crosswalk_row(expense_section, "Weekly Planning")
        weekly_expense_inverse = crosswalk_row(weekly_section, "KKN-F002 - Expenses")
        for row in (expense_link, weekly_expense_inverse):
            self.assertEqual(row[2], "—")
            self.assertEqual(row[3], "`EXCLUDE_OWNER`")
            self.assertIn("49", row[4])
            self.assertIn("controlled archive", row[4])

        weekly_fields = (
            "Week", "Notes", "KKN-F001 — Daily Report", "KKN-F002 - Expenses",
            "Date Start", "Date End", "Kokonut Farms", "Budget Forecast", "Farms Individual Tasks",
        )
        for field in weekly_fields:
            row = crosswalk_row(weekly_section, field)
            self.assertEqual(row[2], "—")
            self.assertEqual(row[3], "`EXCLUDE_OWNER`")
        self.assertEqual(crosswalk_row(weekly_section, "Expenses Actuals")[3], "`EXCLUDE_DERIVED`")

        for section, field in (
            ("F001 — Activity Report (table ID `322673`; 16 fields)", "Weekly Planning"),
            ("Kokonut Farm Tasks (table ID `305801`; 34 fields)", "Weekly Planning"),
            ("Kokonut Farms (table ID `305805`; 54 fields)", "Weekly Planning"),
        ):
            row = crosswalk_row(section, field)
            self.assertEqual(row[3], "`EXCLUDE_OWNER`")

        for section, field in (
            (weekly_section, "KKN-F001 — Daily Report"),
            (weekly_section, "Farms Individual Tasks"),
        ):
            row = crosswalk_row(section, field)
            self.assertEqual(row[3], "`EXCLUDE_OWNER`")

        source_table_ids = {str(spec["source_table_id"]) for spec in ALLOWLIST["target_tables"]}
        self.assertIn("317575", source_table_ids)
        self.assertNotIn("415230", source_table_ids)

    def test_expense_projection_uses_only_reviewed_farm_task_and_amount_fields(self):
        expense_section = "F002 — Expenses (table ID `317575`; 22 fields)"
        expense_spec = next(spec for spec in ALLOWLIST["target_tables"] if spec["source_table_id"] == "317575")
        allowlisted_fields = set(expense_spec["fields"])
        for field, field_id, target, disposition in (
            ("Entity", "2305091", "`expense_event.farm_id` + `expense_event.location_id`", "`RELATIONSHIP`"),
            ("Tasks", "2330115", "`expense_event.farm_task_id`", "`RELATIONSHIP`"),
            ("Monto a Depositar", "2356443", "`expense_event.amount`", "`CANDIDATE`"),
        ):
            row = crosswalk_row(expense_section, field)
            self.assertEqual(row[2], target)
            self.assertEqual(row[3], disposition)
            self.assertIn(field_id, allowlisted_fields)

        for field, field_id, disposition in (
            ("Bank Account", "2305190", "`EXCLUDE_SENSITIVE`"),
            ("Authorized by", "2350403", "`EXCLUDE_OWNER`"),
            ("Archivos", "2305208", "`MANUAL_CURATION`"),
        ):
            row = crosswalk_row(expense_section, field)
            self.assertEqual(row[3], disposition)
            self.assertNotIn(field_id, allowlisted_fields)

    def test_owner_approves_exact_labor_category_without_normalizing_other_labels(self):
        expense_section = "F002 — Expenses (table ID `317575`; 22 fields)"

        category = crosswalk_row(expense_section, "Category")
        self.assertEqual(category[2], "`expense_event.category`")
        self.assertEqual(category[3], "`CONDITIONAL`")
        self.assertIn("exact source option label `Labor`", category[4])
        self.assertIn("mapped to canonical `labor`", category[4])
        self.assertIn("hold every other Category label/option and blank Category value", category[4])
        self.assertIn("supersedes the prior full Category DROP", category[4])

        expense_spec = next(spec for spec in ALLOWLIST["target_tables"] if spec["source_table_id"] == "317575")
        category_rule = expense_spec["fields"]["2330114"]
        self.assertEqual(category_rule["source_disposition"], "CONDITIONAL")
        self.assertEqual(category_rule["source_label"], "Labor")
        self.assertEqual(category_rule["option_map"], {"1775981": "labor"})

        status = crosswalk_row(expense_section, "Expense Status")
        self.assertEqual(status[2], "`expense_event.payment_status`")
        self.assertEqual(status[3], "`CANDIDATE`")
        self.assertIn("stable source option ID", status[4])
        self.assertIn("without normalization", status[4])
        self.assertIn("533 populated values", status[4])
        self.assertIn("at most 14 characters", status[4])
        self.assertIn("separate from workflow", status[4])

        people_count = crosswalk_row(expense_section, "Personas Impactadas")
        self.assertEqual(people_count[2], "`expense_event.people_impacted_count`")
        self.assertEqual(people_count[3], "`CANDIDATE`")
        self.assertIn("count of people per expense", people_count[4])
        self.assertIn("512 populated values, all positive integers", people_count[4])
        self.assertIn("21 blank cells", people_count[4])
        self.assertIn("map blanks to NULL", people_count[4])


        authorized_by = crosswalk_row(expense_section, "Authorized by")
        self.assertEqual(authorized_by[2], "—")
        self.assertEqual(authorized_by[3], "`EXCLUDE_OWNER`")
        self.assertIn("Batch 37 owner drops", authorized_by[4])
        self.assertIn("no workflow `approved_by` value is populated", authorized_by[4])

        self.assertIn("Batch 44 maps each of the 13 additional used option IDs", CROSSWALK)
        self.assertIn("12 occur as single selections across 127 rows", CROSSWALK)
        self.assertIn("one occurs only in the multi-selection rows", CROSSWALK)
        self.assertIn("first selected option in source order as the primary `activity_type`", CROSSWALK)
        self.assertIn("preserve every selected option ID/label/order", CROSSWALK)
        self.assertIn("Batch 46 implements that scope", CROSSWALK)

        source_table_ids = {str(spec["source_table_id"]) for spec in ALLOWLIST["target_tables"]}
        self.assertIn("317575", source_table_ids)


if __name__ == "__main__":
    unittest.main()
