"""Command-planner contracts for optional Kernel deployment profiles."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PLANNER = ROOT / "scripts" / "kernel-profile.py"
RECOVERY_SCRIPT = ROOT / "scripts" / "check-kernel-standard-recovery-disposable.py"
RECOVERY_SPEC = importlib.util.spec_from_file_location(
    "kernel_standard_recovery_check", RECOVERY_SCRIPT
)
assert RECOVERY_SPEC is not None and RECOVERY_SPEC.loader is not None
RECOVERY_CHECK = importlib.util.module_from_spec(RECOVERY_SPEC)
RECOVERY_SPEC.loader.exec_module(RECOVERY_CHECK)


def _run_planner(
    *arguments: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    child_env = os.environ.copy()
    if env is not None:
        child_env.update(env)
    return subprocess.run(
        [sys.executable, str(PLANNER), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=child_env,
        check=False,
    )


def test_default_profile_planner_does_not_select_optional_overlays() -> None:
    result = _run_planner("minimal")

    assert result.returncode == 0
    assert "docker-compose.kernel-proxy.yml" not in result.stdout
    assert "docker-compose.kernel-oidc.yml" not in result.stdout
    assert "--env-file /dev/null" in result.stdout


def test_standard_profile_includes_loopback_caddy_by_default() -> None:
    result = _run_planner("standard")
    command = shlex.split(result.stdout)
    manifests = [
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "-f"
    ]

    assert result.returncode == 0, result.stderr
    assert manifests.count(str(ROOT / "docker-compose.kernel-standard.yml")) == 1
    assert manifests.count(str(ROOT / "docker-compose.kernel-proxy.yml")) == 1
    assert manifests.index(str(ROOT / "docker-compose.kernel-standard.yml")) < manifests.index(
        str(ROOT / "docker-compose.kernel-proxy.yml")
    )

    proxy = yaml.safe_load((ROOT / "docker-compose.kernel-proxy.yml").read_text())
    assert proxy["services"]["proxy"]["ports"] == [
        "${KOKONUT_KERNEL_PROXY_BIND:-127.0.0.1}:${KOKONUT_KERNEL_HTTP_PORT:-8088}:80",
        "${KOKONUT_KERNEL_PROXY_BIND:-127.0.0.1}:${KOKONUT_KERNEL_HTTPS_PORT:-8448}:443",
    ]


def test_standard_profile_selects_runtime_role_after_app_and_worker_overlays() -> None:
    result = _run_planner("standard")
    command = shlex.split(result.stdout)
    manifests = [
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "-f"
    ]

    assert result.returncode == 0, result.stderr
    candidate = str(ROOT / "docker-compose.kernel-candidate.yml")
    standard = str(ROOT / "docker-compose.kernel-standard.yml")
    runtime_role = str(ROOT / "docker-compose.kernel-runtime-role.yml")
    proxy = str(ROOT / "docker-compose.kernel-proxy.yml")
    assert manifests.count(runtime_role) == 1
    assert manifests.index(candidate) < manifests.index(standard) < manifests.index(runtime_role)
    assert manifests.index(runtime_role) < manifests.index(proxy)
    assert "--profile" not in command


def test_standard_profile_can_be_replaced_by_external_ingress() -> None:
    result = _run_planner("standard", "--no-proxy")

    assert result.returncode == 0, result.stderr
    assert "docker-compose.kernel-standard.yml" in result.stdout
    assert result.stdout.count("docker-compose.kernel-runtime-role.yml") == 1
    assert "docker-compose.kernel-proxy.yml" not in result.stdout


def test_standard_oidc_can_use_an_external_https_ingress() -> None:
    result = _run_planner("standard", "--no-proxy", "--oidc")

    assert result.returncode == 0, result.stderr
    assert "docker-compose.kernel-proxy.yml" not in result.stdout
    assert result.stdout.count("docker-compose.kernel-oidc.yml") == 1


def test_standard_oidc_uses_default_proxy_without_redundant_flag() -> None:
    result = _run_planner("standard", "--oidc")

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("docker-compose.kernel-proxy.yml") == 1
    assert result.stdout.count("docker-compose.kernel-oidc.yml") == 1


@pytest.mark.parametrize(
    "options", [("--proxy", "--no-proxy"), ("--no-proxy", "--zitadel")]
)
def test_standard_no_proxy_rejects_conflicting_or_caddy_bundled_options(
    options: tuple[str, ...],
) -> None:
    result = _run_planner("standard", *options)

    assert result.returncode != 0
    assert "--no-proxy" in result.stderr or "cannot be selected together" in result.stderr


@pytest.mark.parametrize("action", ["config", "build", "up"])
def test_standard_actions_include_caddy_exactly_once(action: str) -> None:
    result = _run_planner("standard", "--action", action)

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("docker-compose.kernel-proxy.yml") == 1
    assert result.stdout.count("docker-compose.kernel-runtime-role.yml") == 1


def test_standard_runtime_role_bootstrap_is_an_explicit_one_shot_action() -> None:
    result = _run_planner("standard", "--action", "bootstrap-runtime-role")

    assert result.returncode == 0, result.stderr
    command = shlex.split(result.stdout)
    assert any(Path(value).name == "docker-compose.kernel-runtime-role.yml" for value in command)
    assert command[command.index("--profile") + 1] == "runtime-admin"
    assert command[-4:] == ["run", "--rm", "--build", "runtime-role-bootstrap"]


def test_standard_release_action_requires_digest_pinned_application_image() -> None:
    result = _run_planner(
        "standard", "--action", "release-up", env={"KOKONUT_KERNEL_APP_IMAGE": "kokonut/kernel:latest"}
    )

    assert result.returncode != 0
    assert "immutable image reference" in result.stderr


def test_standard_release_action_pulls_digest_images_and_never_builds() -> None:
    image = "ghcr.io/wasalo/kokonut-kernel@sha256:" + ("a" * 64)
    result = _run_planner(
        "standard", "--action", "release-up", env={"KOKONUT_KERNEL_APP_IMAGE": image}
    )

    assert result.returncode == 0, result.stderr
    assert " pull && " in result.stdout
    assert "up -d --no-build --wait --wait-timeout 300" in result.stdout
    assert "--build" not in result.stdout
    assert "docker-compose.kernel-standard.yml" in result.stdout
    assert image not in result.stdout


def test_standard_oidc_release_requires_its_separately_pinned_image() -> None:
    image = "ghcr.io/wasalo/kokonut-kernel@sha256:" + ("b" * 64)
    result = _run_planner(
        "standard", "--oidc", "--action", "release-up", env={"KOKONUT_KERNEL_APP_IMAGE": image}
    )

    assert result.returncode != 0
    assert "KOKONUT_KERNEL_OIDC_IMAGE" in result.stderr


def test_standard_oidc_release_uses_both_digest_pinned_images() -> None:
    image = "ghcr.io/wasalo/kokonut-kernel@sha256:" + ("b" * 64)
    oidc_image = "ghcr.io/wasalo/kokonut-kernel-oidc@sha256:" + ("c" * 64)
    result = _run_planner(
        "standard",
        "--oidc",
        "--action",
        "release-up",
        env={
            "KOKONUT_KERNEL_APP_IMAGE": image,
            "KOKONUT_KERNEL_OIDC_IMAGE": oidc_image,
        },
    )

    assert result.returncode == 0, result.stderr
    assert "docker-compose.kernel-standard.yml" in result.stdout
    assert "docker-compose.kernel-oidc.yml" in result.stdout
    assert image not in result.stdout
    assert oidc_image not in result.stdout


@pytest.mark.parametrize(
    "overlay",
    ["--grpc", "--http-sensors", "--directus", "--mqtt", "--sensor-anomaly-ml"],
)
def test_standard_release_rejects_overlays_without_release_image_contract(
    overlay: str,
) -> None:
    image = "ghcr.io/wasalo/kokonut-kernel@sha256:" + ("e" * 64)
    result = _run_planner(
        "standard",
        overlay,
        "--action",
        "release-up",
        env={"KOKONUT_KERNEL_APP_IMAGE": image},
    )

    assert result.returncode != 0
    assert "does not yet publish immutable images" in result.stderr


def test_standard_zitadel_release_rejects_mutable_image_override() -> None:
    image = "ghcr.io/wasalo/kokonut-kernel@sha256:" + ("f" * 64)
    result = _run_planner(
        "standard",
        "--zitadel",
        "--action",
        "release-up",
        env={
            "KOKONUT_KERNEL_APP_IMAGE": image,
            "KOKONUT_KERNEL_OIDC_IMAGE": image,
            "KOKONUT_ZITADEL_API_IMAGE": "ghcr.io/zitadel/zitadel:latest",
        },
    )

    assert result.returncode != 0
    assert "KOKONUT_ZITADEL_API_IMAGE" in result.stderr


def test_standard_zitadel_release_accepts_only_digest_pinned_image_overrides() -> None:
    image = "ghcr.io/wasalo/kokonut-kernel@sha256:" + ("1" * 64)
    postgres_image = "postgres:17.10-alpine@sha256:" + ("2" * 64)
    api_image = "ghcr.io/zitadel/zitadel:v4.19.4@sha256:" + ("3" * 64)
    login_image = "ghcr.io/zitadel/zitadel-login:v4.19.4@sha256:" + ("4" * 64)
    result = _run_planner(
        "standard",
        "--zitadel",
        "--action",
        "release-up",
        env={
            "KOKONUT_KERNEL_APP_IMAGE": image,
            "KOKONUT_KERNEL_OIDC_IMAGE": image,
            "KOKONUT_ZITADEL_POSTGRES_IMAGE": postgres_image,
            "KOKONUT_ZITADEL_API_IMAGE": api_image,
            "KOKONUT_ZITADEL_LOGIN_IMAGE": login_image,
        },
    )

    assert result.returncode == 0, result.stderr
    assert "zitadel" in result.stdout


def test_standard_zitadel_default_images_are_digest_pinned() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.kernel-zitadel.yml").read_text())

    for service_name in ("zitadel-db", "zitadel-bootstrap-permissions", "zitadel-api", "zitadel-login"):
        image = compose["services"][service_name]["image"]
        assert "@sha256:" in image


def test_standard_source_build_rejects_an_accidentally_selected_release_digest() -> None:
    image = "ghcr.io/wasalo/kokonut-kernel@sha256:" + ("d" * 64)
    result = _run_planner("standard", "--action", "up", env={"KOKONUT_KERNEL_APP_IMAGE": image})

    assert result.returncode != 0
    assert "source-built local images" in result.stderr


def test_compose_profile_tags_application_and_worker_to_the_same_default_image() -> None:
    candidate = yaml.safe_load((ROOT / "docker-compose.kernel-candidate.yml").read_text())
    standard = yaml.safe_load((ROOT / "docker-compose.kernel-standard.yml").read_text())

    expected = "${KOKONUT_KERNEL_APP_IMAGE:-kokonut-kernel-candidate:local}"
    assert candidate["services"]["app"]["image"] == expected
    assert standard["services"]["worker"]["image"] == expected


def test_oidc_compose_profile_uses_a_distinct_release_image_from_the_base() -> None:
    oidc = yaml.safe_load((ROOT / "docker-compose.kernel-oidc.yml").read_text())

    assert oidc["services"]["app"]["image"] == "${KOKONUT_KERNEL_OIDC_IMAGE:-kokonut-kernel-oidc:local}"


def test_standard_database_up_action_starts_only_the_database() -> None:
    result = _run_planner("standard", "--action", "database-up")

    assert result.returncode == 0, result.stderr
    assert shlex.split(result.stdout)[-3:] == ["up", "-d", "database"]


def test_standard_migrate_action_prints_ordered_schema_only_runner() -> None:
    result = _run_planner("standard", "--action", "migrate")

    assert result.returncode == 0, result.stderr
    command = shlex.split(result.stdout)
    assert command[:5] == [
        "python3", "-m", "services.migration", "migrate", "--schemas-only"
    ]
    assert command[command.index("--compose-project") + 1] == "kokonut-kernel-candidate"
    compose_files = [
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "--compose-file"
    ]
    assert [Path(value).name for value in compose_files] == [
        "docker-compose.kernel-candidate.yml",
        "docker-compose.kernel-standard.yml",
        "docker-compose.kernel-runtime-role.yml",
        "docker-compose.kernel-proxy.yml",
    ]


@pytest.mark.parametrize("action", ["database-up", "migrate", "bootstrap-runtime-role"])
def test_standard_admin_actions_are_rejected_for_other_profiles(action: str) -> None:
    result = _run_planner("minimal", "--action", action)

    assert result.returncode != 0
    assert f"--action {action} applies only to standard" in result.stderr


def test_minimal_and_edge_keep_proxy_opt_in() -> None:
    for profile in ("minimal", "edge"):
        result = _run_planner(profile)

        assert result.returncode == 0, result.stderr
        assert "docker-compose.kernel-proxy.yml" not in result.stdout


def test_explicit_project_is_used_for_an_isolated_zitadel_plan() -> None:
    result = _run_planner("minimal", "--zitadel", "--project", "kokonut-sprint-123")

    assert result.returncode == 0, result.stderr
    command = shlex.split(result.stdout)
    assert command[command.index("-p") + 1] == "kokonut-sprint-123"
    assert "kokonut-kernel-candidate" not in command


@pytest.mark.parametrize("project", ["UPPER", "-bad", "bad.name", "x" * 64])
def test_invalid_project_name_is_rejected(project: str) -> None:
    result = _run_planner("minimal", f"--project={project}")

    assert result.returncode != 0
    assert "--project must be" in result.stderr


def test_default_projects_remain_unchanged_for_both_architectures() -> None:
    amd64 = shlex.split(_run_planner("minimal").stdout)
    arm64 = shlex.split(_run_planner("minimal", "--target-platform", "linux/arm64").stdout)

    assert amd64[amd64.index("-p") + 1] == "kokonut-kernel-candidate"
    assert arm64[arm64.index("-p") + 1] == "kokonut-kernel-candidate-arm64"


def test_core_profile_is_opt_in_and_selects_the_separate_lean_image() -> None:
    minimal = shlex.split(_run_planner("minimal").stdout)
    core = _run_planner("core")

    assert core.returncode == 0, core.stderr
    assert "docker-compose.kernel-core.yml" not in minimal
    assert "docker-compose.kernel-core.yml" in core.stdout
    minimal_compose = yaml.safe_load((ROOT / "docker-compose.kernel-candidate.yml").read_text())
    assert "target" not in minimal_compose["services"]["app"]["build"]
    assert "FROM kernel-base AS kernel" in (ROOT / "Dockerfile.kernel").read_text()
    overlay = yaml.safe_load((ROOT / "docker-compose.kernel-core.yml").read_text())
    assert overlay["services"]["app"]["build"]["target"] == "kernel-core"
    assert overlay["services"]["app"]["build"]["args"] == {
        "KOKONUT_CORE_WEB3": "false",
        "KOKONUT_CORE_EXPORTS": "false",
        "KOKONUT_CORE_LOCAL_MEDIA": "false",
    }


def test_core_capabilities_are_explicit_build_overlays() -> None:
    result = _run_planner("core", "--web3", "--exports", "--local-media")

    assert result.returncode == 0, result.stderr
    for overlay in (
        "docker-compose.kernel-core.yml",
        "docker-compose.kernel-core-web3.yml",
        "docker-compose.kernel-core-exports.yml",
        "docker-compose.kernel-core-local-media.yml",
    ):
        assert overlay in result.stdout
    web3 = yaml.safe_load((ROOT / "docker-compose.kernel-core-web3.yml").read_text())
    exports = yaml.safe_load((ROOT / "docker-compose.kernel-core-exports.yml").read_text())
    media = yaml.safe_load((ROOT / "docker-compose.kernel-core-local-media.yml").read_text())
    assert web3["services"]["app"]["build"]["args"]["KOKONUT_CORE_WEB3"] == "true"
    assert exports["services"]["app"]["build"]["args"]["KOKONUT_CORE_EXPORTS"] == "true"
    assert media["services"]["app"]["build"]["args"]["KOKONUT_CORE_LOCAL_MEDIA"] == "true"
    assert "${MOBILE_MEDIA_LOCAL_KEY:?" in media["services"]["app"]["environment"]["MOBILE_MEDIA_LOCAL_KEY"]
    assert "MOBILE_MEDIA_LOCAL_KEY" not in (ROOT / "Dockerfile.kernel").read_text()


@pytest.mark.parametrize("overlay", ["--web3", "--exports", "--local-media"])
@pytest.mark.parametrize("profile", ["minimal", "edge", "standard", "analytics"])
def test_core_package_overlays_cannot_be_selected_on_existing_profiles(
    profile: str, overlay: str,
) -> None:
    result = _run_planner(profile, overlay)

    assert result.returncode != 0
    assert "apply only to the core profile" in result.stderr


@pytest.mark.parametrize("option", ["--oidc", "--zitadel"])
def test_core_profile_rejects_full_oidc_application_target(option: str) -> None:
    result = _run_planner("core", option)

    assert result.returncode != 0
    assert "select the full OIDC image" in result.stderr


def test_core_profile_uses_the_arm64_candidate_project_and_overlay() -> None:
    result = _run_planner("core", "--target-platform", "linux/arm64")

    assert result.returncode == 0, result.stderr
    assert "kokonut-kernel-candidate-arm64" in result.stdout
    assert "docker-compose.kernel-arm64.yml" in result.stdout
    assert "docker-compose.kernel-core.yml" in result.stdout


def test_core_arm64_capability_overlays_select_the_multiarch_verified_composition() -> None:
    result = _run_planner(
        "core", "--target-platform", "linux/arm64", "--web3", "--exports", "--local-media"
    )

    assert result.returncode == 0, result.stderr
    for filename in (
        "docker-compose.kernel-core-web3.yml",
        "docker-compose.kernel-core-exports.yml",
        "docker-compose.kernel-core-local-media.yml",
        "docker-compose.kernel-arm64.yml",
    ):
        assert filename in result.stdout


def test_default_and_oidc_kernel_runtime_commands_require_schema_readiness() -> None:
    dockerfile = (ROOT / "Dockerfile.kernel").read_text()
    runtime_commands = [line for line in dockerfile.splitlines() if line.startswith("CMD ")
                       and "services.core.runtime" in line]

    assert len(runtime_commands) == 3
    assert all("--require-schema" in command for command in runtime_commands)


def test_oidc_image_installs_authlibs_shared_http_client_dependency() -> None:
    dockerfile = (ROOT / "Dockerfile.kernel").read_text()
    oidc_target = dockerfile.split("FROM kernel-base AS oidc", maxsplit=1)[1].split(
        "FROM --platform=$BUILDPLATFORM", maxsplit=1
    )[0]
    oidc_requirements = (ROOT / "requirements" / "oidc.txt").read_text()
    http_client_requirements = (ROOT / "requirements" / "http-client.txt").read_text()

    assert "authlib" in oidc_requirements
    assert "httpx2" in http_client_requirements
    assert "COPY requirements/oidc.txt requirements/http-client.txt" in oidc_target
    assert "-r requirements/oidc.txt -r requirements/http-client.txt" in oidc_target


def test_standard_api_and_worker_require_schema_readiness() -> None:
    standard = yaml.safe_load((ROOT / "docker-compose.kernel-standard.yml").read_text())

    for service_name in ("app", "worker"):
        command = standard["services"][service_name]["command"]
        assert "--require-schema" in command
        assert "--require-runtime-role" in command


def test_standard_compose_keeps_notification_secrets_on_delivery_worker_only() -> None:
    candidate = yaml.safe_load((ROOT / "docker-compose.kernel-candidate.yml").read_text())
    standard = yaml.safe_load((ROOT / "docker-compose.kernel-standard.yml").read_text())
    runtime_role = yaml.safe_load((ROOT / "docker-compose.kernel-runtime-role.yml").read_text())

    # Model Compose's map merge for the candidate, Standard, and runtime-role
    # overlays. Empty Standard values clear inherited candidate credentials.
    app_environment = {
        **candidate["services"]["app"].get("environment", {}),
        **standard["services"]["app"].get("environment", {}),
        **runtime_role["services"]["app"].get("environment", {}),
    }
    worker_environment = {
        **standard["services"]["worker"].get("environment", {}),
        **runtime_role["services"]["worker"].get("environment", {}),
    }

    assert app_environment["ALERT_SMTP_USER"] == ""
    assert app_environment["ALERT_SMTP_PASSWORD"] == ""
    assert app_environment["ALERT_WEBHOOK_URL"] == ""
    assert app_environment["KOKONUT_NOTIFICATION_WEBHOOK_CONFIGURED"] == (
        "${ALERT_WEBHOOK_URL:+true}"
    )
    assert worker_environment["ALERT_SMTP_USER"] == "${ALERT_SMTP_USER:-}"
    assert worker_environment["ALERT_SMTP_PASSWORD"] == "${ALERT_SMTP_PASSWORD:-}"
    assert worker_environment["ALERT_WEBHOOK_URL"] == "${ALERT_WEBHOOK_URL:-}"

    # The event producer keeps non-secret channel/routing settings needed to
    # enqueue intents; the worker keeps those settings plus SMTP credentials.
    smtp_configuration = (
        "ALERT_SMTP_HOST",
        "ALERT_SMTP_PORT",
        "ALERT_SMTP_TLS_MODE",
        "ALERT_EMAIL_FROM",
        "ALERT_EMAIL_TO",
    )
    for key in smtp_configuration:
        assert app_environment[key] == standard["services"]["app"]["environment"][key]
    for key in smtp_configuration:
        assert worker_environment[key] == standard["services"]["worker"]["environment"][key]


def test_standard_resolved_compose_keeps_notification_secrets_on_delivery_worker() -> None:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("Docker CLI is required to resolve the Standard Compose model")

    environment = {
        "HOME": str(Path.home()),
        "PATH": os.environ.get("PATH", ""),
        "POSTGRES_PASSWORD": "synthetic-postgres-password",
        "KOKONUT_RUNTIME_USER": "kokonut_runtime",
        "KOKONUT_RUNTIME_PASSWORD": "synthetic-runtime-password",
        "KOKONUT_OPERATOR_AUTH_PASSWORD": "synthetic-operator-password",
        "ALERT_SMTP_USER": "synthetic-smtp-user",
        "ALERT_SMTP_PASSWORD": "synthetic-smtp-password",
        "ALERT_SMTP_HOST": "smtp.example.test",
        "ALERT_EMAIL_TO": "ops@example.test",
        "ALERT_WEBHOOK_URL": "https://hooks.example.test/synthetic-token",
    }
    command = [
        docker,
        "compose",
        "--env-file",
        os.devnull,
        "-f",
        "docker-compose.kernel-candidate.yml",
        "-f",
        "docker-compose.kernel-standard.yml",
        "-f",
        "docker-compose.kernel-runtime-role.yml",
        "-f",
        "docker-compose.kernel-proxy.yml",
        "config",
        "--format",
        "json",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    model = json.loads(result.stdout)
    app_environment = model["services"]["app"]["environment"]
    worker_environment = model["services"]["worker"]["environment"]

    assert app_environment["ALERT_SMTP_USER"] == ""
    assert app_environment["ALERT_SMTP_PASSWORD"] == ""
    assert app_environment["ALERT_WEBHOOK_URL"] == ""
    assert app_environment["KOKONUT_NOTIFICATION_WEBHOOK_CONFIGURED"] == "true"
    assert worker_environment["ALERT_SMTP_USER"] == "synthetic-smtp-user"
    assert worker_environment["ALERT_SMTP_PASSWORD"] == "synthetic-smtp-password"
    assert worker_environment["ALERT_WEBHOOK_URL"] == environment["ALERT_WEBHOOK_URL"]
    assert environment["ALERT_WEBHOOK_URL"] not in json.dumps(model["services"]["app"])


def test_standard_worker_uses_durable_progress_healthcheck_without_merging_roles() -> None:
    standard = yaml.safe_load((ROOT / "docker-compose.kernel-standard.yml").read_text())
    app = standard["services"]["app"]
    worker = standard["services"]["worker"]

    assert worker["healthcheck"] == {
        "test": ["CMD", "python3", "-m", "services.core.worker_progress", "--check"],
        "interval": "30s",
        "timeout": "5s",
        "retries": 3,
        "start_period": "60s",
    }
    assert worker["command"] == [
        "python3", "-m", "services.core.runtime", "--workers-only", "--require-schema",
        "--require-runtime-role",
    ]
    assert worker["environment"]["KOKONUT_WORKER_PROGRESS_STALE_SECONDS"] == (
        "${KOKONUT_WORKER_PROGRESS_STALE_SECONDS:-300}"
    )
    assert worker["environment"]["KOKONUT_WORKER_PROGRESS_BACKLOG_SECONDS"] == (
        "${KOKONUT_WORKER_PROGRESS_BACKLOG_SECONDS:-900}"
    )
    assert worker["environment"]["KOKONUT_WORKER_PROGRESS_HEARTBEAT_SECONDS"] == (
        "${KOKONUT_WORKER_PROGRESS_HEARTBEAT_SECONDS:-60}"
    )
    assert worker["environment"]["KOKONUT_WORKER_PROGRESS_HEARTBEAT_FILE"] == (
        "/var/lib/kokonut/worker-progress/supervisor.json"
    )
    assert all(
        "/tmp/kokonut-worker-progress" not in str(mount)
        for mount in worker.get("volumes", [])
    )
    assert "KOKONUT_WORKER_PROGRESS_STALE_SECONDS" not in app.get("environment", {})
    assert worker["environment"]["PG_USER"] == "${KOKONUT_RUNTIME_USER:?KOKONUT_RUNTIME_USER must be set}"


def test_clickhouse_outbox_isolation_is_wired_but_opt_in_across_kernel_profiles():
    profile_files = (
        "docker-compose.kernel-candidate.yml",
        "docker-compose.kernel-standard.yml",
        "docker-compose.kernel-portability.yml",
        "docker-compose.worker.yml",
    )
    for filename in profile_files:
        source = (ROOT / filename).read_text()
        assert "KOKONUT_CLICKHOUSE_OUTBOX_DATABASE_URL" in source
        assert "KOKONUT_FEATURE_ISOLATED_CLICKHOUSE_OUTBOX_WORKER" in source
        assert "${KOKONUT_FEATURE_ISOLATED_CLICKHOUSE_OUTBOX_WORKER:-false}" in source

    runtime_role = yaml.safe_load(
        (ROOT / "docker-compose.kernel-runtime-role.yml").read_text()
    )
    environment = runtime_role["services"]["runtime-role-bootstrap"]["environment"]
    assert "KOKONUT_CLICKHOUSE_OUTBOX_USER" in environment
    assert "KOKONUT_CLICKHOUSE_OUTBOX_PASSWORD" in environment


def test_isolated_notification_worker_has_no_shared_database_environment():
    compose = yaml.safe_load((ROOT / "docker-compose.worker.yml").read_text())
    service = compose["services"]["notification-kernel-worker"]
    assert service["command"][:4] == [
        "python3", "-m", "services.events", "--isolated-notification-worker"
    ]
    assert service["profiles"] == ["notification-isolated"]
    assert "KOKONUT_NOTIFICATION_DELIVERY_DATABASE_URL" in service["environment"]
    assert "PG_USER" not in service["environment"]
    assert "PG_PASSWORD" not in service["environment"]
    assert "POSTGRES_PASSWORD" not in service["environment"]
    runtime_role = yaml.safe_load(
        (ROOT / "docker-compose.kernel-runtime-role.yml").read_text()
    )
    bootstrap = runtime_role["services"]["runtime-role-bootstrap"]["environment"]
    assert "KOKONUT_NOTIFICATION_DELIVERY_USER" in bootstrap
    assert "KOKONUT_NOTIFICATION_DELIVERY_PASSWORD" in bootstrap


def test_oidc_profile_requires_https_proxy_overlay() -> None:
    result = _run_planner("minimal", "--oidc")

    assert result.returncode != 0
    assert "--oidc requires --proxy" in result.stderr


def test_oidc_profile_plans_candidate_proxy_and_oidc_manifests() -> None:
    result = _run_planner("standard", "--proxy", "--oidc")

    assert result.returncode == 0
    assert "docker-compose.kernel-candidate.yml" in result.stdout
    assert "docker-compose.kernel-standard.yml" in result.stdout
    assert "docker-compose.kernel-proxy.yml" in result.stdout
    assert "docker-compose.kernel-oidc.yml" in result.stdout
    assert "up -d" not in result.stdout


def test_zitadel_option_selects_provider_client_and_https_proxy_together() -> None:
    result = _run_planner("minimal", "--zitadel")

    assert result.returncode == 0
    assert "docker-compose.kernel-proxy.yml" in result.stdout
    assert "docker-compose.kernel-oidc.yml" in result.stdout
    assert "docker-compose.kernel-zitadel.yml" in result.stdout
    assert result.stdout.index("docker-compose.kernel-proxy.yml") < result.stdout.index(
        "docker-compose.kernel-zitadel.yml"
    )


def test_zitadel_option_does_not_duplicate_explicit_proxy_or_oidc_overlays() -> None:
    result = _run_planner("minimal", "--proxy", "--oidc", "--zitadel")

    assert result.returncode == 0
    assert result.stdout.count("docker-compose.kernel-proxy.yml") == 1
    assert result.stdout.count("docker-compose.kernel-oidc.yml") == 1
    assert result.stdout.count("docker-compose.kernel-zitadel.yml") == 1


def test_arm64_zitadel_profile_selects_pinned_architecture_overlays() -> None:
    result = _run_planner("minimal", "--target-platform", "linux/arm64", "--zitadel")

    assert result.returncode == 0
    assert "docker-compose.kernel-arm64.yml" in result.stdout
    assert "docker-compose.kernel-arm64-proxy.yml" in result.stdout
    assert "docker-compose.kernel-arm64-zitadel.yml" in result.stdout
    assert result.stdout.index("docker-compose.kernel-zitadel.yml") < result.stdout.index(
        "docker-compose.kernel-arm64-zitadel.yml"
    )


def test_arm64_external_oidc_requires_verified_proxy_and_selects_platform_overlay() -> None:
    result = _run_planner(
        "standard", "--target-platform", "linux/arm64", "--proxy", "--oidc",
    )

    assert result.returncode == 0
    assert "docker-compose.kernel-arm64-proxy.yml" in result.stdout
    assert "docker-compose.kernel-arm64-zitadel.yml" not in result.stdout


def test_arm64_transport_profiles_select_explicit_architecture_overlays() -> None:
    grpc = _run_planner("minimal", "--target-platform", "linux/arm64", "--grpc")
    mqtt = _run_planner("edge", "--target-platform", "linux/arm64", "--mqtt")
    http_sensors = _run_planner(
        "minimal", "--target-platform", "linux/arm64", "--http-sensors"
    )

    assert grpc.returncode == 0
    assert "docker-compose.kernel-grpc.yml" in grpc.stdout
    assert "docker-compose.kernel-arm64-grpc.yml" in grpc.stdout
    assert mqtt.returncode == 0
    assert "docker-compose.kernel-mqtt.yml" in mqtt.stdout
    assert "docker-compose.kernel-arm64-mqtt.yml" in mqtt.stdout
    assert http_sensors.returncode == 0
    assert "docker-compose.kernel-http-sensors.yml" in http_sensors.stdout
    assert "docker-compose.kernel-arm64-http-sensors.yml" in http_sensors.stdout


def test_arm64_directus_selects_its_platform_overlay() -> None:
    directus = _run_planner("minimal", "--target-platform", "linux/arm64", "--directus")

    assert directus.returncode == 0
    assert "docker-compose.kernel-directus.yml" in directus.stdout
    assert "docker-compose.kernel-arm64-directus.yml" in directus.stdout


def test_sensor_anomaly_ml_is_an_explicit_single_location_worker_profile() -> None:
    compose = yaml.safe_load(
        (ROOT / "docker-compose.kernel-sensor-anomaly-ml.yml").read_text()
    )
    worker = compose["services"]["sensor-anomaly-ml-worker"]
    assert worker["profiles"] == ["sensor-anomaly-ml"]
    assert worker["build"]["target"] == "ml-anomaly"
    assert worker["command"] == [
        "python3", "-m", "services.ingestion.sensor_anomaly_ml_cli"
    ]
    assert "KOKONUT_SENSOR_ANOMALY_ML_SOURCE_DATABASE_URL" in worker["environment"]
    assert "KOKONUT_SENSOR_ANOMALY_ML_SOURCE_WORKER_CREDENTIAL" in worker["environment"]
    assert "PG_USER" not in worker["environment"]
    assert "PG_PASSWORD" not in worker["environment"]
    assert "POSTGRES_PASSWORD" not in worker["environment"]

    dockerfile = (ROOT / "Dockerfile.kernel").read_text()
    assert "AS ml-anomaly" in dockerfile
    assert "FROM python:3.11-slim@sha256:" in dockerfile.split("AS ml-anomaly", 1)[1]
    assert "FROM kernel-base AS ml-anomaly" not in dockerfile
    assert "ml-anomaly-runtime.in" in dockerfile
    assert 'CMD ["python3", "-m", "services.ingestion.sensor_anomaly_ml_cli"]' in dockerfile
    assert "AS ml-anomaly-dependencies" in dockerfile
    assert "--platform=$BUILDPLATFORM" in dockerfile
    assert "ARG TARGETARCH" in dockerfile
    assert "--only-binary=:all:" in dockerfile
    assert "--require-hashes" in dockerfile
    assert "-r requirements/ml-anomaly-runtime.lock" in dockerfile
    assert "-r requirements/ml-anomaly-runtime.in" not in dockerfile
    assert "--platform=manylinux_2_28_aarch64" in dockerfile
    assert "--platform=manylinux_2_28_x86_64" in dockerfile
    assert "COPY --from=ml-anomaly-dependencies" in dockerfile

    ml_requirements = {
        line.strip()
        for line in (ROOT / "requirements/ml-anomaly.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert ml_requirements == {
        "pandas>=2.0,<4.0",
        "numpy>=1.26,<2.0",
        "prophet>=1.3.0,<2.0",
        "scikit-learn>=1.9,<2.0",
        "scipy>=1.11,<2.0.0",
    }
    assert "yfinance>=1.0.0,<2.0.0" not in ml_requirements
    assert "gstools>=1.6.0,<2.0.0" not in ml_requirements

    ml_runtime = (ROOT / "requirements/ml-anomaly-runtime.in").read_text()
    assert "-r ml-anomaly.txt" in ml_runtime
    assert "psycopg2-binary>=2.9.12,<3.0.0" in ml_runtime

    ml_lock = (ROOT / "requirements/ml-anomaly-runtime.lock").read_text()
    assert "# binary wheels selected for Linux AMD64 and ARM64" in ml_lock
    assert "numpy==1.26.4" in ml_lock
    assert "--hash=sha256:" in ml_lock

    plan = _run_planner("standard", "--sensor-anomaly-ml")
    assert plan.returncode == 0
    assert "docker-compose.kernel-sensor-anomaly-ml.yml" in plan.stdout


def test_arm64_sensor_anomaly_ml_profile_selects_architecture_overlay() -> None:
    plan = _run_planner(
        "standard", "--target-platform", "linux/arm64", "--sensor-anomaly-ml"
    )

    assert plan.returncode == 0
    assert "docker-compose.kernel-sensor-anomaly-ml.yml" in plan.stdout
    assert "docker-compose.kernel-arm64-sensor-anomaly-ml.yml" in plan.stdout


def test_arm64_analytics_selects_clickhouse_and_worker_platform_overlays() -> None:
    analytics = _run_planner("analytics", "--target-platform", "linux/arm64")
    separate = _run_planner(
        "analytics", "--target-platform", "linux/arm64", "--separate-workers"
    )

    assert analytics.returncode == 0
    assert "docker-compose.kernel-analytics.yml" in analytics.stdout
    assert "docker-compose.kernel-arm64-analytics.yml" in analytics.stdout
    assert separate.returncode == 0
    assert "docker-compose.kernel-standard-analytics.yml" in separate.stdout
    assert "docker-compose.kernel-arm64-standard.yml" in separate.stdout


def test_directus_option_selects_only_the_optional_directus_overlay() -> None:
    result = _run_planner("minimal", "--directus")

    assert result.returncode == 0
    assert "docker-compose.kernel-directus.yml" in result.stdout
    assert "docker-compose.kernel-proxy.yml" not in result.stdout
    assert "docker-compose.kernel-zitadel.yml" not in result.stdout


def test_arm64_planner_rejects_scale_profile() -> None:
    scale = _run_planner("scale", "--target-platform", "linux/arm64")
    assert scale.returncode != 0
    assert "only core, minimal, edge, standard, and analytics profiles" in scale.stderr


def test_profile_planner_selects_isolated_arm64_images_for_edge() -> None:
    result = _run_planner("edge", "--target-platform", "linux/arm64")

    assert result.returncode == 0
    assert "docker-compose.kernel-arm64.yml" in result.stdout
    assert "kokonut-kernel-candidate-arm64" in result.stdout
    assert "docker-compose.kernel-edge.yml" in result.stdout


def test_edge_profile_has_explicit_memory_and_cpu_caps_for_both_services() -> None:
    """Keep the edge profile's declared resource envelope reviewable offline."""
    edge = yaml.safe_load((ROOT / "docker-compose.kernel-edge.yml").read_text())

    assert set(edge["services"]) == {"database", "app"}
    for service in edge["services"].values():
        assert service["mem_limit"] == "1g"
        assert service["cpus"] == 2.0


