from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text()
REPORT = (ROOT / "docs/phase1-baserow-legacy-data-reconciliation.md").read_text()
PROJECTION = json.loads((ROOT / "docs/phase1-baserow-projection-allowlist.json").read_text())
FARM_SECTION = "Kokonut Farms (table ID `305805`; 54 fields)"


def crosswalk_row(field_name: str, field_id: str) -> list[str]:
    block = CROSSWALK.split(f"### {FARM_SECTION}", 1)[1].split("\n### ", 1)[0]
    expected_first_cell = f"`{field_name}` (`{field_id}`)"
    for line in block.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells[0] == expected_first_cell:
                return cells
    raise AssertionError(f"Missing crosswalk field identity: {field_name} ({field_id})")


class KokonutFarmsBatch30Tests(unittest.TestCase):
    def test_inverse_edges_are_validated_but_emitted_only_from_canonical_side(self):
        cases = (
            ("Ground Expenses", "2305092", "expense_event.farm_id", "533 edges"),
            ("KKN-GEN-F001", "2350183", "farm_activity.farm_id", "255 edges"),
            ("Plot of Land", "3136781", "plot.farm_id", "8 edges"),
        )
        for name, field_id, target, edge_count in cases:
            with self.subTest(field=name):
                row = crosswalk_row(name, field_id)
                self.assertIn(f"`{target}`", row[2])
                self.assertEqual(row[3], "`RELATIONSHIP`")
                self.assertIn("exact reciprocal", row[4].casefold())
                self.assertIn(edge_count, row[4])
                self.assertIn("not again", row[4].casefold())

    def test_phase_table_and_project_coordinates_are_excluded_and_crop_edges_dropped(self):
        stage = crosswalk_row("Stage", "2202767")
        self.assertEqual(stage[3], "`EXCLUDE_OWNER`")
        self.assertIn("Development Phases table", stage[4])

        species = crosswalk_row("Species", "2308567")
        self.assertEqual(species[2], "—")
        self.assertEqual(species[3], "`EXCLUDE_OWNER`")
        self.assertIn("Batch 39 owner drops", species[4])
        self.assertIn("32 edges", species[4])
        self.assertIn("controlled archive", species[4])

        coordinates = crosswalk_row("Project Coordinates", "3790808")
        self.assertEqual(coordinates[3], "`EXCLUDE_OWNER`")
        self.assertIn("owner decision", coordinates[4].casefold())
        self.assertIn("do not extract", coordinates[4].casefold())

    def test_owner_approved_per_farm_metadata_paths_remain_candidates_not_imports(self):
        cases = (
            ("Governance Mechanism", "3790827", "governance_mechanism"),
            ("Token Allocation", "3790828", "token_allocation"),
            ("Public Goods Allocation", "3790829", "public_goods_allocation"),
            ("Target Market", "3791643", "target_market"),
            ("Revenue Streams", "3793659", "revenue_streams"),
            ("Start", "2202759", "start"),
            ("Source of Funding", "3790819", "source_of_funding"),
            ("Project Summary", "3790836", "project_summary"),
            ("Local Problem", "3790838", "local_problem"),
            ("Proposed Solution", "3790843", "proposed_solution"),
            ("Project Mission", "4445740", "project_mission"),
        )
        for name, field_id, path in cases:
            with self.subTest(field=name):
                row = crosswalk_row(name, field_id)
                self.assertIn(f"farm.metadata.legacy_source_fields.{path}", row[2])
                self.assertEqual(row[3], "`CANDIDATE`")
                rule = row[4].casefold()
                self.assertTrue("owner approves" in rule or "owner confirms" in rule)
                self.assertIn("candidate", rule)
                self.assertIn("not allow-list or import approval", row[4].casefold())
                if name in {"Governance Mechanism", "Target Market", "Revenue Streams"}:
                    self.assertIn("stable source option id", row[4].casefold())
                    self.assertIn("exact", row[4].casefold())
                if name in {"Target Market", "Revenue Streams"}:
                    self.assertIn("without normalization", row[4].casefold())
                    self.assertIn("or splitting", row[4].casefold())

    def test_batch30_scope_did_not_expand_the_explicit_farm_projection_allowlist(self):
        farm = next(
            entry
            for entry in PROJECTION["target_tables"]
            if str(entry["source_table_id"]) == "305805"
        )
        allowed = set(farm.get("fields", {}))
        for field_id in (
            "2202759",
            "2202767",
            "2305092",
            "2308567",
            "2350183",
            "3136781",
            "3790808",
            "3790819",
            "3790827",
            "3790828",
            "3790829",
            "3790836",
            "3790838",
            "3790843",
            "3791643",
            "3793659",
            "4445740",
        ):
            with self.subTest(field_id=field_id):
                self.assertNotIn(field_id, allowed)
        self.assertIn("Batch 30", REPORT)
        self.assertIn("import_blocked=true", REPORT)


if __name__ == "__main__":
    unittest.main()
