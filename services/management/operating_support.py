"""Private operating-support helpers; governed writes require the Gateway."""

from typing import Any, Dict, List, Optional


def record_coaching_session(conn, scope_type: str, scope_id: str, coachee_party_id: str, focus: str, *, coach_party_id: Optional[str] = None, session_date: Optional[str] = None, commitments: Optional[List[Any]] = None, wellbeing_check: Optional[str] = None, notes: Optional[str] = None, privacy_level: str = "private") -> Dict[str, Any]:
    del (
        conn,
        scope_type,
        scope_id,
        coachee_party_id,
        focus,
        coach_party_id,
        session_date,
        commitments,
        wellbeing_check,
        notes,
        privacy_level,
    )
    raise RuntimeError(
        "Unscoped coaching-session writes are disabled; use the authenticated "
        "operating-pilot Gateway."
    )


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
