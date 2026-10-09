"""Contract tests for the owner-provided Biofactory field crosswalk."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = ROOT / "docs" / "phase1-baserow-field-crosswalk.md"
BIO_SCHEMA = ROOT / "schemas" / "postgres" / "043_bio_factory_operations.sql"
TABLE_HEADER = "### Biofactory (table ID `417033`; 4 fields)"


class BiofactoryMappingSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = CROSSWALK.read_text(encoding="utf-8")
        start = text.index(TABLE_HEADER)
        end = text.find("\n### ", start + len(TABLE_HEADER))
        cls.section = text[start:] if end < 0 else text[start:end]
        cls.schema = BIO_SCHEMA.read_text(encoding="utf-8")

    def crosswalk_row(self, field_id):
        marker = f"(`{field_id}`)"
        line = next(line for line in self.section.splitlines() if marker in line)
        return [cell.strip() for cell in line.split("|")[1:-1]]

    def test_product_type_field_is_owner_excluded_without_an_option_mapping(self):
        row = self.crosswalk_row("3196795")
        self.assertEqual(row[2], "`bio_factory_batch.batch_type`")
        self.assertEqual(row[3], "`EXCLUDE_OWNER`")
        self.assertIn("Owner scope decision", row[4])
        self.assertIn("All 10 source options are used", row[4])
        self.assertIn("only 1 option normalizes", row[4])
        self.assertIn("used by 2 rows", row[4])
        self.assertIn("9 lack an approved map", row[4])
        self.assertIn("No option-level target mapping is established", row[4])
        self.assertIn("Farm Task `other` decision does not apply", row[4])

    def test_notes_are_owner_excluded_with_content_review_rationale(self):
        row = self.crosswalk_row("3196796")
        self.assertEqual(row[2], "`bio_factory_batch.batch_summary`")
        self.assertEqual(row[3], "`EXCLUDE_OWNER`")
        self.assertIn("Owner scope decision", row[4])
        self.assertIn("All 16 rows are populated", row[4])
        self.assertIn("12 distinct notes", row[4])
        self.assertIn("maximum length 53", row[4])
        self.assertIn("review content", row[4])

    def test_farm_edge_is_one_per_batch_and_resolved_by_source_identity(self):
        row = self.crosswalk_row("3196876")
        self.assertEqual(row[2], "`bio_factory_batch.farm_id`")
        self.assertEqual(row[3], "`RELATIONSHIP`")
        self.assertIn("16 forward edges: exactly one linked farm per batch", row[4])
        self.assertIn("across 2 source farms", row[4])
        self.assertIn("No reciprocal Biofactory link field exists", row[4])
        self.assertIn("composite source-key crosswalk", row[4])

    def test_required_batch_fields_without_source_values_remain_blocking(self):
        date_row = self.crosswalk_row("3196878")
        self.assertEqual(date_row[2], "`bio_factory_batch.production_start_date`")
        self.assertEqual(date_row[3], "`CONDITIONAL`")
        self.assertIn("Zero of 16 source rows have a Date value", date_row[4])
        self.assertIn("do not infer or fabricate dates", date_row[4])
        for column in (
            "batch_name VARCHAR(255) NOT NULL",
            "batch_type VARCHAR(100) NOT NULL",
            "production_method VARCHAR(100) NOT NULL",
            "production_start_date DATE NOT NULL",
            "batch_summary TEXT NOT NULL",
        ):
            self.assertIn(column, self.schema)
        self.assertIn("source has no batch-name or production-method field", self.crosswalk_row("3196795")[4])


if __name__ == "__main__":
    unittest.main()
