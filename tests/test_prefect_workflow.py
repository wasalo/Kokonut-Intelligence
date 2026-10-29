"""Prefect workflow tests."""

from pathlib import Path


def test_flows_directory_exists() -> None:
    assert Path("services/flows").exists()


def test_flows_init_exists() -> None:
    assert Path("services/flows/__init__.py").exists()


def test_pipeline_definitions_exist() -> None:
    assert Path("services/flows/pipelines.py").exists()


def test_all_flow_files_exist() -> None:
    flow_files = [
        "weather.py", "sensors.py", "market_data.py",
        "eas_indexer.py", "rpc_indexer.py", "gnosis_indexer.py",
        "remote_sensing.py", "anomaly_detection.py", "metrics.py",
        "dashboards.py", "freshness.py", "climate_data.py",
        "credit_adjustment.py", "health_check.py",
    ]
    for f in flow_files:
        assert Path(f"services/flows/{f}").exists(), f"Missing flow: {f}"


def test_flows_have_flow_decorators() -> None:
    content = Path("services/flows/pipelines.py").read_text()
    assert "@flow" in content
    assert "ingestion_pipeline" in content
    assert "monitoring_pipeline" in content
    assert "analytics_pipeline" in content
    assert "full_pipeline" in content
    assert "scheduled_hourly" in content
    assert "scheduled_every_6h" in content
    assert "scheduled_daily" in content
    assert "scheduled_weekly" in content


def test_flows_import_existing_cli_tools() -> None:
    content = Path("services/flows/pipelines.py").read_text()
    assert "weather_ingestion_flow" in content
    assert "sensor_ingestion_flow" not in content
    assert "market_data_flow" in content
    assert "metrics_computation_flow" in content
    assert "dashboard_refresh_flow" in content


def test_ingestion_pipeline_skips_source_less_sensor_job_and_waits_for_other_jobs() -> None:
    from unittest.mock import Mock, call, patch

    from services.flows.pipelines import ingestion_pipeline

    jobs = ("weather", "market_data", "eas", "rpc", "gnosis")
    futures = {job_id: Mock() for job_id in jobs}

    with patch("services.flows.pipelines._submit_job", side_effect=futures.__getitem__) as submit:
        result = ingestion_pipeline.fn()

    assert result == {"status": "success", "ingestion": "complete"}
    assert submit.call_args_list == [call(job_id) for job_id in jobs]
    assert all(future.result.call_count == 1 for future in futures.values())


def test_eas_flow_preserves_multi_chain_adapter():
    from unittest.mock import patch

    from services.flows.eas_indexer import eas_indexing_flow

    expected = {"status": "success", "chains_processed": 3}
    with patch("services.flows.eas_indexer.run_job_for_eas_chains", return_value=expected) as run:
        assert eas_indexing_flow.fn() == expected

    run.assert_called_once_with()


def test_rpc_flow_preserves_multi_chain_adapter():
    from unittest.mock import patch

    from services.flows.rpc_indexer import rpc_indexing_flow

    expected = {"status": "success", "chains_processed": 7}
    with patch("services.flows.rpc_indexer.run_job_for_rpc_chains", return_value=expected) as run:
        assert rpc_indexing_flow.fn() == expected

    run.assert_called_once_with()


def test_scheduled_hourly_waits_for_explicit_sensor_source_mapping() -> None:
    from inspect import signature
    from unittest.mock import patch
    from uuid import uuid4

    from services.core.jobs import JOBS
    from services.flows.pipelines import scheduled_hourly
    from services.flows.sensors import sensor_ingestion_flow

    assert JOBS["sensors"].required_inputs == ("location_id", "driver_instance_id")
    assert tuple(signature(sensor_ingestion_flow.fn).parameters) == (
        "location_id",
        "driver_instance_id",
    )

    with (
        patch("services.flows.anomaly_detection.anomaly_detection_flow") as anomaly,
        patch("services.flows.freshness.freshness_check_flow") as freshness,
        patch("services.flows.sensors.sensor_ingestion_flow") as sensor,
    ):
        scheduled_hourly.fn()

    anomaly.assert_called_once_with()
    freshness.assert_called_once_with()
    sensor.assert_not_called()

    location_id = str(uuid4())
    driver_instance_id = str(uuid4())
    with patch("services.flows.sensors.run_job", return_value={"status": "success"}) as run_job:
        result = sensor_ingestion_flow.fn(location_id, driver_instance_id)

    assert result == {"status": "success"}
    run_job.assert_called_once_with(
        "sensors",
        location_id=location_id,
        driver_instance_id=driver_instance_id,
    )


def test_scheduled_weekly_runs_only_climate_refresh() -> None:
    from unittest.mock import patch

    from services.flows.pipelines import scheduled_weekly

    with patch("services.flows.climate_data.climate_data_flow") as climate:
        scheduled_weekly.fn()

    climate.assert_called_once_with()


