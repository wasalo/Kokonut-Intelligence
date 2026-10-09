"""Customer value, value capture, and competitive benchmark analytics."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_hypothesis(conn, strategy_plan_id: str, customer_need: str, baseline_alternative: str, proposed_outcome: str, hypothesis: str, *, position_id: Optional[str] = None, buyer_segment_id: Optional[str] = None, owner_party_id: Optional[str] = None, evidence: Optional[list[Any]] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_customer_value_hypothesis
            (strategy_plan_id, position_id, buyer_segment_id, customer_need, baseline_alternative,
             proposed_outcome, hypothesis, owner_party_id, evidence)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s::uuid, %s::jsonb)
            RETURNING *""", (strategy_plan_id, position_id, buyer_segment_id, customer_need,
                              baseline_alternative, proposed_outcome, hypothesis, owner_party_id,
                              json.dumps(evidence or [])))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def submit_hypothesis(conn, hypothesis_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("UPDATE strategy_customer_value_hypothesis SET status = 'submitted', updated_at = NOW() WHERE id = %s::uuid AND status = 'draft' RETURNING *", (hypothesis_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only draft customer-value hypotheses can be submitted")
        conn.commit()
        return _clean(row)


def record_observation(conn, hypothesis_id: str, *, customer_count: Optional[int] = None, outcome_score: Optional[float] = None, willingness_to_pay: Optional[float] = None, observed_price: Optional[float] = None, conversion_rate: Optional[float] = None, retention_rate: Optional[float] = None, switching_cost: Optional[float] = None, evidence: Optional[list[Any]] = None, confidence: str = "moderate", status: str = "draft", created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_customer_value_observation
            (hypothesis_id, customer_count, outcome_score, willingness_to_pay, observed_price,
             conversion_rate, retention_rate, switching_cost, evidence, confidence, status, created_by_party_id)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::uuid)
            RETURNING *""", (hypothesis_id, customer_count, outcome_score, willingness_to_pay,
                              observed_price, conversion_rate, retention_rate, switching_cost,
                              json.dumps(evidence or []), confidence, status,
                              created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def record_capture_bridge(conn, hypothesis_id: str, period_start: str, period_end: str, *, customer_value_created: Optional[float] = None, customer_value_captured: Optional[float] = None, delivery_cost: Optional[float] = None, acquisition_cost: Optional[float] = None, stakeholder_value_distribution: Optional[dict[str, Any]] = None, contribution_margin: Optional[float] = None, confidence: str = "moderate", status: str = "draft", evidence: Optional[list[Any]] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_value_capture_bridge
            (hypothesis_id, period_start, period_end, customer_value_created, customer_value_captured,
             delivery_cost, acquisition_cost, stakeholder_value_distribution, contribution_margin,
             confidence, status, evidence)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb)
            RETURNING *""", (hypothesis_id, period_start, period_end, customer_value_created,
                              customer_value_captured, delivery_cost, acquisition_cost,
                              json.dumps(stakeholder_value_distribution or {}),
                              contribution_margin, confidence, status,
                              json.dumps(evidence or [])))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def record_benchmark(conn, strategy_plan_id: str, benchmark_type: str, subject_type: str, subject_name: str, measure_name: str, unit: str, value: float, observed_at: str, *, buyer_segment_id: Optional[str] = None, currency: Optional[str] = None, source_ref: Optional[str] = None, confidence: str = "moderate", status: str = "draft", evidence: Optional[list[Any]] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_competitive_benchmark
            (strategy_plan_id, buyer_segment_id, benchmark_type, subject_type, subject_name,
             measure_name, unit, value, currency, observed_at, source_ref, confidence, status, evidence)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING *""", (strategy_plan_id, buyer_segment_id, benchmark_type, subject_type,
                              subject_name, measure_name, unit, value, currency, observed_at,
                              source_ref, confidence, status, json.dumps(evidence or [])))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def compare_benchmarks(conn, strategy_plan_id: str, benchmark_type: str, measure_name: str) -> list[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT * FROM strategy_competitive_benchmark
            WHERE strategy_plan_id = %s::uuid AND benchmark_type = %s AND measure_name = %s
              AND status IN ('submitted', 'verified', 'published')
            ORDER BY observed_at DESC, subject_type, subject_name""", (strategy_plan_id, benchmark_type, measure_name))
        return [_clean(row) for row in cur.fetchall()]
