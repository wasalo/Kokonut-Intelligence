from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "postgres"
MIGRATION = ROOT / "docs" / "schema-drafts" / "368_baserow_expense_and_farm_crop_schema_draft.sql"
SQL = MIGRATION.read_text(encoding="utf-8")
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text(encoding="utf-8")
PROJECTION = json.loads((ROOT / "docs/phase1-baserow-projection-allowlist.json").read_text(encoding="utf-8"))


def field_row(field_id: str) -> list[str]:
    for line in CROSSWALK.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and f"(`{field_id}`)" in cells[0]:
            return cells
    raise AssertionError(f"Missing crosswalk field ID {field_id}")


def section_rows(section: str) -> list[list[str]]:
    block = CROSSWALK.split(f"### {section}", 1)[1].split("\n### ", 1)[0]
    return [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in block.splitlines()
        if line.startswith("|") and line.strip().startswith("| `")
    ]


class ExpenseFarmCropDraftTests(unittest.TestCase):
    def test_migration_is_new_transactional_and_ordered(self):
        sql_files = [path for path in SCHEMA_DIR.glob("*.sql") if path.stem.split("_", 1)[0].isdigit()]
        versions = [path.stem.split("_", 1)[0] for path in sql_files]
        self.assertTrue(MIGRATION.exists())
        self.assertNotIn(MIGRATION.name, {path.name for path in sql_files})
        self.assertEqual(MIGRATION.stem.split("_", 1)[0], "368")
        self.assertEqual(len(versions), len(set(versions)))
        self.assertTrue(SQL.lstrip().startswith("--"))
        self.assertIn("BEGIN;", SQL)
        self.assertTrue(SQL.rstrip().endswith("COMMIT;"))
        self.assertNotIn("INSERT INTO", SQL.upper())
        self.assertNotIn("COPY ", SQL.upper())

    def test_expense_payment_status_is_separate_and_unmapped_by_default(self):
        payment_line = next(line for line in SQL.splitlines() if "ADD COLUMN IF NOT EXISTS payment_status" in line)
        count_line = next(line for line in SQL.splitlines() if "ADD COLUMN IF NOT EXISTS people_impacted_count" in line)
        self.assertIn("VARCHAR(50)", payment_line)
        self.assertNotIn("DEFAULT", payment_line.upper())
        self.assertIn("INTEGER", count_line)
        self.assertNotIn("DEFAULT", count_line.upper())
        self.assertIn("people_impacted_count IS NULL OR people_impacted_count >= 0", SQL)
        self.assertIn("separate from workflow status", SQL)
        self.assertNotIn("ALTER COLUMN status", SQL)
        self.assertEqual(field_row("4244464")[2], "`expense_event.payment_status`")
        self.assertEqual(field_row("4244464")[3], "`CANDIDATE`")
        self.assertEqual(field_row("4261434")[2], "`expense_event.people_impacted_count`")
        self.assertEqual(field_row("4261434")[3], "`CANDIDATE`")

    def test_farm_crop_is_a_typed_many_to_many_with_optional_complete_provenance(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS public.farm_crop", SQL)
        self.assertIn("farm_id UUID NOT NULL REFERENCES public.farm(id) ON DELETE RESTRICT", SQL)
        self.assertIn("crop_id UUID NOT NULL REFERENCES public.crop(id) ON DELETE RESTRICT", SQL)
        self.assertIn("PRIMARY KEY (farm_id, crop_id)", SQL)
        self.assertIn("chk_farm_crop_source_provenance_complete", SQL)
        for source_column in (
            "source_database_id", "source_table_id", "source_field_id", "source_row_id",
            "source_related_table_id", "source_related_row_id",
        ):
            self.assertIn(f"{source_column} IS NOT NULL", SQL)
        self.assertIn("uq_farm_crop_source_edge", SQL)
        self.assertIn("idx_farm_crop_crop_id", SQL)
        for field_id in ("2308566", "2308567"):
            row = field_row(field_id)
            self.assertEqual(row[2], "—")
            self.assertEqual(row[3], "`EXCLUDE_OWNER`")
            self.assertIn("Batch 39 owner drops", row[4])
            self.assertIn("controlled archive", row[4])
            self.assertIn("do not emit `farm_crop` edges", row[4])
        source_table_ids = {str(item["source_table_id"]) for item in PROJECTION["target_tables"]}
        self.assertIn("317629", source_table_ids)
        self.assertIn("does not authorize Species-row projection/import", field_row("4034223")[4])

    def test_dropped_tables_and_staff_actor_edges_are_excluded_but_endpoints_remain(self):
        for section, count in (
            ("Development Phases (table ID `326753`; 5 fields)", 5),
            ("Framework Steps (table ID `331882`; 9 fields)", 9),
        ):
            rows = section_rows(section)
            self.assertEqual(len(rows), count)
            self.assertTrue(all(row[3] == "`EXCLUDE_OWNER`" for row in rows))
        for field_id in ("2202767", "2386683", "3136769", "3918767", "2437665", "2350403", "2350404"):
            self.assertEqual(field_row(field_id)[3], "`EXCLUDE_OWNER`")
        self.assertNotIn("326753", {str(item["source_table_id"]) for item in PROJECTION["target_tables"]})
        self.assertNotIn("331882", {str(item["source_table_id"]) for item in PROJECTION["target_tables"]})


if __name__ == "__main__":
    unittest.main()
