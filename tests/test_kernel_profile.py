"""Command-planner contracts for optional Kernel deployment profiles."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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
