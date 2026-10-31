#!/usr/bin/env python3
"""Exercise the Standard worker health query on network-isolated PostgreSQL 16."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.core.worker_progress import WORKER_NAMES, _progress_sql  # noqa: E402

DEFAULT_IMAGE = os.environ.get("WORKER_PROGRESS_TEST_IMAGE", "postgres:16")
DEFAULT_OUTPUT = (
    ROOT
    / "docs/refactor/builds/2026-10-31-recovery/standard-worker-backlog-disposable.json"
)


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        safe_command = [
            "POSTGRES_PASSWORD=<redacted>" if item.startswith("POSTGRES_PASSWORD=") else item
            for item in command
        ]
        detail = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(safe_command)}\n{detail}"
        )
    return result.stdout.strip()


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run(
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
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    stable = 0
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            stable += 1
            if stable == 4:
                return
        else:
            stable = 0
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become stably ready")


SCHEMA_AND_FIXTURES = r"""
CREATE TABLE scheduled_task (
    id UUID PRIMARY KEY,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    next_run_at TIMESTAMPTZ,
    retry_at TIMESTAMPTZ,
    lease_expires_at TIMESTAMPTZ,
    dependency_mode TEXT NOT NULL DEFAULT 'last_completed',
    run_window_at TIMESTAMPTZ,
    depends_on UUID[] NOT NULL DEFAULT '{}',
    allow_overlap BOOLEAN NOT NULL DEFAULT FALSE,
    last_status TEXT
);
CREATE TABLE task_run (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES scheduled_task(id),
    status TEXT NOT NULL,
    scheduled_for TIMESTAMPTZ
);
CREATE TABLE platform_event (
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    lease_expires_at TIMESTAMPTZ
);
CREATE TABLE notification_outbox (
    status TEXT NOT NULL,
    available_at TIMESTAMPTZ NOT NULL,
    lease_expires_at TIMESTAMPTZ
);
CREATE TEMP TABLE worker_progress_fixture_clock AS
SELECT statement_timestamp() - INTERVAL '300 seconds' AS window_at;

-- Scheduler: overdue cadence and retry are due; a future retry supersedes an
-- older cadence; active leases, disabled tasks, unmet dependencies, and
-- non-overlap running work are not unclaimed backlog.
INSERT INTO scheduled_task (id, next_run_at) VALUES
    ('10000000-0000-0000-0000-000000000001', NOW() - INTERVAL '1800 seconds'),
    ('10000000-0000-0000-0000-000000000002', NOW() + INTERVAL '600 seconds'),
    ('10000000-0000-0000-0000-000000000003', NOW() - INTERVAL '5000 seconds');
UPDATE scheduled_task
   SET retry_at = NOW() + INTERVAL '700 seconds'
 WHERE id = '10000000-0000-0000-0000-000000000003';
INSERT INTO scheduled_task (id, next_run_at, retry_at)
VALUES ('10000000-0000-0000-0000-000000000004',
        NOW() - INTERVAL '5000 seconds', NOW() - INTERVAL '1200 seconds');
INSERT INTO scheduled_task (id, next_run_at, lease_expires_at)
VALUES ('10000000-0000-0000-0000-000000000005', NOW() - INTERVAL '5000 seconds',
        NOW() + INTERVAL '700 seconds');
INSERT INTO scheduled_task (id, is_enabled, next_run_at)
VALUES ('10000000-0000-0000-0000-000000000006', FALSE, NOW() - INTERVAL '5000 seconds');
INSERT INTO scheduled_task (id, next_run_at, depends_on)
VALUES ('10000000-0000-0000-0000-000000000007', NOW() - INTERVAL '1800 seconds',
        ARRAY['20000000-0000-0000-0000-000000000001'::uuid]);
INSERT INTO scheduled_task (id, is_enabled, last_status)
VALUES ('20000000-0000-0000-0000-000000000001', FALSE, 'failed');
INSERT INTO scheduled_task (id, next_run_at, dependency_mode, run_window_at, depends_on)
VALUES ('10000000-0000-0000-0000-000000000008', NOW() - INTERVAL '1800 seconds',
        'same_window', NULL,
        ARRAY['20000000-0000-0000-0000-000000000002'::uuid]);
INSERT INTO scheduled_task (id, is_enabled, last_status)
VALUES ('20000000-0000-0000-0000-000000000002', FALSE, 'completed');
INSERT INTO scheduled_task (id, next_run_at, dependency_mode, run_window_at, depends_on)
SELECT '10000000-0000-0000-0000-000000000009', fixture.window_at,
       'same_window', fixture.window_at,
       ARRAY['20000000-0000-0000-0000-000000000002'::uuid]
FROM worker_progress_fixture_clock AS fixture;
INSERT INTO task_run (id, task_id, status, scheduled_for)
SELECT '30000000-0000-0000-0000-000000000001',
       '20000000-0000-0000-0000-000000000002', 'completed', fixture.window_at
FROM worker_progress_fixture_clock AS fixture;
INSERT INTO scheduled_task (id, next_run_at, allow_overlap, lease_expires_at)
VALUES ('10000000-0000-0000-0000-000000000010', NOW() - INTERVAL '1800 seconds',
        FALSE, NOW() + INTERVAL '700 seconds');
INSERT INTO task_run (id, task_id, status)
VALUES ('30000000-0000-0000-0000-000000000002',
        '10000000-0000-0000-0000-000000000010', 'running');
INSERT INTO task_run (id, task_id, status)
VALUES ('30000000-0000-0000-0000-000000000003',
        '10000000-0000-0000-0000-000000000005', 'running');
INSERT INTO scheduled_task (id) VALUES ('10000000-0000-0000-0000-000000000011');

