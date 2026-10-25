"""Tenant-scoped, recorded-only pollinator observation capture."""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_POLLINATOR_TYPES = {
    "honeybee", "wild_bee", "butterfly", "moth", "beetle", "fly", "bird", "bat", "other",
}
_OBSERVATION_METHODS = {"transect", "pan_trap", "visual_count", "hive_weight", "other"}
_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")


class PollinatorObservationInvalid(ValueError):
    """A pollinator observation request is invalid or outside its bounds."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _identifier(value, field: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise PollinatorObservationInvalid(f"Invalid {field} identifier") from exc


def _text(value, field: str, maximum: int, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise PollinatorObservationInvalid(f"Invalid {field}")
    normalized = value.strip()
    if len(normalized) > maximum or _CONTROL_CHARACTER.search(value):
        raise PollinatorObservationInvalid(f"Invalid {field}")
    return normalized or None


def _integer(value, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 2_147_483_647:
        raise PollinatorObservationInvalid(f"{field} must be a non-negative integer")
    return value


def _temperature(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise PollinatorObservationInvalid("Temperature must be between -100 and 100 °C")
    try:
        temperature = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PollinatorObservationInvalid("Temperature must be between -100 and 100 °C") from exc
    if not temperature.is_finite() or not Decimal("-100") <= temperature <= Decimal("100"):
        raise PollinatorObservationInvalid("Temperature must be between -100 and 100 °C")
    return temperature


def _weather(value) -> dict:
    if value is None:
        return {}
    if isinstance(value, str):
        normalized = _text(value, "weather description", 500)
        return {"description": normalized} if normalized else {}
    if not isinstance(value, dict):
        raise PollinatorObservationInvalid("Weather conditions must be an object or description")
    try:
        encoded = json.dumps(value, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise PollinatorObservationInvalid("Weather conditions must be a JSON object") from exc
    if len(encoded.encode("utf-8")) > 4096:
        raise PollinatorObservationInvalid("Weather conditions exceed 4 KB")
    return value


def _normalize_payload(payload: dict) -> tuple:
    if not isinstance(payload, dict):
        raise PollinatorObservationInvalid("Pollinator observation body must be an object")
    allowed = {
        "request_id", "pollinator_type", "count", "observation_method",
        "duration_minutes", "plot_id", "observation_date", "species_name",
        "weather_conditions", "temperature_c", "hive_record_id", "notes",
    }
    if set(payload) != allowed:
        raise PollinatorObservationInvalid(
            "Pollinator observation fields do not match the supported contract"
        )
    request_id = _identifier(payload["request_id"], "request")
    pollinator_type = payload["pollinator_type"]
    if not isinstance(pollinator_type, str) or pollinator_type not in _POLLINATOR_TYPES:
        raise PollinatorObservationInvalid("Unsupported pollinator type")
    observation_method = payload["observation_method"]
    if not isinstance(observation_method, str) or observation_method not in _OBSERVATION_METHODS:
        raise PollinatorObservationInvalid("Unsupported observation method")

    count = _integer(payload["count"], "Observation count")
    duration = _integer(payload["duration_minutes"], "Observation duration")
    observation_date = payload["observation_date"]
    if observation_date is None:
        observed_on = date.today()
    elif isinstance(observation_date, str):
        try:
            observed_on = date.fromisoformat(observation_date)
        except ValueError as exc:
            raise PollinatorObservationInvalid("Observation date must use YYYY-MM-DD") from exc
        if observed_on.isoformat() != observation_date:
            raise PollinatorObservationInvalid("Observation date must use YYYY-MM-DD")
    else:
        raise PollinatorObservationInvalid("Observation date must use YYYY-MM-DD")

    temperature = _temperature(payload["temperature_c"])
    return (
        request_id,
        pollinator_type,
        count,
        observation_method,
        duration,
        _identifier(payload["plot_id"], "plot", optional=True),
        observed_on,
        _text(payload["species_name"], "species name", 200, optional=True),
        _weather(payload["weather_conditions"]),
        temperature,
        _identifier(payload["hive_record_id"], "hive", optional=True),
        _text(payload["notes"], "notes", 2000, optional=True),
    )


def create_location_pollinator_observation(
    operator_id: str,
    location_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create one recorded observation with an exact-location create grant.

    Validation completes before database access. PostgreSQL checks signed
    operator context, the exact create grant, and location-bound plot/hive links;
    its private receipt makes a same-request retry idempotent.
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
            resource="pollinator_health",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.create_location_pollinator_observation("
                "%s::uuid, %s::uuid, %s::text, %s::integer, %s::text, "
                "%s::integer, %s::uuid, %s::date, %s::text, %s::jsonb, "
                "%s::numeric, %s::uuid, %s::text)",
                (location_id, *normalized[:8], json.dumps(normalized[8]), *normalized[9:]),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Pollinator capture returned no observation")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
            if (
                not isinstance(result, dict)
                or result.get("location_id") != location_id
                or result.get("status") != "recorded"
                or result.get("pollinator_type") != normalized[1]
                or result.get("count") != normalized[2]
                or not isinstance(result.get("observation_id"), str)
                or not isinstance(result.get("replayed"), bool)
            ):
                raise RuntimeError("Pollinator capture returned an invalid result")
            connection.commit()
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
