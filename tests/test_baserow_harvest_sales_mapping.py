from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text()
REPORT = (ROOT / "docs/phase1-baserow-legacy-data-reconciliation.md").read_text()
PROJECTION = json.loads((ROOT / "docs/phase1-baserow-projection-allowlist.json").read_text())
CROP_SCHEMA = (ROOT / "schemas/postgres/002_crops.sql").read_text()
OPERATIONS_SCHEMA = (ROOT / "schemas/postgres/003_operations.sql").read_text()


def crosswalk_row(section: str, field: str) -> list[str]:
    block = CROSSWALK.split(f"### {section}", 1)[1].split("\n### ", 1)[0]
    for line in block.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells[0].startswith(f"`{field}` (`"):
                return cells
    raise AssertionError(f"Missing crosswalk row: {section}.{field}")


class HarvestSalesMappingTests(unittest.TestCase):
    def test_multi_plot_source_edges_are_held_against_scalar_cycle_plot(self):
        source = crosswalk_row("Harvest & Sales (table ID `317638`; 28 fields)", "Lots of Land")
        inverse = crosswalk_row("Land Lots (table ID `410138`; 10 fields)", "Harvest Forecast")
        self.assertEqual(source[2], "—")
        self.assertEqual(source[3], "`HOLD_RELATIONSHIP`")
        self.assertIn("thirteen exact reciprocal edges", source[4].casefold())
        self.assertIn("3 have no plot", source[4].casefold())
        self.assertIn("4 have one", source[4].casefold())
        self.assertIn("1 has four", source[4].casefold())
        self.assertIn("1 has five", source[4].casefold())
        self.assertEqual(inverse[3], "`HOLD_RELATIONSHIP`")
        self.assertIn("13 reciprocal edges", inverse[4].casefold())
        self.assertIn("plot_id UUID NOT NULL", CROP_SCHEMA)

    def test_crop_relation_is_scalar_and_reciprocal_without_duplicate_insertion(self):
        source = crosswalk_row("Harvest & Sales (table ID `317638`; 28 fields)", "Crops")
        inverse = crosswalk_row("Species (table ID `317629`; 21 fields)", "Harvest Forecast")
        self.assertEqual(source[2], "`crop_cycle.crop_id`")
        self.assertEqual(source[3], "`RELATIONSHIP`")
        self.assertIn("nine exact reciprocal edges", source[4].casefold())
        self.assertEqual(inverse[2], "`crop_cycle.crop_id`")
        self.assertEqual(inverse[3], "`RELATIONSHIP`")
        self.assertIn("do not insert", inverse[4].casefold())
        self.assertIn("crop_id UUID NOT NULL", CROP_SCHEMA)

    def test_farm_edge_and_source_uuid_have_named_provenance_destinations(self):
        farm = crosswalk_row("Harvest & Sales (table ID `317638`; 28 fields)", "Kokonut Farms")
        farm_inverse = crosswalk_row("Kokonut Farms (table ID `305805`; 54 fields)", "Harvest & Sales Forecast")
        source_uuid = crosswalk_row("Harvest & Sales (table ID `317638`; 28 fields)", "UUID")
        farm_path = "crop_cycle.metadata.baserow_legacy.farm_source_keys"
        self.assertEqual(farm[2], f"`{farm_path}`")
        self.assertEqual(farm[3], "`PROVENANCE_ONLY`")
        self.assertIn("three exact reciprocal farm edges", farm[4].casefold())
        self.assertIn("location_id", farm[4])
        self.assertEqual(farm_inverse[2], f"`{farm_path}`")
        self.assertEqual(farm_inverse[3], "`PROVENANCE_ONLY`")
        self.assertIn("do not write a second relationship", farm_inverse[4].casefold())
        self.assertEqual(source_uuid[2], "`crop_cycle.metadata.baserow_legacy.source_uuid`")
        self.assertEqual(source_uuid[3], "`PROVENANCE_ONLY`")
        self.assertNotIn("farm_id UUID", CROP_SCHEMA)
        self.assertIn("metadata JSONB", CROP_SCHEMA)

    def test_forecast_price_requires_unit_and_single_plot_and_never_becomes_a_sale(self):
        price = crosswalk_row("Harvest & Sales (table ID `317638`; 28 fields)", "Avg Sale Price")
        unit = crosswalk_row("Harvest & Sales (table ID `317638`; 28 fields)", "Production Metric")
        self.assertEqual(price[3], "`CONDITIONAL`")
        self.assertIn("expected_price_per_unit", price[2])
        self.assertIn("expected_price_currency", price[2])
        self.assertIn("DOP", price[4])
        self.assertIn("nine values", price[4].casefold())
        self.assertIn("three rows", price[4].casefold())
        self.assertIn("no plot", price[4].casefold())
        self.assertIn("zero rows", price[4].casefold())
        self.assertEqual(unit[3], "`CONDITIONAL`")
        self.assertIn("actual_yield_unit", unit[2])
        self.assertIn("crop_cycle.metadata.baserow_legacy.expected_price_unit", unit[2])
        self.assertNotIn("expected_yield_unit", unit[2])
        self.assertIn("none of the two actual-production quantities has a unit", unit[4].casefold())
        self.assertIn("expected_price_per_unit NUMERIC(12,4)", CROP_SCHEMA)
        self.assertIn("CREATE TABLE IF NOT EXISTS sales_event", OPERATIONS_SCHEMA)
        self.assertIn("sale_date DATE NOT NULL", OPERATIONS_SCHEMA)
        self.assertIn("do not create a `sales_event`", price[4].casefold())

    def test_actual_yield_and_harvest_events_remain_distinct(self):
        quantity = crosswalk_row("Harvest & Sales (table ID `317638`; 28 fields)", "Actual Production Quantity")
        forecast_date = crosswalk_row("Harvest & Sales (table ID `317638`; 28 fields)", "Harvest Forecast Date")
        realized_sales = crosswalk_row("Harvest & Sales (table ID `317638`; 28 fields)", "Realized Total Sales")
        self.assertEqual(quantity[3], "`CONDITIONAL`")
        self.assertIn("two rows contain a value", quantity[4].casefold())
        self.assertIn("neither has a `production metric` unit", quantity[4].casefold())
        self.assertIn("do not create a `harvest_event`", quantity[4])
        self.assertEqual(forecast_date[2], "`crop_cycle.expected_harvest_date`")
        self.assertIn("two forecast dates co-occur with planting date", forecast_date[4].casefold())
        self.assertIn("never treat as an actual harvest date", forecast_date[4].casefold())
        self.assertEqual(realized_sales[3], "`EXCLUDE_DERIVED`")
        self.assertIn("harvest_date DATE NOT NULL", OPERATIONS_SCHEMA)

    def test_untyped_planting_values_and_status_have_named_held_paths(self):
        quantity_planted = crosswalk_row("Harvest & Sales (table ID `317638`; 28 fields)", "Quantity Planted")
        live_quantity = crosswalk_row("Harvest & Sales (table ID `317638`; 28 fields)", "Live quantity")
        planted_plot_count = crosswalk_row("Harvest & Sales (table ID `317638`; 28 fields)", "Planted Plot of Lands")
        status = crosswalk_row("Harvest & Sales (table ID `317638`; 28 fields)", "Status")
        for row in (quantity_planted, live_quantity, planted_plot_count, status):
            self.assertEqual(row[3], "`HOLD_FIELD`")
            self.assertIn("crop_cycle.metadata.baserow_legacy.", row[2])
            self.assertIn("do not project", row[4].casefold())
        self.assertIn("six rows", quantity_planted[4].casefold())
        self.assertIn("none has a paired `Planting Metric`", quantity_planted[4])
        self.assertIn("eight values", status[4].casefold())
        self.assertIn("zero exactly match", status[4].casefold())
        self.assertIn("inherit the target default", status[4].casefold())

    def test_cycle_rows_remain_outside_allowlist_and_snapshot_mapping_stays_blocked(self):
        ids = {entry["source_table_id"] for entry in PROJECTION["target_tables"]}
        self.assertNotIn("317638", ids)
        self.assertIn("Harvest & Sales", REPORT)
        self.assertIn("no `crop_cycle` rows were projected or imported", REPORT.casefold())
        self.assertIn("import_blocked=true", REPORT)


if __name__ == "__main__":
    unittest.main()
