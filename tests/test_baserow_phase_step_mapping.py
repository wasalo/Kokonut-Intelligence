from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text(encoding="utf-8")
REPORT = (ROOT / "docs/phase1-baserow-legacy-data-reconciliation.md").read_text(encoding="utf-8")
PROJECTION = json.loads((ROOT / "docs/phase1-baserow-projection-allowlist.json").read_text(encoding="utf-8"))
SCHEMA_DRAFT = (ROOT / "docs/schema-drafts/368_baserow_expense_and_farm_crop_schema_draft.sql").read_text(encoding="utf-8")
SCHEMA_PROPOSAL = (ROOT / "docs/phase1-baserow-schema-proposal-batch36.md").read_text(encoding="utf-8")
PHASES = "Development Phases (table ID `326753`; 5 fields)"
FRAMEWORK = "Framework Steps (table ID `331882`; 9 fields)"


def section_rows(section: str) -> list[list[str]]:
    block = CROSSWALK.split(f"### {section}", 1)[1].split("\n### ", 1)[0]
    return [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in block.splitlines()
        if line.startswith("|") and line.strip().startswith("| `")
    ]


def field_row(field_id: str) -> list[str]:
    for line in CROSSWALK.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and f"(`{field_id}`)" in cells[0]:
            return cells
    raise AssertionError(f"Missing crosswalk field ID {field_id}")


class PhaseStepMappingTests(unittest.TestCase):
    def test_entire_phase_and_framework_step_tables_are_owner_excluded(self):
        for section, expected_count in ((PHASES, 5), (FRAMEWORK, 9)):
            rows = section_rows(section)
            self.assertEqual(len(rows), expected_count)
            for row in rows:
                with self.subTest(section=section, field=row[0]):
                    self.assertEqual(row[2], "—")
                    self.assertEqual(row[3], "`EXCLUDE_OWNER`")
                    self.assertIn("excludes the entire", row[4].casefold())
                    self.assertIn("controlled archive", row[4].casefold())

    def test_every_inverse_edge_is_excluded_without_excluding_endpoint_tables(self):
        # Farm.Stage, Farm Task.Framework Steps, Land Lots phase/step links, Equipment link,
        # and the F002/Staff actor edges are excluded; their endpoint records remain separate.
        for field_id in ("2202767", "2386683", "3136769", "3918767", "2437665", "2350403", "2350404"):
            row = field_row(field_id)
            with self.subTest(field_id=field_id):
                self.assertEqual(row[2], "—")
                self.assertEqual(row[3], "`EXCLUDE_OWNER`")
                self.assertIn("preserve", row[4].casefold())
        self.assertIn("F002 expense rows remain independently scoped", field_row("2350403")[4])
        self.assertIn("Staff rows remain independently scoped", field_row("2350404")[4])

    def test_phase_step_catalog_proposal_is_superseded_and_not_implemented(self):
        self.assertIn("superseded by batch 37", SCHEMA_PROPOSAL.casefold())
        self.assertIn("Development Phases and Framework Steps", SCHEMA_PROPOSAL)
        self.assertNotIn("development_phase_catalog", SCHEMA_DRAFT)
        self.assertNotIn("framework_step_catalog", SCHEMA_DRAFT)
        source_table_ids = {str(item["source_table_id"]) for item in PROJECTION["target_tables"]}
        self.assertTrue({"326753", "331882"}.isdisjoint(source_table_ids))
        self.assertIn("Batch 37", REPORT)


if __name__ == "__main__":
    unittest.main()
