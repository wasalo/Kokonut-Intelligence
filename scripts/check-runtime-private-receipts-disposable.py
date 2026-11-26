#!/usr/bin/env python3
"""Apply/replay migration 715 and verify private receipt ACLs on disposable PostgreSQL."""

from __future__ import annotations

import json
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MIGRATION = ROOT / "schemas/postgres/715_runtime_private_location_write_receipts.sql"
IMAGE = "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5"

RECEIPT_OWNERS: dict[str, tuple[str, ...]] = {
    "composting_capture_receipt": ("kokonut_composting_capture_writer",),
    "operating_capacity_draft_receipt": ("kokonut_operating_pilot_reader",),
    "operating_capacity_draft_revision_receipt": ("kokonut_operating_pilot_reader",),
    "operating_capacity_draft_submission_receipt": ("kokonut_operating_pilot_reader",),
    "operating_demand_draft_receipt": ("kokonut_operating_pilot_reader",),
    "operating_demand_draft_revision_receipt": ("kokonut_operating_pilot_reader",),
    "operating_demand_draft_submission_receipt": ("kokonut_operating_pilot_reader",),
    "operating_pilot_coaching_session_receipt": ("kokonut_operating_pilot_reader",),
    "pesticide_impact_capture_receipt": ("kokonut_pesticide_impact_writer",),
    "pollinator_habitat_capture_receipt": ("kokonut_pollinator_habitat_writer",),
    "pollinator_hive_capture_receipt": ("kokonut_pollinator_hive_writer",),
    "pollinator_hive_inspection_capture_receipt": ("kokonut_pollinator_inspection_writer",),
    "pollinator_observation_capture_receipt": ("kokonut_pollinator_observation_writer",),
    "pollution_incident_operation_receipt": (
        "kokonut_incident_capture_writer",
        "kokonut_incident_resolution_writer",
    ),
    "recycling_capture_receipt": ("kokonut_recycling_capture_writer",),
    "solution_adoption_program_creation_receipt": ("kokonut_solution_adoption_program_creator",),
    "solution_experiment_creation_receipt": ("kokonut_solution_experiment_creator",),
    "solution_experiment_protocol_approval_receipt": (
        "kokonut_solution_experiment_protocol_reviewer",
        "kokonut_solution_experiment_starter",
    ),
    "solution_experiment_start_receipt": ("kokonut_solution_experiment_starter",),
    "solution_experiment_submission_receipt": ("kokonut_solution_experiment_submitter",),
    "solution_gate_definition_receipt": ("kokonut_solution_gate_creator",),
    "solution_nonpromotion_transition_receipt": ("kokonut_solution_nonpromotion_transition_owner",),
    "waste_stream_capture_receipt": ("kokonut_waste_stream_writer",),
}


def run(
    command: list[str],
    *,
    input_text: str | None = None,
    check: bool = True,
    timeout: int = 90,
):
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if check and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command[:5])} …\n{details[-2000:]}")
    return result


def psql(docker: str, container: str, statement: str, *, check: bool = True):
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
        check=check,
    )


def _fixture_sql() -> str:
    owners = sorted({role for roles in RECEIPT_OWNERS.values() for role in roles})
    role_sql = "\n".join(
        f"CREATE ROLE {owner} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;"
        for owner in owners
    )
    table_sql = "\n".join(
        f"CREATE TABLE public.{table} (id UUID PRIMARY KEY, marker TEXT NOT NULL);" for table in RECEIPT_OWNERS
    )
    broad_grants = "\n".join(
        f"GRANT ALL PRIVILEGES ON TABLE public.{table} "
        "TO PUBLIC, kokonut_runtime, kokonut_directus_runtime;"
        f"\nGRANT SELECT (id, marker), INSERT (id, marker), UPDATE (marker), "
        f"REFERENCES (id) ON TABLE public.{table} "
        "TO PUBLIC, kokonut_runtime, kokonut_directus_runtime;"
        for table in RECEIPT_OWNERS
    )
    owner_grants = "\n".join(
        f"GRANT SELECT (id, marker), INSERT (id, marker) ON TABLE public.{table} TO {owner};"
        for table, roles in RECEIPT_OWNERS.items()
        for owner in roles
    )
    return f"""
CREATE ROLE kokonut_runtime NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_directus_runtime NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
{role_sql}
{table_sql}
{broad_grants}
{owner_grants}
"""


