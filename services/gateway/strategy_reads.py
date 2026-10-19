"""Location-scoped, read-only Kernel projections for strategy plans."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 100


class StrategyReadInvalid(ValueError):
    """A strategy identifier or page bound is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise StrategyReadInvalid(f"Invalid {field} identifier") from exc


def _page_value(value: int | str, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise StrategyReadInvalid(f"{field} must be an integer between {minimum} and {maximum}")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise StrategyReadInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        ) from exc
    if str(parsed) != str(value).strip() or not minimum <= parsed <= maximum:
        raise StrategyReadInvalid(f"{field} must be an integer between {minimum} and {maximum}")
    return parsed


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def list_location_strategy_plan_summaries(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 50,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List bounded plan metadata and execution counts for one granted location."""
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
            resource="strategy",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_strategy_plan_summaries(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]

        has_more = len(rows) > page_size
        plans = rows[:page_size]
        return {
            "location_id": location_id,
            "offset": page_offset,
            "plans": plans,
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
