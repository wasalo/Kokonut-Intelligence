"""Read-only durable-progress health contract for the Standard worker role."""

from __future__ import annotations

import json
import os
import time
import uuid

import pytest

from services.core import worker_progress


@pytest.fixture(autouse=True)
def fresh_supervisor_heartbeat(monkeypatch, tmp_path):
    path = tmp_path / "worker-progress" / "supervisor.json"
    path.parent.mkdir(mode=0o700)
    path.write_text(
        json.dumps(
            {
                "generation": uuid.uuid4().hex,
                "monotonic_ns": time.monotonic_ns(),
                "pid": os.getpid(),
            }
        )
    )
    path.chmod(0o600)
    monkeypatch.setenv(worker_progress.HEARTBEAT_FILE_ENV, str(path))
    return path


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


def _worker_row(worker, values):
    active, stale, *backlog = values
    queued, oldest_due_seconds = backlog or (0, None)
    return worker, active, stale, queued, oldest_due_seconds


def _rows(*, scheduler=(0, 0), events=(0, 0), notifications=(0, 0)):
    return [
        _worker_row("events", events),
        _worker_row("notifications", notifications),
        _worker_row("scheduler", scheduler),
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
        "backlog_after_seconds": 900,
        "backlog_workers": [],
        "supervisor": {"alive": True, "age_seconds": 0},
        "workers": {
            "events": {"active": 0, "stale": 0, "queued": 0, "oldest_due_seconds": None},
            "notifications": {"active": 0, "stale": 0, "queued": 0, "oldest_due_seconds": None},
            "scheduler": {"active": 0, "stale": 0, "queued": 0, "oldest_due_seconds": None},
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
    assert result["backlog_after_seconds"] == 900
    assert result["supervisor"]["alive"] is True
    assert result["workers"]["scheduler"] == {
        "active": 2, "stale": 0, "queued": 0, "oldest_due_seconds": None
    }


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
    assert result["workers"][worker] == {
        "active": counts[0], "stale": counts[1], "queued": 0, "oldest_due_seconds": None
    }


@pytest.mark.parametrize("worker", worker_progress.WORKER_NAMES)
def test_old_due_work_makes_health_unhealthy_without_exposing_rows(worker):
    values = {name: (0, 0) for name in worker_progress.WORKER_NAMES}
    values[worker] = (0, 0, 4, 901)
    connection = _Connection(_rows(**values))

    result = worker_progress.check_progress(
        connection_factory=lambda **_kwargs: connection,
        enabled_workers=worker_progress.WORKER_NAMES,
    )

    assert result["status"] == "unhealthy"
    assert result["state"] == "backlog"
    assert result["backlog_workers"] == [worker]
    assert result["workers"][worker] == {
        "active": 0,
        "stale": 0,
        "queued": 4,
        "oldest_due_seconds": 901,
    }
    assert "payload" not in repr(result)
    assert "id" not in result


def test_due_backlog_younger_than_threshold_is_healthy():
    connection = _Connection(_rows(events=(0, 0, 5, 899)))

    result = worker_progress.check_progress(
        connection_factory=lambda **_kwargs: connection,
        backlog_seconds=900,
        enabled_workers=worker_progress.WORKER_NAMES,
    )

    assert result["status"] == "healthy"
    assert result["state"] == "idle"
    assert result["backlog_workers"] == []
    assert result["workers"]["events"]["queued"] == 5


def test_future_dated_pending_event_has_zero_age():
    connection = _Connection([_worker_row("events", (0, 0, 1, 0))])

    result = worker_progress.check_progress(
        connection_factory=lambda **_kwargs: connection,
        enabled_workers=("events",),
    )

    assert result["status"] == "healthy"
    assert result["workers"]["events"]["queued"] == 1
    assert result["workers"]["events"]["oldest_due_seconds"] == 0


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "300seconds", "2678401", " 0300"])
def test_stale_threshold_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        worker_progress.stale_threshold_seconds(value)


def test_threshold_can_be_configured_with_positive_bounded_integer(monkeypatch):
    monkeypatch.setenv("KOKONUT_WORKER_PROGRESS_STALE_SECONDS", "120")
    assert worker_progress.stale_threshold_seconds() == 120
    assert worker_progress.stale_threshold_seconds(1) == 1
    assert worker_progress.stale_threshold_seconds(worker_progress.MAX_STALE_SECONDS) == worker_progress.MAX_STALE_SECONDS


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "300seconds", "2678401", " 0900"])
def test_backlog_threshold_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        worker_progress.backlog_threshold_seconds(value)


def test_backlog_threshold_can_be_configured(monkeypatch):
    monkeypatch.setenv("KOKONUT_WORKER_PROGRESS_BACKLOG_SECONDS", "1200")
    assert worker_progress.backlog_threshold_seconds() == 1200
    assert worker_progress.backlog_threshold_seconds(1) == 1
    assert worker_progress.backlog_threshold_seconds(worker_progress.MAX_STALE_SECONDS) == worker_progress.MAX_STALE_SECONDS


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "60seconds", "2678401", " 0060"])
def test_heartbeat_threshold_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        worker_progress.heartbeat_threshold_seconds(value)


