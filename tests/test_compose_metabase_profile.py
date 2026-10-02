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
    "CLICKHOUSE_PASSWORD": "compose-test-only",
    "CADDY_DOMAIN": "localhost",
    "PUBLIC_URL": "https://example.invalid",
    "KOKONUT_DOMAIN": "example.invalid",
    "KOKONUT_METABASE_DOMAIN": "metabase.example.invalid",
    "KOKONUT_TRAEFIK_NETWORK": "traefik",
    "KOKONUT_TLS_RESOLVER": "letsencrypt",
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


def test_sandbox_keeps_seed_profile_independent_and_metabase_opt_in() -> None:
    sandbox_files = ("docker-compose.yml", "docker-compose.sandbox.yml")
    default_services = _compose_services("sandbox", files=sandbox_files)
    assert "sandbox-seed" in default_services
    assert "metabase" not in default_services

    config = _compose_config("sandbox", "metabase", files=sandbox_files)
    metabase = config["services"]["metabase"]
    assert metabase["ports"] == [{"host_ip": "127.0.0.1", "published": "3001", "target": 3000, "protocol": "tcp", "mode": "ingress"}]


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
        "curl": "#!/bin/sh\nprintf 'curl %s\\n' \"$*\" >> \"$HEALTH_TEST_LOG\"\nexit 0\n",
        "psql": "#!/bin/sh\nexit 0\n",
        "docker": (
            "#!/bin/sh\n"
            "printf 'docker %s\\n' \"$*\" >> \"$HEALTH_TEST_LOG\"\n"
            "case \" $* \" in\n"
            "  *\" --filter \"*) exit 0 ;;\n"
            "  *) printf 'database\\ndirectus\\nclickhouse\\n'; "
            "if [ \"${HEALTH_CHECK_METABASE:-false}\" = \"true\" ]; then printf 'metabase\\n'; fi ;;\n"
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
