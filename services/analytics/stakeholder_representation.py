"""Stakeholder participation, representation, and equity service."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2.extras


ACTIVITY_TYPES = ("engagement_plan", "touchpoint", "delphi_study", "decision", "cooperative_meeting", "feedback", "other")
NEED_TYPES = ("language", "channel", "device", "mobility", "hearing", "vision", "literacy", "schedule", "privacy", "other")
DISTRIBUTION_TYPES = ("benefit", "harm", "cost", "remedy")


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row(row: Any) -> Optional[Dict[str, Any]]:
    return {key: _value(value) for key, value in dict(row).items()} if row else None


def record_participation(
    conn,
    activity_type: str,
    activity_id: str,
    *,
    party_id: Optional[str] = None,
    anonymous_group: Optional[str] = None,
    stakeholder_role: Optional[str] = None,
    invitation_status: str = "invited",
    invited_at: Optional[datetime] = None,
    responded_at: Optional[datetime] = None,
    participated_at: Optional[datetime] = None,
    contribution_count: int = 0,
    consent_checked: bool = False,
    access_needs_recorded: bool = False,
    language: Optional[str] = None,
    evidence: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    if activity_type not in ACTIVITY_TYPES:
        raise ValueError(f"activity_type must be one of {ACTIVITY_TYPES}")
    if not party_id and not anonymous_group:
        raise ValueError("party_id or anonymous_group is required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_participation
               (activity_type, activity_id, party_id, anonymous_group, stakeholder_role,
                invitation_status, invited_at, responded_at, participated_at,
                contribution_count, consent_checked, access_needs_recorded, language, evidence)
               VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s, COALESCE(%s, NOW()), %s, %s,
                       %s, %s, %s, %s, %s::jsonb)
               ON CONFLICT (activity_type, activity_id, party_id, anonymous_group) DO UPDATE SET
                   stakeholder_role = EXCLUDED.stakeholder_role,
                   invitation_status = EXCLUDED.invitation_status,
                   responded_at = EXCLUDED.responded_at,
                   participated_at = EXCLUDED.participated_at,
                   contribution_count = EXCLUDED.contribution_count,
                   consent_checked = EXCLUDED.consent_checked,
                   access_needs_recorded = EXCLUDED.access_needs_recorded,
                   language = EXCLUDED.language,
                   evidence = EXCLUDED.evidence
               RETURNING *""",
            (activity_type, activity_id, party_id, anonymous_group, stakeholder_role,
             invitation_status, invited_at, responded_at, participated_at,
             contribution_count, consent_checked, access_needs_recorded, language,
             json.dumps(evidence or [])),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def record_accessibility_request(
    conn,
    participation_id: str,
    need_type: str,
    requested_support: str,
    *,
    party_id: Optional[str] = None,
) -> Dict[str, Any]:
    if need_type not in NEED_TYPES:
        raise ValueError(f"need_type must be one of {NEED_TYPES}")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_accessibility_request
               (participation_id, party_id, need_type, requested_support)
               VALUES (%s::uuid, %s::uuid, %s, %s) RETURNING *""",
            (participation_id, party_id, need_type, requested_support),
        )
        result = _row(cur.fetchone())
        cur.execute(
            "UPDATE stakeholder_participation SET access_needs_recorded = TRUE WHERE id = %s::uuid",
            (participation_id,),
        )
        conn.commit()
        return result


def record_minority_view(
    conn,
    activity_type: str,
    activity_id: str,
    view_summary: str,
    *,
    party_id: Optional[str] = None,
    anonymous_group: Optional[str] = None,
    concern_or_risk: Optional[str] = None,
    preserved: bool = True,
    decision_response: Optional[str] = None,
    evidence: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    if not party_id and not anonymous_group:
        raise ValueError("party_id or anonymous_group is required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_minority_view
               (activity_type, activity_id, party_id, anonymous_group, view_summary,
                concern_or_risk, preserved, decision_response, evidence)
               VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::jsonb)
               RETURNING *""",
            (activity_type, activity_id, party_id, anonymous_group, view_summary,
             concern_or_risk, preserved, decision_response, json.dumps(evidence or [])),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def record_distribution(
    conn,
    scope_type: str,
    distribution_type: str,
    metric_name: str,
    amount: float,
    unit: str,
    *,
    scope_id: Optional[str] = None,
    beneficiary_party_id: Optional[str] = None,
    stakeholder_type: Optional[str] = None,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    evidence: Optional[List[Any]] = None,
    status: str = "draft",
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    if distribution_type not in DISTRIBUTION_TYPES:
        raise ValueError(f"distribution_type must be one of {DISTRIBUTION_TYPES}")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_distribution
               (scope_type, scope_id, distribution_type, beneficiary_party_id,
                stakeholder_type, metric_name, amount, unit, period_start,
                period_end, evidence, status, created_by)
               VALUES (%s, %s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s, %s,
                       %s::jsonb, %s, %s::uuid)
               RETURNING *""",
            (scope_type, scope_id, distribution_type, beneficiary_party_id,
             stakeholder_type, metric_name, amount, unit, period_start, period_end,
             json.dumps(evidence or []), status, created_by),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def representation_metrics(conn, activity_type: str, activity_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM v_stakeholder_representation_metrics WHERE activity_type = %s AND activity_id = %s::uuid",
            (activity_type, activity_id),
        )
        return _row(cur.fetchone())


def list_distribution_summary(conn, *, scope_type: Optional[str] = None, scope_id: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if scope_type:
        clauses.append("scope_type = %s")
        params.append(scope_type)
    if scope_id:
        clauses.append("scope_id = %s::uuid")
        params.append(scope_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_stakeholder_equity_distribution{where} ORDER BY distribution_type, metric_name", params)
        return [_row(row) for row in cur.fetchall()]
