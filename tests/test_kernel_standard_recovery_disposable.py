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
                "command": ["python3", "-m", "services.core.runtime", "--port", "8099", "--require-schema", "--require-runtime-role"],
                "ports": ["127.0.0.1:8098:8099"],
                "environment": {"KOKONUT_ENV": "production", "PG_USER": "kokonut_runtime"},
                "networks": {"kernel": {}},
            },
            "worker": {
                "command": ["python3", "-m", "services.core.runtime", "--workers-only", "--require-schema", "--require-runtime-role"],
                "environment": {"KOKONUT_ENV": "production", "PG_USER": "kokonut_runtime"},
                "healthcheck": {"interval": "30s"},
                "networks": {"kernel": {}},
            },
            "proxy": {
                "ports": ["127.0.0.1:8448:443"],
                "networks": {"kernel": {}},
            },
            "runtime-role-bootstrap": {
                "profiles": ["runtime-admin"],
                "networks": {"kernel": {}},
            },
            "unrelated": {"networks": {"kernel": {}}},
        },
        "networks": {"kernel": {"name": "synthetic_standard_kernel"}},
        "volumes": {"kernel-postgres-data": {"name": "synthetic_pg_data"}},
    }


def test_isolated_model_preserves_split_standard_roles_without_published_ports() -> None:
    model = CHECK._isolated_compose_model(_resolved_compose_model())

    assert set(model["services"]) == {"database", "app", "worker", "proxy", "runtime-role-bootstrap"}
    assert all("ports" not in service for service in model["services"].values())
    assert model["networks"]["kernel"]["internal"] is True
    assert model["services"]["app"]["command"] == [
        "python3", "-m", "services.core.runtime", "--port", "8099", "--require-schema", "--require-runtime-role"
    ]
    assert model["services"]["worker"]["command"] == [
        "python3", "-m", "services.core.runtime", "--workers-only", "--require-schema", "--require-runtime-role"
    ]
    assert model["services"]["app"]["environment"]["KOKONUT_ENV"] == "development"
    assert model["services"]["app"]["environment"]["PG_USER"] == "kokonut_runtime"
    assert model["services"]["runtime-role-bootstrap"]["profiles"] == ["runtime-admin"]
    assert model["services"]["worker"]["environment"]["KOKONUT_ENV_SECRETS_NOT_REQUIRED"] == "true"
    assert model["services"]["worker"]["healthcheck"]["interval"] == "2s"


