"""Keep remote-sensing status and attempt cursors closed on write failures."""

from datetime import datetime, timezone

import pytest

from services.ingestion import remote_sensing_fetcher


class _FailingCursor:
    def __init__(self):
        self.closed = False

    def execute(self, *_args):
        raise RuntimeError("synthetic write failure")

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self):
        self.cursor_instance = _FailingCursor()

    def cursor(self):
        return self.cursor_instance


@pytest.mark.parametrize(
    "operation",
    [
        pytest.param(
            lambda conn: remote_sensing_fetcher._update_job_status(
                conn, "synthetic-job", status="error"
            ),
            id="update-status",
        ),
        pytest.param(
            lambda conn: remote_sensing_fetcher._record_provider_attempt(
                conn,
                "synthetic-job",
                {
                    "provider": "gee",
                    "attempt_number": 1,
                    "outcome": "retryable",
                    "started_at": datetime.now(timezone.utc),
                    "finished_at": datetime.now(timezone.utc),
                },
            ),
            id="record-provider-attempt",
        ),
    ],
)
def test_write_cursor_closes_when_execute_fails(operation):
    connection = _Connection()

    with pytest.raises(RuntimeError, match="synthetic write failure"):
        operation(connection)

    assert connection.cursor_instance.closed
