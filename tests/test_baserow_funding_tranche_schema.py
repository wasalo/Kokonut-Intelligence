"""Contract tests for the owner-approved external grant tranche model."""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas" / "postgres" / "367_external_grant_tranche.sql"
ALLOWLIST = ROOT / "docs" / "phase1-baserow-projection-allowlist.json"


class ExternalGrantTrancheSchemaTests(unittest.TestCase):
    def migration_sql(self):
        self.assertTrue(MIGRATION.exists(), "migration 367 must define the approved tranche model")
        return MIGRATION.read_text(encoding="utf-8")

    def normalized_sql(self):
        return re.sub(r"\s+", " ", self.migration_sql())

    def test_tranche_requires_program_scope_and_explicit_location(self):
        sql = self.normalized_sql()
        self.assertIn("CREATE TABLE IF NOT EXISTS external_grant_tranche", sql)
        self.assertIn("location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT", sql)
        self.assertIn("program_name TEXT NOT NULL", sql)
        self.assertIn("program_date DATE NOT NULL", sql)
        self.assertIn("CONSTRAINT uq_external_grant_tranche_source_identity UNIQUE ( source_system, source_database_id, source_table_id, source_row_id )", sql)

    def test_funder_association_preserves_many_to_many_source_edges(self):
        sql = self.normalized_sql()
        self.assertIn("CREATE TABLE IF NOT EXISTS external_grant_tranche_funder", sql)
        self.assertIn("tranche_id UUID NOT NULL REFERENCES external_grant_tranche(id) ON DELETE CASCADE", sql)
        self.assertIn("CONSTRAINT fk_external_grant_tranche_funder_source_row FOREIGN KEY (source_system, source_database_id, source_table_id, source_row_id) REFERENCES external_grant_tranche (source_system, source_database_id, source_table_id, source_row_id) ON DELETE CASCADE", sql)
        self.assertIn("organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE RESTRICT", sql)
        self.assertIn("PRIMARY KEY (tranche_id, organization_id)", sql)
        for column in (
            "source_system TEXT NOT NULL",
            "source_database_id BIGINT NOT NULL",
            "source_table_id BIGINT NOT NULL",
            "source_field_id BIGINT NOT NULL",
            "source_row_id BIGINT NOT NULL",
            "source_related_table_id BIGINT NOT NULL",
            "source_related_row_id BIGINT NOT NULL",
        ):
            self.assertIn(column, sql)

    def test_migration_does_not_turn_unresolved_amounts_into_transactions(self):
        sql = self.normalized_sql()
        self.assertNotIn("CREATE TABLE IF NOT EXISTS financial_transaction", sql)
        self.assertNotIn("grant_amount", sql.casefold())
        self.assertNotIn("crowdfunding_amount", sql.casefold())
        self.assertNotIn("transaction_date", sql.casefold())

    def test_schema_approval_does_not_authorize_source_projection(self):
        allowlist = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
        targets = {item["target_table"] for item in allowlist["target_tables"]}
        self.assertNotIn("external_grant_tranche", targets)
        self.assertNotIn("external_grant_tranche_funder", targets)


if __name__ == "__main__":
    unittest.main()
