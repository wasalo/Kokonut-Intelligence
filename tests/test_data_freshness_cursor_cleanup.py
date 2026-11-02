"""Freshness worker cursors close on SQL, fetch, and transaction failures."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from services.ingestion import data_freshness, freshness_worker


class _Cursor:
    def __init__(self, spec=None):
        self.spec = spec or {}
        self.closed = False
        self.execute_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
        return False

    def execute(self, *_args):
        self.execute_calls += 1
        if self.spec.get("execute_fails"):
            raise RuntimeError("synthetic freshness execute failure")

    def fetchone(self):
        if self.spec.get("fetchone_fails"):
            raise RuntimeError("synthetic freshness fetchone failure")
        return self.spec.get("fetchone_result", ("synthetic-id",))

    def fetchall(self):
        if self.spec.get("fetchall_fails"):
            raise RuntimeError("synthetic freshness fetchall failure")
        return self.spec.get("fetchall_result", [])

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, specs=(), *, commit_fails=False):
        self.specs = list(specs)
        self.cursors = []
        self.commits = 0
        self.rollbacks = 0
        self.commit_fails = commit_fails

    def cursor(self, **_kwargs):
        spec = self.specs[len(self.cursors)] if len(self.cursors) < len(self.specs) else {}
        cursor = _Cursor(spec)
        self.cursors.append(cursor)
        return cursor

    def commit(self):
        self.commits += 1
        if self.commit_fails:
            raise RuntimeError("synthetic freshness commit failure")

    def rollback(self):
        self.rollbacks += 1


def test_freshness_rows_adapter_closes_cursor_on_execute_and_fetch_failure():
    for spec, operation, message in (
        ({"execute_fails": True}, lambda persistence: persistence.list_configs("weather"), "execute"),
        ({"fetchall_fails": True}, lambda persistence: persistence.list_configs("weather"), "fetchall"),
    ):
        connection = _Connection([spec])
        persistence = freshness_worker.FreshnessPersistence(connection)

        with pytest.raises(RuntimeError, match=f"freshness {message} failure"):
            operation(persistence)

        assert len(connection.cursors) == 1
        assert connection.cursors[0].closed


def test_freshness_one_adapter_closes_cursor_on_execute_and_fetch_failure():
    for spec, message in (
        ({"execute_fails": True}, "execute"),
        ({"fetchone_fails": True}, "fetchone"),
    ):
        connection = _Connection([spec])
        persistence = freshness_worker.FreshnessPersistence(connection)

        with pytest.raises(RuntimeError, match=f"freshness {message} failure"):
            persistence.latest_data_at("weather", False, None)

        assert len(connection.cursors) == 1
        assert connection.cursors[0].closed


def _freshness_persistence(*, latest_data_at=None, latest_data_error=None):
    persistence = Mock()
    persistence.list_configs.return_value = [{
        "id": "config-id",
        "source_system": "weather",
        "stale_threshold_minutes": 30,
        "critical_threshold_minutes": 60,
        "location_scoped": False,
        "alert_cooldown_minutes": 60,
        "escalation_cooldown_minutes": 15,
    }]
    if latest_data_error is not None:
        persistence.latest_data_at.side_effect = latest_data_error
    else:
        persistence.latest_data_at.return_value = latest_data_at or datetime.now(timezone.utc)
    persistence.insert_check.return_value = "check-id"
    persistence.lock_alert_state.return_value = {
        "id": "state-id",
        "current_status": "fresh",
        "last_event_status": "fresh",
        "last_event_at": None,
    }
    return persistence


@pytest.mark.parametrize(
    ("fail_cursor", "expected_rollbacks"),
    [(0, 0), (1, 1)],
    ids=("savepoint", "release-savepoint"),
)
def test_freshness_transaction_cursors_close_when_commands_fail(
    fail_cursor, expected_rollbacks
):
    specs = [{} for _ in range(fail_cursor)] + [{"execute_fails": True}]
    connection = _Connection(specs)
    persistence = _freshness_persistence()

    with pytest.raises(RuntimeError, match="freshness execute failure"):
        data_freshness.check_freshness(connection, persistence=persistence)

    assert all(cursor.closed for cursor in connection.cursors)
    assert connection.commits == 0
    assert connection.rollbacks == expected_rollbacks


def test_freshness_rollback_savepoint_cursor_closes_when_rollback_fails():
    connection = _Connection([{}, {"execute_fails": True}])
    persistence = _freshness_persistence(latest_data_error=RuntimeError("source read failed"))

    with pytest.raises(RuntimeError, match="freshness execute failure"):
        data_freshness.check_freshness(connection, persistence=persistence)

    assert len(connection.cursors) == 2
    assert all(cursor.closed for cursor in connection.cursors)
    assert connection.commits == 0


def test_freshness_commit_failure_rolls_back_and_closes_transaction_cursors():
    connection = _Connection(commit_fails=True)
    persistence = _freshness_persistence()

    with pytest.raises(RuntimeError, match="freshness commit failure"):
        data_freshness.check_freshness(connection, persistence=persistence)

    assert all(cursor.closed for cursor in connection.cursors)
    assert connection.commits == 1
    assert connection.rollbacks == 1
