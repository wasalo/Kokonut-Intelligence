"""Legacy current-weather observations and audit rows share one transaction."""

from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import weather

LOCATION_ONE = "5e15b529-965d-4845-9c76-2f80fb781a8f"
LOCATION_TWO = "cda03c3e-0105-46a0-9b83-b8a4a21b0a26"


def _connection(locations):
    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = locations
    return db, cursor


def _provider_record(temperature):
    return {
        "dt": 1_790_000_000,
        "main": {"temp": temperature, "humidity": 60, "pressure": 1012},
        "wind": {"speed": 2.0, "deg": 90},
        "rain": {},
        "clouds": {"all": 20},
        "visibility": 10_000,
        "weather": [{"main": "Clouds", "description": "overcast clouds"}],
        "sys": {"country": "DO", "sunrise": 1, "sunset": 2},
    }


def test_location_write_failure_rolls_back_to_savepoint_and_later_location_commits():
    db, cursor = _connection(
        [
            (LOCATION_ONE, "First Farm", 18.5, -69.9),
            (LOCATION_TWO, "Second Farm", 18.6, -70.0),
        ]
    )
    audit_rows = []
    stored_records = []

    def record_audit(**kwargs):
        audit_rows.append(kwargs)

    def insert_observation(_db, record, source_raw=None):
        if record["location_id"] == LOCATION_ONE:
            raise RuntimeError("synthetic insert failure")
        stored_records.append(record)
        return "observation-two"

    with (
        patch.object(weather, "OPENWEATHERMAP_API_KEY", "synthetic-key"),
        patch.object(weather, "get_db", return_value=db),
        patch.object(
            weather,
            "fetch_weather",
            side_effect=[_provider_record(20), _provider_record(21)],
        ),
        patch.object(weather, "insert_weather", side_effect=insert_observation),
        patch.object(weather, "log_ingestion", side_effect=record_audit),
        patch.object(weather, "insert_weather_clickhouse") as project,
        patch.object(weather.time, "sleep"),
    ):
        weather.run(all_locations=True)

    assert [row["location_id"] for row in audit_rows] == [LOCATION_ONE, LOCATION_TWO]
    assert all(row["db"] is db for row in audit_rows)
    assert [row["status"] for row in audit_rows] == ["failed", "success"]
    assert audit_rows[0]["error_message"] == "weather location processing failed (RuntimeError)"
    assert [record["location_id"] for record in stored_records] == [LOCATION_TWO]

    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements.count("SAVEPOINT weather_location") == 2
    assert statements.count("ROLLBACK TO SAVEPOINT weather_location") == 1
    assert statements.count("RELEASE SAVEPOINT weather_location") == 2
    project.assert_called_once_with(stored_records, db)
    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()
    db.close.assert_called_once_with()


def test_projection_failure_rolls_back_observation_and_audit_together():
    db, _cursor = _connection([(LOCATION_ONE, "First Farm", 18.5, -69.9)])
    record = _provider_record(20)

    with (
        patch.object(weather, "OPENWEATHERMAP_API_KEY", "synthetic-key"),
        patch.object(weather, "get_db", return_value=db),
        patch.object(weather, "fetch_weather", return_value=record),
        patch.object(weather, "insert_weather", return_value="observation-one"),
        patch.object(weather, "log_ingestion") as audit,
        patch.object(
            weather,
            "insert_weather_clickhouse",
            side_effect=RuntimeError("synthetic outbox failure"),
        ),
        patch.object(weather.time, "sleep"),
        pytest.raises(RuntimeError, match="synthetic outbox failure"),
    ):
        weather.run(all_locations=True)

    audit.assert_called_once()
    assert audit.call_args.kwargs["db"] is db
    assert audit.call_args.kwargs["status"] == "success"
    db.commit.assert_not_called()
    db.rollback.assert_called_once_with()
    db.close.assert_called_once_with()
