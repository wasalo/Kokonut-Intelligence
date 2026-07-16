"""Scenario-linked contingency choices and human adaptation decisions."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_choice(
    conn, strategy_plan_id: str, scenario_id: str, title: str, action_summary: str,
    *, trigger_metric_key: Optional[str] = None, trigger_operator: Optional[str] = None,
    trigger_threshold: Optional[float] = None, priority: str = "medium",
    created_by_party_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not title.strip() or not action_summary.strip():
        raise ValueError("contingency title and action are required")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_contingency_choice
            (strategy_plan_id, scenario_id, title, trigger_metric_key, trigger_operator,
             trigger_threshold, action_summary, priority, created_by_party_id)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s::uuid)
            RETURNING *""", (strategy_plan_id, scenario_id, title, trigger_metric_key,
                              trigger_operator, trigger_threshold, action_summary, priority,
                              created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def approve_choice(conn, choice_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""UPDATE strategy_contingency_choice
            SET status = 'approved', approved_by_party_id = %s::uuid, approved_at = NOW()
            WHERE id = %s::uuid AND status = 'proposed' RETURNING *""", (approved_by_party_id, choice_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only proposed contingency choices can be approved")
        conn.commit()
        return _clean(row)


def record_adaptation(
    conn, choice_id: str, decision: str, rationale: str, *,
    decided_by_party_id: Optional[str] = None, to_strategy_plan_id: Optional[str] = None,
    status: str = "approved",
) -> Dict[str, Any]:
    if not rationale.strip():
        raise ValueError("adaptation rationale is required")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT strategy_plan_id, scenario_id, status
            FROM strategy_contingency_choice WHERE id = %s::uuid FOR UPDATE""", (choice_id,))
        choice = cur.fetchone()
        if not choice or choice["status"] not in ("approved", "active"):
            conn.rollback()
            raise ValueError("only approved contingency choices can produce adaptations")
        cur.execute("""INSERT INTO strategy_adaptation_event
            (strategy_plan_id, contingency_choice_id, from_strategy_plan_id, to_strategy_plan_id,
             decision, rationale, status, decided_by_party_id)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::uuid)
            RETURNING *""", (choice["strategy_plan_id"], choice_id, choice["strategy_plan_id"],
                              to_strategy_plan_id, decision, rationale, status, decided_by_party_id))
        event = cur.fetchone()
        cur.execute("""INSERT INTO strategy_evidence_link
            (strategy_plan_id, subject_type, subject_id, source_type, source_id, relevance,
             confidence, interpretation, created_by_party_id)
            VALUES (%s::uuid, 'choice', %s::uuid, 'scenario', %s::uuid, 'required',
                    'moderate', %s, %s::uuid)
            ON CONFLICT DO NOTHING""", (choice["strategy_plan_id"], choice_id, choice["scenario_id"], rationale, decided_by_party_id))
        conn.commit()
        return _clean(event)
