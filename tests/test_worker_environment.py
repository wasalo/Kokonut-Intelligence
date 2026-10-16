"""Worker credentials must cross subprocess boundaries only by policy."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services.common.worker_environment import worker_subprocess_environment

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
                and environment.func.id == "worker_subprocess_environment"
            ):
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert violations == []
