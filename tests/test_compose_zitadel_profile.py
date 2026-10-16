"""Compose contract for the opt-in, isolated self-hosted ZITADEL profile."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLANNER = ROOT / "scripts" / "kernel-profile.py"
FILES = (
    "docker-compose.kernel-candidate.yml",
    "docker-compose.kernel-proxy.yml",
    "docker-compose.kernel-oidc.yml",
    "docker-compose.kernel-zitadel.yml",
)
TEST_ENV = {
    "PATH": os.environ["PATH"],
    "POSTGRES_PASSWORD": "compose-test-only-postgres",
    "MOBILE_MEDIA_LOCAL_KEY": "compose-test-only-local-media-key",
    "KOKONUT_OPERATOR_AUTH_PASSWORD": "compose-test-only-auth-password",
    "KOKONUT_OPERATOR_OIDC_ISSUER": "https://zitadel.example.test:9443",
    "KOKONUT_OPERATOR_OIDC_CLIENT_ID": "compose-test-client",
    "KOKONUT_OPERATOR_OIDC_CLIENT_SECRET": "compose-test-client-secret",
    "KOKONUT_OPERATOR_OIDC_REDIRECT_URI": "https://hub.example.test:9443/operator/auth/callback",
    "KOKONUT_OPERATOR_OIDC_STATE_SECRET": "compose-test-state-secret-at-least-32-bytes",
    "KOKONUT_ZITADEL_DOMAIN": "zitadel.example.test",
    "KOKONUT_KERNEL_HTTPS_PORT": "9443",
    "KOKONUT_ZITADEL_POSTGRES_ADMIN_PASSWORD": "compose-test-db-admin-password",
    "KOKONUT_ZITADEL_DATABASE_PASSWORD": "a" * 64,
    "KOKONUT_ZITADEL_MASTERKEY": "m" * 32,
    "KOKONUT_ZITADEL_ADMIN_USERNAME": "synthetic-admin",
    "KOKONUT_ZITADEL_ADMIN_PASSWORD": "compose-test-admin-password",
    "KOKONUT_ZITADEL_LOGIN_CLIENT_PAT_EXPIRATION": "2027-10-15T00:00:00Z",
    "KOKONUT_ZITADEL_LOGIN_COOKIE_SECRET": "compose-test-login-cookie-secret-32-bytes",
}


def _compose(*files: str) -> dict:
    command = ["docker", "compose", "--env-file", "/dev/null"]
    for filename in files:
        command.extend(["-f", filename])
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


def _services(*files: str) -> set[str]:
    command = ["docker", "compose", "--env-file", "/dev/null"]
    for filename in files:
        command.extend(["-f", filename])
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


def test_default_and_edge_profiles_do_not_include_zitadel() -> None:
    assert _services("docker-compose.kernel-candidate.yml") == {"app", "database"}
    assert "zitadel-api" not in _services(
        "docker-compose.kernel-candidate.yml", "docker-compose.kernel-edge.yml"
    )


def test_zitadel_profile_is_private_and_uses_a_dedicated_non_superuser_database_role() -> None:
    config = _compose(*FILES)
    services = config["services"]

    assert {"zitadel-db", "zitadel-api", "zitadel-login", "proxy"} <= set(services)
    assert not services["zitadel-db"].get("ports")
    assert not services["zitadel-api"].get("ports")
    assert not services["zitadel-login"].get("ports")

    db = services["zitadel-db"]
    assert "zitadel-data" in db["networks"]
    assert db["environment"]["POSTGRES_USER"] == "postgres"
    assert db["environment"]["KOKONUT_ZITADEL_DATABASE_PASSWORD"] == "a" * 64
    assert "init-db.sh" in " ".join(item["source"] for item in db["volumes"])

    api = services["zitadel-api"]
    assert api["image"] == (
        "ghcr.io/zitadel/zitadel:v4.19.4@sha256:"
        "90a3045b80a2b5b395e1e770302076906af3a5911225af7c464b4f3bd00d0a1b"
    )
    assert api["command"] == ["start-from-init", "--masterkeyFromEnv", "--tlsMode", "disabled"]
    assert api["environment"]["ZITADEL_DATABASE_POSTGRES_DSN"].startswith(
        "postgresql://zitadel:"
    )
    assert api["environment"]["ZITADEL_EXTERNALSECURE"] == "true"
    assert api["environment"]["ZITADEL_EXTERNALPORT"] == "9443"
    assert api["environment"]["ZITADEL_DEFAULTINSTANCE_FEATURES_LOGINV2_BASEURI"].startswith(
        "https://zitadel.example.test:9443/"
    )
    assert api["environment"]["ZITADEL_TLS_ENABLED"] == "false"
    assert api["environment"]["ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORDCHANGEREQUIRED"] == "true"
    assert "zitadel-data" in api["networks"]
    assert "kernel" in api["networks"]

    login = services["zitadel-login"]
    assert login["image"] == (
        "ghcr.io/zitadel/zitadel-login:v4.19.4@sha256:"
        "93ffd1395b827f685ba29c02fa70aee881fc21102519c4e2bbb0b89c0e00f42c"
    )
    assert login["environment"]["NEXT_PUBLIC_BASE_PATH"] == "/ui/v2/login"
    assert login["environment"]["ZITADEL_SERVICE_USER_TOKEN_FILE"] == "/zitadel/bootstrap/login-client.pat"


def test_optional_identity_proxy_uses_h2c_and_routes_login_v2_separately() -> None:
    config = _compose(*FILES)
    proxy = config["services"]["proxy"]

    assert any(item["source"].endswith("Caddyfile.kernel.zitadel") for item in proxy["volumes"])
    assert {"zitadel-api", "zitadel-login"} <= set(proxy["depends_on"])

    caddyfile = (ROOT / "config/caddy/Caddyfile.kernel.zitadel").read_text()
    assert "reverse_proxy /ui/v2/login/* http://zitadel-login:3000" in caddyfile
    assert "reverse_proxy h2c://zitadel-api:8080" in caddyfile
    assert "header_up -TE" in caddyfile
    assert "reverse_proxy app:8099" in caddyfile


def test_zitadel_planner_selects_only_the_required_optional_overlays() -> None:
    result = subprocess.run(
        [sys.executable, str(PLANNER), "minimal", "--zitadel"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "docker-compose.kernel-proxy.yml" in result.stdout
    assert "docker-compose.kernel-oidc.yml" in result.stdout
    assert "docker-compose.kernel-zitadel.yml" in result.stdout
    assert "docker-compose.kernel-analytics.yml" not in result.stdout
    assert "docker-compose.kernel-metabase.yml" not in result.stdout


def test_standard_zitadel_arm64_planner_command_resolves_all_services_for_arm64() -> None:
    planned = subprocess.run(
        [
            sys.executable,
            str(PLANNER),
            "standard",
            "--target-platform",
            "linux/arm64",
            "--zitadel",
            "--action",
            "config",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert planned.returncode == 0, planned.stderr

    command = shlex.split(planned.stdout)
    assert command[-2:] == ["config", "--quiet"]
    command[-2:] = ["config", "--format", "json"]
    rendered = subprocess.run(
        command,
        cwd=ROOT,
        env=TEST_ENV,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rendered.returncode == 0, rendered.stderr
    services = json.loads(rendered.stdout)["services"]

    assert set(services) == {
        "app",
        "database",
        "worker",
        "proxy",
        "zitadel-db",
        "zitadel-api",
        "zitadel-login",
    }
    assert all(service.get("platform") == "linux/arm64" for service in services.values())
    assert services["app"]["build"]["target"] == "oidc"
    assert services["zitadel-db"]["image"] == (
        "postgres:17.10-alpine@sha256:"
        "742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193"
    )


def test_database_bootstrap_creates_only_a_bounded_login_role_and_owned_database() -> None:
    bootstrap = (ROOT / "scripts/zitadel/init-db.sh").read_text()

    assert "NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT" in bootstrap
    assert "CREATE DATABASE zitadel OWNER zitadel" in bootstrap
    assert "\\getenv zitadel_password KOKONUT_ZITADEL_DATABASE_PASSWORD" in bootstrap
    assert "echo" not in bootstrap.lower()
