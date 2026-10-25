"""Tenant-scoped waste-stream capture through the Kernel Gateway."""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_WASTE_TYPES = {
    "crop_residue",
    "processing_waste",
    "packaging",
    "chemical_container",
    "organic_waste",
    "wastewater",
    "other",
}
_DISPOSAL_METHODS = {
    "composting",
    "burning",
    "landfill",
    "recycling",
    "animal_feed",
    "biogas",
    "mulching",
    "other",
}
_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")


class WasteManagementWriteInvalid(ValueError):
    """A waste-stream capture request is invalid or outside its bounds."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _identifier(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise WasteManagementWriteInvalid(f"Invalid {field} identifier") from exc


def _bounded_text(value, field: str, maximum: int, *, required: bool = False):
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise WasteManagementWriteInvalid(f"Invalid {field}")
    normalized = value.strip()
    if (required and not normalized) or len(normalized) > maximum or _CONTROL_CHARACTER.search(value):
        raise WasteManagementWriteInvalid(f"Invalid {field}")
    return normalized or None


def _normalize_payload(payload: dict) -> tuple:
    if not isinstance(payload, dict):
        raise WasteManagementWriteInvalid("Waste capture body must be an object")
    allowed = {
        "request_id", "waste_type", "waste_name", "quantity_kg",
        "record_date", "disposal_method", "notes",
    }
    if set(payload) != allowed:
        raise WasteManagementWriteInvalid("Waste capture fields do not match the supported contract")

    request_id = _identifier(payload["request_id"], "request")
    waste_type = payload["waste_type"]
    if not isinstance(waste_type, str) or waste_type not in _WASTE_TYPES:
        raise WasteManagementWriteInvalid("Unsupported waste type")
    waste_name = _bounded_text(payload["waste_name"], "waste name", 200, required=True)

    quantity_value = payload["quantity_kg"]
    if isinstance(quantity_value, bool) or not isinstance(quantity_value, (str, int, float, Decimal)):
        raise WasteManagementWriteInvalid("Quantity must be a positive number of kilograms")
    try:
        quantity_kg = Decimal(str(quantity_value))
    except (InvalidOperation, ValueError) as exc:
        raise WasteManagementWriteInvalid("Quantity must be a positive number of kilograms") from exc
    if (
        not quantity_kg.is_finite()
        or quantity_kg <= 0
        or quantity_kg > Decimal("99999999.99")
        or quantity_kg != quantity_kg.quantize(Decimal("0.01"))
    ):
        raise WasteManagementWriteInvalid("Quantity must be between 0 and 99999999.99 kg")
    quantity_kg = quantity_kg.quantize(Decimal("0.01"))

    date_value = payload["record_date"]
    if not isinstance(date_value, str):
        raise WasteManagementWriteInvalid("Record date must use YYYY-MM-DD")
    try:
        record_date = date.fromisoformat(date_value)
    except ValueError as exc:
        raise WasteManagementWriteInvalid("Record date must use YYYY-MM-DD") from exc
    if record_date.isoformat() != date_value or record_date > date.today():
        raise WasteManagementWriteInvalid("Record date must be today or earlier")

    disposal_method = payload["disposal_method"]
    if disposal_method is not None and (
        not isinstance(disposal_method, str) or disposal_method not in _DISPOSAL_METHODS
    ):
        raise WasteManagementWriteInvalid("Unsupported disposal method")
    notes = _bounded_text(payload["notes"], "notes", 1000)
    return (
        request_id,
        waste_type,
        waste_name,
        quantity_kg,
        record_date,
        disposal_method,
        notes,
    )


def create_location_waste_stream_record(
    operator_id: str,
    location_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create one recorded-only waste row with an exact-location create grant.

    Validation is completed before the database connection is opened. The
    SECURITY DEFINER function owns the insert and private retry receipt; the
    signed operator tenant context and exact grant are checked in PostgreSQL.
    """
    operator_id = _identifier(operator_id, "operator")
    location_id = _identifier(location_id, "location")
    normalized = _normalize_payload(payload)

    connection = (connection_factory or _connection_factory())()
    try:
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="waste_management",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.create_location_waste_stream_record("
                "%s::uuid, %s::uuid, %s::text, %s::text, %s::numeric, %s::date, "
                "%s::text, %s::text)",
                (location_id, *normalized),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Waste capture returned no record")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
            if (
                not isinstance(result, dict)
                or result.get("location_id") != location_id
                or result.get("status") != "recorded"
                or not isinstance(result.get("record_id"), str)
                or not isinstance(result.get("replayed"), bool)
            ):
                raise RuntimeError("Waste capture returned an invalid result")
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
