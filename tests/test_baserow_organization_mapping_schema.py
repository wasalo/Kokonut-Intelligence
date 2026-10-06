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

    def test_funding_relationship_remains_held_until_funding_target_is_resolved(self):
        crosswalk = CROSSWALK.read_text(encoding="utf-8")
        self.assertIn("`Organization` (`4446734`) | `link_row` → `Organizations` | — | `HOLD_RELATIONSHIP`", crosswalk)
        self.assertIn("`Funding` (`4446757`) | `link_row` → `Funding` | — | `HOLD_RELATIONSHIP`", crosswalk)
        self.assertIn("16 exact reciprocal edges", crosswalk)
        self.assertIn("Funding target is unresolved", crosswalk)


if __name__ == "__main__":
    unittest.main()
