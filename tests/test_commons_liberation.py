"""Commons liberation, aligned capital, governance inclusion, and land stewardship tests."""

from pathlib import Path

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


if __name__ == "__main__":
    test_commons_schema_defines_records_and_public_views()
    test_commons_seed_and_dashboards_exist()
    test_pilot_seed_has_adelphi_examples_without_venus_claims()
    test_commons_agent_task_catalogue_and_validation()
    test_commons_agent_summarizes_public_safe_records()
    test_commons_report_generators_registered()
    test_commons_report_generators_public_safe()
