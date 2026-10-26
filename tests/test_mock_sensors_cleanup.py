"""Mock sensor cleanup must be limited to explicitly marked demo devices."""

from __future__ import annotations

import pytest

from services.ingestion import mock_sensors


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


def test_cleanup_only_deletes_rows_for_marked_demo_devices(monkeypatch) -> None:
    database = _Database()
    monkeypatch.setattr(mock_sensors, "get_db", lambda: database)

    mock_sensors.cleanup()

    assert len(database.db_cursor.queries) == 2
    alert_delete, reading_delete = database.db_cursor.queries
    assert alert_delete.startswith("DELETE FROM sensor_alert WHERE sensor_device_id IN")
    assert "metadata->>'mock_sensor_demo' = 'true'" in alert_delete
    assert reading_delete.startswith("DELETE FROM sensor_reading WHERE")
    assert "metadata->>'mock' = 'true'" in reading_delete
    assert "metadata->>'mock_sensor_demo' = 'true'" in reading_delete
    assert database.committed
    assert not database.rolled_back
    assert database.closed


def test_cleanup_rolls_back_and_closes_when_delete_fails(monkeypatch) -> None:
    database = _Database(fail_on="DELETE FROM sensor_reading")
    monkeypatch.setattr(mock_sensors, "get_db", lambda: database)

    with pytest.raises(RuntimeError, match="synthetic query failure"):
        mock_sensors.cleanup()

    assert not database.committed
    assert database.rolled_back
    assert database.closed


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
