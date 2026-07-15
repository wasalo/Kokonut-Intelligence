"""Protected grievance, remedy, appeal, and closure service."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2.extras


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row(row: Any) -> Optional[Dict[str, Any]]:
    return {key: _value(value) for key, value in dict(row).items()} if row else None


def _case_number() -> str:
    return f"GRV-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def create_case(
    conn,
    category: str,
    summary: str,
    *,
    feedback_id: Optional[str] = None,
    complainant_party_id: Optional[str] = None,
    affected_party_id: Optional[str] = None,
    location_id: Optional[str] = None,
    severity: str = "medium",
    confidentiality: str = "restricted",
    protected_details: Optional[str] = None,
    retaliation_risk: bool = False,
    owner_party_id: Optional[str] = None,
    due_at: Optional[datetime] = None,
    work_item_id: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_grievance_case
               (case_number, feedback_id, complainant_party_id, affected_party_id,
                location_id, category, severity, confidentiality, summary,
                protected_details, retaliation_risk, owner_party_id, due_at, work_item_id)
               VALUES (%s, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s,
                       %s, %s, %s, %s::uuid, %s, %s::uuid)
               RETURNING *""",
            (_case_number(), feedback_id, complainant_party_id, affected_party_id,
             location_id, category, severity, confidentiality, summary,
             protected_details, retaliation_risk, owner_party_id, due_at, work_item_id),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def acknowledge_case(conn, case_id: str, *, owner_party_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE stakeholder_grievance_case
               SET status = 'acknowledged', acknowledged_at = COALESCE(acknowledged_at, NOW()),
                   owner_party_id = COALESCE(%s::uuid, owner_party_id), updated_at = NOW()
               WHERE id = %s::uuid AND status IN ('received', 'acknowledged')
               RETURNING *""",
            (owner_party_id, case_id),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def assign_investigation(
    conn,
    case_id: str,
    investigator_party_id: str,
    scope: str,
    *,
    conflict_check_status: str = "clear",
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT complainant_party_id, affected_party_id, owner_party_id FROM stakeholder_grievance_case WHERE id = %s::uuid",
            (case_id,),
        )
        case = cur.fetchone()
        if not case:
            raise ValueError(f"grievance case not found: {case_id}")
        if investigator_party_id in {
            str(case["complainant_party_id"]) if case["complainant_party_id"] else None,
            str(case["affected_party_id"]) if case["affected_party_id"] else None,
            str(case["owner_party_id"]) if case["owner_party_id"] else None,
        }:
            raise ValueError("investigator has a prohibited conflict of interest")
        if conflict_check_status == "conflict":
            raise ValueError("conflicted investigators cannot be assigned")
        cur.execute(
            """INSERT INTO grievance_investigation
               (case_id, investigator_party_id, conflict_check_status, scope, status, started_at)
               VALUES (%s::uuid, %s::uuid, %s, %s, 'in_progress', NOW())
               RETURNING *""",
            (case_id, investigator_party_id, conflict_check_status, scope),
        )
        result = _row(cur.fetchone())
        cur.execute(
            "UPDATE stakeholder_grievance_case SET status = 'investigating', updated_at = NOW() WHERE id = %s::uuid",
            (case_id,),
        )
        conn.commit()
        return result


def add_evidence(
    conn,
    case_id: str,
    evidence_type: str,
    title: str,
    *,
    investigation_id: Optional[str] = None,
    description: Optional[str] = None,
    content_hash: Optional[str] = None,
    content_cid: Optional[str] = None,
    submitted_by_party_id: Optional[str] = None,
    confidentiality: str = "restricted",
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO grievance_evidence
               (case_id, investigation_id, evidence_type, title, description,
                content_hash, content_cid, submitted_by_party_id, confidentiality)
               VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::uuid, %s)
               RETURNING *""",
            (case_id, investigation_id, evidence_type, title, description,
             content_hash, content_cid, submitted_by_party_id, confidentiality),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def propose_remedy(
    conn,
    case_id: str,
    remedy_type: str,
    proposal: str,
    *,
    owner_party_id: Optional[str] = None,
    due_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO grievance_remedy
               (case_id, remedy_type, proposal, owner_party_id, due_at)
               VALUES (%s::uuid, %s, %s, %s::uuid, %s)
               RETURNING *""",
            (case_id, remedy_type, proposal, owner_party_id, due_at),
        )
        result = _row(cur.fetchone())
        cur.execute(
            "UPDATE stakeholder_grievance_case SET status = 'remedy_proposed', updated_at = NOW() WHERE id = %s::uuid",
            (case_id,),
        )
        conn.commit()
        return result


def update_remedy(
    conn,
    remedy_id: str,
    status: str,
    *,
    affected_party_confirmed: Optional[bool] = None,
    completion_evidence: Optional[List[Any]] = None,
) -> Optional[Dict[str, Any]]:
    if status not in ("proposed", "accepted", "in_progress", "completed", "rejected", "waived"):
        raise ValueError("invalid remedy status")
    completed_at = datetime.now(timezone.utc) if status == "completed" else None
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE grievance_remedy
               SET status = %s,
                   affected_party_confirmed = COALESCE(%s, affected_party_confirmed),
                   completion_evidence = CASE WHEN %s::jsonb = '[]'::jsonb THEN completion_evidence ELSE %s::jsonb END,
                   completed_at = COALESCE(%s, completed_at), updated_at = NOW()
               WHERE id = %s::uuid
               RETURNING *""",
            (status, affected_party_confirmed, json.dumps(completion_evidence or []),
             json.dumps(completion_evidence or []), completed_at, remedy_id),
        )
        result = _row(cur.fetchone())
        if result and status in ("accepted", "in_progress"):
            cur.execute(
                "UPDATE stakeholder_grievance_case SET status = 'remedy_in_progress', updated_at = NOW() WHERE id = %s::uuid",
                (result["case_id"],),
            )
        conn.commit()
        return result


def appeal_case(conn, case_id: str, reason: str, *, appealed_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    if not reason.strip():
        raise ValueError("appeal reason is required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO grievance_appeal (case_id, appealed_by_party_id, reason)
               VALUES (%s::uuid, %s::uuid, %s) RETURNING *""",
            (case_id, appealed_by_party_id, reason),
        )
        result = _row(cur.fetchone())
        cur.execute(
            "UPDATE stakeholder_grievance_case SET status = 'appealed', updated_at = NOW() WHERE id = %s::uuid",
            (case_id,),
        )
        conn.commit()
        return result


def decide_appeal(
    conn,
    appeal_id: str,
    status: str,
    reviewer_party_id: str,
    decision_notes: str,
) -> Optional[Dict[str, Any]]:
    if status not in ("upheld", "overturned", "closed"):
        raise ValueError("appeal decision must be upheld, overturned, or closed")
    if not decision_notes.strip():
        raise ValueError("appeal decision notes are required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT ga.case_id, ga.appealed_by_party_id, gc.complainant_party_id,
                      gc.affected_party_id, gc.owner_party_id
               FROM grievance_appeal ga
               JOIN stakeholder_grievance_case gc ON gc.id = ga.case_id
               WHERE ga.id = %s::uuid""",
            (appeal_id,),
        )
        source = cur.fetchone()
        if not source:
            return None
        prohibited = {
            str(source["appealed_by_party_id"]) if source["appealed_by_party_id"] else None,
            str(source["complainant_party_id"]) if source["complainant_party_id"] else None,
            str(source["affected_party_id"]) if source["affected_party_id"] else None,
            str(source["owner_party_id"]) if source["owner_party_id"] else None,
        }
        if reviewer_party_id in prohibited:
            raise ValueError("appeal reviewer has a prohibited conflict of interest")
        cur.execute(
            """UPDATE grievance_appeal
               SET status = %s, reviewer_party_id = %s::uuid,
                   conflict_check_status = 'clear', decision_notes = %s, decided_at = NOW()
               WHERE id = %s::uuid
               RETURNING *""",
            (status, reviewer_party_id, decision_notes, appeal_id),
        )
        result = _row(cur.fetchone())
        if status == "overturned":
            cur.execute(
                "UPDATE stakeholder_grievance_case SET status = 'investigating', updated_at = NOW() WHERE id = %s::uuid",
                (source["case_id"],),
            )
        conn.commit()
        return result


def close_case(
    conn,
    case_id: str,
    closure_reason: str,
    *,
    satisfaction_score: Optional[float] = None,
    complainant_confirmed: Optional[bool] = None,
    independent_review_completed: bool = False,
    closed_by_party_id: Optional[str] = None,
    closure_notes: Optional[str] = None,
) -> Dict[str, Any]:
    if not closure_reason.strip():
        raise ValueError("closure reason is required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM grievance_remedy WHERE case_id = %s::uuid AND status IN ('proposed', 'accepted', 'in_progress')",
            (case_id,),
        )
        if cur.fetchone():
            raise ValueError("cannot close a case with open remedies")
        cur.execute(
            "SELECT id FROM grievance_appeal WHERE case_id = %s::uuid AND status IN ('submitted', 'reviewing')",
            (case_id,),
        )
        if cur.fetchone():
            raise ValueError("cannot close a case with an undecided appeal")
        cur.execute(
            """INSERT INTO grievance_closure
               (case_id, closure_reason, satisfaction_score, complainant_confirmed,
                independent_review_completed, closure_notes, closed_by_party_id)
               VALUES (%s::uuid, %s, %s, %s, %s, %s, %s::uuid)
               RETURNING *""",
            (case_id, closure_reason, satisfaction_score, complainant_confirmed,
             independent_review_completed, closure_notes, closed_by_party_id),
        )
        closure = _row(cur.fetchone())
        cur.execute(
            """UPDATE stakeholder_grievance_case
               SET status = 'closed', closed_at = NOW(), resolved_at = COALESCE(resolved_at, NOW()), updated_at = NOW()
               WHERE id = %s::uuid
               RETURNING *""",
            (case_id,),
        )
        case = _row(cur.fetchone())
        conn.commit()
        return {"closure": closure, "case": case}


def list_case_health(conn, *, status: Optional[str] = None, overdue_only: bool = False) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if overdue_only:
        clauses.append("is_overdue = TRUE")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_stakeholder_grievance_health{where} ORDER BY severity DESC, received_at", params)
        return [_row(row) for row in cur.fetchall()]
