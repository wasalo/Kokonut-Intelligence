from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text()
REPORT = (ROOT / "docs/phase1-baserow-legacy-data-reconciliation.md").read_text()
GUILD_SCHEMA = (ROOT / "schemas/postgres/025_kokonut_framework_alignment.sql").read_text()
GUILD_DOMAIN_SCHEMA = (ROOT / "schemas/postgres/318_guild_protocol_projection.sql").read_text()


def crosswalk_row(section: str, field: str) -> list[str]:
    block = CROSSWALK.split(f"### {section}", 1)[1].split("\n### ", 1)[0]
    for line in block.splitlines():
        if line.startswith("|") and f"`{field}`" in line:
            return [cell.strip() for cell in line.strip("|").split("|")]
    raise AssertionError(f"Missing crosswalk row: {section}.{field}")


class EcosystemMappingTests(unittest.TestCase):
    def test_ecosystem_branch_identity_and_status_remain_held(self):
        section = "Ecosystem Branches (table ID `594558`; 4 fields)"
        name = crosswalk_row(section, "Name")
        active = crosswalk_row(section, "Active")
        guild_table = GUILD_SCHEMA.split("CREATE TABLE IF NOT EXISTS kokonut_guild", 1)[1].split(");", 1)[0]
        self.assertEqual(name[2], "`kokonut_guild.name`")
        self.assertEqual(name[3], "`HOLD_FIELD`")
        self.assertIn("guild_key", name[4])
        self.assertEqual(active[2], "`kokonut_guild.status`")
        self.assertEqual(active[3], "`HOLD_FIELD`")
        self.assertIn("false", active[4].casefold())
        self.assertIn("status VARCHAR(50) DEFAULT 'active'", guild_table)
        self.assertNotIn("staff_id", guild_table)
        self.assertIn("branch is not approved as a guild", REPORT.casefold())

    def test_owner_link_and_inverse_remain_quarantined(self):
        section = "Ecosystem Branches (table ID `594558`; 4 fields)"
        owner = crosswalk_row(section, "Owner")
        self.assertEqual(owner[3], "`HOLD_RELATIONSHIP`")
        self.assertIn("metadata.baserow_legacy", owner[2])
        self.assertIn("zero edges on both sides", owner[4].casefold())
        self.assertIn("no staff foreign key", owner[4].casefold())

    def test_empty_kokonut_dependencies_do_not_map_to_domain_specific_edges(self):
        section = "Kokonut Dependencies (table ID `594507`; 3 fields)"
        for field in ("Name", "Notes", "URL"):
            row = crosswalk_row(section, field)
            self.assertEqual(row[2], "—")
            self.assertEqual(row[3], "`HOLD_FIELD`")
            self.assertIn("zero populated", row[4].casefold())
            self.assertIn("generic dependency", row[4].casefold())
        self.assertNotIn("Kokonut Dependencies", GUILD_DOMAIN_SCHEMA)
        self.assertIn("no generic dependency target", REPORT.casefold())


if __name__ == "__main__":
    unittest.main()
