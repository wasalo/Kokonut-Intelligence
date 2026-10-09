from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text()
REPORT = (ROOT / "docs/phase1-baserow-legacy-data-reconciliation.md").read_text()
TECH_SCHEMA = (ROOT / "schemas/postgres/212_technology_roadmap.sql").read_text()


def crosswalk_row(section: str, field: str) -> list[str]:
    block = CROSSWALK.split(f"### {section}", 1)[1].split("\n### ", 1)[0]
    for line in block.splitlines():
        if line.startswith("|") and f"`{field}`" in line:
            return [cell.strip() for cell in line.strip("|").split("|")]
    raise AssertionError(f"Missing crosswalk row: {section}.{field}")


class TechnologyMappingTests(unittest.TestCase):
    def test_contract_and_url_are_owner_excluded_with_named_provenance_candidates(self):
        contract = crosswalk_row("Digital Legos Tracker (table ID `594502`; 8 fields)", "Contract")
        url = crosswalk_row("Digital Legos Tracker (table ID `594502`; 8 fields)", "URL")
        self.assertEqual(contract[2], "`technology_alternative.metadata.baserow_legacy.contract_source_value`")
        self.assertEqual(contract[3], "`EXCLUDE_OWNER`")
        self.assertIn("Owner scope decision", contract[4])
        self.assertIn("chain", contract[4].casefold())
        self.assertEqual(url[2], "`technology_alternative.metadata.baserow_legacy.source_url`")
        self.assertEqual(url[3], "`EXCLUDE_OWNER`")
        self.assertIn("Owner scope decision", url[4])
        self.assertIn("driver", url[4].casefold())
        self.assertIn("metadata JSONB NOT NULL", TECH_SCHEMA)

    def test_status_and_area_identity_are_held_without_semantic_or_parent_match(self):
        status = crosswalk_row("Digital Legos Tracker (table ID `594502`; 8 fields)", "Status")
        area = crosswalk_row("Ecosystem Infra Stack (table ID `594514`; 5 fields)", "Name")
        self.assertEqual(status[3], "`EXCLUDE_OWNER`")
        self.assertIn("Owner scope decision", status[4])
        self.assertIn("zero exact", status[4].casefold())
        self.assertEqual(area[3], "`EXCLUDE_OWNER`")
        self.assertIn("Owner scope decision", area[4])
        self.assertIn("roadmap_id", area[4])
        self.assertIn("exact", area[4].casefold())
        self.assertIn("roadmap_id UUID NOT NULL", TECH_SCHEMA)
        self.assertIn("no exact source-name matches", REPORT.casefold())

    def test_reciprocal_source_edges_have_no_safe_direct_target_join(self):
        forward = crosswalk_row("Digital Legos Tracker (table ID `594502`; 8 fields)", "Ecosystem Infra Stack")
        reverse = crosswalk_row("Ecosystem Infra Stack (table ID `594514`; 5 fields)", "Digital Legos Tracker")
        self.assertEqual(forward[3], "`EXCLUDE_OWNER`")
        self.assertIn("Owner scope decision", forward[4])
        self.assertEqual(reverse[3], "`EXCLUDE_OWNER`")
        self.assertIn("Owner scope decision", reverse[4])
        self.assertIn("area→driver→alternative", forward[4])
        self.assertIn("area→driver→alternative", reverse[4])
        self.assertIn("two source link edges are exactly reciprocal", REPORT.casefold())


if __name__ == "__main__":
    unittest.main()
