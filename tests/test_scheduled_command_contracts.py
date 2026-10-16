"""Scheduler command contracts fail closed before activation or dispatch."""

from argparse import Namespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.core.jobs import JOBS, run_job
from services.scheduler.graph import audit_graph
from services.scheduler.job_plan import build_job_plan
from services.security.execution_allowlist import ALLOWED_SCHEDULED_MODULES
from services.security.scheduled_command_contracts import (
    _OPTIONS,
    ScheduledCommandRejected,
    validate_scheduled_command,
)


def test_every_scheduled_module_has_a_command_contract():
    assert frozenset(_OPTIONS) == ALLOWED_SCHEDULED_MODULES


@pytest.mark.parametrize(
    ("module", "arguments"),
    [
        ("services.ingestion.weather", ["--location-id", str(uuid4())]),
        ("services.ingestion.market_data", ["--source", "world_bank"]),
        ("services.ingestion.market_data", ["--month", "2", "--year", "2026"]),
        ("services.ingestion.eas_indexer", ["--chain", "celo"]),
        ("services.ingestion.rpc_indexer", ["--wallet", "0x" + "a" * 40]),
        ("services.ingestion.gnosis_indexer", ["--from-block", "1", "--to-block", "2"]),
        ("services.ingestion.anomaly_detector", []),
        ("services.ingestion.anomaly_detector", ["--baseline-check"]),
        ("services.metrics", ["--compute", "--all-locations"]),
        ("services.metrics", ["--reconcile-noi-snapshots"]),
        ("services.ingestion.data_freshness", ["--check"]),
        ("services.export.dataset_refresh", ["--all"]),
        (
            "services.ingestion.climate_data",
            ["--all", "--location-id", str(uuid4())],
        ),
        ("services.events", ["--process"]),
        ("services.events", ["--notification-process", "--batch-size", "50"]),
        ("services.ingestion.remote_sensing_fetcher", ["--run-jobs"]),
        ("services.ingestion.remote_sensing_fetcher", ["--run-jobs", "--limit", "10"]),
        ("services.ingestion.clickhouse_outbox", ["--run-once"]),
        ("services.ingestion.clickhouse_outbox", ["--run-once", "--limit", "100"]),
        (
            "services.analytics.carbon_credit_adjustment_check",
            ["--location-id", str(uuid4())],
        ),
    ],
)
def test_supported_operations_accept_valid_argv(module, arguments):
    assert validate_scheduled_command(module, arguments) == tuple(arguments)


@pytest.mark.parametrize(
    ("module", "arguments"),
    [
        ("os", ["--help"]),
        ("services.ingestion.sensor_ingester", []),
        ("services.ingestion.sensor_ingester", ["--file", "/tmp/readings.csv"]),
        ("services.analytics.carbon_credit_adjustment_check", []),
        ("services.ingestion.weather", []),
        ("services.ingestion.climate_data", ["--all"]),
        ("services.ingestion.climate_data", ["--all", "--location-id", "invalid"]),
        ("services.ingestion.climate_data", ["--all", "--worldclim", "--location-id", str(uuid4())]),
        ("services.ingestion.market_data", ["--month", "1"]),
        ("services.ingestion.market_data", ["--source", "unknown"]),
        ("services.ingestion.rpc_indexer", ["--wallet", "not-an-address"]),
        ("services.ingestion.gnosis_indexer", ["--from-block", "10", "--to-block", "9"]),
        ("services.metrics", ["--verify-value", str(uuid4()), "--verified-by", str(uuid4())]),
        ("services.metrics", ["--compute", "--all-locations", "--location-id", str(uuid4())]),
        ("services.metrics", ["--compute", "--metric", "value_flowed"]),
        ("services.events", ["--cleanup"]),
        ("services.events", ["--worker"]),
        ("services.events", ["--dispose-dead-letter", "--event-id", str(uuid4())]),
        ("services.analytics.carbon_credits", ["--check-adjustments"]),
        ("services.ingestion.remote_sensing_fetcher", []),
        ("services.ingestion.remote_sensing_fetcher", ["--list-jobs"]),
        ("services.ingestion.remote_sensing_fetcher", ["--run-jobs", "--limit", "0"]),
        ("services.ingestion.remote_sensing_fetcher", ["--run-jobs", "--limit", "11"]),
        ("services.ingestion.remote_sensing_fetcher", ["--run-jobs", "--location-id", str(uuid4())]),
        ("services.ingestion.clickhouse_outbox", []),
        ("services.ingestion.clickhouse_outbox", ["--reconcile"]),
        ("services.ingestion.clickhouse_outbox", ["--list-dead-letter"]),
        ("services.ingestion.clickhouse_outbox", ["--replay-dead-letter", str(uuid4())]),
        ("services.ingestion.clickhouse_outbox", ["--dispose-dead-letter", str(uuid4())]),
        ("services.analytics.carbon_credit_adjustment_check", ["--adjust", "--location-id", str(uuid4())]),
        (
            "services.analytics.carbon_credits",
            ["--confirm-retirement", "--retirement-id", str(uuid4()), "--reviewer-id", str(uuid4())],
        ),
        ("services.export.dataset_refresh", []),
        ("services.export.dataset_refresh", ["--all", "--dataset-id", str(uuid4())]),
    ],
)
def test_unsupported_or_incomplete_operations_are_rejected(module, arguments):
    with pytest.raises(ScheduledCommandRejected):
        validate_scheduled_command(module, arguments)


