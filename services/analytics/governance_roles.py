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
AUTHORITY_LEVELS = ("observe", "recommend", "decide", "execute")
ASSIGNMENT_TYPES = ("primary", "delegate", "representative", "interim")


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


def add_domain(
    conn,
    role_id: str,
    domain_type: str,
    domain_key: str,
    *,
    scope_type: str = "network",
    scope_id: Optional[str] = None,
    authority_level: str = "recommend",
    constraints: Optional[Dict[str, Any]] = None,
    requires_human_approval: bool = True,
) -> Dict[str, Any]:
    if scope_type not in SCOPE_TYPES:
        raise ValueError(f"scope_type must be one of {SCOPE_TYPES}")
    if authority_level not in AUTHORITY_LEVELS:
        raise ValueError(f"authority_level must be one of {AUTHORITY_LEVELS}")
    if not domain_type.strip() or not domain_key.strip():
        raise ValueError("domain_type and domain_key are required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO governance_role_domain
               (role_id, domain_type, domain_key, scope_type, scope_id,
                authority_level, constraints, requires_human_approval, status)
               VALUES (%s::uuid, %s, %s, %s, %s::uuid, %s, %s::jsonb, %s, 'active')
               ON CONFLICT (role_id, domain_type, domain_key, scope_type, scope_id)
               DO UPDATE SET authority_level = EXCLUDED.authority_level,
                             constraints = EXCLUDED.constraints,
                             requires_human_approval = EXCLUDED.requires_human_approval,
                             status = 'active', updated_at = NOW()
               RETURNING *""",
            (role_id, domain_type, domain_key, scope_type, scope_id,
             authority_level, json.dumps(constraints or {}), requires_human_approval),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def list_domains(conn, role_id: str) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT * FROM governance_role_domain
               WHERE role_id = %s::uuid AND status = 'active'
               ORDER BY domain_type, domain_key""",
            (role_id,),
        )
        return [_row(row) for row in cur.fetchall()]


def add_policy(
    conn,
    role_id: str,
    policy_key: str,
    policy_text: str,
    *,
    status: str = "draft",
    created_by_party_id: Optional[str] = None,
    evidence: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    if not policy_key.strip() or not policy_text.strip():
        raise ValueError("policy_key and policy_text are required")
    if status not in ("draft", "submitted", "active", "retired", "rejected"):
        raise ValueError("invalid policy status")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO governance_role_policy
               (role_id, policy_key, policy_text, status, created_by_party_id, evidence)
               VALUES (%s::uuid, %s, %s, %s, %s::uuid, %s::jsonb)
               ON CONFLICT (role_id, policy_key) DO UPDATE SET
                   policy_text = EXCLUDED.policy_text,
                   status = EXCLUDED.status,
                   evidence = EXCLUDED.evidence,
                   updated_at = NOW()
               RETURNING *""",
            (role_id, policy_key, policy_text, status, created_by_party_id,
             json.dumps(evidence or [])),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def assign_role(
    conn,
    role_id: str,
    party_id: str,
    *,
    assignment_type: str = "primary",
    assigned_by_party_id: Optional[str] = None,
    mandate: Optional[str] = None,
    effective_from: Optional[datetime] = None,
    review_due_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    if assignment_type not in ASSIGNMENT_TYPES:
        raise ValueError(f"assignment_type must be one of {ASSIGNMENT_TYPES}")
    if assignment_type == "delegate" and not (mandate or "").strip():
        raise ValueError("delegated role assignments require a mandate")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO governance_role_assignment
               (role_id, party_id, assignment_type, assigned_by_party_id,
                mandate, effective_from, review_due_at)
               VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s, COALESCE(%s, NOW()), %s)
               RETURNING *""",
            (role_id, party_id, assignment_type, assigned_by_party_id,
             mandate, effective_from, review_due_at),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def approve_assignment(
    conn,
    assignment_id: str,
    approved_by_party_id: str,
    *,
    approval_evidence: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE governance_role_assignment
               SET status = 'active', approved_by_party_id = %s::uuid,
                   approval_evidence = %s::jsonb, updated_at = NOW()
               WHERE id = %s::uuid
               RETURNING *""",
            (approved_by_party_id, json.dumps(approval_evidence or []), assignment_id),
        )
        result = _row(cur.fetchone())
        if not result:
            conn.rollback()
            raise ValueError("role assignment not found")
        conn.commit()
        return result


def end_assignment(conn, assignment_id: str, *, recused: bool = False) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE governance_role_assignment
               SET status = CASE WHEN %s THEN 'suspended' ELSE 'ended' END,
                   recusal_status = CASE WHEN %s THEN 'recused' ELSE recusal_status END,
                   effective_until = COALESCE(effective_until, NOW()),
                   updated_at = NOW()
               WHERE id = %s::uuid
               RETURNING *""",
            (recused, recused, assignment_id),
        )
        result = _row(cur.fetchone())
        if not result:
            conn.rollback()
            raise ValueError("role assignment not found")
        conn.commit()
        return result


def list_assignments(conn, *, role_id: Optional[str] = None, party_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if role_id:
        clauses.append("role_id = %s::uuid")
        params.append(role_id)
    if party_id:
        clauses.append("party_id = %s::uuid")
        params.append(party_id)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_governance_role_assignments{where} ORDER BY role_name, party_name", params)
        return [_row(row) for row in cur.fetchall()]


def role_can_act(
    conn,
    party_id: str,
    domain_type: str,
    domain_key: str,
    *,
    scope_type: str = "network",
    scope_id: Optional[str] = None,
    required_level: str = "recommend",
) -> bool:
    levels = {name: index for index, name in enumerate(AUTHORITY_LEVELS)}
    if required_level not in levels:
        raise ValueError(f"required_level must be one of {AUTHORITY_LEVELS}")
    with conn.cursor() as cur:
        cur.execute(
            """SELECT d.authority_level, d.requires_human_approval
               FROM governance_role_assignment a
               JOIN governance_role_domain d ON d.role_id = a.role_id
               WHERE a.party_id = %s::uuid AND a.status = 'active'
                 AND a.recusal_status = 'clear' AND d.status = 'active'
                 AND d.domain_type = %s AND d.domain_key = %s
                 AND d.scope_type = %s AND d.scope_id IS NOT DISTINCT FROM %s::uuid
                 AND (a.effective_until IS NULL OR a.effective_until >= NOW())
               ORDER BY CASE d.authority_level
                   WHEN 'observe' THEN 0 WHEN 'recommend' THEN 1
                   WHEN 'decide' THEN 2 WHEN 'execute' THEN 3 END DESC
               LIMIT 1""",
            (party_id, domain_type, domain_key, scope_type, scope_id),
        )
        row = cur.fetchone()
    return bool(row and levels[row[0]] >= levels[required_level])
