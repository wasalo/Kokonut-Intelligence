from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text()
REPORT = (ROOT / "docs/phase1-baserow-legacy-data-reconciliation.md").read_text()
EBF_SCHEMA = (ROOT / "schemas/postgres/032_ebf_scorecard.sql").read_text()
EBF_SEED = (ROOT / "schemas/seeds/032_ebf_rubric.sql").read_text()
GROUND_SCHEMA = (ROOT / "schemas/postgres/026_ground_analytics.sql").read_text()


def section_for(table_name: str) -> str:
    marker = f"### {table_name} (table ID `"
    start = CROSSWALK.index(marker)
    end = CROSSWALK.find("\n### ", start + len(marker))
    return CROSSWALK[start:] if end < 0 else CROSSWALK[start:end]


def row_for(table_name: str, field_name: str) -> list[str]:
    section = section_for(table_name)
    prefix = f"| `{field_name}` (`"
    line = next(line for line in section.splitlines() if line.startswith(prefix))
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


class EbfAndGroundAnalyticsMappingTests(unittest.TestCase):
    def test_ebf_boolean_maps_to_inactive_without_creating_pillars(self):
        row = row_for("EBF", "Active")
        self.assertEqual(row[2], "`ebf_pillar.status`")
        self.assertEqual(row[3], "`CANDIDATE`")
        self.assertIn("false", row[4].lower())
        self.assertIn("inactive", row[4].lower())
        self.assertIn("no target rows", row[4].lower())

    def test_ebf_required_identity_and_order_block_both_source_rows(self):
        name = row_for("EBF", "Name")
        self.assertIn("zero of two", name[4].lower())
        self.assertIn("pillar_key VARCHAR(50) NOT NULL UNIQUE", EBF_SCHEMA)
        self.assertIn("pillar_name VARCHAR(100) NOT NULL", EBF_SCHEMA)
        self.assertIn("sort_order INTEGER NOT NULL", EBF_SCHEMA)
        self.assertIn("INSERT INTO ebf_pillar", EBF_SEED)
        self.assertIn("neither source table has a source name", REPORT.lower())

    def test_ground_analytics_fields_remain_held_without_an_event_mapping(self):
        for field in ("Name", "Notes", "Active"):
            row = row_for("Ground Analytics", field)
            self.assertEqual(row[2], "—")
            self.assertEqual(row[3], "`HOLD_FIELD`")
        self.assertNotIn("CREATE TABLE IF NOT EXISTS ground_analytics (", GROUND_SCHEMA)
        self.assertIn("location_id UUID NOT NULL", GROUND_SCHEMA)
        self.assertIn("analysis_date DATE NOT NULL", GROUND_SCHEMA)
        self.assertIn("no direct `ground_analytics` target", REPORT.lower())


if __name__ == "__main__":
    unittest.main()
