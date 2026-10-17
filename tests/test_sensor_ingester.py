"""Tests for services.ingestion.sensor_ingester — sensor data ingestion."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

SENSOR_TYPE_RANGES = {
    "soil_moisture": (0, 100),
    "soil_temperature": (-40, 80),
    "air_temperature": (-50, 60),
    "humidity": (0, 100),
    "light": (0, 200000),
    "rainfall": (0, 500),
    "water_level": (0, 10000),
}


def test_sensor_ingester_validate_reading_in_range():
    from services.ingestion.field_validation import validate_sensor_reading

    result = validate_sensor_reading(50.0, "soil_moisture", "sensor", ranges=SENSOR_TYPE_RANGES)
    assert result.status == "accepted"


def test_sensor_ingester_validate_reading_below_min():
    from services.ingestion.field_validation import validate_sensor_reading

    result = validate_sensor_reading(-5.0, "soil_moisture", "sensor", ranges=SENSOR_TYPE_RANGES)
    assert result.status == "suspect"
    assert any("outside configured range" in w for w in result.warnings)


def test_sensor_ingester_validate_reading_above_max():
    from services.ingestion.field_validation import validate_sensor_reading

    result = validate_sensor_reading(150.0, "humidity", "sensor", ranges=SENSOR_TYPE_RANGES)
    assert result.status == "suspect"
    assert any("outside configured range" in w for w in result.warnings)


def test_sensor_ingester_validate_reading_nan():
    from services.ingestion.field_validation import validate_sensor_reading

    result = validate_sensor_reading(float("nan"), "air_temperature", "sensor", ranges=SENSOR_TYPE_RANGES)
    assert result.status == "rejected"
    assert any("finite" in e for e in result.errors)


def test_sensor_ingester_get_sensor_type_ranges_returns_defaults():
    from services.ingestion.sensor_ingester import get_sensor_type_ranges

    mock_db = MagicMock()
    mock_db.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_db.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_db.cursor.return_value.__enter__.return_value.execute.side_effect = Exception("no table")

    ranges = get_sensor_type_ranges(mock_db)
    assert "soil_moisture" in ranges
    assert ranges["soil_moisture"] == (0, 100)


@pytest.mark.parametrize(
    "operation",
    ["get_active_sensors", "check_calibration_status", "list_calibration_status"],
)
def test_sensor_inventory_queries_bind_location_scope(operation):
    from services.ingestion.sensor_ingester import (
        check_calibration_status,
        get_active_sensors,
        list_calibration_status,
    )

    location_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    function = {
        "get_active_sensors": get_active_sensors,
        "check_calibration_status": check_calibration_status,
        "list_calibration_status": list_calibration_status,
    }[operation]

    if operation == "list_calibration_status":
        with patch("services.ingestion.sensor_ingester.get_db", return_value=connection):
            function(location_id)
    else:
        function(connection, location_id)

    sql, parameters = cursor.execute.call_args.args
    assert "sd.location_id = %s" in sql
    assert parameters == (location_id,)


def test_sensor_ingester_validate_ch_value_rejects_bad_input():
    import re

    from services.ingestion.sensor_ingester import _validate_ch_value

    pattern = re.compile(r'^[0-9a-f-]+$', re.IGNORECASE)
    with pytest.raises(ValueError, match="Invalid"):
        _validate_ch_value("'; DROP TABLE--", pattern, "test_id")


def test_sensor_ingester_ch_str_escapes():
    from services.ingestion.sensor_ingester import _ch_str

    result = _ch_str("it's a \\ test")
    assert "\\'" in result
    assert "\\\\" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
