"""Scheduler command contracts fail closed before activation or dispatch."""

import sys
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
        ("services.ingestion.weather_worker", ["--location-id", str(uuid4())]),
        ("services.ingestion.weather_forecast", ["--location-id", str(uuid4())]),
        ("services.ingestion.weather_forecast_worker", ["--location-id", str(uuid4())]),
        ("services.ingestion.market_data", ["--source", "world_bank"]),
        ("services.ingestion.market_data", ["--month", "2", "--year", "2026"]),
        ("services.ingestion.market_data_worker", []),
        ("services.ingestion.market_data_worker", ["--commodity", "coffee"]),
        ("services.ingestion.market_data_worker", ["--month", "2", "--year", "2026"]),
        ("services.ingestion.eas_indexer", ["--chain", "celo"]),
        ("services.ingestion.eas_worker", ["--chain", "celo"]),
        ("services.ingestion.eas_indexer", ["--chain", "optimism"]),
        ("services.ingestion.eas_indexer", ["--chain", "base"]),
        ("services.ingestion.rpc_indexer", ["--chain", "celo"]),
        ("services.ingestion.rpc_indexer", ["--chain", "ethereum", "--wallet", "0x" + "a" * 40]),
        ("services.ingestion.rpc_indexer", ["--chain", "celo-alfajores"]),
        ("services.ingestion.gnosis_indexer", ["--from-block", "1", "--to-block", "2"]),
        (
            "services.ingestion.sensor_ingester",
            ["--location-id", str(uuid4()), "--driver-instance-id", str(uuid4())],
        ),
        (
            "services.ingestion.sensor_worker",
            ["--location-id", str(uuid4()), "--driver-instance-id", str(uuid4())],
        ),
        ("services.ingestion.anomaly_detector", ["--location-id", str(uuid4())]),
        ("services.ingestion.anomaly_detector", ["--baseline-check", "--location-id", str(uuid4())]),
        ("services.metrics", ["--compute", "--all", "--location-id", str(uuid4())]),
        ("services.metrics", ["--compute", "--metric", "value_flowed", "--location-id", str(uuid4())]),
        ("services.metrics.noi_snapshot_worker", ["--location-id", str(uuid4())]),
        ("services.ingestion.data_freshness", ["--check"]),
        ("services.export.dataset_refresh", ["--all"]),
        (
            "services.ingestion.climate_data",
            ["--all", "--location-id", str(uuid4())],
        ),
        ("services.events", ["--process"]),
        ("services.events", ["--notification-process", "--batch-size", "50"]),
        ("services.ingestion.remote_sensing_fetcher", ["--run-jobs", "--location-id", str(uuid4())]),
        ("services.ingestion.remote_sensing_fetcher", ["--run-jobs", "--limit", "10", "--location-id", str(uuid4())]),
        ("services.ingestion.remote_sensing_worker", ["--location-id", str(uuid4())]),
        ("services.ingestion.remote_sensing_worker", ["--location-id", str(uuid4()), "--limit", "10"]),
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
        ("services.ingestion.sensor_worker", []),
        ("services.ingestion.sensor_ingester", ["--file", "/tmp/readings.csv"]),
        ("services.ingestion.sensor_ingester", ["--location-id", str(uuid4())]),
        (
            "services.ingestion.sensor_ingester",
            ["--location-id", str(uuid4()), "--driver-instance-id", "invalid"],
        ),
        (
            "services.ingestion.sensor_worker",
            ["--location-id", str(uuid4()), "--driver-instance-id", "invalid"],
        ),
        ("services.analytics.carbon_credit_adjustment_check", []),
        ("services.ingestion.weather", []),
        ("services.ingestion.weather_worker", []),
        ("services.ingestion.weather_forecast", []),
        ("services.ingestion.weather_forecast", ["--all-locations"]),
        ("services.ingestion.eas_indexer", []),
        ("services.ingestion.eas_worker", []),
        ("services.ingestion.eas_indexer", ["--chain", "ethereum"]),
        ("services.ingestion.eas_indexer", ["--chain", "celo", "--chain", "base"]),
        ("services.ingestion.eas_worker", ["--chain", "celo", "--chain", "base"]),
        (
            "services.ingestion.eas_worker",
            ["--chain", "celo", "--replay-lookback-seconds", "3600"],
        ),
        ("services.ingestion.rpc_indexer", []),
        ("services.ingestion.rpc_indexer", ["--wallet", "0x" + "a" * 40]),
        ("services.ingestion.rpc_indexer", ["--chain", "polygon"]),
        ("services.ingestion.anomaly_detector", []),
        ("services.ingestion.anomaly_detector", ["--baseline-check"]),
        ("services.ingestion.climate_data", ["--all"]),
        ("services.ingestion.climate_data", ["--all", "--location-id", "invalid"]),
        ("services.ingestion.climate_data", ["--all", "--worldclim", "--location-id", str(uuid4())]),
        ("services.ingestion.market_data", ["--month", "1"]),
        ("services.ingestion.market_data", ["--source", "unknown"]),
        ("services.ingestion.market_data_worker", ["--source", "seed"]),
        ("services.ingestion.market_data_worker", ["--month", "1"]),
        ("services.ingestion.market_data_worker", ["--commodity", "durian"]),
        ("services.ingestion.market_data_worker", ["--year", "2031", "--month", "1"]),
        ("services.ingestion.rpc_indexer", ["--wallet", "not-an-address"]),
        ("services.ingestion.gnosis_indexer", ["--from-block", "10", "--to-block", "9"]),
        ("services.metrics", ["--verify-value", str(uuid4()), "--verified-by", str(uuid4())]),
        ("services.metrics", ["--compute", "--all-locations"]),
        ("services.metrics", ["--compute", "--all"]),
        ("services.metrics", ["--compute", "--all-locations", "--location-id", str(uuid4())]),
        ("services.metrics", ["--reconcile-noi-snapshots", "--location-id", str(uuid4())]),
        ("services.metrics.noi_snapshot_worker", []),
        ("services.metrics.noi_snapshot_worker", ["--location-id", "invalid"]),
        ("services.metrics.noi_snapshot_worker", ["--location-id", str(uuid4()), "--all-locations"]),
        ("services.metrics", ["--compute", "--metric", "value_flowed"]),
        ("services.events", ["--cleanup"]),
        ("services.events", ["--worker"]),
        ("services.events", ["--event-worker"]),
        ("services.events", ["--notification-worker"]),
        ("services.events", ["--dispose-dead-letter", "--event-id", str(uuid4())]),
        ("services.analytics.carbon_credits", ["--check-adjustments"]),
        ("services.ingestion.remote_sensing_fetcher", []),
        ("services.ingestion.remote_sensing_fetcher", ["--list-jobs"]),
        ("services.ingestion.remote_sensing_fetcher", ["--run-jobs", "--limit", "0"]),
        ("services.ingestion.remote_sensing_fetcher", ["--run-jobs", "--limit", "11"]),
        ("services.ingestion.remote_sensing_fetcher", ["--location-id", str(uuid4())]),
        ("services.ingestion.remote_sensing_worker", []),
        ("services.ingestion.remote_sensing_worker", ["--location-id", str(uuid4()), "--run-jobs"]),
        ("services.ingestion.remote_sensing_worker", ["--location-id", str(uuid4()), "--limit", "11"]),
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
        ("services.ingestion.weather", ["--all-locations"]),
        ("services.ingestion.weather_worker", ["--all-locations"]),
        ("services.ingestion.anomaly_detector", ["--all-locations"]),
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


