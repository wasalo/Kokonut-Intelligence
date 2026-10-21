"""Single sensor readings keep audit and projection in one location transaction."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.ingestion import sensor_ingester

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


def _setup_accepted_reading(monkeypatch, db, audit, event_bus):
    validation = SimpleNamespace(
        status="accepted",
        warnings=[],
        errors=[],
        dedupe_key="dedupe-key",
    )
    monkeypatch.setattr(sensor_ingester, "get_db", lambda: db)
    monkeypatch.setattr(sensor_ingester, "get_sensor_type_ranges", lambda *_args: {})
    monkeypatch.setattr(sensor_ingester, "get_sensor_by_id_or_slug", lambda *_args: SENSOR_INFO)
    monkeypatch.setattr(sensor_ingester, "validate_sensor_reading", lambda *_args, **_kwargs: validation)
    monkeypatch.setattr(sensor_ingester, "insert_reading", lambda *_args, **_kwargs: "reading-id")
    monkeypatch.setattr(sensor_ingester, "insert_reading_clickhouse", lambda *_args: None)
    monkeypatch.setattr(sensor_ingester, "log_ingestion", audit)
    monkeypatch.setattr(sensor_ingester, "_get_event_bus", lambda **_kwargs: event_bus)


def test_single_reading_audit_uses_same_location_connection(monkeypatch):
    db = MagicMock()
    audit = MagicMock()
    event_bus = MagicMock()
    _setup_accepted_reading(monkeypatch, db, audit, event_bus)

    sensor_ingester.run_single(
        "soil-probe",
        42.0,
        date_str="2026-10-21",
        time_str="12:00:00",
        location_id=LOCATION_ID,
    )

    assert audit.call_args.kwargs["db"] is db
    assert audit.call_args.kwargs["location_id"] == LOCATION_ID
    assert audit.call_args.kwargs["status"] == "success"
    assert audit.call_args.kwargs["target_id"] == "reading-id"
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()


def test_rejected_single_reading_persists_scoped_audit_only(monkeypatch):
    db = MagicMock()
    audit = MagicMock()
    logger = MagicMock()
    validation = SimpleNamespace(
        status="rejected",
        errors=["value must be finite"],
        warnings=[],
        dedupe_key="dedupe-key",
    )
    monkeypatch.setattr(sensor_ingester, "get_db", lambda: db)
    monkeypatch.setattr(sensor_ingester, "get_sensor_type_ranges", lambda *_args: {})
    monkeypatch.setattr(sensor_ingester, "get_sensor_by_id_or_slug", lambda *_args: SENSOR_INFO)
    monkeypatch.setattr(sensor_ingester, "validate_sensor_reading", lambda *_args, **_kwargs: validation)
    monkeypatch.setattr(sensor_ingester, "log_ingestion", audit)
    monkeypatch.setattr(sensor_ingester, "logger", logger)
    monkeypatch.setattr(
        sensor_ingester,
        "insert_reading",
        lambda *_args, **_kwargs: pytest.fail("rejected reading must not be inserted"),
    )

    with pytest.raises(ValueError, match="sensor reading rejected by validation"):
        sensor_ingester.run_single(
            "soil-probe",
            float("nan"),
            date_str="2026-10-21",
            time_str="12:00:00",
            location_id=LOCATION_ID,
        )

    assert audit.call_args.kwargs["db"] is db
    assert audit.call_args.kwargs["location_id"] == LOCATION_ID
    assert audit.call_args.kwargs["status"] == "failed"
    assert audit.call_args.kwargs["validation_errors"] == ["value must be finite"]
    assert audit.call_args.kwargs["error_message"] == "sensor reading rejected by validation"
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()


def test_single_reading_projection_failure_rolls_back_audit_and_read(monkeypatch):
    db = MagicMock()
    audit = MagicMock()
    event_bus = MagicMock()
    event_bus.publish.side_effect = RuntimeError("outbox unavailable")
    _setup_accepted_reading(monkeypatch, db, audit, event_bus)

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        sensor_ingester.run_single(
            "soil-probe",
            42.0,
            date_str="2026-10-21",
            time_str="12:00:00",
            location_id=LOCATION_ID,
        )

    assert audit.call_args.kwargs["db"] is db
    assert audit.call_args.kwargs["location_id"] == LOCATION_ID
    db.commit.assert_not_called()
    db.rollback.assert_called_once()
    db.close.assert_called_once()


def test_unknown_single_reading_sensor_is_audited_in_selected_location(monkeypatch):
    db = MagicMock()
    audit = MagicMock()
    logger = MagicMock()
    monkeypatch.setattr(sensor_ingester, "get_db", lambda: db)
    monkeypatch.setattr(sensor_ingester, "get_sensor_type_ranges", lambda *_args: {})
    monkeypatch.setattr(sensor_ingester, "get_sensor_by_id_or_slug", lambda *_args: None)
    monkeypatch.setattr(sensor_ingester, "log_ingestion", audit)
    monkeypatch.setattr(sensor_ingester, "logger", logger)

    with pytest.raises(SystemExit) as exc_info:
        sensor_ingester.run_single(
            "unknown-sensor",
            42.0,
            location_id=LOCATION_ID,
        )

    assert exc_info.value.code == 1
    assert audit.call_args.kwargs["db"] is db
    assert audit.call_args.kwargs["location_id"] == LOCATION_ID
    assert audit.call_args.kwargs["error_message"] == "sensor not found in scoped location"
    assert "unknown-sensor" not in str(logger.error.call_args)
    db.commit.assert_called_once()
    db.close.assert_called_once()


def test_csv_event_publish_leaves_transaction_to_sensor_batch(tmp_path, monkeypatch):
    db = MagicMock()
    event_bus = MagicMock()
    audit = MagicMock()
    csv_path = tmp_path / "readings.csv"
    csv_path.write_text(
        "device_id,reading_date,reading_time,value\n"
        "soil-probe,2026-10-21,12:00:00,42\n",
        encoding="utf-8",
    )
    validation = SimpleNamespace(
        status="accepted",
        warnings=[],
        errors=[],
        dedupe_key="dedupe-key",
    )
    monkeypatch.setattr(sensor_ingester, "get_db", lambda: db)
    monkeypatch.setattr(sensor_ingester, "get_sensor_type_ranges", lambda *_args: {})
    monkeypatch.setattr(sensor_ingester, "get_sensor_by_id_or_slug", lambda *_args: SENSOR_INFO)
    monkeypatch.setattr(sensor_ingester, "validate_sensor_reading", lambda *_args, **_kwargs: validation)
    monkeypatch.setattr(sensor_ingester, "insert_reading", lambda *_args, **_kwargs: "reading-id")
    monkeypatch.setattr(sensor_ingester, "insert_reading_clickhouse", lambda *_args: None)
    monkeypatch.setattr(sensor_ingester, "log_ingestion", audit)
    monkeypatch.setattr(sensor_ingester, "_get_event_bus", lambda **_kwargs: event_bus)

    sensor_ingester.run_csv(str(csv_path), LOCATION_ID)

    assert event_bus.publish.call_args.kwargs["commit"] is False
    db.commit.assert_called_once()
    db.close.assert_called_once()


def test_failed_csv_row_does_not_roll_back_prior_accepted_row(tmp_path, monkeypatch):
    db = MagicMock()
    event_bus = MagicMock()
    audit = MagicMock()
    csv_path = tmp_path / "readings.csv"
    csv_path.write_text(
        "device_id,reading_date,reading_time,value\n"
        "soil-probe,2026-10-21,12:00:00,42\n"
        "soil-probe,2026-10-21,12:01:00,43\n",
        encoding="utf-8",
    )
    validation = SimpleNamespace(
        status="accepted",
        warnings=[],
        errors=[],
        dedupe_key="dedupe-key",
    )
    insert_calls = 0

    def insert_reading(*_args, **_kwargs):
        nonlocal insert_calls
        insert_calls += 1
        if insert_calls == 2:
            raise RuntimeError("synthetic row failure")
        return "reading-1"

    monkeypatch.setattr(sensor_ingester, "get_db", lambda: db)
    monkeypatch.setattr(sensor_ingester, "get_sensor_type_ranges", lambda *_args: {})
    monkeypatch.setattr(sensor_ingester, "get_sensor_by_id_or_slug", lambda *_args: SENSOR_INFO)
    monkeypatch.setattr(sensor_ingester, "validate_sensor_reading", lambda *_args, **_kwargs: validation)
    monkeypatch.setattr(sensor_ingester, "insert_reading", insert_reading)
    monkeypatch.setattr(sensor_ingester, "insert_reading_clickhouse", lambda *_args: None)
    monkeypatch.setattr(sensor_ingester, "log_ingestion", audit)
    monkeypatch.setattr(sensor_ingester, "_get_event_bus", lambda **_kwargs: event_bus)

    sensor_ingester.run_csv(str(csv_path), LOCATION_ID)

    assert [call.kwargs["status"] for call in audit.call_args_list] == ["success", "failed"]
    assert audit.call_args_list[0].kwargs["target_id"] == "reading-1"
    assert audit.call_args_list[1].kwargs["error_message"] == "row processing failed (RuntimeError)"
    assert event_bus.publish.call_count == 1
    statements = [call.args[0] for call in db.cursor.return_value.__enter__.return_value.execute.call_args_list]
    assert statements.count("SAVEPOINT sensor_csv_row") == 2
    assert "ROLLBACK TO SAVEPOINT sensor_csv_row" in statements
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()

