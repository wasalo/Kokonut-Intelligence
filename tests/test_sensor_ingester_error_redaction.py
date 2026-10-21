"""CSV and ClickHouse sensor failures must not disclose raw values or errors."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from services.ingestion import sensor_ingester

SECRET = "field-reading-secret-value"
LOCATION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SENSOR_INFO = (
    "sensor-id",
    "Soil probe",
    "soil-probe",
    "sensor-type-id",
    "soil_moisture",
    LOCATION_ID,
    None,
    "active",
    "http",
)


def _write_csv(path, reading_date="2026-10-17", value="42.0"):
    path.write_text(
        f"device_id,reading_date,reading_time,value\nsoil-probe,{reading_date},09:00:00,{value}\n",
        encoding="utf-8",
    )
    return str(path)


def test_legacy_clickhouse_insert_failure_logs_only_exception_class(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(sensor_ingester, "logger", logger)
    monkeypatch.setattr(
        sensor_ingester,
        "insert_clickhouse_rows",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(f"ClickHouse DSN {SECRET}")),
    )

    sensor_ingester.insert_reading_clickhouse(
        SENSOR_INFO, "2026-10-17", "09:00:00", 42.0
    )

    assert SECRET not in str(logger.warning.call_args)
    assert "RuntimeError" in str(logger.warning.call_args)


def test_csv_invalid_timestamp_is_not_copied_to_logs_or_audit(tmp_path, monkeypatch):
    connection = MagicMock()
    logger = MagicMock()
    audit = MagicMock()
    csv_path = _write_csv(tmp_path / "readings.csv", reading_date=SECRET)
    monkeypatch.setattr(sensor_ingester, "get_db", lambda: connection)
    monkeypatch.setattr(sensor_ingester, "get_sensor_type_ranges", lambda *_args: {})
    monkeypatch.setattr(sensor_ingester, "hash_payload", lambda _row: "a" * 64)
    monkeypatch.setattr(sensor_ingester, "log_ingestion", audit)
    monkeypatch.setattr(sensor_ingester, "logger", logger)

    sensor_ingester.run_csv(csv_path, location_id=LOCATION_ID)

    audit.assert_called_once()
    assert audit.call_args.kwargs["error_message"] == "invalid timestamp"
    assert audit.call_args.kwargs["validation_errors"] == ["invalid timestamp"]
    assert audit.call_args.kwargs["db"] is connection
    assert audit.call_args.kwargs["location_id"] == LOCATION_ID
    assert SECRET not in str(audit.call_args)
    assert SECRET not in str(logger.warning.call_args)
    connection.commit.assert_called_once()
    connection.close.assert_called_once()


def test_csv_invalid_numeric_value_is_not_logged(tmp_path, monkeypatch):
    connection = MagicMock()
    logger = MagicMock()
    csv_path = _write_csv(tmp_path / "readings.csv", value=SECRET)
    monkeypatch.setattr(sensor_ingester, "get_db", lambda: connection)
    monkeypatch.setattr(sensor_ingester, "get_sensor_type_ranges", lambda *_args: {})
    monkeypatch.setattr(sensor_ingester, "logger", logger)

    sensor_ingester.run_csv(csv_path, location_id=LOCATION_ID)

    assert SECRET not in str(logger.warning.call_args)
    assert "invalid numeric value" in str(logger.warning.call_args)
    connection.close.assert_called_once()


def test_csv_processing_exception_is_redacted_in_audit_and_log(tmp_path, monkeypatch):
    connection = MagicMock()
    logger = MagicMock()
    audit = MagicMock()
    csv_path = _write_csv(tmp_path / "readings.csv")
    validation = SimpleNamespace(status="accepted", warnings=[], errors=[], dedupe_key="dedupe")
    monkeypatch.setattr(sensor_ingester, "get_db", lambda: connection)
    monkeypatch.setattr(sensor_ingester, "get_sensor_type_ranges", lambda *_args: {})
    monkeypatch.setattr(sensor_ingester, "get_sensor_by_id_or_slug", lambda *_args: SENSOR_INFO)
    monkeypatch.setattr(sensor_ingester, "validate_sensor_reading", lambda *_args, **_kwargs: validation)
    monkeypatch.setattr(sensor_ingester, "hash_payload", lambda _row: "b" * 64)
    monkeypatch.setattr(sensor_ingester, "log_ingestion", audit)
    monkeypatch.setattr(sensor_ingester, "logger", logger)
    monkeypatch.setattr(
        sensor_ingester,
        "insert_reading",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(f"database DSN {SECRET}")),
    )

    sensor_ingester.run_csv(csv_path, location_id=LOCATION_ID)

    audit.assert_called_once()
    assert audit.call_args.kwargs["error_message"] == "row processing failed (RuntimeError)"
    assert audit.call_args.kwargs["db"] is connection
    assert audit.call_args.kwargs["location_id"] == LOCATION_ID
    assert SECRET not in str(audit.call_args)
    assert SECRET not in str(logger.error.call_args)
    assert "RuntimeError" in str(logger.error.call_args)
    connection.rollback.assert_called_once()
    connection.commit.assert_called_once()
    connection.close.assert_called_once()
