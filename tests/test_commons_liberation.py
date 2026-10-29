"""Commons liberation, aligned capital, governance inclusion, and land stewardship tests."""

import re
from datetime import date
from pathlib import Path

import pytest

from services.agents.commons_agent import synthesize_commons
from services.agents.tasks import get_task, list_tasks, validate_output
from services.export.report_generator import (
    REPORT_GENERATORS,
    generate_capital_alignment,
    generate_governance_inclusion,
    generate_land_stewardship,
    generate_time_liberation,
)

SCHEMA = Path("schemas/postgres/037_commons_liberation_and_stewardship.sql")
SEED = Path("schemas/seeds/038_commons_liberation_and_stewardship.sql")
PILOT_SEED = Path("schemas/seeds/038_pilot_commons_liberation.sql")


def test_commons_schema_defines_records_and_public_views() -> None:
    text = SCHEMA.read_text()
    for table in [
        "time_liberation_observation",
        "capital_alignment_assessment",
        "governance_inclusion_observation",
        "land_stewardship_commitment",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text
    for view in [
        "v_public_time_liberation_summary",
        "v_public_capital_alignment_summary",
        "v_public_governance_inclusion_summary",
        "v_public_land_stewardship_summary",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text
    assert "evidence_maturity >= 3" in text
    assert "farm_registry_record" in text
    assert "pseudonymous_participation_enabled" in text


def test_commons_seed_and_dashboards_exist() -> None:
    text = SEED.read_text()
    for metric in [
        "operator_time_reclaimed_hours",
        "field_reporting_burden_reduction_pct",
        "aligned_capital_share_pct",
        "extractive_capital_risk_count",
        "governance_representation_coverage_pct",
        "pseudonymous_participation_enabled",
        "land_stewardship_commitment_count",
        "landlord_dependency_risk_level",
    ]:
        assert metric in text
    for sql in [
        "35_time_liberation.sql",
        "36_capital_alignment.sql",
        "37_governance_inclusion.sql",
        "38_land_stewardship.sql",
    ]:
        assert Path("dashboards/metabase/sql").joinpath(sql).exists()
    for dashboard in [
        "35_time_liberation.json",
        "36_capital_alignment.json",
        "37_governance_inclusion.json",
        "38_land_stewardship.json",
    ]:
        assert Path("dashboards/metabase").joinpath(dashboard).exists()
    assert "refresh_cron" in text


def test_pilot_seed_has_adelphi_examples_without_venus_claims() -> None:
    text = PILOT_SEED.read_text()
    assert "Adelphi estimates three hours" in text
    assert "capital_alignment_assessment" in text
    assert "governance_inclusion_observation" in text
    assert "land_stewardship_commitment" in text
    assert "unsupported_claims_excluded" in text
    assert "Kokonut Venus Farm" in text
    assert "100% women-based leadership" not in text


def test_commons_agent_task_catalogue_and_validation() -> None:
    assert "commons_liberation_synthesis" in list_tasks()
    task = get_task("commons_liberation_synthesis")
    assert task["writes"] == ["ai_summary:draft"]
    assert task["high_risk"] is False
    assert validate_output("commons_liberation_synthesis", {}) == ["Missing required output field: summary"]


def test_commons_agent_summarizes_public_safe_records() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchall(self):
            if self.calls == 1:
                return [{
                    "workflow_area": "monthly_operator_reporting",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "observation_date": "2026-03-31",
                    "baseline_hours": 8,
                    "observed_hours": 5,
                    "hours_reclaimed": 3,
                    "burden_reduction_pct": 37.5,
                    "automation_or_agent_used": True,
                    "automation_type": "ai_summary",
                    "beneficiary_group": "farm_operator",
                    "public_summary": "Time summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 2:
                return [{
                    "provider_name": "DAO funders",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "assessment_date": "2026-03-31",
                    "provider_type": "public_goods_funder",
                    "alignment_status": "aligned",
                    "extractive_risk_level": "low",
                    "community_control_terms": "Community control.",
                    "profit_extraction_limits": "No guaranteed return.",
                    "commons_reinvestment_commitment_pct": 10,
                    "public_summary": "Capital summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 3:
                return [{
                    "governance_body": "Impact Guild",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "observation_date": "2026-03-31",
                    "inclusion_scope": "guild",
                    "represented_groups": ["farm_operator"],
                    "missing_groups": ["local-language reviewer"],
                    "pseudonymous_participation_enabled": True,
                    "marginalized_voice_count": 2,
                    "total_participant_count": 4,
                    "representation_coverage_pct": 75,
                    "public_summary": "Inclusion summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            return [{
                "stewardship_model": "family_stewardship_with_public_goods",
                "location_id": "a0000000-0000-0000-0000-000000000001",
                "commitment_date": "2026-03-31",
                "landlord_dependency_risk": "low",
                "anti_speculation_terms": "No speculative claim.",
                "community_benefit_rights": "Public goods.",
                "commons_transition_path": "Requires governed evidence.",
                "public_summary": "Land summary.",
                "evidence_maturity": 3,
                "evidence_maturity_label": "Reviewed record",
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    summary = synthesize_commons(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["time_liberation_count"] == 1
    assert summary["capital_alignment_count"] == 1
    assert summary["governance_inclusion_count"] == 1
    assert summary["land_stewardship_count"] == 1
    assert summary["total_hours_reclaimed"] == 3
    assert summary["pseudonymous_participation_enabled_count"] == 1
    assert "unsupported land-transfer claims" in summary["safety_note"]


def test_commons_report_generators_registered() -> None:
    for report_type in [
        "time_liberation",
        "capital_alignment",
        "governance_inclusion",
        "land_stewardship",
    ]:
        assert report_type in REPORT_GENERATORS


def test_commons_report_generators_public_safe() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            return [{
                "public_summary": "Public summary",
                "hours_reclaimed": 3,
                "extractive_risk_level": "low",
                "pseudonymous_participation_enabled": True,
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    conn = Conn()
    assert generate_time_liberation(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "time_liberation"
    assert generate_capital_alignment(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "capital_alignment"
    assert generate_governance_inclusion(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "governance_inclusion"
    land = generate_land_stewardship(conn, "a0000000-0000-0000-0000-000000000001")
    assert land["report_type"] == "land_stewardship"
    assert "not legal opinions" in land["limitations"][0]


def test_time_liberation_projection_preserves_complete_view_payload() -> None:
    location_id = "a0000000-0000-0000-0000-000000000001"
    period_start = "2026-01-01"
    period_end = "2026-03-31"
    source_row = {
        "id": "b0000000-0000-0000-0000-000000000001",
        "location_id": location_id,
        "farm_id": "c0000000-0000-0000-0000-000000000001",
        "observation_date": date(2026, 3, 31),
        "workflow_area": "monthly_operator_reporting",
        "baseline_hours": 8.0,
        "observed_hours": 5.25,
        "hours_reclaimed": 2.75,
        "burden_reduction_pct": 34.375,
        "automation_or_agent_used": True,
        "automation_type": "reviewed_assistant",
        "beneficiary_group": "farm_operator",
        "public_summary": "Reviewed workflow outcome.",
        "evidence_maturity": 3,
        "evidence_maturity_label": "Reviewed record",
        "metadata": {"source": "reviewed", "labels": ["quarterly"]},
    }
    expected_columns = (
        "id, location_id, farm_id, observation_date, workflow_area, baseline_hours, observed_hours, "
        "hours_reclaimed, burden_reduction_pct, automation_or_agent_used, automation_type, "
        "beneficiary_group, public_summary, evidence_maturity, evidence_maturity_label, metadata"
    )

    class Cursor:
        query = None
        params = None

        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            return [source_row]

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    report = generate_time_liberation(conn, location_id, period_start, period_end)

    normalized_query = re.sub(r"\s+", " ", conn.cursor_value.query).strip()
    assert normalized_query == (
        f"SELECT {expected_columns} FROM v_public_time_liberation_summary "
        "WHERE location_id = %s AND (%s::date IS NULL OR observation_date >= %s::date) "
        "AND (%s::date IS NULL OR observation_date <= %s::date) "
        "ORDER BY observation_date DESC, workflow_area"
    )
    assert conn.cursor_value.params == (location_id, period_start, period_start, period_end, period_end)
    assert report["report_type"] == "time_liberation"
    assert report["location_name"] == "Kokonut Adelphi"
    assert report["observations"] == [
        {**source_row, "observation_date": "2026-03-31"}
    ]
    assert report["total_hours_reclaimed"] == 2.75


def test_capital_alignment_projection_preserves_payload_and_extractive_risk_count() -> None:
    location_id = "a0000000-0000-0000-0000-000000000001"
    period_start = "2026-01-01"
    period_end = "2026-03-31"
    source_row = {
        "id": "b0000000-0000-0000-0000-000000000001",
        "location_id": location_id,
        "farm_id": "c0000000-0000-0000-0000-000000000001",
        "capital_source_id": "d0000000-0000-0000-0000-000000000001",
        "assessment_date": date(2026, 3, 31),
        "provider_name": "Kokonut Network",
        "provider_type": "community_fund",
        "alignment_status": "aligned",
        "extractive_risk_level": "high",
        "community_control_terms": "Community retains veto rights.",
        "exit_pressure_risk": "low",
        "profit_extraction_limits": "Returns capped by policy.",
        "commons_reinvestment_commitment_pct": 70.0,
        "public_summary": "Reviewed capital alignment assessment.",
        "evidence_maturity": 3,
        "evidence_maturity_label": "Reviewed record",
        "metadata": {"source": "reviewed", "cycle": "Q1"},
    }
    low_risk_row = {
        **source_row,
        "id": "b0000000-0000-0000-0000-000000000002",
        "assessment_date": date(2026, 2, 28),
        "provider_name": "Community revolving fund",
        "provider_type": "community_fund",
        "extractive_risk_level": "low",
    }
    source_rows = [source_row, low_risk_row]
    columns = (
        "id, location_id, farm_id, capital_source_id, assessment_date, provider_name, provider_type, "
        "alignment_status, extractive_risk_level, community_control_terms, exit_pressure_risk, "
        "profit_extraction_limits, commons_reinvestment_commitment_pct, public_summary, "
        "evidence_maturity, evidence_maturity_label, metadata"
    )

    class Cursor:
        def __init__(self):
            self.executed = []

        def execute(self, query, params):
            self.executed.append((query, params))

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            return source_rows

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    report = generate_capital_alignment(conn, location_id, period_start, period_end)
    query, params = conn.cursor_value.executed[1]

    assert re.sub(r"\s+", " ", query).strip() == (
        f"SELECT {columns} FROM v_public_capital_alignment_summary "
        "WHERE location_id = %s AND (%s::date IS NULL OR assessment_date >= %s::date) "
        "AND (%s::date IS NULL OR assessment_date <= %s::date) "
        "ORDER BY assessment_date DESC, provider_type"
    )
    assert params == (location_id, period_start, period_start, period_end, period_end)
    assert report["report_type"] == "capital_alignment"
    assert report["location_name"] == "Kokonut Adelphi"
    assert report["assessments"] == [
        {**row, "assessment_date": row["assessment_date"].isoformat()}
        for row in source_rows
    ]
    assert report["high_or_critical_extractive_risk_count"] == 1


@pytest.mark.parametrize("location_id", [None, ""])
def test_governance_inclusion_requires_location_before_database_access(location_id) -> None:
    class NoDatabase:
        def cursor(self, **_kwargs):
            raise AssertionError("unscoped report must fail before opening a cursor")

    with pytest.raises(ValueError, match="governance_inclusion requires an explicit location_id"):
        generate_governance_inclusion(NoDatabase(), location_id)


def test_governance_inclusion_keeps_selected_location_and_global_rows() -> None:
    class Cursor:
        query = None
        params = None

        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchall(self):
            return []

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    location_id = "a0000000-0000-0000-0000-000000000001"

    report = generate_governance_inclusion(conn, location_id)

    assert report["location_id"] == location_id
    assert "WHERE (location_id = %s OR location_id IS NULL)" in conn.cursor_value.query
    assert conn.cursor_value.params == (location_id, None, None, None, None)


if __name__ == "__main__":
    test_commons_schema_defines_records_and_public_views()
    test_commons_seed_and_dashboards_exist()
    test_pilot_seed_has_adelphi_examples_without_venus_claims()
    test_commons_agent_task_catalogue_and_validation()
    test_commons_agent_summarizes_public_safe_records()
    test_commons_report_generators_registered()
    test_commons_report_generators_public_safe()
