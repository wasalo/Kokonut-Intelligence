"""Tension intake and triage for role-and-circle governance."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2.extras


TENSION_TYPES = (
    "unmet_interest", "unclear_accountability", "authority_gap",
    "authority_conflict", "commitment_risk", "representation_gap",
    "consent_gap", "evidence_gap", "harm_risk", "policy_gap",
    "cross_circle_dependency", "role_overload",
)
STATUSES = ("draft", "submitted", "triaged", "in_progress", "resolved", "deferred", "rejected", "closed")
LINK_TYPES = ("interest", "commitment", "work_item", "decision", "grievance", "evidence", "relationship", "proposal", "outcome")


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row(row: Any) -> Optional[Dict[str, Any]]:
    return {key: _value(value) for key, value in dict(row).items()} if row else None


def report_tension(
    conn,
    tension_key: str,
    title: str,
    description: str,
    tension_type: str,
    *,
    circle_id: Optional[str] = None,
    scope_type: str = "network",
    scope_id: Optional[str] = None,
    reported_by_party_id: Optional[str] = None,
    affected_party_id: Optional[str] = None,
    affected_interest_id: Optional[str] = None,
    severity: int = 3,
    urgency: int = 3,
    evidence: Optional[List[Any]] = None,
    review_due_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    if tension_type not in TENSION_TYPES:
        raise ValueError(f"tension_type must be one of {TENSION_TYPES}")
    if not 1 <= severity <= 5 or not 1 <= urgency <= 5:
        raise ValueError("severity and urgency must be between 1 and 5")
    if not tension_key.strip() or not title.strip() or not description.strip():
        raise ValueError("tension_key, title, and description are required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO governance_tension
               (tension_key, title, description, tension_type, severity, urgency,
                circle_id, scope_type, scope_id, reported_by_party_id,
                affected_party_id, affected_interest_id, evidence, review_due_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s::uuid, %s, %s::uuid,
                       %s::uuid, %s::uuid, %s::uuid, %s::jsonb, %s)
               RETURNING *""",
            (tension_key, title, description, tension_type, severity, urgency,
             circle_id, scope_type, scope_id, reported_by_party_id,
             affected_party_id, affected_interest_id, json.dumps(evidence or []),
             review_due_at),
        )
        result = _row(cur.fetchone())
        cur.execute(
            """INSERT INTO governance_tension_event
               (tension_id, actor_party_id, to_status, action, note)
               VALUES (%s::uuid, %s::uuid, 'draft', 'reported', %s)""",
            (result["id"], reported_by_party_id, "Tension reported"),
        )
        conn.commit()
        return result


def get_tension(conn, tension_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_governance_tension_health WHERE tension_id = %s::uuid", (tension_id,))
        result = _row(cur.fetchone())
        if result:
            cur.execute(
                "SELECT * FROM governance_tension_link WHERE tension_id = %s::uuid ORDER BY created_at",
                (tension_id,),
            )
            result["links"] = [_row(row) for row in cur.fetchall()]
        return result


def list_tensions(
    conn,
    *,
    circle_id: Optional[str] = None,
    status: Optional[str] = None,
    overdue_only: bool = False,
) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if circle_id:
        clauses.append("circle_id = %s::uuid")
        params.append(circle_id)
    if status:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        clauses.append("status = %s")
        params.append(status)
    if overdue_only:
        clauses.append("is_overdue = TRUE")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"SELECT * FROM v_governance_tension_health{where} ORDER BY severity DESC, urgency DESC, created_at",
            params,
        )
        return [_row(row) for row in cur.fetchall()]


def _transition(conn, tension_id: str, to_status: str, *, actor_party_id: Optional[str], action: str, note: Optional[str] = None, **updates: Any) -> Dict[str, Any]:
    if to_status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT status FROM governance_tension WHERE id = %s::uuid FOR UPDATE", (tension_id,))
        current = cur.fetchone()
        if not current:
            conn.rollback()
            raise ValueError("tension not found")
        sets = ["status = %s", "updated_at = NOW()"]
        params: List[Any] = [to_status]
        for key, value in updates.items():
            if key in {"owner_role_id", "owner_party_id", "work_item_id", "decision_id", "grievance_id"}:
                sets.append(f"{key} = %s::uuid")
            else:
                sets.append(f"{key} = %s")
            params.append(value)
        params.append(tension_id)
        cur.execute(
            f"UPDATE governance_tension SET {', '.join(sets)} WHERE id = %s::uuid RETURNING *",
            params,
        )
        result = _row(cur.fetchone())
        cur.execute(
            """INSERT INTO governance_tension_event
               (tension_id, actor_party_id, from_status, to_status, action, note)
               VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s)""",
            (tension_id, actor_party_id, current["status"], to_status, action, note),
        )
        conn.commit()
        return result


def submit_tension(conn, tension_id: str, *, actor_party_id: Optional[str] = None) -> Dict[str, Any]:
    return _transition(conn, tension_id, "submitted", actor_party_id=actor_party_id, action="submitted")


def triage_tension(conn, tension_id: str, *, owner_role_id: Optional[str] = None, owner_party_id: Optional[str] = None, actor_party_id: Optional[str] = None, note: Optional[str] = None) -> Dict[str, Any]:
    if not owner_role_id and not owner_party_id:
        raise ValueError("triage requires an owner role or party")
    return _transition(
        conn, tension_id, "triaged", actor_party_id=actor_party_id,
        action="triaged", note=note, owner_role_id=owner_role_id,
        owner_party_id=owner_party_id,
    )


def start_tension(conn, tension_id: str, *, actor_party_id: Optional[str] = None) -> Dict[str, Any]:
    return _transition(conn, tension_id, "in_progress", actor_party_id=actor_party_id, action="started")


def link_record(conn, tension_id: str, link_type: str, entity_type: str, entity_id: str, *, summary: Optional[str] = None, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    if link_type not in LINK_TYPES:
        raise ValueError(f"link_type must be one of {LINK_TYPES}")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO governance_tension_link
               (tension_id, link_type, entity_type, entity_id, summary, created_by_party_id)
               VALUES (%s::uuid, %s, %s, %s::uuid, %s, %s::uuid)
               ON CONFLICT (tension_id, link_type, entity_type, entity_id) DO UPDATE SET
                   summary = EXCLUDED.summary,
                   created_by_party_id = EXCLUDED.created_by_party_id
               RETURNING *""",
            (tension_id, link_type, entity_type, entity_id, summary, created_by_party_id),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def attach_work_item(conn, tension_id: str, work_item_id: str, *, actor_party_id: Optional[str] = None) -> Dict[str, Any]:
    link_record(conn, tension_id, "work_item", "work_item", work_item_id, created_by_party_id=actor_party_id)
    return _transition(
        conn, tension_id, "in_progress", actor_party_id=actor_party_id,
        action="linked_work_item", work_item_id=work_item_id,
    )


def resolve_tension(conn, tension_id: str, resolution_summary: str, *, actor_party_id: Optional[str] = None) -> Dict[str, Any]:
    if not resolution_summary.strip():
        raise ValueError("resolution_summary is required")
    return _transition(
        conn, tension_id, "resolved", actor_party_id=actor_party_id,
        action="resolved", resolution_summary=resolution_summary,
    )


def defer_tension(conn, tension_id: str, deferred_until: datetime, *, actor_party_id: Optional[str] = None, note: Optional[str] = None) -> Dict[str, Any]:
    return _transition(
        conn, tension_id, "deferred", actor_party_id=actor_party_id,
        action="deferred", note=note, deferred_until=deferred_until,
    )
