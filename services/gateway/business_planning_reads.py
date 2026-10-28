"""Location-scoped, read-only Kernel projections for business planning."""

from __future__ import annotations

import json
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 50
_MAX_VERSION_PAGE_SIZE = 5
_MAX_VERSION_RESPONSE_BYTES = 524_288


class BusinessPlanningReadInvalid(ValueError):
    """A business planning identifier or page bound is invalid."""


class BusinessPlanningHistoryTooLarge(ValueError):
    """A version history page exceeds its bounded response size."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise BusinessPlanningReadInvalid(f"Invalid {field} identifier") from exc


def _page_value(value: int | str, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise BusinessPlanningReadInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise BusinessPlanningReadInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        ) from exc
    if str(parsed) != str(value).strip() or not minimum <= parsed <= maximum:
        raise BusinessPlanningReadInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        )
    return parsed


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def list_location_business_model_canvases(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List bounded, location-owned canvas content for one business-planning grant."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit", 1, _MAX_PAGE_SIZE)
    page_offset = _page_value(offset, "Offset", 0, 10000)

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="business_planning",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_business_model_canvases(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]

        next_offset = page_offset + page_size
        has_more = len(rows) > page_size and next_offset <= 10000
        return {
            "location_id": location_id,
            "offset": page_offset,
            "canvases": rows[:page_size],
            "has_more": has_more,
            "next_offset": next_offset if has_more else None,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_business_model_canvas_versions(
    operator_id: str,
    location_id: str,
    canvas_id: str,
    *,
    limit: int | str = 5,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded historical snapshots and current state for one canvas."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    canvas_id = _normalize_uuid(canvas_id, "canvas")
    page_size = _page_value(limit, "Limit", 1, _MAX_VERSION_PAGE_SIZE)
    page_offset = _page_value(offset, "Offset", 0, 10000)

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="business_planning",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_business_model_canvas_versions(
                           %s::uuid, %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, canvas_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]

        has_more = len(rows) > page_size
        page = rows[:page_size]
        result = {
            "location_id": location_id,
            "canvas_id": canvas_id,
            "offset": page_offset,
            "versions": page,
            "has_more": has_more,
            "next_offset": page_offset + page_size if has_more else None,
        }
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_VERSION_RESPONSE_BYTES:
            raise BusinessPlanningHistoryTooLarge("Business canvas history exceeds 512 KiB")
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
