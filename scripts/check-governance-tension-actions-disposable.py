#!/usr/bin/env python3
"""Apply migration 437 and exercise its bounded functions on disposable PG16."""

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
MIGRATION = ROOT / "schemas/postgres/437_governance_operator_binding_and_actions.sql"
DEFAULT_OUTPUT = (
    ROOT
    / "docs/refactor/builds/2026-10-18-recovery/governance-tension-actions-disposable.json"
)

ORG_ID = "a0000000-0000-4000-8000-000000000101"
LOCATION_ID = "a0000000-0000-4000-8000-000000000201"
OPERATOR_ONE = "a0000000-0000-4000-8000-000000000401"
OPERATOR_TWO = "a0000000-0000-4000-8000-000000000402"
OPERATOR_THREE = "a0000000-0000-4000-8000-000000000403"
OPERATOR_DISABLED = "a0000000-0000-4000-8000-000000000404"
PARTY_ONE = "a0000000-0000-4000-8000-000000000501"
PARTY_TWO = "a0000000-0000-4000-8000-000000000502"
PARTY_ORG = "a0000000-0000-4000-8000-000000000503"


def run(command: list[str], *, input_text: str | None = None, check: bool = True):
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{details}")
    return result


def docker_sql(container: str, statement: str, *, check: bool = True):
    result = run(
        [
            "docker", "exec", "-i", container, "psql", "-X", "-v",
            "ON_ERROR_STOP=1", "-t", "-A", "-U", "postgres", "-d", "postgres",
        ],
        input_text="\\set VERBOSITY verbose\n" + statement,
        check=check,
    )
    return result


