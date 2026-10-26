"""Worker credentials must cross subprocess boundaries only by policy."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services.common.worker_environment import (
    ISOLATED_WORKER_KEY_ENV,
    scheduled_module_worker_key,
    worker_subprocess_environment,
)

ROOT = Path(__file__).resolve().parents[1]


def test_default_child_environment_removes_all_worker_secrets():
    source = {
        "PATH": "/synthetic/bin",
        "DATABASE_URL": "postgresql://application",
        "KOKONUT_SCHEDULER_DATABASE_URL": "postgresql://scheduler",
        "KOKONUT_SCHEDULER_WORKER_CREDENTIAL": "scheduler-secret",
        "KOKONUT_EVENT_BUS_DATABASE_URL": "postgresql://events",
        "KOKONUT_EVENT_BUS_WORKER_CREDENTIAL": "event-secret",
        "KOKONUT_PROVIDER_API_KEY": "provider-config",
    }

    assert worker_subprocess_environment(environ=source) == {
        "PATH": "/synthetic/bin",
        "DATABASE_URL": "postgresql://application",
        "KOKONUT_PROVIDER_API_KEY": "provider-config",
    }


def test_child_environment_allows_only_the_named_worker_key():
    source = {
        "KOKONUT_SCHEDULER_DATABASE_URL": "postgresql://scheduler",
        "KOKONUT_SCHEDULER_WORKER_CREDENTIAL": "scheduler-secret",
        "KOKONUT_EVENT_BUS_DATABASE_URL": "postgresql://events",
        "KOKONUT_EVENT_BUS_WORKER_CREDENTIAL": "event-secret",
    }
    assert worker_subprocess_environment(
        allowed_worker_keys=("scheduler",), environ=source
    ) == {
        "KOKONUT_SCHEDULER_DATABASE_URL": "postgresql://scheduler",
        "KOKONUT_SCHEDULER_WORKER_CREDENTIAL": "scheduler-secret",
    }


def test_scheduled_noi_worker_receives_only_its_exact_secret_pair():
    source = {
        "KOKONUT_NOI_SNAPSHOT_DATABASE_URL": "postgresql://noi-worker",
        "KOKONUT_NOI_SNAPSHOT_WORKER_CREDENTIAL": "noi-secret",
        "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://anomaly-worker",
        "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "anomaly-secret",
        "PG_HOST": "database",
        "PG_PORT": "5432",
        "PG_DB": "kokonut_intelligence",
        "PG_USER": "kokonut_runtime",
        "PG_PASSWORD": "shared-runtime-secret",
        "POSTGRES_PASSWORD": "database-admin-secret",
    }
    module = "services.metrics.noi_snapshot_worker"
    worker_key = scheduled_module_worker_key(module)

    assert worker_key == "noi_snapshot"
    assert worker_subprocess_environment(
        allowed_worker_keys=(worker_key,),
        isolated_database_credentials=True,
        environ=source,
    ) == {
        "KOKONUT_NOI_SNAPSHOT_DATABASE_URL": "postgresql://noi-worker",
        "KOKONUT_NOI_SNAPSHOT_WORKER_CREDENTIAL": "noi-secret",
        ISOLATED_WORKER_KEY_ENV: "noi_snapshot",
    }
    assert scheduled_module_worker_key("services.metrics") is None
    assert scheduled_module_worker_key("services.metrics.noi_snapshot_worker.extra") is None


def test_isolated_clickhouse_outbox_receives_only_its_dedicated_dsn():
    source = {
        "KOKONUT_CLICKHOUSE_OUTBOX_DATABASE_URL": "postgresql://clickhouse-worker",
        "KOKONUT_FRESHNESS_DATABASE_URL": "postgresql://other-worker",
        "PG_HOST": "database",
        "PG_USER": "kokonut_runtime",
        "PG_PASSWORD": "shared-secret",
        "DATABASE_URL": "postgresql://shared/app",
    }
    module = "services.ingestion.clickhouse_outbox_worker"
    worker_key = scheduled_module_worker_key(module)

    assert worker_key == "clickhouse_outbox"
    assert worker_subprocess_environment(
        allowed_worker_keys=(worker_key,),
        isolated_database_credentials=True,
        environ=source,
    ) == {
        "KOKONUT_CLICKHOUSE_OUTBOX_DATABASE_URL": "postgresql://clickhouse-worker",
        ISOLATED_WORKER_KEY_ENV: "clickhouse_outbox",
    }


def test_scheduled_anomaly_replay_receives_only_its_existing_worker_identity():
    source = {
        "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://anomaly-worker",
        "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "anomaly-secret",
        "KOKONUT_FRESHNESS_DATABASE_URL": "postgresql://freshness-worker",
        "PG_USER": "kokonut_runtime",
        "PG_PASSWORD": "shared-secret",
    }
    module = "services.ingestion.sensor_anomaly_scan_worker"
    worker_key = scheduled_module_worker_key(module)

    assert worker_key == "sensor_anomaly"
    assert worker_subprocess_environment(
        allowed_worker_keys=(worker_key,),
        isolated_database_credentials=True,
        environ=source,
    ) == {
        "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://anomaly-worker",
        "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "anomaly-secret",
        ISOLATED_WORKER_KEY_ENV: "sensor_anomaly",
    }


def test_scheduled_credit_adjustment_worker_receives_only_its_exact_secret_pair():
    source = {
        "KOKONUT_CREDIT_ADJUSTMENT_DATABASE_URL": "postgresql://credit-worker",
        "KOKONUT_CREDIT_ADJUSTMENT_WORKER_CREDENTIAL": "credit-secret",
        "KOKONUT_NOI_SNAPSHOT_DATABASE_URL": "postgresql://noi-worker",
        "KOKONUT_NOI_SNAPSHOT_WORKER_CREDENTIAL": "noi-secret",
        "PG_HOST": "database",
        "PG_PORT": "5432",
        "PG_DB": "kokonut_intelligence",
        "PG_USER": "kokonut_runtime",
        "PG_PASSWORD": "shared-runtime-secret",
        "POSTGRES_PASSWORD": "database-admin-secret",
    }
    module = "services.analytics.carbon_credit_adjustment_worker"
    worker_key = scheduled_module_worker_key(module)

    assert worker_key == "credit_adjustment"
    assert worker_subprocess_environment(
        allowed_worker_keys=(worker_key,),
        isolated_database_credentials=True,
        environ=source,
    ) == {
        "KOKONUT_CREDIT_ADJUSTMENT_DATABASE_URL": "postgresql://credit-worker",
        "KOKONUT_CREDIT_ADJUSTMENT_WORKER_CREDENTIAL": "credit-secret",
        ISOLATED_WORKER_KEY_ENV: "credit_adjustment",
    }


def test_scheduled_weather_forecast_worker_receives_only_its_exact_secret_pair():
    source = {
        "KOKONUT_WEATHER_FORECAST_DATABASE_URL": "postgresql://forecast-worker",
        "KOKONUT_WEATHER_FORECAST_WORKER_CREDENTIAL": "forecast-secret",
        "KOKONUT_NOI_SNAPSHOT_DATABASE_URL": "postgresql://noi-worker",
        "KOKONUT_NOI_SNAPSHOT_WORKER_CREDENTIAL": "noi-secret",
        "PG_HOST": "database",
        "PG_PORT": "5432",
        "PG_DB": "kokonut_intelligence",
        "PG_USER": "kokonut_runtime",
        "PG_PASSWORD": "shared-runtime-secret",
        "POSTGRES_PASSWORD": "database-admin-secret",
    }
    module = "services.ingestion.weather_forecast_worker"
    worker_key = scheduled_module_worker_key(module)

    assert worker_key == "weather_forecast"
    assert worker_subprocess_environment(
        allowed_worker_keys=(worker_key,),
        isolated_database_credentials=True,
        environ=source,
    ) == {
        "KOKONUT_WEATHER_FORECAST_DATABASE_URL": "postgresql://forecast-worker",
        "KOKONUT_WEATHER_FORECAST_WORKER_CREDENTIAL": "forecast-secret",
        ISOLATED_WORKER_KEY_ENV: "weather_forecast",
    }


def test_scheduled_current_weather_worker_receives_only_its_exact_secrets():
    source = {
        "KOKONUT_WEATHER_DATABASE_URL": "postgresql://weather-worker",
        "KOKONUT_WEATHER_WORKER_CREDENTIAL": "weather-worker-secret",
        "KOKONUT_WEATHER_OPENWEATHERMAP_API_KEY": "weather-provider-secret",
        "KOKONUT_WEATHER_FORECAST_DATABASE_URL": "postgresql://forecast-worker",
        "KOKONUT_WEATHER_FORECAST_WORKER_CREDENTIAL": "forecast-secret",
        "KOKONUT_WEATHER_FORECAST_OPENWEATHERMAP_API_KEY": "forecast-provider-secret",
        "PG_HOST": "database",
        "PG_USER": "kokonut_runtime",
        "PG_PASSWORD": "shared-runtime-secret",
    }
    module = "services.ingestion.weather_worker"
    worker_key = scheduled_module_worker_key(module)

    assert worker_key == "weather"
    assert worker_subprocess_environment(
        allowed_worker_keys=(worker_key,),
        isolated_database_credentials=True,
        environ=source,
    ) == {
        "KOKONUT_WEATHER_DATABASE_URL": "postgresql://weather-worker",
        "KOKONUT_WEATHER_WORKER_CREDENTIAL": "weather-worker-secret",
        "KOKONUT_WEATHER_OPENWEATHERMAP_API_KEY": "weather-provider-secret",
        ISOLATED_WORKER_KEY_ENV: "weather",
    }

    forecast_environment = worker_subprocess_environment(
        allowed_worker_keys=("weather_forecast",),
        isolated_database_credentials=True,
        environ=source,
    )
    assert "KOKONUT_WEATHER_OPENWEATHERMAP_API_KEY" not in forecast_environment
    assert "KOKONUT_WEATHER_FORECAST_OPENWEATHERMAP_API_KEY" in forecast_environment


def test_scheduled_market_data_worker_receives_only_its_named_database_url():
    source = {
        "KOKONUT_MARKET_DATA_DATABASE_URL": "postgresql://market-data-worker",
        "KOKONUT_WEATHER_DATABASE_URL": "postgresql://weather-worker",
        "PG_HOST": "database",
        "PG_USER": "kokonut_runtime",
        "PG_PASSWORD": "shared-runtime-secret",
        "POSTGRES_PASSWORD": "database-admin-secret",
    }
    module = "services.ingestion.market_data_worker"
    worker_key = scheduled_module_worker_key(module)

    assert worker_key == "market_data"
    assert worker_subprocess_environment(
        allowed_worker_keys=(worker_key,),
        isolated_database_credentials=True,
        environ=source,
    ) == {
        "KOKONUT_MARKET_DATA_DATABASE_URL": "postgresql://market-data-worker",
        ISOLATED_WORKER_KEY_ENV: "market_data",
    }


def test_scheduled_eas_worker_receives_only_its_named_database_url():
    source = {
        "KOKONUT_EAS_INDEXER_DATABASE_URL": "postgresql://eas-indexer-worker",
        "KOKONUT_MARKET_DATA_DATABASE_URL": "postgresql://market-data-worker",
        "PG_HOST": "database",
        "PG_USER": "kokonut_runtime",
        "PG_PASSWORD": "shared-runtime-secret",
        "POSTGRES_PASSWORD": "database-admin-secret",
    }
    module = "services.ingestion.eas_worker"
    worker_key = scheduled_module_worker_key(module)

    assert worker_key == "eas_indexer"
    assert worker_subprocess_environment(
        allowed_worker_keys=(worker_key,),
        isolated_database_credentials=True,
        environ=source,
    ) == {
        "KOKONUT_EAS_INDEXER_DATABASE_URL": "postgresql://eas-indexer-worker",
        ISOLATED_WORKER_KEY_ENV: "eas_indexer",
    }


def test_scheduled_rpc_worker_receives_only_its_database_and_provider_endpoints():
    source = {
        "KOKONUT_RPC_INDEXER_DATABASE_URL": "postgresql://rpc-indexer",
        "KOKONUT_RPC_INDEXER_RPC_ENDPOINTS": '{"celo":"https://rpc.example/?token=rpc-secret"}',
        "KOKONUT_EAS_INDEXER_DATABASE_URL": "postgresql://eas-indexer",
        "ETH_RPC_URL": "https://eth.example/?token=global-secret",
        "GNOSIS_RPC_URL": "https://gnosis.example/?token=global-secret",
        "PG_HOST": "database",
        "PG_USER": "kokonut_runtime",
        "PG_PASSWORD": "shared-runtime-secret",
        "POSTGRES_PASSWORD": "database-admin-secret",
    }
    worker_key = scheduled_module_worker_key("services.ingestion.rpc_worker")

    assert worker_key == "rpc_indexer"
    assert worker_subprocess_environment(
        allowed_worker_keys=(worker_key,),
        isolated_database_credentials=True,
        environ=source,
    ) == {
        "KOKONUT_RPC_INDEXER_DATABASE_URL": "postgresql://rpc-indexer",
        "KOKONUT_RPC_INDEXER_RPC_ENDPOINTS": '{"celo":"https://rpc.example/?token=rpc-secret"}',
        ISOLATED_WORKER_KEY_ENV: "rpc_indexer",
    }


def test_scheduled_sensor_worker_receives_only_its_named_credentials():
    source = {
        "KOKONUT_SENSOR_INGESTION_DATABASE_URL": "postgresql://sensor-worker",
        "KOKONUT_SENSOR_INGESTION_WORKER_CREDENTIAL": "sensor-worker-secret",
        "KOKONUT_MARKET_DATA_DATABASE_URL": "postgresql://other-worker",
        "KOKONUT_MARKET_DATA_WORKER_CREDENTIAL": "other-secret",
        "PG_USER": "kokonut_runtime",
        "PG_PASSWORD": "shared-runtime-secret",
        "POSTGRES_PASSWORD": "database-admin-secret",
    }
    module = "services.ingestion.sensor_worker"
    worker_key = scheduled_module_worker_key(module)

    assert worker_key == "sensor_ingestion"
    assert worker_subprocess_environment(
        allowed_worker_keys=(worker_key,),
        isolated_database_credentials=True,
        environ=source,
    ) == {
        "KOKONUT_SENSOR_INGESTION_DATABASE_URL": "postgresql://sensor-worker",
        "KOKONUT_SENSOR_INGESTION_WORKER_CREDENTIAL": "sensor-worker-secret",
        ISOLATED_WORKER_KEY_ENV: "sensor_ingestion",
    }


def test_scheduled_remote_sensing_worker_receives_only_its_identity_and_provider_secrets():
    source = {
        "KOKONUT_REMOTE_SENSING_DATABASE_URL": "postgresql://remote-sensing-worker",
        "KOKONUT_REMOTE_SENSING_WORKER_CREDENTIAL": "remote-sensing-worker-secret",
        "KOKONUT_REMOTE_SENSING_GEE_SERVICE_ACCOUNT_KEY": "/run/secrets/gee.json",
        "KOKONUT_REMOTE_SENSING_COPERNICUS_CLIENT_ID": "synthetic-client",
        "KOKONUT_REMOTE_SENSING_COPERNICUS_CLIENT_SECRET": "synthetic-secret",
        "KOKONUT_MARKET_DATA_DATABASE_URL": "postgresql://other-worker",
        "KOKONUT_MARKET_DATA_WORKER_CREDENTIAL": "other-secret",
        "GEE_SERVICE_ACCOUNT_KEY": "/legacy/gee.json",
        "COPERNICUS_CLIENT_SECRET": "legacy-secret",
        "PG_USER": "kokonut_runtime",
        "PG_PASSWORD": "shared-runtime-secret",
    }
    module = "services.ingestion.remote_sensing_worker"
    worker_key = scheduled_module_worker_key(module)

    assert worker_key == "remote_sensing"
    assert worker_subprocess_environment(
        allowed_worker_keys=(worker_key,),
        isolated_database_credentials=True,
        environ=source,
    ) == {
        "KOKONUT_REMOTE_SENSING_DATABASE_URL": "postgresql://remote-sensing-worker",
        "KOKONUT_REMOTE_SENSING_WORKER_CREDENTIAL": "remote-sensing-worker-secret",
        "KOKONUT_REMOTE_SENSING_GEE_SERVICE_ACCOUNT_KEY": "/run/secrets/gee.json",
        "KOKONUT_REMOTE_SENSING_COPERNICUS_CLIENT_ID": "synthetic-client",
        "KOKONUT_REMOTE_SENSING_COPERNICUS_CLIENT_SECRET": "synthetic-secret",
        ISOLATED_WORKER_KEY_ENV: "remote_sensing",
    }


def test_isolated_worker_marker_is_generated_and_source_marker_never_passes_through():
    source = {
        ISOLATED_WORKER_KEY_ENV: "attacker-supplied",
        "KOKONUT_WEATHER_DATABASE_URL": "postgresql://worker",
        "PG_PASSWORD": "shared-secret",
    }
    assert worker_subprocess_environment(
        allowed_worker_keys=("weather",),
        isolated_database_credentials=True,
        environ=source,
    ) == {
        "KOKONUT_WEATHER_DATABASE_URL": "postgresql://worker",
        ISOLATED_WORKER_KEY_ENV: "weather",
    }


def test_isolated_event_dispatcher_keeps_only_its_database_and_registered_handler_keys():
    source = {
        ISOLATED_WORKER_KEY_ENV: "untrusted",
        "PG_PASSWORD": "shared-secret",
        "DATABASE_URL": "postgresql://shared",
        "GNOSIS_RPC_URL": "https://provider-secret",
        "KOKONUT_EVENT_DISPATCH_DATABASE_URL": "postgresql://event-dispatch",
        "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://anomaly",
        "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "anomaly-secret",
        "KOKONUT_CACHE_INVALIDATION_DATABASE_URL": "postgresql://cache",
        "KOKONUT_NOTIFICATION_ENQUEUE_DATABASE_URL": "postgresql://enqueue",
        "KOKONUT_UNMAPPED_DATABASE_URL": "postgresql://unmapped",
        "DIRECTUS_ADMIN_TOKEN": "handler-provider-setting",
    }

    assert worker_subprocess_environment(
        allowed_worker_keys=("event_dispatch", "sensor_anomaly", "cache_invalidation", "notification_enqueue"),
        isolated_worker_key="event_dispatch",
        environ=source,
    ) == {
        ISOLATED_WORKER_KEY_ENV: "event_dispatch",
        "KOKONUT_EVENT_DISPATCH_DATABASE_URL": "postgresql://event-dispatch",
        "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://anomaly",
        "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "anomaly-secret",
        "KOKONUT_CACHE_INVALIDATION_DATABASE_URL": "postgresql://cache",
        "KOKONUT_NOTIFICATION_ENQUEUE_DATABASE_URL": "postgresql://enqueue",
        "DIRECTUS_ADMIN_TOKEN": "handler-provider-setting",
    }


def test_explicit_isolated_worker_marker_requires_a_matching_allowed_key():
    with pytest.raises(ValueError, match="present in the allowed worker keys"):
        worker_subprocess_environment(
            allowed_worker_keys=("sensor_anomaly",),
            isolated_worker_key="event_dispatch",
            environ={},
        )


@pytest.mark.parametrize("keys", [(), ("weather", "sensor_ingestion")])
def test_isolated_worker_requires_exactly_one_identity(keys):
    with pytest.raises(ValueError, match="exactly one"):
        worker_subprocess_environment(
            allowed_worker_keys=keys,
            isolated_database_credentials=True,
            environ={},
        )

@pytest.mark.parametrize("keys", ["scheduler", b"scheduler", ("bad-key",), (None,), ("ß",)])
def test_worker_environment_rejects_invalid_allowlists(keys):
    with pytest.raises(ValueError, match="worker keys"):
        worker_subprocess_environment(allowed_worker_keys=keys, environ={})


@pytest.mark.parametrize(
    "module",
    [
        "services.metrics.noi_snapshot_worker",
        "services.ingestion.weather_worker",
        "services.ingestion.weather_forecast_worker",
        "services.ingestion.climate_worker",
        "services.ingestion.market_data_worker",
        "services.ingestion.eas_worker",
        "services.ingestion.sensor_worker",
        "services.ingestion.remote_sensing_worker",
        "services.ingestion.clickhouse_outbox_worker",
    ],
)
def test_scheduled_worker_help_imports_without_shared_database_credentials(module):
    import os
    import subprocess
    import sys

    worker_key = scheduled_module_worker_key(module)
    assert worker_key is not None
    source = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(ROOT),
        "KOKONUT_ENV": "production",
        f"KOKONUT_{worker_key.upper()}_DATABASE_URL": "postgresql://synthetic-worker",
        f"KOKONUT_{worker_key.upper()}_WORKER_CREDENTIAL": "synthetic-worker-credential-not-used",
    }
    child_env = worker_subprocess_environment(
        allowed_worker_keys=(worker_key,),
        isolated_database_credentials=True,
        environ=source,
    )

    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=child_env,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()


def test_every_service_subprocess_uses_the_shared_environment_policy():
    violations = []
    for path in sorted((ROOT / "services").rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if not (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id == "subprocess"
                and function.attr in {"run", "Popen", "call", "check_call", "check_output"}
            ):
                continue
            environment = next((item.value for item in node.keywords if item.arg == "env"), None)
            if not (
                isinstance(environment, ast.Call)
                and isinstance(environment.func, ast.Name)
                and environment.func.id
                in {"worker_subprocess_environment", "_handler_child_environment"}
            ):
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert violations == []

    bus_tree = ast.parse((ROOT / "services/events/bus.py").read_text(encoding="utf-8"))
    helper = next(
        node
        for node in bus_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_handler_child_environment"
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "worker_subprocess_environment"
        for node in ast.walk(helper)
    )
