"""KI-21 contract: Metabase stays available but is excluded from default stacks."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEST_ENV = {
    "PATH": os.environ["PATH"],
    "HOME": os.environ.get("HOME", ""),
    "POSTGRES_PASSWORD": "compose-test-only",
    "REDIS_PASSWORD": "compose-test-only",
    "DIRECTUS_SECRET": "compose-test-only",
    "ADMIN_EMAIL": "compose-test@example.invalid",
    "ADMIN_PASSWORD": "compose-test-only",
    "KOKONUT_OPERATOR_AUTH_PASSWORD": "compose-test-only-auth-password",
    "KOKONUT_RUNTIME_PASSWORD": "compose-test-only-runtime-password",
    "CLICKHOUSE_PASSWORD": "compose-test-only",
    "CADDY_DOMAIN": "localhost",
    "PUBLIC_URL": "https://example.invalid",
    "KOKONUT_DOMAIN": "example.invalid",
    "KOKONUT_METABASE_DOMAIN": "metabase.example.invalid",
    "KOKONUT_TRAEFIK_NETWORK": "traefik",
    "KOKONUT_TLS_RESOLVER": "letsencrypt",
}


def _compose_config(
    *profiles: str,
    files: tuple[str, ...] = ("docker-compose.yml",),
    extra_env: dict[str, str] | None = None,
) -> dict:
    command = ["docker", "compose", "--env-file", "/dev/null"]
    for profile in profiles:
        command.extend(["--profile", profile])
    for compose_file in files:
        command.extend(["-f", compose_file])
    command.extend(["config", "--format", "json"])
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=TEST_ENV | (extra_env or {}),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _compose_services(*profiles: str, files: tuple[str, ...] = ("docker-compose.yml",)) -> set[str]:
    command = ["docker", "compose", "--env-file", "/dev/null"]
    for profile in profiles:
        command.extend(["--profile", profile])
    for compose_file in files:
        command.extend(["-f", compose_file])
    command.extend(["config", "--services"])
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=TEST_ENV,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return set(result.stdout.splitlines())


def test_metabase_is_excluded_from_default_compose_but_available_by_profile() -> None:
    assert "metabase" not in _compose_services()
    assert "metabase" in _compose_services("metabase")


def test_staging_keeps_metabase_opt_in_and_loopback_bound() -> None:
    staging_files = ("docker-compose.yml", "deploy/staging/docker-compose.staging.yml")
    assert "metabase" not in _compose_services(files=staging_files)

    config = _compose_config("metabase", files=staging_files)
    metabase = config["services"]["metabase"]
    assert metabase["ports"] == [
        {"host_ip": "127.0.0.1", "published": "13001", "target": 3000, "protocol": "tcp", "mode": "ingress"}
    ]


def test_production_grpc_requires_tls_and_kernel_private_profile_is_explicit() -> None:
    production = _compose_config(files=("docker-compose.yml", "docker-compose.prod.yml"))
    assert production["services"]["grpc"]["environment"]["GRPC_ALLOW_INSECURE"] == "false"

    kernel = _compose_config(
        files=("docker-compose.kernel-candidate.yml", "docker-compose.kernel-grpc.yml")
    )
    grpc = kernel["services"]["grpc"]
    assert grpc["environment"]["GRPC_ALLOW_INSECURE"] == "true"
    assert not grpc.get("ports")


def test_sandbox_keeps_seed_profile_independent_and_metabase_opt_in() -> None:
    sandbox_files = ("docker-compose.yml", "docker-compose.sandbox.yml")
    default_services = _compose_services("sandbox", files=sandbox_files)
    assert "sandbox-seed" in default_services
    assert "metabase" not in default_services

    config = _compose_config("sandbox", "metabase", files=sandbox_files)
    metabase = config["services"]["metabase"]
    assert metabase["ports"] == [
        {"host_ip": "127.0.0.1", "published": "3001", "target": 3000, "protocol": "tcp", "mode": "ingress"}
    ]


def test_production_metabase_is_opt_in_and_traefik_routed() -> None:
    production_files = (
        "docker-compose.yml",
        "docker-compose.prod.yml",
        "docker-compose.traefik.yml",
    )
    assert "metabase" not in _compose_services(files=production_files)

    metabase = _compose_config("metabase", files=production_files)["services"]["metabase"]
    assert not metabase.get("ports")
    assert "traefik.http.routers.kokonut-metabase.rule" in metabase["labels"]


def test_minimal_kernel_profile_omits_redis_and_uses_local_limiter() -> None:
    config = _compose_config(files=("docker-compose.kernel-candidate.yml",))
    assert set(config["services"]) == {"database", "app"}
    environment = config["services"]["app"]["environment"]
    assert environment["KOKONUT_RATE_LIMIT_PROVIDER"] == "local"


def test_standard_kernel_profile_defaults_to_shared_postgres_limiter() -> None:
    config = _compose_config(files=("docker-compose.kernel-candidate.yml", "docker-compose.kernel-standard.yml"))
    assert "cache" not in config["services"]
    assert "agent-summary-worker" not in config["services"]
    assert config["services"]["app"]["environment"]["KOKONUT_RATE_LIMIT_PROVIDER"] == "postgres"


def test_kernel_runtime_role_profile_has_no_orphan_agent_worker_service() -> None:
    config = _compose_config(
        "runtime-admin",
        files=("docker-compose.kernel-candidate.yml", "docker-compose.kernel-runtime-role.yml")
    )

    assert "runtime-role-bootstrap" in config["services"]
    assert "agent-summary-worker" not in config["services"]


def test_cids_export_worker_is_opt_in_and_has_no_shared_database_identity() -> None:
    files = ("docker-compose.yml", "docker-compose.worker.yml")
    assert "cids-export-worker" not in _compose_services(files=files)
    config = _compose_config("cids-export-worker", files=files)
    service = config["services"]["cids-export-worker"]

    assert service["entrypoint"] == ["python3", "-m", "services.agents.cids_agent"]
    assert service["environment"]["KOKONUT_AGENT_CIDS_SOURCE_DATABASE_URL"] == ""
    assert service["environment"]["KOKONUT_AGENT_CIDS_SOURCE_WORKER_CREDENTIAL"] == ""
    assert not any(
        name.startswith("PG_") or name == "DATABASE_URL"
        for name in service["environment"]
    )


def test_edge_kernel_profile_selects_local_private_media_and_resource_limits() -> None:
    config = _compose_config(
        files=("docker-compose.kernel-candidate.yml", "docker-compose.kernel-edge.yml"),
        extra_env={"MOBILE_MEDIA_LOCAL_KEY": "compose-test-only-key"},
    )

    assert set(config["services"]) == {"database", "app"}
    assert config["services"]["database"]["mem_limit"] == str(1024**3)
    assert config["services"]["database"]["cpus"] == 2.0
    environment = config["services"]["app"]["environment"]
    assert environment["MOBILE_MEDIA_PROVIDER"] == "local"
    assert environment["MOBILE_MEDIA_LOCAL_KEY"] == "compose-test-only-key"
    assert "kernel-private-media" in config["volumes"]


def test_analytics_kernel_profile_adds_private_clickhouse() -> None:
    config = _compose_config(files=("docker-compose.kernel-candidate.yml", "docker-compose.kernel-analytics.yml"))

    assert set(config["services"]) == {"database", "app", "clickhouse"}
    assert config["services"]["app"]["environment"]["KOKONUT_FEATURE_CLICKHOUSE"] == "true"
    assert not config["services"]["clickhouse"].get("ports")


def test_legacy_dataset_sql_override_reaches_kernel_app_and_worker_profiles() -> None:
    enabled = {
        "KOKONUT_FEATURE_LEGACY_DATASET_SQL": "true",
        "KOKONUT_ANALYTICS_USER": "kokonut_analytics_ro",
        "KOKONUT_ANALYTICS_PASSWORD": "compose-test-only-analytics-password-32",
    }

    defaults = _compose_config(files=("docker-compose.kernel-candidate.yml",))
    assert defaults["services"]["app"]["environment"]["KOKONUT_FEATURE_LEGACY_DATASET_SQL"] == "false"

    candidate = _compose_config(
        files=("docker-compose.kernel-candidate.yml",),
        extra_env=enabled,
    )
    assert candidate["services"]["app"]["environment"]["KOKONUT_FEATURE_LEGACY_DATASET_SQL"] == "true"

    standard = _compose_config(
        files=("docker-compose.kernel-candidate.yml", "docker-compose.kernel-standard.yml"),
        extra_env=enabled,
    )
    assert standard["services"]["app"]["environment"]["KOKONUT_FEATURE_LEGACY_DATASET_SQL"] == "true"
    assert standard["services"]["worker"]["environment"]["KOKONUT_FEATURE_LEGACY_DATASET_SQL"] == "true"
    assert standard["services"]["worker"]["environment"]["KOKONUT_ANALYTICS_USER"] == "kokonut_analytics_ro"
    assert (
        standard["services"]["worker"]["environment"]["KOKONUT_ANALYTICS_PASSWORD"]
        == enabled["KOKONUT_ANALYTICS_PASSWORD"]
    )

    portability = _compose_config(
        "application",
        "workers",
        files=("docker-compose.kernel-portability.yml",),
        extra_env=enabled,
    )
    assert portability["services"]["app"]["environment"]["KOKONUT_FEATURE_LEGACY_DATASET_SQL"] == "true"
    assert portability["services"]["worker"]["environment"]["KOKONUT_FEATURE_LEGACY_DATASET_SQL"] == "true"
    assert portability["services"]["worker"]["environment"]["KOKONUT_ANALYTICS_USER"] == "kokonut_analytics_ro"
    assert (
        portability["services"]["worker"]["environment"]["KOKONUT_ANALYTICS_PASSWORD"]
        == enabled["KOKONUT_ANALYTICS_PASSWORD"]
    )


def test_portability_profile_builds_images_for_selected_runtime_architecture() -> None:
    portability = _compose_config(
        "application",
        files=("docker-compose.kernel-portability.yml",),
        extra_env={"KOKONUT_DATABASE_PLATFORM": "linux/arm64"},
    )

    for service_name in ("database", "app"):
        service = portability["services"][service_name]
        assert service["platform"] == "linux/arm64"
        assert service["build"]["platforms"] == ["linux/arm64"]


def test_oidc_compose_overlay_is_opt_in_and_requires_provider_settings() -> None:
    candidate_files = ("docker-compose.kernel-candidate.yml",)
    default_app = _compose_config(files=candidate_files)["services"]["app"]
    assert "KOKONUT_OPERATOR_OIDC_ENABLED" not in default_app["environment"]

    oidc_files = (
        "docker-compose.kernel-candidate.yml",
        "docker-compose.kernel-proxy.yml",
        "docker-compose.kernel-oidc.yml",
    )
    command = ["docker", "compose", "--env-file", "/dev/null"]
    for compose_file in oidc_files:
        command.extend(["-f", compose_file])
    command.extend(["config", "--format", "json"])
    missing_issuer_env = {
        **TEST_ENV,
        "KOKONUT_OPERATOR_OIDC_CLIENT_ID": "compose-contract",
        "KOKONUT_OPERATOR_OIDC_CLIENT_SECRET": "compose-test-only",
        "KOKONUT_OPERATOR_OIDC_REDIRECT_URI": ("https://localhost:8448/operator/auth/callback"),
        "KOKONUT_OPERATOR_OIDC_STATE_SECRET": "compose-test-only-state-secret-32-bytes",
    }
    missing_issuer_env.pop("KOKONUT_OPERATOR_OIDC_ISSUER", None)
    missing_settings = subprocess.run(
        command,
        cwd=ROOT,
        env=missing_issuer_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing_settings.returncode != 0
    assert "OIDC issuer must be configured" in missing_settings.stderr

    configured = _compose_config(
        files=oidc_files,
        extra_env={
            "KOKONUT_OPERATOR_OIDC_ISSUER": "https://identity.example.invalid",
            "KOKONUT_OPERATOR_OIDC_CLIENT_ID": "compose-contract",
            "KOKONUT_OPERATOR_OIDC_CLIENT_SECRET": "compose-test-only",
            "KOKONUT_OPERATOR_OIDC_REDIRECT_URI": ("https://localhost:8448/operator/auth/callback"),
            "KOKONUT_OPERATOR_OIDC_STATE_SECRET": "compose-test-only-state-secret-32-bytes",
        },
    )
    environment = configured["services"]["app"]["environment"]
    assert environment["KOKONUT_OPERATOR_OIDC_ENABLED"] == "true"
    assert environment["KOKONUT_OPERATOR_OIDC_ISSUER"] == "https://identity.example.invalid"
    assert environment["KOKONUT_OPERATOR_OIDC_REDIRECT_URI"] == "https://localhost:8448/operator/auth/callback"


def test_metabase_profile_disables_public_sharing_and_embedding_without_secret() -> None:
    environment = _compose_config("metabase")["services"]["metabase"]["environment"]
    assert environment["MB_ENABLE_PUBLIC_SHARING"] == "false"
    assert environment["MB_ENABLE_EMBEDDING_STATIC"] == "false"
    assert "MB_ENABLE_EMBEDDING" not in environment
    assert "MB_EMBEDDING_APP_ORIGIN" not in environment
    assert "MB_EMBEDDING_SECRET_KEY" not in environment
    assert "MB_APPLICATION_ROOT" not in environment


def _run_health_check(tmp_path: Path, *, metabase_enabled: bool) -> tuple[dict, str]:
    project_dir = tmp_path / "project"
    scripts_dir = project_dir / "scripts"
    lib_dir = scripts_dir / "lib"
    bin_dir = tmp_path / "bin"
    lib_dir.mkdir(parents=True)
    bin_dir.mkdir()
    (project_dir / ".env").write_text("")

    shutil.copy2(ROOT / "scripts" / "health-check.sh", scripts_dir / "health-check.sh")
    shutil.copy2(ROOT / "scripts" / "lib" / "common.sh", lib_dir / "common.sh")

    call_log = tmp_path / "calls.log"
    stubs = {
        "curl": '#!/bin/sh\nprintf \'curl %s\\n\' "$*" >> "$HEALTH_TEST_LOG"\nexit 0\n',
        "psql": "#!/bin/sh\nexit 0\n",
        "df": (
            "#!/bin/sh\n"
            "printf 'Filesystem 1K-blocks Used Available Capacity Mounted on\\n"
            "/dev/test 100 40 60 40%% /\\n'\n"
        ),
        "docker": (
            "#!/bin/sh\n"
            'printf \'docker %s\\n\' "$*" >> "$HEALTH_TEST_LOG"\n'
            'case " $* " in\n'
            '  *" --filter "*) exit 0 ;;\n'
            "  *) printf 'database\\ndirectus\\nclickhouse\\n'; "
            'if [ "${HEALTH_CHECK_METABASE:-false}" = "true" ]; then printf \'metabase\\n\'; fi ;;\n'
            "esac\n"
            "exit 0\n"
        ),
    }
    for name, content in stubs.items():
        stub = bin_dir / name
        stub.write_text(content)
        stub.chmod(0o755)

    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "HEALTH_TEST_LOG": str(call_log),
        "HEALTH_CHECK_METABASE": "true" if metabase_enabled else "false",
        "HEALTH_CHECK_DOCKER": "true",
        "KOKONUT_ALLOW_PLAINTEXT_ENV": "true",
        "PG_PASSWORD": "test-only",
        "METABASE_URL": "http://metabase.invalid:3000",
    }
    result = subprocess.run(
        [str(scripts_dir / "health-check.sh"), "--json"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout), call_log.read_text()


def test_health_check_skips_metabase_by_default(tmp_path: Path) -> None:
    _, calls = _run_health_check(tmp_path, metabase_enabled=False)
    assert "metabase.invalid/api/health" not in calls


def test_health_check_includes_metabase_only_when_enabled(tmp_path: Path) -> None:
    _, calls = _run_health_check(tmp_path, metabase_enabled=True)
    assert "http://metabase.invalid:3000/api/health" in calls


def test_caddy_does_not_require_or_route_to_optional_metabase() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    caddy_dependencies = compose["services"]["caddy"].get("depends_on", [])
    if isinstance(caddy_dependencies, dict):
        caddy_dependencies = list(caddy_dependencies)
    assert "metabase" not in caddy_dependencies

    for filename in ("Caddyfile", "Caddyfile.production"):
        content = (ROOT / "config" / "caddy" / filename).read_text()
        assert "metabase:3000" not in content
        assert "/metabase/" not in content
