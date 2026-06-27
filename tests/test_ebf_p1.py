"""EBF P1 calibration, provenance, export, and dashboard tests."""

from decimal import Decimal
from pathlib import Path

from services.scoring.confidence import score_confidence_label, scorecard_confidence_label
from services.scoring.export import export_public_scorecard


SCHEMA = Path("schemas/postgres/033_ebf_p1_operations.sql")
DASHBOARD_SEED = Path("schemas/seeds/033_ebf_dashboard_datasets.sql")


def test_ebf_p1_schema_defines_operational_tables() -> None:
    text = SCHEMA.read_text().lower()
    for table in [
        "ebf_farm_metric_profile",
        "ebf_calibration_session",
        "ebf_calibration_decision",
        "ebf_trust_graph_node",
        "ebf_trust_graph_edge",
        "ebf_improvement_recommendation",
    ]:
        assert f"create table if not exists {table}" in text


def test_ebf_p1_schema_uses_canonical_lifecycle_and_calibration_report_gate() -> None:
    text = SCHEMA.read_text().lower()
    assert "chk_ebf_calibration_session_lifecycle" in text
    for status in ["draft", "submitted", "verified", "published", "rejected"]:
        assert f"'{status}'" in text
    assert "chk_ebf_calibration_session_report" in text
    assert "team_with_report" in text
    assert "third_party" in text


def test_ebf_p1_schema_defines_trust_graph_and_gap_views() -> None:
    text = SCHEMA.read_text().lower()
    assert "v_ebf_evidence_gap_summary" in text
    assert "v_ebf_calibration_history" in text
    assert "missing_evidence" in text
    assert "carbon_requires_level6" in text
    for edge_type in ["supports", "reviewed_by", "calibrated_by", "attested_by", "published_in"]:
        assert f"'{edge_type}'" in text


def test_ebf_p1_dashboard_seed_and_sql_files_exist() -> None:
    text = DASHBOARD_SEED.read_text()
    assert "EBF Farm Scorecard" in text
    assert "EBF Evidence Gaps" in text
    assert "EBF Calibration History" in text
    for path in [
        "dashboards/metabase/sql/22_ebf_scorecard.sql",
        "dashboards/metabase/sql/23_ebf_evidence_gap.sql",
        "dashboards/metabase/sql/24_ebf_calibration_history.sql",
    ]:
        assert Path(path).exists()


def test_ebf_confidence_thresholds() -> None:
    assert score_confidence_label(0, 0) == "insufficient_evidence"
    assert score_confidence_label(1, 2) == "low"
    assert score_confidence_label(2, 4, 1) == "moderate"
    assert score_confidence_label(3, 5, 2) == "high"
    assert scorecard_confidence_label(["high", "moderate"]) == "moderate"
    assert scorecard_confidence_label(["high", "insufficient_evidence"]) == "insufficient_evidence"


def test_public_scorecard_export_shape() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params):
            self.calls += 1

        def fetchone(self):
            return {
                "scorecard_id": "a0000000-0000-0000-0000-000000000100",
                "location_name": "Kokonut Adelphi",
                "overall_score": Decimal("7.2"),
                "overall_confidence": "moderate",
            }

        def fetchall(self):
            return [{
                "pillar_key": "soil_health",
                "pillar_name": "Soil Health",
                "normalized_score": Decimal("7.0"),
                "confidence_level": "moderate",
                "trend_direction": "stable",
                "score_evidence_maturity_level": 4,
                "score_evidence_maturity_label": "Evidence-linked record",
                "evidence_summary": "Linked soil evidence",
                "uncertainty_notes": "Annual sample only",
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    exported = export_public_scorecard(Conn(), "a0000000-0000-0000-0000-000000000100")
    assert exported["export_type"] == "ebf_scorecard_public"
    assert exported["scorecard"]["overall_score"] == 7.2
    assert exported["pillars"][0]["pillar_key"] == "soil_health"
    assert "cids:IndicatorReport" in exported["cids_mapping"]


def test_ebf_csv_templates_exist() -> None:
    assert Path("exports/templates/ebf_scorecard_template.csv").exists()
    assert Path("exports/templates/ebf_evidence_template.csv").exists()


if __name__ == "__main__":
    test_ebf_p1_schema_defines_operational_tables()
    test_ebf_p1_schema_uses_canonical_lifecycle_and_calibration_report_gate()
    test_ebf_p1_schema_defines_trust_graph_and_gap_views()
    test_ebf_p1_dashboard_seed_and_sql_files_exist()
    test_ebf_confidence_thresholds()
    test_public_scorecard_export_shape()
    test_ebf_csv_templates_exist()
