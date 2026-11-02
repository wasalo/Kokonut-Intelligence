#!/usr/bin/env python3
"""Exercise migration 701 in a network-isolated disposable PostgreSQL 16."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/701_location_scoped_extension_learning_writes.sql"
IMAGE = os.environ.get("EXTENSION_LEARNING_TEST_IMAGE", "postgres:16")

ORG_A = "a0000000-0000-4000-8000-000000000101"
ORG_B = "a0000000-0000-4000-8000-000000000102"
LOCATION_A = "a0000000-0000-4000-8000-000000000201"
LOCATION_B = "a0000000-0000-4000-8000-000000000202"
OPERATOR_A = "a0000000-0000-4000-8000-000000000301"
OPERATOR_B = "a0000000-0000-4000-8000-000000000302"
MODULE_A = "a0000000-0000-4000-8000-000000000401"
PROGRESS_A = "a0000000-0000-4000-8000-000000000501"
PROGRESS_B = "a0000000-0000-4000-8000-000000000502"


def run(command: list[str], *, input_text: str | None = None, check: bool = True):
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False
    )
    if check and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"command failed ({result.returncode}): {command[0]} {command[1]} …\n{details}"
        )
    return result


def docker_sql(container: str, statement: str, *, check: bool = True):
    return run(
        [
            "docker", "exec", "-i", container, "psql", "-X", "-q", "-A", "-t",
            "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
        ],
        input_text="\\set VERBOSITY verbose\n" + statement,
        check=check,
    )


def last_line(result) -> str:
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise AssertionError("PostgreSQL returned no result row")
    return lines[-1]


def expect_sqlstate(container: str, statement: str, sqlstate: str, label: str) -> None:
    result = docker_sql(container, statement, check=False)
    output = result.stdout + result.stderr
    if result.returncode == 0 or sqlstate not in output:
        raise AssertionError(
            f"{label}: expected SQLSTATE {sqlstate}, got rc={result.returncode}: {output}"
        )


FIXTURE = f"""
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA kokonut_security;
CREATE ROLE kokonut_runtime NOLOGIN;
CREATE ROLE kokonut_directus_runtime NOLOGIN;
CREATE TABLE organization (id UUID PRIMARY KEY, status TEXT NOT NULL);
CREATE TABLE location (
    id UUID PRIMARY KEY, organization_id UUID NOT NULL REFERENCES organization(id),
    status TEXT NOT NULL
);
CREATE TABLE operator_identity (id UUID PRIMARY KEY, enabled BOOLEAN NOT NULL);
CREATE TABLE operator_organization_membership (
    operator_id UUID NOT NULL REFERENCES operator_identity(id),
    organization_id UUID NOT NULL REFERENCES organization(id), revoked_at TIMESTAMPTZ
);
CREATE TABLE location_tenant_owner_verification (
    location_id UUID NOT NULL REFERENCES location(id),
    organization_id UUID NOT NULL REFERENCES organization(id), revoked_at TIMESTAMPTZ
);
CREATE TABLE location_organization_share (
    location_id UUID NOT NULL REFERENCES location(id),
    organization_id UUID NOT NULL REFERENCES organization(id),
    revoked_at TIMESTAMPTZ, expires_at TIMESTAMPTZ
);
CREATE TABLE operator_scope_grant (
    operator_id UUID NOT NULL REFERENCES operator_identity(id),
    resource TEXT NOT NULL, action TEXT NOT NULL,
    location_id UUID NOT NULL REFERENCES location(id),
    organization_id UUID, revoked_at TIMESTAMPTZ
);
CREATE FUNCTION public.operator_scope_grant_allows(
    requested_operator UUID, requested_resource TEXT, requested_action TEXT,
    requested_location UUID
) RETURNS BOOLEAN LANGUAGE SQL STABLE SECURITY INVOKER AS $$
    SELECT EXISTS (
        SELECT 1 FROM operator_scope_grant grant_row
        JOIN operator_identity identity ON identity.id = grant_row.operator_id AND identity.enabled
        JOIN location loc ON loc.id = grant_row.location_id
        WHERE grant_row.operator_id = requested_operator
          AND grant_row.resource = requested_resource
          AND grant_row.action = requested_action
          AND grant_row.location_id = requested_location
          AND grant_row.revoked_at IS NULL
          AND (
            grant_row.organization_id IS NULL OR (
              grant_row.organization_id = loc.organization_id
              AND EXISTS (
                SELECT 1 FROM operator_organization_membership membership
                JOIN organization tenant ON tenant.id = membership.organization_id
                  AND tenant.status = 'active'
                JOIN location_tenant_owner_verification owner
                  ON owner.location_id = loc.id
                 AND owner.organization_id = loc.organization_id
                 AND owner.revoked_at IS NULL
                WHERE membership.operator_id = requested_operator
                  AND membership.organization_id = grant_row.organization_id
                  AND membership.revoked_at IS NULL
              )
            )
          )
    );