def test_standard_arm64_profile_selects_the_arm64_worker_override() -> None:
    result = _run_planner("standard", "--target-platform", "linux/arm64")

    assert result.returncode == 0
    assert "docker-compose.kernel-standard.yml" in result.stdout
    assert "docker-compose.kernel-runtime-role.yml" in result.stdout
    assert "docker-compose.kernel-arm64.yml" in result.stdout
    assert "docker-compose.kernel-arm64-standard.yml" in result.stdout


def test_arm64_analytics_and_directus_profiles_select_verified_overlays() -> None:
    analytics = _run_planner("analytics", "--target-platform", "linux/arm64")
    directus = _run_planner("minimal", "--target-platform", "linux/arm64", "--directus")

    assert analytics.returncode == 0
    assert "docker-compose.kernel-arm64-analytics.yml" in analytics.stdout
    assert directus.returncode == 0
    assert "docker-compose.kernel-arm64-directus.yml" in directus.stdout


def test_arm64_identity_overlays_pin_each_supported_service_architecture() -> None:
    proxy = yaml.safe_load((ROOT / "docker-compose.kernel-arm64-proxy.yml").read_text())
    zitadel = yaml.safe_load((ROOT / "docker-compose.kernel-arm64-zitadel.yml").read_text())
    provider = yaml.safe_load((ROOT / "docker-compose.kernel-zitadel.yml").read_text())

    assert proxy["services"]["proxy"]["platform"] == "linux/arm64"
    assert set(zitadel["services"]) == {
        "zitadel-db", "zitadel-api", "zitadel-login", "zitadel-bootstrap-permissions"
    }
    assert all(service["platform"] == "linux/arm64" for service in zitadel["services"].values())
    assert "postgres:17.10-alpine@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193" in provider[
        "services"
    ]["zitadel-db"]["image"]


