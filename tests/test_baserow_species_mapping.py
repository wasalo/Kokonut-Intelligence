from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text()
REPORT = (ROOT / "docs/phase1-baserow-legacy-data-reconciliation.md").read_text()
PROJECTION = json.loads((ROOT / "docs/phase1-baserow-projection-allowlist.json").read_text())
CROP_SCHEMA = (ROOT / "schemas/postgres/002_crops.sql").read_text()
FARM_CROP_SCHEMA = (ROOT / "docs/schema-drafts/368_baserow_expense_and_farm_crop_schema_draft.sql").read_text()
RELATIONSHIP_SCHEMA = (ROOT / "schemas/postgres/309_relationship_entities.sql").read_text()


SPECIES = "Species (table ID `317629`; 21 fields)"
FARMS = "Kokonut Farms (table ID `305805`; 54 fields)"
PLOTS = "Land Lots (table ID `410138`; 10 fields)"
HARVEST = "Harvest & Sales (table ID `317638`; 28 fields)"


def crosswalk_row(section: str, field: str, field_id: str) -> list[str]:
    block = CROSSWALK.split(f"### {section}", 1)[1].split("\n### ", 1)[0]
    for line in block.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells[0] == f"`{field}` (`{field_id}`)":
                return cells
    raise AssertionError(f"Missing crosswalk row: {section}.{field} ({field_id})")


