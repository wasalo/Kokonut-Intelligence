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
    proxy = _run_planner("minimal", "--target-platform", "linux/arm64", "--proxy")

    assert analytics.returncode != 0
    assert "only minimal, edge, and standard" in analytics.stderr
    assert proxy.returncode != 0
    assert "optional service images remain unverified" in proxy.stderr


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
