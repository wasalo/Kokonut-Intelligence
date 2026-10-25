"""Tenant-scoped, recorded-only pollinator observation capture."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_POLLINATOR_TYPES = {
    "honeybee", "wild_bee", "butterfly", "moth", "beetle", "fly", "bird", "bat", "other",
}
_POLLINATOR_HABITAT_TYPES = {
    "wildflower_strip", "hedgerow", "nesting_site", "water_source",
    "cover_crop", "native_planting", "other",
}
_OBSERVATION_METHODS = {"transect", "pan_trap", "visual_count", "hive_weight", "other"}
_POLLINATOR_HABITAT_STATUSES = {"active", "inactive", "degraded", "removed"}
_POLLINATOR_HABITAT_CONDITIONS = {"excellent", "good", "fair", "poor"}
_POLLINATOR_HIVE_STATUSES = {"active", "inactive", "decommissioned"}
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


def _optional_decimal(value, field: str, *, maximum: Decimal) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise PollinatorObservationInvalid(f"Invalid {field}")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PollinatorObservationInvalid(f"Invalid {field}") from exc
    if not number.is_finite() or not Decimal("0") <= number <= maximum:
        raise PollinatorObservationInvalid(f"Invalid {field}")
    return number


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


def _normalize_pesticide_payload(payload: dict) -> tuple:
    if not isinstance(payload, dict):
        raise PollinatorObservationInvalid("Pesticide report body must be an object")
    allowed = {
        "request_id", "application_date", "product_name", "active_ingredient",
        "toxicity_class", "application_rate", "rate_unit", "area_treated_m2",
        "bloom_stage_at_application", "pollinator_distance_m",
        "pollinator_safe_period_days", "pollinator_mortality_observed",
        "mortality_pct", "notes",
    }
    if set(payload) != allowed:
        raise PollinatorObservationInvalid("Pesticide report fields do not match the supported contract")
    request_id = _identifier(payload["request_id"], "request")
    application_date = payload["application_date"]
    if not isinstance(application_date, str):
        raise PollinatorObservationInvalid("Application date must use YYYY-MM-DD")
    try:
        applied_on = date.fromisoformat(application_date)
    except ValueError as exc:
        raise PollinatorObservationInvalid("Application date must use YYYY-MM-DD") from exc
    if applied_on.isoformat() != application_date or applied_on > date.today():
        raise PollinatorObservationInvalid("Application date must be a completed date in YYYY-MM-DD format")
    toxicity = payload["toxicity_class"]
    if not isinstance(toxicity, str) or toxicity not in {"low", "moderate", "high", "very_high"}:
        raise PollinatorObservationInvalid("Unsupported toxicity class")
    mortality_observed = payload["pollinator_mortality_observed"]
    if not isinstance(mortality_observed, bool):
        raise PollinatorObservationInvalid("Mortality observed must be a boolean")
    safe_period = payload["pollinator_safe_period_days"]
    if safe_period is not None and (
        isinstance(safe_period, bool) or not isinstance(safe_period, int) or not 0 <= safe_period <= 36500
    ):
        raise PollinatorObservationInvalid("Safe-period days must be between 0 and 36500")
    mortality_pct = _optional_decimal(
        payload["mortality_pct"], "mortality percentage", maximum=Decimal("100")
    )
    rate_unit = _text(payload["rate_unit"], "rate unit", 32, optional=True)
    application_rate = _optional_decimal(
        payload["application_rate"], "application rate", maximum=Decimal("99999999")
    )
    if application_rate is None and rate_unit is not None:
        raise PollinatorObservationInvalid("A rate unit requires an application rate")
    return (
        request_id,
        applied_on,
        _text(payload["product_name"], "product name", 200, optional=True),
        _text(payload["active_ingredient"], "active ingredient", 200, optional=True),
        toxicity,
        application_rate,
        rate_unit,
        _optional_decimal(payload["area_treated_m2"], "treated area", maximum=Decimal("9999999999")),
        _text(payload["bloom_stage_at_application"], "bloom stage", 100, optional=True),
        _optional_decimal(payload["pollinator_distance_m"], "pollinator distance", maximum=Decimal("99999999")),
        safe_period,
        mortality_observed,
        mortality_pct,
        _text(payload["notes"], "notes", 2000, optional=True),
    )


def create_location_pesticide_impact(
    operator_id: str,
    location_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Record a location-scoped pesticide report without making a safety decision."""
    operator_id = _identifier(operator_id, "operator")
    location_id = _identifier(location_id, "location")
    normalized = _normalize_pesticide_payload(payload)

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
                "SELECT kokonut_security.create_location_pesticide_impact("
                "%s::uuid, %s::uuid, %s::date, %s::text, %s::text, %s::text, "
                "%s::numeric, %s::text, %s::numeric, %s::text, %s::numeric, "
                "%s::integer, %s::boolean, %s::numeric, %s::text)",
                (location_id, *normalized),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Pesticide report capture returned no record")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
            if (
                not isinstance(result, dict)
                or result.get("location_id") != location_id
                or result.get("status") != "recorded"
                or result.get("toxicity_class") != normalized[4]
                or not isinstance(result.get("record_id"), str)
                or not isinstance(result.get("replayed"), bool)
            ):
                raise RuntimeError("Pesticide report capture returned an invalid result")
            connection.commit()
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _normalize_habitat_payload(payload: dict) -> tuple:
    if not isinstance(payload, dict):
        raise PollinatorObservationInvalid("Habitat report body must be an object")
    allowed = {
        "request_id", "habitat_name", "habitat_type", "area_m2", "plant_species",
        "bloom_start_month", "bloom_end_month", "water_source", "nesting_sites", "notes",
    }
    if set(payload) != allowed:
        raise PollinatorObservationInvalid("Habitat report fields do not match the supported contract")
    request_id = _identifier(payload["request_id"], "request")
    habitat_name = _text(payload["habitat_name"], "habitat name", 200)
    if not habitat_name:
        raise PollinatorObservationInvalid("Habitat name is required")
    habitat_type = payload["habitat_type"]
    if not isinstance(habitat_type, str) or habitat_type not in _POLLINATOR_HABITAT_TYPES:
        raise PollinatorObservationInvalid("Unsupported pollinator habitat type")
    area = _optional_decimal(payload["area_m2"], "habitat area", maximum=Decimal("99999999"))
    if area is None:
        raise PollinatorObservationInvalid("Habitat area is required")
    plant_species = payload["plant_species"]
    if not isinstance(plant_species, list) or len(plant_species) > 50:
        raise PollinatorObservationInvalid("Plant species must be a list of at most 50 names")
    normalized_species = []
    for species in plant_species:
        normalized = _text(species, "plant species", 100)
        if normalized:
            normalized_species.append(normalized)
    if len(json.dumps(normalized_species, ensure_ascii=True).encode("utf-8")) > 8192:
        raise PollinatorObservationInvalid("Plant species exceed the 8 KB limit")

    bloom_months = []
    for field in ("bloom_start_month", "bloom_end_month"):
        month = payload[field]
        if month is not None and (
            isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12
        ):
            raise PollinatorObservationInvalid("Bloom months must be between 1 and 12")
        bloom_months.append(month)
    water_source = payload["water_source"]
    if not isinstance(water_source, bool):
        raise PollinatorObservationInvalid("Water-source flag must be a boolean")
    return (
        request_id,
        habitat_name,
        habitat_type,
        area,
        normalized_species,
        *bloom_months,
        water_source,
        _text(payload["nesting_sites"], "nesting features", 1000, optional=True),
        _text(payload["notes"], "notes", 2000, optional=True),
    )


