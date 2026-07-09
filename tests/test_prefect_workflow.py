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
    assert "sensor_ingestion_flow" in content
    assert "market_data_flow" in content
    assert "metrics_computation_flow" in content
    assert "dashboard_refresh_flow" in content


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
    content = Path("services/flows/weather.py").read_text()
    assert "services.ingestion.weather" in content
    assert "subprocess" in content


def test_metrics_flow_wraps_cli() -> None:
    content = Path("services/flows/metrics.py").read_text()
    assert "services.metrics" in content
    assert "--all-locations" in content
    assert "--verify" in content


def test_pipeline_has_dependency_chains() -> None:
    content = Path("services/flows/pipelines.py").read_text()
    # Analytics depends on metrics
    assert "metrics_computation_flow" in content
    assert "dashboard_refresh_flow" in content
    # Full pipeline chains ingestion -> monitoring -> analytics
    assert "ingestion_pipeline()" in content
    assert "monitoring_pipeline()" in content
    assert "analytics_pipeline()" in content
