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


@pytest.mark.parametrize(
    ("date_value", "time_value"),
    [
        ("2026-02-30", None),
        ("not-a-date", "12:30:00"),
        ("2026-10-29", "25:00:00"),
        (None, ""),
    ],
)
def test_single_sensor_reading_rejects_bad_date_or_time_before_database(
    monkeypatch, date_value, time_value
):
    import services.ingestion.sensor_ingester as sensor_ingester

    argv = [
        "--sensor", "synthetic-sensor",
        "--value", "12.5",
        "--location-id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    ]
    if date_value is not None:
        argv.extend(["--date", date_value])
    if time_value is not None:
        argv.extend(["--time", time_value])
    monkeypatch.setattr(
        sensor_ingester,
        "run_single",
        lambda *_args, **_kwargs: pytest.fail("invalid input reached database dispatch"),
    )
    monkeypatch.setattr(
        sensor_ingester,
        "get_db",
        lambda *_args, **_kwargs: pytest.fail("invalid input opened PostgreSQL"),
    )

    with pytest.raises(SystemExit) as error:
        sensor_ingester.main(argv)

    assert error.value.code == 2


def test_single_sensor_reading_forwards_valid_date_time_unchanged(monkeypatch):
    import services.ingestion.sensor_ingester as sensor_ingester
    from services.ingestion.field_validation import parse_reading_timestamp

    calls = []
    monkeypatch.setattr(
        sensor_ingester, "run_single", lambda *args: calls.append(args)
    )
    monkeypatch.setattr(
        sensor_ingester,
        "get_db",
        lambda *_args, **_kwargs: pytest.fail("mocked CLI must not open PostgreSQL"),
    )

    sensor_ingester.main(
        [
            "--sensor", "synthetic-sensor",
            "--value", "12.5",
            "--location-id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "--date", "2026-10-29",
            "--time", "12:30:45",
        ]
    )

    assert calls == [
        (
            "synthetic-sensor",
            12.5,
            "2026-10-29",
            "12:30:45",
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        )
    ]
    assert parse_reading_timestamp("2026-10-29", "12:30:45").isoformat() == (
        "2026-10-29T12:30:45+00:00"
    )


def test_single_sensor_reading_omitted_date_time_keep_service_defaults(monkeypatch):
    import services.ingestion.sensor_ingester as sensor_ingester

    calls = []
    monkeypatch.setattr(
        sensor_ingester, "run_single", lambda *args: calls.append(args)
    )

    sensor_ingester.main(
        [
            "--sensor", "synthetic-sensor",
            "--value", "12.5",
            "--location-id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        ]
    )

    assert calls == [
        (
            "synthetic-sensor",
            12.5,
            None,
            None,
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        )
    ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
