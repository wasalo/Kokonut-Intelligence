"""Location-scoped, read-only Kernel projections for management workflows."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class ManagementWorkReadInvalid(ValueError):
    """A management summary location identifier is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ManagementWorkReadInvalid("Invalid location identifier") from exc


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def location_management_work_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return workload, SLA, claim, and escalation counts for one location."""
    try:
        operator_id = str(UUID(operator_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ManagementWorkReadInvalid("Invalid operator identifier") from exc
    location_id = _normalize_uuid(location_id)

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
            resource="management_workflow",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM kokonut_security.location_management_work_summary(%s::uuid)",
                (location_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("management summary returned no row")
            result = _mapping(cursor, row)
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
