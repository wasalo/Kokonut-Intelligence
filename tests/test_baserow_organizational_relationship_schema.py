"""Schema expectations for Baserow organizational relationship mapping."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "postgres"
MIGRATION = SCHEMA_DIR / "360_job_role_department_relationships.sql"


class BaserowOrganizationalRelationshipSchemaTests(unittest.TestCase):
    def test_migration_file_is_present_and_uses_unique_numeric_version(self):
        files = [
            path for path in SCHEMA_DIR.glob("*.sql")
            if path.stem.split("_", 1)[0].isdigit()
        ]
        versions = [path.stem.split("_", 1)[0] for path in files]

        self.assertIn(MIGRATION, files)
        self.assertEqual(len(versions), len(set(versions)))

    def test_job_role_department_relation_preserves_many_to_many_edges(self):
        sql = MIGRATION.read_text(encoding="utf-8")

        for expected in (
            "CREATE TABLE IF NOT EXISTS job_role_department",
            "job_role_id UUID NOT NULL REFERENCES job_role(id) ON DELETE CASCADE",
            "department_id UUID NOT NULL REFERENCES department(id) ON DELETE CASCADE",
            "PRIMARY KEY (job_role_id, department_id)",
            "source_related_row_id BIGINT",
            "chk_job_role_department_source_identity",
            "uq_job_role_department_source_edge",
            "idx_job_role_department_department",
            "BEGIN;",
            "COMMIT;",
        ):
            self.assertIn(expected, sql)

    def test_source_provenance_is_all_or_none_and_edge_unique(self):
        sql = MIGRATION.read_text(encoding="utf-8")

        self.assertIn("source_system IS NULL", sql)
        self.assertIn("source_system IS NOT NULL", sql)
        self.assertIn("AND source_related_row_id IS NOT NULL AND source_related_row_id > 0", sql)
        self.assertIn("WHERE source_system IS NOT NULL", sql)
