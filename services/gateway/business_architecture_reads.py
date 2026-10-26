"""Location-scoped, read-only Kernel projections for business architecture."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 50


class BusinessArchitectureReadInvalid(ValueError):
    """A business architecture identifier or page bound is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise BusinessArchitectureReadInvalid(f"Invalid {field} identifier") from exc


def _page_value(value: int | str, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise BusinessArchitectureReadInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise BusinessArchitectureReadInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        ) from exc
    if str(parsed) != str(value).strip() or not minimum <= parsed <= maximum:
        raise BusinessArchitectureReadInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        )
    return parsed


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def get_location_business_architecture_summary(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Read approved location mission and roadmap mappings for one grant."""
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
            resource="business_architecture",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_business_architecture_missions(
                           %s::uuid
                       )""",
                (location_id,),
            )
            missions = [_mapping(cursor, row) for row in cursor.fetchall()]
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_business_architecture_mappings(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]

        has_more = len(rows) > page_size
        return {
            "location_id": location_id,
            "offset": page_offset,
            "missions": missions,
            "mappings": rows[:page_size],
            "has_more": has_more,
            "next_offset": page_offset + page_size if has_more else None,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
