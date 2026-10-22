"""Location-scoped, aggregate-only Kernel projections for operating pilots."""

from __future__ import annotations

import json
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class OperatingPilotReadInvalid(ValueError):
    """An operating-pilot summary identifier is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise OperatingPilotReadInvalid(f"Invalid {field} identifier") from exc


def _normalize_page(limit: int, offset: int) -> tuple[int, int]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise OperatingPilotReadInvalid("Page limit must be between 1 and 50")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 10000:
        raise OperatingPilotReadInvalid("Page offset must be between 0 and 10000")
    return limit, offset


def get_location_operating_pilot_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return aggregate Adelphi operating health for one active pilot location."""
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
            resource="operating_pilot",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.location_operating_pilot_summary(%s::uuid)",
                (location_id,),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating pilot summary returned no result")
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


def get_location_operating_pilot_demand_signals(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return a bounded, redacted demand page for an active Adelphi location."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    limit, offset = _normalize_page(limit, offset)
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
            resource="operating_pilot",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.location_operating_pilot_demand_signals("
                "%s::uuid, %s::integer, %s::integer)",
                (location_id, limit, offset),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating demand read returned no result")
            page = row[0]
            if isinstance(page, str):
                page = json.loads(page)
            return {"location_id": location_id, **page}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_operating_pilot_capacity_periods(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded period totals from submitted/approved capacity profiles."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    limit, offset = _normalize_page(limit, offset)
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
            resource="operating_pilot",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.location_operating_pilot_capacity_periods("
                "%s::uuid, %s::integer, %s::integer)",
                (location_id, limit, offset),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating capacity read returned no result")
            page = row[0]
            if isinstance(page, str):
                page = json.loads(page)
            return {"location_id": location_id, **page}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_operating_pilot_own_capacity_profiles(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return a bounded page of only the authenticated operator's own records."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    limit, offset = _normalize_page(limit, offset)
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
            resource="operating_pilot",
            action="read_own",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.location_operating_pilot_own_capacity_profiles("
                "%s::uuid, %s::integer, %s::integer)",
                (location_id, limit, offset),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Own operating capacity read returned no result")
            page = row[0]
            if isinstance(page, str):
                page = json.loads(page)
            return {"location_id": location_id, **page}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_operating_pilot_own_demand_signals(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return a bounded page of receipt-backed demand records owned by the operator."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    limit, offset = _normalize_page(limit, offset)
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
            resource="operating_pilot",
            action="read_own",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.location_operating_pilot_own_demand_signals("
                "%s::uuid, %s::integer, %s::integer)",
                (location_id, limit, offset),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Own operating demand read returned no result")
            page = row[0]
            if isinstance(page, str):
                page = json.loads(page)
            return {"location_id": location_id, **page}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_operating_pilot_capacity_review_queue(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return submitted capacity records for independent, location-scoped review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    limit, offset = _normalize_page(limit, offset)
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
            resource="operating_pilot",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.location_operating_pilot_capacity_review_queue("
                "%s::uuid, %s::integer, %s::integer)",
                (location_id, limit, offset),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating capacity review queue returned no result")
            page = row[0]
            if isinstance(page, str):
                page = json.loads(page)
            return {"location_id": location_id, **page}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_operating_pilot_demand_review_queue(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded, redacted submitted demand for independent review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    limit, offset = _normalize_page(limit, offset)
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
            resource="operating_pilot",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.location_operating_pilot_demand_review_queue("
                "%s::uuid, %s::integer, %s::integer)",
                (location_id, limit, offset),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating demand review queue returned no result")
            page = row[0]
            if isinstance(page, str):
                page = json.loads(page)
            return {"location_id": location_id, **page}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_operating_pilot_work_claims(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded, suppressed claim totals by fixed safe work-type bucket."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    limit, offset = _normalize_page(limit, offset)
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
            resource="operating_pilot",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.location_operating_pilot_work_claims("
                "%s::uuid, %s::integer, %s::integer)",
                (location_id, limit, offset),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating work-claim read returned no result")
            page = row[0]
            if isinstance(page, str):
                page = json.loads(page)
            return {"location_id": location_id, **page}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_operating_pilot_work_opportunities(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded work opportunities and only the operator's own claim state."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    limit, offset = _normalize_page(limit, offset)
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
            resource="operating_pilot",
            action="claim_own",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.location_operating_pilot_work_opportunities("
                "%s::uuid, %s::integer, %s::integer)",
                (location_id, limit, offset),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating work-opportunity read returned no result")
            page = row[0]
            if isinstance(page, str):
                page = json.loads(page)
            return {"location_id": location_id, **page}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_operating_pilot_resource_categories(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded, suppressed resource-request category totals."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    limit, offset = _normalize_page(limit, offset)
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
            resource="operating_pilot",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.location_operating_pilot_resource_categories("
                "%s::uuid, %s::integer, %s::integer)",
                (location_id, limit, offset),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating resource read returned no result")
            page = row[0]
            if isinstance(page, str):
                page = json.loads(page)
            return {"location_id": location_id, **page}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
