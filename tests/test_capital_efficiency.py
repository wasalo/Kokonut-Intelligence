"""Capital efficiency, regenerative payback, governance throughput, and utility tests."""

from pathlib import Path

import pytest

from services.agents.capital_efficiency_agent import (
    CapitalEfficiencySynthesisAgent,
    synthesize_capital_efficiency,
)
from services.agents.tasks import get_task, list_tasks, validate_output
from services.export.report_generator import (
    REPORT_GENERATORS,
    generate_capital_efficiency,
    generate_capital_provider_utility,
    generate_governance_throughput,
)

SCHEMA = Path("schemas/postgres/036_capital_efficiency_and_utility.sql")
SEED = Path("schemas/seeds/037_capital_efficiency_and_utility.sql")
PILOT_SEED = Path("schemas/seeds/031_pilot_capital_efficiency.sql")


def test_capital_efficiency_schema_defines_records_and_public_views() -> None:
    text = SCHEMA.read_text()
    for table in [
        "capital_efficiency_scenario",
        "regenerative_efficiency_observation",
        "governance_throughput_observation",
        "capital_provider_utility_scenario",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text
    for view in [
        "v_public_capital_efficiency_summary",
        "v_public_regenerative_efficiency_summary",
        "v_public_governance_throughput_summary",
        "v_public_capital_provider_utility_summary",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text
    assert "evidence_maturity >= 3" in text
    assert "farm_registry_record" in text
    assert "utility_score BETWEEN 0 AND 10" in text


def test_capital_efficiency_seed_and_dashboards_exist() -> None:
    text = SEED.read_text()
    for metric in [
        "capital_efficiency_usd_per_output",
        "regenerative_cost_savings_pct",
        "practice_payback_months",
        "governance_decision_latency_days",
        "capital_leverage_ratio",
        "capital_provider_utility_score",
    ]:
        assert metric in text
    for sql in [
        "32_capital_efficiency.sql",
        "33_governance_throughput.sql",
        "34_capital_provider_utility.sql",
    ]:
        assert Path("dashboards/metabase/sql").joinpath(sql).exists()
    for dashboard in [
        "32_capital_efficiency.json",
        "33_governance_throughput.json",
        "34_capital_provider_utility.json",
    ]:
        assert Path("dashboards/metabase").joinpath(dashboard).exists()
    assert "refresh_cron" in text


def test_pilot_seed_has_efficiency_governance_and_utility_examples() -> None:
    text = PILOT_SEED.read_text()
    assert "Adelphi 2026 blended capital efficiency scenario" in text
    assert "bioinput_production" in text
    assert "governance_throughput_observation" in text
    assert "Adelphi sponsor-supported verification utility scenario" in text
    assert "not an offer of securities or guaranteed return" in text


def test_capital_efficiency_agent_task_catalogue_and_validation() -> None:
    assert "capital_efficiency_synthesis" in list_tasks()
    task = get_task("capital_efficiency_synthesis")
    assert task["writes"] == ["ai_summary:draft"]
    assert task["high_risk"] is False
    assert validate_output("capital_efficiency_synthesis", {}) == ["Missing required output field: summary"]


def test_capital_efficiency_agent_summarizes_public_safe_records() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchall(self):
            if self.calls == 1:
                return [{
                    "scenario_name": "Adelphi capital efficiency",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "scenario_type": "public_goods_loop",
                    "period_start": "2026-04-01",
                    "period_end": "2027-03-31",
                    "capital_deployed_usd": 24500,
                    "gross_output_value_usd": 24500,
                    "net_output_value_usd": 9200,
                    "public_goods_value_usd": 2450,
                    "capital_leverage_ratio": 1.1,
                    "public_summary": "Scenario summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 2:
                return [{
                    "practice_type": "bioinput_production",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "observation_date": "2026-03-31",
                    "baseline_cost_usd": 1200,
                    "observed_cost_usd": 420,
                    "cost_savings_pct": 65,
                    "incremental_output_value_usd": 850,
                    "implementation_cost_usd": 1800,
                    "payback_months": 13.2,
                    "public_summary": "Practice summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 3:
                return [{
                    "proposal_code": "P001",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "venue": "daohaus",
                    "proposal_type": "farm_funding",
                    "proposal_created_at": "2025-10-15T09:00:00+00:00",
                    "decision_at": "2025-10-20T14:00:00+00:00",
                    "executed_at": "2025-10-20T14:00:00+00:00",
                    "decision_latency_days": 5.21,
                    "execution_latency_days": 5.21,
                    "decision_result": "executed",
                    "public_summary": "Governance summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            return [{
                "scenario_name": "Sponsor utility",
                "location_id": "a0000000-0000-0000-0000-000000000001",
                "provider_type": "sponsor",
                "capital_amount_usd": 5000,
                "expected_financial_return_usd": 0,
                "expected_public_goods_value_usd": 2450,
                "expected_verification_outputs": 6,
                "expected_payback_months": None,
                "utility_score": 7.25,
                "public_summary": "Utility summary.",
                "limitations": ["No guaranteed return."],
                "evidence_maturity": 3,
                "evidence_maturity_label": "Reviewed record",
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    summary = synthesize_capital_efficiency(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["capital_efficiency_count"] == 1
    assert summary["regenerative_efficiency_count"] == 1
    assert summary["governance_throughput_count"] == 1
    assert summary["capital_provider_utility_count"] == 1
    assert summary["average_decision_latency_days"] == 5.21
    assert "securities-style return promises" in summary["safety_note"]


def test_capital_efficiency_worker_lineage_is_bounded_and_uses_public_views() -> None:
    class Cursor:
        def __init__(self):
            self.queries = []

        def execute(self, query, params=None):
            self.queries.append((query, params))

        def fetchall(self):
            return [
                {
                    "source_table": table,
                    "row_count": 51,
                    "record_ids": [
                        f"e0000000-0000-4000-8000-{index:012d}"
                        for index in range(1, 51)
                    ],
                }
                for table in CapitalEfficiencySynthesisAgent.source_reference_views
            ]

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    location_id = "a0000000-0000-0000-0000-000000000001"
    references = CapitalEfficiencySynthesisAgent().collect_source_references(
        conn, location_id
    )

    assert set(references) == set(CapitalEfficiencySynthesisAgent.source_reference_views)
    for table, reference in references.items():
        assert reference["row_count"] == 51
        assert len(reference["record_ids"]) == 50
        assert reference["truncated"] is True
        assert all(isinstance(record_id, str) for record_id in reference["record_ids"])
    query, params = conn.cursor_value.queries[0]
    for view_name in CapitalEfficiencySynthesisAgent.source_reference_views.values():
        assert view_name in query
    assert "WHERE location_id = %s" in query
    assert "row_number() OVER (PARTITION BY source_table ORDER BY id)" in query
    assert "numbered.ordinal <= 50" in query
    assert params == (location_id,) * 4


def test_capital_efficiency_report_generators_registered() -> None:
    for report_type in [
        "capital_efficiency",
        "governance_throughput",
        "capital_provider_utility",
    ]:
        assert report_type in REPORT_GENERATORS


def test_capital_efficiency_report_generators_public_safe() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            if self.calls == 1:
                return []
            return [{"public_summary": "Public summary", "decision_latency_days": 5.21}]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    conn = Conn()
    capital = generate_capital_efficiency(conn, "a0000000-0000-0000-0000-000000000001")
    governance = generate_governance_throughput(conn, "a0000000-0000-0000-0000-000000000001")
    utility = generate_capital_provider_utility(conn, "a0000000-0000-0000-0000-000000000001")
    assert capital["report_type"] == "capital_efficiency"
    assert governance["report_type"] == "governance_throughput"
    assert utility["report_type"] == "capital_provider_utility"
    assert "not guaranteed returns" in capital["limitations"][0]
    assert "not an offer of securities" in utility["limitations"][0]


@pytest.mark.parametrize("location_id", [None, ""])
def test_governance_throughput_requires_location_before_database_access(location_id) -> None:
    class NoDatabase:
        def cursor(self, **_kwargs):
            raise AssertionError("unscoped report must fail before opening a cursor")

    with pytest.raises(ValueError, match="governance_throughput requires an explicit location_id"):
        generate_governance_throughput(NoDatabase(), location_id)


def test_governance_throughput_keeps_selected_location_and_public_rows() -> None:
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
    report = generate_governance_throughput(conn, location_id)

    assert report["location_id"] == location_id
    assert "WHERE (location_id = %s OR location_id IS NULL)" in conn.cursor_value.query
    assert conn.cursor_value.params == (location_id, None, None, None, None)


if __name__ == "__main__":
    test_capital_efficiency_schema_defines_records_and_public_views()
    test_capital_efficiency_seed_and_dashboards_exist()
    test_pilot_seed_has_efficiency_governance_and_utility_examples()
    test_capital_efficiency_agent_task_catalogue_and_validation()
    test_capital_efficiency_agent_summarizes_public_safe_records()
    test_capital_efficiency_report_generators_registered()
    test_capital_efficiency_report_generators_public_safe()
