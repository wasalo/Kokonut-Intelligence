from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from services.ingestion import sensor_worker

LOCATION_ID = "00000000-0000-4000-8000-000000000001"
SENSOR_ID = "00000000-0000-4000-8000-000000000002"
TYPE_ID = "00000000-0000-4000-8000-000000000003"


class FakeDriver:
    name = "sensor_csv"
    driver_type = "sensor"
    supports_scheduled_pull = True

    def __init__(self, config):
        self.config = config

    def validate_config(self, config):
        return config.get("file_path") == "input.csv"

    def discover(self, _config):
        return [{"source_id": "input.csv"}]

    def fetch_scheduled(self, _source):
        return {"data": self.config["records"]}

    def transform(self, raw):
        return raw["data"]


def _instance(records):
    return {
        "instance_id": "00000000-0000-4000-8000-000000000004",
        "instance_name": "test instance",
        "driver_name": "sensor_csv",
        "module_path": "services.ingestion.drivers.sensor_csv",
        "class_name": "Driver",
        "driver_type": "sensor",
        "config": {"file_path": "input.csv", "records": records},
        "location_id": LOCATION_ID,
    }


def _catalog_row():
    return (
        SENSOR_ID,
        "Soil probe",
        "soil-probe",
        TYPE_ID,
        "soil_moisture",
        LOCATION_ID,
        None,
        "active",
        "csv",
        "%",
        0,
        100,
    )


def _record(**overrides):
    return {
        "device_id": SENSOR_ID,
        "reading_date": "2026-10-17",
        "reading_time": "12:30:00",
        "value": "55.5",
        **overrides,
    }


def test_prepare_records_validates_and_hashes_a_scoped_source(monkeypatch):
    monkeypatch.setattr(
        sensor_worker.DriverRegistry,
        "load_schedulable_sensor_driver",
        lambda _instance: FakeDriver,
    )

    prepared, fetched = sensor_worker._prepare_records(
        _instance([_record(location_id=LOCATION_ID)]), LOCATION_ID, [_catalog_row()]
    )

    assert fetched == 1
    assert prepared[0]["validation_status"] == "accepted"
    assert prepared[0]["record"] == _record(location_id=LOCATION_ID)
    assert len(prepared[0]["source_id_sha256"]) == 64
    assert len(prepared[0]["payload_hash"]) == 64
    assert prepared[0]["source_index"] == 0
    assert prepared[0]["record_index"] == 0


@pytest.mark.parametrize(
    ("record", "expected_error"),
    [
        (_record(value="NaN"), "finite"),
        (_record(device_id="missing"), "registered"),
        (_record(reading_date="not-a-date"), "timestamp"),
    ],
)
def test_prepare_records_preserves_invalid_rows_as_rejected_audit_items(
    monkeypatch, record, expected_error
):
    monkeypatch.setattr(
        sensor_worker.DriverRegistry,
        "load_schedulable_sensor_driver",
        lambda _instance: FakeDriver,
    )

    prepared, fetched = sensor_worker._prepare_records(
        _instance([record]), LOCATION_ID, [_catalog_row()]
    )

    assert fetched == 1
    assert prepared[0]["validation_status"] == "rejected"
    assert any(expected_error in error for error in prepared[0]["validation_errors"])


def test_prepare_records_marks_out_of_range_values_suspect(monkeypatch):
    monkeypatch.setattr(
        sensor_worker.DriverRegistry,
        "load_schedulable_sensor_driver",
        lambda _instance: FakeDriver,
    )

    prepared, _ = sensor_worker._prepare_records(
        _instance([_record(value="101")]), LOCATION_ID, [_catalog_row()]
    )

    assert prepared[0]["validation_status"] == "suspect"
    assert prepared[0]["validation_warnings"]


def test_prepare_records_rejects_cross_location_source_before_storage(monkeypatch):
    monkeypatch.setattr(
        sensor_worker.DriverRegistry,
        "load_schedulable_sensor_driver",
        lambda _instance: FakeDriver,
    )

    with pytest.raises(ValueError, match="does not match its instance"):
        sensor_worker._prepare_records(
            _instance([_record(location_id="00000000-0000-4000-8000-000000000099")]),
            LOCATION_ID,
            [_catalog_row()],
        )


def test_prepare_records_enforces_record_payload_bound(monkeypatch):
    monkeypatch.setattr(
        sensor_worker.DriverRegistry,
        "load_schedulable_sensor_driver",
        lambda _instance: FakeDriver,
    )

    with pytest.raises(ValueError, match="record exceeds"):
        sensor_worker._prepare_records(
            _instance([_record(extra="x" * 66_000)]), LOCATION_ID, [_catalog_row()]
        )


def test_ingest_uses_signed_bounded_calls_and_updates_success_status(monkeypatch):
    instance = _instance([])
    monkeypatch.setattr(sensor_worker, "get_worker_credential", lambda _key: "c" * 32)
    resolve = MagicMock(return_value=instance)
    catalog = MagicMock(return_value=[_catalog_row()])
    prepare = MagicMock(return_value=([{"record": _record()}], 1))
    store = MagicMock(return_value=(1, 1, 0))
    update = MagicMock()
    monkeypatch.setattr(sensor_worker, "_resolve_instance", resolve)
    monkeypatch.setattr(sensor_worker, "_load_catalog", catalog)
    monkeypatch.setattr(sensor_worker, "_prepare_records", prepare)
    monkeypatch.setattr(sensor_worker, "_store_batch", store)
    monkeypatch.setattr(sensor_worker, "_update_status", update)

    result = sensor_worker.ingest(instance["instance_id"], LOCATION_ID)

    assert result["records_written"] == 1
    assert result["records_rejected"] == 0
    resolve.assert_called_once_with(instance["instance_id"], LOCATION_ID, "c" * 32)
    catalog.assert_called_once_with(LOCATION_ID, "c" * 32)
    store.assert_called_once_with(instance["instance_id"], LOCATION_ID, "c" * 32, prepare.return_value[0])
    assert update.call_args.kwargs["status"] == "success"
    assert update.call_args.kwargs["error"] is None


def test_ingest_marks_known_instance_failed_without_exposing_exception_text(monkeypatch):
    instance = _instance([])
    monkeypatch.setattr(sensor_worker, "get_worker_credential", lambda _key: "c" * 32)
    monkeypatch.setattr(sensor_worker, "_resolve_instance", lambda *_args: instance)
    monkeypatch.setattr(sensor_worker, "_load_catalog", lambda *_args: [_catalog_row()])
    monkeypatch.setattr(
        sensor_worker,
        "_prepare_records",
        MagicMock(side_effect=ValueError("sensitive file path")),
    )
    update = MagicMock()
    monkeypatch.setattr(sensor_worker, "_update_status", update)

    with pytest.raises(ValueError, match="sensitive file path"):
        sensor_worker.ingest(instance["instance_id"], LOCATION_ID)

    assert update.call_args.kwargs["status"] == "failed"
    assert update.call_args.kwargs["error"] == "ValueError"


def test_main_fails_closed_when_feature_is_disabled(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sensor_worker", "--driver-instance-id", "00000000-0000-4000-8000-000000000004", "--location-id", LOCATION_ID])
    monkeypatch.setattr(sensor_worker, "is_enabled", lambda _feature: False)
    ingest = MagicMock()
    monkeypatch.setattr(sensor_worker, "ingest", ingest)

    with pytest.raises(SystemExit):
        sensor_worker.main()

    ingest.assert_not_called()
