#!/usr/bin/env python3
"""Verify strictly location-scoped remote-sensing claims in disposable PostgreSQL."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["KOKONUT_ENV"] = "development"
os.environ["KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT"] = "true"

from services.ingestion.remote_sensing_fetcher import _claim_due_jobs  # noqa: E402


def _docker_executable() -> str:
    executable = shutil.which("docker")
    if executable:
        return executable
    desktop_cli = Path("/Applications/Docker.app/Contents/Resources/bin/docker")
    if desktop_cli.is_file():
        return str(desktop_cli)
    raise RuntimeError("Docker CLI is unavailable")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run(docker: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([docker, *args], capture_output=True, text=True, check=False)
    if check and result.returncode:
        # Do not include argv: it contains the generated disposable password.
        raise RuntimeError(f"Docker {args[0]} failed: {result.stderr.strip()}")
    return result


def main() -> int:
    image = os.environ.get("REMOTE_SENSING_TEST_POSTGRES_IMAGE", "postgres:16-alpine")
    name = f"kokonut-rs-location-{uuid.uuid4().hex[:8]}"
    password = secrets.token_urlsafe(24)
    port = _free_port()
    docker = _docker_executable()
    connection = None
    evidence: dict[str, object] = {
        "result": "failed",
        "postgres_image": image,
        "database_volume": False,
        "database_binding": "127.0.0.1 only",
        "candidate_or_legacy_modified": False,
        "provider_calls": 0,
    }

    try:
        _run(
            docker,
            "run",
            "--detach",
            "--name",
            name,
            "--publish",
            f"127.0.0.1:{port}:5432",
            "--env",
            "POSTGRES_PASSWORD=" + password,
            image,
        )
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            ready = _run(
                docker,
                "exec",
                name,
                "pg_isready",
                "-h", "127.0.0.1", "-U",
                "postgres",
                "-d",
                "postgres",
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise TimeoutError("disposable PostgreSQL did not become ready")

        connection = psycopg2.connect(
            dbname="postgres",
            user="postgres",
            password=password,
            host="127.0.0.1",
            port=port,
            connect_timeout=8,
            application_name="remote-sensing-location-claim-disposable",
        )
        first_location, second_location, unselected_location = (uuid.uuid4() for _ in range(3))
        expected_by_location = {
            str(first_location): [str(uuid.uuid4()), str(uuid.uuid4())],
            str(second_location): [str(uuid.uuid4())],
            str(unselected_location): [str(uuid.uuid4())],
        }
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE remote_sensing_job (
                    id uuid PRIMARY KEY,
                    location_id uuid NOT NULL,
                    status text NOT NULL,
                    next_run_at timestamptz,
                    lease_expires_at timestamptz,
                    lease_owner text,
                    attempt_count integer NOT NULL DEFAULT 0,
                    updated_at timestamptz NOT NULL DEFAULT NOW()
                )
                """
            )
            for location_id, job_ids in expected_by_location.items():
                for job_id in job_ids:
                    cursor.execute(
                        """
                        INSERT INTO remote_sensing_job (id, location_id, status, next_run_at)
                        VALUES (%s, %s, 'active', NOW() - INTERVAL '1 minute')
                        """,
                        (job_id, location_id),
                    )
        connection.commit()

        first_claims = [
            _claim_due_jobs(connection, location_id=str(first_location)),
            _claim_due_jobs(connection, location_id=str(first_location)),
        ]
        second_claim = _claim_due_jobs(connection, location_id=str(second_location))
        try:
            _claim_due_jobs(connection)
        except ValueError:
            unscoped_claim_rejected = True
        else:
            unscoped_claim_rejected = False

        claimed_ids = [rows[0]["id"] for rows in first_claims if rows]
        first_location_scoped = (
            len(claimed_ids) == 2
            and all(str(row["location_id"]) == str(first_location) for rows in first_claims for row in rows)
        )
        second_location_scoped = (
            len(second_claim) == 1 and str(second_claim[0]["location_id"]) == str(second_location)
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM remote_sensing_job WHERE lease_owner IS NULL"
            )
            unclaimed_count = int(cursor.fetchone()[0])

        evidence.update(
            {
                "first_location_claims_only_its_two_jobs": first_location_scoped,
                "second_location_claims_only_its_job": second_location_scoped,
                "unscoped_claim_rejected_before_database_access": unscoped_claim_rejected,
                "unclaimed_rows_after_expected_claims": unclaimed_count,
                "result": "passed"
                if first_location_scoped
                and second_location_scoped
                and unscoped_claim_rejected
                and unclaimed_count == 1
                else "failed",
                "limitations": [
                    "Uses a synthetic remote_sensing_job table and rows; no repository database or provider is contacted.",
                    "Exercises SQL claim filtering and leases only, not provider response parity or worker identity/RLS.",
                    "The container has no volume and publishes PostgreSQL only on loopback.",
                ],
            }
        )
    except Exception as exc:  # emit only safe error metadata
        evidence["error_type"] = type(exc).__name__
    finally:
        if connection is not None:
            connection.rollback()
            connection.close()
        _run(docker, "rm", "--force", name, check=False)

    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
