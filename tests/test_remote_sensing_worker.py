"""Source contracts for the isolated remote-sensing worker."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.ingestion.remote_sensing_worker import (
    _attempt_provider_chain,
    _claim,
    _finish,
    _normalize_records,
    run_due_jobs,
)

LOCATION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_LOCATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def test_provider_chain_retries_with_the_configured_fallback():
    job = {"provider": "gee", "metadata": {"fallback_provider": "copernicus"}}
    first = ({"status": "error", "retryable": True, "observations": 0, "message": "temporary failure"}, [])
    record = {
        "location_id": LOCATION_ID,
        "source_system": "copernicus_api",
        "source_id": "scene-1",
        "metadata": {},
    }
    second = ({"status": "success", "observations": 1}, [record])
    with patch("services.ingestion.remote_sensing_worker._fetch_records", side_effect=[first, second]) as fetch:
        attempts, records, final = _attempt_provider_chain(job)

    assert fetch.call_count == 2
    assert [attempt["provider"] for attempt in attempts] == ["gee", "copernicus"]
    assert attempts[0]["fallback_used"] is False
    assert attempts[1]["fallback_used"] is True
    assert records == [record]
    assert final["provider"] == "copernicus"


def test_provider_chain_stops_after_success_without_fallback():
    job = {"provider": "gee", "metadata": {"fallback_enabled": False}}
    with patch(
        "services.ingestion.remote_sensing_worker._fetch_records",
        return_value=({"status": "success", "observations": 0}, []),
    ) as fetch:
        attempts, records, final = _attempt_provider_chain(job)

    fetch.assert_called_once_with(job)
    assert len(attempts) == 1
    assert records == []
    assert final["outcome"] == "no_data"


def test_provider_chain_redacts_exception_details_from_retry_attempts():
    job = {"provider": "gee", "metadata": {"fallback_enabled": False}}
    secret = "provider-secret-token"
    with patch(
        "services.ingestion.remote_sensing_worker._fetch_records",
        side_effect=TimeoutError(f"request failed at https://catalog.example/{secret}"),
    ):
        attempts, records, final = _attempt_provider_chain(job)

    assert final["outcome"] == "retryable"
    assert attempts[0]["message"] == "gee provider failed (TimeoutError)"
    assert secret not in str(attempts)
    assert records == []


def test_provider_chain_redacts_provider_response_text_from_persisted_attempts():
    job = {"provider": "gee", "metadata": {"fallback_enabled": False}}
    secret = "provider-secret-token"
    with patch(
        "services.ingestion.remote_sensing_worker._fetch_records",
        return_value=(
            {
                "status": "error",
                "retryable": False,
                "observations": 0,
                "message": f"authorization failed for https://catalog.example/{secret}",
            },
            [],
        ),
    ):
        attempts, records, final = _attempt_provider_chain(job)

    assert final["outcome"] == "non_retryable"
    assert attempts[0]["message"] == "gee provider rejected the request"
    assert secret not in str(attempts)
    assert records == []


def test_gee_initialization_log_redacts_provider_exception(monkeypatch):
    from services.ingestion import gee_remote_sensing

    secret = "service-account-secret"
    logger = MagicMock()
    monkeypatch.setattr(gee_remote_sensing, "logger", logger)

    def fail_initialization(*_args):
        raise OSError(f"credential request failed https://gee.example/{secret}")

    monkeypatch.setitem(sys.modules, "ee", SimpleNamespace(ServiceAccountCredentials=fail_initialization))
    monkeypatch.setenv("KOKONUT_REMOTE_SENSING_GEE_SERVICE_ACCOUNT_KEY", "/run/secrets/gee.json")

    assert gee_remote_sensing._get_gee_client() is None
    assert logger.error.call_args.args == ("GEE service account init failed (%s)", "OSError")
    assert secret not in str(logger.error.call_args)


def test_copernicus_catalog_error_is_redacted_at_adapter_boundary(monkeypatch):
    from services.ingestion import copernicus_remote_sensing

    secret = "copernicus-secret-token"
    logger = MagicMock()
    monkeypatch.setattr(copernicus_remote_sensing, "logger", logger)
    monkeypatch.setattr(copernicus_remote_sensing, "_get_token", lambda: "synthetic-token")
    monkeypatch.setattr(copernicus_remote_sensing, "_resolve_bbox", lambda _job: {
        "west": -70,
        "south": 18,
        "east": -69,
        "north": 19,
    })
    monkeypatch.setattr(
        copernicus_remote_sensing.http,
        "get",
        MagicMock(side_effect=OSError(f"catalog request failed https://catalog.example/{secret}")),
    )

    result, records = copernicus_remote_sensing.fetch_copernicus_records(
        {"location_id": LOCATION_ID, "cadence_days": 7}
    )

    assert result["message"] == "Copernicus catalog query failed (OSError)"
    assert result["retryable"] is False
    assert records == []
    assert secret not in str(result)
    assert secret not in str(logger.error.call_args)


@pytest.mark.parametrize(
    "module_name",
    [
        "services.ingestion.gee_remote_sensing",
        "services.ingestion.copernicus_remote_sensing",
    ],
)
def test_connection_free_clickhouse_warning_redacts_exception(monkeypatch, module_name):
    from importlib import import_module

    adapter = import_module(module_name)
    secret = "clickhouse-secret-token"
    logger = MagicMock()
    monkeypatch.setattr(adapter, "logger", logger)
    monkeypatch.setattr(
        adapter,
        "post_clickhouse_rows",
        MagicMock(side_effect=OSError(f"insert failed https://clickhouse.example/{secret}")),
    )

    adapter._insert_ch({
        "observation_date": "2026-10-17",
        "id": "observation-1",
        "location_id": LOCATION_ID,
    })

    assert logger.warning.call_args.args == ("ClickHouse insert failed (%s)", "OSError")
    assert secret not in str(logger.warning.call_args)


def test_records_are_rejected_when_the_provider_changes_location():
    with pytest.raises(ValueError, match="outside the signed location"):
        _normalize_records([{"location_id": OTHER_LOCATION_ID}], LOCATION_ID)


def test_claim_sets_signed_scope_before_calling_the_bounded_function():
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchone.return_value = ({"id": "job-1"},)
    with (
        patch("services.ingestion.remote_sensing_worker.get_worker_db", return_value=connection),
        patch("services.ingestion.remote_sensing_worker.set_worker_tenant_context") as set_scope,
    ):
        job = _claim(LOCATION_ID, "x" * 32)

    assert job == {"id": "job-1"}
    set_scope.assert_called_once_with(
        connection,
        credential="x" * 32,
        location_id=LOCATION_ID,
        resource="remote_sensing",
        action="run",
    )
    connection.cursor.return_value.__enter__.return_value.execute.assert_called_once_with(
        "SELECT kokonut_security.claim_remote_sensing_job(%s::uuid)",
        (LOCATION_ID,),
    )
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_finish_calls_one_bounded_atomic_function_under_the_same_scope():
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (1,)
    job = {"id": "job-1", "lease_owner": "lease-1"}
    attempts = [{"provider": "gee", "outcome": "success"}]
    records = [{"location_id": LOCATION_ID, "metadata": {}}]
    with (
        patch("services.ingestion.remote_sensing_worker.get_worker_db", return_value=connection),
        patch("services.ingestion.remote_sensing_worker.set_worker_tenant_context") as set_scope,
    ):
        written = _finish(job, LOCATION_ID, "x" * 32, attempts, records)

    assert written == 1
    set_scope.assert_called_once_with(
        connection,
        credential="x" * 32,
        location_id=LOCATION_ID,
        resource="remote_sensing",
        action="run",
    )
    sql, params = connection.cursor.return_value.__enter__.return_value.execute.call_args.args
    assert "kokonut_security.finish_remote_sensing_job" in sql
    assert params[:3] == ("job-1", LOCATION_ID, "lease-1")
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_run_due_jobs_requires_scope_and_bounds_claim_count_before_credentials():
    with patch(
        "services.ingestion.remote_sensing_worker.get_worker_credential",
        side_effect=AssertionError("credential should not be read"),
    ) as credential:
        with pytest.raises(ValueError, match="explicit location UUID"):
            run_due_jobs("invalid")
        with pytest.raises(ValueError, match="between 1 and"):
            run_due_jobs(LOCATION_ID, limit=11)
    credential.assert_not_called()


def test_run_due_jobs_claims_and_completes_each_job_inside_the_location():
    job = {
        "id": "job-1",
        "location_id": LOCATION_ID,
        "lease_owner": "lease-1",
        "provider": "gee",
        "bbox": {"west": -70, "south": 18, "east": -69, "north": 19},
    }
    attempts = [{"provider": "gee", "outcome": "success", "observations": 0}]
    with (
        patch("services.ingestion.remote_sensing_worker.get_worker_credential", return_value="x" * 32),
        patch("services.ingestion.remote_sensing_worker._claim", side_effect=[job, None]) as claim,
        patch(
            "services.ingestion.remote_sensing_worker._attempt_provider_chain",
            return_value=(attempts, [], attempts[0]),
        ),
        patch("services.ingestion.remote_sensing_worker._finish", return_value=0) as finish,
    ):
        result = run_due_jobs(LOCATION_ID, limit=2)

    assert claim.call_args_list[0].args == (LOCATION_ID, "x" * 32)
    finish.assert_called_once_with(job, LOCATION_ID, "x" * 32, attempts, [])
    assert result["executed"] == 1
    assert result["success"] == 1
