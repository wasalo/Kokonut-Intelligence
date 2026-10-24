"""Private coaching helpers; resource-request writes require the Gateway."""

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
    del conn, scope_type, scope_id, requested_by_party_id, resource_type, description, urgency, requested_by
    raise RuntimeError(
        "Unscoped resource-request writes are disabled; use the authenticated operating-pilot Gateway."
    )


def decide_resource(conn, request_id: str, decided_by_party_id: str, decision: str, *, reason: Optional[str] = None) -> Dict[str, Any]:
    del conn, request_id, decided_by_party_id, decision, reason
    raise RuntimeError(
        "Unscoped resource decisions are disabled; use the independently authorized operating-pilot Gateway."
    )
