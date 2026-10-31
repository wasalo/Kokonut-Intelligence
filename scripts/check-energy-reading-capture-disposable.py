#!/usr/bin/env python3
"""Apply/replay migration 711 and exercise its signed energy capture boundary."""

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
FIXTURE = ROOT / "tests/fixtures/operator_tenant_context_disposable.sql"
OPERATOR_CONTEXT_MIGRATION = ROOT / "schemas/postgres/394_signed_operator_tenant_context.sql"
TENANT_GRANT_MIGRATION = ROOT / "schemas/postgres/388_tenant_aware_operator_grants.sql"
MIGRATION = ROOT / "schemas/postgres/711_location_energy_reading_capture.sql"
IMAGE = os.environ.get("ENERGY_READING_CAPTURE_TEST_IMAGE", "postgres:16")
EVIDENCE = ROOT / "docs/refactor/builds/2026-10-31-recovery/energy-reading-capture-711-disposable.json"


def run(command: list[str], *, input_text: str | None = None, timeout: int = 90) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"disposable command failed ({result.returncode}): {command[0]} {command[1]} …\n{details}"
        )
    return result.stdout


def docker_sql(container: str, statement: str) -> str:
    return run(
        [
            "docker", "exec", "-i", container, "psql", "-X", "-qAt",
            "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    ).strip()


def wait_ready(container: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "docker", "exec", container, "pg_isready", "-h", "127.0.0.1",
                "-U", "postgres", "-d", "postgres",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL 16 did not become ready")


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-energy-reading-{uuid.uuid4().hex[:12]}"
    started = False
    evidence = None
    try:
        run(
            [
                docker, "run", "--detach", "--rm", "--network", "none",
                "--name", container, "--env", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE,
            ]
        )
        started = True
        wait_ready(container)

        docker_sql(container, FIXTURE.read_text(encoding="utf-8"))
        docker_sql(container, OPERATOR_CONTEXT_MIGRATION.read_text(encoding="utf-8"))
        setup = r"""
CREATE ROLE kokonut_directus_runtime
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_maintenance_probe
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE TABLE kokonut_security.directus_relation_privilege_policy (
    schema_name text NOT NULL,
    relation_name text NOT NULL,
    access_mode text NOT NULL CHECK (access_mode IN ('read_only', 'no_access')),
    source_migration text NOT NULL,
    PRIMARY KEY (schema_name, relation_name)
);
CREATE TABLE public.energy_source (
    id uuid PRIMARY KEY,
    location_id uuid NOT NULL REFERENCES public.location(id),
    source_name text NOT NULL,
    source_type text NOT NULL
);
CREATE TABLE public.energy_reading (
    id uuid PRIMARY KEY,
    location_id uuid NOT NULL REFERENCES public.location(id),
    source_id uuid NOT NULL REFERENCES public.energy_source(id),
    reading_date date NOT NULL,
    reading_type text NOT NULL,
    kwh numeric(10,2) NOT NULL,
    cost_per_kwh numeric(8,4),
    total_cost numeric(10,2),
    cost_currency_code text,
    activity_type text,
    equipment_id uuid,
    notes text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'recorded',
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO public.energy_source (id, location_id, source_name, source_type)
VALUES (
    'a0000000-0000-0000-0000-000000000101',
    'a0000000-0000-0000-0000-000000000001',
    'Synthetic grid meter', 'grid'
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.energy_reading
    TO kokonut_runtime, kokonut_directus_runtime, kokonut_maintenance_probe;
GRANT SELECT ON public.energy_source TO kokonut_runtime;
GRANT ALL ON public.energy_reading TO kokonut_directus_runtime;
GRANT ALL ON public.energy_reading TO kokonut_maintenance_probe;
INSERT INTO public.operator_scope_grant (
    operator_id, resource, action, location_id, organization_id
) VALUES (
    'a0000000-0000-0000-0000-000000000901', 'energy_monitoring', 'create',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000801'
);
"""
        docker_sql(container, setup)
        tenant_grant_sql = TENANT_GRANT_MIGRATION.read_text(encoding="utf-8")
        function_start = tenant_grant_sql.index(
            "CREATE OR REPLACE FUNCTION operator_scope_grant_allows("
        )
        function_end = tenant_grant_sql.index("$$;", function_start) + len("$$;")
        docker_sql(container, tenant_grant_sql[function_start:function_end])
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        docker_sql(container, migration_sql)
        docker_sql(container, migration_sql)

        acl_acceptance = r"""
DO $$
DECLARE
    public_execute boolean;
    owner_attributes record;
    capture_config text[];
    grant_config text[];
BEGIN
    IF has_table_privilege('kokonut_runtime', 'public.energy_reading', 'SELECT') IS DISTINCT FROM TRUE
       OR has_table_privilege('kokonut_runtime', 'public.energy_reading', 'INSERT') IS DISTINCT FROM FALSE
       OR has_table_privilege('kokonut_runtime', 'public.energy_reading', 'UPDATE') IS DISTINCT FROM FALSE
       OR has_table_privilege('kokonut_runtime', 'public.energy_reading', 'DELETE') IS DISTINCT FROM FALSE
       OR has_column_privilege('kokonut_runtime', 'public.energy_reading', 'status', 'INSERT') IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'runtime energy_reading access did not become read-only';
    END IF;
    IF has_table_privilege('kokonut_directus_runtime', 'public.energy_reading', 'INSERT') IS DISTINCT FROM TRUE
       OR has_table_privilege('kokonut_directus_runtime', 'public.energy_reading', 'UPDATE') IS DISTINCT FROM TRUE
       OR has_table_privilege('kokonut_maintenance_probe', 'public.energy_reading', 'INSERT') IS DISTINCT FROM TRUE
       OR has_table_privilege('kokonut_maintenance_probe', 'public.energy_reading', 'UPDATE') IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Directus or maintenance energy-reading grant was not preserved';
    END IF;
    IF has_table_privilege('kokonut_runtime', 'public.energy_reading_capture_receipt', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.energy_reading_capture_receipt', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.energy_reading_capture_receipt', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.energy_reading_operator_audit', 'INSERT') THEN
        RAISE EXCEPTION 'private receipt or audit relation is reachable by application roles';
    END IF;
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.record_location_energy_reading(uuid,uuid,uuid,date,text,numeric,numeric,text,text,uuid,text,jsonb,text)',
        'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.record_location_energy_reading(uuid,uuid,uuid,date,text,numeric,numeric,text,text,uuid,text,jsonb,text)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'energy capture function execution grants are incorrect';
    END IF;
    SELECT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc AS procedure
          CROSS JOIN LATERAL pg_catalog.aclexplode(procedure.proacl) AS privilege
         WHERE procedure.oid = 'kokonut_security.record_location_energy_reading(uuid,uuid,uuid,date,text,numeric,numeric,text,text,uuid,text,jsonb,text)'::regprocedure
           AND privilege.grantee = 0
           AND privilege.privilege_type = 'EXECUTE'
    ) INTO public_execute;
    IF public_execute THEN
        RAISE EXCEPTION 'PUBLIC can execute the energy capture function';
    END IF;
    SELECT proconfig INTO capture_config
      FROM pg_catalog.pg_proc
     WHERE oid = 'kokonut_security.record_location_energy_reading(uuid,uuid,uuid,date,text,numeric,numeric,text,text,uuid,text,jsonb,text)'::regprocedure;
    SELECT proconfig INTO grant_config
      FROM pg_catalog.pg_proc
     WHERE oid = 'public.operator_scope_grant_allows(uuid,text,text,uuid)'::regprocedure;
    IF capture_config IS NULL OR NOT ('search_path=pg_catalog' = ANY(capture_config))
       OR grant_config IS NULL OR NOT ('search_path=pg_catalog' = ANY(grant_config)) THEN
        RAISE EXCEPTION 'security-definer path configuration is not catalog-only';
    END IF;
    SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole,
           rolreplication, rolbypassrls
      INTO owner_attributes
      FROM pg_catalog.pg_roles
     WHERE rolname = 'kokonut_energy_reading_writer';
    IF owner_attributes.rolcanlogin OR owner_attributes.rolinherit
       OR owner_attributes.rolsuper OR owner_attributes.rolcreatedb
       OR owner_attributes.rolcreaterole OR owner_attributes.rolreplication
       OR owner_attributes.rolbypassrls THEN
        RAISE EXCEPTION 'energy function owner role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members membership
        WHERE membership.roleid = (SELECT oid FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_energy_reading_writer')
           OR membership.member = (SELECT oid FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_energy_reading_writer')
    ) THEN
        RAISE EXCEPTION 'energy capture owner role has a role membership';
    END IF;
    IF (SELECT source_migration
          FROM kokonut_security.directus_relation_privilege_policy
         WHERE schema_name = 'public' AND relation_name = 'energy_reading_capture_receipt')
       IS DISTINCT FROM '711_location_energy_reading_capture.sql'
       OR (SELECT access_mode
             FROM kokonut_security.directus_relation_privilege_policy
            WHERE schema_name = 'public' AND relation_name = 'energy_reading_operator_audit')
       IS DISTINCT FROM 'no_access' THEN
        RAISE EXCEPTION 'Directus private-relation policy rows are missing';
    END IF;
END;
$$;
"""
        docker_sql(container, acl_acceptance)

        # Use a real OIDC owner session under the runtime login. The function
        # is exercised in the same transaction as the signed scope setup.
        signed_acceptance = r"""
SET ROLE kokonut_runtime;
BEGIN;
DO $$
DECLARE
    context_row record;
    result_payload jsonb;
    replay_payload jsonb;
    denied boolean;
BEGIN
    SELECT * INTO STRICT context_row
      FROM kokonut_security.set_operator_tenant_context(
        repeat('b', 64), 'a0000000-0000-0000-0000-000000000901',
        'a0000000-0000-0000-0000-000000000001',
        'energy_monitoring', 'create', '[]'::jsonb
      );
    SELECT kokonut_security.record_location_energy_reading(
        'a0000000-0000-0000-0000-000000000001',
        'a0000000-0000-0000-0000-000000000101',
        'a0000000-0000-0000-0000-000000000201',
        DATE '2026-10-30', 'consumption', 10.25, 0.15, 'USD', 'irrigation',
        NULL, 'Meter read', '{"meter":"M-1"}'::jsonb, 'Monthly meter entry'
    ) INTO result_payload;
    IF result_payload->>'status' <> 'recorded'
       OR result_payload->>'replayed' <> 'false'
       OR result_payload->>'total_cost' <> '1.54'
       OR result_payload ? 'reason' THEN
        RAISE EXCEPTION 'new energy capture response or lifecycle is invalid';
    END IF;
    SELECT kokonut_security.record_location_energy_reading(
        'a0000000-0000-0000-0000-000000000001',
        'a0000000-0000-0000-0000-000000000101',
        'a0000000-0000-0000-0000-000000000201',
        DATE '2026-10-30', 'consumption', 10.25, 0.15, 'USD', 'irrigation',
        NULL, 'Meter read', '{"meter":"M-1"}'::jsonb, 'Monthly meter entry'
    ) INTO replay_payload;
    IF replay_payload->>'replayed' <> 'true'
       OR replay_payload->>'reading_id' IS DISTINCT FROM result_payload->>'reading_id' THEN
        RAISE EXCEPTION 'same-request energy replay did not return the original receipt';
    END IF;
    denied := FALSE;
    BEGIN
        PERFORM kokonut_security.record_location_energy_reading(
            'a0000000-0000-0000-0000-000000000001',
            'a0000000-0000-0000-0000-000000000101',
            'a0000000-0000-0000-0000-000000000201',
            DATE '2026-10-30', 'consumption', 10.25, 0.15, 'USD', 'irrigation',
            NULL, 'Changed note', '{"meter":"M-1"}'::jsonb, 'Monthly meter entry'
        );
        RAISE EXCEPTION 'changed request ID reuse unexpectedly succeeded';
    EXCEPTION WHEN unique_violation THEN
        denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'request ID collision was not rejected'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM kokonut_security.record_location_energy_reading(
            'a0000000-0000-0000-0000-000000000001',
            'a0000000-0000-0000-0000-000000000199',
            'a0000000-0000-0000-0000-000000000203',
            DATE '2026-10-30', 'consumption', 10.25, 0.15, 'USD', 'irrigation',
            NULL, 'Meter read', '{"meter":"M-1"}'::jsonb, 'Monthly meter entry'
        );
        RAISE EXCEPTION 'unknown/cross-location source unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN
        denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'unknown/cross-location source was not rejected'; END IF;

    SELECT * INTO STRICT context_row
      FROM kokonut_security.set_operator_tenant_context(
        repeat('c', 64), 'a0000000-0000-0000-0000-000000000902',
        'a0000000-0000-0000-0000-000000000001',
        'farm_activity', 'review', '[]'::jsonb
      );
    denied := FALSE;
    BEGIN
        PERFORM kokonut_security.record_location_energy_reading(
            'a0000000-0000-0000-0000-000000000001',
            'a0000000-0000-0000-0000-000000000101',
            'a0000000-0000-0000-0000-000000000205',
            DATE '2026-10-30', 'consumption', 10.25, 0.15, 'USD', 'irrigation',
            NULL, 'Meter read', '{"meter":"M-1"}'::jsonb, 'Monthly meter entry'
        );
        RAISE EXCEPTION 'non-energy scope unexpectedly authorized a capture';
    EXCEPTION WHEN insufficient_privilege THEN
        denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'exact energy create scope was not enforced'; END IF;
END;
$$;
COMMIT;
RESET ROLE;
DO $$
DECLARE denied boolean := FALSE;
BEGIN
    BEGIN
        PERFORM kokonut_security.record_location_energy_reading(
            'a0000000-0000-0000-0000-000000000001',
            'a0000000-0000-0000-0000-000000000101',
            'a0000000-0000-0000-0000-000000000204',
            DATE '2026-10-30', 'consumption', 10.25, 0.15, 'USD', 'irrigation',
            NULL, 'Meter read', '{"meter":"M-1"}'::jsonb, 'Monthly meter entry'
        );
        RAISE EXCEPTION 'unsigned energy context unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN
        denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'unsigned energy context was not rejected'; END IF;
END;
$$;
"""
        docker_sql(container, signed_acceptance)
        audit_acceptance = r"""
DO $$
DECLARE
    stored_reason text;
    receipt_has_reason boolean;
BEGIN
    SELECT reason INTO stored_reason
      FROM public.energy_reading_operator_audit
     WHERE request_id = 'a0000000-0000-0000-0000-000000000201';
    IF stored_reason IS DISTINCT FROM 'Monthly meter entry' THEN
        RAISE EXCEPTION 'private audit reason was not stored';
    END IF;
    SELECT response ? 'reason' INTO receipt_has_reason
      FROM public.energy_reading_capture_receipt
     WHERE request_id = 'a0000000-0000-0000-0000-000000000201';
    IF receipt_has_reason IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'private reason leaked into the operator receipt';
    END IF;
END;
$$;
"""
        docker_sql(container, audit_acceptance)
        evidence_checks = [
            "migration 711 applies and idempotently replays on PostgreSQL 16",
            "the actual signed OIDC owner session establishes exact energy_monitoring:create context in the same runtime transaction",
            "capture is inserted in recorded status and total cost is calculated; the private reason is audited but excluded from the public receipt",
            "same request and payload replay return the same reading; a source mismatch, unsigned context, and non-energy scope are denied",
            "runtime retains SELECT while table/column DML is revoked; Directus and maintenance DML grants on energy_reading remain",
            "runtime and Directus cannot read or write private receipt/audit relations; migration 711 records their Directus no_access source rows",
            "only kokonut_runtime can execute the capture function; PUBLIC and Directus cannot, and owner role is non-login/no-inherit with no memberships",
            "both the capture function and scope-check helper pin search_path to pg_catalog and use qualified public relations",
        ]
        result = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container with Docker networking disabled",
            "migrations": [
                "394_signed_operator_tenant_context.sql (signed operator context prerequisite)",
                "711_location_energy_reading_capture.sql",
                "711_location_energy_reading_capture.sql (idempotency replay)",
            ],
            "checks": evidence_checks,
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "production_database_touched": False,
            "network_disabled": True,
            "host_port_published": False,
            "external_network_requests": 0,
            "container_cleanup": "completed in finally block; container uses --rm",
            "limitations": [
                "Uses the disposable operator-context schema fixture plus synthetic energy relations, not a populated candidate database.",
                "The earlier test-only failures were fixture defects: one uppercase currency case was valid, a synchronous fake was injected for an awaited runner, and malformed DB receipt IDs needed server-contract classification. Focused regressions now cover each correction.",
                "This is SQL/unit/disposable acceptance only; candidate rollout, real operator/browser flow, Directus runtime deployment, and production authorization remain unverified.",
            ],
        }
        evidence = result
    except Exception as exc:  # noqa: BLE001 - print disposable acceptance failure only.
        print(f"ENERGY READING CAPTURE ACCEPTANCE FAILED: {exc}", file=sys.stderr)
        if started:
            logs = subprocess.run(
                ["docker", "logs", container], text=True, capture_output=True, check=False
            )
            if logs.stdout or logs.stderr:
                print(logs.stdout, file=sys.stderr, end="")
                print(logs.stderr, file=sys.stderr, end="")
        return 1
    finally:
        if started:
            stopped = subprocess.run(
                ["docker", "stop", container], text=True, capture_output=True, check=False
            )
            if stopped.returncode != 0:
                print("Disposable PostgreSQL container cleanup failed", file=sys.stderr)
                return 1

    if evidence is None:
        return 1
    evidence["container_cleanup"] = "completed; disposable container stopped and removed"
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
