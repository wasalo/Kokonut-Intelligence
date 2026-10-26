"""Read-only, tenant-scoped status projection for an operator's nominations."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 100


class GovernanceAssignmentProposalReadInvalid(ValueError):
    """A nomination history identifier, page limit, or cursor is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise GovernanceAssignmentProposalReadInvalid(f"Invalid {field} identifier") from exc


def _normalize_cursor_time(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise GovernanceAssignmentProposalReadInvalid("Invalid cursor timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GovernanceAssignmentProposalReadInvalid("Cursor timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def list_own_governance_assignment_proposals(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 50,
    cursor_created_at: str | datetime | None = None,
    cursor_assignment_id: str | None = None,
    connection_factory: Callable | None = None,
) -> dict:
    """List only the current operator's bounded nomination status history."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    if isinstance(limit, str):
        if not limit.isdecimal():
            raise GovernanceAssignmentProposalReadInvalid("limit must be an integer between 1 and 100")
        limit = int(limit)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_PAGE_SIZE:
        raise GovernanceAssignmentProposalReadInvalid("limit must be an integer between 1 and 100")

    cursor_time = _normalize_cursor_time(cursor_created_at)
    cursor_id = (
        _normalize_uuid(cursor_assignment_id, "cursor assignment")
        if cursor_assignment_id is not None
        else None
    )
    if (cursor_time is None) != (cursor_id is None):
        raise GovernanceAssignmentProposalReadInvalid(
            "cursor_created_at and cursor_assignment_id must be provided together"
        )

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="governance_roles",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM kokonut_security.list_my_governance_role_assignment_proposals(
                           %s::uuid, %s::integer, %s::timestamptz, %s::uuid
                       )""",
                (location_id, limit + 1, cursor_time, cursor_id),
            )
            rows = [_mapping(cur, row) for row in cur.fetchall()]

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
