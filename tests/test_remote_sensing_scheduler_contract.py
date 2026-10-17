"""Bounded source tests for the remote-sensing scheduled operation."""

from unittest.mock import MagicMock, patch

import pytest

from services.ingestion.remote_sensing_fetcher import (
    MAX_RUN_BATCH_SIZE,
    _claim_due_jobs,
    run_due_jobs,
)

LOCATION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def test_due_jobs_are_claimed_one_at_a_time_and_processed_before_next_claim():
    jobs = [
        {"id": "first", "provider": "gee", "location_id": LOCATION_ID},
        {"id": "second", "provider": "copernicus", "location_id": LOCATION_ID},
    ]
    sequence = []

    def claim(_conn, *, location_id):
        assert location_id == LOCATION_ID
        sequence.append("claim")
        return [jobs.pop(0)] if jobs else []

    def fetch(_conn, job, *, location_id):
        assert location_id == LOCATION_ID
        sequence.append(f"fetch:{job['id']}")
        return {"job_id": job["id"], "status": "success"}

    with (
        patch("services.ingestion.remote_sensing_fetcher._claim_due_jobs", side_effect=claim),
        patch("services.ingestion.remote_sensing_fetcher.fetch_job", side_effect=fetch),
    ):
        result = run_due_jobs(object(), limit=2, location_id=LOCATION_ID)

    assert sequence == ["claim", "fetch:first", "claim", "fetch:second"]
    assert result["executed"] == 2
    assert result["success"] == 2
    assert result["failed"] == 0


def test_due_jobs_default_to_one_scoped_claim_and_stop_when_no_job_is_due():
    conn = object()
    with patch("services.ingestion.remote_sensing_fetcher._claim_due_jobs", return_value=[]) as claim:
        result = run_due_jobs(conn, location_id=LOCATION_ID)

        claim.assert_called_once_with(conn, location_id=LOCATION_ID)
    assert result == {"status": "no_jobs_due", "executed": 0}


def test_default_batch_does_not_claim_a_second_due_job():
    conn = object()
    jobs = [{"id": "first", "provider": "gee"}, {"id": "second", "provider": "copernicus"}]
    with (
        patch(
            "services.ingestion.remote_sensing_fetcher._claim_due_jobs",
            side_effect=lambda _conn, *, location_id: [jobs.pop(0)] if jobs else [],
        ) as claim,
        patch(
            "services.ingestion.remote_sensing_fetcher.fetch_job",
            return_value={"status": "success"},
        ) as fetch,
    ):
        jobs[0]["location_id"] = LOCATION_ID
        jobs[1]["location_id"] = LOCATION_ID
        result = run_due_jobs(conn, location_id=LOCATION_ID)

    claim.assert_called_once_with(conn, location_id=LOCATION_ID)
    fetch.assert_called_once_with(
        conn,
        {"id": "first", "provider": "gee", "location_id": LOCATION_ID},
        location_id=LOCATION_ID,
    )
    assert result["executed"] == 1
    assert len(jobs) == 1


@pytest.mark.parametrize("limit", [0, MAX_RUN_BATCH_SIZE + 1, True, 1.5, "1", None])
def test_due_job_batch_limit_rejects_invalid_values_before_claim(limit):
    with patch("services.ingestion.remote_sensing_fetcher._claim_due_jobs") as claim:
        with pytest.raises(ValueError, match="limit must be an integer"):
            run_due_jobs(object(), limit=limit, location_id=LOCATION_ID)

    claim.assert_not_called()


def test_due_job_claim_passes_exact_location_scope_to_sql():
    from uuid import uuid4

    location_id = str(uuid4())
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchall.return_value = []

    assert _claim_due_jobs(conn, location_id=location_id) == []

    sql, params = cursor.execute.call_args.args
    assert "location_id = %s::uuid" in sql
    assert params[0] == location_id
    assert params[1].startswith("remote-sensing-")


def test_direct_unscoped_claim_is_rejected_before_cursor_access():
    conn = MagicMock()

    with pytest.raises(ValueError, match="explicit location UUID"):
        _claim_due_jobs(conn)

    conn.cursor.assert_not_called()


def test_run_due_jobs_forwards_location_scope_to_each_atomic_claim():
    conn = object()
    location_id = "6c02f16f-8853-4e77-bc2c-886b34b94412"
    with patch("services.ingestion.remote_sensing_fetcher._claim_due_jobs", return_value=[]) as claim:
        result = run_due_jobs(conn, location_id=location_id)

    claim.assert_called_once_with(conn, location_id=location_id)
    assert result == {"status": "no_jobs_due", "executed": 0}


