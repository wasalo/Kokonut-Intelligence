"""Bounded source tests for the remote-sensing scheduled operation."""

from unittest.mock import patch

import pytest

from services.ingestion.remote_sensing_fetcher import MAX_RUN_BATCH_SIZE, run_due_jobs


def test_due_jobs_are_claimed_one_at_a_time_and_processed_before_next_claim():
    jobs = [{"id": "first", "provider": "gee"}, {"id": "second", "provider": "copernicus"}]
    sequence = []

    def claim(_conn):
        sequence.append("claim")
        return [jobs.pop(0)] if jobs else []

    def fetch(_conn, job):
        sequence.append(f"fetch:{job['id']}")
        return {"job_id": job["id"], "status": "success"}

    with (
        patch("services.ingestion.remote_sensing_fetcher._claim_due_jobs", side_effect=claim),
        patch("services.ingestion.remote_sensing_fetcher.fetch_job", side_effect=fetch),
    ):
        result = run_due_jobs(object(), limit=2)

    assert sequence == ["claim", "fetch:first", "claim", "fetch:second"]
    assert result["executed"] == 2
    assert result["success"] == 2
    assert result["failed"] == 0


def test_due_jobs_default_to_one_claim_and_stop_when_no_job_is_due():
    conn = object()
    with patch("services.ingestion.remote_sensing_fetcher._claim_due_jobs", return_value=[]) as claim:
        result = run_due_jobs(conn)

    claim.assert_called_once_with(conn)
    assert result == {"status": "no_jobs_due", "executed": 0}


def test_default_batch_does_not_claim_a_second_due_job():
    conn = object()
    jobs = [{"id": "first", "provider": "gee"}, {"id": "second", "provider": "copernicus"}]
    with (
        patch(
            "services.ingestion.remote_sensing_fetcher._claim_due_jobs",
            side_effect=lambda _conn: [jobs.pop(0)] if jobs else [],
        ) as claim,
        patch(
            "services.ingestion.remote_sensing_fetcher.fetch_job",
            return_value={"status": "success"},
        ) as fetch,
    ):
        result = run_due_jobs(conn)

    claim.assert_called_once_with(conn)
    fetch.assert_called_once_with(conn, {"id": "first", "provider": "gee"})
    assert result["executed"] == 1
    assert len(jobs) == 1


@pytest.mark.parametrize("limit", [0, MAX_RUN_BATCH_SIZE + 1, True, 1.5, "1", None])
def test_due_job_batch_limit_rejects_invalid_values_before_claim(limit):
    with patch("services.ingestion.remote_sensing_fetcher._claim_due_jobs") as claim:
        with pytest.raises(ValueError, match="limit must be an integer"):
            run_due_jobs(object(), limit=limit)

    claim.assert_not_called()
