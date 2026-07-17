"""Integration coverage for posterior-driven reviews and solution gates."""

import uuid

import pytest

from services.decision import odds_engine, sequential_evidence, sequential_integration
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002713"


def test_solution_gate_rejects_unlinked_or_invalid_evidence_before_database_access():
    with pytest.raises(ValueError, match="applied evidence"):
        sequential_integration.evaluate_solution_gate_from_hypothesis(
            None, "gate", "hypothesis", "reviewer", minimum_posterior=0.8, evidence=[{}]
        )
    with pytest.raises(ValueError, match="minimum posterior"):
        sequential_integration.evaluate_solution_gate_from_hypothesis(
            None, "gate", "hypothesis", "reviewer", minimum_posterior=1.1,
            evidence=[{"evidence_event_id": str(uuid.uuid4())}]
        )


def test_posterior_can_create_strategy_review_task():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    hypothesis_id = plan_id = org_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Sequential Review Test', 'collective') RETURNING id", (f"seq-review-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Sequential Reviewer')", (PARTY_ID,))
        conn.commit()
        from services.analytics import strategy_kernel
        plan = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Sequential review plan", "2026-01-01", "2026-12-31")
        plan_id = str(plan["id"])
        hypothesis = sequential_evidence.create_hypothesis(conn, "strategy_plan", plan_id, "Risk event will occur", "Risk event will not occur", 0.2, created_by_party_id=PARTY_ID)
        hypothesis_id = str(hypothesis["id"])
        event = sequential_evidence.record_evidence(conn, hypothesis_id, "forecast", "risk_signal", "2026-07-01T00:00:00+00:00", source_ref="forecast-1", likelihood_hypothesis=0.9, likelihood_alternative=0.1, created_by_party_id=PARTY_ID)
        odds_engine.apply_evidence(conn, hypothesis_id, str(event["id"]), evaluated_by_party_id=PARTY_ID)
        evaluation = sequential_integration.evaluate_hypothesis(conn, hypothesis_id, action_threshold=0.5, evaluated_by_party_id=PARTY_ID)
        assert evaluation["action"] == "act"
        assert evaluation["review_task"]["review_type"] == "assumption_failure"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if hypothesis_id:
                cur.execute("DELETE FROM decision_hypothesis WHERE id = %s::uuid", (hypothesis_id,))
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
