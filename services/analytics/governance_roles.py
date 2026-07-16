"""Kokonut-native circle and role registry services.

Roles describe purpose and accountabilities independently from the parties that
fill them. Activation and assignment controls are added in later phases.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2.extras


SCOPE_TYPES = (
    "network", "organization", "location", "farm", "cooperative",
    "value_stream", "initiative", "decision",
)
STATUSES = ("draft", "submitted", "active", "suspended", "retired", "rejected")
ROLE_STATUSES = ("draft", "submitted", "approved", "active", "suspended", "retired", "rejected")


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row(row: Any) -> Optional[Dict[str, Any]]:
    return {key: _value(value) for key, value in dict(row).items()} if row else None


def create_circle(
    conn,
    circle_key: str,
    name: str,
    purpose: str,
    *,
    description: str = "",
    parent_circle_id: Optional[str] = None,
    scope_type: str = "network",
    scope_id: Optional[str] = None,
    status: str = "draft",
    created_by_party_id: Optional[str] = None,
    review_due_at: Optional[datetime] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if scope_type not in SCOPE_TYPES:
        raise ValueError(f"scope_type must be one of {SCOPE_TYPES}")
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    if not circle_key.strip() or not name.strip() or not purpose.strip():
        raise ValueError("circle_key, name, and purpose are required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO governance_circle
               (circle_key, name, purpose, description, parent_circle_id,
                scope_type, scope_id, status, created_by_party_id,
                review_due_at, metadata)
               VALUES (%s, %s, %s, %s, %s::uuid, %s, %s::uuid, %s,
                       %s::uuid, %s, %s::jsonb)
               RETURNING *""",
            (circle_key, name, purpose, description, parent_circle_id,
             scope_type, scope_id, status, created_by_party_id,
             review_due_at, json.dumps(metadata or {})),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def list_circles(conn, *, status: Optional[str] = None, scope_type: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if status:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        clauses.append("status = %s")
        params.append(status)
    if scope_type:
        if scope_type not in SCOPE_TYPES:
            raise ValueError(f"scope_type must be one of {SCOPE_TYPES}")
        clauses.append("scope_type = %s")
        params.append(scope_type)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_governance_circle_registry{where} ORDER BY circle_key", params)
        return [_row(row) for row in cur.fetchall()]


def create_role(
    conn,
    circle_id: str,
    role_key: str,
    name: str,
    purpose: str,
    *,
    status: str = "draft",
    created_by_party_id: Optional[str] = None,
    effective_from: Optional[datetime] = None,
    review_due_at: Optional[datetime] = None,
    supersedes_role_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if status not in ROLE_STATUSES:
        raise ValueError(f"status must be one of {ROLE_STATUSES}")
    if not role_key.strip() or not name.strip() or not purpose.strip():
        raise ValueError("role_key, name, and purpose are required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO governance_role
               (circle_id, role_key, name, purpose, status, created_by_party_id,
                effective_from, review_due_at, supersedes_role_id, metadata)
               VALUES (%s::uuid, %s, %s, %s, %s, %s::uuid, %s, %s,
                       %s::uuid, %s::jsonb)
               RETURNING *""",
            (circle_id, role_key, name, purpose, status, created_by_party_id,
             effective_from, review_due_at, supersedes_role_id,
             json.dumps(metadata or {})),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def list_roles(conn, *, circle_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if circle_id:
        clauses.append("circle_id = %s::uuid")
        params.append(circle_id)
    if status:
        if status not in ROLE_STATUSES:
            raise ValueError(f"status must be one of {ROLE_STATUSES}")
        clauses.append("status = %s")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_governance_role_registry{where} ORDER BY circle_key, role_key", params)
        return [_row(row) for row in cur.fetchall()]


def add_accountability(
    conn,
    role_id: str,
    accountability: str,
    *,
    priority: int = 3,
    required: bool = True,
    evidence_expectation: Optional[str] = None,
) -> Dict[str, Any]:
    if not accountability.strip():
        raise ValueError("accountability is required")
    if not 1 <= priority <= 5:
        raise ValueError("priority must be between 1 and 5")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO governance_role_accountability
               (role_id, accountability, priority, required, evidence_expectation)
               VALUES (%s::uuid, %s, %s, %s, %s)
               ON CONFLICT (role_id, accountability) DO UPDATE SET
                   priority = EXCLUDED.priority,
                   required = EXCLUDED.required,
                   evidence_expectation = EXCLUDED.evidence_expectation,
                   status = 'active'
               RETURNING *""",
            (role_id, accountability, priority, required, evidence_expectation),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def list_accountabilities(conn, role_id: str) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT * FROM governance_role_accountability
               WHERE role_id = %s::uuid AND status = 'active'
               ORDER BY priority, accountability""",
            (role_id,),
        )
        return [_row(row) for row in cur.fetchall()]
