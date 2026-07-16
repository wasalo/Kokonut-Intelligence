"""Tests for composite strategic investment scoring."""

import uuid

import pytest

from services.analytics import strategy_kernel
from services.ingestion.base import get_db
from services.planning import strategy_allocation


PARTY_ID = "b0000000-0000-0000-0000-000000002603"


def test_composite_score_preserves_dimension_scores():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    plan_id = None
    investment_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Allocation Test', 'collective') RETURNING id", (f"allocation-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Allocation Reviewer')", (PARTY_ID,))
        conn.commit()
        plan = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Allocation plan", "2026-01-01", "2026-12-31", PARTY_ID)
        plan_id = str(plan["id"])
        strategy_allocation.create_policy(conn, plan_id)
        investment = strategy_allocation.create_investment_case(conn, plan_id, "Field evidence infrastructure", created_by_party_id=PARTY_ID, financial_score=70, ecological_score=90, social_score=80, governance_score=95, resilience_score=85, strategic_fit_score=100, risk_score=10)
        investment_id = str(investment["id"])
        scored = strategy_allocation.score_investment(conn, investment_id)
        assert scored["status"] == "scored"
        assert scored["composite_score"] > 70
        assert scored["ecological_score"] == 90
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()


def test_allocation_weights_must_sum_to_one():
    with pytest.raises(ValueError, match="sum to 1"):
        strategy_allocation.create_policy(None, str(uuid.uuid4()), financial_weight=1.0)
