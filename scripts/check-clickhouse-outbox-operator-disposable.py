#!/usr/bin/env python3
"""Verify migration 746's authenticated ClickHouse outbox operator boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/746_clickhouse_outbox_operator_actions.sql"
DEFAULT_OUTPUT = ROOT / (
    f"docs/refactor/builds/{datetime.now(timezone.utc):%Y-%m-%d}-recovery/"
    "clickhouse-outbox-operator-746-disposable.json"
)
DEFAULT_IMAGE = "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5"
_OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_SESSION_HASH = "a" * 64

FIXTURE = """
CREATE ROLE kokonut_runtime NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_operator_auth NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE SCHEMA kokonut_security;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_operator_auth;

CREATE TABLE public.operator_identity (
    id UUID PRIMARY KEY,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    display_name TEXT,
    email TEXT,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE public.operator_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id),
    session_token_hash CHAR(64) NOT NULL UNIQUE,
    csrf_token_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);
ALTER TABLE public.operator_identity ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_identity FORCE ROW LEVEL SECURITY;
ALTER TABLE public.operator_session ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_session FORCE ROW LEVEL SECURITY;

CREATE TABLE public.clickhouse_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_key VARCHAR(255) NOT NULL UNIQUE,
    source_table VARCHAR(100) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    target_table VARCHAR(100) NOT NULL,
    columns JSONB NOT NULL,
    rows JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'succeeded', 'retryable', 'dead_letter', 'resolved', 'discarded')),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_owner VARCHAR(100),
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE public.clickhouse_outbox_operator_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outbox_id UUID NOT NULL REFERENCES public.clickhouse_outbox(id),
    event_key VARCHAR(255) NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('replayed', 'resolved', 'discarded')),
    actor VARCHAR(255) NOT NULL CHECK (length(btrim(actor)) > 0),
    reason TEXT NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 2000),
    prior_attempt_count INTEGER NOT NULL CHECK (prior_attempt_count >= 0),
    payload_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON TABLE public.clickhouse_outbox TO kokonut_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON TABLE public.clickhouse_outbox_operator_audit TO kokonut_runtime;

INSERT INTO public.operator_identity (id, issuer, subject, enabled)
VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'https://identity.example', 'operator-1', TRUE);
INSERT INTO public.operator_session (
    operator_id, session_token_hash, csrf_token_hash, expires_at
) VALUES (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', repeat('a', 64), repeat('b', 64),
    NOW() + INTERVAL '1 hour'
);
INSERT INTO public.clickhouse_outbox (
    id, event_key, source_table, source_id, target_table, columns, rows,
    payload_hash, status, attempt_count
) VALUES
    ('b0000000-0000-4000-8000-000000000001', 'event-replay', 'sensor_reading', 'one',
     'sensor_readings', '["timestamp"]', '[["2026-11-03T00:00:00Z"]]', repeat('c', 64), 'dead_letter', 4),
    ('b0000000-0000-4000-8000-000000000002', 'event-resolve', 'sensor_reading', 'two',
     'sensor_readings', '["timestamp"]', '[["2026-11-03T00:00:00Z"]]', repeat('d', 64), 'dead_letter', 2),
    ('b0000000-0000-4000-8000-000000000003', 'event-discard', 'sensor_reading', 'three',
     'sensor_readings', '["timestamp"]', '[["2026-11-03T00:00:00Z"]]', repeat('e', 64), 'dead_letter', 3);