def test_arm64_transport_overlays_force_platform_for_all_selected_services() -> None:
    grpc = yaml.safe_load((ROOT / "docker-compose.kernel-arm64-grpc.yml").read_text())
    mqtt = yaml.safe_load((ROOT / "docker-compose.kernel-arm64-mqtt.yml").read_text())
    mqtt_profile = yaml.safe_load((ROOT / "docker-compose.kernel-mqtt.yml").read_text())
    http_sensors = yaml.safe_load(
        (ROOT / "docker-compose.kernel-arm64-http-sensors.yml").read_text()
    )
    directus = yaml.safe_load((ROOT / "docker-compose.kernel-arm64-directus.yml").read_text())
    analytics = yaml.safe_load(
        (ROOT / "docker-compose.kernel-arm64-analytics.yml").read_text()
    )
    directus_profile = yaml.safe_load((ROOT / "docker-compose.kernel-directus.yml").read_text())

    assert grpc["services"]["grpc"]["platform"] == "linux/arm64"
    assert set(mqtt["services"]) == {"mosquitto", "mqtt-subscriber"}
    assert all(service["platform"] == "linux/arm64" for service in mqtt["services"].values())
    assert "sha256:6f8d8a947c506f8a2290ec65cd4bd2bc7cb4d43fb5f6271f861cb013e2ef9797" in mqtt_profile[
        "services"
    ]["mosquitto"]["image"]
    assert http_sensors["services"]["http-sensors"]["platform"] == "linux/arm64"
    assert set(directus["services"]) == {
        "directus-role-bootstrap",
        "directus-bootstrap",
        "directus",
    }
    assert all(service["platform"] == "linux/arm64" for service in directus["services"].values())
    assert "sha256:27fd291463f4e746a7911139377a1dbc7a5c09ae82ee15b028b97bcc4950c69d" in directus_profile[
        "services"
    ]["directus"]["image"]
    assert analytics["services"]["clickhouse"]["platform"] == "linux/arm64"


