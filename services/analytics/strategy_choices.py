"""Strategic choices and assumptions."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_choice(conn, strategy_plan_id: str, choice_type: str, statement: str, *, rationale: str = "", evidence: Optional[List[Any]] = None, stakeholder_impact: Optional[str] = None, created_by_party_id: Optional[str] = None, visibility: str = "private") -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_choice
            (strategy_plan_id, choice_type, statement, rationale, evidence, stakeholder_impact, created_by_party_id, visibility)
            VALUES (%s::uuid, %s, %s, %s, %s::jsonb, %s, %s::uuid, %s) RETURNING *""", (strategy_plan_id, choice_type, statement, rationale, json.dumps(evidence or []), stakeholder_impact, created_by_party_id, visibility))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def add_alternative(conn, choice_id: str, statement: str, *, expected_outcome: Optional[str] = None, status: str = "considered", reason_not_selected: Optional[str] = None, evidence: Optional[List[Any]] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_alternative
            (choice_id, statement, expected_outcome, reason_not_selected, status, evidence)
            VALUES (%s::uuid, %s, %s, %s, %s, %s::jsonb) RETURNING *""", (choice_id, statement, expected_outcome, reason_not_selected, status, json.dumps(evidence or [])))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def add_tradeoff(conn, choice_id: str, favored_dimension: str, constrained_dimension: str, rationale: str, *, affected_stakeholders: Optional[List[Any]] = None, mitigation: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_tradeoff
            (choice_id, favored_dimension, constrained_dimension, rationale, affected_stakeholders, mitigation)
            VALUES (%s::uuid, %s, %s, %s, %s::jsonb, %s) RETURNING *""", (choice_id, favored_dimension, constrained_dimension, rationale, json.dumps(affected_stakeholders or []), mitigation))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def create_assumption(conn, strategy_plan_id: str, statement: str, *, confidence: float = 0.5, importance: str = "medium", test_metric_key: Optional[str] = None, trigger_operator: Optional[str] = None, trigger_threshold: Optional[float] = None, owner_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_assumption
            (strategy_plan_id, statement, confidence, importance, test_metric_key, trigger_operator, trigger_threshold, owner_party_id)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s::uuid) RETURNING *""", (strategy_plan_id, statement, confidence, importance, test_metric_key, trigger_operator, trigger_threshold, owner_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def test_assumption(conn, assumption_id: str, status: str, *, evidence: Optional[List[Any]] = None) -> Dict[str, Any]:
    if status not in ("testing", "validated", "invalidated", "retired"):
        raise ValueError("invalid assumption status")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""UPDATE strategy_assumption SET status = %s, evidence = %s::jsonb,
            last_tested_at = NOW(), updated_at = NOW() WHERE id = %s::uuid RETURNING *""", (status, json.dumps(evidence or []), assumption_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("assumption not found")
        conn.commit()
        return _clean(row)


def approve_choice(conn, choice_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""UPDATE strategy_choice SET status = 'approved', approved_by_party_id = %s::uuid,
            approved_at = NOW(), updated_at = NOW() WHERE id = %s::uuid AND status = 'submitted' RETURNING *""", (approved_by_party_id, choice_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only submitted choices can be approved")
        conn.commit()
        return _clean(row)


def submit_choice(conn, choice_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("UPDATE strategy_choice SET status = 'submitted', updated_at = NOW() WHERE id = %s::uuid AND status = 'draft' RETURNING *", (choice_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only draft choices can be submitted")
        conn.commit()
        return _clean(row)
