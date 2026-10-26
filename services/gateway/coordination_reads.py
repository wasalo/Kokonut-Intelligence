"""Location-scoped, read-only Kernel coordination governance projection."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class CoordinationReadInvalid(ValueError):
    """A coordination summary identifier is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise CoordinationReadInvalid(f"Invalid {field} identifier") from exc


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def get_location_coordination_governance_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Read aggregate alliance integrity and learning state for one location."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
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
            resource="coordination",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM kokonut_security.location_coordination_governance_summary(%s::uuid)",
                (location_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Coordination summary returned no result")
            return {"location_id": location_id, **_mapping(cursor, row)}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