@pytest.mark.parametrize(
    ("app_command", "worker_command"),
    [
        (["python3", "-m", "services.core.runtime"], ["python3", "-m", "services.core.runtime", "--workers-only", "--require-schema", "--require-runtime-role"]),
        (["python3", "-m", "services.core.runtime", "--with-workers", "--require-schema", "--require-runtime-role"], ["python3", "-m", "services.core.runtime", "--workers-only", "--require-schema", "--require-runtime-role"]),
        (["python3", "-m", "services.core.runtime", "--require-schema", "--require-runtime-role"], ["python3", "-m", "services.core.runtime", "--require-schema", "--require-runtime-role"]),
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
    assert CHECK.RUNTIME_ROLE_COMPOSE.name == "docker-compose.kernel-runtime-role.yml"


def test_disposable_environment_does_not_inherit_provider_credentials(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KOKONUT_WEATHER_FORECAST_OPENWEATHERMAP_API_KEY", "host-secret")
    environment = CHECK._compose_environment(tmp_path)

    assert "KOKONUT_WEATHER_FORECAST_OPENWEATHERMAP_API_KEY" not in environment
    assert environment["POSTGRES_PASSWORD"] != "host-secret"
    assert environment["POSTGRES_PASSWORD"] != environment["KOKONUT_RUNTIME_PASSWORD"]
    assert environment["KOKONUT_RUNTIME_PASSWORD"] != environment["KOKONUT_OPERATOR_AUTH_PASSWORD"]


def test_standard_heartbeat_path_matches_worker_profile() -> None:
    assert CHECK.HEARTBEAT_PATH == "/var/lib/kokonut/worker-progress/supervisor.json"


def test_runtime_reference_read_only_boundary_checks_reads_and_table_column_writes(
    monkeypatch, tmp_path
) -> None:
    calls = []
    output = "\n".join(
        [
            "t|t|t|t|t|t|t",
            "form_of_capital|t|f|f|f|f|f|f|t",
            "pillar_of_value|t|f|f|f|f|f|f|t",
            "regeneration_principle|t|f|f|f|f|f|f|t",
            "sdg|t|f|f|f|f|f|f|t",
            "solution|t|f|f|f|f|f|f|t",
            "solution_lifecycle_event|t|f|f|f|f|f|f|t",
            "time_delay|t|f|f|f|f|f|f|t",
        ]
    )

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(CHECK, "_run", fake_run)
    CHECK._assert_runtime_reference_read_only_boundary(
        "synthetic-standard", tmp_path / "compose.json", {}
    )

    assert len(calls) == 1
    assert calls[0][-8:-4] == ["-U", "kokonut", "-d", "kokonut_intelligence"]
    assert "-XAtq" in calls[0]
    query = calls[0][-1]
    assert "SET ROLE kokonut_runtime" in query
    assert "has_column_privilege" in query
    assert all(name in query for name in CHECK.RUNTIME_REFERENCE_READ_ONLY_TABLES)


@pytest.mark.parametrize(
    "output",
    [
        "f|t|t|t|t|t|t\nform_of_capital|t|f|f|f|f|f|f|t",
        "t|t|t|t|t|t|t\nform_of_capital|t|f|t|f|f|f|f|t",
        "t|t|t|t|t|t|t\nform_of_capital|t|f|f|f|f|f|f|f",
        "t|t|t|t|t|t|t\nform_of_capital|t|f|f|f|f|f|f|t\nsdg|t|f|f|f|f|f|f|t\ntime_delay|t|f|f|f|f|f|f|t",
    ],
)
def test_runtime_reference_read_only_boundary_rejects_missing_or_mutable_acl(
    monkeypatch, tmp_path, output
) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(CHECK, "_run", fake_run)
    with pytest.raises(CHECK.AcceptanceError, match="curated reference tables"):
        CHECK._assert_runtime_reference_read_only_boundary(
            "synthetic-standard", tmp_path / "compose.json", {}
        )


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
            "KOKONUT_DB_ADMIN_PASSWORD": "admin-secret",
            "KOKONUT_RUNTIME_PASSWORD": "synthetic-secret",
            "KOKONUT_OPERATOR_AUTH_PASSWORD": "operator-secret",
        },
    )

    assert "synthetic-secret" not in diagnostics
    assert "admin-secret" not in diagnostics
    assert "operator-secret" not in diagnostics
    assert "[redacted]" in diagnostics


def test_standard_bootstrap_is_explicit_and_not_an_app_or_worker_dependency() -> None:
    model = _resolved_compose_model()
    CHECK._validate_explicit_runtime_role_bootstrap(
        model["services"]["app"],
        model["services"]["worker"],
        model["services"]["runtime-role-bootstrap"],
    )


@pytest.mark.parametrize("value", ["t|f|f|f|f|f|f|f|f|f"])
def test_runtime_role_attributes_accept_least_privilege_login(value) -> None:
    assert CHECK._runtime_role_attributes(value) == {
        "login": True,
        "inherit": False,
        "superuser": False,
        "create_database": False,
        "create_role": False,
        "replication": False,
        "bypass_rls": False,
        "owns_database": False,
        "member_of_database_owner": False,
        "has_role_memberships": False,
    }


@pytest.mark.parametrize(
    "value",
    [
        "t|f|t|f|f|f|f|f|f|f",
        "t|f|f|f|t|f|f|f|f|f",
        "t|t|f|f|f|f|f|f|f|f",
        "t|f|f|f|f|f|f|f|f|t",
        "f|f|f|f|f|f|f|f|f|f",
        "malformed",
    ],
)
def test_runtime_role_attributes_reject_privileged_or_invalid_roles(value) -> None:
    with pytest.raises(CHECK.AcceptanceError):
        CHECK._runtime_role_attributes(value)


def test_unsafe_admin_login_is_rejected_before_children() -> None:
    CHECK._assert_runtime_role_gate_rejected(
        1,
        "Kernel schema readiness failed (runtime_role_unsafe: expected=700); review status",
    )


@pytest.mark.parametrize(
    ("returncode", "output"),
    [
        (0, ""),
        (1, "Kernel schema readiness failed (runtime_role_unavailable)") ,
        (1, "Started Kernel process scheduler"),
    ],
)
def test_unsafe_admin_login_must_fail_with_expected_code_before_spawn(returncode, output) -> None:
    with pytest.raises(CHECK.AcceptanceError):
        CHECK._assert_runtime_role_gate_rejected(returncode, output)


def test_standard_bootstrap_rejects_automatic_runtime_role_dependency() -> None:
    model = _resolved_compose_model()
    model["services"]["app"]["depends_on"] = {"runtime-role-bootstrap": {"condition": "service_completed_successfully"}}

    with pytest.raises(CHECK.AcceptanceError, match="must not auto-run"):
        CHECK._validate_explicit_runtime_role_bootstrap(
            model["services"]["app"],
            model["services"]["worker"],
            model["services"]["runtime-role-bootstrap"],
        )