def test_arm64_overlay_pins_platform_package_versions_and_worker_profile() -> None:
    overlay = yaml.safe_load((ROOT / "docker-compose.kernel-arm64.yml").read_text())

    database = overlay["services"]["database"]
    assert database["platform"] == "linux/arm64"
    assert database["build"]["dockerfile"] == "Dockerfile.kernel-postgis"
    assert database["build"]["platforms"] == ["linux/arm64"]
    assert database["build"]["args"]["POSTGIS_PACKAGE_VERSION"] == "3.6.4+dfsg-2.pgdg12+1"
    assert database["build"]["args"]["POSTGIS_SCRIPTS_VERSION"] == "3.6.4+dfsg-2.pgdg12+1"
    assert overlay["services"]["app"]["build"]["platforms"] == ["linux/arm64"]
    standard = yaml.safe_load((ROOT / "docker-compose.kernel-arm64-standard.yml").read_text())
    assert standard["services"]["worker"]["platform"] == "linux/arm64"
    assert standard["services"]["worker"]["build"]["platforms"] == ["linux/arm64"]


def test_standard_recovery_uses_content_verified_ordered_schema_snapshot(tmp_path) -> None:
    source = tmp_path / "source"
    snapshot = tmp_path / "snapshot"
    source.mkdir()
    (source / "717_last.sql").write_text("SELECT 717;", encoding="utf-8")
    (source / "10_tenth.sql").write_text("SELECT 10;", encoding="utf-8")
    (source / "2_second.sql").write_text("SELECT 2;", encoding="utf-8")
    (source / "not-a-migration.sql").write_text("ignored", encoding="utf-8")

    files, manifest_digest = RECOVERY_CHECK._snapshot_schema_migrations(source, snapshot)

    assert [path.name for path in files] == ["2_second.sql", "10_tenth.sql", "717_last.sql"]
    expected_manifest = "\n".join(
        f"{name}\t{hashlib.sha256(content).hexdigest()}"
        for name, content in (
            ("2_second.sql", b"SELECT 2;"),
            ("10_tenth.sql", b"SELECT 10;"),
            ("717_last.sql", b"SELECT 717;"),
        )
    )
    assert manifest_digest == hashlib.sha256(expected_manifest.encode("utf-8")).hexdigest()

    (source / "717_last.sql").write_text("SELECT changed;", encoding="utf-8")
    (source / "718_new.sql").write_text("SELECT 718;", encoding="utf-8")
    assert [path.name for path in RECOVERY_CHECK._ordered_schema_migration_files(snapshot)] == [
        "2_second.sql",
        "10_tenth.sql",
        "717_last.sql",
    ]
    assert files[-1].read_text(encoding="utf-8") == "SELECT 717;"


