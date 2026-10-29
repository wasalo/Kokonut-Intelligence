"""Open Source Capitalist scaling economics, barriers, stress, and reuse tests."""

import re
from pathlib import Path
from unittest.mock import Mock

import pytest

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
        def __init__(self, queries):
            self.queries = queries

        def execute(self, query, params=None):
            self.queries.append((query, params))

        def fetchall(self):
            if len(self.queries) == 1:
                return [{"total_launch_cost_usd": 60000, "planned_farm_count": 2, "public_summary": "Economics"}]
            if len(self.queries) == 2:
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
        def __init__(self):
            self.queries = []

        def cursor(self, cursor_factory=None):
            return Cursor(self.queries)

    conn = Conn()
    economics = generate_scaling_economics(conn, "a0000000-0000-0000-0000-000000000001")
    assert economics["report_type"] == "scaling_economics"
    assert economics["scope"] == "location"
    assert economics["planned_farm_count"] == 2
    assert economics["target_farm_count"] is None
    assert economics["total_target_capital_usd"] is None
    assert economics["network_targets"] == []
    assert len(conn.queries) == 1
    assert "WHERE location_id = %s::uuid" in conn.queries[0][0]
    assert conn.queries[0][1] == ("a0000000-0000-0000-0000-000000000001",)
    assert "not guaranteed ROI" in economics["limitations"][0]
    assert generate_adoption_barriers(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "adoption_barriers"
    barrier_query, barrier_params = conn.queries[1]
    assert "WHERE (location_id = %s OR location_id IS NULL)" in barrier_query
    assert barrier_params[0] == "a0000000-0000-0000-0000-000000000001"
    assert generate_perpetual_value_stress(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "perpetual_value_stress"
    open_source = generate_open_source_impact(conn)
    assert open_source["report_type"] == "open_source_impact"
    assert "Hypercert" in open_source["limitations"][1]


def test_open_source_impact_uses_exact_projection_and_preserves_payload() -> None:
    expected_columns = [
        "id", "artifact_name", "artifact_type", "repository_path", "external_url",
        "license", "version", "reuse_status", "reuse_count", "supported_use_cases",
        "verification_outputs", "maintenance_owner", "public_summary",
        "evidence_maturity", "evidence_maturity_label", "metadata",
    ]
    artifact = {
        "id": "artifact-1",
        "artifact_name": "Kokonut data schema",
        "artifact_type": "schema",
        "repository_path": "schemas/postgres/",
        "external_url": "https://example.test/schema",
        "license": "Apache-2.0",
        "version": "1.2.0",
        "reuse_status": "in_use",
        "reuse_count": 4,
        "supported_use_cases": ["farm evidence", "reporting"],
        "verification_outputs": ["schema tests"],
        "maintenance_owner": "Technology Guild",
        "public_summary": "A public governed schema artifact.",
        "evidence_maturity": 3,
        "evidence_maturity_label": "field_validated",
        "metadata": {"source": "catalog"},
    }

    class Cursor:
        def __init__(self):
            self.sql = ""
            self.params = None

        def execute(self, sql, params=None):
            self.sql = " ".join(sql.split())
            self.params = params

        def fetchall(self):
            return [artifact]

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    report = generate_open_source_impact(conn)
    projection = re.search(
        r"SELECT (.*?) FROM v_public_open_source_impact_artifact", conn.cursor_value.sql
    )

    assert projection is not None
    assert [column.strip() for column in projection.group(1).split(",")] == expected_columns
    assert "ORDER BY reuse_count DESC, artifact_type, artifact_name" in conn.cursor_value.sql
    assert conn.cursor_value.params == ()
    assert report["location_id"] is None
    assert report["artifacts"] == [artifact]
    assert report["artifact_count"] == 1
    assert report["total_reuse_count"] == 4


def test_adoption_barrier_report_rejects_missing_location_before_database_access() -> None:
    conn = Mock()

    with pytest.raises(ValueError, match="adoption_barriers requires an explicit location_id"):
        generate_adoption_barriers(conn, None)

    conn.cursor.assert_not_called()


@pytest.mark.parametrize("location_id", [None, ""])
def test_perpetual_value_stress_rejects_missing_location_before_database_access(location_id) -> None:
    conn = Mock()

    with pytest.raises(ValueError, match="perpetual_value_stress requires an explicit location_id"):
        generate_perpetual_value_stress(conn, location_id)

    conn.cursor.assert_not_called()


def test_scaling_economics_network_scope_includes_network_targets() -> None:
    class Cursor:
        def __init__(self, queries):
            self.queries = queries

        def execute(self, query, params=None):
            self.queries.append((query, params))

        def fetchall(self):
            if len(self.queries) == 1:
                return [{"total_launch_cost_usd": 60000, "planned_farm_count": 2}]
            return [{"capital_required_usd": 120000, "target_farm_count": 4}]

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.queries = []

        def cursor(self, cursor_factory=None):
            return Cursor(self.queries)

    conn = Conn()
    report = generate_scaling_economics(conn, "all")

    assert report["scope"] == "network"
    assert report["location_id"] is None
    assert report["total_target_capital_usd"] == 120000
    assert report["target_farm_count"] == 4
    assert len(conn.queries) == 2
    assert "v_public_network_scaling_target" in conn.queries[1][0]


@pytest.mark.parametrize("location_id", ["", "x", "not-a-uuid", "all,location"])
def test_scaling_economics_rejects_malformed_location_before_database_access(location_id):
    conn = Mock()

    with pytest.raises(ValueError, match="scaling_economics requires a valid location_id"):
        generate_scaling_economics(conn, location_id)

    conn.cursor.assert_not_called()


@pytest.mark.parametrize("location_id", [None, "all"])
def test_scaling_economics_keeps_explicit_network_scope(location_id):
    class Cursor:
        def __init__(self, queries):
            self.queries = queries

        def execute(self, query, params=None):
            self.queries.append((query, params))

        def fetchall(self):
            return []

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.queries = []

        def cursor(self, cursor_factory=None):
            return Cursor(self.queries)

    conn = Conn()
    report = generate_scaling_economics(conn, location_id)

    assert report["scope"] == "network"
    assert report["location_id"] is None
    assert report["total_target_capital_usd"] == 0
    assert len(conn.queries) == 2
    assert "v_public_network_scaling_target" in conn.queries[1][0]


if __name__ == "__main__":
    test_open_source_capitalist_schema_defines_records_and_public_views()
    test_open_source_capitalist_seed_and_dashboards_exist()
    test_pilot_seed_has_claim_boundaries_and_no_unsupported_live_farm_claims()
    test_open_source_capitalist_agent_task_catalogue_and_validation()
    test_open_source_capitalist_agent_summarizes_public_safe_records()
    test_open_source_capitalist_report_generators_registered()
    test_open_source_capitalist_report_generators_public_safe()
