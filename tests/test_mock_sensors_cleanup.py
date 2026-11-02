"""Mock sensor cleanup must be limited to explicitly marked demo devices."""

from __future__ import annotations

import pytest

from services.ingestion import mock_sensors, sensor_mock_cleanup_worker

LOCATION_ID = "1f31512c-3b1d-4312-bd0f-54a2b23b31d0"


class _Cursor:
    def __init__(self, *, fail_on: str | None = None) -> None:
        self.queries: list[str] = []
        self.fail_on = fail_on

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def execute(self, query: str, _params: object = None) -> None:
        normalized = " ".join(query.split())
        self.queries.append(normalized)
        if self.fail_on and self.fail_on in normalized:
            raise RuntimeError("synthetic query failure")

    def fetchall(self) -> list[tuple[object, ...]]:
        return []


class _Database:
    def __init__(self, *, fail_on: str | None = None) -> None:
        self.db_cursor = _Cursor(fail_on=fail_on)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> _Cursor:
        return self.db_cursor

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def test_cleanup_deletes_alerts_and_readings_through_signed_workers(monkeypatch) -> None:
    alert_cleanup_calls: list[str] = []
    reading_cleanup_calls: list[str] = []
    monkeypatch.setattr(
        mock_sensors,
        "get_db",
        lambda: pytest.fail("cleanup must not use the shared runtime database"),
    )
    monkeypatch.setattr(
        sensor_mock_cleanup_worker,
        "delete_mock_sensor_alerts",
        lambda location_id: alert_cleanup_calls.append(location_id) or 2,
    )
    monkeypatch.setattr(
        sensor_mock_cleanup_worker,
        "delete_mock_sensor_readings",
        lambda location_id: reading_cleanup_calls.append(location_id) or 14,
    )

    mock_sensors.cleanup(LOCATION_ID.upper())

    assert alert_cleanup_calls == [LOCATION_ID]
    assert reading_cleanup_calls == [LOCATION_ID]


def test_cleanup_propagates_signed_reading_cleanup_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        sensor_mock_cleanup_worker,
        "delete_mock_sensor_alerts",
        lambda _location: 0,
    )
    monkeypatch.setattr(
        sensor_mock_cleanup_worker,
        "delete_mock_sensor_readings",
        lambda _location: (_ for _ in ()).throw(RuntimeError("signed cleanup denied")),
    )

    with pytest.raises(RuntimeError, match="signed cleanup denied"):
        mock_sensors.cleanup(LOCATION_ID)

def test_cleanup_rejects_missing_or_invalid_location_before_worker_or_db(monkeypatch) -> None:
    monkeypatch.setattr(
        sensor_mock_cleanup_worker,
        "delete_mock_sensor_alerts",
        lambda _location: pytest.fail("invalid scope must fail before worker access"),
    )
    monkeypatch.setattr(
        sensor_mock_cleanup_worker,
        "delete_mock_sensor_readings",
        lambda _location: pytest.fail("invalid scope must fail before worker access"),
    )
    monkeypatch.setattr(
        mock_sensors,
        "get_db",
        lambda: pytest.fail("invalid scope must fail before database access"),
    )

    for location_id in (None, "", "not-a-uuid"):
        with pytest.raises(ValueError, match="--location-id must be a UUID"):
            mock_sensors.cleanup(location_id)


def test_cleanup_stops_before_reading_delete_when_signed_alert_operation_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        sensor_mock_cleanup_worker,
        "delete_mock_sensor_alerts",
        lambda _location: (_ for _ in ()).throw(RuntimeError("signed cleanup denied")),
    )
    monkeypatch.setattr(
        sensor_mock_cleanup_worker,
        "delete_mock_sensor_readings",
        lambda _location: pytest.fail("reading cleanup must not run after alert cleanup fails"),
    )
    monkeypatch.setattr(
        mock_sensors,
        "get_db",
        lambda: pytest.fail("cleanup must not use shared runtime database"),
    )

    with pytest.raises(RuntimeError, match="signed cleanup denied"):
        mock_sensors.cleanup(LOCATION_ID)


def test_setup_sensors_commits_and_closes_on_success(monkeypatch) -> None:
    database = _Database()
    monkeypatch.setattr(mock_sensors, "get_db", lambda: database)
    monkeypatch.setattr(mock_sensors, "get_or_create_location", lambda _db: "location-id")
    monkeypatch.setattr(mock_sensors, "SAMPLE_SENSORS", [])

    mock_sensors.setup_sensors()

    assert database.committed
    assert not database.rolled_back
    assert database.closed


def test_setup_sensors_rolls_back_and_closes_when_location_setup_fails(monkeypatch) -> None:
    database = _Database()
    monkeypatch.setattr(mock_sensors, "get_db", lambda: database)

    def fail_location_setup(_db):
        raise RuntimeError("synthetic setup failure")

    monkeypatch.setattr(mock_sensors, "get_or_create_location", fail_location_setup)

    with pytest.raises(RuntimeError, match="synthetic setup failure"):
        mock_sensors.setup_sensors()

    assert not database.committed
    assert database.rolled_back
    assert database.closed


def test_setup_sensors_rolls_back_and_closes_after_sensor_type_query_fails(monkeypatch) -> None:
    database = _Database(fail_on="SELECT id, name FROM sensor_type")
    monkeypatch.setattr(mock_sensors, "get_db", lambda: database)
    monkeypatch.setattr(mock_sensors, "get_or_create_location", lambda _db: "location-id")

    with pytest.raises(RuntimeError, match="synthetic query failure"):
        mock_sensors.setup_sensors()

    assert not database.committed
    assert database.rolled_back
    assert database.closed


def test_generation_query_excludes_unmarked_operational_sensors(monkeypatch) -> None:
    class _GenerationCursor(_Cursor):
        def fetchall(self) -> list[tuple[object, ...]]:
            return []

    class _GenerationDatabase(_Database):
        def __init__(self) -> None:
            super().__init__()
            self.db_cursor = _GenerationCursor()

    database = _GenerationDatabase()
    monkeypatch.setattr(mock_sensors, "get_db", lambda: database)

    mock_sensors.generate_data(count=1)

    assert len(database.db_cursor.queries) == 1
    assert "sd.metadata->>'mock_sensor_demo' = 'true'" in database.db_cursor.queries[0]
    assert not database.committed
    assert database.closed