def runtime_call(container: str, operator_id: str, action_sql: str):
    statement = f"""
        SET ROLE kokonut_runtime;
        SELECT set_config('test.tenant_id', '{ORG_ID}', FALSE);
        SELECT set_config('test.location_id', '{LOCATION_ID}', FALSE);
        SELECT set_config('test.actor_id', '{operator_id}', FALSE);
        SELECT set_config('test.actor_type', 'operator', FALSE);
        {action_sql}
        RESET ROLE;
    """
    return docker_sql(container, statement)


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
    docker_sql(container, MIGRATION.read_text())
    checks.append("migration 437 applied transactionally to the minimal compatible PostgreSQL 16 fixture")

    privilege = docker_sql(
        container,
        """
        SELECT NOT has_table_privilege('kokonut_runtime',
                   'public.operator_governance_party_binding', 'SELECT')
           AND NOT has_table_privilege('kokonut_runtime',
                   'public.operator_governance_party_binding', 'INSERT')
           AND NOT has_function_privilege('kokonut_runtime',
                   'kokonut_security.bind_operator_governance_party(uuid,uuid,text,text)', 'EXECUTE')
           AND NOT has_function_privilege('kokonut_runtime',
                   'kokonut_security.revoke_operator_governance_party_binding(uuid,text,text)', 'EXECUTE')
           AND NOT has_function_privilege('kokonut_runtime',
                   'kokonut_security.list_operator_governance_party_bindings(uuid)', 'EXECUTE')
           AND has_function_privilege('kokonut_runtime',
                   'kokonut_security.report_governance_tension(uuid,uuid,text,text,text,smallint,smallint)', 'EXECUTE')
           AND has_function_privilege('kokonut_runtime',
                   'kokonut_security.submit_governance_tension(uuid,uuid)', 'EXECUTE');
        """,
    ).stdout.strip()
    if privilege != "t":
        raise AssertionError(f"runtime binding/action ACL contract failed: {privilege}")
    checks.append("runtime can execute only the bounded create/submit functions and cannot access the binding ledger")

    bind_one = docker_sql(
        container,
        f"""
        SET ROLE kokonut_governance_identity_admin;
        SELECT binding_id FROM kokonut_security.bind_operator_governance_party(
            '{OPERATOR_ONE}', '{PARTY_ONE}', 'test administrator',
            'Explicit UUID-confirmed identity mapping'
        );
        RESET ROLE;
        """,
    ).stdout.strip().splitlines()[-2]
    bind_one_again = docker_sql(
        container,
        f"""
        SET ROLE kokonut_governance_identity_admin;
        SELECT binding_id FROM kokonut_security.bind_operator_governance_party(
            '{OPERATOR_ONE}', '{PARTY_ONE}', 'another label', 'repeated explicit mapping'
        );
        RESET ROLE;
        """,
    ).stdout.strip().splitlines()[-2]
    if bind_one != bind_one_again:
        raise AssertionError("repeating an explicit active binding must be idempotent")
    checks.append("administrator can create and idempotently replay an explicit operator/person UUID binding")

    for party_id, label in ((PARTY_ORG, "organization"),):
        assert_sqlstate(
            container,
            f"""SET ROLE kokonut_governance_identity_admin;
                SELECT * FROM kokonut_security.bind_operator_governance_party(
                    '{OPERATOR_TWO}', '{party_id}', 'admin', 'must be a person');""",
            "22023",
            f"reject {label} party binding",
        )
    assert_sqlstate(
        container,
        f"""SET ROLE kokonut_governance_identity_admin;
            SELECT * FROM kokonut_security.bind_operator_governance_party(
                '{OPERATOR_DISABLED}', '{PARTY_TWO}', 'admin', 'disabled identity');""",
        "22023",
        "reject disabled operator binding",
    )
    assert_sqlstate(
        container,
        f"""SET ROLE kokonut_governance_identity_admin;
            SELECT * FROM kokonut_security.bind_operator_governance_party(
                '{OPERATOR_TWO}', '{PARTY_ONE}', 'admin', 'duplicate party');""",
        "23505",
        "reject party already bound to another operator",
    )
    checks.append("binding rejects non-person parties, disabled operators, and duplicate active person mappings")

    docker_sql(
        container,
        f"""
        SET ROLE kokonut_governance_identity_admin;
        SELECT * FROM kokonut_security.bind_operator_governance_party(
            '{OPERATOR_TWO}', '{PARTY_TWO}', 'test administrator',
            'Explicit UUID-confirmed identity mapping'
        );
        RESET ROLE;
        """,
    )

    request_id = str(uuid.uuid4())
    create_sql = f"""SELECT tension_id FROM kokonut_security.report_governance_tension(
        '{LOCATION_ID}', '{request_id}', 'Accountability gap',
        'A scoped report with no identity supplied by the browser.',
        'unclear_accountability', 3::smallint, 2::smallint);"""
    tension_id = runtime_call(container, OPERATOR_ONE, create_sql).stdout.strip().splitlines()[-2]
    replay_id = runtime_call(container, OPERATOR_ONE, create_sql).stdout.strip().splitlines()[-2]
    if tension_id != replay_id:
        raise AssertionError("replaying the same create request must return the original tension")
    if docker_sql(container, "SELECT count(*) FROM public.governance_tension_event;").stdout.strip() != "1":
        raise AssertionError("idempotent create must not append a duplicate report event")
    checks.append("signed-scope create stores an attributed location draft and idempotently suppresses duplicate events")

    assert_sqlstate(
        container,
        """SET ROLE kokonut_runtime;
            SELECT * FROM kokonut_security.report_governance_tension(
              'a0000000-0000-4000-8000-000000000201',
              'b0000000-0000-4000-8000-000000000901', 'Bad', 'Bad',
              'unclear_accountability', 3::smallint, 2::smallint);""",
        "42501",
        "reject create without a signed matching tenant context",
    )
    assert_sqlstate(
        container,
        f"""SET ROLE kokonut_runtime;
            SELECT set_config('test.tenant_id', '{ORG_ID}', FALSE);
            SELECT set_config('test.location_id', '{LOCATION_ID}', FALSE);
            SELECT set_config('test.actor_id', '{OPERATOR_TWO}', FALSE);
            SELECT set_config('test.actor_type', 'operator', FALSE);
            SELECT * FROM kokonut_security.report_governance_tension(
              '{LOCATION_ID}', '{request_id}', 'Unauthorized', 'No create scope',
              'unclear_accountability', 3::smallint, 2::smallint);""",
        "42501",
        "reject create without the exact action grant",
    )
    assert_sqlstate(
        container,
        f"""SET ROLE kokonut_runtime;
            SELECT set_config('test.tenant_id', '{ORG_ID}', FALSE);
            SELECT set_config('test.location_id', '{LOCATION_ID}', FALSE);
            SELECT set_config('test.actor_id', '{OPERATOR_THREE}', FALSE);
            SELECT set_config('test.actor_type', 'operator', FALSE);
            SELECT * FROM kokonut_security.report_governance_tension(
              '{LOCATION_ID}', '{uuid.uuid4()}', 'Unbound', 'No person mapping',
              'unclear_accountability', 3::smallint, 2::smallint);""",
        "42501",
        "reject create without an active human party binding",
    )
    checks.append("create denies absent/mismatched signed context, exact grant, and active person binding")

    assert_sqlstate(
        container,
        f"""SET ROLE kokonut_runtime;
            SELECT set_config('test.tenant_id', '{ORG_ID}', FALSE);
            SELECT set_config('test.location_id', '{LOCATION_ID}', FALSE);
            SELECT set_config('test.actor_id', '{OPERATOR_TWO}', FALSE);
            SELECT set_config('test.actor_type', 'operator', FALSE);
            SELECT * FROM kokonut_security.submit_governance_tension(
              '{LOCATION_ID}', '{tension_id}');""",
        "42501",
        "reject cross-reporter submission",
    )
    submit_sql = f"SELECT tension_id, status FROM kokonut_security.submit_governance_tension('{LOCATION_ID}', '{tension_id}');"
    submitted = runtime_call(container, OPERATOR_ONE, submit_sql).stdout.strip().splitlines()[-2]
    submitted_again = runtime_call(container, OPERATOR_ONE, submit_sql).stdout.strip().splitlines()[-2]
    if submitted != submitted_again or not submitted.endswith("|submitted"):
        raise AssertionError("submit must be replay-safe and leave the record submitted")
    if docker_sql(container, "SELECT count(*) FROM public.governance_tension_event;").stdout.strip() != "2":
        raise AssertionError("submit replay must not append a duplicate lifecycle event")
    checks.append("only the bound reporter can submit its own location draft; repeated submit is idempotent")

    assert_sqlstate(
        container,
        f"""SET ROLE kokonut_runtime;
            SELECT tension_id FROM kokonut_security.submit_governance_tension(
              '{LOCATION_ID}', '{tension_id}');""",
        "42501",
        "reject submission without signed tenant context",
    )
    for statement, label in (
        ("SELECT * FROM public.operator_governance_party_binding;", "binding ledger read"),
        ("INSERT INTO public.operator_governance_party_binding(operator_id, party_id, bound_by, binding_reason) VALUES ('%s', '%s', 'app', 'forbidden');" % (OPERATOR_THREE, PARTY_TWO), "binding ledger insert"),
        ("UPDATE public.governance_tension SET status = 'verified';", "unreviewed lifecycle transition"),
    ):
        assert_sqlstate(
            container,
            f"SET ROLE kokonut_runtime; {statement}",
            "42501",
            f"deny runtime {label}",
        )
    checks.append("runtime cannot read/write identity bindings or directly verify tension lifecycle state")

    revoked = docker_sql(
        container,
        f"""
        SET ROLE kokonut_governance_identity_admin;
        SELECT binding_id FROM kokonut_security.revoke_operator_governance_party_binding(
            '{bind_one}', 'test administrator', 'Synthetic identity correction'
        );
        RESET ROLE;
        """,
    ).stdout.strip().splitlines()[-2]
    if revoked != bind_one:
        raise AssertionError("revocation did not identify the original binding")
    docker_sql(
        container,
        f"""
        SET ROLE kokonut_governance_identity_admin;
        SELECT binding_id FROM kokonut_security.bind_operator_governance_party(
            '{OPERATOR_ONE}', '{PARTY_ONE}', 'test administrator',
            'Corrected explicit UUID mapping'
        );
        RESET ROLE;
        """,
    )
    if docker_sql(
        container,
        f"SELECT count(*) FROM public.operator_governance_party_binding WHERE operator_id = '{OPERATOR_ONE}';",
    ).stdout.strip() != "2":
        raise AssertionError("binding history must preserve both the revoked and replacement mapping")
    checks.append("revocation is audited and permits a new explicit binding without deleting prior history")
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    container = f"kokonut-governance-actions-{uuid.uuid4().hex[:10]}"
    password = secrets.token_urlsafe(24)
    started = time.monotonic()
    run(
        [
            "docker", "run", "-d", "--rm", "--name", container,
            "-e", f"POSTGRES_PASSWORD={password}",
            "-p", "127.0.0.1::5432", "postgres:16-alpine",
        ]
    )
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            ready = run(
                ["docker", "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")

        checks = run_acceptance(container)
        evidence = {
            "title": "Migration 437 governance operator binding and Gateway tension actions",
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
