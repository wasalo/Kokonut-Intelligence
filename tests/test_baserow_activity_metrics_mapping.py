from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text()
REPORT = (ROOT / "docs/phase1-baserow-legacy-data-reconciliation.md").read_text()
METRIC_SCHEMA = (ROOT / "schemas/postgres/007_modeled_outputs.sql").read_text()
METRIC_ENGINE = (ROOT / "services/metrics/engine.py").read_text()
ACTIVITY_SCHEMA = (ROOT / "schemas/postgres/359_activity_scope_and_outputs.sql").read_text()
REPORTED_METRIC_MIGRATION = ROOT / "schemas/postgres/364_reported_activity_output_metrics.sql"
REPORTED_METRIC_SCHEMA = REPORTED_METRIC_MIGRATION.read_text() if REPORTED_METRIC_MIGRATION.exists() else ""


def crosswalk_row(section: str, field: str) -> list[str]:
    block = CROSSWALK.split(f"### {section}", 1)[1].split("\n### ", 1)[0]
    for line in block.splitlines():
        if line.startswith("|") and f"`{field}`" in line:
            return [cell.strip() for cell in line.strip("|").split("|")]
    raise AssertionError(f"Missing crosswalk row: {section}.{field}")


class ActivityMetricsMappingTests(unittest.TestCase):
    def test_indicator_is_preserved_as_reported_label_not_a_governed_definition(self):
        indicator = crosswalk_row("F004 — Activity Metrics (table ID `534174`; 8 fields)", "Indicator")
        self.assertEqual(indicator[2], "`farm_activity_reported_metric.indicator_label`")
        self.assertEqual(indicator[3], "`CANDIDATE`")
        self.assertIn("all 14 populated labels are distinct", indicator[4].casefold())
        self.assertIn("none exactly matches", indicator[4].casefold())
        self.assertIn("repository-seeded", indicator[4].casefold())
        self.assertIn("reported", indicator[4].casefold())
        self.assertIn("not as", indicator[4].casefold())
        self.assertIn("metric_definition.metric_key", indicator[4])

    def test_reported_value_has_explicit_unverified_storage_separate_from_metric_value(self):
        value = crosswalk_row("F004 — Activity Metrics (table ID `534174`; 8 fields)", "Value")
        self.assertEqual(value[2], "`farm_activity_reported_metric.reported_value`")
        self.assertEqual(value[3], "`CANDIDATE`")
        self.assertIn("all 14 numeric values fit", value[4].casefold())
        self.assertIn("unit", value[4].casefold())
        self.assertIn("period", value[4].casefold())
        self.assertIn("unverified", value[4].casefold())
        self.assertIn("never as `metric_value`", value[4].casefold())
        self.assertIn("reported_value NUMERIC(15,4) NOT NULL", REPORTED_METRIC_SCHEMA)
        self.assertIn("reported_unit TEXT", REPORTED_METRIC_SCHEMA)
        self.assertIn("period_start DATE", REPORTED_METRIC_SCHEMA)
        self.assertIn("calculator = CALCULATORS.get(metric_key)", METRIC_ENGINE)
        self.assertIn("NOW(), FALSE", METRIC_ENGINE)
        self.assertIn("unit VARCHAR(50)", METRIC_SCHEMA)

    def test_description_and_output_edges_have_typed_report_targets(self):
        description = crosswalk_row("F004 — Activity Metrics (table ID `534174`; 8 fields)", "Description")
        self.assertEqual(description[2], "`farm_activity_reported_metric.reported_description`")
        self.assertEqual(description[3], "`CANDIDATE`")

        metric_link = crosswalk_row("F004 — Activity Metrics (table ID `534174`; 8 fields)", "F003 - Activity Outputs")
        self.assertEqual(metric_link[2], "`farm_activity_reported_metric_output (reported_metric_id, output_id)`")
        self.assertEqual(metric_link[3], "`RELATIONSHIP`")
        self.assertIn("exact reciprocal relation has 14 edges", metric_link[4].casefold())
        self.assertIn("each metric row links to exactly one output", metric_link[4])
        self.assertIn("across 12 outputs", metric_link[4])
        inverse = crosswalk_row("F003 — Activity Outputs (table ID `534165`; 9 fields)", "F004 - Activity Metrics")
        self.assertEqual(inverse[3], "`RELATIONSHIP`")
        self.assertIn("validate this reciprocal", inverse[4].casefold())
        self.assertIn("REFERENCES farm_activity_output(id)", REPORTED_METRIC_SCHEMA)
        self.assertIn("REFERENCES farm_activity_reported_metric(id)", REPORTED_METRIC_SCHEMA)
        self.assertNotIn("metric_id UUID NOT NULL REFERENCES metric_definition", REPORTED_METRIC_SCHEMA)
        self.assertNotIn("verified BOOLEAN", REPORTED_METRIC_SCHEMA)
        self.assertIn("activity-output", REPORT.casefold())

    def test_activity_outputs_remain_distinct_from_metrics_and_claims(self):
        output = crosswalk_row("F003 — Activity Outputs (table ID `534165`; 9 fields)", "Deliverable Name")
        output_link = crosswalk_row("F003 — Activity Outputs (table ID `534165`; 9 fields)", "F001 — Activity Report")
        media = crosswalk_row("F003 — Activity Outputs (table ID `534165`; 9 fields)", "Proof Media")
        self.assertEqual(output[2], "`farm_activity_output.output_name`")
        self.assertEqual(output[3], "`CANDIDATE`")
        self.assertIn("17 distinct", output[4])
        self.assertIn("source table/row identity", output[4].casefold())
        self.assertEqual(output_link[2], "`farm_activity_output_activity` association")
        self.assertEqual(output_link[3], "`RELATIONSHIP`")
        self.assertIn("22 reciprocal edges", output_link[4])
        self.assertEqual(media[3], "`MANUAL_CURATION`")
        self.assertIn("not formal impact claims", ACTIVITY_SCHEMA.casefold())

    def test_impact_records_and_metric_links_remain_quarantined(self):
        impact_name = crosswalk_row("Impact (table ID `554746`; 14 fields)", "Name")
        impact_score = crosswalk_row("Impact (table ID `554746`; 14 fields)", "Impact Score")
        metric_impact = crosswalk_row("F004 — Activity Metrics (table ID `534174`; 8 fields)", "Impact")
        self.assertEqual(impact_name[3], "`HOLD_FIELD`")
        self.assertIn("work/evidence", impact_name[4].casefold())
        self.assertEqual(impact_score[3], "`HOLD_FIELD`")
        self.assertIn("no supported metric definition", impact_score[4].casefold())
        self.assertEqual(metric_impact[3], "`HOLD_RELATIONSHIP`")
        self.assertIn("zero edges", metric_impact[4].casefold())
        self.assertIn("impact score", REPORT.casefold())
        self.assertIn("zero reciprocal", REPORT.casefold())


if __name__ == "__main__":
    unittest.main()
