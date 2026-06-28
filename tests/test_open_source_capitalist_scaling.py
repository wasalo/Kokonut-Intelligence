"""Open Source Capitalist scaling economics, barriers, stress, and reuse tests."""

from pathlib import Path

from services.agents.open_source_capitalist_agent import synthesize_open_source_capitalist
from services.agents.tasks import get_task, list_tasks, validate_output
from services.export.report_generator import (
    REPORT_GENERATORS,
    generate_adoption_barriers,
    generate_open_source_impact,
    generate_perpetual_value_stress,
    generate_scaling_economics,
)


SCHEMA = Path("schemas/postgres/040_open_source_capitalist_scaling.sql")
SEED = Path("schemas/seeds/041_open_source_capitalist_scaling.sql")
PILOT_SEED = Path("schemas/seeds/041_pilot_open_source_capitalist_scaling.sql")


def test_open_source_capitalist_schema_defines_records_and_public_views() -> None:
    text = SCHEMA.read_text()
    for table in [
        "farm_launch_unit_economics",
        "network_scaling_target",
        "adoption_barrier_assessment",
        "perpetual_value_stress_test",
        "open_source_impact_artifact",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text
    for view in [
        "v_public_farm_launch_unit_economics",
        "v_public_network_scaling_target",
        "v_public_adoption_barrier_assessment",
        "v_public_perpetual_value_stress_test",
        "v_public_open_source_impact_artifact",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text
    assert "evidence_maturity >= 3" in text
    assert "farm_registry_record" in text
    assert "projected_roi_pct" in text
    assert "combined_downside" in text


def test_open_source_capitalist_seed_and_dashboards_exist() -> None:
    text = SEED.read_text()
    for metric in [
        "farm_launch_cost_usd",
        "cost_per_planned_farm_usd",
        "projected_roi_pct",
        "cost_per_beneficiary_usd",
        "cost_per_hectare_restored_usd",
        "downside_runway_months",
        "adoption_barrier_resolution_pct",
        "open_source_artifact_reuse_count",
    ]:
        assert metric in text
    for sql in [
        "48_scaling_economics.sql",
        "49_adoption_barriers.sql",
        "50_perpetual_value_stress.sql",
        "51_open_source_impact.sql",
    ]:
        assert Path("dashboards/metabase/sql").joinpath(sql).exists()
    for dashboard in [
        "48_scaling_economics.json",
        "49_adoption_barriers.json",
        "50_perpetual_value_stress.json",
        "51_open_source_impact.json",
    ]:
        assert Path("dashboards/metabase").joinpath(dashboard).exists()
    assert "refresh_cron" in text


def test_pilot_seed_has_claim_boundaries_and_no_unsupported_live_farm_claims() -> None:
    text = PILOT_SEED.read_text()
    assert "adelphi-two-farm-unit-economics-2026" in text
    assert "planned conditional unit economics, not already operating farms" in text
    assert "not evidence of two already-operating farms" in text
    assert "planned pipeline, not already operating farms" in text
    assert "Kokonut Venus Farm" not in text
    assert "Hypercert" not in text
    assert "Ecocertain" not in text


def test_open_source_capitalist_agent_task_catalogue_and_validation() -> None:
    assert "open_source_capitalist_synthesis" in list_tasks()
    task = get_task("open_source_capitalist_synthesis")
    assert task["writes"] == ["ai_summary:draft"]
    assert task["high_risk"] is False
    assert validate_output("open_source_capitalist_synthesis", {}) == ["Missing required output field: summary"]


def test_open_source_capitalist_agent_summarizes_public_safe_records() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchall(self):
            if self.calls == 1:
                return [{
                    "economics_name": "Two-farm economics",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "target_region": "Dominican Republic pilot cluster",
                    "farm_model": "blended",
                    "planned_farm_count": 2,
                    "planned_hectares": 2.7676,
                    "expected_beneficiary_count": 24,
                    "total_launch_cost_usd": 60000,
                    "cost_per_farm_usd": 30000,
                    "cost_per_hectare_usd": 21679.43,
                    "cost_per_beneficiary_usd": 2500,
                    "projected_annual_revenue_usd": 49000,
                    "projected_annual_noi_usd": 18400,
                    "projected_roi_pct": 30.6667,
                    "payback_months": 39.13,
                    "launch_timeline_months": 12,
                    "assumptions": ["planned/conditional"],
                    "evidence_confidence": "moderate",
                    "public_summary": "Economics summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 2:
                return [{
                    "target_name": "Four-farm playbook",
                    "target_region": "Celo/Gnosis aligned ReFi partner network",
                    "farm_model": "public_good_optimized",
                    "target_date": "2027-06-30",
                    "target_farm_count": 4,
                    "target_hectares": 5.5352,
                    "target_beneficiary_count": 48,
                    "capital_required_usd": 120000,
                    "capital_required_per_farm_usd": 30000,
                    "expected_public_goods_value_usd": 9800,
                    "expected_verification_outputs": 24,
                    "readiness_score": 5.5,
                    "dependency_summary": "Dependencies.",
                    "risk_gate_summary": "Risk gates.",
                    "target_status": "planned",
                    "public_summary": "Target summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 3:
                return [{
                    "assessment_date": "2026-03-31",
                    "barrier_category": "regulatory",
                    "barrier_name": "Local permitting",
                    "affected_scope": "region",
                    "severity": "medium",
                    "likelihood": "unknown",
                    "resolution_status": "open",
                    "owner_role": "Governance Guild",
                    "estimated_mitigation_cost_usd": 2500,
                    "target_resolution_date": "2026-10-31",
                    "public_summary": "Barrier summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 4:
                return [{
                    "scenario_name": "Downside stress",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "scenario_date": "2026-03-31",
                    "stress_type": "combined_downside",
                    "revenue_change_pct": -25,
                    "cost_change_pct": 15,
                    "grant_delay_months": 3,
                    "yield_change_pct": -20,
                    "baseline_runway_months": 9.5,
                    "downside_runway_months": 5.2,
                    "baseline_noi_usd": 9200,
                    "downside_noi_usd": 50,
                    "solvency_status": "needs_mitigation",
                    "mitigation_actions": ["defer expansion"],
                    "public_summary": "Stress summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            return [{
                "artifact_name": "Governed schemas",
                "artifact_type": "schema",
                "repository_path": "schemas/postgres/",
                "external_url": None,
                "license": "repo_license",
                "version": "v2026.06",
                "reuse_status": "in_use",
                "reuse_count": 1,
                "supported_use_cases": ["farm evidence"],
                "verification_outputs": ["public views"],
                "maintenance_owner": "Technology Guild",
                "public_summary": "Artifact summary.",
                "evidence_maturity": 3,
                "evidence_maturity_label": "Reviewed record",
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    summary = synthesize_open_source_capitalist(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["launch_economics_count"] == 1
    assert summary["network_scaling_target_count"] == 1
    assert summary["adoption_barrier_count"] == 1
    assert summary["perpetual_stress_test_count"] == 1
    assert summary["open_source_artifact_count"] == 1
    assert summary["planned_farm_count"] == 2
    assert summary["target_farm_count"] == 4
    assert summary["total_launch_cost_usd"] == 60000
    assert "planned farm counts are not live-farm claims" in summary["safety_note"]


def test_open_source_capitalist_report_generators_registered() -> None:
    for report_type in [
        "scaling_economics",
        "adoption_barriers",
        "perpetual_value_stress",
        "open_source_impact",
    ]:
        assert report_type in REPORT_GENERATORS


def test_open_source_capitalist_report_generators_public_safe() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchall(self):
            if self.calls == 1:
                return [{"total_launch_cost_usd": 60000, "planned_farm_count": 2, "public_summary": "Economics"}]
            if self.calls == 2:
                return [{"capital_required_usd": 120000, "target_farm_count": 4, "public_summary": "Target"}]
            return [{
                "resolution_status": "open",
                "solvency_status": "needs_mitigation",
                "reuse_count": 1,
                "public_summary": "Public summary",
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    conn = Conn()
    economics = generate_scaling_economics(conn, "a0000000-0000-0000-0000-000000000001")
    assert economics["report_type"] == "scaling_economics"
    assert economics["planned_farm_count"] == 2
    assert economics["target_farm_count"] == 4
    assert "not guaranteed ROI" in economics["limitations"][0]
    assert generate_adoption_barriers(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "adoption_barriers"
    assert generate_perpetual_value_stress(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "perpetual_value_stress"
    open_source = generate_open_source_impact(conn, "a0000000-0000-0000-0000-000000000001")
    assert open_source["report_type"] == "open_source_impact"
    assert "Hypercert" in open_source["limitations"][1]


if __name__ == "__main__":
    test_open_source_capitalist_schema_defines_records_and_public_views()
    test_open_source_capitalist_seed_and_dashboards_exist()
    test_pilot_seed_has_claim_boundaries_and_no_unsupported_live_farm_claims()
    test_open_source_capitalist_agent_task_catalogue_and_validation()
    test_open_source_capitalist_agent_summarizes_public_safe_records()
    test_open_source_capitalist_report_generators_registered()
    test_open_source_capitalist_report_generators_public_safe()