def test_market_data_prefect_adapter_is_default_off_and_enabled_mode_dispatches() -> None:
    from unittest.mock import patch

    from services.flows.market_data import dispatch_market_data_job

    skipped = {
        "status": "skipped",
        "reason": "isolated_market_data_worker_disabled",
    }
    with (
        patch("services.flows.market_data.is_enabled", return_value=False),
        patch("services.flows.market_data.run_job") as run_job,
    ):
        assert dispatch_market_data_job() == skipped
    run_job.assert_not_called()

    expected = {"status": "success", "output": "synthetic"}
    with (
        patch("services.flows.market_data.is_enabled", return_value=True),
        patch("services.flows.market_data.run_job", return_value=expected) as run_job,
    ):
        assert dispatch_market_data_job() == expected
    run_job.assert_called_once_with("market_data")


def test_market_data_catalog_dispatch_skips_without_fallback() -> None:
    from unittest.mock import patch

    from services.flows.pipelines import _dispatch_catalog_job

    with (
        patch("services.flows.market_data.is_enabled", return_value=False),
        patch("services.flows.market_data.run_job") as run_job,
    ):
        result = _dispatch_catalog_job("market_data")

    assert result == {
        "status": "skipped",
        "reason": "isolated_market_data_worker_disabled",
    }
    run_job.assert_not_called()


def test_scheduled_daily_continues_after_default_off_market_data_skip() -> None:
    from unittest.mock import patch

    from services.flows.pipelines import scheduled_daily

    calls: list[str] = []
    with (
        patch(
            "services.flows.market_data.market_data_flow",
            side_effect=lambda: calls.append("market_data")
            or {
                "status": "skipped",
                "reason": "isolated_market_data_worker_disabled",
            },
        ),
        patch("services.flows.market_data.run_job") as run_job,
        patch(
            "services.flows.metrics.metrics_computation_flow",
            side_effect=lambda: calls.append("metrics"),
        ),
        patch(
            "services.flows.credit_adjustment.credit_adjustment_flow",
            side_effect=lambda: calls.append("credit_adjustment"),
        ),
    ):
        scheduled_daily.fn()

    run_job.assert_not_called()
    assert calls == ["market_data", "metrics", "credit_adjustment"]


def test_scheduled_every_6h_skips_default_off_dashboard_and_continues() -> None:
    from unittest.mock import patch

    from services.flows.pipelines import scheduled_every_6h

    calls: list[str] = []
    weather_result = {"status": "weather-complete"}
    remote_result = {"status": "remote-complete"}
    with (
        patch("services.flows.pipelines.is_enabled", return_value=False),
        patch(
            "services.flows.weather.weather_ingestion_flow",
            side_effect=lambda: calls.append("weather") or weather_result,
        ),
        patch("services.flows.dashboards.dashboard_refresh_flow") as dashboard,
        patch(
            "services.flows.remote_sensing.remote_sensing_flow",
            side_effect=lambda: calls.append("remote_sensing") or remote_result,
        ),
    ):
        result = scheduled_every_6h.fn()

    assert calls == ["weather", "remote_sensing"]
    dashboard.assert_not_called()
    assert result == {
        "status": "success",
        "weather": weather_result,
        "dashboard_refresh": {
            "status": "skipped",
            "reason": "legacy_dataset_sql_disabled",
        },
        "remote_sensing": remote_result,
    }


def test_scheduled_every_6h_preserves_enabled_dashboard_order() -> None:
    from unittest.mock import patch

    from services.flows.pipelines import scheduled_every_6h

    calls: list[str] = []
    expected = {
        "weather": {"status": "weather-complete"},
        "dashboard": {"status": "dashboard-complete"},
        "remote_sensing": {"status": "remote-complete"},
    }
    with (
        patch("services.flows.pipelines.is_enabled", return_value=True),
        patch(
            "services.flows.weather.weather_ingestion_flow",
            side_effect=lambda: calls.append("weather") or expected["weather"],
        ),
        patch(
            "services.flows.dashboards.dashboard_refresh_flow",
            side_effect=lambda: calls.append("dashboard") or expected["dashboard"],
        ),
        patch(
            "services.flows.remote_sensing.remote_sensing_flow",
            side_effect=lambda: calls.append("remote_sensing") or expected["remote_sensing"],
        ),
    ):
        result = scheduled_every_6h.fn()

    assert calls == ["weather", "dashboard", "remote_sensing"]
    assert result == {
        "status": "success",
        "weather": expected["weather"],
        "dashboard_refresh": expected["dashboard"],
        "remote_sensing": expected["remote_sensing"],
    }


def test_anomaly_prefect_flow_uses_owner_scoped_location_fanout() -> None:
    from unittest.mock import patch

    from services.flows.anomaly_detection import anomaly_detection_flow

    with patch(
        "services.flows.anomaly_detection.run_job_for_kokonut_network_locations",
        return_value={"status": "success", "locations_processed": 2},
    ) as run_job:
        result = anomaly_detection_flow.fn()

    assert result == {"status": "success", "locations_processed": 2}
    run_job.assert_called_once_with("anomaly")