def test_metric_compute_schedule_plan_requires_one_location():
    job = JOBS["metrics"]
    assert job.arguments == ("--compute", "--all")
    assert job.required_inputs == ("location_id",)

    with pytest.raises(ValueError, match="schedule planning requires one location"):
        build_job_plan("metrics", "daily")

    location_id = str(uuid4())
    plan = build_job_plan("metrics", "daily", location_id=location_id)
    task = plan["scheduled_task"]
    assert task["command_args"] == ["--compute", "--all", "--location-id", location_id]
    assert not task["is_enabled"]


def test_eas_job_and_schedule_plan_require_one_explicit_supported_chain():
    job = JOBS["eas"]
    assert job.required_inputs == ("chain",)

    with pytest.raises(ValueError, match="requires a chain"):
        run_job("eas")
    with pytest.raises(ValueError, match="requires one chain"):
        build_job_plan("eas", "every-6h")

    plan = build_job_plan("eas", "every-6h", chain="celo")
    task = plan["scheduled_task"]
    assert task["name"] == "kernel-eas-every-6h-celo"
    assert task["command_args"] == ["--chain", "celo"]
    assert task["is_enabled"] is False

    with pytest.raises(ScheduledCommandRejected, match="EAS chain is not supported"):
        build_job_plan("eas", "every-6h", chain="ethereum")