def test_credit_adjustment_job_uses_dedicated_read_only_entrypoint():
    job = JOBS["credit_adjustment"]

    assert job.module == "services.analytics.carbon_credit_adjustment_check"
    assert job.scheduler_allowed
    assert job.required_inputs == ("location_id",)
    with pytest.raises(ScheduledCommandRejected, match="requires one explicit location"):
        validate_scheduled_command(job.module, list(job.arguments))
    location_id = str(uuid4())
    assert validate_scheduled_command(job.module, ["--location-id", location_id]) == (
        "--location-id",
        location_id,
    )


def test_credit_adjustment_schedule_plan_requires_one_location():
    with pytest.raises(ValueError, match="schedule planning requires one location"):
        build_job_plan("credit_adjustment", "daily")

    location_id = str(uuid4())
    plan = build_job_plan("credit_adjustment", "daily", location_id=location_id)
    task = plan["scheduled_task"]
    assert task["command_args"] == ["--location-id", location_id]
    assert not task["is_enabled"]


def test_interactive_carbon_credit_cli_is_not_scheduler_allowlisted():
    from services.security.execution_allowlist import validate_scheduled_module

    with pytest.raises(ValueError, match="not allowlisted"):
        validate_scheduled_module("services.analytics.carbon_credits")


def test_projection_job_is_scheduler_allowed_but_restricted_to_one_delivery_batch():
    job = JOBS["projections"]

    assert job.module == "services.ingestion.clickhouse_outbox"
    assert job.scheduler_allowed
    assert validate_scheduled_command(job.module, list(job.arguments)) == ("--run-once", "--limit", "100")


def test_weather_job_requires_one_explicit_location_before_dispatch():
    from services.scheduler.job_plan import build_job_plan

    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ValueError, match="Weather refresh requires a location"):
            run_job("weather")
    run.assert_not_called()

    with pytest.raises(ValueError, match="Weather schedule planning requires one location"):
        build_job_plan("weather", "daily")


def test_remote_sensing_job_defaults_to_one_due_job_batch():
    job = JOBS["remote_sensing"]

    assert job.module == "services.ingestion.remote_sensing_fetcher"
    assert job.scheduler_allowed
    assert validate_scheduled_command(job.module, list(job.arguments)) == ("--run-jobs", "--limit", "1")


def test_sensor_job_rejects_missing_source_before_launching_the_noop_cli():
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ScheduledCommandRejected, match="no recurring source contract"):
            run_job("sensors")

    run.assert_not_called()


@pytest.mark.parametrize("arguments", [None, "--process", {"--process": True}, ["--process", 3]])
def test_command_args_must_be_a_json_string_array(arguments):
    with pytest.raises(ScheduledCommandRejected):
        validate_scheduled_command("services.events", arguments)


def test_invalid_command_is_visible_in_schedule_graph_preflight():
    task_id = str(uuid4())
    report = audit_graph(
        [
            {
                "id": task_id,
                "module_path": "services.ingestion.climate_data",
                "command_args": ["--all"],
                "cron_expression": "0 3 * * 0",
                "depends_on": [],
                "dependency_mode": "last_completed",
                "is_enabled": False,
            }
        ]
    )

    assert not report["valid"]
    assert any(error["code"] == "command_contract" for error in report["errors"])


def test_run_now_rejects_invalid_stored_arguments_before_subprocess():
    from services.scheduler.cli import cmd_run_now

    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = ("services.ingestion.climate_data", ["--all"], 30)
    connection = MagicMock()
    connection.cursor.return_value = cursor

    with (
        patch("services.common.database.get_db", return_value=connection),
        patch("subprocess.run") as run,
        pytest.raises(ScheduledCommandRejected),
    ):
        cmd_run_now(Namespace(task_name="invalid-climate"))

    run.assert_not_called()
    connection.close.assert_called_once()


def test_reviewable_job_plans_require_tenant_inputs_and_sensor_source():
    weather = build_job_plan("weather", "hourly", location_id=str(uuid4()))
    assert weather["scheduled_task"]["command_args"][0] == "--location-id"

    climate = build_job_plan("climate", "weekly", location_id=str(uuid4()))
    assert "--location-id" in climate["scheduled_task"]["command_args"]

    snapshots = build_job_plan("noi_snapshots", "daily")
    assert snapshots["scheduled_task"]["command_args"] == ["--reconcile-noi-snapshots"]

    with pytest.raises(ValueError, match="input contract"):
        build_job_plan("sensors", "hourly")


def test_curated_job_runner_rejects_source_less_sensor_job_before_spawn():
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ScheduledCommandRejected, match="no recurring source contract"):
            run_job("sensors")

    run.assert_not_called()
