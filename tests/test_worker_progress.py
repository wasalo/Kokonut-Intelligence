"""Read-only durable-progress health contract for the Standard worker role."""

from __future__ import annotations

import pytest

from services.core import worker_progress


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.params = None
        self.closed = False

    def execute(self, query, params):
        self.query = query
        self.params = params

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, rows):
        self.cursor_instance = _Cursor(rows)
        self.readonly = None
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def set_session(self, *, readonly):
        self.readonly = readonly

    def close(self):
        self.closed = True


def _rows(*, scheduler=(0, 0), events=(0, 0), notifications=(0, 0)):
    return [
        ("events", *events),
        ("notifications", *notifications),
        ("scheduler", *scheduler),
    ]


def test_idle_workers_are_healthy_and_probe_is_read_only():
    connection = _Connection(_rows())
    factory_calls = []

    result = worker_progress.check_progress(
        connection_factory=lambda **kwargs: factory_calls.append(kwargs) or connection,
        enabled_workers=worker_progress.WORKER_NAMES,
    )

    assert result == {
        "status": "healthy",
        "state": "idle",
        "stale_after_seconds": 300,
        "workers": {
            "events": {"active": 0, "stale": 0},
            "notifications": {"active": 0, "stale": 0},
            "scheduler": {"active": 0, "stale": 0},
        },
    }
    assert factory_calls == [{"connect_timeout": 3}]
    assert connection.readonly is True
    assert connection.cursor_instance.params == (300,)
    assert connection.cursor_instance.closed
    assert connection.closed


def test_active_work_with_current_durable_leases_is_healthy():
    connection = _Connection(_rows(scheduler=(2, 0), events=(1, 0), notifications=(3, 0)))

    result = worker_progress.check_progress(
        connection_factory=lambda **_kwargs: connection,
        stale_seconds="90",
        enabled_workers=worker_progress.WORKER_NAMES,
    )

    assert result["status"] == "healthy"
    assert result["state"] == "active"
    assert result["stale_after_seconds"] == 90
    assert result["workers"]["scheduler"] == {"active": 2, "stale": 0}


@pytest.mark.parametrize(
    ("worker", "counts"),
    [
        ("scheduler", (2, 1)),
        ("events", (1, 1)),
        ("notifications", (4, 2)),
    ],
)
def test_stale_active_work_makes_health_unhealthy(worker, counts):
    active = {"scheduler": (0, 0), "events": (0, 0), "notifications": (0, 0)}
    active[worker] = counts
    connection = _Connection(_rows(**active))

    result = worker_progress.check_progress(
        connection_factory=lambda **_kwargs: connection,
        enabled_workers=worker_progress.WORKER_NAMES,
    )

    assert result["status"] == "unhealthy"
    assert result["state"] == "stale"
    assert result["workers"][worker] == {"active": counts[0], "stale": counts[1]}


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "300seconds", "2678401", " 0300"])
def test_stale_threshold_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        worker_progress.stale_threshold_seconds(value)


def test_threshold_can_be_configured_with_positive_bounded_integer(monkeypatch):
    monkeypatch.setenv("KOKONUT_WORKER_PROGRESS_STALE_SECONDS", "120")
    assert worker_progress.stale_threshold_seconds() == 120
    assert worker_progress.stale_threshold_seconds(1) == 1
    assert worker_progress.stale_threshold_seconds(worker_progress.MAX_STALE_SECONDS) == worker_progress.MAX_STALE_SECONDS


def test_database_failure_fails_closed_without_exposing_exception_message():
    def fail_connect(**_kwargs):
        raise RuntimeError("postgresql://private-user:synthetic-secret@database/private")

    result = worker_progress.check_progress(connection_factory=fail_connect)

    assert result == {
        "status": "unhealthy",
        "state": "database_unavailable",
        "stale_after_seconds": 300,
        "workers": {},
        "error": "RuntimeError",
    }
    assert "synthetic-secret" not in repr(result)


def test_probe_query_failure_closes_connection_and_hides_database_message():
    connection = _Connection([])

    def fail_query(_query, _params):
        raise RuntimeError("synthetic credential: password-do-not-print")

    connection.cursor_instance.execute = fail_query
    result = worker_progress.check_progress(
        connection_factory=lambda **_kwargs: connection,
        enabled_workers=worker_progress.WORKER_NAMES,
    )

    assert result["status"] == "unhealthy"
    assert result["state"] == "database_unavailable"
    assert result["error"] == "RuntimeError"
    assert connection.cursor_instance.closed
    assert connection.closed
    assert "password-do-not-print" not in repr(result)


def test_query_reads_only_durable_aggregate_state():
    query = worker_progress._progress_sql(worker_progress.WORKER_NAMES).lower()

    assert "from task_run" in query
    assert "from platform_event" in query
    assert "from notification_outbox" in query
    assert "lease_expires_at" in query
    assert "status = 'running'" in query
    assert "status = 'processing'" in query
    assert "insert " not in query
    assert "update " not in query
    assert "payload" not in query
    assert "worker_id" not in query


def test_disabled_queues_are_not_queried_or_reported_as_stale():
    connection = _Connection([("scheduler", 0, 0)])

    result = worker_progress.check_progress(
        connection_factory=lambda **_kwargs: connection,
        enabled_workers=("scheduler",),
    )

    assert result["status"] == "healthy"
    assert result["state"] == "idle"
    assert set(result["workers"]) == {"scheduler"}
    query = connection.cursor_instance.query.lower()
    assert "from task_run" in query
    assert "from platform_event" not in query
    assert "from notification_outbox" not in query


def test_invalid_threshold_fails_closed_before_database_access():
    called = False

    def connect(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("database should not be opened")

    result = worker_progress.check_progress(
        stale_seconds="not-a-number",
        connection_factory=connect,
        enabled_workers=worker_progress.WORKER_NAMES,
    )

    assert result["status"] == "unhealthy"
    assert result["state"] == "invalid_configuration"
    assert called is False


def test_no_enabled_workers_fails_closed_before_database_access():
    called = False

    def connect(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("database should not be opened")

    result = worker_progress.check_progress(
        connection_factory=connect,
        enabled_workers=(),
    )

    assert result["status"] == "unhealthy"
    assert result["state"] == "no_workers_enabled"
    assert called is False
