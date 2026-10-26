"""Read-only, location-scoped review views for governance tensions."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_QUEUE_STATUSES = ("submitted", "triaged", "in_progress", "deferred")
_MAX_PAGE_SIZE = 100
_MAX_EVENT_HISTORY = 100


class GovernanceTensionReviewInvalid(ValueError):
    """A queue filter, cursor, or identifier is invalid."""


class GovernanceTensionReviewNotFound(LookupError):
    """A tension does not exist in the requested location scope."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise GovernanceTensionReviewInvalid(f"Invalid {field} identifier") from exc


def _columns(cursor) -> list[str]:
    return [column.name for column in (cursor.description or ())]


def _mapping(cursor, row) -> dict:
    return dict(zip(_columns(cursor), row))


def list_location_governance_tensions(
    operator_id: str,
    location_id: str,
    *,
    status: str | None = None,
    limit: int | str = 50,
    cursor: str | None = None,
    connection_factory: Callable | None = None,
) -> dict:
    """List a bounded review queue without exposing reporter or evidence data.

    The default queue contains only submitted and actively managed tensions.
    Pagination uses an ID cursor resolved inside the same location, so a cursor
    from another tenant cannot reveal whether its record exists.
    """
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    if status is None:
        statuses = list(_QUEUE_STATUSES)
    elif status in _QUEUE_STATUSES:
        statuses = [status]
    else:
        raise GovernanceTensionReviewInvalid("status is not available in the review queue")

    if isinstance(limit, str):
        if not limit.isdecimal():
            raise GovernanceTensionReviewInvalid("limit must be an integer between 1 and 100")
        limit = int(limit)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_PAGE_SIZE:
        raise GovernanceTensionReviewInvalid("limit must be an integer between 1 and 100")
    cursor_id = _normalize_uuid(cursor, "cursor") if cursor is not None else None

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
            resource="governance_tension",
            action="read",
        )

        cursor_created_at = None
        if cursor_id is not None:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT tension.created_at
                         FROM public.governance_tension AS tension
                        WHERE tension.id = %s::uuid
                          AND tension.scope_type = 'location'
                          AND tension.scope_id = %s::uuid""",
                    (cursor_id, location_id),
                )
                row = cur.fetchone()
            if row is None:
                raise GovernanceTensionReviewInvalid(
                    "cursor is not available in the requested location"
                )
            cursor_created_at = row[0]

        with conn.cursor() as cur:
            cur.execute(
                """SELECT tension.id, tension.title, tension.tension_type,
                          tension.severity, tension.urgency, tension.status,
                          tension.created_at, tension.review_due_at
                     FROM public.governance_tension AS tension
                    WHERE tension.scope_type = 'location'
                      AND tension.scope_id = %s::uuid
                      AND tension.status = ANY(%s::text[])
                      AND (%s::timestamptz IS NULL OR
                           (tension.created_at, tension.id) <
                           (%s::timestamptz, %s::uuid))
                    ORDER BY tension.created_at DESC, tension.id DESC
                    LIMIT %s""",
                (
                    location_id,
                    statuses,
                    cursor_created_at,
                    cursor_created_at,
                    cursor_id,
                    limit + 1,
                ),
            )
            rows = [_mapping(cur, row) for row in cur.fetchall()]

        has_more = len(rows) > limit
        items = rows[:limit]
        return {
            "location_id": location_id,
            "items": items,
            "next_cursor": str(items[-1]["id"]) if has_more and items else None,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def get_location_governance_tension(
    operator_id: str,
    location_id: str,
    tension_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return one location tension and bounded lifecycle metadata.

    Reporter identities, affected parties, evidence, metadata, links, and free-
    text event notes are excluded from this reviewer projection. Draft and
    terminal records are deliberately indistinguishable from missing records.
    """
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    tension_id = _normalize_uuid(tension_id, "tension")
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
            resource="governance_tension",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """SELECT tension.id, tension.title, tension.description,
                          tension.tension_type, tension.severity, tension.urgency,
                          tension.status, tension.review_due_at,
                          tension.deferred_until, tension.created_at,
                          tension.updated_at
                     FROM public.governance_tension AS tension
                    WHERE tension.id = %s::uuid
                      AND tension.scope_type = 'location'
                      AND tension.scope_id = %s::uuid
                      AND tension.status = ANY(%s::text[])""",
                (tension_id, location_id, list(_QUEUE_STATUSES)),
            )
            row = cur.fetchone()
            if row is None:
                raise GovernanceTensionReviewNotFound(
                    "governance tension was not found in this location"
                )
            tension = _mapping(cur, row)

            cur.execute(
                """SELECT event.from_status, event.to_status, event.action,
                          event.created_at
                     FROM public.governance_tension_event AS event
                    WHERE event.tension_id = %s::uuid
                    ORDER BY event.created_at DESC, event.id DESC
                    LIMIT %s""",
                (tension_id, _MAX_EVENT_HISTORY + 1),
            )
            events = [_mapping(cur, event) for event in cur.fetchall()]

        events_truncated = len(events) > _MAX_EVENT_HISTORY
        return {
            "location_id": location_id,
            "tension": tension,
            "events": events[:_MAX_EVENT_HISTORY],
            "events_truncated": events_truncated,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
