from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text()
REPORT = (ROOT / "docs/phase1-baserow-legacy-data-reconciliation.md").read_text()
PROJECTION = json.loads((ROOT / "docs/phase1-baserow-projection-allowlist.json").read_text())
PHASE_STEP_SCHEMA = (ROOT / "schemas/postgres/061_impact_value_chain.sql").read_text()
TASK_STEP_SCHEMA = (ROOT / "schemas/postgres/361_farm_task_relationships.sql").read_text()
OBJECTIVE_SCHEMA = (ROOT / "schemas/postgres/053_configurable_containers.sql").read_text()


def crosswalk_row(section: str, field: str) -> list[str]:
    block = CROSSWALK.split(f"### {section}", 1)[1].split("\n### ", 1)[0]
    for line in block.splitlines():
        if line.startswith("|") and f"`{field}`" in line:
            return [cell.strip() for cell in line.strip("|").split("|")]
    raise AssertionError(f"Missing crosswalk row: {section}.{field}")


class PhaseStepMappingTests(unittest.TestCase):
    def test_phase_rows_are_blocked_by_order_and_multi_location_scope(self):
        phase_name = crosswalk_row("Development Phases (table ID `326753`; 5 fields)", "Name")
        phase_farm = crosswalk_row("Development Phases (table ID `326753`; 5 fields)", "Kokonut Farms")
        phase_steps = crosswalk_row("Development Phases (table ID `326753`; 5 fields)", "Development Phase Step")
        self.assertEqual(phase_name[3], "`CANDIDATE`")
        self.assertIn("target also requires `phase_order`", phase_name[4].casefold())
        self.assertIn("not approved as phase order", phase_name[4])
        self.assertIn("composite source identity", phase_name[4].casefold())
        self.assertEqual(phase_farm[2], "—")
        self.assertEqual(phase_farm[3], "`HOLD_RELATIONSHIP`")
        self.assertIn("three exact reciprocal edges", phase_farm[4].casefold())
        self.assertIn("2 different locations", phase_farm[4].casefold())
        self.assertEqual(phase_steps[3], "`HOLD_RELATIONSHIP`")
        self.assertIn("fourteen exact reciprocal edges", phase_steps[4].casefold())
        self.assertIn("phase_order INT NOT NULL", PHASE_STEP_SCHEMA)
        self.assertIn("location_id UUID NOT NULL", PHASE_STEP_SCHEMA)

    def test_framework_steps_do_not_infer_required_order_or_default_type(self):
        title = crosswalk_row("Framework Steps (table ID `331882`; 9 fields)", "Title")
        step_type = crosswalk_row("Framework Steps (table ID `331882`; 9 fields)", "Type")
        self.assertEqual(title[3], "`CANDIDATE`")
        self.assertIn("target requires `step_order`", title[4].casefold())
        self.assertIn("not approved as step order", title[4])
        self.assertEqual(step_type[3], "`HOLD_FIELD`")
        self.assertIn("empty in all 14", step_type[4].casefold())
        self.assertIn("do not use that default", step_type[4].casefold())
        self.assertIn("step_order INT NOT NULL", PHASE_STEP_SCHEMA)
        self.assertIn("step_type VARCHAR(100) NOT NULL DEFAULT 'implementation'", PHASE_STEP_SCHEMA)

    def test_phase_farm_and_step_phase_relations_remain_held_without_typed_targets(self):
        step_phase = crosswalk_row("Framework Steps (table ID `331882`; 9 fields)", "Development Phase")
        phase_phase = crosswalk_row("Development Phases (table ID `326753`; 5 fields)", "Development Phase Step")
        self.assertEqual(step_phase[2], "—")
        self.assertEqual(step_phase[3], "`HOLD_RELATIONSHIP`")
        self.assertIn("fourteen exact reciprocal edges", step_phase[4].casefold())
        self.assertIn("no `framework_step.development_phase_id`", step_phase[4])
        self.assertIn("typed target relation", step_phase[4].casefold())
        self.assertEqual(phase_phase[3], "`HOLD_RELATIONSHIP`")
        self.assertIn("no target relation is approved", phase_phase[4].casefold())
        self.assertNotIn("development_phase_id", PHASE_STEP_SCHEMA)

    def test_task_step_edges_are_reciprocal_but_scope_mismatches_are_blocked(self):
        step_side = crosswalk_row("Framework Steps (table ID `331882`; 9 fields)", "Farms Individual Tasks")
        task_side = crosswalk_row("Kokonut Farm Tasks (table ID `305801`; 34 fields)", "Framework Steps")
        self.assertEqual(step_side[3], "`CONDITIONAL`")
        self.assertEqual(task_side[3], "`CONDITIONAL`")
        self.assertIn("forty-one exact reciprocal many-to-many edges", step_side[4].casefold())
        self.assertIn("21", step_side[4])
        self.assertIn("18", step_side[4])
        self.assertIn("2", step_side[4])
        self.assertIn("quarantine", step_side[4].casefold())
        self.assertIn("farm_task_framework_step", TASK_STEP_SCHEMA)

    def test_prerequisites_keep_source_identity_and_validated_acyclic_graph(self):
        prerequisites = crosswalk_row("Framework Steps (table ID `331882`; 9 fields)", "Prerequisites")
        self.assertEqual(prerequisites[3], "`CONDITIONAL`")
        self.assertIn("four source edges", prerequisites[4].casefold())
        self.assertIn("no self-links or cycles", prerequisites[4].casefold())
        self.assertIn("composite source identity", prerequisites[4].casefold())
        self.assertIn("prerequisites JSONB", PHASE_STEP_SCHEMA)

    def test_empty_objectives_and_phase_step_tables_stay_outside_projection(self):
        title = crosswalk_row("Objectives (table ID `554665`; 6 fields)", "Title")
        self.assertEqual(title[2], "`objective.objective_name`")
        self.assertIn("zero of 2 source rows", title[4].casefold())
        self.assertIn("objective_name VARCHAR(255) NOT NULL", OBJECTIVE_SCHEMA)
        ids = {entry["source_table_id"] for entry in PROJECTION["target_tables"]}
        self.assertTrue({"326753", "331882", "554665"}.isdisjoint(ids))
        self.assertIn("objectives table", REPORT.casefold())
        self.assertIn("development phase/framework step", REPORT.casefold())


if __name__ == "__main__":
    unittest.main()
