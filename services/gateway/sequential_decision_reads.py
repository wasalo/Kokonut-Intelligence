"""Location-scoped, aggregate-only Kernel projections for sequential decisions."""

from __future__ import annotations

import json
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class SequentialDecisionReadInvalid(ValueError):
    """A sequential decision summary identifier is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise SequentialDecisionReadInvalid(f"Invalid {field} identifier") from exc


def get_location_sequential_decision_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return aggregate evidence and latest action counts for one location."""
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
            resource="sequential_evidence",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.location_sequential_decision_summary(%s::uuid)",
                (location_id,),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Sequential decision summary returned no result")
            summary = row[0]
            if isinstance(summary, str):
                summary = json.loads(summary)
            return {"location_id": location_id, **summary}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
