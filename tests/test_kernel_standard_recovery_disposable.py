"""Source-level safety checks for the disposable Standard recovery runner."""

from __future__ import annotations

import importlib.util
import json
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
    assert model["services"]["app"]["healthcheck"]["start_period"] == "30s"


def test_failure_diagnostics_include_container_health_probe_output(monkeypatch, tmp_path) -> None:
    manifest = tmp_path / "compose.json"
    manifest.write_text("{}", encoding="utf-8")

    def fake_run(command, **kwargs):
        if command[:2] == ["docker", "inspect"]:
            stdout = '{"Status":"unhealthy","Log":[{"ExitCode":1,"Output":"connection refused"}]}'
        elif command[-1:] == ["-q"]:
            stdout = "synthetic-container-id\n"
        else:
            stdout = ""
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(CHECK, "_run", fake_run)
    diagnostics = CHECK._failure_diagnostics(
        "kokonut-standard-recovery-test", manifest, {}
    )

    assert "Health synthetic-container-id" in diagnostics
    assert "connection refused" in diagnostics


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
    environment = CHECK._compose_environment(tmp_path, "kokonut-standard-recovery-test123")

    assert "KOKONUT_WEATHER_FORECAST_OPENWEATHERMAP_API_KEY" not in environment
    assert environment["POSTGRES_PASSWORD"] != "host-secret"
    assert environment["POSTGRES_PASSWORD"] != environment["KOKONUT_RUNTIME_PASSWORD"]
    assert environment["KOKONUT_RUNTIME_PASSWORD"] != environment["KOKONUT_OPERATOR_AUTH_PASSWORD"]
    assert environment["KOKONUT_FRESHNESS_USER"] == "kokonut_freshness_login"
    assert environment["KOKONUT_FRESHNESS_PASSWORD"] not in {
        environment["POSTGRES_PASSWORD"],
        environment["KOKONUT_RUNTIME_PASSWORD"],
        environment["KOKONUT_OPERATOR_AUTH_PASSWORD"],
        environment["KOKONUT_DIRECTUS_RUNTIME_PASSWORD"],
    }
    assert environment["KOKONUT_DIRECTUS_RUNTIME_USER"] == "kokonut_directus_runtime"
    assert environment["KOKONUT_DIRECTUS_RUNTIME_PASSWORD"] not in {
        environment["POSTGRES_PASSWORD"],
        environment["KOKONUT_RUNTIME_PASSWORD"],
    }
    assert environment["KOKONUT_KERNEL_APP_IMAGE"] == (
        "kokonut-kernel-standard-recovery:test123"
    )


def test_standard_heartbeat_path_matches_worker_profile() -> None:
    assert CHECK.HEARTBEAT_PATH == "/var/lib/kokonut/worker-progress/supervisor.json"


def test_stalled_child_probe_requires_live_pid_fails_before_db_and_restores_pulse(
    monkeypatch, tmp_path
) -> None:
    calls = []
    output = json.dumps(
        {
            "database_unavailable_during_probe": True,
            "health_state": "worker_child_stalled",
            "process_alive_during_stall": True,
            "pulse_restored": True,
            "worker": "scheduler",
        }
    )

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(CHECK, "_run", fake_run)
    result = CHECK._assert_supervised_child_stalled(
        "synthetic-standard", tmp_path / "compose.json", {"POSTGRES_PASSWORD": "unused"}
    )

    assert result == {
        "database_unavailable_during_probe": True,
        "health_state": "worker_child_stalled",
        "process_alive_during_stall": True,
        "pulse_restored": True,
        "worker": "scheduler",
    }
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[:2] == ["docker", "compose"]
    assert command[command.index("exec") + 1 : command.index("exec") + 5] == [
        "-T", "worker", "python3", "-c"
    ]
    assert kwargs["timeout"] == 45
    program = command[-1]
    assert "os.kill(pid, 0)" in program
    assert "time.monotonic_ns() - (threshold + 5)" in program
    assert 'candidate.get("state") == "worker_child_stalled"' in program
    assert 'candidate.get("supervisor", {}).get("children_alive") is True' in program
    assert 'candidate.get("workers") == {}' in program
    assert "finally:" in program
    assert 'restored["monotonic_ns"] = time.monotonic_ns()' in program


