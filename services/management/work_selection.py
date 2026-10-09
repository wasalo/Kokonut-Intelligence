"""Governed work opportunities and bounded self-selection."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

import psycopg2.extras


SELECTION_MODES = ("assigned", "self_selected", "delegated", "volunteer", "rotational")
CLAIM_STATUSES = ("proposed", "accepted", "rejected", "withdrawn")


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _row(row: Any) -> Optional[Dict[str, Any]]:
    return {key: _value(value) for key, value in dict(row).items()} if row else None


def create_opportunity(
    conn,
    organization_id: str,
    title: str,
    created_by_type: str,
    *,
    description: Optional[str] = None,
    work_type: str = "general",
    priority: str = "medium",
    location_id: Optional[str] = None,
    governance_role_id: Optional[str] = None,
    capability_id: Optional[str] = None,
    selection_mode: str = "self_selected",
    autonomy_level: str = "bounded",
    estimated_effort_hours: Optional[float] = None,
    skill_requirements: Optional[List[Any]] = None,
    due_at: Optional[str] = None,
    sla_at: Optional[str] = None,
) -> Dict[str, Any]:
    if selection_mode not in SELECTION_MODES:
        raise ValueError(f"selection_mode must be one of {SELECTION_MODES}")
    if autonomy_level not in ("guided", "bounded", "autonomous"):
        raise ValueError("invalid autonomy_level")
    if not title.strip():
        raise ValueError("title is required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO work_item
               (organization_id, title, description, status, priority,
                created_by_type, location_id, work_type, governance_role_id,
                capability_id, selection_mode, autonomy_level,
                estimated_effort_hours, skill_requirements, due_at, sla_at)
               VALUES (%s::uuid, %s, %s, 'draft', %s, %s, %s::uuid, %s,
                       %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, %s, %s)
               RETURNING *""",
            (organization_id, title, description, priority, created_by_type,
             location_id, work_type, governance_role_id, capability_id,
             selection_mode, autonomy_level, estimated_effort_hours,
             json.dumps(skill_requirements or []), due_at, sla_at),
        )
        result = _row(cur.fetchone())
        cur.execute(
            """INSERT INTO work_item_selection_event (work_item_id, event_type, note)
               VALUES (%s::uuid, 'opened', %s)""",
            (result["id"], "Work opportunity opened"),
        )
        conn.commit()
        return result


def list_opportunities(conn, *, organization_id: Optional[str] = None, location_id: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if organization_id:
        clauses.append("organization_id = %s::uuid")
        params.append(organization_id)
    if location_id:
        clauses.append("location_id = %s::uuid")
        params.append(location_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_work_opportunity_queue{where} ORDER BY priority DESC, due_at NULLS LAST, work_item_id", params)
        return [_row(row) for row in cur.fetchall()]


def claim_work(
    conn,
    work_item_id: str,
    claimant_party_id: str,
    *,
    claimant_role_id: Optional[str] = None,
    proposed_effort_hours: Optional[float] = None,
    capability_evidence: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT selection_mode, allocation_status, status FROM work_item WHERE id = %s::uuid FOR UPDATE",
            (work_item_id,),
        )
        item = cur.fetchone()
        if not item:
            conn.rollback()
            raise ValueError("work item not found")
        if item["selection_mode"] == "assigned":
            conn.rollback()
            raise ValueError("assigned work cannot be self-selected")
        if item["allocation_status"] not in ("open", "claimed") or item["status"] in ("done", "cancelled"):
            conn.rollback()
            raise ValueError("work opportunity is not open")
        cur.execute(
            """INSERT INTO work_item_claim
               (work_item_id, claimant_party_id, claimant_role_id,
                proposed_effort_hours, capability_evidence)
               VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb)
               RETURNING *""",
            (work_item_id, claimant_party_id, claimant_role_id,
             proposed_effort_hours, json.dumps(capability_evidence or [])),
        )
        result = _row(cur.fetchone())
        cur.execute("UPDATE work_item SET allocation_status = 'claimed', updated_at = NOW() WHERE id = %s::uuid", (work_item_id,))
        cur.execute(
            """INSERT INTO work_item_selection_event
               (work_item_id, claim_id, actor_party_id, event_type, note)
               VALUES (%s::uuid, %s::uuid, %s::uuid, 'claimed', %s)""",
            (work_item_id, result["id"], claimant_party_id, "Party claimed work opportunity"),
        )
        conn.commit()
        return result


def review_claim(conn, claim_id: str, reviewer_party_id: str, status: str, *, reason: str = "") -> Dict[str, Any]:
    if status not in ("accepted", "rejected"):
        raise ValueError("claim review status must be accepted or rejected")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM work_item_claim WHERE id = %s::uuid FOR UPDATE",
            (claim_id,),
        )
        claim = cur.fetchone()
        if not claim:
            conn.rollback()
            raise ValueError("claim not found")
        cur.execute(
            "SELECT party_type FROM party WHERE id = %s::uuid",
            (reviewer_party_id,),
        )
        reviewer = cur.fetchone()
        if not reviewer or reviewer["party_type"] != "person":
            conn.rollback()
            raise ValueError("claim review requires a person party")
        cur.execute(
            """UPDATE work_item_claim
               SET status = %s, reviewed_by_party_id = %s::uuid,
                   reviewed_at = NOW(), decision_reason = %s, updated_at = NOW()
               WHERE id = %s::uuid RETURNING *""",
            (status, reviewer_party_id, reason, claim_id),
        )
        result = _row(cur.fetchone())
        allocation = "allocated" if status == "accepted" else "open"
        cur.execute("UPDATE work_item SET allocation_status = %s, updated_at = NOW() WHERE id = %s::uuid", (allocation, claim["work_item_id"]))
        cur.execute(
            """INSERT INTO work_item_selection_event
               (work_item_id, claim_id, actor_party_id, event_type, note)
               VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s)""",
            (claim["work_item_id"], claim_id, reviewer_party_id, status, reason or "Claim reviewed"),
        )
        conn.commit()
        return result