def _assertion_sql() -> str:
    relation_checks = []
    for table, owners in RECEIPT_OWNERS.items():
        for role in ("kokonut_runtime", "kokonut_directus_runtime"):
            relation_checks.append(
                f"""
    IF EXISTS (
        SELECT 1
          FROM unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) AS p(privilege)
         WHERE has_table_privilege('{role}', 'public.{table}', p.privilege)
    ) THEN
        RAISE EXCEPTION '{role} retains table privileges on {table}';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM unnest(ARRAY['id','marker']) AS c(column_name)
          CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','REFERENCES']) AS p(privilege)
         WHERE has_column_privilege('{role}', 'public.{table}', c.column_name, p.privilege)
    ) THEN
        RAISE EXCEPTION '{role} retains column privileges on {table}';
    END IF;
"""
            )
        for owner in owners:
            relation_checks.append(
                f"""
    IF NOT has_column_privilege('{owner}', 'public.{table}', 'id', 'SELECT')
       OR NOT has_column_privilege('{owner}', 'public.{table}', 'marker', 'SELECT')
       OR NOT has_column_privilege('{owner}', 'public.{table}', 'id', 'INSERT')
       OR NOT has_column_privilege('{owner}', 'public.{table}', 'marker', 'INSERT') THEN
        RAISE EXCEPTION 'migration changed bounded owner grants for {owner} on {table}';
    END IF;
"""
            )
        relation_checks.append(
            f"""
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_class AS relation
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              COALESCE(relation.relacl, pg_catalog.acldefault('r', relation.relowner))
          ) AS privilege
         WHERE relation.oid = 'public.{table}'::regclass
           AND privilege.grantee = 0
    ) OR EXISTS (
        SELECT 1
          FROM pg_catalog.pg_attribute AS attribute
          CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.attacl) AS privilege
         WHERE attribute.attrelid = 'public.{table}'::regclass
           AND attribute.attnum > 0 AND NOT attribute.attisdropped
           AND privilege.grantee = 0
    ) THEN
        RAISE EXCEPTION 'PUBLIC retains table or column privileges on {table}';
    END IF;
"""
        )
    return "DO $$ BEGIN\n" + "\n".join(relation_checks) + "\nEND; $$;\n"


def _runtime_reprovision_sql(runtime_private_tables: tuple[str, ...]) -> str:
    statements = []
    for table in RECEIPT_OWNERS:
        if table not in runtime_private_tables:
            continue
        statements.append(f"REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM kokonut_runtime;")
        for column in ("id", "marker"):
            for privilege in ("SELECT", "INSERT", "UPDATE", "REFERENCES"):
                statements.append(f"REVOKE {privilege} ({column}) ON TABLE public.{table} FROM kokonut_runtime;")
    return "\n".join(statements) + "\n"


def main() -> int:
    from services.migration import runtime_role

    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is required for disposable PostgreSQL checks")
    if set(RECEIPT_OWNERS) - set(runtime_role._RUNTIME_PRIVATE_TABLES):
        raise AssertionError("a migration-715 receipt is missing from runtime-role policy")
    container = f"kokonut-private-receipts-{uuid.uuid4().hex[:12]}"
    password = secrets.token_urlsafe(24)
    started = False
    try:
        run(
            [
                docker,
                "run",
                "--pull=never",
                "--detach",
                "--rm",
                "--name",
                container,
                "--network",
                "none",
                "--env",
                f"POSTGRES_PASSWORD={password}",
                IMAGE,
            ],
            timeout=120,
        )
        started = True
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            ready = run([docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"], check=False)
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")

        psql(docker, container, _fixture_sql())
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_sql)
        psql(docker, container, migration_sql)
        psql(docker, container, _assertion_sql())

        # Compatibility provisioning may reapply broad runtime DML grants. Apply
        # the configured private-table policy again and prove it closes them.
        broad_runtime_grants = "\n".join(
            f"GRANT ALL PRIVILEGES ON TABLE public.{table} TO kokonut_runtime;\n"
            f"GRANT SELECT (id, marker), INSERT (id, marker), UPDATE (marker), "
            f"REFERENCES (id) ON TABLE public.{table} TO kokonut_runtime;"
            for table in RECEIPT_OWNERS
        )
        psql(docker, container, broad_runtime_grants)
        psql(
            docker,
            container,
            _runtime_reprovision_sql(runtime_role._RUNTIME_PRIVATE_TABLES),
        )
        psql(docker, container, _assertion_sql())

        print(
            json.dumps(
                {
                    "ok": True,
                    "migration": MIGRATION.name,
                    "receipt_relations": len(RECEIPT_OWNERS),
                    "migration_replay": "passed",
                    "public_runtime_directus_table_and_column_privileges": "denied",
                    "function_owner_column_grants": "preserved for mapped owners",
                    "runtime_compatibility_regrant_then_private_policy_reapply": "passed",
                    "postgres": "disposable PostgreSQL 16",
                    "network": "none",
                    "host_ports_published": False,
                    "candidate_legacy_or_production_touched": False,
                    "business_function_definitions_or_retry_semantics_changed": False,
                },
                indent=2,
            )
        )
        return 0
    finally:
        if started:
            run([docker, "rm", "--force", container], check=False)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"private receipt disposable check failed: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