def test_rpc_job_and_schedule_plan_require_one_explicit_supported_chain():
    job = JOBS["rpc"]
    assert job.required_inputs == ("chain",)

    with pytest.raises(ValueError, match="RPC indexing refresh requires a chain"):
        run_job("rpc")
    with pytest.raises(ValueError, match="RPC schedule planning requires one chain"):
        build_job_plan("rpc", "every-6h")

    plan = build_job_plan("rpc", "every-6h", chain="celo")
    task = plan["scheduled_task"]
    assert task["name"] == "kernel-rpc-every-6h-celo"
    assert task["command_args"] == ["--chain", "celo"]
    assert task["is_enabled"] is False

    with pytest.raises(ScheduledCommandRejected, match="RPC chain is not supported"):
        build_job_plan("rpc", "every-6h", chain="polygon")


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


def test_weather_forecast_job_requires_one_explicit_location_and_stays_disabled():
    job = JOBS["weather_forecast"]

    assert job.module == "services.ingestion.weather_forecast_worker"
    assert job.scheduler_allowed
    assert job.required_inputs == ("location_id",)
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ValueError, match="Weather forecast refresh requires a location"):
            run_job("weather_forecast")
    run.assert_not_called()

    location_id = str(uuid4())
    plan = build_job_plan("weather_forecast", "every-6h", location_id=location_id)
    task = plan["scheduled_task"]
    assert task["module_path"] == job.module
    assert task["command_args"] == ["--location-id", location_id]
    assert task["is_enabled"] is False
    assert task["allow_overlap"] is False


def test_weather_forecast_dispatch_forwards_only_its_exact_worker_credentials():
    location_id = str(uuid4())
    completed = MagicMock(returncode=0, stdout='{"rows_written": 1}')
    environment = {
        "KOKONUT_WEATHER_FORECAST_DATABASE_URL": "synthetic-dsn",
        "KOKONUT_WEATHER_FORECAST_WORKER_CREDENTIAL": "synthetic-credential",
    }
    with (
        patch("services.core.jobs.subprocess.run", return_value=completed) as run,
        patch("services.core.jobs.worker_subprocess_environment", return_value=environment) as child_environment,
    ):
        result = run_job("weather_forecast", location_id=location_id)

    assert result["status"] == "success"
    assert run.call_args.args[0] == [
        sys.executable,
        "-m",
        "services.ingestion.weather_forecast_worker",
        "--location-id",
        location_id,
    ]
    assert run.call_args.kwargs["env"] is environment
    child_environment.assert_called_once_with(
        allowed_worker_keys=("weather_forecast",),
        isolated_database_credentials=True,
    )


