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


def test_scheduled_hourly_preserves_anomaly_and_freshness_without_sensor_flow() -> None:
    from unittest.mock import patch

    from services.flows.pipelines import scheduled_hourly

    with (
        patch("services.flows.anomaly_detection.anomaly_detection_flow") as anomaly,
        patch("services.flows.freshness.freshness_check_flow") as freshness,
        patch("services.flows.sensors.sensor_ingestion_flow") as sensor,
    ):
        scheduled_hourly.fn()

    anomaly.assert_called_once_with()
    freshness.assert_called_once_with()
    sensor.assert_not_called()


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


def test_pipeline_has_dependency_chains() -> None:
    content = Path("services/flows/pipelines.py").read_text()
    # Analytics depends on metrics
    assert "metrics_computation_flow" in content
    assert "dashboard_refresh_flow" in content
    # Full pipeline chains ingestion -> monitoring -> analytics
    assert "ingestion_pipeline()" in content
    assert "monitoring_pipeline()" in content
    assert "analytics_pipeline()" in content
