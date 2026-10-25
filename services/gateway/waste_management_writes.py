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
_COMPOST_FEEDSTOCK_TYPES = {
    "crop_residue", "manure", "food_waste", "green_waste", "mixed", "other",
}
_COMPOST_METHODS = {"heap", "pit", "vermiculture", "bokashi", "other"}
_RECYCLING_MATERIAL_TYPES = {"plastic", "metal", "glass", "paper", "organic", "other"}
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


def _bounded_decimal(value, field: str, *, minimum: Decimal, maximum: Decimal, places: int):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise WasteManagementWriteInvalid(f"Invalid {field}")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise WasteManagementWriteInvalid(f"Invalid {field}") from exc
    quantum = Decimal(1).scaleb(-places)
    if (
        not number.is_finite()
        or number < minimum
        or number > maximum
        or number.as_tuple().exponent < -places
        or number != number.quantize(quantum)
    ):
        raise WasteManagementWriteInvalid(f"Invalid {field}")
    return number.quantize(quantum)


def _normalize_composting_payload(payload: dict) -> tuple:
    if not isinstance(payload, dict):
        raise WasteManagementWriteInvalid("Composting body must be an object")
    allowed = {
        "request_id", "compost_date", "feedstock_type", "feedstock_kg",
        "compost_method", "temperature_c", "moisture_pct", "duration_days",
        "output_kg", "ph", "notes",
    }
    if set(payload) != allowed:
        raise WasteManagementWriteInvalid("Composting fields do not match the supported contract")

    request_id = _identifier(payload["request_id"], "request")
    compost_date_value = payload["compost_date"]
    if not isinstance(compost_date_value, str):
        raise WasteManagementWriteInvalid("Composting date must use YYYY-MM-DD")
    try:
        compost_date = date.fromisoformat(compost_date_value)
    except ValueError as exc:
        raise WasteManagementWriteInvalid("Composting date must use YYYY-MM-DD") from exc
    if compost_date.isoformat() != compost_date_value or compost_date > date.today():
        raise WasteManagementWriteInvalid("Composting date must be today or earlier")

    source_feedstock_type = _bounded_text(
        payload["feedstock_type"], "compost feedstock type", 200, required=True
    )
    feedstock_key = re.sub(r"[\s-]+", "_", source_feedstock_type.lower())
    feedstock_type = (
        feedstock_key if feedstock_key in _COMPOST_FEEDSTOCK_TYPES else "other"
    )
    feedstock_label = source_feedstock_type if feedstock_key != feedstock_type else None

    source_compost_method = _bounded_text(
        payload["compost_method"], "compost method", 100, required=True
    )
    method_key = re.sub(r"[\s-]+", "_", source_compost_method.lower())
    method_aliases = {"vermicomposting": "vermiculture"}
    compost_method = method_aliases.get(method_key, method_key)
    if compost_method not in _COMPOST_METHODS:
        compost_method = "other"
    compost_method_label = (
        source_compost_method if method_key != compost_method else None
    )
    feedstock_kg = _bounded_decimal(
        payload["feedstock_kg"], "feedstock quantity",
        minimum=Decimal("0.01"), maximum=Decimal("99999999.99"), places=2,
    )
    temperature_c = _bounded_decimal(
        payload["temperature_c"], "temperature",
        minimum=Decimal("-100"), maximum=Decimal("200"), places=1,
    )
    moisture_pct = _bounded_decimal(
        payload["moisture_pct"], "moisture",
        minimum=Decimal("0"), maximum=Decimal("100"), places=1,
    )
    output_kg = _bounded_decimal(
        payload["output_kg"], "finished compost quantity",
        minimum=Decimal("0"), maximum=Decimal("99999999.99"), places=2,
    )
    ph = _bounded_decimal(
        payload["ph"], "pH", minimum=Decimal("0"), maximum=Decimal("14"), places=2,
    )
    duration_days = payload["duration_days"]
    if duration_days is not None and (
        isinstance(duration_days, bool)
        or not isinstance(duration_days, int)
        or duration_days < 0
        or duration_days > 36500
    ):
        raise WasteManagementWriteInvalid("Invalid compost duration")
    notes = _bounded_text(payload["notes"], "notes", 1000)
    return (
        request_id,
        compost_date,
        feedstock_type,
        feedstock_label,
        feedstock_kg,
        compost_method,
        compost_method_label,
        temperature_c,
        moisture_pct,
        duration_days,
        output_kg,
        ph,
        notes,
    )


