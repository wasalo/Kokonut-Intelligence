"""Command-planner contracts for optional Kernel deployment profiles."""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PLANNER = ROOT / "scripts" / "kernel-profile.py"


def _run_planner(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PLANNER), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_default_profile_planner_does_not_select_optional_overlays() -> None:
    result = _run_planner("minimal")

    assert result.returncode == 0
    assert "docker-compose.kernel-proxy.yml" not in result.stdout
    assert "docker-compose.kernel-oidc.yml" not in result.stdout
    assert "--env-file /dev/null" in result.stdout


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