class SpeciesMappingTests(unittest.TestCase):
    def test_crop_names_are_candidates_but_seed_name_collisions_are_not_merged(self):
        name = crosswalk_row(SPECIES, "Name", "2305620")
        scientific_name = crosswalk_row(SPECIES, "Scientific Name", "2305621")
        self.assertEqual(name[2], "`crop.name`")
        self.assertEqual(name[3], "`CANDIDATE`")
        self.assertIn("43 source names", name[4].casefold())
        self.assertIn("two", name[4].casefold())
        self.assertIn("static pilot crop seed", name[4].casefold())
        self.assertIn("do not merge", name[4].casefold())
        self.assertIn("seed insert omits `scientific_name`", name[4].casefold())
        self.assertEqual(scientific_name[2], "`crop.scientific_name`")
        self.assertEqual(scientific_name[3], "`CANDIDATE`")
        self.assertIn("20 values are populated", scientific_name[4].casefold())
        self.assertIn("unique", scientific_name[4].casefold())
        self.assertIn("name VARCHAR(255) NOT NULL", CROP_SCHEMA)
        self.assertIn("scientific_name VARCHAR(255)", CROP_SCHEMA)

    def test_maturity_weeks_convert_to_positive_integer_days(self):
        maturity = crosswalk_row(SPECIES, "Weeks to Maturity", "4034419")
        self.assertEqual(maturity[2], "`crop.growing_season_days`")
        self.assertEqual(maturity[3], "`CANDIDATE`")
        self.assertIn("weeks × 7", maturity[4])
        self.assertIn("three populated values", maturity[4].casefold())
        self.assertIn("positive integer days", maturity[4].casefold())
        self.assertIn("growing_season_days INTEGER", CROP_SCHEMA)

    def test_species_type_maps_all_source_options_without_import_authorization(self):
        source_type = crosswalk_row(SPECIES, "Type", "4034223")
        self.assertEqual(source_type[2], "`crop.crop_category`")
        self.assertEqual(source_type[3], "`CANDIDATE`")
        self.assertIn("3110859", source_type[4])
        self.assertIn("fruit", source_type[4].casefold())
        self.assertIn("3110860", source_type[4])
        self.assertIn("vegetable", source_type[4].casefold())
        self.assertIn("3110861", source_type[4])
        self.assertIn("ornamental", source_type[4].casefold())
        self.assertIn("3110862", source_type[4])
        self.assertIn("utility", source_type[4].casefold())
        self.assertIn("all four source options", source_type[4].casefold())
        self.assertIn("does not authorize Species-row projection/import", source_type[4])
        self.assertIn("does not authorize species-row projection/import", source_type[4].casefold())
        self.assertIn("crop_category VARCHAR(100)", CROP_SCHEMA)

    def test_new_category_labels_are_documented_as_free_text_schema_values(self):
        migration = ROOT / "schemas/postgres/366_crop_category_extensions.sql"
        self.assertTrue(migration.exists(), "missing crop category vocabulary migration")
        sql = migration.read_text().casefold()
        self.assertIn("comment on column crop.crop_category", sql)
        self.assertIn("ornamental", sql)
        self.assertIn("utility", sql)
        self.assertIn("free-text", sql)

    def test_owner_scope_drops_density_and_unit_of_metric(self):
        unit = crosswalk_row(SPECIES, "Unit of Metric", "2729828")
        density = crosswalk_row(
            SPECIES, "Harvest Units Density in Square Meter", "4039538"
        )
        self.assertEqual(unit[2], "—")
        self.assertEqual(unit[3], "`EXCLUDE_OWNER`")
        self.assertIn("Batch 39 owner drops this field", unit[4])
        self.assertIn("superseding its earlier held metadata-path candidate", unit[4])
        self.assertIn("controlled archive", unit[4])
        self.assertIn("do not map to `crop.expected_yield_unit`", unit[4])
        self.assertEqual(
            density[2],
            "`crop.metadata.baserow_legacy.harvest_units_density_per_m2`",
        )
        self.assertEqual(density[3], "`EXCLUDE_OWNER`")
        self.assertIn("Owner scope decision", density[4])
        self.assertIn("43 explicit numeric values", density[4].casefold())
        self.assertIn("40 are zero", density[4].casefold())
        self.assertIn("3 nonzero", density[4].casefold())
        self.assertIn("two nonzero values have a unit", density[4].casefold())
        self.assertTrue(
            "one nonzero value lacks a unit" in density[4].casefold()
            or "one nonzero value does not" in density[4].casefold()
        )
        self.assertIn("excluded by owner decision", density[4].casefold())
        self.assertIn("meaning of zero", density[4].casefold())
        self.assertIn("do not project or map to expected yield", density[4].casefold())
        self.assertIn("expected_yield_per_ha NUMERIC(12,4)", CROP_SCHEMA)

    def test_unmodeled_crop_parameters_have_specific_held_paths(self):
        bed_area = crosswalk_row(SPECIES, "Bed Area in Square Meter", "4039545")
        beds = crosswalk_row(SPECIES, "Beds per Plot of Land", "4039547")
        loss = crosswalk_row(SPECIES, "Loss Rate %", "4039670")
        expected = (
            (bed_area, "crop.metadata.baserow_legacy.bed_area_m2"),
            (beds, "crop.metadata.baserow_legacy.beds_per_plot"),
            (loss, "crop.metadata.baserow_legacy.loss_rate_percent"),
        )
        for row, path in expected:
            self.assertEqual(row[2], f"`{path}`")
            self.assertEqual(row[3], "`EXCLUDE_OWNER`")
            self.assertIn("Owner scope decision", row[4])
            self.assertIn("43 explicit numeric values", row[4].casefold())
            self.assertTrue(
                "40 are zero" in row[4].casefold()
                or "40 zero" in row[4].casefold()
            )
            self.assertTrue(
                "do not project" in row[4].casefold()
                or "project it" in row[4].casefold()
            )
        self.assertIn("one value is fractional", beds[4].casefold())
        self.assertIn("cycle-specific", bed_area[4].casefold())

    def test_source_uuid_and_gbif_url_are_provenance_only(self):
        source_uuid = crosswalk_row(SPECIES, "UUID", "4033810")
        gbif = crosswalk_row(SPECIES, "GBIF Database", "4033391")
        self.assertEqual(
            source_uuid[2], "`crop.metadata.baserow_legacy.source_uuid`"
        )
        self.assertEqual(source_uuid[3], "`PROVENANCE_ONLY`")
        self.assertIn("43 values are unique", source_uuid[4].casefold())
        self.assertIn("table-scoped", source_uuid[4].casefold())
        self.assertEqual(
            gbif[2], "`crop.metadata.baserow_legacy.gbif_database_url`"
        )
        self.assertEqual(gbif[3], "`PROVENANCE_ONLY`")
        self.assertIn("20", gbif[4])
        self.assertIn("HTTP(S)", gbif[4])
        self.assertIn("no crop identity", gbif[4].casefold())
        self.assertIn("inferred", gbif[4].casefold())
        self.assertIn("metadata JSONB", CROP_SCHEMA)

    def test_owner_drops_both_farm_crop_edges_but_keeps_species_rows_scoped(self):
        source = crosswalk_row(SPECIES, "Projects", "2308566")
        inverse = crosswalk_row(FARMS, "Species", "2308567")
        for row in (source, inverse):
            self.assertEqual(row[2], "—")
            self.assertEqual(row[3], "`EXCLUDE_OWNER`")
            self.assertIn("Batch 39 owner drops", row[4])
            self.assertIn("controlled archive", row[4])
            self.assertIn("do not emit `farm_crop` edges", row[4])
        self.assertIn("32 edges", source[4])
        self.assertIn("Species rows and other fields remain independently scoped", source[4])
        self.assertIn("existing Species candidate mapping in the projection allow-list is unchanged", source[4])
        self.assertIn("CREATE TABLE IF NOT EXISTS public.farm_crop", FARM_CROP_SCHEMA)
        source_table_ids = {str(spec["source_table_id"]) for spec in PROJECTION["target_tables"]}
        self.assertIn("317629", source_table_ids)
        self.assertIn("is not row-import authorization", source[4])

    def test_plot_species_edges_are_reciprocal_and_not_crop_cycles(self):
        source = crosswalk_row(SPECIES, "Plot of Land", "3136390")
        inverse = crosswalk_row(PLOTS, "Crops", "3136389")
        path = "crop.metadata.baserow_legacy.plot_source_row_ids"
        for row in (source, inverse):
            self.assertEqual(row[2], f"`{path}`")
            self.assertEqual(row[3], "`EXCLUDE_OWNER`")
            self.assertIn("Owner scope decision", row[4])
            self.assertIn("2 exact reciprocal edges", row[4].casefold())
        self.assertIn("two species rows link one plot each", source[4].casefold())
        self.assertTrue(
            "41 have no plot edge" in source[4].casefold()
            or "41 species rows have no plot edge" in source[4].casefold()
        )
        self.assertIn("do not create", source[4].casefold())
        self.assertIn("location_id UUID NOT NULL", CROP_SCHEMA)

    def test_harvest_forecast_relation_is_excluded_with_harvest_sales_scope(self):
        source = crosswalk_row(SPECIES, "Harvest Forecast", "2305710")
        inverse = crosswalk_row(HARVEST, "Crops", "2305709")
        for row in (source, inverse):
            self.assertEqual(row[2], "—")
            self.assertEqual(row[3], "`EXCLUDE_OWNER`")
            self.assertIn("owner-excluded harvest & sales table", row[4].casefold())
        self.assertIn("do not emit", source[4].casefold())
        self.assertIn("do not emit", inverse[4].casefold())

    def test_species_type_is_field_allowlisted_without_import_authorization(self):
        species_entry = next(
            entry for entry in PROJECTION["target_tables"]
            if entry["source_table_id"] == "317629"
        )
        self.assertEqual(set(species_entry["fields"]), {"2305620", "2305621", "4034223"})
        self.assertIn("owner approved species type", REPORT.casefold())
        self.assertIn("future field allow-list only", REPORT.casefold())
        self.assertIn("no source projection or import", REPORT.casefold())
        self.assertIn("no import authorization", PROJECTION["run_scope"].casefold())
        self.assertIn("import_blocked=true", REPORT.casefold())
        self.assertIn("Staging remains stopped", REPORT)


if __name__ == "__main__":
    unittest.main()
