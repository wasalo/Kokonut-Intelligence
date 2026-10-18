"""Location-scoped, read-only governance role and tactical views."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_ROLE_STATUSES = ("submitted", "approved", "active", "suspended")
_CIRCLE_STATUSES = ("submitted", "active", "suspended")
_TACTICAL_STATUSES = ("open", "in_progress")
_MAX_PAGE_SIZE = 100


class GovernanceOperationsInvalid(ValueError):
    """A role/tactical filter, cursor, or identifier is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise GovernanceOperationsInvalid(f"Invalid {field} identifier") from exc


def _page_size(value: str | int) -> int:
    if isinstance(value, str):
        if not value.isdecimal():
            raise GovernanceOperationsInvalid("limit must be an integer between 1 and 100")
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= _MAX_PAGE_SIZE:
        raise GovernanceOperationsInvalid("limit must be an integer between 1 and 100")
    return value


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def _open_readonly(factory: Callable):
    connection = factory()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
    except Exception:
        try:
            connection.rollback()
        finally:
            connection.close()
        raise
    return connection


def list_location_governance_roles(
    operator_id: str,
    location_id: str,
    *,
    status: str | None = None,
    limit: str | int = 50,
    cursor: str | None = None,
    connection_factory: Callable | None = None,
) -> dict:
    """List location-owned role definitions without party or policy fields."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    if status is None:
        statuses = list(_ROLE_STATUSES)
    elif status in _ROLE_STATUSES:
        statuses = [status]
    else:
        raise GovernanceOperationsInvalid("status is not available in the role registry")
    page_size = _page_size(limit)
    cursor_id = _normalize_uuid(cursor, "cursor") if cursor is not None else None
    conn = _open_readonly(connection_factory or _connection_factory())
    try:
        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="governance_roles",
            action="read",
        )
        cursor_created_at = None
        if cursor_id is not None:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT role.created_at
                         FROM public.governance_role AS role
                         JOIN public.governance_circle AS circle
                           ON circle.id = role.circle_id
                        WHERE role.id = %s::uuid
                          AND role.status = ANY(%s::text[])
                          AND circle.status = ANY(%s::text[])
                          AND circle.scope_type = 'location'
                          AND circle.scope_id = %s::uuid""",
                    (cursor_id, statuses, list(_CIRCLE_STATUSES), location_id),
                )
                row = cur.fetchone()
            if row is None:
                raise GovernanceOperationsInvalid(
                    "cursor is not available in the requested location"
                )
            cursor_created_at = row[0]

        with conn.cursor() as cur:
            cur.execute(
                """SELECT role.id, role.role_key, role.name, role.purpose,
                          role.status, role.effective_from, role.effective_until,
                          role.review_due_at, role.created_at,
                          circle.circle_key, circle.name AS circle_name,
                          circle.status AS circle_status,
                          COUNT(DISTINCT accountability.id) FILTER (
                              WHERE accountability.status = 'active'
                          ) AS active_accountability_count,
                          COUNT(DISTINCT assignment.id) FILTER (
                              WHERE assignment.status = 'active'
                                AND assignment.recusal_status <> 'recused'
                                AND assignment.effective_from <= NOW()
                                AND (assignment.effective_until IS NULL
                                     OR assignment.effective_until >= NOW())
                          ) AS current_assignment_count,
                          COUNT(DISTINCT domain.id) FILTER (
                              WHERE domain.status = 'active'
                                AND (domain.scope_type = 'location'
                                     AND domain.scope_id = %s::uuid
                                     OR domain.scope_type = 'network'
                                     AND domain.scope_id IS NULL)
                          ) AS applicable_authority_domain_count
                     FROM public.governance_role AS role
                     JOIN public.governance_circle AS circle
                       ON circle.id = role.circle_id
                     LEFT JOIN public.governance_role_accountability AS accountability
                       ON accountability.role_id = role.id
                     LEFT JOIN public.governance_role_assignment AS assignment
                       ON assignment.role_id = role.id
                     LEFT JOIN public.governance_role_domain AS domain
                       ON domain.role_id = role.id
                    WHERE circle.scope_type = 'location'
                      AND circle.scope_id = %s::uuid
                      AND circle.status = ANY(%s::text[])
                      AND role.status = ANY(%s::text[])
                      AND (%s::timestamptz IS NULL OR
                           (role.created_at, role.id) < (%s::timestamptz, %s::uuid))
                    GROUP BY role.id, circle.id
                    ORDER BY role.created_at DESC, role.id DESC
                    LIMIT %s""",
                (
                    location_id,
                    location_id,
                    list(_CIRCLE_STATUSES),
                    statuses,
                    cursor_created_at,
                    cursor_created_at,
                    cursor_id,
                    page_size + 1,
                ),
            )
            rows = [_mapping(cur, row) for row in cur.fetchall()]
        has_more = len(rows) > page_size
        items = rows[:page_size]
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


def list_location_governance_tactical_items(
    operator_id: str,
    location_id: str,
    *,
    limit: str | int = 50,
    cursor: str | None = None,
    connection_factory: Callable | None = None,
) -> dict:
    """List open tactical actions without parties, notes, or disposition text."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_size(limit)
    cursor_id = _normalize_uuid(cursor, "cursor") if cursor is not None else None
    conn = _open_readonly(connection_factory or _connection_factory())
    try:
        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="governance_tactical",
            action="read",
        )
        cursor_created_at = None
        if cursor_id is not None:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT item.created_at
                         FROM public.governance_tactical_item AS item
                         JOIN public.governance_tactical_session AS session
                           ON session.id = item.session_id
                         JOIN public.governance_circle AS circle
                           ON circle.id = session.circle_id
                        WHERE item.id = %s::uuid
                          AND item.status = ANY(%s::text[])
                          AND session.status <> 'cancelled'
                          AND circle.scope_type = 'location'
                          AND circle.scope_id = %s::uuid""",
                    (cursor_id, list(_TACTICAL_STATUSES), location_id),
                )
                row = cur.fetchone()
            if row is None:
                raise GovernanceOperationsInvalid(
                    "cursor is not available in the requested location"
                )
            cursor_created_at = row[0]

        with conn.cursor() as cur:
            cur.execute(
                """SELECT item.id, item.requested_next_action, item.priority,
                          item.due_at, item.status, item.created_at,
                          session.session_type, session.title AS session_title,
                          session.scheduled_at, session.status AS session_status,
                          role.role_key AS owner_role_key
                     FROM public.governance_tactical_item AS item
                     JOIN public.governance_tactical_session AS session
                       ON session.id = item.session_id
                     JOIN public.governance_circle AS circle
                       ON circle.id = session.circle_id
                     LEFT JOIN public.governance_role AS role
                       ON role.id = item.owner_role_id
                    WHERE circle.scope_type = 'location'
                      AND circle.scope_id = %s::uuid
                      AND circle.status = ANY(%s::text[])
                      AND session.status <> 'cancelled'
                      AND item.status = ANY(%s::text[])
                      AND (%s::timestamptz IS NULL OR
                           (item.created_at, item.id) < (%s::timestamptz, %s::uuid))
                    ORDER BY item.created_at DESC, item.id DESC
                    LIMIT %s""",
                (
                    location_id,
                    list(_CIRCLE_STATUSES),
                    list(_TACTICAL_STATUSES),
                    cursor_created_at,
                    cursor_created_at,
                    cursor_id,
                    page_size + 1,
                ),
            )
            rows = [_mapping(cur, row) for row in cur.fetchall()]
        has_more = len(rows) > page_size
        items = rows[:page_size]
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
