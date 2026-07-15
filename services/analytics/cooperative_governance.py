"""Governed cooperative meetings, proposals, votes, and conflicts."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import psycopg2.extras


def _row(row: Any) -> Optional[Dict[str, Any]]:
    return dict(row) if row else None


def create_meeting(conn, cooperative_id: str, title: str, meeting_type: str, scheduled_at: str, *, created_by_party_id: Optional[str] = None):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""INSERT INTO cooperative_meeting
            (cooperative_id, title, meeting_type, scheduled_at, created_by_party_id)
            VALUES (%s::uuid, %s, %s, %s, %s::uuid) RETURNING *""",
            (cooperative_id, title, meeting_type, scheduled_at, created_by_party_id))
        result = _row(cur.fetchone()); conn.commit(); return result


def create_proposal(conn, cooperative_id: str, title: str, description: str, *, meeting_id: Optional[str] = None, proposed_by_party_id: Optional[str] = None):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""INSERT INTO cooperative_proposal
            (cooperative_id, meeting_id, title, description, proposed_by_party_id, status, submitted_at)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s::uuid, 'submitted', NOW()) RETURNING *""",
            (cooperative_id, meeting_id, title, description, proposed_by_party_id))
        result = _row(cur.fetchone()); conn.commit(); return result


def create_motion(conn, proposal_id: str, motion_type: str, text: str, *, moved_by_membership_id: Optional[str] = None):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""INSERT INTO cooperative_motion
            (proposal_id, motion_type, text, moved_by_membership_id)
            VALUES (%s::uuid, %s, %s, %s::uuid) RETURNING *""",
            (proposal_id, motion_type, text, moved_by_membership_id))
        result = _row(cur.fetchone()); conn.commit(); return result


def cast_vote(conn, motion_id: str, membership_id: str, vote: str, *, party_id: Optional[str] = None):
    if vote not in ("for", "against", "abstain", "recuse"):
        raise ValueError("invalid cooperative vote")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""INSERT INTO cooperative_vote (motion_id, membership_id, party_id, vote)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s)
            ON CONFLICT (motion_id, membership_id) DO UPDATE SET vote = EXCLUDED.vote, party_id = EXCLUDED.party_id, cast_at = NOW()
            RETURNING *""", (motion_id, membership_id, party_id, vote))
        result = _row(cur.fetchone()); conn.commit(); return result


def record_quorum(conn, meeting_id: str, eligible_count: int, present_count: int, required_pct: float, *, verified_by_party_id: Optional[str] = None):
    achieved = eligible_count > 0 and present_count / eligible_count * 100 >= required_pct
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""INSERT INTO cooperative_quorum
            (meeting_id, eligible_count, present_count, required_pct, achieved, verified_by_party_id, verified_at)
            VALUES (%s::uuid, %s, %s, %s, %s, %s::uuid, CASE WHEN %s::uuid IS NULL THEN NULL ELSE NOW() END)
            ON CONFLICT (meeting_id) DO UPDATE SET eligible_count = EXCLUDED.eligible_count,
              present_count = EXCLUDED.present_count, required_pct = EXCLUDED.required_pct,
              achieved = EXCLUDED.achieved, verified_by_party_id = EXCLUDED.verified_by_party_id,
              verified_at = EXCLUDED.verified_at RETURNING *""",
            (meeting_id, eligible_count, present_count, required_pct, achieved, verified_by_party_id, verified_by_party_id))
        result = _row(cur.fetchone()); conn.commit(); return result


def declare_conflict(conn, cooperative_id: str, description: str, *, party_id: Optional[str] = None, membership_id: Optional[str] = None, scope_type: str = "cooperative", scope_id: Optional[str] = None):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""INSERT INTO cooperative_conflict_declaration
            (cooperative_id, party_id, membership_id, scope_type, scope_id, description)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::uuid, %s) RETURNING *""",
            (cooperative_id, party_id, membership_id, scope_type, scope_id, description))
        result = _row(cur.fetchone()); conn.commit(); return result


def governance_health(conn, cooperative_id: Optional[str] = None):
    query = "SELECT * FROM v_cooperative_governance_health"
    params = []
    if cooperative_id:
        query += " WHERE cooperative_id = %s::uuid"; params.append(cooperative_id)
    query += " ORDER BY name"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params); return [dict(row) for row in cur.fetchall()]
