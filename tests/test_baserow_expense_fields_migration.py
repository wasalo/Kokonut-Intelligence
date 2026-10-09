"""Contract tests for the expense-only source-field migration."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "postgres"
MIGRATION = SCHEMA_DIR / "370_baserow_expense_fields.sql"


class ExpenseFieldsMigrationTests(unittest.TestCase):
    def test_migration_adds_only_nullable_expense_fields_and_nonnegative_count_check(self) -> None:
        self.assertTrue(MIGRATION.exists(), "expense-only migration 370 is missing")
        sql = MIGRATION.read_text(encoding="utf-8")
        normalized = re.sub(r"\s+", " ", sql).casefold()

        self.assertEqual(MIGRATION.stem.split("_", 1)[0], "370")
        sql_migrations = [
            path for path in SCHEMA_DIR.glob("*.sql")
            if path.stem.split("_", 1)[0].isdigit()
        ]
        versions = [path.stem.split("_", 1)[0] for path in sql_migrations]
        self.assertEqual(len(versions), len(set(versions)))
        self.assertTrue(sql.lstrip().startswith("--"))
        self.assertIn("begin;", normalized)
        self.assertTrue(normalized.rstrip().endswith("commit;"))
        self.assertRegex(normalized, r"alter table(?: if exists)? expense_event")
        self.assertIn("add column if not exists payment_status varchar(50)", normalized)
        self.assertIn("add column if not exists people_impacted_count integer", normalized)
        self.assertIn("people_impacted_count is null or people_impacted_count >= 0", normalized)
        self.assertNotRegex(normalized, r"alter table (?!expense_event\b)")
        self.assertNotIn("alter column status", normalized)
        self.assertNotIn("create table", normalized)
        self.assertNotIn("insert into", normalized)
        self.assertNotIn("farm_crop", normalized)

        for line in sql.splitlines():
            lowered = line.casefold()
            if "add column if not exists payment_status" in lowered or "add column if not exists people_impacted_count" in lowered:
                self.assertNotIn("default", lowered)


if __name__ == "__main__":
    unittest.main()
