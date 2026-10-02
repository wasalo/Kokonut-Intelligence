"""KI-21 contract: Metabase stays available but is excluded from default stacks."""

from __future__ import annotations

import json
import os
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
    "CLICKHOUSE_PASSWORD": "compose-test-only",
}


def _compose_config(*profiles: str, files: tuple[str, ...] = ("docker-compose.yml",)) -> dict:
    command = ["docker", "compose", "--env-file", "/dev/null"]
    for profile in profiles:
        command.extend(["--profile", profile])
    for compose_file in files:
        command.extend(["-f", compose_file])
    command.extend(["config", "--format", "json"])
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=TEST_ENV,
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
    assert metabase["ports"] == [{"host_ip": "127.0.0.1", "published": "13001", "target": 3000, "protocol": "tcp", "mode": "ingress"}]


def test_metabase_profile_disables_public_sharing_and_embedding_without_secret() -> None:
    environment = _compose_config("metabase")["services"]["metabase"]["environment"]
    assert environment["MB_ENABLE_PUBLIC_SHARING"] == "false"
    assert environment["MB_ENABLE_EMBEDDING_STATIC"] == "false"
    assert "MB_ENABLE_EMBEDDING" not in environment
    assert "MB_EMBEDDING_APP_ORIGIN" not in environment
    assert "MB_EMBEDDING_SECRET_KEY" not in environment
    assert "MB_APPLICATION_ROOT" not in environment


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
