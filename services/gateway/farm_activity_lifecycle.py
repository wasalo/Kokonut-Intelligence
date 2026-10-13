"""Human-only governed transitions for Field Collector farm activity drafts."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID


class FarmActivityTransitionInvalid(ValueError):
    """Raised when a requested human decision is malformed."""


class FarmActivityTransitionConflict(RuntimeError):
    """Raised when the current lifecycle state cannot accept a decision."""


_TRANSITIONS = {
    "submit": ("submit", "submitted", "submitted", {"draft"}, False),
    "verify": ("verify", "verified", "verified", {"submitted"}, False),
    "reject": ("reject", "rejected", "rejected", {"submitted", "verified"}, True),
    "request-rework": ("rework", "rework_requested", "draft", {"rejected"}, True),
    "publish": ("publish", "published", "published", {"verified"}, False),
    "close-exception": ("close_exception", "exception_closed", "rejected", {"rejected"}, True),
}


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_ids(operator_id: str, activity_id: str, location_id: str) -> tuple[str, str, str]:
    try:
        return str(UUID(operator_id)), str(UUID(activity_id)), str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator, farm activity, or location identifier") from exc


def transition_farm_activity(
    operator_id: str,
    activity_id: str,
    location_id: str,
    action: str,
    reason: str | None = None,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Apply one authorized decision to a Field Collector activity.

    PostgreSQL guards the transition and writes its append-only workflow event
    in the same transaction. The route supplies the OIDC operator identity;
    device and participant identities are never substituted for it.
    """
    operator_id, activity_id, location_id = _normalize_ids(operator_id, activity_id, location_id)
    transition = _TRANSITIONS.get(action)
    if transition is None:
        raise FarmActivityTransitionInvalid("Unsupported farm activity transition")
    grant_action, event_action, to_status, allowed_from, reason_required = transition

    if reason is not None and not isinstance(reason, str):
        raise FarmActivityTransitionInvalid("Transition reason must be text")
    normalized_reason = reason.strip() if isinstance(reason, str) else ""
    if len(normalized_reason) > 2000:
        raise FarmActivityTransitionInvalid("Transition reason exceeds 2000 characters")
    if reason_required and not normalized_reason:
        raise FarmActivityTransitionInvalid("A reason is required for this transition")

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")
            cur.execute(
                "SELECT set_config('kokonut.actor_id', %s, true), "
                "set_config('kokonut.actor_type', 'operator', true), "
                "set_config('kokonut.workflow_action', %s, true), "
                "set_config('kokonut.workflow_reason', %s, true)",
                (operator_id, event_action, normalized_reason),
            )
            cur.execute(
                """SELECT id::text, location_id::text, status::text, source_system
                     FROM farm_activity
                    WHERE id = %s::uuid
                      AND location_id = %s::uuid
                      AND source_system = 'field_collector'
                    FOR UPDATE""",
                (activity_id, location_id),
            )
            activity = cur.fetchone()
            if activity is None:
                conn.rollback()
                return None
            if activity[2] not in allowed_from:
                raise FarmActivityTransitionConflict("Farm activity is not in a state for this decision")

            cur.execute(
                """SELECT id FROM operator_scope_grant
                    WHERE operator_id = %s::uuid
                      AND resource = 'farm_activity'
                      AND action = %s
                      AND location_id = %s::uuid
                      AND revoked_at IS NULL
                    FOR SHARE""",
                (operator_id, grant_action, location_id),
            )
            if cur.fetchone() is None:
                conn.rollback()
                return None

            cur.execute(
                "UPDATE farm_activity SET status = %s, updated_at = NOW() WHERE id = %s::uuid",
                (to_status, activity_id),
            )
            cur.execute(
                """SELECT id::text, action, from_status, to_status, reason, created_at
                     FROM farm_activity_workflow_event
                    WHERE farm_activity_id = %s::uuid
                      AND actor_operator_id = %s::uuid
                      AND action = %s
                      AND from_status IS NOT DISTINCT FROM %s
                      AND to_status = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1""",
                (activity_id, operator_id, event_action, activity[2], to_status),
            )
            event = cur.fetchone()
            if event is None:
                raise FarmActivityTransitionConflict("Farm activity transition evidence was not recorded")

        conn.commit()
        return {
            "event_id": str(event[0]),
            "activity_id": activity_id,
            "location_id": location_id,
            "action": event[1],
            "from_status": event[2],
            "to_status": event[3],
            "reason": event[4],
            "created_at": event[5].isoformat() if hasattr(event[5], "isoformat") else str(event[5]),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
