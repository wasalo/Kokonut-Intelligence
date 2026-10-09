"""Governance proposal and objection services."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2.extras

PROPOSAL_TYPES = (
    "create_role", "amend_role", "retire_role", "change_domain", "change_policy",
    "create_circle", "change_circle_scope", "retire_circle", "appoint_representative",
    "change_decision_rule",
)
STATUSES = ("draft", "submitted", "in_review", "approved", "rejected", "implemented", "superseded", "cancelled")
OBJECTION_TYPES = (
    "material_harm", "scope_conflict", "authority_conflict", "consent_failure",
    "evidence_failure", "representation_gap", "operational_risk",
    "legal_or_policy_conflict", "minority_view",
)


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row(row: Any) -> Optional[Dict[str, Any]]:
    return {key: _value(value) for key, value in dict(row).items()} if row else None


def create_proposal(
    conn,
    proposal_key: str,
    circle_id: str,
    proposal_type: str,
    title: str,
    purpose: str,
    proposed_state: str,
    *,
    current_state: Optional[str] = None,
    tension_id: Optional[str] = None,
    proposed_by_party_id: Optional[str] = None,
    proposed_by_role_id: Optional[str] = None,
    affected_scope_type: str = "network",
    affected_scope_id: Optional[str] = None,
    harm_review_status: str = "not_required",
    minority_review_status: str = "not_required",
    evidence: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    if proposal_type not in PROPOSAL_TYPES:
        raise ValueError(f"proposal_type must be one of {PROPOSAL_TYPES}")
    if not proposal_key.strip() or not title.strip() or not purpose.strip() or not proposed_state.strip():
        raise ValueError("proposal key, title, purpose, and proposed state are required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO governance_proposal
               (proposal_key, circle_id, proposal_type, title, purpose,
                current_state, proposed_state, tension_id, proposed_by_party_id,
                proposed_by_role_id, affected_scope_type, affected_scope_id,
                harm_review_status, minority_review_status, evidence)
               VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s::uuid, %s::uuid,
                       %s::uuid, %s, %s::uuid, %s, %s, %s::jsonb)
               RETURNING *""",
            (proposal_key, circle_id, proposal_type, title, purpose,
             current_state, proposed_state, tension_id, proposed_by_party_id,
             proposed_by_role_id, affected_scope_type, affected_scope_id,
             harm_review_status, minority_review_status, json.dumps(evidence or [])),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def get_proposal(conn, proposal_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_governance_proposal_lineage WHERE proposal_id = %s::uuid", (proposal_id,))
        result = _row(cur.fetchone())
        if result:
            cur.execute("SELECT * FROM governance_proposal_objection WHERE proposal_id = %s::uuid ORDER BY created_at", (proposal_id,))
            result["objections"] = [_row(row) for row in cur.fetchall()]
            cur.execute("SELECT * FROM governance_proposal_review WHERE proposal_id = %s::uuid ORDER BY created_at", (proposal_id,))
            result["reviews"] = [_row(row) for row in cur.fetchall()]
        return result


def list_proposals(conn, *, circle_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
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
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_governance_proposal_lineage{where} ORDER BY created_at", params)
        return [_row(row) for row in cur.fetchall()]


def _set_status(conn, proposal_id: str, status: str, **updates: Any) -> Dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    sets = ["status = %s", "updated_at = NOW()"]
    params: List[Any] = [status]
    for key, value in updates.items():
        if key in {"approved_by_party_id", "implementation_work_item_id"}:
            sets.append(f"{key} = %s::uuid")
        else:
            sets.append(f"{key} = %s")
        params.append(value)
    params.append(proposal_id)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"UPDATE governance_proposal SET {', '.join(sets)} WHERE id = %s::uuid RETURNING *", params)
        result = _row(cur.fetchone())
        if not result:
            conn.rollback()
            raise ValueError("proposal not found")
        conn.commit()
        return result


def submit_proposal(conn, proposal_id: str) -> Dict[str, Any]:
    return _set_status(conn, proposal_id, "submitted")


def start_review(conn, proposal_id: str) -> Dict[str, Any]:
    return _set_status(conn, proposal_id, "in_review")


def add_objection(
    conn,
    proposal_id: str,
    objection_type: str,
    objection_text: str,
    *,
    objector_party_id: Optional[str] = None,
    objector_role_id: Optional[str] = None,
    severity: int = 3,
    evidence: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    if objection_type not in OBJECTION_TYPES:
        raise ValueError(f"objection_type must be one of {OBJECTION_TYPES}")
    if not objector_party_id and not objector_role_id:
        raise ValueError("objection requires an objector party or role")
    if not objection_text.strip() or not 1 <= severity <= 5:
        raise ValueError("objection text and severity are required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO governance_proposal_objection
               (proposal_id, objector_party_id, objector_role_id, objection_type,
                objection_text, severity, evidence)
               VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb)
               RETURNING *""",
            (proposal_id, objector_party_id, objector_role_id, objection_type,
             objection_text, severity, json.dumps(evidence or [])),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def respond_to_objection(conn, objection_id: str, status: str, response: str, resolved_by_party_id: str) -> Dict[str, Any]:
    if status not in ("accepted", "rejected", "resolved", "withdrawn"):
        raise ValueError("invalid objection resolution status")
    if not response.strip():
        raise ValueError("objection response is required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE governance_proposal_objection
               SET status = %s, response = %s, resolved_by_party_id = %s::uuid,
                   resolved_at = NOW(), updated_at = NOW()
               WHERE id = %s::uuid RETURNING *""",
            (status, response, resolved_by_party_id, objection_id),
        )
        result = _row(cur.fetchone())
        if not result:
            conn.rollback()
            raise ValueError("objection not found")
        conn.commit()
        return result


def record_review(conn, proposal_id: str, reviewer_party_id: str, review_type: str, result: str, notes: str, *, evidence: Optional[List[Any]] = None) -> Dict[str, Any]:
    if review_type not in ("harm", "minority", "scope", "evidence", "implementation"):
        raise ValueError("invalid review type")
    if result not in ("required", "clear", "blocked", "reviewed", "needs_revision"):
        raise ValueError("invalid review result")
    if not notes.strip():
        raise ValueError("review notes are required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO governance_proposal_review
               (proposal_id, reviewer_party_id, review_type, result, notes, evidence)
               SELECT %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb
               WHERE EXISTS (SELECT 1 FROM party WHERE id = %s::uuid AND party_type = 'person')
               RETURNING *""",
            (proposal_id, reviewer_party_id, review_type, result, notes,
             json.dumps(evidence or []), reviewer_party_id),
        )
        review = _row(cur.fetchone())
        if not review:
            conn.rollback()
            raise ValueError("proposal review requires an identified human reviewer")
        updates = {}
        if review_type == "harm":
            updates["harm_review_status"] = "clear" if result == "clear" else result
        if review_type == "minority":
            updates["minority_review_status"] = "reviewed" if result == "reviewed" else result
        if updates:
            sets = [f"{key} = %s" for key in updates]
            cur.execute(
                f"UPDATE governance_proposal SET {', '.join(sets)}, updated_at = NOW() WHERE id = %s::uuid",
                [*updates.values(), proposal_id],
            )
        conn.commit()
        return review


def approve_proposal(conn, proposal_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    return _set_status(conn, proposal_id, "approved", approved_by_party_id=approved_by_party_id, approved_at=datetime.now(timezone.utc))


def implement_proposal(conn, proposal_id: str, work_item_id: str, implementation_summary: str) -> Dict[str, Any]:
    if not implementation_summary.strip():
        raise ValueError("implementation summary is required")
    return _set_status(
        conn, proposal_id, "implemented", implementation_work_item_id=work_item_id,
        implementation_summary=implementation_summary,
    )