def test_flows_have_retry_config() -> None:
    for f in Path("services/flows").glob("*.py"):
        content = f.read_text()
        if "@flow" in content:
            assert "retries" in content or "retry" in content, f"{f.name} missing retry config"


def test_deployment_yaml_exists() -> None:
    assert Path("config/prefect/deployment.yaml").exists()


def test_deployment_yaml_has_schedules() -> None:
    content = Path("config/prefect/deployment.yaml").read_text()
    assert "cron" in content
    assert "hourly" in content
    assert "daily" in content
    assert "weekly" in content


def test_requirements_has_prefect() -> None:
    content = Path("requirements.txt").read_text()
    assert "prefect" in content


def test_weather_flow_wraps_cli() -> None:
    from unittest.mock import patch

    from services.flows.weather import weather_ingestion_flow

    with patch("services.flows.weather.run_job", return_value={"status": "success"}) as run_job:
        assert weather_ingestion_flow.fn("80b1d06b-a82d-4d02-a4f6-243e81fdf122") == {"status": "success"}
    run_job.assert_called_once_with("weather", location_id="80b1d06b-a82d-4d02-a4f6-243e81fdf122")


def test_metrics_flow_wraps_cli() -> None:
    from services.core.jobs import JOBS

    spec = JOBS["metrics"]
    assert spec.module == "services.metrics"
    assert spec.arguments == ("--compute", "--all")
    assert spec.required_inputs == ("location_id",)
    assert "--verify" not in spec.arguments


def test_metrics_and_credit_prefect_flows_preserve_owner_scoped_fanout() -> None:
    from unittest.mock import patch

    from services.flows.credit_adjustment import credit_adjustment_flow
    from services.flows.metrics import metrics_computation_flow

    with (
        patch("services.flows.metrics.run_job_for_kokonut_network_locations", return_value={"status": "success"}) as metrics_fanout,
        patch("services.flows.credit_adjustment.run_job_for_kokonut_network_locations", return_value={"status": "success"}) as credit_fanout,
    ):
        metrics_computation_flow.fn()
        credit_adjustment_flow.fn()

    metrics_fanout.assert_called_once_with("metrics")
    credit_fanout.assert_called_once_with("credit_adjustment")


def test_remote_sensing_prefect_flow_preserves_owner_scoped_fanout() -> None:
    from unittest.mock import patch

    from services.flows.remote_sensing import remote_sensing_flow

    with patch(
        "services.flows.remote_sensing.run_job_for_kokonut_network_locations",
        return_value={"status": "success"},
    ) as fanout:
        assert remote_sensing_flow.fn() == {"status": "success"}

    fanout.assert_called_once_with("remote_sensing")


def test_pipeline_dispatch_routes_required_location_jobs_through_owner_fanout() -> None:
    from unittest.mock import patch

    from services.flows.pipelines import _dispatch_catalog_job

    with (
        patch("services.flows.pipelines.run_job_for_kokonut_network_locations", return_value={"status": "success"}) as fanout,
        patch("services.flows.pipelines.run_job") as run_job,
    ):
        result = _dispatch_catalog_job("weather")

    assert result == {"status": "success"}
    fanout.assert_called_once_with("weather")
    run_job.assert_not_called()


def test_pipeline_dispatch_scopes_eas_to_explicit_chains():
    from unittest.mock import patch

    from services.flows.pipelines import _dispatch_catalog_job

    with (
        patch("services.flows.pipelines.run_job_for_eas_chains", return_value={"status": "success"}) as eas,
        patch("services.flows.pipelines.run_job") as run_job,
    ):
        result = _dispatch_catalog_job("eas")

    assert result == {"status": "success"}
    eas.assert_called_once_with()
    run_job.assert_not_called()


def test_pipeline_dispatch_scopes_rpc_to_explicit_chains():
    from unittest.mock import patch

    from services.flows.pipelines import _dispatch_catalog_job

    with (
        patch("services.flows.pipelines.run_job_for_rpc_chains", return_value={"status": "success"}) as rpc,
        patch("services.flows.pipelines.run_job") as run_job,
    ):
        result = _dispatch_catalog_job("rpc")

    assert result == {"status": "success"}
    rpc.assert_called_once_with()
    run_job.assert_not_called()


def test_pipeline_has_dependency_chains() -> None:
    content = Path("services/flows/pipelines.py").read_text()
    # Analytics depends on metrics
    assert "metrics_computation_flow" in content
    assert "dashboard_refresh_flow" in content
    # Full pipeline chains ingestion -> monitoring -> analytics
    assert "ingestion_pipeline()" in content
    assert "monitoring_pipeline()" in content
    assert "analytics_pipeline()" in content
