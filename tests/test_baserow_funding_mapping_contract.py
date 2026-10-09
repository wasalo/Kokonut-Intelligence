"""Contract tests for owner-excluded Baserow Funding data and finance schema."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = ROOT / "docs" / "phase1-baserow-field-crosswalk.md"
FINANCE_SCHEMA = ROOT / "schemas" / "postgres" / "004_finance.sql"
TRANCHE_SCHEMA = ROOT / "schemas" / "postgres" / "367_external_grant_tranche.sql"
REPORT = ROOT / "docs" / "phase1-baserow-legacy-data-reconciliation.md"
ALLOWLIST = ROOT / "docs" / "phase1-baserow-projection-allowlist.json"
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
        cls.tranche_schema = TRANCHE_SCHEMA.read_text(encoding="utf-8")
        cls.report = REPORT.read_text(encoding="utf-8")

    def row(self, field_id):
        marker = f"(`{field_id}`)"
        line = next(line for line in self.section.splitlines() if marker in line)
        return [cell.strip() for cell in line.split("|")[1:-1]]

    def test_every_funding_field_is_excluded_but_the_source_archive_is_preserved(self):
        field_ids = (
            "4446732", "4446733", "4446734", "4446791", "4446799", "4446800",
            "4447192", "4447364", "4447367", "4457708", "4638640", "4638641", "4646240",
        )
        for field_id in field_ids:
            with self.subTest(field_id=field_id):
                row = self.row(field_id)
                self.assertEqual(row[2], "—")
                self.assertEqual(row[3], "`EXCLUDE_OWNER`")
        self.assertIn("owner excludes every Funding field and edge", self.section)
        self.assertIn("original reciprocal links in the controlled archive", self.section)
        self.assertIn("No Funding projection or manual KI entry is authorized now", self.section)
        self.assertEqual(sum(line.startswith("| `") for line in self.section.splitlines()), 13)

    def test_typed_tranche_schema_and_historical_semantics_remain_nonoperative(self):
        for token in (
            "CREATE TABLE IF NOT EXISTS external_grant_tranche",
            "location_id UUID NOT NULL REFERENCES location(id)",
            "program_name TEXT NOT NULL",
            "program_date DATE NOT NULL",
            "CREATE TABLE IF NOT EXISTS external_grant_tranche_funder",
        ):
            self.assertIn(token, self.tranche_schema)
        for token in (
            "external_grant_tranche(program_name, program_date, location_id)",
            "external_grant_tranche_funder",
            "grant-round/program date, not a cash-receipt date",
            "Do not map the program date to `financial_transaction.transaction_date`",
            "Nine rows have both amount fields",
            "exact accounting treatment",
            "Batch 34",
        ):
            self.assertIn(token.casefold(), self.report.casefold())
        finance = self.schema
        for column in (
            "location_id UUID NOT NULL REFERENCES location(id)",
            "transaction_date DATE NOT NULL",
            "transaction_type VARCHAR(50) NOT NULL",
            "amount NUMERIC(15,2) NOT NULL",
        ):
            self.assertIn(column, finance)

    def test_funding_organization_edges_are_excluded_without_excluding_organizations(self):
        funding_link = self.row("4446734")
        self.assertEqual(funding_link[3], "`EXCLUDE_OWNER`")
        self.assertIn("16 exact reciprocal source edges", funding_link[4])
        self.assertIn("controlled archive", funding_link[4])
        self.assertIn("canonical identity resolution remains a gate", funding_link[4])

        organizations_header = "### Organizations (table ID `554714`; 5 fields)"
        start = self.crosswalk.index(organizations_header)
        end = self.crosswalk.find("\n### ", start + len(organizations_header))
        organizations = self.crosswalk[start:] if end < 0 else self.crosswalk[start:end]
        for name in ("Name", "Notes", "Active"):
            row = next(line for line in organizations.splitlines() if f"`{name}`" in line)
            self.assertIn("`CANDIDATE`", row)
        self.assertIn("16 exact reciprocal source edges", organizations)
        self.assertIn("canonical identity resolution remains a gate", organizations)
        allowlist = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
        source_tables = {str(entry["source_table_id"]) for entry in allowlist["target_tables"]}
        self.assertNotIn("554709", source_tables)

    def test_external_tranche_remains_separate_from_funding_milestones(self):
        self.assertIn("not an external grant milestone", self.report.casefold())
        milestone_link = self.crosswalk.split("### Funding Milestones", 1)[1].split("\n### ", 1)[0]
        source_link = next(line for line in milestone_link.splitlines() if "`Source of Funding`" in line)
        self.assertIn("`EXCLUDE_OWNER`", source_link)
        self.assertIn("Funding Milestones records and their other fields remain independently scoped", source_link)


if __name__ == "__main__":
    unittest.main()
