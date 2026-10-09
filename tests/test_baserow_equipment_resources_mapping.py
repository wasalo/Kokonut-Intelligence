from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text()
REPORT = (ROOT / "docs/phase1-baserow-legacy-data-reconciliation.md").read_text()
LOCATION_SCHEMA = (ROOT / "schemas/postgres/001_locations.sql").read_text()


def crosswalk_row(section: str, field: str) -> list[str]:
    block = CROSSWALK.split(f"### {section}", 1)[1].split("\n### ", 1)[0]
    for line in block.splitlines():
        if line.startswith("|") and f"`{field}`" in line:
            return [cell.strip() for cell in line.strip("|").split("|")]
    raise AssertionError(f"Missing crosswalk row: {section}.{field}")


class EquipmentAndResourcesInputTests(unittest.TestCase):
    def test_equipment_requires_location_identity_and_type_not_in_source(self):
        section = "Equipment (table ID `305807`; 12 fields)"
        for field, target in (
            ("Name", "`infrastructure_asset.name`"),
            ("Description", "`infrastructure_asset.description`"),
            ("Category", "`infrastructure_asset.asset_type`"),
        ):
            row = crosswalk_row(section, field)
            self.assertEqual(row[2], target)
            self.assertEqual(row[3], "`CONDITIONAL`")
            self.assertIn("zero populated", row[4].casefold())
            self.assertIn("location_id", row[4])
        asset = LOCATION_SCHEMA.split("CREATE TABLE IF NOT EXISTS infrastructure_asset", 1)[1].split(");", 1)[0]
        self.assertIn("location_id UUID NOT NULL", asset)
        self.assertIn("name VARCHAR(255) NOT NULL", asset)
        self.assertIn("asset_type VARCHAR(100) NOT NULL", asset)
        self.assertIn("capacity NUMERIC(12,4)", asset)

    def test_quantity_and_equipment_links_are_held_without_unit_or_edges(self):
        section = "Equipment (table ID `305807`; 12 fields)"
        quantity = crosswalk_row(section, "Quantity")
        self.assertEqual(quantity[2], "`infrastructure_asset.metadata.baserow_legacy.quantity`")
        self.assertEqual(quantity[3], "`HOLD_FIELD`")
        self.assertIn("unit", quantity[4].casefold())
        self.assertIn("capacity", quantity[4].casefold())
        for field in ("Farm Specific Task", "Resources Inputs"):
            row = crosswalk_row(section, field)
            self.assertEqual(row[3], "`HOLD_RELATIONSHIP`")
            self.assertIn("zero source edges", row[4].casefold())
        framework_steps = crosswalk_row(section, "Framework Steps")
        self.assertEqual(framework_steps[3], "`EXCLUDE_OWNER`")
        self.assertIn("Batch 37", framework_steps[4])
        self.assertIn("only the table-scoped uuid is populated", REPORT.casefold())

    def test_resources_inputs_has_no_generic_catalog_and_no_edges(self):
        section = "F005 -- Resources Inputs (table ID `555496`; 7 fields)"
        for field in ("Name", "Notes"):
            row = crosswalk_row(section, field)
            self.assertEqual(row[2], "—")
            self.assertEqual(row[3], "`HOLD_FIELD`")
            self.assertIn("no generic resource-input target", row[4].casefold())
        active = crosswalk_row(section, "Active")
        self.assertEqual(active[2], "—")
        self.assertEqual(active[3], "`EXCLUDE_OWNER`")
        self.assertIn("Owner scope decision", active[4])
        for field in ("Expenses", "Staff", "Equipment"):
            row = crosswalk_row(section, field)
            self.assertEqual(row[3], "`HOLD_RELATIONSHIP`")
            self.assertIn("zero edges on both sides", row[4].casefold())
        self.assertIn("no generic resource-input target", REPORT.casefold())


if __name__ == "__main__":
    unittest.main()