def test_standard_recovery_rejects_source_changes_during_snapshot(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source"
    snapshot = tmp_path / "snapshot"
    source.mkdir()
    (source / "717_last.sql").write_text("SELECT 717;", encoding="utf-8")
    discover = RECOVERY_CHECK._ordered_schema_migration_files
    calls = 0

    def add_migration_between_inventory_reads(directory: Path) -> list[Path]:
        nonlocal calls
        calls += 1
        if calls == 2:
            (source / "718_new.sql").write_text("SELECT 718;", encoding="utf-8")
        return discover(directory)

    monkeypatch.setattr(
        RECOVERY_CHECK, "_ordered_schema_migration_files", add_migration_between_inventory_reads
    )

    with pytest.raises(RECOVERY_CHECK.AcceptanceError, match="changed while.*captured"):
        RECOVERY_CHECK._snapshot_schema_migrations(source, snapshot)


def test_standard_recovery_migration_command_pins_cli_to_snapshot(tmp_path) -> None:
    command = RECOVERY_CHECK._migration_runner_command(
        "synthetic-project", tmp_path / "compose.json", tmp_path / "schema-snapshot"
    )

    assert command[1] == "-c"
    assert command[3] == str(tmp_path / "schema-snapshot")
    assert "cli.SCHEMA_DIR = Path(sys.argv.pop(1))" in command[2]
    assert command.count("migrate") == 1
    assert command[-2:] == ["migrate", "--schemas-only"]


def test_standard_recovery_cli_can_validate_a_snapshot_without_database_access(tmp_path) -> None:
    snapshot = tmp_path / "schema-snapshot"
    snapshot.mkdir()
    (snapshot / "717_snapshot_probe.sql").write_text("SELECT 717;", encoding="utf-8")
    compose_manifest = tmp_path / "compose.json"
    compose_manifest.write_text("{}", encoding="utf-8")
    command = RECOVERY_CHECK._migration_runner_command(
        "synthetic-project", compose_manifest, snapshot
    )
    command[-2] = "validate"

    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    assert "Validated 1 migration source files." in result.stdout


def test_standard_recovery_built_image_probe_requires_exact_snapshot_manifest() -> None:
    expected = {"count": 1, "latest": "schema:717_snapshot_probe.sql", "sha256": "a" * 64}

    assert RECOVERY_CHECK._assert_image_schema_snapshot(
        json.dumps(expected),
        expected_count=1,
        expected_latest="schema:717_snapshot_probe.sql",
        expected_digest="a" * 64,
    ) == expected

    with pytest.raises(RECOVERY_CHECK.AcceptanceError, match="does not match the captured"):
        RECOVERY_CHECK._assert_image_schema_snapshot(
            json.dumps({**expected, "sha256": "b" * 64}),
            expected_count=1,
            expected_latest="schema:717_snapshot_probe.sql",
            expected_digest="a" * 64,
        )
