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
        self.assertIn("Do not sum or duplicate amounts", grant[4])
        self.assertIn("Currency and whether this is an additional component", crowdfunding[4])

    def test_receipt_model_keeps_required_location_and_date_blockers(self):
        date = self.row("4638641")
        self.assertEqual(date[3], "`HOLD_FIELD`")
        self.assertIn("meaning (receipt, award, or another grant-round date) is not confirmed", date[4])
        self.assertIn("required `location_id` has no source location/link", date[4])
        for column in (
            "location_id UUID NOT NULL REFERENCES location(id)",
            "transaction_date DATE NOT NULL",
            "transaction_type VARCHAR(50) NOT NULL",
            "amount NUMERIC(15,2) NOT NULL",
        ):
            self.assertIn(column, self.schema)

    def test_organization_edges_are_held_without_a_typed_finance_relation(self):
        row = self.row("4446734")
        self.assertEqual(row[3], "`HOLD_RELATIONSHIP`")
        self.assertIn("16 exact reciprocal edges", row[4])
        self.assertIn("up to 3 linked Organizations per Funding row", row[4])
        self.assertIn("Neither `capital_source` nor `financial_transaction` has a typed Organization FK/join", row[4])

    def test_program_and_receipt_are_not_forced_into_internal_funding_rounds(self):
        program = self.row("4446732")
        self.assertEqual(program[3], "`HOLD_FIELD`")
        self.assertIn("received grant-round tranche", program[4])
        self.assertIn("`capital_source` models a source; `financial_transaction` models a cash transaction", program[4])
        self.assertIn("do not duplicate records", program[4].lower())
        self.assertIn("do not force-map to `funding_round`", self.crosswalk)


if __name__ == "__main__":
    unittest.main()
