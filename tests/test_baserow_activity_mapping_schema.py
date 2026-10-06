"""Schema expectations for the owner-approved F001/F003 mapping model."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "postgres"
MIGRATION = SCHEMA_DIR / "359_activity_scope_and_outputs.sql"


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

    def test_mapping_schema_preserves_nonnegative_elapsed_time_and_date_order(self):
        sql = MIGRATION.read_text(encoding="utf-8")

        self.assertIn("CHECK (duration_minutes >= 0)", sql)
        self.assertIn("CHECK (activity_end_date IS NULL OR activity_end_date >= activity_date)", sql)
