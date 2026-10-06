from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text()
REPORT = (ROOT / "docs/phase1-baserow-legacy-data-reconciliation.md").read_text()
SOLUTION_FUNDING = (ROOT / "schemas/postgres/290_solution_funding.sql").read_text()
IMPACT_SCHEMA = (ROOT / "schemas/postgres/031_impact_claims_and_cids.sql").read_text()


def crosswalk_row(section: str, field: str) -> list[str]:
    block = CROSSWALK.split(f"### {section}", 1)[1].split("\n### ", 1)[0]
    for line in block.splitlines():
        if line.startswith("|") and f"`{field}`" in line:
            return [cell.strip() for cell in line.strip("|").split("|")]
    raise AssertionError(f"Missing crosswalk row: {section}.{field}")


class FundingMilestonesMappingTests(unittest.TestCase):
    def test_funding_milestone_fields_stay_held_without_external_milestone_target(self):
        section = "Funding Milestones (table ID `554723`; 8 fields)"
        for field in ("Title", "Priority", "Start Date", "End Date", "Description"):
            row = crosswalk_row(section, field)
            self.assertEqual(row[2], "—")
            self.assertEqual(row[3], "`HOLD_FIELD`")
            self.assertIn("zero populated", row[4].casefold())
            self.assertIn("external grant milestone", row[4].casefold())
        source_link = crosswalk_row(section, "Source of Funding")
        updates = crosswalk_row(section, "Milestones Updates")
        for row in (source_link, updates):
            self.assertEqual(row[3], "`HOLD_RELATIONSHIP`")
            self.assertIn("zero edges on both sides", row[4].casefold())
        tranche = SOLUTION_FUNDING.split("CREATE TABLE IF NOT EXISTS solution_funding_tranche", 1)[1].split(");", 1)[0]
        self.assertIn("funding_case_id UUID NOT NULL", tranche)
        self.assertIn("amount NUMERIC(15,2) NOT NULL", tranche)
        self.assertIn("not an external grant milestone", REPORT.casefold())

    def test_milestone_outcome_fields_and_links_remain_quarantined(self):
        section = "Milestones Outcomes (table ID `554745`; 7 fields)"
        for field in ("Title", "Description", "Output Proof"):
            row = crosswalk_row(section, field)
            self.assertEqual(row[2], "—")
            self.assertEqual(row[3], "`HOLD_FIELD`")
            self.assertIn("zero populated", row[4].casefold())
        proof_file = crosswalk_row(section, "Output File")
        self.assertEqual(proof_file[3], "`MANUAL_CURATION`")
        self.assertIn("zero", proof_file[4].casefold())
        for field in ("Funding Milestones", "Objectives"):
            row = crosswalk_row(section, field)
            self.assertEqual(row[3], "`HOLD_RELATIONSHIP`")
            self.assertIn("zero edges on both sides", row[4].casefold())
        stakeholder = IMPACT_SCHEMA.split("CREATE TABLE IF NOT EXISTS stakeholder_outcome", 1)[1].split(");", 1)[0]
        self.assertIn("location_id UUID NOT NULL", stakeholder)
        self.assertIn("stakeholder_group VARCHAR(100) NOT NULL", stakeholder)
        self.assertIn("not a stakeholder outcome", REPORT.casefold())


if __name__ == "__main__":
    unittest.main()