def create_location_pollinator_habitat(
    operator_id: str,
    location_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create self-reported habitat inventory with exact location authorization."""
    operator_id = _identifier(operator_id, "operator")
    location_id = _identifier(location_id, "location")
    normalized = _normalize_habitat_payload(payload)
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
                "SELECT kokonut_security.create_location_pollinator_habitat("
                "%s::uuid, %s::uuid, %s::text, %s::text, %s::numeric, "
                "%s::jsonb, %s::smallint, %s::smallint, %s::boolean, %s::text, %s::text)",
                (
                    location_id,
                    *normalized[:4],
                    json.dumps(normalized[4]),
                    *normalized[5:],
                ),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Habitat capture returned no record")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
            area_value = result.get("area_m2") if isinstance(result, dict) else None
            if (
                not isinstance(result, dict)
                or result.get("location_id") != location_id
                or result.get("habitat_type") != normalized[2]
                or result.get("status") != "active"
                or not isinstance(result.get("habitat_id"), str)
                or not isinstance(result.get("replayed"), bool)
                or isinstance(area_value, bool)
                or not isinstance(area_value, (int, float))
                or not Decimal("0") <= Decimal(str(area_value)) <= Decimal("99999999")
            ):
                raise RuntimeError("Habitat capture returned an invalid result")
            connection.commit()
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _normalize_habitat_lifecycle_payload(payload: dict) -> tuple:
    if not isinstance(payload, dict):
        raise PollinatorObservationInvalid("Habitat update body must be an object")
    required = {"request_id", "expected_updated_at", "reason"}
    allowed = required | {"status", "condition", "last_maintenance"}
    if not required.issubset(payload) or not set(payload).issubset(allowed):
        raise PollinatorObservationInvalid("Habitat update fields do not match the supported contract")

    request_id = _identifier(payload["request_id"], "request")
    expected_updated_at = payload["expected_updated_at"]
    if not isinstance(expected_updated_at, str) or len(expected_updated_at) > 64:
        raise PollinatorObservationInvalid("expected_updated_at must be a timezone-aware timestamp")
    try:
        expected_timestamp = datetime.fromisoformat(expected_updated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PollinatorObservationInvalid(
            "expected_updated_at must be a timezone-aware timestamp"
        ) from exc
    if expected_timestamp.tzinfo is None or expected_timestamp.utcoffset() is None:
        raise PollinatorObservationInvalid("expected_updated_at must include a timezone")
    expected_timestamp = expected_timestamp.astimezone(timezone.utc)

    status_supplied = "status" in payload
    status = payload.get("status")
    if status_supplied and (
        not isinstance(status, str) or status not in _POLLINATOR_HABITAT_STATUSES
    ):
        raise PollinatorObservationInvalid("Unsupported habitat status")

    condition_supplied = "condition" in payload
    condition = payload.get("condition")
    if condition_supplied and condition is not None and (
        not isinstance(condition, str) or condition not in _POLLINATOR_HABITAT_CONDITIONS
    ):
        raise PollinatorObservationInvalid("Unsupported habitat condition")

    maintenance_supplied = "last_maintenance" in payload
    last_maintenance = payload.get("last_maintenance")
    if maintenance_supplied and last_maintenance is not None:
        if not isinstance(last_maintenance, str):
            raise PollinatorObservationInvalid("last_maintenance must use YYYY-MM-DD or null")
        try:
            parsed_date = date.fromisoformat(last_maintenance)
        except ValueError as exc:
            raise PollinatorObservationInvalid("last_maintenance must use YYYY-MM-DD or null") from exc
        if parsed_date.isoformat() != last_maintenance or parsed_date > date.today():
            raise PollinatorObservationInvalid("last_maintenance must be a valid non-future date")
        last_maintenance = parsed_date

    if not (status_supplied or condition_supplied or maintenance_supplied):
        raise PollinatorObservationInvalid("At least one habitat state field must be supplied")
    reason = _text(payload["reason"], "change reason", 500)
    if not reason:
        raise PollinatorObservationInvalid("A habitat change reason is required")
    return (
        request_id, expected_timestamp, status, status_supplied,
        condition, condition_supplied, last_maintenance, maintenance_supplied, reason,
    )


def update_location_pollinator_habitat(
    operator_id: str,
    location_id: str,
    habitat_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Change reported habitat status/condition/maintenance under exact edit scope."""
    operator_id = _identifier(operator_id, "operator")
    location_id = _identifier(location_id, "location")
    habitat_id = _identifier(habitat_id, "habitat")
    normalized = _normalize_habitat_lifecycle_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="pollinator_health",
            action="edit",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.update_location_pollinator_habitat("
                "%s::uuid, %s::uuid, %s::uuid, %s::timestamptz, %s::text, %s::boolean, "
                "%s::text, %s::boolean, %s::date, %s::boolean, %s::text)",
                (location_id, habitat_id, *normalized),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Habitat update returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
            condition = result.get("condition") if isinstance(result, dict) else None
            maintenance_date = result.get("last_maintenance") if isinstance(result, dict) else None
            if (
                not isinstance(result, dict)
                or result.get("location_id") != location_id
                or result.get("habitat_id") != habitat_id
                or not isinstance(result.get("event_id"), str)
                or result.get("status") not in _POLLINATOR_HABITAT_STATUSES
                or (condition is not None and condition not in _POLLINATOR_HABITAT_CONDITIONS)
                or (maintenance_date is not None and not isinstance(maintenance_date, str))
                or not isinstance(result.get("updated_at"), str)
                or not isinstance(result.get("replayed"), bool)
            ):
                raise RuntimeError("Habitat update returned an invalid result")
            connection.commit()
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _normalize_hive_payload(payload: dict) -> tuple:
    if not isinstance(payload, dict):
        raise PollinatorObservationInvalid("Managed hive body must be an object")
    allowed = {
        "request_id", "hive_id", "hive_type", "colony_strength",
        "colony_strength_score", "queen_status", "frame_count", "queen_year", "notes",
    }
    if set(payload) != allowed:
        raise PollinatorObservationInvalid("Managed hive fields do not match the supported contract")
    request_id = _identifier(payload["request_id"], "request")
    hive_id = _text(payload["hive_id"], "hive identifier", 100)
    hive_type = _text(payload["hive_type"], "hive type", 50)
    if not hive_id or not hive_type:
        raise PollinatorObservationInvalid("Hive identifier and type are required")

    strength = payload["colony_strength"]
    score = payload["colony_strength_score"]
    if (strength is None) == (score is None):
        raise PollinatorObservationInvalid("Provide either colony strength category or score")
    if strength is not None and (
        not isinstance(strength, str)
        or strength not in {"strong", "moderate", "weak", "dead"}
    ):
        raise PollinatorObservationInvalid("Unsupported colony strength category")
    if score is not None and (
        isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 10
    ):
        raise PollinatorObservationInvalid("Colony strength score must be between 0 and 10")

    queen_status = payload["queen_status"]
    if not isinstance(queen_status, str) or queen_status not in {
        "present", "absent", "replaced", "unknown",
    }:
        raise PollinatorObservationInvalid("Unsupported queen status")
    frame_count = payload["frame_count"]
    if isinstance(frame_count, bool) or not isinstance(frame_count, int) or not 0 <= frame_count <= 500:
        raise PollinatorObservationInvalid("Frame count must be between 0 and 500")
    queen_year = payload["queen_year"]
    if queen_year is not None and (
        isinstance(queen_year, bool)
        or not isinstance(queen_year, int)
        or not 1800 <= queen_year <= date.today().year
    ):
        raise PollinatorObservationInvalid("Queen year is outside the supported range")
    return (
        request_id, hive_id, hive_type, strength, score, queen_status, frame_count,
        queen_year, _text(payload["notes"], "notes", 2000, optional=True),
    )


def create_location_pollinator_hive(
    operator_id: str,
    location_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create an active managed-hive inventory entry under exact location grant."""
    operator_id = _identifier(operator_id, "operator")
    location_id = _identifier(location_id, "location")
    normalized = _normalize_hive_payload(payload)
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
                "SELECT kokonut_security.create_location_pollinator_hive("
                "%s::uuid, %s::uuid, %s::text, %s::text, %s::text, "
                "%s::smallint, %s::text, %s::integer, %s::smallint, %s::text)",
                (location_id, *normalized),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Managed-hive capture returned no record")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
            if (
                not isinstance(result, dict)
                or result.get("location_id") != location_id
                or result.get("hive_id") != normalized[1]
                or result.get("hive_type") != normalized[2]
                or result.get("queen_status") != normalized[5]
                or result.get("frame_count") != normalized[6]
                or result.get("status") != "active"
                or not isinstance(result.get("hive_record_id"), str)
                or not isinstance(result.get("replayed"), bool)
            ):
                raise RuntimeError("Managed-hive capture returned an invalid result")
            connection.commit()
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _normalize_hive_inspection_payload(payload: dict) -> tuple:
    if not isinstance(payload, dict):
        raise PollinatorObservationInvalid("Hive inspection body must be an object")
    allowed = {
        "request_id", "hive_id", "inspection_date", "colony_strength",
        "colony_strength_score", "queen_status", "queen_seen", "varroa_count",
        "brood_pattern", "honey_stores", "disease_signs", "temperament",
        "population_estimate", "swarm_cells", "notes",
    }
    if set(payload) != allowed:
        raise PollinatorObservationInvalid("Hive inspection fields do not match the supported contract")
    request_id = _identifier(payload["request_id"], "request")
    hive_id = _text(payload["hive_id"], "hive identifier", 100)
    if not hive_id:
        raise PollinatorObservationInvalid("Hive identifier is required")

    inspection_date = payload["inspection_date"]
    if inspection_date is not None:
        if not isinstance(inspection_date, str):
            raise PollinatorObservationInvalid("Inspection date must use YYYY-MM-DD")
        try:
            inspection_date = date.fromisoformat(inspection_date)
        except ValueError as exc:
            raise PollinatorObservationInvalid("Inspection date must use YYYY-MM-DD") from exc
        if inspection_date.isoformat() != payload["inspection_date"] or inspection_date > date.today():
            raise PollinatorObservationInvalid("Inspection date must be a completed date in YYYY-MM-DD format")

    strength = payload["colony_strength"]
    score = payload["colony_strength_score"]
    if strength is not None and (
        not isinstance(strength, str)
        or strength not in {"strong", "moderate", "weak", "dead"}
    ):
        raise PollinatorObservationInvalid("Unsupported colony strength category")
    if score is not None and (
        isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 10
    ):
        raise PollinatorObservationInvalid("Colony strength score must be between 0 and 10")
    if strength is not None and score is not None:
        raise PollinatorObservationInvalid("Provide a colony strength category or score, not both")

    queen_status = payload["queen_status"]
    if queen_status is not None and (
        not isinstance(queen_status, str)
        or queen_status not in {"present", "absent", "replaced", "unknown"}
    ):
        raise PollinatorObservationInvalid("Unsupported queen status")
    queen_seen = payload["queen_seen"]
    if queen_seen is not None and not isinstance(queen_seen, bool):
        raise PollinatorObservationInvalid("Queen-seen value must be a boolean or null")

    def optional_integer(field: str, maximum: int) -> int | None:
        value = payload[field]
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
            raise PollinatorObservationInvalid(f"{field.replace('_', ' ').capitalize()} is outside its bounds")
        return value

    swarm_cells = payload["swarm_cells"]
    if not isinstance(swarm_cells, bool):
        raise PollinatorObservationInvalid("Swarm-cells value must be a boolean")
    varroa_count = optional_integer("varroa_count", 100_000)
    brood_pattern = _text(payload["brood_pattern"], "brood pattern", 100, optional=True)
    honey_stores = _text(payload["honey_stores"], "honey stores", 500, optional=True)
    disease_signs = _text(payload["disease_signs"], "disease signs", 2000, optional=True)
    temperament = _text(payload["temperament"], "temperament", 100, optional=True)
    population_estimate = optional_integer("population_estimate", 100_000_000)
    notes = _text(payload["notes"], "notes", 2000, optional=True)
    if not any((
        strength, score is not None, queen_status, queen_seen is not None,
        varroa_count is not None, brood_pattern, honey_stores, disease_signs,
        temperament, population_estimate is not None, swarm_cells, notes,
    )):
        raise PollinatorObservationInvalid("At least one inspection observation is required")
    return (
        request_id, hive_id, inspection_date, strength, score, queen_status, queen_seen,
        varroa_count, brood_pattern, honey_stores, disease_signs, temperament,
        population_estimate, swarm_cells, notes,
    )


def record_location_pollinator_hive_inspection(
    operator_id: str,
    location_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Append one recorded hive inspection and update its scoped snapshot atomically."""
    operator_id = _identifier(operator_id, "operator")
    location_id = _identifier(location_id, "location")
    normalized = _normalize_hive_inspection_payload(payload)
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
                "SELECT kokonut_security.record_location_pollinator_hive_inspection("
                "%s::uuid, %s::uuid, %s::text, %s::date, %s::text, %s::smallint, "
                "%s::text, %s::boolean, %s::integer, %s::text, %s::text, %s::text, "
                "%s::text, %s::integer, %s::boolean, %s::text)",
                (location_id, *normalized),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Hive inspection capture returned no record")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
            if (
                not isinstance(result, dict)
                or result.get("location_id") != location_id
                or result.get("status") != "recorded"
                or not isinstance(result.get("inspection_id"), str)
                or not isinstance(result.get("replayed"), bool)
            ):
                raise RuntimeError("Hive inspection capture returned an invalid result")
            connection.commit()
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _normalize_hive_lifecycle_payload(payload: dict) -> tuple:
    if not isinstance(payload, dict):
        raise PollinatorObservationInvalid("Managed-hive update body must be an object")
    required = {"request_id", "expected_updated_at", "reason"}
    allowed = required | {"status", "last_maintenance_date"}
    if not required.issubset(payload) or not set(payload).issubset(allowed):
        raise PollinatorObservationInvalid("Managed-hive update fields do not match the supported contract")

    request_id = _identifier(payload["request_id"], "request")
    expected_updated_at = payload["expected_updated_at"]
    if not isinstance(expected_updated_at, str) or len(expected_updated_at) > 64:
        raise PollinatorObservationInvalid("expected_updated_at must be a timezone-aware timestamp")
    try:
        expected_timestamp = datetime.fromisoformat(expected_updated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PollinatorObservationInvalid(
            "expected_updated_at must be a timezone-aware timestamp"
        ) from exc
    if expected_timestamp.tzinfo is None or expected_timestamp.utcoffset() is None:
        raise PollinatorObservationInvalid("expected_updated_at must include a timezone")
    expected_timestamp = expected_timestamp.astimezone(timezone.utc)

    status_supplied = "status" in payload
    status = payload.get("status")
    if status_supplied and (not isinstance(status, str) or status not in _POLLINATOR_HIVE_STATUSES):
        raise PollinatorObservationInvalid("Unsupported managed-hive status")

    maintenance_supplied = "last_maintenance_date" in payload
    maintenance_date = payload.get("last_maintenance_date")
    if maintenance_supplied and maintenance_date is not None:
        if not isinstance(maintenance_date, str):
            raise PollinatorObservationInvalid("last_maintenance_date must use YYYY-MM-DD or null")
        try:
            parsed_date = date.fromisoformat(maintenance_date)
        except ValueError as exc:
            raise PollinatorObservationInvalid(
                "last_maintenance_date must use YYYY-MM-DD or null"
            ) from exc
        if parsed_date.isoformat() != maintenance_date or parsed_date > date.today():
            raise PollinatorObservationInvalid("last_maintenance_date must be a valid non-future date")
        maintenance_date = parsed_date

    if not (status_supplied or maintenance_supplied):
        raise PollinatorObservationInvalid("At least one managed-hive lifecycle field must be supplied")
    reason = _text(payload["reason"], "change reason", 500)
    if not reason:
        raise PollinatorObservationInvalid("A managed-hive change reason is required")
    return (
        request_id,
        expected_timestamp,
        status,
        status_supplied,
        maintenance_date,
        maintenance_supplied,
        reason,
    )


def update_location_pollinator_hive(
    operator_id: str,
    location_id: str,
    hive_record_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Change reported hive status/maintenance under exact location edit scope."""
    operator_id = _identifier(operator_id, "operator")
    location_id = _identifier(location_id, "location")
    hive_record_id = _identifier(hive_record_id, "managed hive")
    normalized = _normalize_hive_lifecycle_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="pollinator_health",
            action="edit",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.update_location_pollinator_hive("
                "%s::uuid, %s::uuid, %s::uuid, %s::timestamptz, %s::text, %s::boolean, "
                "%s::date, %s::boolean, %s::text)",
                (location_id, hive_record_id, *normalized),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Managed-hive update returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
            maintenance_date = result.get("last_maintenance_date") if isinstance(result, dict) else None
            if (
                not isinstance(result, dict)
                or result.get("location_id") != location_id
                or result.get("hive_record_id") != hive_record_id
                or not isinstance(result.get("event_id"), str)
                or result.get("status") not in _POLLINATOR_HIVE_STATUSES
                or (maintenance_date is not None and not isinstance(maintenance_date, str))
                or not isinstance(result.get("updated_at"), str)
                or not isinstance(result.get("replayed"), bool)
            ):
                raise RuntimeError("Managed-hive update returned an invalid result")
            connection.commit()
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _normalize_pollinator_review_payload(payload: dict) -> tuple:
    if not isinstance(payload, dict):
        raise PollinatorObservationInvalid("Pollinator review body must be an object")
    if set(payload) != {"request_id", "expected_updated_at", "decision", "reason"}:
        raise PollinatorObservationInvalid("Pollinator review fields do not match the supported contract")
    request_id = _identifier(payload["request_id"], "request")
    expected_updated_at = payload["expected_updated_at"]
    if not isinstance(expected_updated_at, str) or len(expected_updated_at) > 64:
        raise PollinatorObservationInvalid("expected_updated_at must be a timezone-aware timestamp")
    try:
        expected_timestamp = datetime.fromisoformat(expected_updated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PollinatorObservationInvalid(
            "expected_updated_at must be a timezone-aware timestamp"
        ) from exc
    if expected_timestamp.tzinfo is None or expected_timestamp.utcoffset() is None:
        raise PollinatorObservationInvalid("expected_updated_at must include a timezone")
    decision = payload["decision"]
    if decision not in {"reviewed", "dismissed"}:
        raise PollinatorObservationInvalid("Unsupported pollinator review decision")
    reason = _text(payload["reason"], "review reason", 500)
    if not reason:
        raise PollinatorObservationInvalid("A pollinator review reason is required")
    return request_id, expected_timestamp, decision, reason


def review_location_pollinator_record(
    operator_id: str,
    location_id: str,
    record_type: str,
    record_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Review a submitted observation or completed pesticide-impact report.

    The database enforces independent reviewer identity, exact location scope,
    optimistic concurrency, immutable reasoned decisions, and exact retries.
    """
    operator_id = _identifier(operator_id, "operator")
    location_id = _identifier(location_id, "location")
    record_id = _identifier(record_id, "pollinator record")
    if record_type not in {"observation", "pesticide_impact", "hive_inspection"}:
        raise PollinatorObservationInvalid("Unsupported pollinator record type")
    normalized = _normalize_pollinator_review_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="pollinator_health",
            action="review",
        )
        with connection.cursor() as cursor:
            if record_type == "hive_inspection":
                cursor.execute(
                    "SELECT kokonut_security.review_location_pollinator_hive_inspection("
                    "%s::uuid, %s::uuid, %s::uuid, %s::timestamptz, %s::text, %s::text)",
                    (location_id, record_id, *normalized),
                )
            else:
                cursor.execute(
                    "SELECT kokonut_security.review_location_pollinator_record("
                    "%s::uuid, %s::text, %s::uuid, %s::uuid, %s::timestamptz, %s::text, %s::text)",
                    (location_id, record_type, record_id, *normalized),
                )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Pollinator review returned no decision")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
            if (
                not isinstance(result, dict)
                or result.get("location_id") != location_id
                or result.get("record_type") != record_type
                or result.get("record_id") != record_id
                or result.get("status") != normalized[2]
                or not isinstance(result.get("decision_id"), str)
                or not isinstance(result.get("replayed"), bool)
            ):
                raise RuntimeError("Pollinator review returned an invalid decision")
            connection.commit()
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
