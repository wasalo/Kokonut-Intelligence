from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text()
REPORT = (ROOT / "docs/phase1-baserow-legacy-data-reconciliation.md").read_text()
DECISIONS = (ROOT / "docs/phase1-baserow-blocker-decisions.md").read_text()
PROJECTION = json.loads((ROOT / "docs/phase1-baserow-projection-allowlist.json").read_text())


HARVEST_SECTION = "Harvest & Sales (table ID `317638`; 28 fields)"


def crosswalk_row(section: str, field: str, field_id: str) -> list[str]:
    block = CROSSWALK.split(f"### {section}", 1)[1].split("\n### ", 1)[0]
    expected_first_cell = f"`{field}` (`{field_id}`)"
    for line in block.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells[0] == expected_first_cell:
                return cells
    raise AssertionError(f"Missing crosswalk row: {section}.{field}")


class HarvestSalesMappingTests(unittest.TestCase):
    def test_table_scope_excludes_all_harvest_sales_fields(self):
        block = CROSSWALK.split(f"### {HARVEST_SECTION}", 1)[1].split("\n### ", 1)[0]
        rows = []
        for line in block.splitlines():
            if not line.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) == 5 and cells[0] not in {"Source field (ID)", "---"}:
                rows.append(cells)
        self.assertEqual(len(rows), 28)
        self.assertEqual(
            {row[3] for row in rows},
            {"`EXCLUDE_OWNER`", "`EXCLUDE_DERIVED`"},
        )
        table_note = block.casefold()
        self.assertIn("exclude every harvest & sales source row", table_note)
        self.assertIn("preserve the source snapshot in the controlled archive", table_note)
        self.assertIn("does not authorize manual ki entry", table_note)

    def test_current_harvest_sales_scope_decisions_are_all_drop(self):
        blocker_table = DECISIONS.split("## Field-by-field decisions", 1)[1].split("## Decision totals", 1)[0]
        rows = [
            line
            for line in blocker_table.splitlines()
            if line.startswith("|") and "| Harvest & Sales |" in line
        ]
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row.rstrip().endswith("**DROP** |") for row in rows))
        self.assertIn("66 DROP and 18 PURSUE", DECISIONS)

    def test_harvest_sales_record_edges_and_inverses_are_excluded(self):
        edges = (
            (HARVEST_SECTION, "Crops", "2305709"),
            (HARVEST_SECTION, "Lots of Land", "3142259"),
            (HARVEST_SECTION, "Kokonut Farms", "4042180"),
            ("Species (table ID `317629`; 21 fields)", "Harvest Forecast", "2305710"),
            ("Kokonut Farms (table ID `305805`; 54 fields)", "Harvest & Sales Forecast", "4042181"),
            ("Land Lots (table ID `410138`; 10 fields)", "Harvest Forecast", "3142260"),
        )
        for section, field, field_id in edges:
            with self.subTest(field=field, field_id=field_id):
                row = crosswalk_row(section, field, field_id)
                self.assertEqual(row[3], "`EXCLUDE_OWNER`")
                self.assertEqual(row[2], "—")

    def test_harvest_sales_table_is_not_in_projection_allowlist(self):
        table_ids = {entry["source_table_id"] for entry in PROJECTION["target_tables"]}
        self.assertNotIn("317638", table_ids)
        self.assertIn("### Batch 33", REPORT)
        self.assertIn("no allow-list change, projection, import", DECISIONS.casefold())


if __name__ == "__main__":
    unittest.main()
