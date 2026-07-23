"""Tests for services.ingestion.sensor_ingester — sensor data ingestion."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_sensor_ingester_validate_reading_in_range():
    from services.ingestion.sensor_ingester import validate_reading, SENSOR_TYPE_RANGES

    warnings = validate_reading(50.0, "soil_moisture", SENSOR_TYPE_RANGES)
    assert warnings == []


def test_sensor_ingester_validate_reading_below_min():
    from services.ingestion.sensor_ingester import validate_reading, SENSOR_TYPE_RANGES

    warnings = validate_reading(-5.0, "soil_moisture", SENSOR_TYPE_RANGES)
    assert len(warnings) == 1
    assert "Below minimum" in warnings[0]


def test_sensor_ingester_validate_reading_above_max():
    from services.ingestion.sensor_ingester import validate_reading, SENSOR_TYPE_RANGES

    warnings = validate_reading(150.0, "humidity", SENSOR_TYPE_RANGES)
    assert len(warnings) == 1
    assert "Above maximum" in warnings[0]


def test_sensor_ingester_validate_reading_nan():
    from services.ingestion.sensor_ingester import validate_reading, SENSOR_TYPE_RANGES

    warnings = validate_reading(float("nan"), "air_temperature", SENSOR_TYPE_RANGES)
    assert any("NaN" in w for w in warnings)


def test_sensor_ingester_get_sensor_type_ranges_returns_defaults():
    from services.ingestion.sensor_ingester import get_sensor_type_ranges, SENSOR_TYPE_RANGES

    mock_db = MagicMock()
    mock_db.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_db.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_db.cursor.return_value.__enter__.return_value.execute.side_effect = Exception("no table")

    ranges = get_sensor_type_ranges(mock_db)
    assert "soil_moisture" in ranges
    assert ranges["soil_moisture"] == (0, 100)


def test_sensor_ingester_validate_ch_value_rejects_bad_input():
    from services.ingestion.sensor_ingester import _validate_ch_value
    import re

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
