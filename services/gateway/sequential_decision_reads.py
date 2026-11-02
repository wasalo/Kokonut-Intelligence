"""Location-scoped, aggregate-only Kernel projections for sequential decisions."""

from __future__ import annotations

import json
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class SequentialDecisionReadInvalid(ValueError):
    """A sequential decision summary identifier is invalid."""


class SequentialDecisionResponseTooLarge(ValueError):
    """A bounded sequential evidence page exceeds the response budget."""


_MAX_PAGE_SIZE = 50
_MAX_RESPONSE_BYTES = 131_072


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


def _page_value(value: int | str, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise SequentialDecisionReadInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SequentialDecisionReadInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        ) from exc
    if str(parsed) != str(value).strip() or not minimum <= parsed <= maximum:
        raise SequentialDecisionReadInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        )
    return parsed


def list_location_sequential_evidence_timeline(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded sequence metadata for evidence linked to one location."""
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
            resource="sequential_evidence",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.location_sequential_evidence_timeline(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size, page_offset),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Sequential evidence timeline returned no result")
            timeline = row[0]
            if isinstance(timeline, str):
                timeline = json.loads(timeline)
            response = {"location_id": location_id, **timeline}
            if (
                response.get("has_more") is True
                and page_offset + page_size > 10000
            ):
                response["has_more"] = False
                response["next_offset"] = None
            response_bytes = len(
                json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            )
            if response_bytes > _MAX_RESPONSE_BYTES:
                raise SequentialDecisionResponseTooLarge(
                    "Sequential evidence page exceeds the response size limit"
                )
            return response
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