def test_stalled_child_healthcheck_stops_database_then_restores_healthy_probe(
    monkeypatch, tmp_path
) -> None:
    calls = []
    monkeypatch.setattr(
        CHECK, "_compose_command", lambda project, manifest: ["docker", "compose", "-p", project]
    )

    def fake_run(command, **kwargs):
        calls.append(("run", command))
        return subprocess.CompletedProcess(command, 0, "", "")

    def fake_assert_stalled(project, manifest, environment):
        calls.append(("stalled_probe", project))
        return {
            "database_unavailable_during_probe": True,
            "health_state": "worker_child_stalled",
            "process_alive_during_stall": True,
            "pulse_restored": True,
            "worker": "events",
        }

    def fake_wait(project, manifest, environment, service, expected, timeout):
        calls.append(("wait", service, expected))
        return {"State": {"Health": {"Status": "healthy"}}}

    def fake_worker_probe(project, manifest, environment):
        calls.append(("healthy_probe", project))
        return {
            "status": "healthy",
            "supervisor": {"children_progressing": True},
        }

    monkeypatch.setattr(CHECK, "_run", fake_run)
    monkeypatch.setattr(CHECK, "_assert_supervised_child_stalled", fake_assert_stalled)
    monkeypatch.setattr(CHECK, "_wait_for_health", fake_wait)
    monkeypatch.setattr(CHECK, "_worker_probe", fake_worker_probe)

    result = CHECK._exercise_stalled_child_healthcheck(
        "synthetic-standard", tmp_path / "compose.json", {}, timeout=90
    )

    assert [call[0] for call in calls] == [
        "run", "stalled_probe", "run", "wait", "wait", "healthy_probe"
    ]
    assert calls[0][1][-2:] == ["stop", "database"]
    assert calls[2][1][-2:] == ["start", "database"]
    assert calls[3][1:] == ("database", "healthy")
    assert calls[4][1:] == ("worker", "healthy")
    assert result == {
        "database_unavailable_during_probe": True,
        "health_state": "worker_child_stalled",
        "process_alive_during_stall": True,
        "pulse_restored": True,
        "worker": "events",
        "database_healthy_after_restore": True,
        "worker_healthy_after_restore": True,
        "health_state_after_restore": "healthy",
    }


def test_recovery_limitations_do_not_claim_task_completion_or_business_success() -> None:
    assert (
        "Child heartbeat freshness shows the supervised process is responsive, not that individual tasks completed or business work succeeded."
        in CHECK.RECOVERY_LIMITATIONS
    )
    assert not any("idle child" in item for item in CHECK.RECOVERY_LIMITATIONS)


