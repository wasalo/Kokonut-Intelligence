"""Focused source and mocked contract checks for the baseline worker slice.

These tests are authored for the grouped acceptance batch; they are not run as
part of this change slice.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from services.ingestion import sensor_baseline_worker as worker

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/729_signed_sensor_baseline_worker.sql"
LOCATION_ID = "00000000-0000-0000-0000-000000000101"
BASELINE_ID = "00000000-0000-0000-0000-000000000102"
ALERT_ID = "00000000-0000-0000-0000-000000000103"
EVENT_ID = "00000000-0000-0000-0000-000000000104"
READING_ID = "00000000-0000-0000-0000-000000000105"
RULE_ID = "00000000-0000-0000-0000-000000000106"
DEVICE_ID = "00000000-0000-0000-0000-000000000107"


def _alert_row(outcome: str = "alert_created") -> tuple[object, ...]:
    return (
        BASELINE_ID,
        outcome,
        ALERT_ID,
        EVENT_ID,
        READING_ID,
        RULE_ID,
        DEVICE_ID,
        "warning",
        (
            "Baseline deviation: soil_moisture 40.00% is above baseline "
            "20.00% (100% deviation)"
        ),
        40.0,
        20.0,
        10,
        datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
        "Soil probe",
        "soil_moisture",
        "Kokonut Farm",
        LOCATION_ID,
    )


class _Cursor:
    def __init__(self, connection: "_Connection") -> None:
        self.connection = connection
        self.result: tuple[object, ...] | None = None

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.connection.calls.append((sql, params))
        if "evaluate_sensor_baselines" in sql:
            self.result = (self.connection.rows,)
        else:
            self.result = (self.connection.enqueues.pop(0),)

    def fetchall(self) -> list[tuple[object, ...]]:
        assert self.result is not None
        return list(self.result[0])  # type: ignore[arg-type]

    def fetchone(self) -> tuple[object, ...] | None:
        assert self.result is not None
        return self.result  # type: ignore[return-value]


class _Connection:
    def __init__(
        self,
        rows: list[tuple[object, ...]],
        enqueues: list[bool] | None = None,
    ) -> None:
        self.rows = rows
        self.enqueues = list(enqueues or [])
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def test_migration_declares_bounded_worker_function_signatures() -> None:
    sql = MIGRATION.read_text()
    assert """FUNCTION kokonut_security.evaluate_sensor_baselines(
    requested_location_id UUID
)""" in sql
    assert """FUNCTION kokonut_security.enqueue_sensor_baseline_notification_intent(
    requested_alert_event_id UUID,
    requested_baseline_id UUID,
    requested_sensor_alert_id UUID,
    requested_location_id UUID,
    requested_channel TEXT,
    requested_destination_key TEXT,
    requested_payload JSONB
)""" in sql
    assert """RETURNS TABLE (
    baseline_id UUID,
    outcome TEXT,
    sensor_alert_id UUID,
    alert_event_id UUID,
    reading_id UUID,
    alert_rule_id UUID,
    sensor_device_id UUID,
    severity TEXT,
    message TEXT,
    reading_value NUMERIC,
    threshold_value NUMERIC,
    sample_count INTEGER,
    triggered_at TIMESTAMPTZ,
    sensor_name TEXT,
    sensor_type TEXT,
    location_name TEXT,
    location_id UUID
)""" in sql
    assert "PRIMARY KEY (baseline_id, reading_id)" in sql
    assert "JOIN public.sensor_device AS source_device" in sql
    assert "JOIN public.sensor_type AS source_type" in sql
    assert "source_type.name = source.sensor_type" in sql
    assert "WHERE source_type.name = baseline.metric_name" in sql
    assert "TO kokonut_worker_execution" in sql
    assert "kokonut_sensor_baseline_owner" in sql
    assert "current_worker_scope(\n          'sensor_reading', 'process'" in sql


def test_invalid_location_fails_before_worker_credentials_or_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential = Mock(side_effect=AssertionError("credential read before preflight"))
    database = Mock(side_effect=AssertionError("database opened before preflight"))
    monkeypatch.setattr(worker, "get_worker_credential", credential)
    monkeypatch.setattr(worker, "get_worker_db", database)

    with pytest.raises(ValueError, match="location_id"):
        worker.run_baseline_check("not-a-uuid")

    credential.assert_not_called()
    database.assert_not_called()


def test_alert_enqueue_uses_signed_scope_and_commits_on_same_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _Connection([_alert_row()], [True, False])
    contexts: list[dict[str, object]] = []
    monkeypatch.setattr(
        worker,
        "get_worker_credential",
        lambda key: f"credential:{key}",
    )
    monkeypatch.setattr(worker, "get_worker_db", lambda key: connection)
    monkeypatch.setattr(
        worker,
        "set_worker_tenant_context",
        lambda conn, **kwargs: contexts.append({"connection": conn, **kwargs}),
    )
    monkeypatch.setattr(
        worker,
        "_notification_payloads",
        lambda *_args, **_kwargs: [
            ("webhook", "primary", {"text": "alert"}),
            ("email", "primary", {"subject": "alert", "body": "alert"}),
        ],
    )

    result = worker.run_baseline_check(LOCATION_ID)

    assert result == {
        "baselines_checked": 1,
        "alerts_triggered": 1,
        "alerts_replayed": 0,
        "notifications_enqueued": 1,
    }
    assert contexts == [
        {
            "connection": connection,
            "credential": "credential:sensor_anomaly",
            "location_id": LOCATION_ID,
            "resource": "sensor_reading",
            "action": "process",
        }
    ]
    assert len(connection.calls) == 3
    assert "evaluate_sensor_baselines" in connection.calls[0][0]
    assert all(
        "enqueue_sensor_baseline_notification_intent" in sql
        for sql, _params in connection.calls[1:]
    )
    assert all(params[3] == LOCATION_ID for _sql, params in connection.calls[1:])
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed


def test_empty_destination_list_is_a_valid_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _Connection([_alert_row()])
    monkeypatch.setattr(worker, "get_worker_credential", lambda _key: "credential")
    monkeypatch.setattr(worker, "get_worker_db", lambda _key: connection)
    monkeypatch.setattr(
        worker,
        "set_worker_tenant_context",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(worker, "_notification_payloads", lambda *_args, **_kwargs: [])

    result = worker.run_baseline_check(LOCATION_ID)

    assert result["alerts_triggered"] == 1
    assert result["notifications_enqueued"] == 0
    assert len(connection.calls) == 1
    assert connection.commits == 1


def test_exact_retry_returns_existing_alert_without_duplicate_intents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _Connection([_alert_row("alert_replayed")])
    payload_builder = Mock(side_effect=AssertionError("replay must not enqueue"))
    monkeypatch.setattr(worker, "get_worker_credential", lambda _key: "credential")
    monkeypatch.setattr(worker, "get_worker_db", lambda _key: connection)
    monkeypatch.setattr(
        worker,
        "set_worker_tenant_context",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(worker, "_notification_payloads", payload_builder)

    result = worker.run_baseline_check(LOCATION_ID)

    assert result == {
        "baselines_checked": 1,
        "alerts_triggered": 0,
        "alerts_replayed": 1,
        "notifications_enqueued": 0,
    }
    payload_builder.assert_not_called()
    assert len(connection.calls) == 1
    assert connection.commits == 1


def test_malformed_evaluator_result_rolls_back_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _Connection([(BASELINE_ID, "unknown-outcome")])
    monkeypatch.setattr(worker, "get_worker_credential", lambda _key: "credential")
    monkeypatch.setattr(worker, "get_worker_db", lambda _key: connection)
    monkeypatch.setattr(
        worker,
        "set_worker_tenant_context",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(worker.SensorBaselineWorkerError):
        worker.run_baseline_check(LOCATION_ID)

    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed
