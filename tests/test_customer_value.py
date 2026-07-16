"""Integration coverage for customer value and value capture economics."""

import uuid

import pytest

from services.analytics import customer_value, strategy_kernel
from services.ingestion.base import get_db


def test_customer_value_bridge_exposes_surplus_and_capture():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = plan_id = hypothesis_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Value Test', 'collective') RETURNING id", (f"value-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
        conn.commit()
        plan = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Value plan", "2026-01-01", "2026-12-31")
        plan_id = str(plan["id"])
        hypothesis = customer_value.create_hypothesis(conn, plan_id, "Verified supply", "Unverified spot supply", "Reliable evidence-backed supply", "Buyers pay more for reliable verified supply")
        hypothesis_id = str(hypothesis["id"])
        customer_value.submit_hypothesis(conn, hypothesis_id)
        customer_value.record_observation(conn, hypothesis_id, willingness_to_pay=120, observed_price=90, conversion_rate=0.4, retention_rate=0.8, status="verified", evidence=[{"source":"buyer_interview"}])
        customer_value.record_capture_bridge(conn, hypothesis_id, "2026-01-01", "2026-03-31", customer_value_created=120, customer_value_captured=90, delivery_cost=30, acquisition_cost=10, contribution_margin=50, status="verified", evidence=[{"source":"ledger"}])
        with conn.cursor() as cur:
            cur.execute("SELECT customer_surplus, value_capture_pct, contribution_margin FROM v_strategy_customer_value_economics WHERE hypothesis_id = %s::uuid", (hypothesis_id,))
            surplus, capture, margin = cur.fetchone()
            assert float(surplus) == 30
            assert float(capture) == 75
            assert float(margin) == 50
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
