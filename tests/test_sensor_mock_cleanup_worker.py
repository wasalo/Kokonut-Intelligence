"""Signed, retry-safe sensor mock alert cleanup worker contract."""

from __future__ import annotations

import pytest

from services.ingestion import sensor_mock_cleanup_worker as worker

LOCATION_ID = "1f31512c-3b1d-4312-bd0f-54a2b23b31d0"


class _Cursor:
    def __init__(self, events: list[tuple], result=(3,)) -> None:
        self.events = events
        self.result = result

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement: str, params: tuple[str, ...]) -> None:
        self.events.append(("execute", " ".join(statement.split()), params))

    def fetchone(self):
        return self.result


class _Connection:
    def __init__(self, events: list[tuple], result=(3,)) -> None:
        self.events = events
        self.db_cursor = _Cursor(events, result=result)

    def cursor(self) -> _Cursor:
        return self.db_cursor

    def commit(self) -> None:
        self.events.append(("commit",))

    def rollback(self) -> None:
        self.events.append(("rollback",))

    def close(self) -> None:
        self.events.append(("close",))


def test_cleanup_uses_exact_sensor_anomaly_scope_and_returns_deleted_count(monkeypatch) -> None:
    events: list[tuple] = []
    connection = _Connection(events)
    monkeypatch.setattr(
        worker,
        "get_worker_credential",
        lambda key: events.append(("credential", key)) or "c" * 32,
    )
    monkeypatch.setattr(
        worker, "get_worker_db", lambda key: events.append(("db", key)) or connection
    )

    def set_context(conn, **kwargs):
        assert conn is connection
        events.append(("scope", kwargs))

    monkeypatch.setattr(worker, "set_worker_tenant_context", set_context)

    assert worker.delete_mock_sensor_alerts(LOCATION_ID.upper()) == 3

    assert events[0:3] == [
        ("credential", "sensor_anomaly"),
        ("db", "sensor_anomaly"),
        (
            "scope",
            {
                "credential": "c" * 32,
                "location_id": LOCATION_ID,
                "resource": "sensor_reading",
                "action": "process",
            },
        ),
    ]
    execution = next(event for event in events if event[0] == "execute")
    assert "kokonut_security.delete_mock_sensor_alerts(%s::uuid)" in execution[1]
    assert execution[2] == (LOCATION_ID,)
    assert events[-2:] == [("commit",), ("close",)]


def test_reading_cleanup_uses_exact_sensor_anomaly_scope_and_bounded_function(monkeypatch) -> None:
    events: list[tuple] = []
    connection = _Connection(events, result=(5,))
    monkeypatch.setattr(
        worker,
        "get_worker_credential",
        lambda key: events.append(("credential", key)) or "c" * 32,
    )
    monkeypatch.setattr(
        worker, "get_worker_db", lambda key: events.append(("db", key)) or connection
    )
    monkeypatch.setattr(
        worker,
        "set_worker_tenant_context",
        lambda conn, **kwargs: events.append(("scope", conn is connection, kwargs)),
    )

    assert worker.delete_mock_sensor_readings(LOCATION_ID.upper()) == 5

    execution = next(event for event in events if event[0] == "execute")
    assert "kokonut_security.delete_mock_sensor_readings(%s::uuid)" in execution[1]
    assert execution[2] == (LOCATION_ID,)
    assert events[-2:] == [("commit",), ("close",)]


@pytest.mark.parametrize("location_id", [None, "", "not-a-uuid"])
def test_invalid_location_fails_before_worker_secret_or_database(monkeypatch, location_id) -> None:
    monkeypatch.setattr(
        worker,
        "get_worker_credential",
        lambda _key: pytest.fail("invalid location must be checked before secret access"),
    )
    monkeypatch.setattr(
        worker,
        "get_worker_db",
        lambda _key: pytest.fail("invalid location must be checked before database access"),
    )

    with pytest.raises(ValueError, match="location_id must be a UUID"):
        worker.delete_mock_sensor_alerts(location_id)


@pytest.mark.parametrize("result", [None, (), (True,), (-1,), (1.5,), ("2",)])
def test_invalid_database_result_rolls_back_and_closes(monkeypatch, result) -> None:
    events: list[tuple] = []
    connection = _Connection(events, result=result)
    monkeypatch.setattr(worker, "get_worker_credential", lambda _key: "c" * 32)
    monkeypatch.setattr(worker, "get_worker_db", lambda _key: connection)
    monkeypatch.setattr(worker, "set_worker_tenant_context", lambda *_args, **_kwargs: None)

    with pytest.raises(worker.SensorMockCleanupWorkerError):
        worker.delete_mock_sensor_alerts(LOCATION_ID)

    assert ("rollback",) in events
    assert events[-1] == ("close",)


def test_context_or_query_failure_rolls_back_and_closes(monkeypatch) -> None:
    events: list[tuple] = []
    connection = _Connection(events)
    monkeypatch.setattr(worker, "get_worker_credential", lambda _key: "c" * 32)
    monkeypatch.setattr(worker, "get_worker_db", lambda _key: connection)

    def deny_context(*_args, **_kwargs):
        raise PermissionError("scope denied")

    monkeypatch.setattr(worker, "set_worker_tenant_context", deny_context)

    with pytest.raises(PermissionError, match="scope denied"):
        worker.delete_mock_sensor_alerts(LOCATION_ID)

    assert events == [("rollback",), ("close",)]
