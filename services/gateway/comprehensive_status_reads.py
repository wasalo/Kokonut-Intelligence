"""Location-scoped, read-only Comprehensive Status projection for the Gateway."""

from __future__ import annotations

import json
from datetime import date
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

MAX_COMPREHENSIVE_STATUS_BYTES = 524_288


class ComprehensiveStatusReadInvalid(ValueError):
    """A Comprehensive Status identifier or period is invalid."""


class ComprehensiveStatusPayloadTooLarge(ValueError):
    """The generated report exceeds the bounded Gateway response size."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ComprehensiveStatusReadInvalid(f"Invalid {field} identifier") from exc


def _period_date(value: str | None, field: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ComprehensiveStatusReadInvalid(f"{field} must use YYYY-MM-DD format")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ComprehensiveStatusReadInvalid(f"{field} must use YYYY-MM-DD format") from exc
    if parsed.isoformat() != value:
        raise ComprehensiveStatusReadInvalid(f"{field} must use YYYY-MM-DD format")
    return value


def get_location_comprehensive_status(
    operator_id: str,
    location_id: str,
    *,
    period_start: str | None = None,
    period_end: str | None = None,
    connection_factory: Callable | None = None,
) -> dict:
    """Generate the legacy 14-section report inside an exact read grant.

    The operator's database-signed tenant context is established before any
    report query. The existing generators are read-only and receive exactly
    one validated location; network-wide mode is not exposed by this method.
    """
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    period_start = _period_date(period_start, "period_start")
    period_end = _period_date(period_end, "period_end")
    if period_start and period_end and period_start > period_end:
        raise ComprehensiveStatusReadInvalid("period_start must not be after period_end")

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
            resource="comprehensive_status",
            action="read",
        )

        from services.export.reports.state import generate_comprehensive_status

        report = generate_comprehensive_status(
            connection,
            location_id=location_id,
            period_start=period_start,
            period_end=period_end,
        )
        encoded_size = len(json.dumps(report, default=str, separators=(",", ":")).encode("utf-8"))
        if encoded_size > MAX_COMPREHENSIVE_STATUS_BYTES:
            raise ComprehensiveStatusPayloadTooLarge(
                "Comprehensive Status exceeds the 512 KiB response limit"
            )
        return report
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
