"""Stakeholder decision, trade-off, approval, and evidence lineage service."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2.extras


DECISION_TYPES = ("policy", "resource_allocation", "operational", "technology", "governance", "remedy", "other")
PARTICIPANT_ROLES = ("affected", "consulted", "decision_maker", "steward", "observer", "proxy")
TRADEOFF_DIRECTIONS = ("benefit", "harm", "cost", "risk", "neutral")
EVIDENCE_ROLES = ("input", "supporting", "contradicting", "impact", "approval", "outcome")
OUTCOME_TYPES = ("benefit", "harm", "metric", "work_item", "engagement", "remedy", "feedback")


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row(row: Any) -> Optional[Dict[str, Any]]:
    return {key: _value(value) for key, value in dict(row).items()} if row else None


def create_decision(
    conn, title: str, description: str, decision_type: str, *,
    decision_key: Optional[str] = None, scope_type: str = "network",
    scope_id: Optional[str] = None, proposed_action: Optional[str] = None,
    created_by_party_id: Optional[str] = None,
) -> Dict[str, Any]:
    if decision_type not in DECISION_TYPES:
        raise ValueError(f"decision_type must be one of {DECISION_TYPES}")
    if not title.strip() or not description.strip():
        raise ValueError("title and description are required")
    key = decision_key or f"SD-{uuid.uuid4().hex[:12].upper()}"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_decision
               (decision_key, title, description, decision_type, scope_type, scope_id,
                proposed_action, created_by_party_id)
               VALUES (%s, %s, %s, %s, %s, %s::uuid, %s, %s::uuid)
               RETURNING *""",
            (key, title, description, decision_type, scope_type, scope_id,
             proposed_action, created_by_party_id),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def submit_decision(conn, decision_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE stakeholder_decision SET status = 'submitted', updated_at = NOW()
               WHERE id = %s::uuid AND status = 'draft' RETURNING *""", (decision_id,)
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def approve_decision(conn, decision_id: str, approved_by_party_id: str, *, approval_role: str = "stakeholder_reviewer", approval_evidence: Optional[List[Any]] = None) -> Optional[Dict[str, Any]]:
    if not approved_by_party_id:
        raise ValueError("a human approving party is required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""SELECT COUNT(*) AS unresolved_harm_count
                       FROM stakeholder_decision_tradeoff
                       WHERE decision_id = %s::uuid AND direction IN ('harm', 'risk') AND NOT accepted""", (decision_id,))
        if cur.fetchone()["unresolved_harm_count"]:
            raise ValueError("stakeholder decision has unresolved material harm")
        cur.execute(
            """UPDATE stakeholder_decision
               SET status = 'approved', approval_status = 'approved',
                   approved_by_party_id = %s::uuid, approved_at = NOW(), updated_at = NOW()
                   , approval_actor_type = 'human', approval_role = %s,
                   approval_evidence = %s::jsonb, material_harm_review_status = 'clear'
               WHERE id = %s::uuid AND status = 'submitted' AND approval_status = 'pending'
               RETURNING *""",
            (approved_by_party_id, approval_role, json.dumps(approval_evidence or []), decision_id),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def reject_decision(conn, decision_id: str, *, reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE stakeholder_decision
               SET status = 'rejected', approval_status = 'rejected', updated_at = NOW(),
                   description = CASE WHEN %s IS NULL THEN description ELSE description || E'\n\nRejection: ' || %s END
               WHERE id = %s::uuid AND status = 'submitted' AND approval_status = 'pending'
               RETURNING *""",
            (reason, reason, decision_id),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def link_execution(conn, decision_id: str, *, work_item_id: Optional[str] = None, decision_log_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not work_item_id and not decision_log_id:
        raise ValueError("work_item_id or decision_log_id is required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE stakeholder_decision
               SET status = 'in_execution', work_item_id = COALESCE(%s::uuid, work_item_id),
                   decision_log_id = COALESCE(%s::uuid, decision_log_id), updated_at = NOW()
               WHERE id = %s::uuid AND status = 'approved' AND approval_status = 'approved'
               RETURNING *""",
            (work_item_id, decision_log_id, decision_id),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def complete_decision(conn, decision_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE stakeholder_decision SET status = 'completed', updated_at = NOW()
               WHERE id = %s::uuid AND status = 'in_execution' AND approval_status = 'approved'
               RETURNING *""", (decision_id,)
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def add_participant(conn, decision_id: str, *, party_id: Optional[str] = None,
                    participation_id: Optional[str] = None, stakeholder_role: str,
                    participation_status: str = "invited", consent_checked: bool = False,
                    perspective_summary: Optional[str] = None, minority_view: bool = False) -> Dict[str, Any]:
    if stakeholder_role not in PARTICIPANT_ROLES:
        raise ValueError(f"stakeholder_role must be one of {PARTICIPANT_ROLES}")
    if not party_id and not participation_id:
        raise ValueError("party_id or participation_id is required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_decision_participant
               (decision_id, party_id, participation_id, stakeholder_role, participation_status,
                consent_checked, perspective_summary, minority_view)
               VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s)
               ON CONFLICT (decision_id, party_id, stakeholder_role) DO UPDATE SET
                 participation_id = EXCLUDED.participation_id,
                 participation_status = EXCLUDED.participation_status,
                 consent_checked = EXCLUDED.consent_checked,
                 perspective_summary = EXCLUDED.perspective_summary,
                 minority_view = EXCLUDED.minority_view
               RETURNING *""",
            (decision_id, party_id, participation_id, stakeholder_role, participation_status,
             consent_checked, perspective_summary, minority_view),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def add_tradeoff(conn, decision_id: str, description: str, direction: str, *,
                 interest_id: Optional[str] = None, party_id: Optional[str] = None,
                 severity: Optional[float] = None, accepted: bool = False,
                 mitigation: Optional[str] = None, evidence: Optional[List[Any]] = None) -> Dict[str, Any]:
    if direction not in TRADEOFF_DIRECTIONS:
        raise ValueError(f"direction must be one of {TRADEOFF_DIRECTIONS}")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_decision_tradeoff
               (decision_id, interest_id, party_id, direction, description, severity, accepted, mitigation, evidence)
               VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::jsonb) RETURNING *""",
            (decision_id, interest_id, party_id, direction, description, severity, accepted, mitigation,
             json.dumps(evidence or [])),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def resolve_tradeoff(conn, tradeoff_id: str, *, accepted: bool, mitigation: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not accepted and not (mitigation or '').strip():
        raise ValueError('unaccepted trade-offs require a mitigation or remain unresolved')
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE stakeholder_decision_tradeoff
               SET accepted = %s, mitigation = COALESCE(%s, mitigation)
               WHERE id = %s::uuid RETURNING *""",
            (accepted, mitigation, tradeoff_id),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def add_evidence(conn, decision_id: str, source_type: str, summary: str, *,
                 evidence_role: str = "supporting", source_id: Optional[str] = None,
                 source_key: Optional[str] = None, content_hash: Optional[str] = None,
                 content_cid: Optional[str] = None, evidence_maturity: Optional[int] = None,
                 verified: bool = False, audience: str = "internal",
                 added_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    if evidence_role not in EVIDENCE_ROLES:
        raise ValueError(f"evidence_role must be one of {EVIDENCE_ROLES}")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_decision_evidence
               (decision_id, source_type, source_id, source_key, evidence_role, summary,
                content_hash, content_cid, evidence_maturity, verified, audience, added_by_party_id)
               VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid)
               RETURNING *""",
            (decision_id, source_type, source_id, source_key, evidence_role, summary,
             content_hash, content_cid, evidence_maturity, verified, audience, added_by_party_id),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def record_outcome(conn, decision_id: str, outcome_type: str, summary: str, *,
                   source_id: Optional[str] = None, outcome_status: str = "observed",
                   evidence: Optional[List[Any]] = None, recorded_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    if outcome_type not in OUTCOME_TYPES:
        raise ValueError(f"outcome_type must be one of {OUTCOME_TYPES}")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_decision_outcome
               (decision_id, outcome_type, source_id, summary, outcome_status, evidence, recorded_by_party_id)
               VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s::jsonb, %s::uuid) RETURNING *""",
            (decision_id, outcome_type, source_id, summary, outcome_status, json.dumps(evidence or []), recorded_by_party_id),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def get_decision(conn, decision_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_stakeholder_decision_lineage WHERE decision_id = %s::uuid", (decision_id,))
        return _row(cur.fetchone())


def list_decisions(conn, *, status: Optional[str] = None, scope_id: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses, params = [], []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if scope_id:
        clauses.append("scope_id = %s::uuid")
        params.append(scope_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_stakeholder_decision_lineage{where} ORDER BY approved_at DESC NULLS LAST, decision_id", params)
        return [_row(row) for row in cur.fetchall()]