def test_runtime_reference_read_only_boundary_checks_reads_and_table_column_writes(
    monkeypatch, tmp_path
) -> None:
    calls = []
    output = "\n".join(
        [
            "t|t|t|t|t|t|t|t|t|t|t|t|t|t|t|t",
            "bio_ingredient_composition_reference|t|f|f|f|f|f|f|t",
            "bio_regional_input_availability|t|f|f|f|f|f|f|t",
            "data_freshness_config|t|f|f|f|f|f|f|t",
            "form_of_capital|t|f|f|f|f|f|f|t",
            "location_baseline|t|f|f|f|f|f|f|t",
            "pillar_of_value|t|f|f|f|f|f|f|t",
            "quality_grade|t|f|f|f|f|f|f|t",
            "readiness_dimension|t|f|f|f|f|f|f|t",
            "regeneration_principle|t|f|f|f|f|f|f|t",
            "sdg|t|f|f|f|f|f|f|t",
            "solution|t|f|f|f|f|f|f|t",
            "solution_lifecycle_event|t|f|f|f|f|f|f|t",
            "time_delay|t|f|f|f|f|f|f|t",
            "v_public_ebf_scorecard|t|f|f|f|f|f|f|t",
            "v_public_metric_summary|t|f|f|f|f|f|f|t",
            "v_public_wellbeing_metric_summary|t|f|f|f|f|f|f|t",
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
    assert "count(*) FROM public.location_baseline" in query
    assert "count(*) FROM public.bio_ingredient_composition_reference" in query
    assert "count(*) FROM public.bio_regional_input_availability" in query
    assert "count(*) FROM public.data_freshness_config" in query
    assert "count(*) FROM public.quality_grade" in query
    assert "count(*) FROM public.readiness_dimension" in query
    assert "count(*) FROM public.v_public_ebf_scorecard" in query
    assert "count(*) FROM public.v_public_metric_summary" in query
    assert "count(*) FROM public.v_public_wellbeing_metric_summary" in query


@pytest.mark.parametrize(
    "output",
    [
        "f|t|t|t|t|t|t|t|t|t|t|t|t|t|t|t\nform_of_capital|t|f|f|f|f|f|f|t",
        "t|t|t|t|t|t|t|t|t|t|t|t|t|t|t|t\nform_of_capital|t|f|t|f|f|f|f|t",
        "t|t|t|t|t|t|t|t|t|t|t|t|t|t|t|t\nform_of_capital|t|f|f|f|f|f|f|f",
        "t|t|t|t|t|t|t|t|t|t|t|t|t|t|t|t\nform_of_capital|t|f|f|f|f|f|f|t\nsdg|t|f|f|f|f|f|f|t\ntime_delay|t|f|f|f|f|f|f|t",
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


def test_directus_reference_boundary_checks_optional_role_select_and_mutation_denials(
    monkeypatch, tmp_path
) -> None:
    calls = []
    targets = (
        "location_baseline",
        "bio_ingredient_composition_reference",
        "bio_regional_input_availability",
        "data_freshness_config",
        "quality_grade",
        "readiness_dimension",
    )
    output = "\n".join(["t"] * len(targets) + ["t|f|f|f|f|f|f|t"] * len(targets))

    def fake_run(command, **kwargs):
        calls.append(command)
        if "--no-deps" in command:
            stdout = '{"status":"provisioned"}'
        elif command[-1].startswith("SET ROLE kokonut_directus_runtime; "):
            stdout = ""
            return subprocess.CompletedProcess(command, 1, stdout, "permission denied for table probe")
        else:
            stdout = output
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(CHECK, "_run", fake_run)
    environment = CHECK._compose_environment(tmp_path, "synthetic-standard")
    provisioned = CHECK._provision_directus_runtime_role(
        "synthetic-standard", tmp_path / "compose.json", environment
    )
    CHECK._assert_directus_reference_read_only_boundary(
        "synthetic-standard", tmp_path / "compose.json", environment
    )

    assert provisioned["status"] == "provisioned"
    assert len(calls) == 2 + 4 * len(targets)
    provisioning_command = calls[0]
    assert "app" in provisioning_command
    assert "services.migration.directus_role" in provisioning_command
    assert "directus" not in CHECK._isolated_compose_model(_resolved_compose_model())["services"]
    query = calls[1][-1]
    assert "SET ROLE kokonut_directus_runtime" in query
    assert "has_table_privilege('kokonut_directus_runtime'" in query
    assert all(relation in query for relation in targets)
    assert query.count(";") == 2 + 2 * len(targets)
    assert all("kokonut_directus_runtime" in call[-1] for call in calls[2:])
    assert all(
        any(
            statement in call[-1]
            for statement in (
                "UPDATE public.",
                "INSERT INTO public.",
                "DELETE FROM public.",
                "TRUNCATE public.",
            )
        )
        for call in calls[2:]
    )


def test_directus_reference_boundary_rejects_any_mutating_effective_privilege(
    monkeypatch, tmp_path
) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            "\n".join(["t"] * 6 + ["t|f|t|f|f|f|f|t"] + ["t|f|f|f|f|f|f|t"] * 5),
            "",
        )

    monkeypatch.setattr(CHECK, "_run", fake_run)
    environment = CHECK._compose_environment(tmp_path, "synthetic-standard")
    with pytest.raises(CHECK.AcceptanceError, match="SELECT-only access"):
        CHECK._assert_directus_reference_read_only_boundary(
            "synthetic-standard", tmp_path / "compose.json", environment
        )


def test_freshness_worker_path_uses_dedicated_login_and_bounded_reader(
    monkeypatch, tmp_path
) -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "t\n0\n", "")

    monkeypatch.setattr(CHECK, "_run", fake_run)
    CHECK._assert_freshness_worker_path(
        "synthetic-standard", tmp_path / "compose.json", {}
    )

    assert len(calls) == 1
    query = calls[0][-1]
    assert "kokonut_freshness_login" in query
    assert "kokonut_security.list_freshness_configs(text)" in query
    assert "SET SESSION AUTHORIZATION kokonut_freshness_login" in query
    assert "FROM kokonut_security.list_freshness_configs(NULL)" in query
    assert "public.data_freshness_config" in query


@pytest.mark.parametrize("output", ["f\n0\n", "t\n1\n", "t\n", "t\n0\nextra\n"])
def test_freshness_worker_path_rejects_missing_role_or_function(
    monkeypatch, tmp_path, output
) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(CHECK, "_run", fake_run)
    with pytest.raises(CHECK.AcceptanceError, match="dedicated freshness login"):
        CHECK._assert_freshness_worker_path(
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
