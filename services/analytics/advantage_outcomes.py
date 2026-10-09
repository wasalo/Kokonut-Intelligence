"""Realized performance and durability analytics for strategic advantages."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def record_outcome(conn, advantage_id: str, outcome_type: str, period_start: str, period_end: str, *, baseline_value: Optional[float] = None, target_value: Optional[float] = None, actual_value: Optional[float] = None, comparator_type: Optional[str] = None, comparator_value: Optional[float] = None, unit: Optional[str] = None, objective_id: Optional[str] = None, objective_kpi_id: Optional[str] = None, attribution_confidence: str = "moderate", status: str = "draft", evidence: Optional[list[Any]] = None, observed_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_advantage_outcome
            (advantage_id, objective_id, objective_kpi_id, outcome_type, period_start, period_end,
             baseline_value, target_value, actual_value, comparator_type, comparator_value, unit,
             attribution_confidence, status, evidence, observed_by_party_id)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::uuid)
            RETURNING *""", (advantage_id, objective_id, objective_kpi_id, outcome_type, period_start,
                              period_end, baseline_value, target_value, actual_value, comparator_type,
                              comparator_value, unit, attribution_confidence, status,
                              json.dumps(evidence or []), observed_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def record_renewal_event(conn, advantage_id: str, event_type: str, event_date: str, description: str, *, investment_id: Optional[str] = None, expected_effect: Optional[str] = None, observed_effect: Optional[str] = None, status: str = "proposed", evidence: Optional[list[Any]] = None, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_advantage_renewal_event
            (advantage_id, investment_id, event_type, event_date, description, expected_effect,
             observed_effect, status, evidence, created_by_party_id)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::uuid)
            RETURNING *""", (advantage_id, investment_id, event_type, event_date, description,
                              expected_effect, observed_effect, status, json.dumps(evidence or []),
                              created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def performance(conn, strategy_plan_id: str) -> list[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_strategy_advantage_performance WHERE strategy_plan_id = %s::uuid ORDER BY defensibility_score DESC NULLS LAST, name", (strategy_plan_id,))
        return [_clean(row) for row in cur.fetchall()]