def test_anomaly_job_requires_one_explicit_location_before_dispatch():
    job = JOBS["anomaly"]

    assert job.module == "services.ingestion.anomaly_detector"
    assert job.required_inputs == ("location_id",)
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ValueError, match="Anomaly refresh requires a location"):
            run_job("anomaly")
    run.assert_not_called()

    with pytest.raises(ValueError, match="Anomaly schedule planning requires one location"):
        build_job_plan("anomaly", "hourly")

    location_id = str(uuid4())
    plan = build_job_plan("anomaly", "hourly", location_id=location_id)
    assert plan["scheduled_task"]["command_args"] == ["--location-id", location_id]
    assert plan["scheduled_task"]["is_enabled"] is False


def test_remote_sensing_job_defaults_to_one_due_job_batch():
    job = JOBS["remote_sensing"]

    assert job.module == "services.ingestion.remote_sensing_worker"
    assert job.scheduler_allowed
    assert job.required_inputs == ("location_id",)
    with pytest.raises(ScheduledCommandRejected, match="requires one explicit location"):
        validate_scheduled_command(job.module, list(job.arguments))
    location_id = str(uuid4())
    assert validate_scheduled_command(
        job.module, [*job.arguments, "--location-id", location_id]
    ) == (*job.arguments, "--location-id", location_id)
    with pytest.raises(ValueError, match="requires one location"):
        build_job_plan("remote_sensing", "every-6h")
    plan = build_job_plan("remote_sensing", "every-6h", location_id=location_id)
    assert plan["scheduled_task"]["command_args"] == ["--location-id", location_id]
    assert plan["scheduled_task"]["is_enabled"] is False


def test_sensor_job_requires_a_registered_instance_and_location_before_launch():
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ValueError, match="requires a location and a driver instance"):
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


def test_run_now_passes_filtered_environment_to_task_child():
    from services.scheduler.cli import cmd_run_now

    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    location_id = str(uuid4())
    cursor.fetchone.return_value = ("services.metrics", ["--compute", "--all", "--location-id", location_id], 30)
    connection = MagicMock()
    connection.cursor.return_value = cursor
    child_env = {"PATH": "/synthetic/bin"}
    completed = MagicMock(returncode=0)

    with (
        patch("services.common.database.get_db", return_value=connection),
        patch("subprocess.run", return_value=completed) as run,
        patch("services.scheduler.cli.worker_subprocess_environment", return_value=child_env),
    ):
        result = cmd_run_now(Namespace(task_name="metrics"))

    assert result == 0
    run.assert_called_once_with(
        [sys.executable, "-m", "services.metrics", "--compute", "--all", "--location-id", location_id],
        timeout=30,
        env=child_env,
    )
    connection.close.assert_called_once()


def test_run_now_forwards_noi_worker_secrets_only_to_signed_module():
    from services.scheduler.cli import cmd_run_now

    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    location_id = str(uuid4())
    cursor.fetchone.return_value = (
        "services.metrics.noi_snapshot_worker",
        ["--location-id", location_id],
        30,
    )
    connection = MagicMock()
    connection.cursor.return_value = cursor
    child_env = {"KOKONUT_NOI_SNAPSHOT_WORKER_CREDENTIAL": "synthetic"}
    completed = MagicMock(returncode=0)

    with (
        patch("services.common.database.get_db", return_value=connection),
        patch("subprocess.run", return_value=completed) as run,
        patch("services.scheduler.cli.worker_subprocess_environment", return_value=child_env) as env_builder,
    ):
        result = cmd_run_now(Namespace(task_name="noi_snapshots"))

    assert result == 0
    env_builder.assert_called_once_with(
        allowed_worker_keys=("noi_snapshot",), isolated_database_credentials=True
    )
    assert run.call_args.kwargs["env"] is child_env
    connection.close.assert_called_once()


