"""Shared validation rules for field and sensor ingestion paths."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
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


def validate_sensor_reading(
    value: float,
    sensor_type: str,
    unit: str | None = None,
    timestamp: datetime | None = None,
    quality: str | None = None,
    ranges: dict[str, tuple[float, float]] | None = None,
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
    return ValidationResult(status, errors, warnings, normalized)
