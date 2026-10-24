"""Contracts for the disposable credit-adjustment database runner."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_runner_path = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "check-credit-adjustment-worker-disposable.py"
)
_runner_spec = spec_from_file_location("credit_adjustment_disposable", _runner_path)
assert _runner_spec is not None and _runner_spec.loader is not None
_runner = module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(_runner)
docker_run_command = _runner.docker_run_command
build_argument_parser = _runner.build_argument_parser


def test_arm64_disposable_runner_requests_platform_without_changing_loopback_scope():
    command = docker_run_command(
        "docker",
        "synthetic-credit-test",
        "kokonut-kernel-postgis-arm64:local",
        "synthetic-password",
        "linux/arm64",
    )

    assert command[:8] == [
        "docker",
        "run",
        "-d",
        "--rm",
        "--name",
        "synthetic-credit-test",
        "--platform",
        "linux/arm64",
    ]
    assert command[8:12] == ["-e", "POSTGRES_PASSWORD=synthetic-password", "-p", "127.0.0.1::5432"]
    assert command[-1] == "kokonut-kernel-postgis-arm64:local"


def test_default_runner_remains_host_platform_compatible():
    command = docker_run_command(
        "docker", "synthetic-credit-test", "postgres:16", "synthetic-password"
    )

    assert "--platform" not in command
    assert "127.0.0.1::5432" in command


def test_startup_timeout_defaults_to_three_minutes_and_remains_bounded():
    parser = build_argument_parser()

    assert parser.parse_args([]).startup_timeout == 180
    assert parser.parse_args(["--startup-timeout", "360"]).startup_timeout == 360