def test_reviewable_job_plans_require_tenant_and_driver_inputs():
    weather = build_job_plan("weather", "hourly", location_id=str(uuid4()))
    assert weather["scheduled_task"]["command_args"][0] == "--location-id"

    climate = build_job_plan("climate", "weekly", location_id=str(uuid4()))
    assert "--location-id" in climate["scheduled_task"]["command_args"]

    with pytest.raises(ValueError, match="requires one location"):
        build_job_plan("noi_snapshots", "daily")

    location_id = str(uuid4())
    snapshots = build_job_plan("noi_snapshots", "daily", location_id=location_id)
    assert snapshots["scheduled_task"]["module_path"] == "services.metrics.noi_snapshot_worker"
    assert snapshots["scheduled_task"]["command_args"] == ["--location-id", location_id]
    assert snapshots["scheduled_task"]["is_enabled"] is False

    with pytest.raises(ValueError, match="requires one location and one driver instance"):
        build_job_plan("sensors", "hourly")

    location_id = str(uuid4())
    driver_instance_id = str(uuid4())
    sensors = build_job_plan(
        "sensors",
        "hourly",
        location_id=location_id,
        driver_instance_id=driver_instance_id,
    )
    assert sensors["scheduled_task"]["command_args"] == [
        "--location-id",
        location_id,
        "--driver-instance-id",
        driver_instance_id,
    ]
    assert sensors["scheduled_task"]["is_enabled"] is False


def test_noi_snapshot_job_requires_location_before_dispatch():
    job = JOBS["noi_snapshots"]

    assert job.module == "services.metrics.noi_snapshot_worker"
    assert job.required_inputs == ("location_id",)
    with (
        patch("services.core.jobs.subprocess.run") as run,
        patch("services.core.jobs.worker_subprocess_environment") as child_environment,
    ):
        with pytest.raises(ValueError, match="requires a location"):
            run_job("noi_snapshots")
    run.assert_not_called()
    child_environment.assert_not_called()

    location_id = str(uuid4())
    completed = MagicMock(returncode=0, stdout='{"reconciled": 1}')
    environment = {"KOKONUT_NOI_SNAPSHOT_WORKER_CREDENTIAL": "synthetic"}
    with (
        patch("services.core.jobs.subprocess.run", return_value=completed) as run,
        patch("services.core.jobs.worker_subprocess_environment", return_value=environment) as child_environment,
    ):
        result = run_job("noi_snapshots", location_id=location_id)

    assert result["status"] == "success"
    assert run.call_args.args[0] == [
        sys.executable,
        "-m",
        "services.metrics.noi_snapshot_worker",
        "--location-id",
        location_id,
    ]
    assert run.call_args.kwargs["env"] is environment
    child_environment.assert_called_once_with(
        allowed_worker_keys=("noi_snapshot",), isolated_database_credentials=True
    )


def test_sensor_job_dispatch_passes_only_registered_instance_and_location():
    location_id = str(uuid4())
    driver_instance_id = str(uuid4())
    environment = {"KOKONUT_SENSOR_INGESTION_DATABASE_URL": "postgresql://sensor-worker"}
    completed = MagicMock(returncode=0, stdout='{"records_written": 1}')
    with (
        patch("services.core.jobs.subprocess.run", return_value=completed) as run,
        patch("services.core.jobs.worker_subprocess_environment", return_value=environment) as child_environment,
    ):
        result = run_job(
            "sensors",
            location_id=location_id,
            driver_instance_id=driver_instance_id,
        )

    assert result["status"] == "success"
    assert run.call_args.args[0] == [
        sys.executable,
        "-m",
        "services.ingestion.sensor_worker",
        "--location-id",
        location_id,
        "--driver-instance-id",
        driver_instance_id,
    ]
    assert run.call_args.kwargs["env"] is environment
    child_environment.assert_called_once_with(
        allowed_worker_keys=("sensor_ingestion",),
        isolated_database_credentials=True,
    )
