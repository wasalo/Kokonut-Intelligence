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
        ("services.ingestion.weather", []),
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
        ("services.analytics.carbon_credits", ["--check-adjustments"]),
        (
            "services.analytics.carbon_credits",
            ["--check-adjustments", "--location-id", str(uuid4())],
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
        ("services.analytics.carbon_credits", []),
        ("services.analytics.carbon_credits", ["--adjust", "--location-id", str(uuid4())]),
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


def test_credit_adjustment_job_is_scheduler_allowed_but_restricted_to_check():
    job = JOBS["credit_adjustment"]

    assert job.module == "services.analytics.carbon_credits"
    assert job.scheduler_allowed
    assert validate_scheduled_command(job.module, list(job.arguments)) == ("--check-adjustments",)


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


def test_reviewable_job_plans_are_validated_and_sensor_source_remains_required():
    weather = build_job_plan("weather", "hourly")
    assert weather["scheduled_task"]["command_args"] == []

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
