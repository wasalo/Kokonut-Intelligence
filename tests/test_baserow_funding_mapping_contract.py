"""Contract tests for held Baserow funding mappings and finance-schema blockers."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = ROOT / "docs" / "phase1-baserow-field-crosswalk.md"
FINANCE_SCHEMA = ROOT / "schemas" / "postgres" / "004_finance.sql"
FUNDING_HEADER = "### Funding (table ID `554709`; 13 fields)"


class FundingMappingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = CROSSWALK.read_text(encoding="utf-8")
        start = text.index(FUNDING_HEADER)
        end = text.find("\n### ", start + len(FUNDING_HEADER))
        cls.crosswalk = text
        cls.section = text[start:] if end < 0 else text[start:end]
        cls.schema = FINANCE_SCHEMA.read_text(encoding="utf-8")

    def row(self, field_id):
        marker = f"(`{field_id}`)"
        line = next(line for line in self.section.splitlines() if marker in line)
        return [cell.strip() for cell in line.split("|")[1:-1]]

    def test_amount_overlap_is_explicit_and_amounts_are_not_combined(self):
        grant = self.row("4446800")
        crowdfunding = self.row("4638640")
        self.assertEqual(grant[3], "`HOLD_FIELD`")
        self.assertEqual(crowdfunding[3], "`HOLD_FIELD`")
        self.assertIn("Nine of these rows also contain `Crowdfunding Amount`", grant[4])
        self.assertIn("one contains Grant Amount only", grant[4])
        self.assertIn("2 rows have neither amount", grant[4])
        self.assertIn("do not sum, choose, duplicate, or project them", grant[4])
        self.assertIn("Owner directs keeping both amount fields held", crowdfunding[4])

    def test_tranche_model_keeps_program_date_separate_from_cash_date(self):
        date = self.row("4638641")
        self.assertEqual(date[2], "`external_grant_tranche.program_date`")
        self.assertEqual(date[3], "`CANDIDATE`")
        self.assertIn("represent a grant-round/program date, not a cash-receipt date", date[4])
        self.assertIn("never map to `financial_transaction.transaction_date`", date[4])
        self.assertIn("required per-tranche `location_id` has no source location/link", date[4])
        for column in (
            "location_id UUID NOT NULL REFERENCES location(id)",
            "transaction_date DATE NOT NULL",
            "transaction_type VARCHAR(50) NOT NULL",
            "amount NUMERIC(15,2) NOT NULL",
        ):
            self.assertIn(column, self.schema)

    def test_funder_edges_use_the_owner_approved_typed_association(self):
        row = self.row("4446734")
        self.assertEqual(row[2], "`external_grant_tranche_funder(tranche_id, organization_id)`")
        self.assertEqual(row[3], "`RELATIONSHIP`")
        self.assertIn("16 exact reciprocal edges", row[4])
        self.assertIn("up to 3 funders per tranche", row[4])
        self.assertIn("Owner confirms linked Organizations are the funder/source of money", row[4])
        self.assertIn("endpoints remain unprojected", row[4])

        organizations_header = "### Organizations (table ID `554714`; 5 fields)"
        start = self.crosswalk.index(organizations_header)
        end = self.crosswalk.find("\n### ", start + len(organizations_header))
        organizations = self.crosswalk[start:] if end < 0 else self.crosswalk[start:end]
        self.assertIn("`external_grant_tranche_funder(tranche_id, organization_id)`", organizations)
        self.assertIn("16 exact reciprocal edges", organizations)

    def test_external_tranche_keeps_funding_milestones_separate(self):
        program = self.row("4446732")
        self.assertEqual(program[2], "`external_grant_tranche.program_name`")
        self.assertEqual(program[3], "`CANDIDATE`")
        self.assertIn("received grant-round tranche", program[4])
        self.assertIn("keep each source row distinct", program[4])
        self.assertIn("no tranche row is eligible for projection or import", program[4])
        self.assertIn("Do not force-map by label; hold pending an external grant milestone target.", self.crosswalk)


if __name__ == "__main__":
    unittest.main()
