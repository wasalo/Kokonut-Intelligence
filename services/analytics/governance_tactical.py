"""Tactical sessions and concrete next-action coordination."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2.extras


SESSION_TYPES = ("weekly_review", "stakeholder_health", "relationship_review", "risk_triage", "governance_followup")
ITEM_STATUSES = ("open", "in_progress", "disposed", "cancelled")
DISPOSITIONS = ("next_action", "delegate", "create_work_item", "create_proposal", "escalate", "defer", "no_action")


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row(row: Any) -> Optional[Dict[str, Any]]:
    return {key: _value(value) for key, value in dict(row).items()} if row else None


def create_session(
    conn,
    circle_id: str,
    session_type: str,
    title: str,
    *,
    scheduled_at: Optional[datetime] = None,
    facilitator_role_id: Optional[str] = None,
    recorder_role_id: Optional[str] = None,
    agenda_scope: Optional[str] = None,
    created_by_party_id: Optional[str] = None,
) -> Dict[str, Any]:
    if session_type not in SESSION_TYPES:
        raise ValueError(f"session_type must be one of {SESSION_TYPES}")
    if not title.strip():
        raise ValueError("session title is required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO governance_tactical_session
               (circle_id, session_type, title, scheduled_at,
                facilitator_role_id, recorder_role_id, agenda_scope, created_by_party_id)
               VALUES (%s::uuid, %s, %s, %s, %s::uuid, %s::uuid, %s, %s::uuid)
               RETURNING *""",
            (circle_id, session_type, title, scheduled_at, facilitator_role_id,
             recorder_role_id, agenda_scope, created_by_party_id),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def start_session(conn, session_id: str) -> Dict[str, Any]:
    return _update_session(conn, session_id, "active")


def complete_session(conn, session_id: str, outcome_summary: str) -> Dict[str, Any]:
    if not outcome_summary.strip():
        raise ValueError("session outcome summary is required")
    return _update_session(conn, session_id, "completed", outcome_summary=outcome_summary)


def _update_session(conn, session_id: str, status: str, **updates: Any) -> Dict[str, Any]:
    sets = ["status = %s", "updated_at = NOW()"]
    params: List[Any] = [status]
    for key, value in updates.items():
        sets.append(f"{key} = %s")
        params.append(value)
    params.append(session_id)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"UPDATE governance_tactical_session SET {', '.join(sets)} WHERE id = %s::uuid RETURNING *", params)
        result = _row(cur.fetchone())
        if not result:
            conn.rollback()
            raise ValueError("tactical session not found")
        conn.commit()
        return result


def add_item(
    conn,
    session_id: str,
    requested_next_action: str,
    *,
    tension_id: Optional[str] = None,
    work_item_id: Optional[str] = None,
    decision_id: Optional[str] = None,
    proposer_party_id: Optional[str] = None,
    owner_role_id: Optional[str] = None,
    owner_party_id: Optional[str] = None,
    priority: int = 3,
    due_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    if not requested_next_action.strip():
        raise ValueError("requested_next_action is required")
    if not 1 <= priority <= 5:
        raise ValueError("priority must be between 1 and 5")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO governance_tactical_item
               (session_id, tension_id, work_item_id, decision_id, proposer_party_id,
                owner_role_id, owner_party_id, requested_next_action, priority, due_at)
               VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid,
                       %s::uuid, %s::uuid, %s, %s, %s)
               RETURNING *""",
            (session_id, tension_id, work_item_id, decision_id, proposer_party_id,
             owner_role_id, owner_party_id, requested_next_action, priority, due_at),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def start_item(conn, item_id: str) -> Dict[str, Any]:
    return _update_item(conn, item_id, "in_progress")


def dispose_item(conn, item_id: str, disposition_type: str, disposition_summary: str, disposed_by_party_id: str) -> Dict[str, Any]:
    if disposition_type not in DISPOSITIONS:
        raise ValueError(f"disposition_type must be one of {DISPOSITIONS}")
    if not disposition_summary.strip():
        raise ValueError("disposition summary is required")
    return _update_item(
        conn, item_id, "disposed", disposition_type=disposition_type,
        disposition_summary=disposition_summary, disposed_by_party_id=disposed_by_party_id,
        disposed_at=datetime.utcnow(),
    )


def _update_item(conn, item_id: str, status: str, **updates: Any) -> Dict[str, Any]:
    if status not in ITEM_STATUSES:
        raise ValueError(f"status must be one of {ITEM_STATUSES}")
    sets = ["status = %s", "updated_at = NOW()"]
    params: List[Any] = [status]
    for key, value in updates.items():
        if key in {"work_item_id", "decision_id", "disposed_by_party_id"}:
            sets.append(f"{key} = %s::uuid")
        else:
            sets.append(f"{key} = %s")
        params.append(value)
    params.append(item_id)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"UPDATE governance_tactical_item SET {', '.join(sets)} WHERE id = %s::uuid RETURNING *", params)
        result = _row(cur.fetchone())
        if not result:
            conn.rollback()
            raise ValueError("tactical item not found")
        conn.commit()
        return result


def list_sessions(conn, *, circle_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if circle_id:
        clauses.append("circle_id = %s::uuid")
        params.append(circle_id)
    if status:
        clauses.append("session_status = %s")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_governance_tactical_health{where} ORDER BY scheduled_at NULLS LAST", params)
        return [_row(row) for row in cur.fetchall()]


def list_items(conn, session_id: str, *, status: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = ["session_id = %s::uuid"]
    params: List[Any] = [session_id]
    if status:
        if status not in ITEM_STATUSES:
            raise ValueError(f"status must be one of {ITEM_STATUSES}")
        clauses.append("status = %s")
        params.append(status)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"SELECT * FROM governance_tactical_item WHERE {' AND '.join(clauses)} ORDER BY priority DESC, due_at NULLS LAST",
            params,
        )
        return [_row(row) for row in cur.fetchall()]
