"""Financial resilience, risk mitigation, scaling, and publication status tests."""

import re
from pathlib import Path

import pytest

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
                "document_path": "docs/green-paper.md",
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
    assert generate_green_paper_publication_status(conn, None)["report_type"] == "green_paper_publication_status"


def test_risk_mitigation_uses_exact_projection_and_preserves_scope_payload() -> None:
    columns = [
        "id", "location_id", "farm_id", "risk_category", "risk_description",
        "likelihood", "impact_level", "mitigation_strategy", "insurance_scope",
        "oversight_mechanism", "technical_support_provider", "owner_role",
        "review_cadence", "residual_risk_level", "review_date", "next_review_date",
        "public_summary", "evidence_maturity", "evidence_maturity_label", "metadata",
    ]
    row = {
        "id": "00000000-0000-4000-8000-000000000001",
        "location_id": "a0000000-0000-0000-0000-000000000001",
        "farm_id": "00000000-0000-4000-8000-000000000002",
        "risk_category": "water",
        "risk_description": "Seasonal water shortage",
        "likelihood": "medium",
        "impact_level": "high",
        "mitigation_strategy": "Maintain a reviewed storage buffer",
        "insurance_scope": "Crop and infrastructure coverage",
        "oversight_mechanism": "Quarterly review",
        "technical_support_provider": "Regional agronomist",
        "owner_role": "Farm operator",
        "review_cadence": "quarterly",
        "residual_risk_level": "low",
        "review_date": "2026-09-30",
        "next_review_date": "2026-12-30",
        "public_summary": "A reviewed water resilience measure.",
        "evidence_maturity": 4,
        "evidence_maturity_label": "Verified",
        "metadata": {"reviewed": True},
    }

    class Cursor:
        def __init__(self):
            self.calls = []
            self.current_query = ""

        def execute(self, query, params=None):
            self.current_query = " ".join(query.split())
            self.calls.append((self.current_query, params))

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            return [row] if "v_public_risk_mitigation_summary" in self.current_query else []

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    location_id = row["location_id"]
    period_start, period_end = "2026-07-01", "2026-12-31"
    report = generate_risk_mitigation(conn, location_id, period_start, period_end)

    query, params = conn.cursor_value.calls[1]
    projection = re.search(r"SELECT (.*?) FROM v_public_risk_mitigation_summary", query)
    assert projection is not None
    assert [column.strip() for column in projection.group(1).split(",")] == columns
    assert "WHERE location_id = %s" in query
    assert "ORDER BY next_review_date NULLS LAST, risk_category" in query
    assert params == (location_id, period_start, period_start, period_end, period_end)
    assert report["location_id"] == location_id
    assert report["location_name"] == "Kokonut Adelphi"
    assert report["risks"] == [row]


def test_financial_sustainability_uses_exact_public_projection_and_preserves_scope_payload() -> None:
    columns = [
        "id",
        "location_id",
        "farm_id",
        "plan_name",
        "farm_model",
        "plan_period_start",
        "plan_period_end",
        "revenue_streams",
        "grant_dependency_pct",
        "reinvestment_pct",
        "public_goods_allocation_pct",
        "break_even_month",
        "runway_months",
        "projected_annual_revenue_usd",
        "projected_annual_operating_cost_usd",
        "projected_annual_noi_usd",
        "sustainability_status",
        "public_summary",
        "evidence_maturity",
        "evidence_maturity_label",
        "metadata",
    ]
    location_id = "a0000000-0000-0000-0000-000000000001"
    plan = {
        "id": "00000000-0000-4000-8000-000000000001",
        "location_id": location_id,
        "farm_id": "00000000-0000-4000-8000-000000000002",
        "plan_name": "Adelphi transition plan",
        "farm_model": "agroforestry",
        "plan_period_start": "2026-01-01",
        "plan_period_end": "2026-12-31",
        "revenue_streams": ["produce", "training"],
        "grant_dependency_pct": 20.0,
        "reinvestment_pct": 35.0,
        "public_goods_allocation_pct": 10.0,
        "break_even_month": 8,
        "runway_months": 18.0,
        "projected_annual_revenue_usd": 125000.0,
        "projected_annual_operating_cost_usd": 90000.0,
        "projected_annual_noi_usd": 35000.0,
        "sustainability_status": "transitioning",
        "public_summary": "Reviewed public financial sustainability plan.",
        "evidence_maturity": 4,
        "evidence_maturity_label": "Verified",
        "metadata": {"reviewed": True},
    }

    class Cursor:
        def __init__(self):
            self.calls = []
            self.current_query = ""

        def execute(self, query, params=None):
            self.current_query = " ".join(query.split())
            self.calls.append((self.current_query, params))

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            return [plan] if "v_public_financial_sustainability_summary" in self.current_query else []

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    report = generate_financial_sustainability(
        conn, location_id, period_start="2026-01-01", period_end="2026-12-31"
    )

    query, params = conn.cursor_value.calls[1]
    projection = re.search(
        r"SELECT (.*?) FROM v_public_financial_sustainability_summary", query
    )
    assert projection is not None
    assert [column.strip() for column in projection.group(1).split(",")] == columns
    assert "WHERE location_id = %s" in query
    assert "plan_period_start >= %s::date" in query
    assert "plan_period_end IS NULL OR plan_period_end <= %s::date" in query
    assert "ORDER BY plan_period_start DESC, plan_name" in query
    assert params == (location_id, "2026-01-01", "2026-01-01", "2026-12-31", "2026-12-31")
    assert report["location_id"] == location_id
    assert report["location_name"] == "Kokonut Adelphi"
    assert report["plans"] == [plan]


