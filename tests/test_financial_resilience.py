"""Financial resilience, risk mitigation, scaling, and publication status tests."""

from pathlib import Path

from services.agents.resilience_agent import synthesize_resilience
from services.agents.tasks import get_task, list_tasks, validate_output
from services.export.report_generator import (
    REPORT_GENERATORS,
    generate_financial_sustainability,
    generate_green_paper_publication_status,
    generate_risk_mitigation,
    generate_scaling_roadmap,
)


SCHEMA = Path("schemas/postgres/035_financial_resilience_and_scaling.sql")
SEED = Path("schemas/seeds/036_financial_resilience_and_scaling.sql")
PILOT_SEED = Path("schemas/seeds/030_pilot_financial_resilience.sql")


def test_financial_resilience_schema_defines_records_and_views() -> None:
    text = SCHEMA.read_text()
    for table in [
        "financial_sustainability_plan",
        "risk_mitigation_register",
        "scaling_roadmap_milestone",
        "green_paper_publication_review",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text
    for view in [
        "v_public_financial_sustainability_summary",
        "v_public_risk_mitigation_summary",
        "v_public_scaling_roadmap_summary",
        "v_public_green_paper_publication_status",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text
    assert "grant_dependency_pct BETWEEN 0 AND 100" in text
    assert "farm_registry_record" in text


def test_financial_resilience_seed_and_dashboards_exist() -> None:
    text = SEED.read_text()
    for metric in [
        "grant_dependency_pct",
        "reinvestment_rate_pct",
        "public_goods_allocation_pct",
        "sustainability_runway_months",
        "risk_mitigation_coverage_pct",
        "scaling_readiness_score",
    ]:
        assert metric in text
    for sql in [
        "28_financial_sustainability.sql",
        "29_risk_mitigation.sql",
        "30_scaling_roadmap.sql",
        "31_green_paper_publication.sql",
    ]:
        assert Path("dashboards/metabase/sql").joinpath(sql).exists()
    for dashboard in [
        "28_financial_sustainability.json",
        "29_risk_mitigation.json",
        "30_scaling_roadmap.json",
        "31_green_paper_publication.json",
    ]:
        assert Path("dashboards/metabase").joinpath(dashboard).exists()
    assert "refresh_cron" in text


def test_pilot_seed_has_sustainability_risk_scaling_and_publication_examples() -> None:
    text = PILOT_SEED.read_text()
    assert "Adelphi 2026 transition to reinvested operations" in text
    assert "risk_mitigation_register" in text
    assert "Adelphi replication readiness" in text
    assert "green_paper_publication_review" in text
    assert "stakeholder_review" in text


def test_resilience_agent_task_catalogue_and_validation() -> None:
    assert "financial_resilience_synthesis" in list_tasks()
    task = get_task("financial_resilience_synthesis")
    assert task["writes"] == ["ai_summary:draft"]
    assert task["high_risk"] is False
    assert validate_output("financial_resilience_synthesis", {}) == ["Missing required output field: summary"]


def test_resilience_agent_summarizes_public_safe_records() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchall(self):
            if self.calls == 1:
                return [{
                    "plan_name": "Adelphi 2026 transition",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "farm_model": "blended",
                    "sustainability_status": "transitioning",
                    "grant_dependency_pct": 35,
                    "reinvestment_pct": 20,
                    "public_goods_allocation_pct": 10,
                    "runway_months": 9.5,
                    "projected_annual_revenue_usd": 24500,
                    "projected_annual_noi_usd": 9200,
                    "public_summary": "Transitioning toward reinvested operations.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 2:
                return [{
                    "risk_category": "climate",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "likelihood": "medium",
                    "impact_level": "high",
                    "residual_risk_level": "medium",
                    "owner_role": "Impact Guild",
                    "review_cadence": "quarterly",
                    "next_review_date": "2026-06-30",
                    "insurance_scope": "Annual crop insurance premium recorded.",
                    "oversight_mechanism": "Quarterly operator review.",
                    "technical_support_provider": "Dominican Agronomy Advisors",
                    "public_summary": "Climate risk has mitigation.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 3:
                return [{
                    "roadmap_name": "Adelphi replication readiness",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "target_region": "Dominican Republic",
                    "farm_model": "blended",
                    "planned_farm_count": 2,
                    "capital_required_usd": 35000,
                    "partner_requirements": ["buyers"],
                    "operational_dependencies": ["risk register"],
                    "risk_gates": ["runway >= 6 months"],
                    "target_date": "2026-12-31",
                    "milestone_status": "planned",
                    "public_summary": "Roadmap milestone.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            return [{
                "version": "1.0",
                "document_path": "docs/green-paper-v1.md",
                "review_status": "stakeholder_review",
                "review_owner": "Communications Guild",
                "target_publication_date": "2026-07-31",
                "open_question_count": 2,
                "approval_record_count": 1,
                "publication_cid": None,
                "publication_hash": None,
                "published_at": None,
                "public_summary": "Publication status.",
                "evidence_maturity": 3,
                "evidence_maturity_label": "Reviewed record",
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    summary = synthesize_resilience(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["financial_plan_count"] == 1
    assert summary["risk_register_count"] == 1
    assert summary["scaling_milestone_count"] == 1
    assert summary["total_scaling_capital_required_usd"] == 35000
    assert "private financial terms" in summary["safety_note"]


def test_resilience_report_generators_registered() -> None:
    for report_type in [
        "financial_sustainability",
        "risk_mitigation",
        "scaling_roadmap",
        "green_paper_publication_status",
    ]:
        assert report_type in REPORT_GENERATORS


def test_financial_resilience_report_generators_public_safe() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1
        def fetchone(self):
            return {"name": "Kokonut Adelphi"}
        def fetchall(self):
            return [{"public_summary": "Public summary", "capital_required_usd": 1000}]
        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    conn = Conn()
    assert generate_financial_sustainability(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "financial_sustainability"
    assert generate_risk_mitigation(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "risk_mitigation"
    assert generate_scaling_roadmap(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "scaling_roadmap"
    assert generate_green_paper_publication_status(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "green_paper_publication_status"


if __name__ == "__main__":
    test_financial_resilience_schema_defines_records_and_views()
    test_financial_resilience_seed_and_dashboards_exist()
    test_pilot_seed_has_sustainability_risk_scaling_and_publication_examples()
    test_resilience_agent_task_catalogue_and_validation()
    test_resilience_agent_summarizes_public_safe_records()
    test_resilience_report_generators_registered()
    test_financial_resilience_report_generators_public_safe()