$$;
CREATE TABLE public.peer_network (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    network_name VARCHAR(255) NOT NULL, description TEXT,
    network_type VARCHAR(100) NOT NULL,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    max_members INTEGER, meeting_cadence VARCHAR(100), language VARCHAR(50) DEFAULT 'en',
    status VARCHAR(50) DEFAULT 'active', metadata JSONB DEFAULT '{{}}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE public.learning_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id),
    module_id UUID NOT NULL,
    farmer_name VARCHAR(255) NOT NULL,
    progress_pct NUMERIC(5,2) DEFAULT 0 CHECK (progress_pct >= 0 AND progress_pct <= 100),
    score NUMERIC(5,2) CHECK (score >= 0 AND score <= 100),
    time_spent_min INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ DEFAULT NOW(), completed_at TIMESTAMPTZ,
    attempts INTEGER DEFAULT 1,
    status VARCHAR(50) DEFAULT 'in_progress', metadata JSONB DEFAULT '{{}}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('not_started','in_progress','completed','failed','expired'))
);
CREATE FUNCTION kokonut_security.current_tenant_context()
RETURNS TABLE (tenant_id UUID, location_id UUID, actor_id UUID, actor_type TEXT)
LANGUAGE SQL STABLE SECURITY DEFINER AS $$
    SELECT NULL::UUID,
           NULLIF(current_setting('test.location_id', TRUE), '')::UUID,
           NULLIF(current_setting('test.actor_id', TRUE), '')::UUID,
           NULLIF(current_setting('test.actor_type', TRUE), '')::TEXT
$$;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_runtime;
INSERT INTO organization VALUES ('{ORG_A}', 'active'), ('{ORG_B}', 'active');
INSERT INTO location VALUES
    ('{LOCATION_A}', '{ORG_A}', 'active'), ('{LOCATION_B}', '{ORG_B}', 'active');
INSERT INTO operator_identity VALUES ('{OPERATOR_A}', TRUE), ('{OPERATOR_B}', TRUE);
INSERT INTO operator_organization_membership VALUES
    ('{OPERATOR_A}', '{ORG_A}', NULL), ('{OPERATOR_B}', '{ORG_B}', NULL);
INSERT INTO location_tenant_owner_verification VALUES
    ('{LOCATION_A}', '{ORG_A}', NULL), ('{LOCATION_B}', '{ORG_B}', NULL);
INSERT INTO operator_scope_grant VALUES
    ('{OPERATOR_A}', 'extension_learning', 'create_peer_network', '{LOCATION_A}', '{ORG_A}', NULL),
    ('{OPERATOR_A}', 'extension_learning', 'update_progress', '{LOCATION_A}', '{ORG_A}', NULL);
INSERT INTO learning_progress
    (id, location_id, module_id, farmer_name, progress_pct, score, time_spent_min,
     status, metadata)
VALUES
    ('{PROGRESS_A}', '{LOCATION_A}', '{MODULE_A}', 'private synthetic participant',
     10, NULL, 5, 'in_progress', '{{"existing":"retained","nested":{{"old":true}}}}'),
    ('{PROGRESS_B}', '{LOCATION_B}', '{MODULE_A}', 'other synthetic participant',
     0, NULL, 0, 'not_started', '{{}}');
