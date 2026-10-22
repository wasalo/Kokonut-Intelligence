"""Authenticated, exact-location draft actions for operating-pilot data."""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Any, Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_WORK_TYPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _./-]{0,49}$")
_PRIORITIES = {"low", "medium", "high", "critical"}


class OperatingPilotWriteInvalid(ValueError):
    """A demand draft does not satisfy the bounded write contract."""


def _normalize_uuid(value: Any, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise OperatingPilotWriteInvalid(f"Invalid {field} identifier") from exc


def _normalize_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise OperatingPilotWriteInvalid(f"{field} must be an ISO date")
    try:
        normalized = date.fromisoformat(value)
    except ValueError as exc:
        raise OperatingPilotWriteInvalid(f"{field} must be an ISO date") from exc
    if normalized.isoformat() != value:
        raise OperatingPilotWriteInvalid(f"{field} must be an ISO date")
    return normalized


def _normalize_demand_payload(payload: Any) -> tuple[str, date, date, Decimal, str, str | None]:
    if not isinstance(payload, dict):
        raise OperatingPilotWriteInvalid("Demand draft body must be an object")
    work_type = payload.get("work_type")
    if not isinstance(work_type, str) or not _WORK_TYPE.fullmatch(work_type.strip()):
        raise OperatingPilotWriteInvalid("Work type must be 1 to 50 safe characters")
    work_type = work_type.strip()
    start = _normalize_date(payload.get("period_start"), "period_start")
    end = _normalize_date(payload.get("period_end"), "period_end")
    if end < start or (end - start).days > 366:
        raise OperatingPilotWriteInvalid("Demand period must be ordered and no longer than 367 days")
    hours = payload.get("required_hours")
    if isinstance(hours, bool) or not isinstance(hours, (int, float, str, Decimal)):
        raise OperatingPilotWriteInvalid("Required hours must be a positive decimal")
    try:
        required_hours = Decimal(str(hours))
    except (InvalidOperation, ValueError) as exc:
        raise OperatingPilotWriteInvalid("Required hours must be a positive decimal") from exc
    if (
        not required_hours.is_finite()
        or required_hours <= 0
        or required_hours > Decimal("100000")
        or required_hours.as_tuple().exponent < -2
    ):
        raise OperatingPilotWriteInvalid(
            "Required hours must be positive, at most 100000, and use at most two decimals"
        )
    priority = payload.get("priority", "medium")
    if not isinstance(priority, str) or priority not in _PRIORITIES:
        raise OperatingPilotWriteInvalid("Priority must be low, medium, high, or critical")
    description = payload.get("description")
    if description is not None:
        if not isinstance(description, str) or len(description) > 2000 or "\x00" in description:
            raise OperatingPilotWriteInvalid("Description must be text of at most 2000 characters")
        description = description.strip() or None
    unexpected = set(payload) - {"work_type", "period_start", "period_end", "required_hours", "priority", "description"}
    if unexpected:
        raise OperatingPilotWriteInvalid("Demand draft contains unsupported fields")
    return work_type, start, end, required_hours, priority, description


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def create_location_operating_pilot_demand_draft(
    operator_id: str,
    location_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create or replay a private draft; this action cannot submit or approve it."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    request_id = _normalize_uuid(request_id, "request")
    work_type, start, end, hours, priority, description = _normalize_demand_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.create_location_operating_pilot_demand_draft(
                           %s::uuid, %s::uuid, %s::text, %s::date, %s::date,
                           %s::numeric, %s::text, %s::text)""",
                (location_id, request_id, work_type, start, end, hours, priority, description),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot demand draft returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
