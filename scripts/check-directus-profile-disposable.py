#!/usr/bin/env python3
"""Start the optional Directus profile on a fresh disposable Kernel database."""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = f"kokonut-directus-profile-check-{uuid.uuid4().hex[:10]}"
EVIDENCE = ROOT / "docs/refactor/builds/2026-10-15-recovery/directus-profile-disposable.json"


def free_loopback_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def run(
    command: list[str],
    *,
    env: dict[str, str],
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def compose_base() -> list[str]:
    return [
        "docker",
        "compose",
        "--env-file",
        "/dev/null",
        "-p",
        PROJECT,
        "-f",
        str(ROOT / "docker-compose.kernel-candidate.yml"),
        "-f",
        str(ROOT / "docker-compose.kernel-directus.yml"),
    ]


def require_success(result: subprocess.CompletedProcess[str], action: str, env: dict[str, str]) -> None:
    if result.returncode == 0:
        return
    diagnostic = "\n".join((result.stdout or "", result.stderr or ""))
    for name in (
        "POSTGRES_PASSWORD",
        "DIRECTUS_SECRET",
        "ADMIN_PASSWORD",
        "KOKONUT_DIRECTUS_RUNTIME_PASSWORD",
    ):
        diagnostic = diagnostic.replace(env[name], "[redacted]")
    raise RuntimeError(f"{action} failed ({result.returncode}):\n" + "\n".join(diagnostic.splitlines()[-35:]))


def request(url: str, *, body: dict[str, str] | None = None) -> tuple[int, dict | str]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            payload = response.read()
            try:
                return response.status, json.loads(payload)
            except json.JSONDecodeError:
                return response.status, payload.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def main() -> int:
    port = free_loopback_port()
    admin_email = "directus-profile-check@example.com"
    secrets_by_name = {
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "DIRECTUS_SECRET": secrets.token_urlsafe(48),
        "ADMIN_PASSWORD": secrets.token_urlsafe(32),
        "KOKONUT_DIRECTUS_RUNTIME_PASSWORD": secrets.token_urlsafe(32),
    }
    env = os.environ.copy()
    for name in ("COMPOSE_FILE", "COMPOSE_PROJECT_NAME"):
        env.pop(name, None)
    env.update(secrets_by_name)
    env.update(
        {
            "ADMIN_EMAIL": admin_email,
            "KOKONUT_KERNEL_DIRECTUS_BIND": "127.0.0.1",
            "KOKONUT_KERNEL_DIRECTUS_PORT": str(port),
            "KOKONUT_DIRECTUS_PUBLIC_URL": f"http://127.0.0.1:{port}",
            "KOKONUT_DIRECTUS_RUNTIME_USER": "kokonut_directus_runtime",
            "KOKONUT_DB_ADMIN_USER": "kokonut",
        }
    )
    compose = compose_base()
    evidence: dict[str, object] = {
        "status": "failed",
        "project": PROJECT,
        "database": "fresh isolated Kernel PostgreSQL volume",
        "profile": "optional Directus overlay",
        "secrets_logged": False,
        "candidate_or_legacy_database_used": False,
    }

    try:
        build_extensions = run(["make", "hooks-build"], env=env)
        require_success(build_extensions, "Directus extension build", env)

        database_start = run([*compose, "up", "-d", "database"], env=env)
        require_success(database_start, "disposable Kernel database start", env)
        database_ready = False
        database_deadline = time.monotonic() + 90
        while time.monotonic() < database_deadline:
            readiness = run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "database",
                    "pg_isready",
                    "-U",
                    "kokonut",
                    "-d",
                    "kokonut_intelligence",
                ],
                env=env,
            )
            if readiness.returncode == 0:
                database_ready = True
                break
            time.sleep(1)
        if not database_ready:
            raise RuntimeError("disposable Kernel PostgreSQL did not become ready")

        schema_setup = run(
            [
                *compose,
                "exec",
                "-T",
                "database",
                "psql",
                "-U",
                "kokonut",
                "-d",
                "kokonut_intelligence",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "CREATE SCHEMA kokonut AUTHORIZATION kokonut",
            ],
            env=env,
        )
        require_success(schema_setup, "migration-owned Kokonut schema fixture", env)

        role = run([*compose, "--profile", "directus-admin", "run", "--rm", "directus-role-bootstrap"], env=env)
        require_success(role, "Directus role bootstrap", env)
        bootstrap = run([*compose, "--profile", "directus-admin", "run", "--rm", "directus-bootstrap"], env=env)
        require_success(bootstrap, "owner-backed Directus bootstrap", env)

        permission_seed = (ROOT / "config/directus/permissions.sql").read_text(encoding="utf-8")
        permission_seed_command = [
            *compose,
            "exec",
            "-T",
            "database",
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "kokonut",
            "-d",
            "kokonut_intelligence",
        ]
        seed_first = run(permission_seed_command, env=env, input_text=permission_seed)
        require_success(seed_first, "Directus permission seed", env)
        permission_counts_query = """
            SELECT
                count(*) FILTER (WHERE collection = 'farm_activity'),
                count(*) FILTER (WHERE collection = 'field_note')
              FROM public.directus_permissions
             WHERE policy IN (
                'b1000000-0000-0000-0000-000000000001',
                'b1000000-0000-0000-0000-000000000002',
                'b1000000-0000-0000-0000-000000000003',
                'b1000000-0000-0000-0000-000000000004',
                'b1000000-0000-0000-0000-000000000005',
                'b1000000-0000-0000-0000-000000000006',
                'b1000000-0000-0000-0000-000000000007',
                'b1000000-0000-0000-0000-000000000008',
                'b1000000-0000-0000-0000-000000000009'
             )
        """

        def permission_counts() -> tuple[int, int]:
            result = run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "database",
                    "psql",
                    "-X",
                    "-t",
                    "-A",
                    "-F",
                    "|",
                    "-U",
                    "kokonut",
                    "-d",
                    "kokonut_intelligence",
                    "-c",
                    permission_counts_query,
                ],
                env=env,
            )
            require_success(result, "Directus permission seed verification", env)
            values = result.stdout.strip().split("|")
            if len(values) != 2 or not all(value.isdigit() for value in values):
                raise RuntimeError("Directus permission seed returned an unexpected count shape")
            return int(values[0]), int(values[1])

        first_counts = permission_counts()
        if first_counts[0] != 0 or first_counts[1] == 0:
            raise RuntimeError("Directus seed must remove farm_activity while preserving other role permissions")
        seed_replay = run(permission_seed_command, env=env, input_text=permission_seed)
        require_success(seed_replay, "Directus permission seed replay", env)
        replay_counts = permission_counts()
        if replay_counts != first_counts:
            raise RuntimeError("Directus permission seed replay changed curated role-permission counts")

        start = run([*compose, "up", "-d", "directus"], env=env)
        require_success(start, "Directus runtime start", env)

        base_url = f"http://127.0.0.1:{port}"
        ping_status = 0
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                ping_status, _ = request(f"{base_url}/server/ping")
                if ping_status == 200:
                    break
            except (OSError, TimeoutError):
                pass
            time.sleep(1)
        if ping_status != 200:
            raise RuntimeError("Directus did not become healthy on its loopback endpoint")

        login_status, login = request(
            f"{base_url}/auth/login",
            body={"email": admin_email, "password": secrets_by_name["ADMIN_PASSWORD"]},
        )
        if login_status != 200 or not isinstance(login, dict) or not login.get("data", {}).get("access_token"):
            raise RuntimeError(f"Directus owner login failed with HTTP {login_status}")

        database_result = run(
            [
                *compose,
                "exec",
                "-T",
                "database",
                "psql",
                "-U",
                "kokonut",
                "-d",
                "kokonut_intelligence",
                "-X",
                "-t",
                "-A",
                "-c",
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                "AND usename = 'kokonut_directus_runtime'",
            ],
            env=env,
        )
        require_success(database_result, "Directus runtime database identity check", env)
        if not database_result.stdout.strip().isdigit() or int(database_result.stdout.strip()) < 1:
            raise RuntimeError("Directus connections did not use the dedicated runtime role")

        evidence.update(
            {
                "status": "passed",
                "directus_health": ping_status,
                "owner_login": login_status,
                "runtime_database_identity": "kokonut_directus_runtime",
                "owner_backed_bootstrap": "passed",
                "permission_seed": {
                    "first_application": "passed",
                    "replay": "passed",
                    "repository_managed_farm_activity_permissions": first_counts[0],
                    "other_curated_permissions": first_counts[1],
                },
                "loopback_only": True,
            }
        )
    finally:
        cleanup = run([*compose, "down", "--volumes", "--remove-orphans"], env=env)
        evidence["cleanup"] = "passed" if cleanup.returncode == 0 else "failed"
        evidence["checked_at"] = datetime.now(timezone.utc).isoformat()
        if cleanup.returncode:
            raise RuntimeError("failed to remove the disposable Directus profile project")
        if evidence["status"] == "passed":
            EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
            EVIDENCE.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if evidence["status"] == "passed":
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 0
    print(json.dumps(evidence, indent=2, sort_keys=True), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
