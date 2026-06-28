"""Regenerative outcomes, governance, replication, and stewardship tests."""

from pathlib import Path

from services.agents.regenerator_agent import synthesize_regenerator
from services.agents.tasks import get_task, list_tasks, validate_output
from services.export.report_generator import (
    REPORT_GENERATORS,
    generate_adaptive_stewardship,
    generate_community_governance,
    generate_regenerative_outcomes,
    generate_replication_readiness,
)


SCHEMA = Path("schemas/postgres/039_regenerative_outcomes_and_stewardship.sql")
SEED = Path("schemas/seeds/040_regenerative_outcomes_and_stewardship.sql")
PILOT_SEED = Path("schemas/seeds/040_pilot_regenerative_outcomes.sql")


def test_regenerative_schema_defines_records_and_public_views() -> None:
    text = SCHEMA.read_text()
    for table in [
        "regenerative_outcome_summary",
        "community_governance_mechanism",
        "replication_readiness_assessment",
        "adaptive_stewardship_review",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text
    for view in [
        "v_public_regenerative_outcome_summary",
        "v_public_community_governance_mechanism",
        "v_public_replication_readiness_summary",
        "v_public_adaptive_stewardship_summary",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text
    assert "evidence_maturity >= 3" in text
    assert "farm_registry_record" in text
    assert "replication_status IN" in text
    assert "ready_for_replication" in text


def test_regenerative_seed_and_dashboards_exist() -> None:
    text = SEED.read_text()
    for metric in [
        "hectares_restored",
        "species_diversity_delta",
        "soil_carbon_delta_t_ha",
        "tree_survival_rate_pct",
        "community_governance_participation_pct",
        "replication_readiness_score",
        "adaptive_stewardship_action_completion_pct",
    ]:
        assert metric in text
    for sql in [
        "44_regenerative_outcomes.sql",
        "45_community_governance.sql",
        "46_replication_readiness.sql",
        "47_adaptive_stewardship.sql",
    ]:
        assert Path("dashboards/metabase/sql").joinpath(sql).exists()
    for dashboard in [
        "44_regenerative_outcomes.json",
        "45_community_governance.json",
        "46_replication_readiness.json",
        "47_adaptive_stewardship.json",
    ]:
        assert Path("dashboards/metabase").joinpath(dashboard).exists()
    assert "refresh_cron" in text


def test_pilot_seed_has_adelphi_examples_and_claim_boundaries() -> None:
    text = PILOT_SEED.read_text()
    assert "adelphi-regenerative-outcomes-2026-03" in text
    assert "adelphi-community-governance-2026-03" in text
    assert "conditional readiness, not guaranteed replication" in text
    assert "renewable energy remains planned not implemented" in text
    assert "Kokonut Venus Farm" not in text
    assert "100% women-based leadership" not in text
    assert "not unlimited scaling" in text


def test_regenerator_agent_task_catalogue_and_validation() -> None:
    assert "regenerator_synthesis" in list_tasks()
    task = get_task("regenerator_synthesis")
    assert task["writes"] == ["ai_summary:draft"]
    assert task["high_risk"] is False
    assert validate_output("regenerator_synthesis", {}) == ["Missing required output field: summary"]


def test_regenerator_agent_summarizes_public_safe_records() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchall(self):
            if self.calls == 1:
                return [{
                    "summary_name": "Adelphi outcomes",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "period_start": "2025-10-01",
                    "period_end": "2026-03-31",
                    "hectares_restored": 1.3838,
                    "latest_species_count": 14,
                    "species_diversity_delta": 0.42,
                    "soil_carbon_delta_t_ha": 1.6,
                    "trees_planted_count": 154,
                    "tree_survival_rate_pct": 91.5584,
                    "regenerative_score": 78,
                    "jobs_or_roles_supported_count": 4,
                    "training_hours": 36,
                    "beneficiary_count": 12,
                    "evidence_confidence": "moderate",
                    "public_summary": "Outcome summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 2:
                return [{
                    "mechanism_name": "Farm-to-DAO pathway",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "governance_level": "farm",
                    "decision_body": "Operators and Guilds",
                    "decision_method": "hybrid",
                    "quorum_rule": "operator review",
                    "voting_or_consensus_rights": "field notes",
                    "community_veto_rights": "defer claims",
                    "escalation_path": "Governance Guild",
                    "power_distribution_summary": "Split across operators, Guilds, and DAO.",
                    "participation_cadence": "monthly",
                    "public_summary": "Governance summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 3:
                return [{
                    "target_region": "Dominican Republic pilot cluster",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "assessment_date": "2026-03-31",
                    "farm_model": "blended",
                    "readiness_score": 6.5,
                    "ecological_prerequisites": ["water baseline"],
                    "cultural_governance_prerequisites": ["local-language reporting"],
                    "infrastructure_prerequisites": ["nursery"],
                    "barriers": ["renewable energy not implemented"],
                    "enablers": ["Adelphi evidence"],
                    "support_structures": ["operator playbook"],
                    "minimum_evidence_maturity": 3,
                    "replication_status": "conditional",
                    "public_summary": "Replication summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            return [{
                "stewardship_scope": "ecological",
                "location_id": "a0000000-0000-0000-0000-000000000001",
                "review_date": "2026-03-31",
                "review_period_start": "2026-01-01",
                "review_period_end": "2026-03-31",
                "review_cadence": "quarterly",
                "trigger_thresholds": ["tree survival below 85%"],
                "observed_triggers": ["Spanish reporting gap"],
                "corrective_actions": ["publish Spanish summaries"],
                "action_completion_pct": 50,
                "responsible_role": "Impact Guild",
                "funding_continuity_plan": "Use reinvestment after risk gates.",
                "next_review_date": "2026-06-30",
                "public_summary": "Stewardship summary.",
                "evidence_maturity": 3,
                "evidence_maturity_label": "Reviewed record",
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    summary = synthesize_regenerator(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["regenerative_outcome_count"] == 1
    assert summary["community_governance_count"] == 1
    assert summary["replication_readiness_count"] == 1
    assert summary["adaptive_stewardship_count"] == 1
    assert summary["total_hectares_restored"] == 1.3838
    assert "unlimited-scaling claim" in summary["safety_note"]


def test_regenerative_report_generators_registered() -> None:
    for report_type in [
        "regenerative_outcomes",
        "community_governance",
        "replication_readiness",
        "adaptive_stewardship",
    ]:
        assert report_type in REPORT_GENERATORS


def test_regenerative_report_generators_public_safe() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            return [{
                "public_summary": "Public summary",
                "hectares_restored": 1.3838,
                "replication_status": "conditional",
                "action_completion_pct": 50,
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    conn = Conn()
    outcomes = generate_regenerative_outcomes(conn, "a0000000-0000-0000-0000-000000000001")
    assert outcomes["report_type"] == "regenerative_outcomes"
    assert outcomes["total_hectares_restored"] == 1.3838
    assert "external certification" in outcomes["limitations"][1]
    assert generate_community_governance(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "community_governance"
    replication = generate_replication_readiness(conn, "a0000000-0000-0000-0000-000000000001")
    assert replication["report_type"] == "replication_readiness"
    assert "not an unlimited-scaling claim" in replication["limitations"][0]
    assert generate_adaptive_stewardship(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "adaptive_stewardship"


if __name__ == "__main__":
    test_regenerative_schema_defines_records_and_public_views()
    test_regenerative_seed_and_dashboards_exist()
    test_pilot_seed_has_adelphi_examples_and_claim_boundaries()
    test_regenerator_agent_task_catalogue_and_validation()
    test_regenerator_agent_summarizes_public_safe_records()
    test_regenerative_report_generators_registered()
    test_regenerative_report_generators_public_safe()
