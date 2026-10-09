"""Schema and crosswalk checks for Staff relationship allocation."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "postgres"
MIGRATION = SCHEMA_DIR / "362_farm_staff_membership.sql"
CROSSWALK = ROOT / "docs" / "phase1-baserow-field-crosswalk.md"


class BaserowFarmStaffMembershipTests(unittest.TestCase):
    def test_migration_version_is_unique(self):
        migrations = [
            path for path in SCHEMA_DIR.glob("*.sql")
            if path.stem.split("_", 1)[0].isdigit()
        ]
        versions = [path.stem.split("_", 1)[0] for path in migrations]
        self.assertIn(MIGRATION, migrations)
        self.assertEqual(len(versions), len(set(versions)))

    def test_membership_is_typed_many_to_many_with_optional_edge_provenance(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        for expected in (
            "CREATE TABLE IF NOT EXISTS farm_staff_member",
            "farm_id UUID NOT NULL REFERENCES farm(id)",
            "staff_id UUID NOT NULL REFERENCES staff(id)",
            "PRIMARY KEY (farm_id, staff_id)",
            "chk_farm_staff_member_source_identity",
            "source_related_row_id BIGINT",
            "uq_farm_staff_member_source_edge",
            "BEGIN;",
            "COMMIT;",
        ):
            self.assertIn(expected, sql)
        self.assertNotIn("employment_status", sql)
        self.assertNotIn("hire_date", sql)

    def test_source_team_relation_maps_once_through_stable_ids(self):
        crosswalk = CROSSWALK.read_text(encoding="utf-8")
        self.assertIn(
            "`Projects - Team` (`2202729`) | `link_row` → `Kokonut Farms` | `farm_staff_member(farm_id, staff_id)` | `RELATIONSHIP`",
            crosswalk,
        )
        self.assertIn(
            "`Team` (`2202766`) | `link_row` → `Staff` | `farm_staff_member(farm_id, staff_id)` | `RELATIONSHIP`",
            crosswalk,
        )
        self.assertIn("validate exact edge-set equality", crosswalk)

    def test_staff_task_activity_and_expense_links_are_documented(self):
        crosswalk = CROSSWALK.read_text(encoding="utf-8")
        f001_staff = [line for line in crosswalk.splitlines() if "`KKN-F001` (`2350179`)" in line]
        self.assertEqual(len(f001_staff), 1)
        self.assertIn("| — | `EXCLUDE_OWNER` |", f001_staff[0])
        self.assertIn("Batch 45 owner decision", f001_staff[0])
        self.assertNotIn("farm_activity_responsible_staff", f001_staff[0])
        f002_actor = [line for line in crosswalk.splitlines() if "`Authorized by` (`2350403`)" in line]
        staff_actor = [line for line in crosswalk.splitlines() if "`Ground Expenses` (`2350404`)" in line]
        self.assertEqual(len(f002_actor), 1)
        self.assertEqual(len(staff_actor), 1)
        for line in (f002_actor[0], staff_actor[0]):
            self.assertIn("| — | `EXCLUDE_OWNER` |", line)
            self.assertIn("Batch 37 owner", line)
        self.assertIn("no workflow `approved_by` value is populated", f002_actor[0])
        self.assertIn("Staff rows remain independently scoped", staff_actor[0])

    def test_staff_name_is_owner_excluded_without_dropping_the_staff_table_scope(self):
        crosswalk = CROSSWALK.read_text(encoding="utf-8")
        name_line = next(line for line in crosswalk.splitlines() if "`Name` (`2202722`)" in line)
        self.assertIn("| — | `EXCLUDE_OWNER` |", name_line)
        self.assertIn("Batch 38 owner drops Staff.Name", name_line)
        self.assertIn("Staff rows and other Staff fields remain separately scoped", name_line)
        self.assertIn("F001 responsibility edge is excluded by Batch 45", name_line)
        self.assertNotIn("F001 responsibility identity remains a separate hold", name_line)

    def test_active_boolean_uses_strict_parse_without_employment_inference(self):
        crosswalk = CROSSWALK.read_text(encoding="utf-8")
        self.assertIn("`Active` (`8686938`) | `boolean` | `staff.is_active` | `CANDIDATE`", crosswalk)
        self.assertIn("strict boolean parse", crosswalk.casefold())
        self.assertIn("not `employment_status`", crosswalk)


if __name__ == "__main__":
    unittest.main()
