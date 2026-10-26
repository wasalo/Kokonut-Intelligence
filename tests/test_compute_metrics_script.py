"""Execution-mode contracts for the one-shot metrics helper."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/compute-metrics.sh"


def test_host_override_runs_metrics_without_resolving_docker_worker(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_calls = tmp_path / "docker-calls.txt"
    fake_python = fake_bin / "python3"
    fake_python.write_text(
        "#!/bin/sh\n"
        "printf 'python3'\n"
        "printf ' %s' \"$@\"\n"
        "printf '\\n'\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$*\" >> \"$DOCKER_CALLS\"\n"
        "exit 88\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "KOKONUT_METRICS_EXECUTION": "host",
            "PG_HOST": "127.0.0.1",
            "DOCKER_CALLS": str(docker_calls),
        }
    )
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "python3 -m services.metrics --compute --all-locations --json" in result.stdout
    assert not docker_calls.exists()


def test_github_ci_selects_host_metrics_mode_before_computation() -> None:
    ci_script = (ROOT / "scripts/run-github-ci.sh").read_text(encoding="utf-8")

    assert "export KOKONUT_METRICS_EXECUTION=host" in ci_script
    assert ci_script.index("export KOKONUT_METRICS_EXECUTION=host") < ci_script.index(
        "./scripts/compute-metrics.sh"
    )
