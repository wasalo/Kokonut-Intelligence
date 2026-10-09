"""Contract tests for the Baserow Organizations crosswalk."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = ROOT / "docs" / "phase1-baserow-field-crosswalk.md"
ORG_SCHEMA = ROOT / "schemas" / "postgres" / "064_organization.sql"


class OrganizationMappingSchemaTests(unittest.TestCase):
    def test_active_boolean_maps_only_to_supported_status_values(self):
        crosswalk = CROSSWALK.read_text(encoding="utf-8")
        organization_schema = ORG_SCHEMA.read_text(encoding="utf-8")
        active_row = next(line for line in crosswalk.splitlines() if "`Active` (`4446752`)" in line)
        self.assertIn("`organization.status` | `CANDIDATE`", active_row)
        self.assertIn("true -> `active`; false -> `inactive`", active_row)
        self.assertIn("null or unrecognized values stay held", active_row)
        self.assertIn("never infer `dissolved`", active_row)
        self.assertIn("status IN ('active', 'inactive', 'dissolved')", organization_schema)

    def test_required_organization_type_default_is_not_used(self):
        crosswalk = CROSSWALK.read_text(encoding="utf-8").casefold()
        organization_schema = ORG_SCHEMA.read_text(encoding="utf-8")
        self.assertIn("org_type VARCHAR(100) NOT NULL DEFAULT 'cooperative'", organization_schema)
        self.assertIn("do not use the schema default `cooperative`", crosswalk)
        self.assertIn("owner approves `other` for all 8 source rows without a source-backed type", crosswalk)
        self.assertIn("derive required `org_key` from the composite source identity", crosswalk)

    def test_funding_edges_are_excluded_but_organization_records_remain_independent(self):
        crosswalk = CROSSWALK.read_text(encoding="utf-8")
        self.assertIn("`Organization` (`4446734`) | `link_row` → `Organizations` | — | `EXCLUDE_OWNER`", crosswalk)
        self.assertIn("`Funding` (`4446757`) | `link_row` → `Funding` | — | `EXCLUDE_OWNER`", crosswalk)
        self.assertIn("16 exact reciprocal source edges", crosswalk)
        self.assertIn("original reciprocal links in the controlled archive", crosswalk)
        self.assertIn("do not emit them to KI", crosswalk)
        self.assertIn("canonical identity resolution remains a gate", crosswalk)
        for field in ("Name", "Notes", "Active"):
            self.assertIn(f"`{field}`", crosswalk)
        self.assertIn("`organization.name` | `CANDIDATE`", crosswalk)
        self.assertIn("`organization.description` | `CANDIDATE`", crosswalk)
        self.assertIn("`organization.status` | `CANDIDATE`", crosswalk)
        self.assertIn("Owner approves `organization.org_type = 'other'`", crosswalk)
        self.assertIn("this mapping applies to its 8 rows unless separate source evidence is reviewed", crosswalk)


if __name__ == "__main__":
    unittest.main()
