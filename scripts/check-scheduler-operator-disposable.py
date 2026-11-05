#!/usr/bin/env python3
"""Verify migration 749 scheduler operator capabilities in network-disabled PostgreSQL."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import secrets
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_OUTBOX_SPEC = importlib.util.spec_from_file_location(
    "check_clickhouse_outbox_operator_disposable",
    Path(__file__).with_name("check-clickhouse-outbox-operator-disposable.py"),
)
if _OUTBOX_SPEC is None or _OUTBOX_SPEC.loader is None:
    raise RuntimeError("could not load the shared disposable PostgreSQL helpers")
outbox = importlib.util.module_from_spec(_OUTBOX_SPEC)
sys.modules[_OUTBOX_SPEC.name] = outbox
_OUTBOX_SPEC.loader.exec_module(outbox)

MIGRATION = ROOT / "schemas/postgres/749_scheduler_operator_actions.sql"
DEFAULT_OUTPUT = ROOT / (
    f"docs/refactor/builds/{datetime.now(timezone.utc):%Y-%m-%d}-recovery/"
    "scheduler-operator-749-disposable.json"
)
_TASK_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

SCHEDULER_FIXTURE = f"""
CREATE TABLE public.scheduled_task (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    is_enabled BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE ROLE kokonut_scheduler_login NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
INSERT INTO public.scheduled_task (id, name, is_enabled)
VALUES ('{_TASK_ID}', 'disposable-scheduled-task', TRUE);
"""

CAPABILITY_GRANTS = f"""
SELECT kokonut_security.grant_operator_global_capability(
    '{outbox._OPERATOR_ID}', 'scheduler:read',
    'Synthetic DBA reviewer', 'Disposable scheduler read acceptance'
);
SELECT kokonut_security.grant_operator_global_capability(
    '{outbox._OPERATOR_ID}', 'scheduler:enable',
    'Synthetic DBA reviewer', 'Disposable scheduler enable acceptance'
);
"""

AUTH_ACCEPTANCE = f"""
SET SESSION AUTHORIZATION kokonut_operator_auth;
DO $$
BEGIN
    IF NOT kokonut_security.operator_global_capability_allows(
        '{outbox._SESSION_HASH}', 'scheduler:read'
    ) THEN
        RAISE EXCEPTION 'scheduler read capability was not recognized';
    END IF;
    IF kokonut_security.operator_global_capability_allows(
        '{outbox._SESSION_HASH}', 'scheduler:disable'
    ) THEN
        RAISE EXCEPTION 'ungranted scheduler disable capability was recognized';
    END IF;
    IF has_function_privilege(
        current_user,
        'kokonut_security.audit_scheduler_operator_action(text,uuid,text,text)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'operator-auth can execute the scheduler mutation audit function';
    END IF;
    IF has_function_privilege(
        'kokonut_scheduler_login',
        'kokonut_security.audit_scheduler_operator_action(text,uuid,text,text)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'scheduler executor can execute the scheduler operator function';
    END IF;
END;
$$;
RESET SESSION AUTHORIZATION;
"""

ENABLE_ACCEPTANCE = f"""
SET SESSION AUTHORIZATION kokonut_runtime;
DO $$
BEGIN
    PERFORM kokonut_security.audit_scheduler_operator_action(
        '{outbox._SESSION_HASH}', '{_TASK_ID}', 'enable', 'Reviewed disposable enable'
    );
    BEGIN
        PERFORM kokonut_security.audit_scheduler_operator_action(
            '{outbox._SESSION_HASH}', '{_TASK_ID}', 'disable', 'Missing disable grant'
        );
        RAISE EXCEPTION 'ungranted scheduler disable action was accepted';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
    BEGIN
        PERFORM id FROM kokonut_security.scheduler_operator_audit;
        RAISE EXCEPTION 'runtime can read operator audit rows directly';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
END;
$$;
RESET SESSION AUTHORIZATION;
"""

DISABLE_ACCEPTANCE = f"""
SELECT kokonut_security.grant_operator_global_capability(
    '{outbox._OPERATOR_ID}', 'scheduler:disable',
    'Synthetic DBA reviewer', 'Disposable scheduler disable acceptance'
);
UPDATE public.scheduled_task SET is_enabled = FALSE WHERE id = '{_TASK_ID}';
SET SESSION AUTHORIZATION kokonut_runtime;
SELECT kokonut_security.audit_scheduler_operator_action(
    '{outbox._SESSION_HASH}', '{_TASK_ID}', 'disable', 'Reviewed disposable disable'
);
RESET SESSION AUTHORIZATION;
"""

FINAL_ASSERTIONS = f"""
DO $$
DECLARE
    audit_count INTEGER;
    action_owner TEXT;
BEGIN
    SELECT count(*) INTO audit_count
      FROM kokonut_security.scheduler_operator_audit
     WHERE operator_id = '{outbox._OPERATOR_ID}'
       AND scheduled_task_id = '{_TASK_ID}'
       AND reason LIKE 'Reviewed disposable %';
    IF audit_count <> 2 THEN
        RAISE EXCEPTION 'scheduler operator actions were not audited';
    END IF;
    IF (SELECT count(*) FROM kokonut_security.scheduler_operator_audit
         WHERE action IN ('enabled', 'disabled')) <> 2 THEN
        RAISE EXCEPTION 'scheduler action types are incorrect';
    END IF;
    SELECT pg_get_userbyid(proowner) INTO action_owner
      FROM pg_proc
     WHERE oid = 'kokonut_security.audit_scheduler_operator_action(text,uuid,text,text)'::regprocedure;
    IF action_owner <> 'kokonut_operator_capability_owner' THEN
        RAISE EXCEPTION 'scheduler audit function has an unexpected owner';
    END IF;
    IF has_table_privilege('kokonut_runtime', 'kokonut_security.scheduler_operator_audit', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'kokonut_security.scheduler_operator_audit', 'INSERT') THEN
        RAISE EXCEPTION 'runtime has direct scheduler audit relation privileges';
    END IF;
END;
$$;
"""


def wait_for_stable_postgres(docker: str, container: str) -> None:
    """Wait for TCP readiness after the PostGIS entrypoint's socket-only bootstrap."""
    deadline = time.monotonic() + 90
    consecutive_successes = 0
    while time.monotonic() < deadline:
        probe = subprocess.run(
            [
                docker,
                "exec",
                container,
                "pg_isready",
                "-h",
                "127.0.0.1",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-q",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if probe.returncode == 0:
            consecutive_successes += 1
            if consecutive_successes == 3:
                return
        else:
            consecutive_successes = 0
        time.sleep(1)
    raise RuntimeError("disposable PostgreSQL did not remain TCP-ready for three checks")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--image", default=outbox.DEFAULT_IMAGE)
    parser.add_argument("--platform", choices=("linux/amd64", "linux/arm64"))
    args = parser.parse_args()
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is unavailable")

    migration = MIGRATION.read_text(encoding="utf-8")
    dependency_migration = (
        ROOT / "schemas/postgres/746_clickhouse_outbox_operator_actions.sql"
    ).read_text(encoding="utf-8")
    container = f"kokonut-scheduler-operator-{secrets.token_hex(4)}"
    output = args.output or DEFAULT_OUTPUT
    created = False
    try:
        command = [docker, "run", "-d", "--rm", "--network", "none", "--name", container]
        if args.platform is not None:
            command.extend(("--platform", args.platform))
        command.extend(("-e", f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}", args.image))
        outbox.run(command)
        created = True
        wait_for_stable_postgres(docker, container)
        architecture = outbox.run([docker, "exec", container, "uname", "-m"]).strip()
        expected_architecture = {
            "linux/amd64": "x86_64",
            "linux/arm64": "aarch64",
        }.get(args.platform)
        if expected_architecture is not None and architecture != expected_architecture:
            raise RuntimeError("disposable PostgreSQL architecture mismatch")
        outbox.docker_sql(docker, container, outbox.FIXTURE)
        outbox.docker_sql(docker, container, SCHEDULER_FIXTURE)
        outbox.docker_sql(docker, container, dependency_migration)
        outbox.docker_sql(docker, container, migration)
        outbox.docker_sql(docker, container, CAPABILITY_GRANTS)
        outbox.docker_sql(docker, container, AUTH_ACCEPTANCE)
        outbox.docker_sql(docker, container, ENABLE_ACCEPTANCE)
        outbox.docker_sql(docker, container, DISABLE_ACCEPTANCE)
        outbox.docker_sql(docker, container, FINAL_ASSERTIONS)

        evidence = {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source_revision": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True
            ).stdout.strip(),
            "source_worktree_clean": outbox._worktree_clean(),
            "evidence_level": "disposable_acceptance",
            "kind": "scheduler-operator-migration-acceptance",
            "migration_id": "schema:749_scheduler_operator_actions.sql",
            "migration_sha256": hashlib.sha256(migration.encode("utf-8")).hexdigest(),
            "dependency_migration_id": "schema:746_clickhouse_outbox_operator_actions.sql",
            "dependency_migration_sha256": hashlib.sha256(
                dependency_migration.encode("utf-8")
            ).hexdigest(),
            "database_image": args.image,
            "requested_platform": args.platform,
            "container_architecture": architecture,
            "network": "disabled; no host ports published",
            "checks": [
                "migration 749 extends the reviewed global capability catalog with scheduler read/enable/disable actions",
                "operator-auth can check scheduler capabilities but cannot execute schedule mutation audit functions",
                "the dedicated scheduler executor login cannot execute the schedule administration function",
                "the runtime action is session-bound, capability-checked, and records operator, task, action, and reason",
                "ungranted actions fail closed and runtime has no direct scheduler audit-table access",
                "the security-definer audit function is owned by the unprivileged NOLOGIN capability owner",
            ],
            "candidate_legacy_production_touched": False,
            "result": "passed",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, sort_keys=True))
    finally:
        if created:
            subprocess.run([docker, "rm", "-f", container], text=True, capture_output=True, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
