"""Integration coverage for scenario-linked strategy adaptation."""

import uuid

import pytest

from services.analytics import strategy_contingency, strategy_kernel
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002605"


def test_approved_scenario_choice_records_adaptation_lineage():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = plan_id = scenario_id = choice_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Contingency Test', 'collective') RETURNING id", (f"contingency-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Contingency Reviewer')", (PARTY_ID,))
            cur.execute("INSERT INTO forecast_scenario (name, scenario_type, status) VALUES ('Drought case', 'conservative', 'submitted') RETURNING id")
            scenario_id = str(cur.fetchone()[0])
        conn.commit()
        plan = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Contingency plan", "2026-01-01", "2026-12-31", PARTY_ID)
        plan_id = str(plan["id"])
        choice = strategy_contingency.create_choice(conn, plan_id, scenario_id, "Activate drought reserve", "Release drought-tolerant seed reserve", trigger_metric_key="rainfall_deficit", trigger_operator="gte", trigger_threshold=30, created_by_party_id=PARTY_ID)
        choice_id = str(choice["id"])
        strategy_contingency.approve_choice(conn, choice_id, PARTY_ID)
        event = strategy_contingency.record_adaptation(conn, choice_id, "activate", "Verified rainfall deficit crossed the approved threshold", decided_by_party_id=PARTY_ID)
        assert event["status"] == "approved"
        with conn.cursor() as cur:
            cur.execute("SELECT source_type, source_id, subject_id FROM strategy_evidence_link WHERE subject_id = %s::uuid", (choice_id,))
            evidence = cur.fetchone()
            assert evidence[0] == "scenario"
            assert str(evidence[1]) == scenario_id
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            if scenario_id:
                cur.execute("DELETE FROM forecast_scenario WHERE id = %s::uuid", (scenario_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
