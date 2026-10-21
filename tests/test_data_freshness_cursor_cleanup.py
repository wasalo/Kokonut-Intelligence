"""Ensure freshness database-helper cursors close on SQL/fetch failures."""

from datetime import datetime, timezone

import pytest

from services.ingestion import data_freshness


class _Cursor:
    def __init__(self, spec):
        self.spec = spec
        self.execute_count = 0
        self.closed = False

    def execute(self, *_args):
        self.execute_count += 1
        if self.spec.get("execute_fail_at") == self.execute_count:
            raise RuntimeError("synthetic freshness SQL failure")

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
    def __init__(self, specs):
        self.specs = list(specs)
        self.cursors = []

    def cursor(self, **_kwargs):
        spec = self.specs[len(self.cursors)] if len(self.cursors) < len(self.specs) else {}
        cursor = _Cursor(spec)
        self.cursors.append(cursor)
        return cursor


def _raise_and_assert_closed(operation, specs):
    connection = _Connection(specs)

    with pytest.raises(RuntimeError, match="synthetic freshness"):
        operation(connection)

    assert connection.cursors
    assert all(cursor.closed for cursor in connection.cursors)


@pytest.mark.parametrize(
    ("operation", "specs"),
    [
        pytest.param(
            lambda conn: data_freshness._query_freshness_configs(conn),
            [{"execute_fail_at": 1}],
            id="config-query-execute",
        ),
        pytest.param(
            lambda conn: data_freshness._query_freshness_configs(conn),
            [{"fetchall_fails": True}],
            id="config-query-fetch",
        ),
        pytest.param(
            data_freshness._location_ids,
            [{"execute_fail_at": 1}],
            id="location-list-execute",
        ),
        pytest.param(
            data_freshness._location_ids,
            [{"fetchall_fails": True}],
            id="location-list-fetch",
        ),
        pytest.param(
            lambda conn: data_freshness._query_latest_ingestion(conn, "weather"),
            [{"execute_fail_at": 1}],
            id="latest-ingestion-execute",
        ),
        pytest.param(
            lambda conn: data_freshness._query_latest_ingestion(conn, "weather"),
            [{"fetchone_fails": True}],
            id="latest-ingestion-fetch",
        ),
        pytest.param(
            lambda conn: data_freshness._alert_state(conn, "weather", None),
            [{"execute_fail_at": 1}],
            id="alert-state-select-execute",
        ),
        pytest.param(
            lambda conn: data_freshness._alert_state(conn, "weather", None),
            [{"fetchone_fails": True}],
            id="alert-state-select-fetch",
        ),
        pytest.param(
            lambda conn: data_freshness._alert_state(conn, "weather", None),
            [{"fetchone_result": None}, {"execute_fail_at": 1}],
            id="alert-state-insert-execute",
        ),
        pytest.param(
            lambda conn: data_freshness._alert_state(conn, "weather", None),
            [{"fetchone_result": None}, {}, {"execute_fail_at": 1}],
            id="alert-state-lock-execute",
        ),
        pytest.param(
            lambda conn: data_freshness._alert_state(conn, "weather", None),
            [{"fetchone_result": None}, {}, {"fetchone_fails": True}],
            id="alert-state-lock-fetch",
        ),
    ],
)
def test_freshness_read_and_state_cursors_close_on_failure(operation, specs):
    _raise_and_assert_closed(operation, specs)


@pytest.mark.parametrize(
    ("operation", "specs"),
    [
        pytest.param(
            lambda conn: data_freshness._persist_alert_event(
                conn,
                {"id": "state-id"},
                "check-id",
                "weather",
                None,
                "alert",
                "fresh",
                "stale",
                20,
                datetime.now(timezone.utc),
            ),
            [{"execute_fail_at": 1}],
            id="alert-history-insert-failure",
        ),
        pytest.param(
            lambda conn: data_freshness._persist_alert_event(
                conn,
                {"id": "state-id"},
                "check-id",
                "weather",
                None,
                "alert",
                "fresh",
                "stale",
                20,
                datetime.now(timezone.utc),
            ),
            [{"execute_fail_at": 2}],
            id="alert-state-update-failure",
        ),
        pytest.param(
            lambda conn: data_freshness._persist_delivery_attempt(
                conn, "alert-id", "webhook", delivered=False
            ),
            [{"execute_fail_at": 1}],
            id="delivery-attempt-insert-failure",
        ),
        pytest.param(
            lambda conn: data_freshness._persist_delivery_attempt(
                conn, "alert-id", "webhook", delivered=True
            ),
            [{"execute_fail_at": 2}],
            id="delivery-state-update-failure",
        ),
        pytest.param(
            lambda conn: data_freshness._insert_check_result(
                conn, "config-id", "weather", None, None, None, "no_data"
            ),
            [{"execute_fail_at": 1}],
            id="check-result-insert-failure",
        ),
        pytest.param(
            lambda conn: data_freshness._insert_check_result(
                conn, "config-id", "weather", None, None, None, "no_data"
            ),
            [{"fetchone_fails": True}],
            id="check-result-receipt-failure",
        ),
    ],
)
def test_freshness_write_helper_cursors_close_on_failure(operation, specs):
    _raise_and_assert_closed(operation, specs)
