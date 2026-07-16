"""Private coaching and explicit resource requests."""

import json
import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def record_coaching_session(conn, scope_type: str, scope_id: str, coachee_party_id: str, focus: str, *, coach_party_id: Optional[str] = None, session_date: Optional[str] = None, commitments: Optional[List[Any]] = None, wellbeing_check: Optional[str] = None, notes: Optional[str] = None, privacy_level: str = "private") -> Dict[str, Any]:
    if scope_type not in ("internal", "adelphi"):
        raise ValueError("scope_type must be internal or adelphi")
    if privacy_level not in ("private", "limited", "aggregate_only"):
        raise ValueError("invalid privacy_level")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO operating_coaching_session
            (scope_type, scope_id, coachee_party_id, coach_party_id, session_date, focus, commitments, wellbeing_check, notes, privacy_level)
            VALUES (%s, %s::uuid, %s::uuid, %s::uuid, COALESCE(%s::date, CURRENT_DATE), %s, %s::jsonb, %s, %s, %s) RETURNING *""", (scope_type, scope_id, coachee_party_id, coach_party_id, session_date, focus, json.dumps(commitments or []), wellbeing_check, notes, privacy_level))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def request_resource(conn, scope_type: str, scope_id: str, requested_by_party_id: str, resource_type: str, description: str, *, urgency: str = "medium", requested_by: Optional[str] = None) -> Dict[str, Any]:
    if scope_type not in ("internal", "adelphi"):
        raise ValueError("scope_type must be internal or adelphi")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO operating_resource_request
            (scope_type, scope_id, requested_by_party_id, resource_type, description, urgency, requested_by)
            VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s, COALESCE(%s::date, CURRENT_DATE)) RETURNING *""", (scope_type, scope_id, requested_by_party_id, resource_type, description, urgency, requested_by))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def decide_resource(conn, request_id: str, decided_by_party_id: str, decision: str, *, reason: Optional[str] = None) -> Dict[str, Any]:
    if decision not in ("approved", "partially_approved", "declined", "fulfilled"):
        raise ValueError("invalid resource decision")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""UPDATE operating_resource_request
            SET decision = %s, decision_reason = %s, decided_by_party_id = %s::uuid,
                decided_at = NOW(), status = 'reviewed', updated_at = NOW()
            WHERE id = %s::uuid RETURNING *""", (decision, reason, decided_by_party_id, request_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("resource request not found")
        conn.commit()
        return _clean(row)
