"""Tenant-scoped, human-reviewed solution lifecycle actions."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class SolutionLifecycleActionInvalid(ValueError):
    """A solution lifecycle action identifier or payload is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise SolutionLifecycleActionInvalid(f"Invalid {field} identifier") from exc


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def approve_location_solution_retirement(
    operator_id: str,
    location_id: str,
    retirement_id: str,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Approve a location-originated retirement with an idempotent review receipt."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    retirement_id = _normalize_uuid(retirement_id, "retirement")
    request_id = _normalize_uuid(request_id, "request")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.approve_location_solution_retirement(
                           %s::uuid, %s::uuid, %s::uuid
                       )""",
                (location_id, retirement_id, request_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution retirement approval returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
