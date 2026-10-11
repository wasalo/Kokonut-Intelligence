"""Shared validation rules for field and sensor ingestion paths."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SENSOR_RANGES = {
    "soil_moisture": (0, 100),
    "soil_temperature": (-40, 80),
    "air_temperature": (-50, 60),
    "humidity": (0, 100),
    "light": (0, 200000),
    "rainfall": (0, 500),
    "water_level": (0, 10000),
}


@dataclass
class ValidationResult:
    """Normalized validation outcome shared by ingestion adapters."""

    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    dedupe_key: str | None = None


def parse_reading_timestamp(reading_date: str, reading_time: str | None = None) -> datetime:
    """Parse the canonical field-reading date/time format as UTC."""
    date_part = datetime.strptime(reading_date, "%Y-%m-%d").date()
    time_part = datetime.strptime(reading_time or "00:00:00", "%H:%M:%S").time()
    return datetime.combine(date_part, time_part, tzinfo=timezone.utc)


def get_transport_timestamp_mode(mode: str | None = None) -> str:
    """Validate deployment policy independently of individual payloads."""
    mode = os.environ.get("KOKONUT_SENSOR_TIMESTAMP_MODE", "legacy") if mode is None else mode
    if mode not in {"legacy", "utc"}:
        raise ValueError("KOKONUT_SENSOR_TIMESTAMP_MODE must be legacy or utc")
    return mode


def parse_transport_timestamp(value: str | None, mode: str | None = None) -> datetime:
    """Opt-in UTC identity for HTTP/MQTT without rewriting historical rows."""
    mode = get_transport_timestamp_mode(mode)
    if not value:
        if mode == "utc":
            raise ValueError("An explicit timestamp is required in UTC mode")
        return datetime.now(timezone.utc)
    if not isinstance(value, str):
        raise ValueError("Timestamp must be an ISO datetime string")
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if mode == "utc":
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Timestamp must include a timezone in UTC mode")
        timestamp = timestamp.astimezone(timezone.utc)
    return timestamp


def build_dedupe_key(sensor_id: str, timestamp: datetime) -> str:
    """Build the canonical sensor identity used by CSV, HTTP, and MQTT."""
    return f"sensor_reading:{sensor_id}:{timestamp.astimezone(timezone.utc).isoformat()}"


def validate_sensor_reading(
    value: float,
    sensor_type: str,
    unit: str | None = None,
    timestamp: datetime | None = None,
    quality: str | None = None,
    ranges: dict[str, tuple[float, float]] | None = None,
    identity: str | None = None,
) -> ValidationResult:
    """Apply common numeric, timestamp, range, and quality validation."""
    errors: list[str] = []
    warnings: list[str] = []
    normalized: dict[str, Any] = {"value": value, "sensor_type": sensor_type}

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        errors.append("value must be numeric")
    else:
        normalized["value"] = numeric_value
        if not math.isfinite(numeric_value):
            errors.append("value must be finite")

    if not sensor_type:
        errors.append("sensor_type is required")
    if not unit:
        warnings.append("unit is missing")
    if quality and quality not in {"good", "estimated", "suspect", "bad"}:
        errors.append("quality is invalid")
    if timestamp is not None and timestamp.tzinfo is None:
        warnings.append("timestamp has no timezone")

    configured_ranges = ranges or SENSOR_RANGES
    value_for_range = normalized.get("value")
    if sensor_type in configured_ranges and isinstance(value_for_range, float) and math.isfinite(value_for_range):
        minimum, maximum = configured_ranges[sensor_type]
        if value_for_range < minimum or value_for_range > maximum:
            warnings.append(f"value outside configured range [{minimum}, {maximum}]")

    if errors:
        status = "rejected"
    elif warnings or quality in {"suspect", "bad"}:
        status = "suspect"
    else:
        status = "accepted"
    provenance = {
        "schema_version": "field-ingestion-v1",
        "validation_status": status,
        "warnings": warnings,
        "errors": errors,
    }
    dedupe_key = None
    if timestamp is not None and (identity or sensor_type):
        dedupe_key = build_dedupe_key(identity or sensor_type, timestamp)
    return ValidationResult(status, errors, warnings, normalized, provenance, dedupe_key)