"""

AUTH_READ_ACCEPTANCE = f"""
SET SESSION AUTHORIZATION kokonut_operator_auth;
DO $$
BEGIN
    IF NOT kokonut_security.operator_global_capability_allows(
        '{_SESSION_HASH}', 'clickhouse_outbox:read'
    ) THEN
        RAISE EXCEPTION 'active operator read capability was not recognized';
    END IF;
    IF kokonut_security.operator_global_capability_allows(
        '{_SESSION_HASH}', 'clickhouse_outbox:replay'
    ) THEN
        RAISE EXCEPTION 'ungranted operator replay capability was recognized';
    END IF;
    IF has_function_privilege(
        current_user,
        'kokonut_security.resolve_clickhouse_outbox_operator_session(text)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'operator-auth can execute the internal session resolver';
    END IF;
    BEGIN
        PERFORM id FROM public.operator_identity;
        RAISE EXCEPTION 'operator-auth has direct identity-table access';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
END;
$$;
RESET SESSION AUTHORIZATION;
"""

ACTION_DENIAL_ACCEPTANCE = f"""
SET SESSION AUTHORIZATION kokonut_clickhouse_outbox_operator_login;
DO $$
DECLARE
    page JSONB;
BEGIN
    page := kokonut_security.list_clickhouse_outbox_operator_dead_letters('{_SESSION_HASH}', 10);
    IF jsonb_array_length(page -> 'items') <> 3
       OR page -> 'capabilities' ->> 'replay' <> 'false' THEN
        RAISE EXCEPTION 'operator dead-letter read projection or capability set is incorrect';
    END IF;
    BEGIN
        PERFORM kokonut_security.list_clickhouse_outbox_operator_dead_letters('{_SESSION_HASH}', NULL);
        RAISE EXCEPTION 'NULL list limit was accepted';
    EXCEPTION WHEN SQLSTATE '22023' THEN
        NULL;
    END;
    BEGIN
        PERFORM kokonut_security.list_clickhouse_outbox_operator_dead_letters('{_SESSION_HASH}', 101);
        RAISE EXCEPTION 'oversized list limit was accepted';
    EXCEPTION WHEN SQLSTATE '22023' THEN
        NULL;
    END;
    BEGIN
        PERFORM kokonut_security.transition_clickhouse_outbox_operator_dead_letter(
            '{_SESSION_HASH}', 'b0000000-0000-4000-8000-000000000001', 'replay', 'unauthorized'
        );
        RAISE EXCEPTION 'ungranted replay action was accepted';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
    BEGIN
        PERFORM kokonut_security.transition_clickhouse_outbox_operator_dead_letter(
            '{_SESSION_HASH}', 'b0000000-0000-4000-8000-000000000001', NULL, 'invalid'
        );
        RAISE EXCEPTION 'NULL transition action was accepted';
    EXCEPTION WHEN SQLSTATE '22023' THEN
        NULL;
    END;
    BEGIN
        PERFORM kokonut_security.transition_clickhouse_outbox_operator_dead_letter(
            '{_SESSION_HASH}', 'b0000000-0000-4000-8000-000000000001', 'discard', repeat('x', 2001)
        );
        RAISE EXCEPTION 'oversized action reason was accepted';
    EXCEPTION WHEN SQLSTATE '22023' THEN
        NULL;
    END;
    BEGIN
        PERFORM id FROM public.clickhouse_outbox;
        RAISE EXCEPTION 'operator login has direct outbox-table access';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
END;
$$;
RESET SESSION AUTHORIZATION;
"""

ACTION_ACCEPTANCE = f"""
SET SESSION AUTHORIZATION kokonut_clickhouse_outbox_operator_login;
DO $$
DECLARE
    page JSONB;
    result JSONB;
BEGIN
    page := kokonut_security.list_clickhouse_outbox_operator_dead_letters('{_SESSION_HASH}', 3);
    IF jsonb_array_length(page -> 'items') <> 3
       OR page -> 'capabilities' ->> 'replay' <> 'true'
       OR page -> 'capabilities' ->> 'resolve' <> 'true'
       OR page -> 'capabilities' ->> 'discard' <> 'true' THEN
        RAISE EXCEPTION 'operator dead-letter page omitted granted capabilities';
    END IF;
    result := kokonut_security.transition_clickhouse_outbox_operator_dead_letter(
        '{_SESSION_HASH}', 'b0000000-0000-4000-8000-000000000001', 'replay', 'reviewed replay'
    );
    IF result ->> 'status' <> 'pending' OR result ->> 'action' <> 'replayed' THEN
        RAISE EXCEPTION 'replay did not requeue the dead-letter row';
    END IF;
    result := kokonut_security.transition_clickhouse_outbox_operator_dead_letter(
        '{_SESSION_HASH}', 'b0000000-0000-4000-8000-000000000002', 'resolve', 'reviewed resolution'
    );
    IF result ->> 'status' <> 'resolved' OR result ->> 'action' <> 'resolved' THEN
        RAISE EXCEPTION 'resolve did not close the dead-letter row';
    END IF;
    result := kokonut_security.transition_clickhouse_outbox_operator_dead_letter(
        '{_SESSION_HASH}', 'b0000000-0000-4000-8000-000000000003', 'discard', 'reviewed discard'
    );
    IF result ->> 'status' <> 'discarded' OR result ->> 'action' <> 'discarded' THEN
        RAISE EXCEPTION 'discard did not close the dead-letter row';
    END IF;
END;
$$;
RESET SESSION AUTHORIZATION;
"""

RUNTIME_ACCEPTANCE = """
SET SESSION AUTHORIZATION kokonut_runtime;
DO $$
DECLARE affected INTEGER;
BEGIN
    INSERT INTO public.clickhouse_outbox (
        event_key, source_table, source_id, target_table, columns, rows, payload_hash
    ) VALUES (
        'runtime-enqueue', 'sensor_reading', 'runtime', 'sensor_readings',
        '["timestamp"]', '[["2026-11-03T00:00:00Z"]]', repeat('f', 64)
    );
    UPDATE public.clickhouse_outbox
       SET updated_at = NOW()
     WHERE event_key = 'runtime-enqueue';
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 1 THEN
        RAISE EXCEPTION 'runtime lost the bounded enqueue timestamp update';
    END IF;
    BEGIN
        UPDATE public.clickhouse_outbox SET status = 'resolved' WHERE event_key = 'runtime-enqueue';
        RAISE EXCEPTION 'runtime can directly transition outbox state';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
    BEGIN
        DELETE FROM public.clickhouse_outbox WHERE event_key = 'runtime-enqueue';
        RAISE EXCEPTION 'runtime can directly delete outbox rows';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
    BEGIN
        INSERT INTO public.clickhouse_outbox_operator_audit (
            outbox_id, event_key, action, actor, reason, prior_attempt_count, payload_hash
        ) SELECT id, event_key, 'resolved', 'runtime', 'must deny', attempt_count, payload_hash
          FROM public.clickhouse_outbox WHERE event_key = 'runtime-enqueue';
        RAISE EXCEPTION 'runtime can write operator audit rows';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
END;
$$;
RESET SESSION AUTHORIZATION;
"""

REVOKE_REPLAY = f"""
DO $$
DECLARE replay_capability_id UUID;
BEGIN
    SELECT id INTO replay_capability_id
      FROM kokonut_security.operator_global_capability
     WHERE operator_id = '{_OPERATOR_ID}'
       AND capability_code = 'clickhouse_outbox:replay'
       AND revoked_at IS NULL;
    IF replay_capability_id IS NULL THEN
        RAISE EXCEPTION 'active replay capability was not found for revocation';
    END IF;
    PERFORM kokonut_security.revoke_operator_global_capability(
        replay_capability_id, 'Synthetic DBA reviewer', 'Revoke disposable replay capability'
    );
END;
$$;

SET SESSION AUTHORIZATION kokonut_operator_auth;
DO $$
BEGIN
    IF kokonut_security.operator_global_capability_allows(
        '{_SESSION_HASH}', 'clickhouse_outbox:replay'
    ) THEN
        RAISE EXCEPTION 'revoked operator capability remains active';
    END IF;
END;
$$;
RESET SESSION AUTHORIZATION;
"""

FINAL_ASSERTIONS = f"""
DO $$
DECLARE
    capability_owner TEXT;
    action_owner TEXT;
    audit_count INTEGER;
    capability_audit_count INTEGER;
BEGIN
    IF (SELECT status FROM public.clickhouse_outbox WHERE event_key = 'event-replay') <> 'pending'
       OR (SELECT attempt_count FROM public.clickhouse_outbox WHERE event_key = 'event-replay') <> 0
       OR (SELECT last_error FROM public.clickhouse_outbox WHERE event_key = 'event-replay') IS NOT NULL
       OR (SELECT status FROM public.clickhouse_outbox WHERE event_key = 'event-resolve') <> 'resolved'
       OR (SELECT status FROM public.clickhouse_outbox WHERE event_key = 'event-discard') <> 'discarded' THEN
        RAISE EXCEPTION 'outbox operator state transitions are incorrect';
    END IF;
    SELECT count(*) INTO audit_count
      FROM public.clickhouse_outbox_operator_audit
     WHERE operator_id = '{_OPERATOR_ID}'
       AND actor = 'operator:{_OPERATOR_ID}'
       AND reason LIKE 'reviewed %';
    IF audit_count <> 3 THEN
        RAISE EXCEPTION 'operator transition audit attribution or count is incorrect';
    END IF;
    SELECT count(*) INTO capability_audit_count
      FROM kokonut_security.operator_global_capability_audit
     WHERE operator_id = '{_OPERATOR_ID}';
    IF capability_audit_count <> 5 THEN
        RAISE EXCEPTION 'capability grant/revoke audit history is incomplete';
    END IF;
    IF (SELECT count(*) FROM kokonut_security.operator_global_capability
         WHERE operator_id = '{_OPERATOR_ID}' AND revoked_at IS NULL) <> 3 THEN
        RAISE EXCEPTION 'capability revoke did not preserve only the remaining grants';
    END IF;
    SELECT pg_get_userbyid(proowner) INTO capability_owner
      FROM pg_proc
     WHERE oid = 'kokonut_security.revoke_operator_global_capability(uuid,text,text)'::regprocedure;
    SELECT pg_get_userbyid(proowner) INTO action_owner
      FROM pg_proc
     WHERE oid = 'kokonut_security.transition_clickhouse_outbox_operator_dead_letter(text,uuid,text,text)'::regprocedure;
    IF capability_owner <> 'kokonut_operator_capability_owner'
       OR action_owner <> 'kokonut_clickhouse_outbox_operator_owner' THEN
        RAISE EXCEPTION 'operator functions have incorrect NOLOGIN owners';
    END IF;
    IF has_table_privilege('kokonut_runtime', 'public.clickhouse_outbox', 'UPDATE')
       OR NOT has_column_privilege('kokonut_runtime', 'public.clickhouse_outbox', 'updated_at', 'UPDATE')
       OR has_table_privilege('kokonut_runtime', 'public.clickhouse_outbox_operator_audit', 'INSERT') THEN
        RAISE EXCEPTION 'runtime role has broader outbox privileges than enqueue needs';
    END IF;
    IF has_table_privilege('kokonut_clickhouse_outbox_operator_login', 'public.clickhouse_outbox', 'SELECT')
       OR has_table_privilege('kokonut_clickhouse_outbox_operator_login', 'public.clickhouse_outbox', 'UPDATE')
       OR has_table_privilege('kokonut_clickhouse_outbox_operator_login', 'public.clickhouse_outbox_operator_audit', 'INSERT')
       OR has_table_privilege('kokonut_operator_auth', 'public.operator_session', 'SELECT') THEN
        RAISE EXCEPTION 'operator logins retain direct relation privileges';
    END IF;
END;
$$;
"""


def _safe_command(command: list[str]) -> list[str]:
    return [
        "POSTGRES_PASSWORD=<redacted>" if item.startswith("POSTGRES_PASSWORD=") else item
        for item in command
    ]


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"disposable command failed ({result.returncode}): {' '.join(_safe_command(command))}\n{details}"
        )
    return result.stdout


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
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                docker,
                "exec",
                container,
                "psql",
                "-X",
                "-q",
                "-t",
                "-A",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-c",
                "SELECT 1",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip() == "1":
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def _source_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def _worktree_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return not result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--platform", choices=("linux/amd64", "linux/arm64"))
    args = parser.parse_args()
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is unavailable")

    migration = MIGRATION.read_text(encoding="utf-8")
    container = f"kokonut-outbox-operator-{secrets.token_hex(4)}"
    output = args.output or DEFAULT_OUTPUT
    created = False
    try:
        command = [
            docker,
            "run",
            "-d",
            "--rm",
            "--network",
            "none",
            "--name",
            container,
        ]
        if args.platform is not None:
            command.extend(("--platform", args.platform))
        command.extend(
            (
                "-e",
                f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}",
                args.image,
            )
        )
        run(command)
        created = True
        wait_ready(docker, container)
        architecture = run([docker, "exec", container, "uname", "-m"]).strip()
        expected_architecture = {
            "linux/amd64": "x86_64",
            "linux/arm64": "aarch64",
        }.get(args.platform)
        if expected_architecture is not None and architecture != expected_architecture:
            raise RuntimeError("disposable PostgreSQL architecture mismatch")

        docker_sql(docker, container, FIXTURE)
        docker_sql(
            docker,
            container,
            migration,
        )
        docker_sql(
            docker,
            container,
            "SELECT kokonut_security.grant_operator_global_capability("
            f"'{_OPERATOR_ID}', 'clickhouse_outbox:read', "
            "'Synthetic DBA reviewer', 'Read-only acceptance grant');",
        )
        docker_sql(docker, container, AUTH_READ_ACCEPTANCE)
        docker_sql(docker, container, ACTION_DENIAL_ACCEPTANCE)
        for capability in ("replay", "resolve", "discard"):
            docker_sql(
                docker,
                container,
                "SELECT kokonut_security.grant_operator_global_capability("
                f"'{_OPERATOR_ID}', 'clickhouse_outbox:{capability}', "
                f"'Synthetic DBA reviewer', 'Disposable {capability} acceptance grant');",
            )
        docker_sql(docker, container, ACTION_ACCEPTANCE)
        docker_sql(docker, container, RUNTIME_ACCEPTANCE)
        docker_sql(docker, container, REVOKE_REPLAY)
        docker_sql(docker, container, FINAL_ASSERTIONS)

        evidence = {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source_revision": _source_revision(),
            "source_worktree_clean": _worktree_clean(),
            "evidence_level": "disposable_acceptance",
            "kind": "clickhouse-outbox-operator-migration-acceptance",
            "migration_id": "schema:746_clickhouse_outbox_operator_actions.sql",
            "migration_sha256": hashlib.sha256(migration.encode("utf-8")).hexdigest(),
            "database_image": args.image,
            "requested_platform": args.platform,
            "container_architecture": architecture,
            "network": "disabled; no host ports published",
            "checks": [
                "migration 746 creates the separated NOLOGIN owners and a provisionable action login",
                "capability grants and revocations are DBA-only, session-bound, audited, and enforced by bounded functions",
                "operator-auth can check only the global capability function and cannot read operator tables directly",
                "the action login can list only bounded dead-letter projections and cannot access tables directly",
                "replay, resolve, and discard require distinct capabilities and append operator-attributed audit rows",
                "NULL/oversized page limits, NULL/unknown actions, and oversized reasons fail closed",
                "runtime retains outbox enqueue plus updated_at only and cannot transition rows or write operator audit",
                "operator and capability function ownership matches runtime-role declarations",
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
