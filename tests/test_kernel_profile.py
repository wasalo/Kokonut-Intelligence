"""Command-planner contracts for optional Kernel deployment profiles."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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


def test_default_and_oidc_kernel_runtime_commands_require_schema_readiness() -> None:
    dockerfile = (ROOT / "Dockerfile.kernel").read_text()
    runtime_commands = [line for line in dockerfile.splitlines() if line.startswith("CMD ")
                       and "services.core.runtime" in line]

    assert len(runtime_commands) == 2
    assert all("--require-schema" in command for command in runtime_commands)


def test_standard_api_and_worker_require_schema_readiness() -> None:
    standard = yaml.safe_load((ROOT / "docker-compose.kernel-standard.yml").read_text())

    for service_name in ("app", "worker"):
        command = standard["services"][service_name]["command"]
        assert "--require-schema" in command


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

    assert grpc.returncode == 0
    assert "docker-compose.kernel-grpc.yml" in grpc.stdout
    assert "docker-compose.kernel-arm64-grpc.yml" in grpc.stdout
    assert mqtt.returncode == 0
    assert "docker-compose.kernel-mqtt.yml" in mqtt.stdout
    assert "docker-compose.kernel-arm64-mqtt.yml" in mqtt.stdout


def test_directus_option_selects_only_the_optional_directus_overlay() -> None:
    result = _run_planner("minimal", "--directus")

    assert result.returncode == 0
    assert "docker-compose.kernel-directus.yml" in result.stdout
    assert "docker-compose.kernel-proxy.yml" not in result.stdout
    assert "docker-compose.kernel-zitadel.yml" not in result.stdout


def test_directus_option_is_rejected_for_unverified_arm64_optional_images() -> None:
    result = _run_planner("minimal", "--target-platform", "linux/arm64", "--directus")

    assert result.returncode != 0
    assert "ARM64 does not verify these optional overlays: directus" in result.stderr


def test_profile_planner_selects_isolated_arm64_images_for_edge() -> None:
    result = _run_planner("edge", "--target-platform", "linux/arm64")

    assert result.returncode == 0
    assert "docker-compose.kernel-arm64.yml" in result.stdout
    assert "kokonut-kernel-candidate-arm64" in result.stdout
    assert "docker-compose.kernel-edge.yml" in result.stdout


def test_standard_arm64_profile_selects_the_arm64_worker_override() -> None:
    result = _run_planner("standard", "--target-platform", "linux/arm64")

    assert result.returncode == 0
    assert "docker-compose.kernel-standard.yml" in result.stdout
    assert "docker-compose.kernel-arm64.yml" in result.stdout
    assert "docker-compose.kernel-arm64-standard.yml" in result.stdout


def test_arm64_planner_rejects_unverified_analytics_and_optional_images() -> None:
    analytics = _run_planner("analytics", "--target-platform", "linux/arm64")
    directus = _run_planner("minimal", "--target-platform", "linux/arm64", "--directus")

    assert analytics.returncode != 0
    assert "only minimal, edge, and standard" in analytics.stderr
    assert directus.returncode != 0
    assert "ARM64 does not verify these optional overlays: directus" in directus.stderr


def test_arm64_identity_overlays_pin_each_supported_service_architecture() -> None:
    proxy = yaml.safe_load((ROOT / "docker-compose.kernel-arm64-proxy.yml").read_text())
    zitadel = yaml.safe_load((ROOT / "docker-compose.kernel-arm64-zitadel.yml").read_text())
    provider = yaml.safe_load((ROOT / "docker-compose.kernel-zitadel.yml").read_text())

    assert proxy["services"]["proxy"]["platform"] == "linux/arm64"
    assert set(zitadel["services"]) == {"zitadel-db", "zitadel-api", "zitadel-login"}
    assert all(service["platform"] == "linux/arm64" for service in zitadel["services"].values())
    assert "postgres:17.10-alpine@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193" in provider[
        "services"
    ]["zitadel-db"]["image"]


def test_arm64_transport_overlays_force_platform_for_all_selected_services() -> None:
    grpc = yaml.safe_load((ROOT / "docker-compose.kernel-arm64-grpc.yml").read_text())
    mqtt = yaml.safe_load((ROOT / "docker-compose.kernel-arm64-mqtt.yml").read_text())
    mqtt_profile = yaml.safe_load((ROOT / "docker-compose.kernel-mqtt.yml").read_text())

    assert grpc["services"]["grpc"]["platform"] == "linux/arm64"
    assert set(mqtt["services"]) == {"mosquitto", "mqtt-subscriber"}
    assert all(service["platform"] == "linux/arm64" for service in mqtt["services"].values())
    assert "sha256:6f8d8a947c506f8a2290ec65cd4bd2bc7cb4d43fb5f6271f861cb013e2ef9797" in mqtt_profile[
        "services"
    ]["mosquitto"]["image"]


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