def test_green_paper_status_projects_public_view_columns_and_preserves_rows() -> None:
    columns = [
        "id",
        "version",
        "document_path",
        "review_status",
        "review_owner",
        "target_publication_date",
        "open_question_count",
        "approval_record_count",
        "publication_cid",
        "publication_hash",
        "published_at",
        "public_summary",
        "evidence_maturity",
        "evidence_maturity_label",
    ]
    row = {
        "id": "00000000-0000-4000-8000-000000000001",
        "version": "1.0",
        "document_path": "docs/green-paper.md",
        "review_status": "published",
        "review_owner": "Communications Guild",
        "target_publication_date": "2026-07-31",
        "open_question_count": 0,
        "approval_record_count": 3,
        "publication_cid": "bafybeigdyrzt",
        "publication_hash": "a" * 64,
        "published_at": "2026-07-29T12:00:00+00:00",
        "public_summary": "Reviewed public summary.",
        "evidence_maturity": 4,
        "evidence_maturity_label": "Published",
    }

    class Cursor:
        query = None

        def execute(self, query, params=None):
            self.query = " ".join(query.split())
            assert params is None

        def fetchall(self):
            return [row]

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()

    report = generate_green_paper_publication_status(conn, None)

    projection = conn.cursor_value.query.split(" FROM ", maxsplit=1)[0]
    assert projection == "SELECT " + ", ".join(columns)
    assert "FROM v_public_green_paper_publication_status ORDER BY target_publication_date DESC, version DESC" in conn.cursor_value.query
    assert report["reviews"] == [row]


@pytest.mark.parametrize("location_id", [None, ""])
def test_scaling_roadmap_requires_location_before_database_access(location_id) -> None:
    class NoDatabase:
        def cursor(self, **_kwargs):
            raise AssertionError("unscoped report must fail before opening a cursor")

    with pytest.raises(ValueError, match="scaling_roadmap requires an explicit location_id"):
        generate_scaling_roadmap(NoDatabase(), location_id)


def test_scaling_roadmap_filters_location_and_keeps_reviewed_global_rows() -> None:
    columns = [
        "id", "roadmap_name", "location_id", "target_region", "farm_model",
        "planned_farm_count", "capital_required_usd", "partner_requirements",
        "operational_dependencies", "risk_gates", "target_date", "milestone_status",
        "public_summary", "evidence_maturity", "evidence_maturity_label", "metadata",
    ]
    rows = [
        {
            "id": "00000000-0000-4000-8000-000000000001",
            "roadmap_name": "Adelphi expansion",
            "location_id": "a0000000-0000-0000-0000-000000000001",
            "target_region": "Monte Plata",
            "farm_model": "agroforestry",
            "planned_farm_count": 2,
            "capital_required_usd": 1000,
            "partner_requirements": ["nursery"],
            "operational_dependencies": ["water access"],
            "risk_gates": ["site review"],
            "target_date": "2027-01-01",
            "milestone_status": "planned",
            "public_summary": "A location-owned expansion milestone.",
            "evidence_maturity": 4,
            "evidence_maturity_label": "Verified",
            "metadata": {},
        },
        {
            "id": "00000000-0000-4000-8000-000000000002",
            "roadmap_name": "Network nursery",
            "location_id": None,
            "target_region": "Dominican Republic",
            "farm_model": "nursery",
            "planned_farm_count": 1,
            "capital_required_usd": 500,
            "partner_requirements": [],
            "operational_dependencies": [],
            "risk_gates": [],
            "target_date": "2027-02-01",
            "milestone_status": "planned",
            "public_summary": "A shared network milestone.",
            "evidence_maturity": 3,
            "evidence_maturity_label": "Substantiated",
            "metadata": {},
        },
    ]

    class Cursor:
        def __init__(self):
            self.query = None
            self.params = None

        def execute(self, query, params):
            self.query = " ".join(query.split())
            self.params = params

        def fetchall(self):
            return rows

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    location_id = "a0000000-0000-0000-0000-000000000001"
    report = generate_scaling_roadmap(conn, location_id)

    projection = re.search(r"SELECT (.*?) FROM v_public_scaling_roadmap_summary", conn.cursor_value.query)
    assert projection is not None
    assert [column.strip() for column in projection.group(1).split(",")] == columns
    assert report["location_id"] == location_id
    assert "WHERE (location_id = %s OR location_id IS NULL)" in conn.cursor_value.query
    assert conn.cursor_value.params == (location_id, None, None, None, None)
    assert report["total_capital_required_usd"] == 1500
    assert report["milestones"] == rows


if __name__ == "__main__":
    test_financial_resilience_schema_defines_records_and_views()
    test_financial_resilience_seed_and_dashboards_exist()
    test_pilot_seed_has_sustainability_risk_scaling_and_publication_examples()
    test_resilience_agent_task_catalogue_and_validation()
    test_resilience_agent_summarizes_public_safe_records()
    test_resilience_report_generators_registered()
    test_financial_resilience_report_generators_public_safe()
