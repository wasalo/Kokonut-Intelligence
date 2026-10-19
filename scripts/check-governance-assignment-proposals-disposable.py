#!/usr/bin/env python3
"""Exercise governance role nomination and readback migrations on disposable PostgreSQL 16."""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/governance_tension_actions_disposable.sql"
MIGRATIONS = (
    ROOT / "schemas/postgres/437_governance_operator_binding_and_actions.sql",
    ROOT / "schemas/postgres/438_governance_role_assignment_proposals.sql",
    ROOT / "schemas/postgres/439_governance_role_assignment_proposal_readback.sql",
)
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-18-recovery/governance-assignment-proposals-disposable.json"

ORG_ID = "a0000000-0000-4000-8000-000000000101"
LOCATION_ID = "a0000000-0000-4000-8000-000000000201"
OPERATOR_ONE = "a0000000-0000-4000-8000-000000000401"
OPERATOR_TWO = "a0000000-0000-4000-8000-000000000402"
OPERATOR_THREE = "a0000000-0000-4000-8000-000000000403"
PARTY_ONE = "a0000000-0000-4000-8000-000000000501"
PARTY_TWO = "a0000000-0000-4000-8000-000000000502"
PARTY_RETIRED = "a0000000-0000-4000-8000-000000000504"
PARTY_THREE = "a0000000-0000-4000-8000-000000000505"
ROLE_LOCATION = "a0000000-0000-4000-8000-000000000811"
ROLE_NETWORK = "a0000000-0000-4000-8000-000000000812"


def run(command: list[str], *, input_text: str | None = None, check: bool = True):
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if check and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{details}")
    return result


def docker_sql(container: str, statement: str, *, check: bool = True):
    return run(
        [
            "docker", "exec", "-i", container, "psql", "-X", "-v",
            "ON_ERROR_STOP=1", "-t", "-A", "-U", "postgres", "-d", "postgres",
        ],
        input_text="\\set VERBOSITY verbose\n" + statement,
        check=check,
    )


def runtime_call(container: str, operator_id: str, sql: str):
    return docker_sql(
        container,
        f"""
        SET ROLE kokonut_runtime;
        SELECT set_config('test.tenant_id', '{ORG_ID}', FALSE);
        SELECT set_config('test.location_id', '{LOCATION_ID}', FALSE);
        SELECT set_config('test.actor_id', '{operator_id}', FALSE);
        SELECT set_config('test.actor_type', 'operator', FALSE);
        {sql}
        """,
    )


def assert_sqlstate(container: str, statement: str, sqlstate: str, label: str):
    result = docker_sql(container, statement, check=False)
    if result.returncode == 0 or sqlstate not in (result.stdout + result.stderr):
        raise AssertionError(
            f"{label}: expected SQLSTATE {sqlstate}, got rc={result.returncode}: "
            f"{result.stdout}{result.stderr}"
        )


