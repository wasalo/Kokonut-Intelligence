"""Schema expectations for Baserow Farm Task relationship mapping."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "postgres"
MIGRATION = SCHEMA_DIR / "361_farm_task_relationships.sql"


class BaserowFarmTaskRelationshipSchemaTests(unittest.TestCase):
    def test_migration_file_is_present_and_uses_unique_numeric_version(self):
        files = [
            path for path in SCHEMA_DIR.glob("*.sql")
            if path.stem.split("_", 1)[0].isdigit()
        ]
        versions = [path.stem.split("_", 1)[0] for path in files]

        self.assertIn(MIGRATION, files)
        self.assertEqual(len(versions), len(set(versions)))

    def test_relationship_targets_are_typed_and_provenance_bearing(self):
        sql = MIGRATION.read_text(encoding="utf-8")

        for expected in (
            "ADD COLUMN IF NOT EXISTS farm_task_id UUID REFERENCES farm_task(id)",
            "CREATE TABLE IF NOT EXISTS farm_task_dependency",
            "CREATE TABLE IF NOT EXISTS farm_task_framework_step",
            "CREATE TABLE IF NOT EXISTS farm_task_weekly_plan",
            "prerequisite_task_id UUID NOT NULL REFERENCES farm_task(id)",
            "framework_step_id UUID NOT NULL REFERENCES framework_step(id)",
            "weekly_plan_id UUID NOT NULL REFERENCES weekly_plan(id)",
            "source_related_row_id BIGINT",
            "chk_farm_task_dependency_not_self",
            "validate_expense_event_farm_task_scope",
            "trg_expense_event_farm_task_scope",
            "uq_farm_task_dependency_source_edge",
            "uq_farm_task_framework_step_source_edge",
            "uq_farm_task_weekly_plan_source_edge",
            "BEGIN;",
            "COMMIT;",
        ):
            self.assertIn(expected, sql)

    def test_expense_task_link_is_location_scoped_and_self_prerequisites_are_rejected(self):
        sql = MIGRATION.read_text(encoding="utf-8")

        self.assertIn("task_location_id <> NEW.location_id", sql)
        self.assertIn("CHECK (task_id <> prerequisite_task_id)", sql)

    def test_association_source_provenance_is_all_or_none(self):
        sql = MIGRATION.read_text(encoding="utf-8")

        self.assertEqual(sql.count("source_system IS NULL AND source_database_id IS NULL"), 3)
        self.assertEqual(sql.count("source_system IS NOT NULL AND btrim(source_system) <> ''"), 3)
