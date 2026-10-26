"""Focused contract checks for scheduled signed anomaly-event replay."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import sensor_anomaly_scan_worker, sensor_anomaly_worker

LOCATION_ID = "a0000000-0000-0000-0000-000000000001"


class _Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters):
        self.connection.statement = statement
        self.connection.parameters = parameters

    def fetchall(self):
        return self.connection.rows


class _Connection:
    autocommit = False

    def __init__(self, rows):
        self.rows = rows
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_default_off_feature_fails_before_worker_credentials_or_database(monkeypatch):
    monkeypatch.setattr(sensor_anomaly_scan_worker, "require_feature", MagicMock(
        side_effect=RuntimeError("disabled")
    ))
    with (
        patch.object(sensor_anomaly_worker, "get_worker_credential") as credential,
        patch.object(sensor_anomaly_worker, "get_worker_db") as get_db,
        pytest.raises(RuntimeError, match="disabled"),
    ):
        sensor_anomaly_scan_worker.run(location_id=LOCATION_ID)
    credential.assert_not_called()
    get_db.assert_not_called()


@pytest.mark.parametrize(
    ("location_id", "since", "batch_size"),
    [
        ("not-a-uuid", None, 100),
        (LOCATION_ID, datetime(2026, 10, 26), 100),
        (LOCATION_ID, None, 0),
        (LOCATION_ID, None, 101),
    ],
)
def test_replay_input_validation_precedes_database_access(
    monkeypatch, location_id, since, batch_size
):
    monkeypatch.setattr(sensor_anomaly_scan_worker, "require_feature", lambda _feature: None)
    with (
        patch.object(sensor_anomaly_worker, "get_worker_credential") as credential,
        patch.object(sensor_anomaly_worker, "get_worker_db") as get_db,
        pytest.raises(ValueError),
    ):
        sensor_anomaly_scan_worker.run(
            location_id=location_id, since=since, batch_size=batch_size
        )
    credential.assert_not_called()
    get_db.assert_not_called()


def test_pending_event_inventory_uses_signed_location_and_bounded_function(monkeypatch):
    created_at = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    connection = _Connection([("event-id", "sensor-id", created_at)])
    monkeypatch.setattr(sensor_anomaly_worker, "get_worker_credential", lambda _key: "x" * 40)
    monkeypatch.setattr(sensor_anomaly_worker, "get_worker_db", lambda _key: connection)
    set_context = MagicMock()
    monkeypatch.setattr(sensor_anomaly_worker, "set_worker_tenant_context", set_context)

    since = created_at - timedelta(minutes=5)
    result = sensor_anomaly_worker.list_pending_sensor_reading_events(
        location_id=LOCATION_ID.upper(), since=since, batch_size=5
    )

    set_context.assert_called_once_with(
        connection,
        credential="x" * 40,
        location_id=LOCATION_ID,
        resource="sensor_reading",
        action="process",
    )
    assert "kokonut_security.list_sensor_anomaly_events_since" in connection.statement
    assert connection.parameters == (LOCATION_ID, since, 5)
    assert result == [{"event_id": "event-id", "sensor_id": "sensor-id", "created_at": created_at}]
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed


def test_default_scan_window_is_the_database_maximum_recovery_horizon(monkeypatch):
    monkeypatch.setattr(sensor_anomaly_scan_worker, "require_feature", lambda _feature: None)
    since = datetime.now(timezone.utc)
    replay = MagicMock(return_value={"events_found": 0})
    monkeypatch.setattr(sensor_anomaly_scan_worker, "replay_recent_sensor_reading_events", replay)

    sensor_anomaly_scan_worker.run(location_id=LOCATION_ID, since=since)

    assert replay.call_args.kwargs["since"] == since
    assert replay.call_args.kwargs["batch_size"] == 100


def test_inventory_failure_rolls_back_and_closes(monkeypatch):
    connection = _Connection([])

    def fail_execute(*_args, **_kwargs):
        raise RuntimeError("synthetic database denial")

    monkeypatch.setattr(sensor_anomaly_worker, "get_worker_credential", lambda _key: "x" * 40)
    monkeypatch.setattr(sensor_anomaly_worker, "get_worker_db", lambda _key: connection)
    monkeypatch.setattr(sensor_anomaly_worker, "set_worker_tenant_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(_Cursor, "execute", fail_execute)

    with pytest.raises(RuntimeError, match="synthetic database denial"):
        sensor_anomaly_worker.list_pending_sensor_reading_events(
            location_id=LOCATION_ID,
            since=datetime.now(timezone.utc) - timedelta(hours=1),
        )

    assert connection.rollbacks == 1
    assert connection.closed


def test_replay_delegates_each_event_to_idempotent_handler_and_aggregates(monkeypatch):
    event_time = datetime.now(timezone.utc)
    monkeypatch.setattr(sensor_anomaly_scan_worker, "require_feature", lambda _feature: None)
    monkeypatch.setattr(
        sensor_anomaly_worker,
        "list_pending_sensor_reading_events",
        lambda **_kwargs: [
            {"event_id": "event-a", "sensor_id": "sensor-a", "created_at": event_time},
            {"event_id": "event-b", "sensor_id": "sensor-b", "created_at": event_time},
        ],
    )
    process = MagicMock(side_effect=[
        {"rules": 3, "reserved": 3, "alerts": 1, "claims": 0,
         "notifications": 1, "actuation_intents": 0, "skipped": 0},
        {"rules": 2, "reserved": 2, "alerts": 0, "claims": 0,
         "notifications": 0, "actuation_intents": 0, "skipped": 2},
    ])
    monkeypatch.setattr(sensor_anomaly_worker, "process_sensor_reading", process)

    result = sensor_anomaly_scan_worker.run(
        location_id=LOCATION_ID,
        since=event_time - timedelta(hours=1),
        batch_size=10,
    )

    assert result == {
        "events_found": 2, "events_processed": 2, "rules": 5, "reserved": 5,
        "alerts": 1, "claims": 0, "notifications": 1,
        "actuation_intents": 0, "skipped": 2,
    }
    assert [call.kwargs for call in process.call_args_list] == [
        {"sensor_id": "sensor-a", "location_id": LOCATION_ID, "event_id": "event-a"},
        {"sensor_id": "sensor-b", "location_id": LOCATION_ID, "event_id": "event-b"},
    ]
