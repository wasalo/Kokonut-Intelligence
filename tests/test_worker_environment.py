"""Worker credentials must cross subprocess boundaries only by policy."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services.common.worker_environment import (
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
    }
    assert scheduled_module_worker_key("services.metrics") is None
    assert scheduled_module_worker_key("services.metrics.noi_snapshot_worker.extra") is None


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
    }

@pytest.mark.parametrize("keys", ["scheduler", b"scheduler", ("bad-key",), (None,), ("ß",)])
def test_worker_environment_rejects_invalid_allowlists(keys):
    with pytest.raises(ValueError, match="worker keys"):
        worker_subprocess_environment(allowed_worker_keys=keys, environ={})


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
