"""Tests for shared field-ingestion validation outcomes."""

from datetime import datetime, timezone

from services.ingestion.field_validation import validate_sensor_reading


def test_in_range_reading_is_accepted():
    result = validate_sensor_reading(
        42, "soil_moisture", unit="percent", timestamp=datetime.now(timezone.utc)
    )

    assert result.status == "accepted"
    assert result.errors == []


def test_out_of_range_reading_is_suspect():
    result = validate_sensor_reading(120, "soil_moisture", unit="percent")

    assert result.status == "suspect"
    assert result.warnings


def test_non_finite_reading_is_rejected():
    result = validate_sensor_reading(float("nan"), "soil_moisture", unit="percent")

    assert result.status == "rejected"
    assert "finite" in result.errors[0]


def test_invalid_quality_is_rejected():
    result = validate_sensor_reading(42, "soil_moisture", quality="unknown")

    assert result.status == "rejected"
    assert "quality" in result.errors[0]
