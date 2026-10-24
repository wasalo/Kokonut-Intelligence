"""Tenant-scoped human review for proposed governance role assignments."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 100
_DECISIONS = frozenset({"approve", "reject"})


class GovernanceAssignmentReviewInvalid(ValueError):
    """A review request, cursor, or identifier is malformed."""


class GovernanceAssignmentReviewConflict(RuntimeError):
    """The proposal cannot be reviewed in its current state."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise GovernanceAssignmentReviewInvalid(f"Invalid {field} identifier") from exc


def _normalize_cursor_time(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise GovernanceAssignmentReviewInvalid("Invalid cursor timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GovernanceAssignmentReviewInvalid("Cursor timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def list_governance_assignment_reviews(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 50,
    cursor_created_at: str | datetime | None = None,
    cursor_assignment_id: str | None = None,
    connection_factory: Callable | None = None,
) -> dict:
    """Return pending proposals to a location reviewer without mutation."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    if isinstance(limit, str):
        if not limit.isdecimal():
            raise GovernanceAssignmentReviewInvalid("limit must be an integer between 1 and 100")
        limit = int(limit)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_PAGE_SIZE:
        raise GovernanceAssignmentReviewInvalid("limit must be an integer between 1 and 100")
    cursor_time = _normalize_cursor_time(cursor_created_at)
    cursor_id = (
        _normalize_uuid(cursor_assignment_id, "cursor assignment")
        if cursor_assignment_id is not None
        else None
    )
    if (cursor_time is None) != (cursor_id is None):
        raise GovernanceAssignmentReviewInvalid(
            "cursor_created_at and cursor_assignment_id must be provided together"
        )

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="governance_roles",
            action="review",
        )
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_governance_role_assignment_review_queue(
                           %s::uuid, %s::integer, %s::timestamptz, %s::uuid
                       )""",
                (location_id, limit + 1, cursor_time, cursor_id),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = {
                "created_at": last["created_at"].isoformat(),
                "assignment_id": str(last["assignment_id"]),
            }
        return {"location_id": location_id, "items": items, "next_cursor": next_cursor}
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def decide_governance_assignment(
    operator_id: str,
    location_id: str,
    role_id: str,
    assignment_id: str,
    decision: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Record an independent approve/reject decision through the bounded DB function."""
    if not isinstance(decision, str) or decision not in _DECISIONS:
        raise GovernanceAssignmentReviewInvalid("decision is not supported")
    if not isinstance(payload, dict) or set(payload) != {"decision_request_id", "reason"}:
        raise GovernanceAssignmentReviewInvalid(
            "Decision must contain decision_request_id and reason"
        )
    operator_id, location_id, role_id, assignment_id, request_id = tuple(
        _normalize_uuid(value, label)
        for value, label in (
            (operator_id, "operator"),
            (location_id, "location"),
            (role_id, "role"),
            (assignment_id, "assignment"),
            (payload.get("decision_request_id"), "decision request"),
        )
    )
    reason = payload.get("reason")
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 4000:
        raise GovernanceAssignmentReviewInvalid("reason must contain 1 to 4000 characters")
    reason = reason.strip()

    conn = (connection_factory or _connection_factory())()
    committed = False
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="governance_roles",
            action=decision,
        )
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.decide_governance_role_assignment(
                           %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s
                       )""",
                (location_id, role_id, assignment_id, request_id, decision, reason),
            )
            row = cursor.fetchone()
            if row is None:
                raise GovernanceAssignmentReviewConflict("Assignment decision returned no result")
            result = _mapping(cursor, row)
        conn.commit()
        committed = True
        return result
    finally:
        if not committed:
            conn.rollback()
        conn.close()
