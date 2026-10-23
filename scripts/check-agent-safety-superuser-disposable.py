#!/usr/bin/env python3
"""Verify worker lifecycle guards distinguish workers from superuser sessions."""

from __future__ import annotations

import json
import re
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/598_agent_safety_superuser_session_guard.sql"


def project_postgres_image() -> str:
    compose = (ROOT / "docker-compose.yml").read_text().splitlines()
    in_database_service = False
    for line in compose:
        if line == "  database:":
            in_database_service = True
            continue
        if in_database_service and line.startswith("  ") and not line.startswith("    "):
            break
        if in_database_service and line.startswith("    image:"):
            image = line.split("image:", 1)[1].strip()
            if not re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", image):
                raise RuntimeError("database Compose image must remain digest-pinned")
            return image
    raise RuntimeError("could not find the digest-pinned database image in Compose")


def run(
    command: list[str],
    *,
    input_text: str | None = None,
    expected_status: int = 0,
    timeout: float = 180,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode != expected_status:
        details = "\n".join(
            part.strip() for part in (result.stdout, result.stderr) if part.strip()
        )
        raise RuntimeError(
            f"command exited {result.returncode}, expected {expected_status}: "
            f"{' '.join(command)}\n{details[-4000:]}"
        )
    return result


def psql(container: str, sql: str, *, expected_status: int = 0) -> str:
    result = run(
        [
            "docker",
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-t",
            "-A",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
        input_text=sql,
        expected_status=expected_status,
    )
    return result.stdout + result.stderr


def require_error(output: str, expected: str) -> None:
    if expected not in output:
        raise AssertionError(f"expected PostgreSQL denial was not observed: {expected}")


def main() -> int:
    container = f"ki-agent-safety-{uuid.uuid4().hex[:12]}"
    image = project_postgres_image()
    assertions: dict[str, bool] = {}
    started = False
    try:
        run(
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--name",
                container,
                "--network",
                "none",
                "--env",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                image,
            ]
        )
        started = True
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                ready = subprocess.run(
                    [
                        "docker",
                        "exec",
                        container,
                        "pg_isready",
                        "-h",
                        "127.0.0.1",
                        "-U",
                        "postgres",
                        "-d",
                        "postgres",
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=10,
                )
            except subprocess.TimeoutExpired:
                # Docker Desktop may accept `run` before its exec endpoint is
                # responsive. Keep polling until the overall readiness window
                # expires instead of failing on one slow daemon round trip.
                time.sleep(0.5)
                continue
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")

        migration = MIGRATION.read_text()
        for _ in range(2):
            psql(container, migration)
        assertions["migration_replays_twice"] = True
        version = psql(container, "SELECT current_setting('server_version');").strip()

        psql(
            container,
            """
            CREATE ROLE kokonut_worker_execution
                NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS;
            CREATE ROLE kokonut_worker_login
                LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS;
            GRANT kokonut_worker_execution TO kokonut_worker_login
                WITH INHERIT FALSE, SET TRUE;
            CREATE ROLE kokonut_operator_login
                NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS;
            CREATE TABLE public.safety_probe (
                id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                status TEXT NOT NULL
            );
            CREATE TRIGGER trg_agent_safety_probe_insert
                BEFORE INSERT ON public.safety_probe
                FOR EACH ROW
                WHEN (NEW.status IN ('verified', 'published'))
                EXECUTE FUNCTION public.assert_agent_safety();
            CREATE TRIGGER trg_agent_safety_probe_update
                BEFORE UPDATE ON public.safety_probe
                FOR EACH ROW
                WHEN (NEW.status IS DISTINCT FROM OLD.status)
                EXECUTE FUNCTION public.assert_agent_safety();
            GRANT USAGE, SELECT ON SEQUENCE public.safety_probe_id_seq
                TO kokonut_worker_execution, kokonut_worker_login,
                   kokonut_operator_login;
            GRANT INSERT, SELECT, UPDATE ON public.safety_probe
                TO kokonut_worker_execution, kokonut_worker_login,
                   kokonut_operator_login;
            """,
        )

        psql(container, "INSERT INTO public.safety_probe(status) VALUES ('published');")
        assertions["superuser_can_publish"] = True
        psql(
            container,
            """
            SET SESSION AUTHORIZATION kokonut_operator_login;
            INSERT INTO public.safety_probe(status) VALUES ('published');
            RESET SESSION AUTHORIZATION;
            """,
        )
        assertions["ordinary_operator_can_publish"] = True
        psql(
            container,
            """
            SET SESSION AUTHORIZATION kokonut_worker_login;
            INSERT INTO public.safety_probe(status) VALUES ('draft');
            RESET SESSION AUTHORIZATION;
            """,
        )
        assertions["worker_can_create_draft"] = True

        denied_insert = psql(
            container,
            """
            SET SESSION AUTHORIZATION kokonut_worker_login;
            INSERT INTO public.safety_probe(status) VALUES ('published');
            """,
            expected_status=3,
        )
        require_error(
            denied_insert,
            "Agent worker operations cannot insert terminal status published",
        )
        assertions["worker_cannot_insert_terminal_status"] = True

        denied_update = psql(
            container,
            """
            SET SESSION AUTHORIZATION kokonut_worker_login;
            UPDATE public.safety_probe SET status = 'published' WHERE status = 'draft';
            """,
            expected_status=3,
        )
        require_error(denied_update, "Agent worker operations cannot set status to published")
        assertions["worker_cannot_promote_to_terminal_status"] = True

        denied_set_role = psql(
            container,
            """
            GRANT INSERT ON public.safety_probe TO kokonut_worker_execution;
            GRANT USAGE, SELECT ON SEQUENCE public.safety_probe_id_seq
                TO kokonut_worker_execution;
            SET ROLE kokonut_worker_execution;
            INSERT INTO public.safety_probe(status) VALUES ('published');
            """,
            expected_status=3,
        )
        require_error(
            denied_set_role,
            "Agent worker operations cannot insert terminal status published",
        )
        assertions["superuser_set_role_worker_is_blocked"] = True

        denied_marker = psql(
            container,
            """
            SET app.agent_id = 'synthetic-agent';
            INSERT INTO public.safety_probe(status) VALUES ('published');
            """,
            expected_status=3,
        )
        require_error(
            denied_marker,
            "Agent worker operations cannot insert terminal status published",
        )
        assertions["compatibility_marker_remains_restrictive"] = True

        counts = psql(
            container,
            """
            SELECT count(*) FILTER (WHERE status = 'published'),
                   count(*) FILTER (WHERE status = 'draft')
              FROM public.safety_probe;
            """,
        ).strip()
        if counts != "2|1":
            raise AssertionError(f"unexpected synthetic row counts: {counts}")
        assertions["denied_operations_left_no_rows"] = True

        evidence = {
            "result": "passed",
            "migration": MIGRATION.name,
            "database": f"PostgreSQL {version}",
            "image": image,
            "network_mode": "none",
            "host_ports_published": False,
            "assertions": assertions,
        }
    finally:
        if started:
            cleanup = subprocess.run(
                ["docker", "rm", "--force", container],
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            if cleanup.returncode != 0:
                raise RuntimeError("could not remove the disposable PostgreSQL container")

    evidence["cleanup_completed"] = True
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