"""


def operator_call(container: str, actor: str, location: str, expression: str) -> str:
    statement = f"""
        SET ROLE kokonut_runtime;
        SELECT set_config('test.actor_id', '{actor}', FALSE);
        SELECT set_config('test.location_id', '{location}', FALSE);
        SELECT set_config('test.actor_type', 'operator', FALSE);
        SELECT row_to_json(result)::TEXT FROM {expression} AS result;
        RESET ROLE;
    """
    return last_line(docker_sql(container, statement))


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-extension-learning-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    started = False
    assertions: list[str] = []
    try:
        run([
            docker, "run", "--detach", "--rm", "--network", "none", "--name", container,
            "--env", f"POSTGRES_PASSWORD={password}", IMAGE,
        ])
        started = True
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            ready = subprocess.run(
                [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
                text=True, capture_output=True, check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("disposable PostgreSQL 16 did not become ready")

        docker_sql(container, FIXTURE)
        docker_sql(container, MIGRATION.read_text())
        docker_sql(container, MIGRATION.read_text())
        assertions.append("migration 701 applied and replayed transactionally on network-disabled PostgreSQL 16")

        acl = last_line(docker_sql(container, """
            SELECT has_function_privilege('kokonut_runtime',
                'kokonut_security.create_extension_peer_network(uuid,uuid,text,text,text,integer,text,text,jsonb)', 'EXECUTE')
               AND has_function_privilege('kokonut_runtime',
                'kokonut_security.update_extension_learning_progress(uuid,uuid,uuid,text,numeric,numeric,integer,jsonb)', 'EXECUTE')
               AND NOT has_table_privilege('kokonut_runtime', 'public.extension_peer_network_create_receipt', 'SELECT')
               AND NOT has_table_privilege('kokonut_runtime', 'public.extension_learning_progress_update_receipt', 'SELECT')
               AND NOT has_function_privilege('kokonut_directus_runtime',
                'kokonut_security.create_extension_peer_network(uuid,uuid,text,text,text,integer,text,text,jsonb)', 'EXECUTE');
        """))
        if acl != "t":
            raise AssertionError(f"bounded function/receipt ACL failed: {acl}")
        assertions.append("runtime can execute the two bounded functions, Directus cannot, and receipt ledgers are private")

        request_id = "a0000000-0000-4000-8000-000000000601"
        create_call = (
            f"kokonut_security.create_extension_peer_network("
            f"'{LOCATION_A}', '{request_id}', 'Learning circle', 'A synthetic group', "
            f"'learning_group', 12, 'weekly', 'en', '{{\"origin\":\"test\"}}'::jsonb)"
        )
        first = json.loads(operator_call(container, OPERATOR_A, LOCATION_A, create_call))
        replay = json.loads(operator_call(container, OPERATOR_A, LOCATION_A, create_call))
        if first["created"] is not True or replay["created"] is not False or first["peer_network_id"] != replay["peer_network_id"]:
            raise AssertionError("peer-network create and idempotent replay contract failed")
        count = last_line(docker_sql(container, f"SELECT COUNT(*) FROM peer_network WHERE location_id = '{LOCATION_A}';"))
        if count != "1":
            raise AssertionError("peer-network replay created duplicate rows")
        assertions.append("peer-network create is location-bound and exact retries return the original receipt without duplication")
        expect_sqlstate(container,
            f"UPDATE public.extension_peer_network_create_receipt SET network_name=network_name WHERE request_id='{request_id}';",
            "55000", "immutable peer-network receipt")

        conflict_call = create_call.replace("Learning circle", "Different circle")
        expect_sqlstate(container,
            f"SET ROLE kokonut_runtime; SELECT set_config('test.actor_id','{OPERATOR_A}',FALSE); "
            f"SELECT set_config('test.location_id','{LOCATION_A}',FALSE); SELECT set_config('test.actor_type','operator',FALSE); SELECT * FROM {conflict_call};",
            "23505", "peer-network idempotency content conflict")
        expect_sqlstate(container,
            f"SET ROLE kokonut_runtime; SELECT set_config('test.actor_id','{OPERATOR_B}',FALSE); "
            f"SELECT set_config('test.location_id','{LOCATION_A}',FALSE); SELECT set_config('test.actor_type','operator',FALSE); SELECT * FROM {create_call};",
            "42501", "peer-network missing grant")
        expect_sqlstate(container,
            f"SET ROLE kokonut_runtime; SELECT set_config('test.actor_id','{OPERATOR_A}',FALSE); "
            f"SELECT set_config('test.location_id','{LOCATION_B}',FALSE); SELECT set_config('test.actor_type','operator',FALSE); SELECT * FROM {create_call};",
            "42501", "peer-network signed location mismatch")
        assertions.append("content collisions, missing exact grants, and signed-location mismatch fail closed")

        progress_request = "a0000000-0000-4000-8000-000000000602"
        progress_call = (
            f"kokonut_security.update_extension_learning_progress("
            f"'{LOCATION_A}', '{PROGRESS_A}', '{progress_request}', 'completed', 88.5, 75, 20, "
            "'{\"nested\":{\"new\":true},\"reviewed\":\"yes\"}'::jsonb)"
        )
        updated = json.loads(operator_call(container, OPERATOR_A, LOCATION_A, progress_call))
        replayed_update = json.loads(operator_call(container, OPERATOR_A, LOCATION_A, progress_call))
        expected_fields = {
            "progress_id", "location_id", "module_id", "progress_pct", "score",
            "time_spent_min", "status", "completed_at", "updated_at", "request_id",
        }
        if set(updated) != expected_fields or "farmer_name" in updated:
            raise AssertionError("progress update response is not the exact identity-minimized contract")
        if updated != replayed_update:
            raise AssertionError("progress replay did not return the original response snapshot")
        if updated["progress_pct"] != 75 or updated["score"] != 88.5 or updated["time_spent_min"] != 25 or updated["status"] != "completed" or updated["completed_at"] is None:
            raise AssertionError("progress mutation did not apply requested values and completion timestamp")
        row = json.loads(last_line(docker_sql(container, f"""
            SELECT row_to_json(progress)::TEXT FROM learning_progress AS progress
             WHERE progress.id = '{PROGRESS_A}';
        """)))
        if row["farmer_name"] != "private synthetic participant" or row["time_spent_min"] != 25:
            raise AssertionError("progress mutation changed participant identity or applied time delta incorrectly")
        if row["metadata"] != {"existing": "retained", "nested": {"new": True}, "reviewed": "yes"}:
            raise AssertionError(f"progress metadata merge did not preserve existing fields: {row['metadata']!r}")
        expect_sqlstate(container,
            f"DELETE FROM public.extension_learning_progress_update_receipt WHERE request_id='{progress_request}';",
            "55000", "immutable progress receipt")
        assertions.append("progress update preserves legacy completion/metadata semantics, accumulates time once, and omits identity")

        conflicting_update = progress_call.replace("88.5", "89.5")
        expect_sqlstate(container,
            f"SET ROLE kokonut_runtime; SELECT set_config('test.actor_id','{OPERATOR_A}',FALSE); "
            f"SELECT set_config('test.location_id','{LOCATION_A}',FALSE); SELECT set_config('test.actor_type','operator',FALSE); SELECT * FROM {conflicting_update};",
            "23505", "progress idempotency content conflict")
        cross_location_progress = progress_call.replace(PROGRESS_A, PROGRESS_B).replace(progress_request, "a0000000-0000-4000-8000-000000000603")
        expect_sqlstate(container,
            f"SET ROLE kokonut_runtime; SELECT set_config('test.actor_id','{OPERATOR_A}',FALSE); "
            f"SELECT set_config('test.location_id','{LOCATION_A}',FALSE); SELECT set_config('test.actor_type','operator',FALSE); SELECT * FROM {cross_location_progress};",
            "P0002", "progress from another location")
        invalid_progress = progress_call.replace("'completed', 88.5", "'not_a_status', 88.5").replace(progress_request, "a0000000-0000-4000-8000-000000000604")
        expect_sqlstate(container,
            f"SET ROLE kokonut_runtime; SELECT set_config('test.actor_id','{OPERATOR_A}',FALSE); "
            f"SELECT set_config('test.location_id','{LOCATION_A}',FALSE); SELECT set_config('test.actor_type','operator',FALSE); SELECT * FROM {invalid_progress};",
            "22023", "invalid progress status")
        assertions.append("progress conflicts, cross-location IDs, and invalid lifecycle values are rejected without extra writes")

        for relation, statement in (
            ("peer network", f"INSERT INTO public.peer_network (network_name,network_type,location_id) VALUES ('denied','other','{LOCATION_A}')"),
            ("learning progress", f"UPDATE public.learning_progress SET status='completed' WHERE id='{PROGRESS_A}'"),
        ):
            result = docker_sql(container, f"SET ROLE kokonut_runtime; {statement};", check=False)
            if result.returncode == 0 or "permission denied" not in (result.stdout + result.stderr).lower():
                raise AssertionError(f"runtime direct {relation} mutation unexpectedly succeeded")
        assertions.append("runtime direct table writes remain denied in the isolated privilege fixture")

        report = {
            "result": "passed",
            "migration": MIGRATION.name,
            "database": "network-disabled disposable PostgreSQL 16 container",
            "candidate_legacy_production_touched": False,
            "assertions": assertions,
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    finally:
        if started:
            subprocess.run([docker, "stop", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"extension-learning disposable check failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
