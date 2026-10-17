"""Scheduled sensor ingestion resolves a scoped driver instance, never a path."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from services.drivers.registry import DriverRegistry
from services.ingestion import sensor_ingester
from services.ingestion.drivers.sensor_csv import (
    MAX_SENSOR_CSV_RECORDS,
)
from services.ingestion.drivers.sensor_csv import (
    Driver as SensorCsvDriver,
)


def test_registry_loads_only_enabled_sensor_instance_at_exact_location():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    instance_id = str(uuid4())
    location_id = str(uuid4())
    cursor.fetchone.return_value = (
        instance_id,
        "north-sensors",
        "sensor_csv",
        "services.ingestion.drivers.sensor_csv",
        "Driver",
        "sensor",
        json.dumps({"file_path": "/data/readings.csv"}),
        location_id,
    )

    result = DriverRegistry(conn=connection).get_schedulable_instance(
        instance_id, location_id
    )

    assert result == {
        "instance_id": instance_id,
        "instance_name": "north-sensors",
        "driver_name": "sensor_csv",
        "module_path": "services.ingestion.drivers.sensor_csv",
        "class_name": "Driver",
        "driver_type": "sensor",
        "config": {"file_path": "/data/readings.csv"},
        "location_id": location_id,
    }
    query, parameters = cursor.execute.call_args.args
    assert "di.location_id = %s" in query
    assert "di.is_enabled = TRUE" in query
    assert "dr.is_enabled = TRUE" in query
    assert "dr.driver_type = 'sensor'" in query
    assert parameters == (instance_id, location_id)


def test_insert_reading_reports_exact_duplicate_without_claiming_new_event():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    reading_id = str(uuid4())
    cursor.fetchone.side_effect = [
        None,
        (reading_id, Decimal("34.5000"), "good"),
    ]
    sensor = (
        str(uuid4()), "Probe", "soil-probe-1", str(uuid4()), "soil_moisture",
        str(uuid4()), None, "active", "csv",
    )

    result = sensor_ingester.insert_reading(
        connection,
        sensor,
        "2026-10-16",
        "12:00:00",
        34.5,
        return_created=True,
    )

    assert result == (reading_id, False)
    assert cursor.execute.call_count == 2


def test_insert_reading_rejects_conflicting_timestamp_value():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [
        None,
        (str(uuid4()), Decimal("35.0000"), "good"),
    ]
    sensor = (
        str(uuid4()), "Probe", "soil-probe-1", str(uuid4()), "soil_moisture",
        str(uuid4()), None, "active", "csv",
    )

    with pytest.raises(ValueError, match="timestamp conflicts"):
        sensor_ingester.insert_reading(
            connection,
            sensor,
            "2026-10-16",
            "12:00:00",
            34.5,
            return_created=True,
        )

    assert cursor.execute.call_count == 2


@pytest.fixture
def scheduled_sensor_runtime(monkeypatch):
    connection = MagicMock()
    instance_id = str(uuid4())
    location_id = str(uuid4())
    sensor_id = str(uuid4())
    reading_id = str(uuid4())
    source = {"source_id": "synthetic-source"}
    record = {
        "device_id": "soil-probe-1",
        "reading_date": "2026-10-16",
        "reading_time": "12:00:00",
        "value": "34.5",
    }
    driver = MagicMock()
    driver.name = "sensor_csv"
    driver.driver_type = "sensor"
    driver.supports_scheduled_pull = True
    driver.validate_config.return_value = True
    driver.discover.return_value = [source]
    driver.fetch.return_value = {"raw": True}
    driver.transform.return_value = [record]
    registry = MagicMock()
    registry.get_schedulable_instance.return_value = {
        "instance_id": instance_id,
        "instance_name": "synthetic",
        "driver_name": "sensor_csv",
        "config": {"file_path": "/not-read-by-test.csv"},
        "location_id": location_id,
    }
    registry.load.return_value = lambda **_kwargs: driver
    sensor = (sensor_id, "Probe", "soil-probe-1", "soil-type", "soil_moisture", location_id, None, "active", "csv")
    validation = MagicMock(status="valid", errors=[], warnings=[], dedupe_key="dedupe")
    bus = MagicMock()
    insert = MagicMock(return_value=(reading_id, True))

    monkeypatch.setattr(sensor_ingester, "get_db", lambda: connection)
    monkeypatch.setattr("services.drivers.registry.DriverRegistry", lambda **_kwargs: registry)
    monkeypatch.setattr(sensor_ingester, "get_sensor_type_ranges", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(sensor_ingester, "get_sensor_by_id_or_slug", lambda *_args: sensor)
    monkeypatch.setattr(sensor_ingester, "validate_sensor_reading", lambda *_args, **_kwargs: validation)
    monkeypatch.setattr(sensor_ingester, "hash_payload", lambda _value: "a" * 64)
    monkeypatch.setattr(sensor_ingester, "insert_reading", insert)
    monkeypatch.setattr(sensor_ingester, "insert_reading_clickhouse", MagicMock())
    monkeypatch.setattr(sensor_ingester, "log_ingestion", MagicMock())
    monkeypatch.setattr(sensor_ingester, "_get_event_bus", lambda **_kwargs: bus)
    monkeypatch.setattr(sensor_ingester, "_event_bus", None)

    return {
        "connection": connection,
        "instance_id": instance_id,
        "location_id": location_id,
        "sensor_id": sensor_id,
        "reading_id": reading_id,
        "driver": driver,
        "registry": registry,
        "bus": bus,
        "insert": insert,
        "record": record,
    }


def test_scheduled_pull_commits_reading_projection_audit_and_event_together(
    monkeypatch, scheduled_sensor_runtime
):
    runtime = scheduled_sensor_runtime
    created_args = {}

    def insert_reading(*_args, **kwargs):
        created_args.update(kwargs)
        return runtime["reading_id"], True

    monkeypatch.setattr(sensor_ingester, "insert_reading", insert_reading)
    result = sensor_ingester.run_driver_instance(
        runtime["instance_id"], runtime["location_id"]
    )

    assert result["records_fetched"] == 1
    assert result["records_written"] == 1
    assert result["records_rejected"] == 0
    assert created_args["return_created"] is True
    runtime["connection"].commit.assert_called_once()
    runtime["connection"].rollback.assert_not_called()
    runtime["connection"].close.assert_called_once()
    runtime["bus"].publish.assert_called_once()
    assert runtime["bus"].publish.call_args.kwargs["commit"] is False
    runtime["registry"].update_instance_status.assert_called_once()
    assert runtime["registry"].update_instance_status.call_args.args[:2] == (
        runtime["instance_id"],
        "success",
    )


def test_scheduled_pull_does_not_republish_an_existing_reading(
    monkeypatch, scheduled_sensor_runtime
):
    runtime = scheduled_sensor_runtime
    monkeypatch.setattr(
        sensor_ingester,
        "insert_reading",
        lambda *_args, **_kwargs: (runtime["reading_id"], False),
    )

    result = sensor_ingester.run_driver_instance(
        runtime["instance_id"], runtime["location_id"]
    )

    assert result["records_written"] == 0
    runtime["bus"].publish.assert_not_called()
    runtime["connection"].commit.assert_called_once()


def test_scheduled_pull_rejects_cross_location_record_and_rolls_back(
    scheduled_sensor_runtime
):
    runtime = scheduled_sensor_runtime
    runtime["driver"].transform.return_value = [
        {**runtime["record"], "location_id": str(uuid4())}
    ]

    with pytest.raises(ValueError, match="location does not match"):
        sensor_ingester.run_driver_instance(
            runtime["instance_id"], runtime["location_id"]
        )

    runtime["connection"].rollback.assert_called_once()
    runtime["connection"].commit.assert_not_called()
    runtime["registry"].update_instance_status.assert_called_once()
    assert runtime["registry"].update_instance_status.call_args.kwargs["error_message"] == "ValueError"
    runtime["bus"].publish.assert_not_called()


def test_scheduled_pull_rejects_event_driven_driver_before_fetch(
    scheduled_sensor_runtime
):
    runtime = scheduled_sensor_runtime
    runtime["driver"].supports_scheduled_pull = False

    with pytest.raises(ValueError, match="does not support scheduled pull"):
        sensor_ingester.run_driver_instance(
            runtime["instance_id"], runtime["location_id"]
        )

    runtime["driver"].fetch.assert_not_called()
    runtime["connection"].rollback.assert_called_once()
    runtime["bus"].publish.assert_not_called()


def test_scheduled_pull_rejects_driver_registry_identity_mismatch(
    scheduled_sensor_runtime
):
    runtime = scheduled_sensor_runtime
    runtime["driver"].name = "different_driver"

    with pytest.raises(ValueError, match="identity does not match"):
        sensor_ingester.run_driver_instance(
            runtime["instance_id"], runtime["location_id"]
        )

    runtime["driver"].fetch.assert_not_called()
    runtime["connection"].rollback.assert_called_once()
    runtime["bus"].publish.assert_not_called()


def test_scheduled_pull_bounds_discovered_source_count(scheduled_sensor_runtime):
    runtime = scheduled_sensor_runtime
    runtime["driver"].discover.return_value = [
        {"source_id": f"source-{index}"} for index in range(101)
    ]

    with pytest.raises(ValueError, match="source list"):
        sensor_ingester.run_driver_instance(
            runtime["instance_id"], runtime["location_id"]
        )

    runtime["driver"].fetch.assert_not_called()
    runtime["connection"].rollback.assert_called_once()
    runtime["bus"].publish.assert_not_called()


def test_sensor_csv_scheduled_pull_caps_source_rows(tmp_path):
    source = tmp_path / "readings.csv"
    source.write_text(
        "device_id,reading_date,reading_time,value\n"
        + "soil-probe-1,2026-10-16,12:00:00,34.5\n" * (MAX_SENSOR_CSV_RECORDS + 1),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="record limit"):
        SensorCsvDriver(config={"file_path": str(source)}).fetch(
            {"source_id": str(source)}
        )