def _normalize_recycling_payload(payload: dict) -> tuple:
    if not isinstance(payload, dict):
        raise WasteManagementWriteInvalid("Recycling body must be an object")
    allowed = {
        "request_id", "record_date", "material_type", "quantity_kg",
        "destination", "revenue", "notes",
    }
    if set(payload) != allowed:
        raise WasteManagementWriteInvalid("Recycling fields do not match the supported contract")

    request_id = _identifier(payload["request_id"], "request")
    record_date_value = payload["record_date"]
    if not isinstance(record_date_value, str):
        raise WasteManagementWriteInvalid("Recycling date must use YYYY-MM-DD")
    try:
        record_date = date.fromisoformat(record_date_value)
    except ValueError as exc:
        raise WasteManagementWriteInvalid("Recycling date must use YYYY-MM-DD") from exc
    if record_date.isoformat() != record_date_value or record_date > date.today():
        raise WasteManagementWriteInvalid("Recycling date must be today or earlier")

    source_material_type = _bounded_text(
        payload["material_type"], "recycling material type", 100, required=True
    )
    material_key = re.sub(r"[\s-]+", "_", source_material_type.lower())
    material_type = (
        material_key if material_key in _RECYCLING_MATERIAL_TYPES else "other"
    )
    material_label = source_material_type if material_key != material_type else None
    quantity_kg = _bounded_decimal(
        payload["quantity_kg"], "recycling quantity",
        minimum=Decimal("0.01"), maximum=Decimal("99999999.99"), places=2,
    )
    destination = _bounded_text(payload["destination"], "recycling destination", 200, required=True)
    revenue = _bounded_decimal(
        payload["revenue"], "recycling revenue",
        minimum=Decimal("-99999999.99"), maximum=Decimal("99999999.99"), places=2,
    )
    notes = _bounded_text(payload["notes"], "notes", 1000)
    return (
        request_id,
        record_date,
        material_type,
        material_label,
        quantity_kg,
        destination,
        revenue,
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
            connection.commit()
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_location_composting_record(
    operator_id: str,
    location_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create one recorded-only compost batch under an exact create grant."""
    operator_id = _identifier(operator_id, "operator")
    location_id = _identifier(location_id, "location")
    normalized = _normalize_composting_payload(payload)

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
                "SELECT kokonut_security.create_location_composting_record("
                "%s::uuid, %s::uuid, %s::date, %s::text, %s::text, %s::numeric, "
                "%s::text, %s::text, %s::numeric, %s::numeric, %s::integer, "
                "%s::numeric, %s::numeric, %s::text)",
                (location_id, *normalized),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Composting capture returned no record")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
            if (
                not isinstance(result, dict)
                or result.get("location_id") != location_id
                or not isinstance(result.get("compost_date"), str)
                or result.get("status") != "recorded"
                or not isinstance(result.get("record_id"), str)
                or not isinstance(result.get("replayed"), bool)
            ):
                raise RuntimeError("Composting capture returned an invalid result")
            connection.commit()
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_location_recycling_record(
    operator_id: str,
    location_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create one recorded-only recycling row under an exact create grant."""
    operator_id = _identifier(operator_id, "operator")
    location_id = _identifier(location_id, "location")
    normalized = _normalize_recycling_payload(payload)

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
                "SELECT kokonut_security.create_location_recycling_record("
                "%s::uuid, %s::uuid, %s::date, %s::text, %s::text, "
                "%s::numeric, %s::text, %s::numeric, %s::text)",
                (location_id, *normalized),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Recycling capture returned no record")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
            if (
                not isinstance(result, dict)
                or result.get("location_id") != location_id
                or not isinstance(result.get("record_date"), str)
                or result.get("status") != "recorded"
                or not isinstance(result.get("record_id"), str)
                or not isinstance(result.get("replayed"), bool)
            ):
                raise RuntimeError("Recycling capture returned an invalid result")
            connection.commit()
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
