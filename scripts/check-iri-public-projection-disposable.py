#!/usr/bin/env python3
"""Apply and replay the public-IRI projection migration on disposable PostgreSQL."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/420_iri_public_projection_snapshot.sql"
DEFAULT_OUTPUT = (
    ROOT
    / "docs/refactor/builds/2026-10-16-recovery/public-iri-projection-migration-disposable.json"
)


def run(command: list[str], *, input_text: str | None = None, check: bool = True):
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        raise RuntimeError(
            f"{command[0]} {command[1] if len(command) > 1 else ''} failed: "
            f"{result.stderr.strip()}"
        )
    return result


def docker_sql(docker: str, container: str, statement: str):
    return run(
        [
            docker,
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-q",
            "-A",
            "-t",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        check = run(
            [docker, "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            check=False,
        )
        if check.returncode == 0:
            return
        time.sleep(0.25)
    raise TimeoutError("disposable PostgreSQL did not become ready")


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("docker CLI is required for this disposable PostgreSQL check")

    image = os.environ.get("IRI_PROJECTION_POSTGRES_IMAGE", "postgres:16-alpine")
    container = f"kokonut-iri-projection-{uuid.uuid4().hex[:10]}"
    result = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "migration": MIGRATION.name,
        "database_image": image,
        "network": "none",
        "host_port": None,
        "persistent_volume": False,
        "candidate_or_legacy_modified": False,
    }

    try:
        run(
            [
                docker,
                "run",
                "--detach",
                "--rm",
                "--network",
                "none",
                "--name",
                container,
                "--env",
                "POSTGRES_PASSWORD=disposable-only",
                image,
            ]
        )
        wait_ready(docker, container)
        docker_sql(
            docker,
            container,
            "CREATE TABLE iri_registry (id UUID PRIMARY KEY);\n",
        )

        migration_sql = MIGRATION.read_text(encoding="utf-8")
        docker_sql(docker, container, migration_sql)
        docker_sql(docker, container, migration_sql)

        docker_sql(
            docker,
            container,
            """
            INSERT INTO iri_registry (id, public_projection)
            VALUES ('11111111-1111-4111-8111-111111111111',
                    '{"name":"Public Farm","country":"DO","region":"North","status":"active"}'::jsonb);
            INSERT INTO iri_registry (id, public_projection)
            VALUES ('22222222-2222-4222-8222-222222222222', NULL);
            """,
        )
        # Run invalid data separately so its transaction failure cannot affect
        # the valid object and NULL cases above.
        invalid = run(
            [
                docker,
                "exec",
                "-i",
                container,
                "psql",
                "-X",
                "-q",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "postgres",
                "-d",
                "postgres",
            ],
            input_text=(
                "INSERT INTO iri_registry (id, public_projection) VALUES "
                "('33333333-3333-4333-8333-333333333333', '[]'::jsonb);\n"
            ),
            check=False,
        )
        if invalid.returncode == 0 or "chk_iri_public_projection_object" not in invalid.stderr:
            raise AssertionError("migration did not reject a non-object public projection")

        counts = docker_sql(
            docker,
            container,
            "SELECT count(*) || ':' || count(*) FILTER (WHERE public_projection IS NOT NULL) "
            "FROM iri_registry;\n",
        ).stdout.strip().splitlines()[-1]
        if counts != "2:1":
            raise AssertionError(f"unexpected projection fixture counts: {counts}")

        result.update(
            {
                "result": "passed",
                "migration_apply": "passed",
                "migration_replay": "passed",
                "valid_object": "accepted",
                "null_snapshot": "accepted",
                "non_object_snapshot": "rejected",
                "invalid_row_persisted": False,
                "fixture_counts": counts,
            }
        )
    finally:
        run([docker, "rm", "--force", container], check=False)

    output_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"result": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        raise
