"""Schema expectations for the owner-approved F001/F003 mapping model."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "postgres"
MIGRATION = SCHEMA_DIR / "359_activity_scope_and_outputs.sql"
CROSSWALK = (ROOT / "docs" / "phase1-baserow-field-crosswalk.md").read_text(encoding="utf-8")
PROPOSAL = (
    ROOT / "docs" / "phase1-baserow-activity-selection-schema-proposal-batch40.md"
).read_text(encoding="utf-8")


class BaserowActivityMappingSchemaTests(unittest.TestCase):
    def test_migration_file_is_present_and_uses_unique_numeric_version(self):
        files = [
            path for path in SCHEMA_DIR.glob("*.sql")
            if path.stem.split("_", 1)[0].isdigit()
        ]
        selected = [path for path in files if path.name == MIGRATION.name]
        versions = [path.stem.split("_", 1)[0] for path in files]

        self.assertEqual(len(selected), 1)
        self.assertEqual(len(versions), len(set(versions)))

    def test_activity_mapping_schema_has_typed_columns_and_relationship_tables(self):
        sql = MIGRATION.read_text(encoding="utf-8")

        for expected in (
            "ADD COLUMN IF NOT EXISTS farm_id UUID REFERENCES farm(id)",
            "ADD COLUMN IF NOT EXISTS farm_task_id UUID REFERENCES farm_task(id)",
            "ADD COLUMN IF NOT EXISTS duration_minutes INTEGER",
            "ADD COLUMN IF NOT EXISTS activity_end_date DATE",
            "CREATE TABLE IF NOT EXISTS farm_activity_responsible_staff",
            "CREATE TABLE IF NOT EXISTS farm_activity_plot",
            "CREATE TABLE IF NOT EXISTS farm_activity_output",
            "CREATE TABLE IF NOT EXISTS farm_activity_output_activity",
            "source_database_id BIGINT NOT NULL",
            "source_related_row_id BIGINT NOT NULL",
            "validate_farm_activity_scope",
            "chk_farm_activity_duration_minutes",
            "chk_farm_activity_end_date",
            "activity-scope-outputs-v1",
        ):
            self.assertIn(expected, sql)

    def test_land_lots_daily_report_is_the_validated_inverse_of_approved_plot_edges(self):
        activity_line = next(
            line for line in CROSSWALK.splitlines()
            if "`Plot of Land` (`3143346`)" in line
        )
        plot_line = next(
            line for line in CROSSWALK.splitlines()
            if "`KKN-F001 — Daily Report` (`3143347`)" in line
        )

        self.assertIn("`farm_activity_plot`", activity_line)
        self.assertIn("`farm_activity_plot(activity_id, plot_id)` (inverse-only)", plot_line)
        self.assertIn("359 edges on each side", plot_line)
        self.assertIn("source edge sets exactly equal (zero differences)", plot_line)
        self.assertIn("`RELATIONSHIP`", plot_line)

    def test_mapping_schema_preserves_nonnegative_elapsed_time_and_date_order(self):
        sql = MIGRATION.read_text(encoding="utf-8")

        self.assertIn("CHECK (duration_minutes >= 0)", sql)
        self.assertIn("CHECK (activity_end_date IS NULL OR activity_end_date >= activity_date)", sql)

    def test_candidate_mapping_has_scratch_scope_but_not_persistent_import_authority(self):
        activity_line = next(
            line for line in CROSSWALK.splitlines()
            if "`Actividad` (`2350134`)" in line
        )

        self.assertIn("activity_type_source_options JSONB", PROPOSAL)
        self.assertIn("exact source metadata label", PROPOSAL)
        self.assertIn("first selected option in source order", PROPOSAL)
        self.assertIn("Batch 45 separately authorizes scratch projection-scope expansion", PROPOSAL)
        self.assertIn("no persistent import is authorized", PROPOSAL)
        self.assertEqual(activity_line.split("|")[4].strip(), "`CANDIDATE`")
        self.assertIn("exact source metadata label", activity_line)
        self.assertIn("first selected option in source order", activity_line)
        self.assertIn("Batch 45 authorizes scratch projection", activity_line)
        self.assertIn("not a persistent import", activity_line)
        self.assertIn("13 additional", activity_line)

    def test_batch42_strategy_and_batch44_primary_rule_are_recorded(self):
        activity_line = next(
            line for line in CROSSWALK.splitlines()
            if "`Actividad` (`2350134`)" in line
        )

        self.assertIn("first selected option in source order", activity_line)
        self.assertIn("preserve every selected option ID/label/order", activity_line)
        self.assertIn("do not split rows", activity_line)
        self.assertIn("`CANDIDATE`", activity_line)
        self.assertIn("Batch 45 authorizes scratch projection", activity_line)
        self.assertIn("not a persistent import", activity_line)

    def test_activity_source_options_migration_adds_nullable_json_array_field(self):
        migration = SCHEMA_DIR / "369_baserow_activity_source_options.sql"
        self.assertTrue(migration.is_file())
        sql = migration.read_text(encoding="utf-8")

        self.assertIn("ADD COLUMN IF NOT EXISTS activity_type_source_options JSONB", sql)
        self.assertIn("jsonb_typeof(activity_type_source_options) = 'array'", sql)
        self.assertIn("COMMENT ON COLUMN public.farm_activity.activity_type_source_options", sql)
        self.assertNotIn("ALTER COLUMN activity_type DROP NOT NULL", sql)
        self.assertNotIn("UPDATE public.farm_activity", sql)

    def test_migration_rehearsal_status_is_scratch_only_and_current(self):
        activity_line = next(
            line for line in CROSSWALK.splitlines()
            if "`Actividad` (`2350134`)" in line
        )

        self.assertIn("isolated disposable PostgreSQL rehearsal", PROPOSAL)
        self.assertIn("not been applied to any persistent database", PROPOSAL)
        self.assertIn("Batch 45 authorizes scratch projection", activity_line)
        self.assertNotIn("has not been PostgreSQL-rehearsed", activity_line)

    def test_owner_exclusion_drops_both_f001_staff_relationship_fields(self):
        activity_line = next(
            line for line in CROSSWALK.splitlines()
            if "`Responsable` (`2350178`)" in line
        )
        staff_line = next(
            line for line in CROSSWALK.splitlines()
            if "`KKN-F001` (`2350179`)" in line
        )

        for line in (activity_line, staff_line):
            columns = [column.strip() for column in line.split("|")]
            self.assertEqual(columns[3], "—")
            self.assertEqual(columns[4], "`EXCLUDE_OWNER`")
            self.assertIn("controlled archive", line)