def test_run_due_jobs_requires_location_before_claiming():
    with patch("services.ingestion.remote_sensing_fetcher._claim_due_jobs") as claim:
        with pytest.raises(ValueError, match="explicit location UUID"):
            run_due_jobs(object())

    claim.assert_not_called()


def test_fetch_job_rejects_a_mismatched_location_before_bbox_or_provider_work():
    from services.ingestion.remote_sensing_fetcher import fetch_job

    with patch("services.ingestion.remote_sensing_fetcher._resolve_bbox_from_job") as bbox:
        with pytest.raises(ValueError, match="outside the requested location"):
            fetch_job(
                object(),
                {"id": "job-1", "location_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"},
                location_id=LOCATION_ID,
            )

    bbox.assert_not_called()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--run-jobs"],
        ["--list-jobs"],
        ["--job-id", "job-1"],
        ["--run-jobs", "--list-jobs", "--location-id", LOCATION_ID],
        ["--run-jobs", "--location-id", "invalid"],
        ["--job-id", "", "--location-id", LOCATION_ID],
        ["--run-jobs", "--limit", "0", "--location-id", LOCATION_ID],
    ],
)
def test_cli_rejects_unscoped_or_conflicting_commands_before_database(arguments, monkeypatch):
    from services.ingestion import remote_sensing_fetcher

    monkeypatch.setattr(
        remote_sensing_fetcher,
        "get_db",
        lambda: pytest.fail("invalid remote-sensing command must fail before database access"),
    )

    with pytest.raises(SystemExit) as error:
        remote_sensing_fetcher.main(arguments)

    assert error.value.code == 2


def test_cli_help_without_an_operation_is_offline(monkeypatch, capsys):
    from services.ingestion import remote_sensing_fetcher

    monkeypatch.setattr(
        remote_sensing_fetcher,
        "get_db",
        lambda: pytest.fail("remote-sensing help must not open the database"),
    )

    remote_sensing_fetcher.main([])

    assert "usage:" in capsys.readouterr().out


def test_cli_passes_location_to_job_listing(monkeypatch):
    from services.ingestion import remote_sensing_fetcher

    conn = MagicMock()
    monkeypatch.setattr(remote_sensing_fetcher, "get_db", lambda: conn)
    list_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(remote_sensing_fetcher, "list_jobs", list_jobs)
    monkeypatch.setattr(remote_sensing_fetcher, "print_json", lambda value: None)

    remote_sensing_fetcher.main(["--list-jobs", "--location-id", LOCATION_ID])

    list_jobs.assert_called_once_with(conn, LOCATION_ID)
    conn.close.assert_called_once()


def test_job_lookup_binds_location_scope_to_sql():
    from services.ingestion.remote_sensing_fetcher import _query_job

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = None

    _query_job(conn, "job-1", LOCATION_ID)

    sql, parameters = cursor.execute.call_args.args
    assert "id = %s AND location_id = %s" in sql
    assert parameters == ("job-1", LOCATION_ID)


def test_job_listing_and_active_job_query_bind_location_scope():
    from services.ingestion.remote_sensing_fetcher import _query_active_jobs, list_jobs

    for operation in (list_jobs, _query_active_jobs):
        conn = MagicMock()
        cursor = conn.cursor.return_value
        cursor.fetchall.return_value = []

        operation(conn, LOCATION_ID)

        sql, parameters = cursor.execute.call_args.args
        assert "location_id = %s" in sql
        assert parameters == (LOCATION_ID,)


def test_fetch_job_rolls_back_and_propagates_outbox_failure(monkeypatch):
    from services.ingestion import remote_sensing_fetcher
    from services.ingestion.clickhouse_outbox import OutboxEnqueueError

    conn = MagicMock()
    job = {"id": "job-1", "provider": "gee", "location_id": LOCATION_ID}
    monkeypatch.setattr(remote_sensing_fetcher, "_resolve_bbox_from_job", lambda *_args: None)
    monkeypatch.setattr(
        "services.ingestion.gee_remote_sensing.fetch_gee",
        lambda *_args: (_ for _ in ()).throw(OutboxEnqueueError("outbox unavailable")),
        raising=False,
    )
    with patch.object(remote_sensing_fetcher, "_record_provider_attempt") as record_attempt:
        with pytest.raises(OutboxEnqueueError, match="outbox unavailable"):
            remote_sensing_fetcher.fetch_job(conn, job, location_id=LOCATION_ID)

    conn.rollback.assert_called_once_with()
    conn.commit.assert_not_called()
    record_attempt.assert_not_called()