INSERT INTO platform_event (status, created_at, lease_expires_at) VALUES
    ('pending', NOW() - INTERVAL '1200 seconds', NULL),
    ('pending', NOW() - INTERVAL '60 seconds', NULL),
    ('pending', NOW() + INTERVAL '600 seconds', NULL),
    ('processing', NOW() - INTERVAL '2400 seconds', NOW() + INTERVAL '600 seconds'),
    ('processing', NOW() - INTERVAL '1800 seconds', NOW() - INTERVAL '500 seconds'),
    ('completed', NOW() - INTERVAL '9000 seconds', NULL),
    ('dead_letter', NOW() - INTERVAL '9000 seconds', NULL);

INSERT INTO notification_outbox (status, available_at, lease_expires_at) VALUES
    ('pending', NOW() - INTERVAL '1400 seconds', NULL),
    ('pending', NOW() + INTERVAL '600 seconds', NULL),
    ('retryable', NOW() - INTERVAL '45 seconds', NULL),
    ('processing', NOW() - INTERVAL '2400 seconds', NOW() + INTERVAL '600 seconds'),
    ('processing', NOW() - INTERVAL '1800 seconds', NOW() - INTERVAL '500 seconds'),
    ('dead_letter', NOW() - INTERVAL '9000 seconds', NULL),
    ('resolved', NOW() - INTERVAL '9000 seconds', NULL);
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")

    container = f"kokonut-worker-progress-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    created = False
    try:
        run(
            [
                docker,
                "run",
                "-d",
                "--rm",
                "--network",
                "none",
                "--name",
                container,
                "-e",
                f"POSTGRES_PASSWORD={password}",
                args.image,
            ]
        )
        created = True
        wait_ready(docker, container)
        docker_sql(docker, container, SCHEMA_AND_FIXTURES)
        query = _progress_sql(WORKER_NAMES).replace("%s", "300", 1)
        output = docker_sql(
            docker,
            container,
            "\\pset format unaligned\n\\pset fieldsep '|'\n" + query + ";\n",
        )
        actual: dict[str, dict[str, int | None]] = {}
        for line in output.splitlines():
            fields = line.strip().split("|")
            if len(fields) != 5 or fields[0] not in WORKER_NAMES:
                continue
            worker, active, stale, queued, age = fields
            actual[worker] = {
                "active": int(active),
                "stale": int(stale),
                "queued": int(queued),
                "oldest_due_seconds": None if age == "" else int(age),
            }

        expected = {
            "events": {"active": 2, "stale": 1, "queued": 3, "oldest_due_seconds": 1200},
            "notifications": {
                "active": 2,
                "stale": 1,
                "queued": 2,
                "oldest_due_seconds": 1400,
            },
            "scheduler": {"active": 2, "stale": 0, "queued": 4, "oldest_due_seconds": 1800},
        }
        if actual != expected:
            raise RuntimeError(f"worker progress aggregate mismatch: {actual!r}")

        docker_sql(
            docker,
            container,
            "DELETE FROM platform_event;"
            "INSERT INTO platform_event (status, created_at) "
            "VALUES ('pending', NOW() + INTERVAL '600 seconds');",
        )
        future_event_query = _progress_sql(("events",)).replace("%s", "300", 1)
        future_event_output = docker_sql(
            docker,
            container,
            "\\pset format unaligned\n\\pset fieldsep '|'\n" + future_event_query + ";\n",
        )
        fields = next(
            line.split("|")
            for line in future_event_output.splitlines()
            if line.split("|")[0] == "events"
        )
        future_event = {
            "active": int(fields[1]),
            "stale": int(fields[2]),
            "queued": int(fields[3]),
            "oldest_due_seconds": None if fields[4] == "" else int(fields[4]),
        }
        if future_event != {
            "active": 0,
            "stale": 0,
            "queued": 1,
            "oldest_due_seconds": 0,
        }:
            raise RuntimeError(f"future-created event age was not clamped to zero: {future_event!r}")

        run([docker, "rm", "-f", container])
        remaining = subprocess.run(
            [docker, "inspect", container], text=True, capture_output=True, check=False
        )
        if remaining.returncode == 0:
            raise RuntimeError("disposable PostgreSQL container remained after cleanup")

        assertions = [
            "Event pending rows are counted by created_at; completed and dead-letter rows are excluded.",
            "Notification pending/retryable rows count only when available_at is due; future retries are excluded.",
            "Scheduler cadence and retry rows count only when due, enabled, unleased, dependency-ready, and overlap-eligible.",
            "Current leases are active, expired/missing leases are stale, and dead-letter rows are not queue backlog.",
            "Future-created pending events are counted but reported with age zero rather than a negative age.",
            "Probe returns aggregate counts/ages only, with no row identifiers or payload fields.",
            "PostgreSQL ran with Docker networking disabled and no published host port.",
            "Disposable container removal was verified before writing evidence.",
        ]
        evidence = {
            "status": "passed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "check": "standard_worker_due_backlog_age",
            "database": "network-disabled disposable PostgreSQL 16 container; no host port",
            "image": args.image,
            "thresholds_seconds": {"stale": 300, "backlog": 900},
            "expected": expected,
            "actual": actual,
            "assertions": assertions,
            "cleanup": {"container_removed": True, "container_absent_after_remove": True},
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(f"PASS: Standard worker backlog probe passed {len(assertions)} disposable PostgreSQL assertions")
        print(f"Evidence: {args.output.relative_to(ROOT)}")
        return 0
    except Exception as exc:  # noqa: BLE001 - disposable acceptance reports the actionable SQL failure.
        print(f"worker-progress disposable check failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1
    finally:
        if created:
            subprocess.run([docker, "rm", "-f", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
