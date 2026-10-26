"""The isolated event dispatcher uses only its bounded worker identity."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from services.events.dispatch_worker import IsolatedEventBus, run_once


def _event_tuple(*, retry_count: int = 0, max_retries: int = 3):
    return (
        "10000000-0000-0000-0000-000000000001",
        "sensor_reading",
        {"location_id": "20000000-0000-0000-0000-000000000001"},
        retry_count,
        max_retries,
        "30000000-0000-0000-0000-000000000001",
    )


def test_dispatch_claims_and_completes_only_through_bounded_functions(monkeypatch):
    bus = IsolatedEventBus(conn=Mock(), lease_seconds=300)
    calls = []
    handler = (
        "40000000-0000-0000-0000-000000000001",
        "services.ingestion.anomaly_detector",
        "handle_sensor_reading",
        30,
        None,
    )
    results = iter(([_event_tuple()], [handler], (True,), (True,), (True,), (True,)))

    def invoke(*args, **kwargs):
        calls.append(("handler", args, kwargs))
        return "success", None

    monkeypatch.setattr(bus, "_function", lambda query, parameters, **kwargs: calls.append((query, parameters)) or next(results))
    monkeypatch.setattr(bus, "_invoke_handler", invoke)

    outcome = bus.process_pending(batch_size=7, worker_id="worker-7")

    assert outcome == {"processed": 1, "failed": 0, "skipped": 0, "lease_lost": 0}
    function_calls = [call[0] for call in calls if isinstance(call[0], str) and call[0].startswith("SELECT")]
    assert function_calls == [
        "SELECT * FROM kokonut_security.claim_platform_event_batch(%s, %s, %s)",
        "SELECT * FROM kokonut_security.list_platform_event_handlers(%s, %s, %s, %s)",
        "SELECT kokonut_security.renew_platform_event_lease(%s, %s, %s, %s)",
        "SELECT kokonut_security.begin_platform_event_handler(%s, %s, %s, %s)",
        "SELECT kokonut_security.finish_platform_event_handler(%s, %s, %s, %s, %s, %s, %s)",
        "SELECT kokonut_security.complete_platform_event(%s, %s, %s)",
    ]
    assert calls[-1][1] == (_event_tuple()[0], "worker-7", _event_tuple()[-1])


def test_failed_handler_retries_through_bounded_function_and_preserves_counts(monkeypatch):
    bus = IsolatedEventBus(conn=Mock(), lease_seconds=300)
    calls = []
    handler = (
        "40000000-0000-0000-0000-000000000001",
        "services.events.handlers",
        "handle_alert_notification",
        45,
        "error",
    )
    results = iter(([_event_tuple(retry_count=1, max_retries=4)], [handler], (True,), (True,), (True,), ("pending",)))
    monkeypatch.setattr(bus, "_function", lambda query, parameters, **kwargs: calls.append((query, parameters)) or next(results))
    monkeypatch.setattr(bus, "_invoke_handler", lambda *_args, **_kwargs: ("error", "Handler failed (OSError)"))

    outcome = bus.process_pending(batch_size=1, worker_id="worker-8")

    assert outcome == {"processed": 0, "failed": 1, "skipped": 0, "lease_lost": 0}
    retry_query, retry_params = calls[-1]
    assert retry_query == "SELECT kokonut_security.retry_platform_event(%s, %s, %s, %s, %s)"
    assert retry_params == (_event_tuple()[0], "worker-8", _event_tuple()[-1], 2, 4)


def test_stale_lease_stops_before_handler_execution(monkeypatch):
    bus = IsolatedEventBus(conn=Mock(), lease_seconds=300)
    results = iter(([_event_tuple()], [
        ("40000000-0000-0000-0000-000000000001", "services.events.handlers", "handle_alert_notification", 30, None)
    ], (False,)))
    monkeypatch.setattr(bus, "_function", lambda *_args, **_kwargs: next(results))
    invoke = Mock()
    monkeypatch.setattr(bus, "_invoke_handler", invoke)

    outcome = bus.process_pending(batch_size=1, worker_id="stale-worker")

    assert outcome == {"processed": 0, "failed": 0, "skipped": 0, "lease_lost": 1}
    invoke.assert_not_called()


def test_no_enabled_handlers_completes_as_skipped(monkeypatch):
    bus = IsolatedEventBus(conn=Mock(), lease_seconds=300)
    results = iter(([_event_tuple()], [], (True,)))
    calls = []
    monkeypatch.setattr(bus, "_function", lambda query, params, **kwargs: calls.append(query) or next(results))

    outcome = bus.process_pending(batch_size=1, worker_id="worker-9")

    assert outcome == {"processed": 0, "failed": 0, "skipped": 1, "lease_lost": 0}
    assert calls[-1] == "SELECT kokonut_security.complete_platform_event(%s, %s, %s)"


@pytest.mark.parametrize(
    ("worker_id", "batch_size", "lease_seconds"),
    [("bad worker", 1, 300), ("worker", 0, 300), ("worker", 101, 300), ("worker", 1, 29)],
)
def test_invalid_worker_arguments_fail_before_connection(monkeypatch, worker_id, batch_size, lease_seconds):
    get_db = Mock()
    monkeypatch.setattr("services.events.dispatch_worker.get_worker_db", get_db)

    with pytest.raises(ValueError):
        from services.events.dispatch_worker import _validate

        _validate(worker_id, batch_size, lease_seconds)

    get_db.assert_not_called()


def test_run_once_requires_isolated_marker_before_database_access(monkeypatch):
    monkeypatch.setattr("services.events.dispatch_worker.require_feature", lambda _name: None)
    monkeypatch.setattr("services.events.dispatch_worker.isolated_worker_key", lambda: None)
    get_db = Mock()
    monkeypatch.setattr("services.events.dispatch_worker.get_worker_db", get_db)

    with pytest.raises(RuntimeError, match="identity was not established"):
        run_once()

    get_db.assert_not_called()


def test_run_once_uses_and_closes_only_the_event_dispatch_database(monkeypatch):
    connection = Mock()
    monkeypatch.setattr("services.events.dispatch_worker.require_feature", lambda _name: None)
    monkeypatch.setattr("services.events.dispatch_worker.isolated_worker_key", lambda: "event_dispatch")
    get_db = Mock(return_value=connection)
    monkeypatch.setattr("services.events.dispatch_worker.get_worker_db", get_db)
    process_pending = Mock(return_value={"processed": 1, "failed": 0, "skipped": 0, "lease_lost": 0})
    monkeypatch.setattr(IsolatedEventBus, "process_pending", process_pending)

    result = run_once("worker-10", 5, 600)

    assert result["processed"] == 1
    get_db.assert_called_once_with("event_dispatch")
    process_pending.assert_called_once_with(5, "worker-10")
    connection.close.assert_called_once_with()