def test_heartbeat_threshold_can_be_configured(monkeypatch):
    monkeypatch.setenv("KOKONUT_WORKER_PROGRESS_HEARTBEAT_SECONDS", "90")
    assert worker_progress.heartbeat_threshold_seconds() == 90
    assert worker_progress.heartbeat_threshold_seconds(1) == 1
    assert worker_progress.heartbeat_threshold_seconds(worker_progress.MAX_STALE_SECONDS) == worker_progress.MAX_STALE_SECONDS


def test_database_failure_fails_closed_without_exposing_exception_message():
    def fail_connect(**_kwargs):
        raise RuntimeError("postgresql://private-user:synthetic-secret@database/private")

    result = worker_progress.check_progress(connection_factory=fail_connect)

    assert result == {
        "status": "unhealthy",
        "state": "database_unavailable",
        "stale_after_seconds": 300,
        "backlog_after_seconds": 900,
        "backlog_workers": [],
        "supervisor": {"alive": True, "age_seconds": 0},
        "workers": {},
        "error": "RuntimeError",
    }
    assert "synthetic-secret" not in repr(result)


@pytest.mark.parametrize(
    "failure",
    ["missing", "malformed", "stale", "future", "dead", "permissions", "directory_permissions"],
)
def test_invalid_supervisor_heartbeat_fails_closed_before_database_access(
    failure, fresh_supervisor_heartbeat, monkeypatch
):
    path = fresh_supervisor_heartbeat
    monkeypatch.setenv("KOKONUT_WORKER_PROGRESS_HEARTBEAT_SECONDS", "60")
    if failure == "missing":
        path.unlink()
    elif failure == "malformed":
        path.write_text("not-json")
        path.chmod(0o600)
    elif failure in {"stale", "future", "dead"}:
        payload = json.loads(path.read_text())
        if failure == "stale":
            payload["monotonic_ns"] = time.monotonic_ns() - 61_000_000_000
        elif failure == "future":
            payload["monotonic_ns"] = time.monotonic_ns() + 1_000_000_000
        else:
            payload["pid"] = 2_147_483_647
        path.write_text(json.dumps(payload))
        path.chmod(0o600)
    elif failure == "permissions":
        path.chmod(0o644)
    else:
        path.parent.chmod(0o755)

    factory_calls = []

    def connect(**_kwargs):
        factory_calls.append(True)
        raise AssertionError("unresponsive supervisor must fail before database access")

    result = worker_progress.check_progress(
        connection_factory=connect,
        enabled_workers=worker_progress.WORKER_NAMES,
    )

    assert result["status"] == "unhealthy"
    assert result["state"] == "supervisor_unresponsive"
    assert result["supervisor"]["alive"] is False
    assert set(result["supervisor"]) == {"alive", "age_seconds"}
    assert factory_calls == []


def test_supervisor_liveness_reports_only_alive_and_aggregate_age(fresh_supervisor_heartbeat):
    result = worker_progress._supervisor_liveness(path=fresh_supervisor_heartbeat)

    assert result["alive"] is True
    assert result["age_seconds"] == 0
    assert set(result) == {"alive", "age_seconds"}


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
    assert result["backlog_after_seconds"] == 900
    assert result["supervisor"]["alive"] is True
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
    assert "status = 'pending'" in query
    assert "'retryable'" in query
    assert "greatest(0, floor(extract(epoch from" in query
    assert "available_at <= probe.checked_at" in query
    assert "retry_at <= probe.checked_at" in query
    assert "task.is_enabled = true" in query
    assert "task.lease_expires_at <= probe.checked_at" in query
    assert "dependency.last_status is distinct from 'completed'" in query
    assert "scheduled_for" in query
    assert "dead_letter" not in query
    assert "insert " not in query
    assert "update " not in query
    assert "payload" not in query
    assert "worker_id" not in query


def test_disabled_queues_are_not_queried_or_reported_as_stale():
    connection = _Connection([_worker_row("scheduler", (0, 0))])

    result = worker_progress.check_progress(
        connection_factory=lambda **_kwargs: connection,
        enabled_workers=("scheduler",),
    )

    assert result["status"] == "healthy"
    assert result["state"] == "idle"
    assert set(result["workers"]) == {"scheduler"}
    assert result["backlog_after_seconds"] == 900
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


def test_invalid_backlog_threshold_fails_closed_before_database_access():
    called = False

    def connect(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("database should not be opened")

    result = worker_progress.check_progress(
        backlog_seconds="infinite",
        connection_factory=connect,
        enabled_workers=worker_progress.WORKER_NAMES,
    )

    assert result["status"] == "unhealthy"
    assert result["state"] == "invalid_configuration"
    assert result["backlog_after_seconds"] is None
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
