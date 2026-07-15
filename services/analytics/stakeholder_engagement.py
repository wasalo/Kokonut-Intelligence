"""Stakeholder engagement plans, touchpoints, commitments, and outcomes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2.extras


ENGAGEMENT_MODES = ("inform", "consult", "involve", "collaborate", "empower", "steward")
OUTCOME_TYPES = ("progress", "benefit", "harm", "feedback", "resolution", "relationship_change")


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row(row: Any) -> Optional[Dict[str, Any]]:
    return {key: _value(value) for key, value in dict(row).items()} if row else None


def create_plan(
    conn,
    name: str,
    stakeholder_party_id: str,
    *,
    description: str = "",
    owner_party_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    scope_type: str = "network",
    scope_id: Optional[str] = None,
    engagement_mode: str = "collaborate",
    cadence_days: Optional[int] = 90,
    status: str = "draft",
) -> Dict[str, Any]:
    if engagement_mode not in ENGAGEMENT_MODES:
        raise ValueError(f"engagement_mode must be one of {ENGAGEMENT_MODES}")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_engagement_plan
               (name, description, stakeholder_party_id, owner_party_id, organization_id,
                scope_type, scope_id, engagement_mode, cadence_days, status)
               VALUES (%s, %s, %s::uuid, %s::uuid, %s::uuid, %s, %s::uuid, %s, %s, %s)
               RETURNING *""",
            (name, description, stakeholder_party_id, owner_party_id, organization_id,
             scope_type, scope_id, engagement_mode, cadence_days, status),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def list_plans(conn, *, stakeholder_party_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if stakeholder_party_id:
        clauses.append("stakeholder_party_id = %s::uuid")
        params.append(stakeholder_party_id)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_stakeholder_engagement_summary{where} ORDER BY name", params)
        return [_row(row) for row in cur.fetchall()]


def add_objective(
    conn,
    plan_id: str,
    title: str,
    desired_outcome: str,
    *,
    description: str = "",
    success_metric: Optional[str] = None,
    target_value: Optional[float] = None,
    unit: Optional[str] = None,
    target_date: Optional[str] = None,
    priority: int = 3,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_engagement_objective
               (plan_id, title, description, desired_outcome, success_metric,
                target_value, unit, target_date, priority)
               VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING *""",
            (plan_id, title, description, desired_outcome, success_metric,
             target_value, unit, target_date, priority),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def schedule_touchpoint(
    conn,
    plan_id: str,
    purpose: str,
    *,
    objective_id: Optional[str] = None,
    channel_type: Optional[str] = None,
    interaction_type: str = "engagement",
    scheduled_at: Optional[datetime] = None,
    consent_checked: bool = False,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_touchpoint
               (plan_id, objective_id, channel_type, interaction_type, purpose,
                scheduled_at, consent_checked, notes)
               VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)
               RETURNING *""",
            (plan_id, objective_id, channel_type, interaction_type, purpose,
             scheduled_at, consent_checked, notes),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def create_commitment(
    conn,
    plan_id: str,
    title: str,
    *,
    description: str = "",
    objective_id: Optional[str] = None,
    touchpoint_id: Optional[str] = None,
    committed_by_party_id: Optional[str] = None,
    committed_to_party_id: Optional[str] = None,
    owner_party_id: Optional[str] = None,
    due_at: Optional[datetime] = None,
    work_item_id: Optional[str] = None,
    responsibility_id: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_commitment
               (plan_id, objective_id, touchpoint_id, title, description,
                committed_by_party_id, committed_to_party_id, owner_party_id,
                due_at, work_item_id, responsibility_id)
               VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s::uuid, %s::uuid,
                       %s::uuid, %s, %s::uuid, %s::uuid)
               RETURNING *""",
            (plan_id, objective_id, touchpoint_id, title, description,
             committed_by_party_id, committed_to_party_id, owner_party_id,
             due_at, work_item_id, responsibility_id),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def update_commitment(
    conn,
    commitment_id: str,
    *,
    status: Optional[str] = None,
    work_item_id: Optional[str] = None,
    responsibility_id: Optional[str] = None,
    owner_party_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    allowed = {"status", "work_item_id", "responsibility_id", "owner_party_id"}
    values = {key: value for key, value in {
        "status": status,
        "work_item_id": work_item_id,
        "responsibility_id": responsibility_id,
        "owner_party_id": owner_party_id,
    }.items() if value is not None}
    if not values:
        return get_commitment(conn, commitment_id)
    sets = []
    params: List[Any] = []
    for key, value in values.items():
        if key in {"work_item_id", "responsibility_id", "owner_party_id"}:
            sets.append(f"{key} = %s::uuid")
        else:
            sets.append(f"{key} = %s")
        params.append(value)
    sets.append("updated_at = NOW()")
    params.append(commitment_id)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"UPDATE stakeholder_commitment SET {', '.join(sets)} WHERE id = %s::uuid RETURNING *", params)
        result = _row(cur.fetchone())
        conn.commit()
        return result


def get_commitment(conn, commitment_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_stakeholder_commitment_health WHERE commitment_id = %s::uuid", (commitment_id,))
        return _row(cur.fetchone())


def list_commitment_health(conn, *, plan_id: Optional[str] = None, overdue_only: bool = False) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if plan_id:
        clauses.append("plan_id = %s::uuid")
        params.append(plan_id)
    if overdue_only:
        clauses.append("is_overdue = TRUE")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_stakeholder_commitment_health{where} ORDER BY due_at NULLS LAST, title", params)
        return [_row(row) for row in cur.fetchall()]


def record_outcome(
    conn,
    plan_id: str,
    outcome_type: str,
    outcome_summary: str,
    *,
    objective_id: Optional[str] = None,
    commitment_id: Optional[str] = None,
    satisfaction_score: Optional[float] = None,
    evidence: Optional[List[Any]] = None,
    recorded_by: Optional[str] = None,
) -> Dict[str, Any]:
    if outcome_type not in OUTCOME_TYPES:
        raise ValueError(f"outcome_type must be one of {OUTCOME_TYPES}")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_engagement_outcome
               (plan_id, objective_id, commitment_id, outcome_type, outcome_summary,
                satisfaction_score, evidence, recorded_by)
               VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, %s::uuid)
               RETURNING *""",
            (plan_id, objective_id, commitment_id, outcome_type, outcome_summary,
             satisfaction_score, json.dumps(evidence or []), recorded_by),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result
