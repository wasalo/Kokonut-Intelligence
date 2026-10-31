"""Source-level safety checks for the disposable Standard recovery runner."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-kernel-standard-recovery-disposable.py"
SPEC = importlib.util.spec_from_file_location("kernel_standard_recovery_check", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


def _resolved_compose_model() -> dict:
    return {
        "services": {
            "database": {"ports": ["127.0.0.1:5432:5432"], "networks": {"kernel": {}}},
            "app": {
                "command": ["python3", "-m", "services.core.runtime", "--port", "8099", "--require-schema"],
                "ports": ["127.0.0.1:8098:8099"],
                "environment": {"KOKONUT_ENV": "production"},
                "networks": {"kernel": {}},
            },
            "worker": {
                "command": ["python3", "-m", "services.core.runtime", "--workers-only", "--require-schema"],
                "environment": {"KOKONUT_ENV": "production"},
                "healthcheck": {"interval": "30s"},
                "networks": {"kernel": {}},
            },
            "proxy": {
                "ports": ["127.0.0.1:8448:443"],
                "networks": {"kernel": {}},
            },
            "unrelated": {"networks": {"kernel": {}}},
        },
        "networks": {"kernel": {"name": "synthetic_standard_kernel"}},
        "volumes": {"kernel-postgres-data": {"name": "synthetic_pg_data"}},
    }


def test_isolated_model_preserves_split_standard_roles_without_published_ports() -> None:
    model = CHECK._isolated_compose_model(_resolved_compose_model())

    assert set(model["services"]) == {"database", "app", "worker", "proxy"}
    assert all("ports" not in service for service in model["services"].values())
    assert model["networks"]["kernel"]["internal"] is True
    assert model["services"]["app"]["command"] == [
        "python3", "-m", "services.core.runtime", "--port", "8099", "--require-schema"
    ]
    assert model["services"]["worker"]["command"] == [
        "python3", "-m", "services.core.runtime", "--workers-only", "--require-schema"
    ]
    assert model["services"]["app"]["environment"]["KOKONUT_ENV"] == "development"
    assert model["services"]["worker"]["environment"]["KOKONUT_ENV_SECRETS_NOT_REQUIRED"] == "true"
    assert model["services"]["worker"]["healthcheck"]["interval"] == "2s"


@pytest.mark.parametrize(
    ("app_command", "worker_command"),
    [
        (["python3", "-m", "services.core.runtime"], ["python3", "-m", "services.core.runtime", "--workers-only", "--require-schema"]),
        (["python3", "-m", "services.core.runtime", "--with-workers", "--require-schema"], ["python3", "-m", "services.core.runtime", "--workers-only", "--require-schema"]),
        (["python3", "-m", "services.core.runtime", "--require-schema"], ["python3", "-m", "services.core.runtime", "--require-schema"]),
    ],
)
def test_isolated_model_rejects_nonstandard_or_unready_command_pair(app_command, worker_command) -> None:
    model = _resolved_compose_model()
    model["services"]["app"]["command"] = app_command
    model["services"]["worker"]["command"] = worker_command

    with pytest.raises(CHECK.AcceptanceError):
        CHECK._isolated_compose_model(model)


def test_isolated_model_rejects_a_missing_runtime_network() -> None:
    model = _resolved_compose_model()
    model["networks"] = {}

    with pytest.raises(CHECK.AcceptanceError, match="no kernel network"):
        CHECK._isolated_compose_model(model)


@pytest.mark.parametrize(
    ("ports", "expected"),
    [({}, True), ({"8099/tcp": None}, True), ({"8099/tcp": [{"HostPort": "8099"}]}, False)],
)
def test_container_binding_guard_detects_any_published_host_port(ports, expected) -> None:
    assert CHECK._container_has_no_published_ports(
        {"NetworkSettings": {"Ports": ports}}
    ) is expected


def test_compose_file_set_matches_default_standard_proxy_profile() -> None:
    assert CHECK.BASE_COMPOSE.name == "docker-compose.kernel-candidate.yml"
    assert CHECK.STANDARD_COMPOSE.name == "docker-compose.kernel-standard.yml"
    assert CHECK.PROXY_COMPOSE.name == "docker-compose.kernel-proxy.yml"


def test_disposable_environment_does_not_inherit_provider_credentials(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KOKONUT_WEATHER_FORECAST_OPENWEATHERMAP_API_KEY", "host-secret")
    environment = CHECK._compose_environment(tmp_path)

    assert "KOKONUT_WEATHER_FORECAST_OPENWEATHERMAP_API_KEY" not in environment
    assert environment["POSTGRES_PASSWORD"] != "host-secret"


def test_standard_heartbeat_path_matches_worker_profile() -> None:
    assert CHECK.HEARTBEAT_PATH == "/var/lib/kokonut/worker-progress/supervisor.json"


def test_service_lookup_finds_exited_container_for_failure_diagnostics(monkeypatch, tmp_path) -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        output = "" if len(calls) == 1 else "exited-container-id\n"
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(CHECK, "_run", fake_run)

    assert CHECK._service_id("synthetic", tmp_path / "compose.json", {}, "worker") == "exited-container-id"
    assert calls[1][-4:] == ["ps", "--all", "-q", "worker"]


def test_failure_diagnostics_redact_disposable_secrets(monkeypatch, tmp_path) -> None:
    manifest = tmp_path / "compose.json"
    manifest.write_text("{}", encoding="utf-8")

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "password=synthetic-secret", "")

    monkeypatch.setattr(CHECK, "_run", fake_run)
    diagnostics = CHECK._failure_diagnostics(
        "synthetic-project",
        manifest,
        {
            "POSTGRES_PASSWORD": "synthetic-secret",
            "KOKONUT_RUNTIME_PASSWORD": "synthetic-secret",
        },
    )

    assert "synthetic-secret" not in diagnostics
    assert "[redacted]" in diagnostics