def run_acceptance(container: str) -> list[str]:
    checks: list[str] = []
    docker_sql(container, FIXTURE.read_text())
    docker_sql(container, MIGRATIONS[0].read_text())
    migration_sql = MIGRATIONS[1].read_text()
    docker_sql(container, migration_sql)
    docker_sql(container, migration_sql)
    readback_sql = MIGRATIONS[2].read_text()
    docker_sql(container, readback_sql)
    docker_sql(container, readback_sql)
    checks.append("migrations 438 and 439 apply and replay transactionally after migration 437")

    privilege = docker_sql(
        container,
        """
        SELECT has_table_privilege('kokonut_runtime', 'public.governance_role_assignment', 'SELECT')
           AND NOT has_table_privilege('kokonut_runtime', 'public.governance_role_assignment', 'INSERT')
           AND NOT has_table_privilege('kokonut_runtime', 'public.governance_role_assignment', 'UPDATE')
           AND NOT has_table_privilege('kokonut_runtime', 'public.governance_role_assignment', 'DELETE')
           AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_role_assignment', 'INSERT')
           AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_role_assignment', 'UPDATE')
           AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_role_assignment', 'DELETE')
           AND NOT has_table_privilege('kokonut_runtime', 'public.governance_role_assignment_request', 'SELECT')
           AND NOT has_table_privilege('kokonut_runtime', 'public.governance_role_assignment_request', 'INSERT')
           AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_role_assignment_request', 'SELECT')
           AND has_function_privilege('kokonut_runtime',
             'kokonut_security.propose_governance_role_assignment(uuid,uuid,uuid,uuid,text,text)', 'EXECUTE')
           AND has_function_privilege('kokonut_runtime',
             'kokonut_security.list_my_governance_role_assignment_proposals(uuid,integer,timestamp with time zone,uuid)', 'EXECUTE')
           AND NOT has_function_privilege('kokonut_directus_runtime',
             'kokonut_security.list_my_governance_role_assignment_proposals(uuid,integer,timestamp with time zone,uuid)', 'EXECUTE');
        """,
    ).stdout.strip()
    if privilege != "t":
        raise AssertionError(f"role nomination ACL contract failed: {privilege}")
    checks.append("runtime retains assignment reads and bounded proposal execution but loses direct table writes and ledger access")

    docker_sql(
        container,
        f"""SET ROLE kokonut_governance_identity_admin;
            SELECT binding_id FROM kokonut_security.bind_operator_governance_party(
                '{OPERATOR_ONE}', '{PARTY_ONE}', 'test administrator', 'explicit test binding'
            ); RESET ROLE;""",
    )
    request_id = str(uuid.uuid4())
    proposal_sql = f"""SELECT assignment_id || '|' || role_id || '|' || assignment_type || '|' || status
        FROM kokonut_security.propose_governance_role_assignment(
            '{LOCATION_ID}', '{request_id}', '{ROLE_LOCATION}', '{PARTY_TWO}', 'primary', NULL
        );"""
    created = runtime_call(container, OPERATOR_ONE, proposal_sql).stdout.strip().splitlines()[-1]
    replayed = runtime_call(container, OPERATOR_ONE, proposal_sql).stdout.strip().splitlines()[-1]
    if created != replayed or not created.endswith("|primary|proposed"):
        raise AssertionError(f"proposal must replay as the same pending assignment: {created} / {replayed}")
    assignment_id = created.split("|")[0]
    state = docker_sql(
        container,
        f"""SELECT status || '|' || COALESCE(approved_by_party_id::text, 'null') || '|' ||
                       COALESCE(effective_from::text, 'null') || '|' || assigned_by_party_id::text || '|' || party_id::text
              FROM public.governance_role_assignment WHERE id = '{assignment_id}';""",
    ).stdout.strip()
    counts = docker_sql(
        container,
        f"""SELECT (SELECT count(*) FROM public.governance_role_assignment WHERE id = '{assignment_id}') || '|' ||
                   (SELECT count(*) FROM public.governance_role_assignment_request WHERE operator_id = '{OPERATOR_ONE}' AND request_id = '{request_id}');""",
    ).stdout.strip()
    if state != f"proposed|null|null|{PARTY_ONE}|{PARTY_TWO}" or counts != "1|1":
        raise AssertionError(f"proposal must remain unapproved and create one ledger row: {state}, {counts}")
    checks.append("active bound operator creates an attributed location role nomination; exact retry returns the same proposed row without activation")

    second_request_id = str(uuid.uuid4())
    second_proposal_sql = f"""SELECT assignment_id::text || '|' || status
        FROM kokonut_security.propose_governance_role_assignment(
            '{LOCATION_ID}', '{second_request_id}', '{ROLE_LOCATION}', '{PARTY_TWO}', 'primary', NULL
        );"""
    second_created = runtime_call(container, OPERATOR_ONE, second_proposal_sql).stdout.strip().splitlines()[-1]
    second_assignment_id, second_status = second_created.split("|")
    if second_status != "proposed" or second_assignment_id == assignment_id:
        raise AssertionError(f"second operator nomination was not created as a distinct proposal: {second_created}")

    docker_sql(
        container,
        f"""SET ROLE kokonut_governance_identity_admin;
            SELECT binding_id FROM kokonut_security.bind_operator_governance_party(
                '{OPERATOR_TWO}', '{PARTY_THREE}', 'test administrator', 'explicit test binding'
            ); RESET ROLE;""",
    )
    first_page = runtime_call(
        container,
        OPERATOR_ONE,
        f"""SELECT assignment_id::text || '|' || created_at::text
             FROM kokonut_security.list_my_governance_role_assignment_proposals(
                 '{LOCATION_ID}', 1, NULL, NULL
             );""",
    ).stdout.strip().splitlines()[-1]
    first_assignment_id, first_created_at = first_page.split("|", 1)
    next_page = runtime_call(
        container,
        OPERATOR_ONE,
        f"""SELECT assignment_id::text
             FROM kokonut_security.list_my_governance_role_assignment_proposals(
                 '{LOCATION_ID}', 2, '{first_created_at}', '{first_assignment_id}'
             );""",
    ).stdout.strip().splitlines()[-1]
    if first_assignment_id != second_assignment_id or next_page != assignment_id:
        raise AssertionError(f"proposal readback keyset order is unstable: {first_page}, {next_page}")
    other_operator_rows = runtime_call(
        container,
        OPERATOR_TWO,
        f"""SELECT count(*) FROM kokonut_security.list_my_governance_role_assignment_proposals(
                 '{LOCATION_ID}', 10, NULL, NULL
             );""",
    ).stdout.strip().splitlines()[-1]
    if other_operator_rows != "0":
        raise AssertionError(f"readback exposed another operator's proposal: {other_operator_rows}")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_THREE, f"""SELECT * FROM kokonut_security.list_my_governance_role_assignment_proposals(
            '{LOCATION_ID}', 10, NULL, NULL);"""),
        "42501",
        "reject operator without exact governance role read grant",
    )
    wrong_location_context = f"""SET ROLE kokonut_runtime;
        SELECT set_config('test.tenant_id', '{ORG_ID}', FALSE);
        SELECT set_config('test.location_id', 'a0000000-0000-4000-8000-000000000299', FALSE);
        SELECT set_config('test.actor_id', '{OPERATOR_ONE}', FALSE);
        SELECT set_config('test.actor_type', 'operator', FALSE);
        SELECT * FROM kokonut_security.list_my_governance_role_assignment_proposals(
            '{LOCATION_ID}', 10, NULL, NULL);"""
    assert_sqlstate(
        container,
        wrong_location_context,
        "42501",
        "reject readback with mismatched signed location context",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.list_my_governance_role_assignment_proposals(
            '{LOCATION_ID}', 10, NULL, '{assignment_id}');"""),
        "22023",
        "reject incomplete keyset cursor",
    )
    result_shape = docker_sql(
        container,
        """SELECT pg_get_function_result(
              'kokonut_security.list_my_governance_role_assignment_proposals(uuid,integer,timestamptz,uuid)'::regprocedure
            );""",
    ).stdout
    if "party_id" in result_shape or "mandate" in result_shape:
        raise AssertionError(f"readback projection contains nominee or mandate fields: {result_shape}")
    checks.append("read-only readback pages only the signed operator's nominations, rejects missing or mismatched scope, and omits nominee identity and mandate")

    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.propose_governance_role_assignment(
            '{LOCATION_ID}', '{request_id}', '{ROLE_LOCATION}', '{PARTY_ONE}', 'primary', NULL);"""),
        "22023",
        "reject reuse of a request ID with different content",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_TWO, f"""SELECT * FROM kokonut_security.propose_governance_role_assignment(
            '{LOCATION_ID}', '{uuid.uuid4()}', '{ROLE_LOCATION}', '{PARTY_TWO}', 'primary', NULL);"""),
        "42501",
        "reject operator without exact governance role create grant",
    )
    docker_sql(
        container,
        f"""INSERT INTO public.operator_scope_grant VALUES
          ('a0000000-0000-4000-8000-000000000705', '{OPERATOR_THREE}', 'governance_roles', 'create', '{LOCATION_ID}', '{ORG_ID}', NULL);""",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_THREE, f"""SELECT * FROM kokonut_security.propose_governance_role_assignment(
            '{LOCATION_ID}', '{uuid.uuid4()}', '{ROLE_LOCATION}', '{PARTY_TWO}', 'primary', NULL);"""),
        "42501",
        "reject unbound operator",
    )
    checks.append("signed tenant context, exact location grant, active party binding, and request-content identity are enforced")

    for role_id, party_id, assignment_type, mandate, sqlstate, label in (
        (ROLE_NETWORK, PARTY_TWO, "primary", None, "22023", "network role outside requested location"),
        (ROLE_LOCATION, PARTY_RETIRED, "primary", None, "22023", "inactive nominee party"),
        (ROLE_LOCATION, PARTY_TWO, "delegate", None, "22023", "delegate without mandate"),
    ):
        mandate_sql = "NULL" if mandate is None else "'" + mandate.replace("'", "''") + "'"
        assert_sqlstate(
            container,
            runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.propose_governance_role_assignment(
                '{LOCATION_ID}', '{uuid.uuid4()}', '{role_id}', '{party_id}', '{assignment_type}', {mandate_sql});"""),
            sqlstate,
            label,
        )
    checks.append("role location, nominee active state, and delegate mandate are validated before writing")

    for sql, label in (
        ("INSERT INTO public.governance_role_assignment(role_id, party_id, assignment_type) VALUES ('%s', '%s', 'primary');" % (ROLE_LOCATION, PARTY_TWO), "direct runtime insert"),
        ("UPDATE public.governance_role_assignment SET status = 'active' WHERE id = '%s';" % assignment_id, "direct runtime activation"),
        ("DELETE FROM public.governance_role_assignment WHERE id = '%s';" % assignment_id, "direct runtime delete"),
        ("SELECT * FROM public.governance_role_assignment_request;", "request ledger read"),
        ("INSERT INTO public.governance_role_assignment(role_id, party_id, assignment_type) VALUES ('%s', '%s', 'primary');" % (ROLE_LOCATION, PARTY_TWO), "direct Directus insert"),
        ("UPDATE public.governance_role_assignment SET status = 'active' WHERE id = '%s';" % assignment_id, "direct Directus activation"),
        ("DELETE FROM public.governance_role_assignment WHERE id = '%s';" % assignment_id, "direct Directus delete"),
        ("SELECT * FROM public.governance_role_assignment_request;", "Directus request ledger read"),
    ):
        database_role = "kokonut_directus_runtime" if label.startswith("direct Directus") or label.startswith("Directus") else "kokonut_runtime"
        assert_sqlstate(container, f"SET ROLE {database_role}; {sql}", "42501", label)
    assert_sqlstate(
        container,
        f"UPDATE public.governance_role_assignment_request SET mandate = 'rewritten' WHERE operator_id = '{OPERATOR_ONE}' AND request_id = '{request_id}';",
        "P0001",
        "immutable request history",
    )
    checks.append("runtime cannot bypass the bounded write function, activate/delete assignments, inspect the private request ledger, or rewrite request history")
    return checks


def runtime_sql(operator_id: str, sql: str) -> str:
    return f"""SET ROLE kokonut_runtime;
        SELECT set_config('test.tenant_id', '{ORG_ID}', FALSE);
        SELECT set_config('test.location_id', '{LOCATION_ID}', FALSE);
        SELECT set_config('test.actor_id', '{operator_id}', FALSE);
        SELECT set_config('test.actor_type', 'operator', FALSE);
        {sql}"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    container = f"kokonut-governance-proposals-{uuid.uuid4().hex[:10]}"
    password = secrets.token_urlsafe(24)
    started = time.monotonic()
    run(["docker", "run", "-d", "--rm", "--name", container, "-e", f"POSTGRES_PASSWORD={password}", "-p", "127.0.0.1::5432", "postgres:16-alpine"])
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if run(["docker", "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"], check=False).returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")
        checks = run_acceptance(container)
        evidence = {
            "title": "Migrations 438-439 tenant-scoped governance role assignment proposals and readback",
            "status": "passed",
            "checks": checks,
            "isolation": "Only a temporary PostgreSQL 16 container was used; candidate and legacy databases were not accessed.",
            "elapsed_seconds": round(time.monotonic() - started, 2),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence, indent=2))
    finally:
        run(["docker", "rm", "-f", container], check=False)


if __name__ == "__main__":
    main()
