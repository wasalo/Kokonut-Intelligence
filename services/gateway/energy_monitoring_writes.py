"""Location-scoped energy-reading capture for the authenticated Gateway."""

from __future__ import annotations

import json
import math
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_READING_TYPES = frozenset({"consumption", "production"})
_ACTIVITY_TYPES = frozenset(
    {"irrigation", "processing", "storage", "lighting", "pump", "other"}
)
_MAX_JSON_BYTES = 16 * 1024


class EnergyReadingCaptureInvalid(ValueError):
    """A submitted reading is malformed or outside its supported bounds."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _uuid(value: object, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise EnergyReadingCaptureInvalid(f"Invalid {label} identifier") from exc


def _decimal(value: object, label: str, *, max_value: Decimal) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise EnergyReadingCaptureInvalid(f"{label} must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        raise EnergyReadingCaptureInvalid(f"{label} must be finite")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise EnergyReadingCaptureInvalid(f"{label} must be numeric") from exc
    if not result.is_finite() or abs(result) > max_value:
        raise EnergyReadingCaptureInvalid(f"{label} is outside its supported bounds")
    return result


def _json_object(value: object) -> str:
    if not isinstance(value, dict):
        raise EnergyReadingCaptureInvalid("metadata must be an object")

    def reject_nul(item):
        if isinstance(item, str):
            if "\x00" in item:
                raise EnergyReadingCaptureInvalid(
                    "metadata must not contain null characters"
                )
        elif isinstance(item, dict):
            for key, nested in item.items():
                reject_nul(key)
                reject_nul(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item:
                reject_nul(nested)

    reject_nul(value)
    try:
        encoded = json.dumps(value, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise EnergyReadingCaptureInvalid("metadata must be valid JSON") from exc
    if len(encoded.encode("utf-8")) > _MAX_JSON_BYTES:
        raise EnergyReadingCaptureInvalid("metadata exceeds 16 KiB")
    return encoded


def record_location_energy_reading(
    operator_id: str,
    location_id: str,
    payload: object,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Persist a recorded reading via migration 711's signed SQL contract.

    The SQL function verifies the exact `energy_monitoring:create` grant,
    resolves the source within the requested location, stores the reading in
    its initial `recorded` state, and appends a private idempotency receipt and
    audit event in the same transaction. This function never verifies a
    reading or changes its lifecycle state.
    """
    if not isinstance(payload, dict) or set(payload) != {
        "request_id", "source_id", "reading_date", "reading_type", "kwh",
        "cost_per_kwh", "cost_currency_code", "activity_type", "equipment_id",
        "notes", "metadata", "reason",
    }:
        raise EnergyReadingCaptureInvalid("Energy reading request fields are invalid")

    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    request_id = _uuid(payload["request_id"], "request")
    source_id = _uuid(payload["source_id"], "source")
    reading_date_value = payload["reading_date"]
    if reading_date_value is None:
        reading_date_value = date.today()
    elif isinstance(reading_date_value, str):
        try:
            reading_date_value = date.fromisoformat(reading_date_value)
        except ValueError as exc:
            raise EnergyReadingCaptureInvalid("reading_date must use YYYY-MM-DD") from exc
        if reading_date_value.isoformat() != payload["reading_date"]:
            raise EnergyReadingCaptureInvalid("reading_date must use YYYY-MM-DD")
    if not isinstance(reading_date_value, date):
        raise EnergyReadingCaptureInvalid("reading_date must use YYYY-MM-DD")

    reading_type = payload["reading_type"]
    if reading_type not in _READING_TYPES:
        raise EnergyReadingCaptureInvalid("reading_type is invalid")
    kwh = _decimal(
        payload["kwh"], "kwh", max_value=Decimal("99999999.99")
    )

    cost_per_kwh = payload["cost_per_kwh"]
    currency = payload["cost_currency_code"]
    if cost_per_kwh is None:
        if currency is not None:
            raise EnergyReadingCaptureInvalid(
                "cost_currency_code requires cost_per_kwh"
            )
        normalized_cost = None
        normalized_currency = None
    else:
        normalized_cost = _decimal(
            cost_per_kwh, "cost_per_kwh", max_value=Decimal("9999.9999")
        )
        normalized_currency = str(currency or "").strip().upper()
        if len(normalized_currency) != 3 or not normalized_currency.isalpha() or not normalized_currency.isascii():
            raise EnergyReadingCaptureInvalid(
                "cost_currency_code must be three uppercase letters"
            )

    activity_type = payload["activity_type"]
    if activity_type is not None and activity_type not in _ACTIVITY_TYPES:
        raise EnergyReadingCaptureInvalid("activity_type is invalid")
    equipment_id = (
        _uuid(payload["equipment_id"], "equipment")
        if payload["equipment_id"] is not None
        else None
    )
    notes = payload["notes"]
    if notes is not None and (not isinstance(notes, str) or len(notes) > 2000 or "\x00" in notes):
        raise EnergyReadingCaptureInvalid("notes exceed their supported bounds")
    reason = payload["reason"]
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 2000 or "\x00" in reason:
        raise EnergyReadingCaptureInvalid("reason must contain 1 to 2000 characters")
    metadata = _json_object(payload["metadata"])

    connection = (connection_factory or _connection_factory())()
    committed = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="energy_monitoring",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.record_location_energy_reading(
                           %s::uuid, %s::uuid, %s::uuid, %s::date, %s::text,
                           %s::numeric, %s::numeric, %s::text, %s::text,
                           %s::uuid, %s::text, %s::jsonb, %s::text
                       )""",
                (
                    location_id,
                    source_id,
                    request_id,
                    reading_date_value,
                    reading_type,
                    kwh,
                    normalized_cost,
                    normalized_currency,
                    activity_type,
                    equipment_id,
                    notes,
                    metadata,
                    reason.strip(),
                ),
            )
            row = cursor.fetchone()
        if not row or row[0] is None:
            raise RuntimeError("Energy reading capture returned no receipt")
        result = row[0]
        if isinstance(result, str):
            result = json.loads(result)
        if not isinstance(result, dict):
            raise RuntimeError("Energy reading capture returned an invalid receipt")
        expected = {
            "location_id": location_id,
            "source_id": source_id,
            "request_id": request_id,
            "reading_date": reading_date_value.isoformat(),
            "reading_type": reading_type,
            "status": "recorded",
        }
        for name, expected_value in expected.items():
            actual = result.get(name)
            if name.endswith("_id"):
                try:
                    actual = _uuid(actual, name)
                except EnergyReadingCaptureInvalid as exc:
                    raise RuntimeError(
                        "Energy reading receipt does not match the request"
                    ) from exc
            if actual != expected_value:
                raise RuntimeError("Energy reading receipt does not match the request")
        if not isinstance(result.get("replayed"), bool):
            raise RuntimeError("Energy reading replay marker is invalid")
        try:
            reading_id = _uuid(result.get("reading_id"), "reading")
        except EnergyReadingCaptureInvalid as exc:
            raise RuntimeError("Energy reading receipt has an invalid reading ID") from exc
        result["reading_id"] = reading_id
        if not isinstance(result.get("created_at"), str):
            raise RuntimeError("Energy reading timestamp is invalid")
        connection.commit()
        committed = True
        return result
    finally:
        if not committed:
            connection.rollback()
        connection.close()
