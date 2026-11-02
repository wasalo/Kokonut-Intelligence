"""Bounded source tests for the remote-sensing scheduled operation."""

from unittest.mock import MagicMock, patch

import pytest

from services.ingestion.remote_sensing_fetcher import (
    MAX_RUN_BATCH_SIZE,
    _claim_due_jobs,
    run_due_jobs,
)

LOCATION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def test_legacy_due_job_claim_fails_before_database_access():
    conn = MagicMock()

    with pytest.raises(RuntimeError, match="legacy remote-sensing due-job claims are disabled"):
        _claim_due_jobs(conn, LOCATION_ID)

    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()


def test_unscoped_legacy_due_job_claim_fails_before_database_access():
    conn = MagicMock()

    with pytest.raises(ValueError, match="explicit location UUID"):
        _claim_due_jobs(conn)

    conn.cursor.assert_not_called()


@pytest.mark.parametrize("limit", [0, MAX_RUN_BATCH_SIZE + 1, True, 1.5, "1", None])
def test_retired_due_job_runner_rejects_invalid_batch_before_access(limit):
    conn = MagicMock()
    with pytest.raises(ValueError, match="limit must be an integer"):
        run_due_jobs(conn, limit=limit, location_id=LOCATION_ID)

    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()


def test_retired_due_job_runner_fails_before_database_or_provider_access():
    conn = MagicMock()
    with (
        patch("services.ingestion.remote_sensing_fetcher.fetch_job") as fetch_job,
        pytest.raises(RuntimeError, match="legacy remote-sensing due-job execution is disabled"),
    ):
        run_due_jobs(conn, location_id=LOCATION_ID)

    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()
    fetch_job.assert_not_called()


def test_retired_due_job_runner_requires_scope_without_database_access():
    conn = MagicMock()

    with pytest.raises(ValueError, match="explicit location UUID"):
        run_due_jobs(conn)

    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()


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
        ["--job-id", "12345678-1234-5678-1234-567812345679"],
        ["--run-jobs", "--list-jobs", "--location-id", LOCATION_ID],
        ["--run-jobs", "--location-id", "invalid"],
        ["--job-id", "not-a-uuid", "--location-id", LOCATION_ID],
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

    job_id = "12345678-1234-5678-1234-567812345679"
    _query_job(conn, job_id, LOCATION_ID)

    sql, parameters = cursor.execute.call_args.args
    assert "id = %s AND location_id = %s" in sql
    assert parameters == (job_id, LOCATION_ID)


def test_job_listing_binds_location_scope():
    from services.ingestion.remote_sensing_fetcher import list_jobs

    list_conn = MagicMock()
    list_cursor = list_conn.cursor.return_value
    list_cursor.fetchall.return_value = []
    list_jobs(list_conn, LOCATION_ID)
    list_sql, list_parameters = list_cursor.execute.call_args.args
    assert "location_id = %s" in list_sql
    assert list_parameters == (LOCATION_ID,)

def test_fetch_job_rolls_back_and_propagates_outbox_failure(monkeypatch):
    from services.ingestion import remote_sensing_fetcher
    from services.ingestion.clickhouse_outbox import OutboxEnqueueError

    conn = MagicMock()
    job = {"id": "job-1", "provider": "gee", "location_id": LOCATION_ID}
    secret = "remote-sensing-outbox-secret"
    monkeypatch.setattr(remote_sensing_fetcher, "_resolve_bbox_from_job", lambda *_args: None)
    monkeypatch.setattr(
        "services.ingestion.gee_remote_sensing.fetch_gee",
        lambda *_args: (_ for _ in ()).throw(OutboxEnqueueError(f"outbox failed: {secret}")),
        raising=False,
    )
    with patch.object(remote_sensing_fetcher, "_record_provider_attempt") as record_attempt:
        with pytest.raises(OutboxEnqueueError, match="ClickHouse outbox enqueue failed") as error:
            remote_sensing_fetcher.fetch_job(conn, job, location_id=LOCATION_ID)

    conn.rollback.assert_called_once_with()
    conn.commit.assert_not_called()
    record_attempt.assert_not_called()
    assert secret not in str(error.value)


def test_fetch_job_redacts_provider_response_before_audit_and_status(monkeypatch):
    from services.ingestion import remote_sensing_fetcher

    conn = MagicMock()
    job = {
        "id": "job-1",
        "provider": "gee",
        "location_id": LOCATION_ID,
        "metadata": {"fallback_enabled": False},
    }
    secret = "provider-secret-token"
    monkeypatch.setattr(remote_sensing_fetcher, "_resolve_bbox_from_job", lambda *_args: None)
    monkeypatch.setattr(
        "services.ingestion.gee_remote_sensing.fetch_gee",
        lambda *_args: {
            "status": "error",
            "retryable": True,
            "observations": 0,
            "message": f"request failed at https://catalog.example/{secret}",
        },
        raising=False,
    )
    with (
        patch.object(remote_sensing_fetcher, "_record_provider_attempt") as record_attempt,
        patch.object(remote_sensing_fetcher, "_update_job_status") as update_status,
    ):
        result = remote_sensing_fetcher.fetch_job(conn, job, location_id=LOCATION_ID)

    attempt = record_attempt.call_args.args[2]
    assert attempt["message"] == "gee provider failed (retryable)"
    assert update_status.call_args.kwargs["error_message"] == "gee provider failed (retryable)"
    assert result["message"] == "gee provider failed (retryable)"
    assert secret not in str((attempt, update_status.call_args, result))
