"""Ensure remote-sensing read cursors close when database operations fail."""

import pytest

from services.ingestion import remote_sensing_fetcher

LOCATION_ID = "12345678-1234-5678-1234-567812345678"


class _FailingCursor:
    def __init__(self, fail_at):
        self.fail_at = fail_at
        self.closed = False

    def execute(self, *_args):
        if self.fail_at == "execute":
            raise RuntimeError("synthetic query failure")

    def fetchone(self):
        if self.fail_at == "fetchone":
            raise RuntimeError("synthetic fetch failure")
        return None

    def fetchall(self):
        if self.fail_at == "fetchall":
            raise RuntimeError("synthetic fetch failure")
        return []

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, fail_at):
        self.cursor_instance = _FailingCursor(fail_at)

    def cursor(self, **_kwargs):
        return self.cursor_instance


@pytest.mark.parametrize(
    ("operation", "fail_at"),
    [
        pytest.param(
            lambda conn: remote_sensing_fetcher._query_active_jobs(conn, LOCATION_ID),
            "execute",
            id="active-jobs-execute",
        ),
        pytest.param(
            lambda conn: remote_sensing_fetcher._query_active_jobs(conn, LOCATION_ID),
            "fetchall",
            id="active-jobs-fetch",
        ),
        pytest.param(
            lambda conn: remote_sensing_fetcher._query_job(conn, "job-id", LOCATION_ID),
            "execute",
            id="single-job-execute",
        ),
        pytest.param(
            lambda conn: remote_sensing_fetcher._query_job(conn, "job-id", LOCATION_ID),
            "fetchone",
            id="single-job-fetch",
        ),
        pytest.param(
            lambda conn: remote_sensing_fetcher.list_jobs(conn, LOCATION_ID),
            "execute",
            id="job-list-execute",
        ),
        pytest.param(
            lambda conn: remote_sensing_fetcher.list_jobs(conn, LOCATION_ID),
            "fetchall",
            id="job-list-fetch",
        ),
        pytest.param(
            lambda conn: remote_sensing_fetcher._resolve_bbox_from_job(
                conn, {"id": "job-id", "location_id": LOCATION_ID, "bbox": "BOX"}
            ),
            "execute",
            id="stored-bbox-execute",
        ),
        pytest.param(
            lambda conn: remote_sensing_fetcher._resolve_bbox_from_job(
                conn, {"id": "job-id", "location_id": LOCATION_ID, "bbox": "BOX"}
            ),
            "fetchone",
            id="stored-bbox-fetch",
        ),
        pytest.param(
            lambda conn: remote_sensing_fetcher._resolve_bbox_from_job(
                conn, {"id": "job-id", "location_id": LOCATION_ID}
            ),
            "execute",
            id="plot-bbox-execute",
        ),
        pytest.param(
            lambda conn: remote_sensing_fetcher._resolve_bbox_from_job(
                conn, {"id": "job-id", "location_id": LOCATION_ID}
            ),
            "fetchone",
            id="plot-bbox-fetch",
        ),
    ],
)
def test_read_cursor_closes_when_query_or_fetch_fails(operation, fail_at):
    connection = _Connection(fail_at)

    with pytest.raises(RuntimeError, match="synthetic"):
        operation(connection)

    assert connection.cursor_instance.closed
