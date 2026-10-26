"""Keep demo sensor ingestion failures free of identifiers and driver details."""

import logging

from services.ingestion import mock_sensors


class _Cursor:
    def __init__(self, sensitive_detail):
        self.sensitive_detail = sensitive_detail

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _params=None):
        if "INSERT INTO sensor_reading" in query:
            raise RuntimeError(self.sensitive_detail)

    def fetchall(self):
        return [
            (
                "sensor-123",
                "Private Field Sensor",
                "private-field-sensor",
                "sensor-type-123",
                "soil_moisture",
                "location-123",
                None,
                "active",
                "http",
                {"base_value": 20.0, "daily_variation": 0.0, "noise": 0.0},
            )
        ]


class _Database:
    def __init__(self, sensitive_detail):
        self.sensitive_detail = sensitive_detail
        self.closed = False
        self.committed = False

    def cursor(self):
        return _Cursor(self.sensitive_detail)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_mock_sensor_insert_failure_redacts_identity_time_and_driver_detail(
    caplog, monkeypatch
):
    sensor_name = "Private Field Sensor"
    sensitive_detail = "postgres error at /private/database/socket"
    database = _Database(sensitive_detail)
    monkeypatch.setattr(mock_sensors, "get_db", lambda: database)
    monkeypatch.setattr(mock_sensors, "DEMO_DIRECT_CLICKHOUSE", False)
    caplog.set_level(logging.ERROR, logger="kokonut.ingestion.mock_sensors")

    mock_sensors.generate_data(count=1)

    assert "Mock sensor reading insert failed (RuntimeError)" in caplog.text
    assert sensor_name not in caplog.text
    assert sensitive_detail not in caplog.text
    assert database.committed
    assert database.closed
