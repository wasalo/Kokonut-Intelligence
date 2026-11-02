#!/usr/bin/env python3
"""Exercise metric Kernel functions on an isolated network-disabled PostgreSQL 16."""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/metric_value_kernel_disposable.sql"
MIGRATION = ROOT / "schemas/postgres/703_location_scoped_metric_value_kernel.sql"
DEFAULT_OUTPUT = (
    ROOT / "docs/refactor/builds/2026-10-30-recovery/metric-value-kernel-disposable.json"
)
IMAGE = "postgres:16"

OPERATOR = "a0000000-0000-4000-8000-000000000401"
REVIEWER = "a0000000-0000-4000-8000-000000000402"
LOCATION = "a0000000-0000-4000-8000-000000000201"
OTHER_LOCATION = "a0000000-0000-4000-8000-000000000202"
DEFINITION = "a0000000-0000-4000-8000-000000000601"


def run(command: list[str], *, input_text: str | None = None, check: bool = True):
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False
    )
    if check and result.returncode:
        detail = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{detail}"
        )
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


def last_nonempty(output: str) -> str:
    return next(line for line in reversed(output.splitlines()) if line.strip())


def scoped_call(
    container: str,
    *,
    actor: str,
    location: str,
    action: str,
    expression: str,
    check: bool = True,
):
    statement = f"""
        SET ROLE kokonut_runtime;
        SELECT set_config('test.actor_id', '{actor}', FALSE);
        SELECT set_config('test.location_id', '{location}', FALSE);
        SELECT set_config('test.actor_type', 'operator', FALSE);
        SELECT set_config('test.allowed_action', '{action}', FALSE);
        SELECT {expression};
        RESET ROLE;
    """
    return docker_sql(container, statement, check=check)


def json_call(result) -> dict:
    for line in reversed(result.stdout.splitlines()):
        try:
            value = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict):
            return value
    raise AssertionError(f"SQL function did not return a JSON object: {result.stdout}")


def run_acceptance(container: str) -> list[str]:
    checks = []
    docker_sql(container, FIXTURE.read_text())
    docker_sql(container, MIGRATION.read_text())
    docker_sql(container, MIGRATION.read_text())
    checks.append("migration 703 applies and replays on a disposable PostgreSQL 16 fixture")

    privilege = docker_sql(
        container,
        """
        SELECT has_function_privilege('kokonut_runtime',
                   'kokonut_security.create_location_metric_value_draft(uuid,uuid,uuid,text,date,date,numeric,text,text,uuid[],jsonb)', 'EXECUTE')
           AND has_function_privilege('kokonut_runtime',
                   'kokonut_security.verify_location_metric_value(uuid,uuid,uuid,text)', 'EXECUTE')
           AND has_function_privilege('kokonut_runtime',
                   'kokonut_security.list_location_metric_values(uuid,text,integer)', 'EXECUTE')
           AND NOT has_function_privilege('kokonut_directus_runtime',
                   'kokonut_security.create_location_metric_value_draft(uuid,uuid,uuid,text,date,date,numeric,text,text,uuid[],jsonb)', 'EXECUTE')
           AND NOT has_table_privilege('kokonut_runtime',
                   'public.metric_value_compute_receipt', 'SELECT')
           AND NOT has_table_privilege('kokonut_directus_runtime',
                   'public.metric_value_verification_receipt', 'SELECT')
           AND has_column_privilege('kokonut_metric_value_manager',
                   'public.operator_identity', 'enabled', 'SELECT')
           AND NOT has_column_privilege('kokonut_metric_value_manager',
                   'public.operator_identity', 'secret_label', 'SELECT')
           AND has_column_privilege('kokonut_metric_value_manager',
                   'public.operator_scope_grant', 'organization_id', 'SELECT')
           AND has_column_privilege('kokonut_metric_value_manager',
                   'public.location', 'organization_id', 'SELECT')
           AND has_table_privilege('kokonut_runtime', 'public.metric_value', 'SELECT');
        """,
    )
    if last_nonempty(privilege.stdout) != "t":
        raise AssertionError(f"metric function/table ACL contract failed: {privilege.stdout}")
    checks.append("runtime has bounded function access; Directus and runtime cannot read private receipts")

    def create(request_id: str, *, value: str = "3.2500", location: str = LOCATION):
        return json_call(
            scoped_call(
                container,
                actor=OPERATOR,
                location=location,
                action="compute",
                expression=(
                    "kokonut_security.create_location_metric_value_draft("
                    f"'{location}', '{request_id}', '{DEFINITION}', 'soil_organic_matter', "
                    "DATE '2026-01-01', DATE '2026-01-31', "
                    f"{value}::numeric, '%', 'soil_organic_matter', ARRAY[]::uuid[], '{{}}'::jsonb)"
                ),
            )
        )

    create_request = str(uuid.uuid4())
    draft = create(create_request)
    draft_replay = create(create_request)
    if draft["created"] is not True or draft_replay["created"] is not False:
        raise AssertionError("metric draft create/replay flags are inconsistent")
    if draft["metric_value_id"] != draft_replay["metric_value_id"]:
        raise AssertionError("metric draft retry did not preserve the created row")
    if draft["status"] != "draft" or draft["verified"] is not False:
        raise AssertionError("metric creation must remain an unverified draft")
    checks.append("draft creation is unverified, location-bound, and request-id replay-safe")

    collision = scoped_call(
        container,
        actor=OPERATOR,
        location=LOCATION,
        action="compute",
        expression=(
            "kokonut_security.create_location_metric_value_draft("
            f"'{LOCATION}', '{create_request}', '{DEFINITION}', 'soil_organic_matter', "
            "DATE '2026-01-01', DATE '2026-01-31', 8.0000::numeric, '%', "
            "'soil_organic_matter', ARRAY[]::uuid[], '{}'::jsonb)"
        ),
        check=False,
    )
    if collision.returncode == 0 or "P0001" not in (collision.stdout + collision.stderr):
        raise AssertionError("changed-payload retry must fail with SQLSTATE P0001")
    checks.append("request-id reuse with changed metric input is rejected")

    denied = scoped_call(
        container,
        actor=REVIEWER,
        location=LOCATION,
        action="read",
        expression=(
            "kokonut_security.create_location_metric_value_draft("
            f"'{LOCATION}', '{uuid.uuid4()}', '{DEFINITION}', 'soil_organic_matter', "
            "NULL::date, NULL::date, 1::numeric, '%', 'soil_organic_matter', "
            "ARRAY[]::uuid[], '{}'::jsonb)"
        ),
        check=False,
    )
    if denied.returncode == 0 or "42501" not in (denied.stdout + denied.stderr):
        raise AssertionError("a wrong-action location grant must fail with SQLSTATE 42501")
    checks.append("a signed context without the exact compute grant is denied")

    second = create(str(uuid.uuid4()), value="4.0000")
    other = create(str(uuid.uuid4()), value="9.0000", location=OTHER_LOCATION)
    page = json_call(
        scoped_call(
            container,
            actor=OPERATOR,
            location=LOCATION,
            action="read",
            expression=f"kokonut_security.list_location_metric_values('{LOCATION}', '0', 1)",
        )
    )
    if page["location_id"] != LOCATION or page["limit"] != 1:
        raise AssertionError("metric page is not bound to request scope")
    if not page["has_more"] or page["next_cursor"] != "1" or len(page["items"]) != 1:
        raise AssertionError("metric first-page continuation is inconsistent")
    expected_item_fields = {
        "metric_value_id", "metric_key", "display_name", "period_start", "period_end",
        "value", "unit", "status", "computed_at", "verified_at",
    }
    if set(page["items"][0]) != expected_item_fields:
        raise AssertionError("metric list leaks or omits response fields")
    if any(item["metric_value_id"] == other["metric_value_id"] for item in page["items"]):
        raise AssertionError("metric page crossed locations")
    checks.append("metric list uses the exact identity-minimized projection, stable pagination, and location filter")

    review_request = str(uuid.uuid4())
    verification_expression = (
        "kokonut_security.verify_location_metric_value("
        f"'{LOCATION}', '{draft['metric_value_id']}', '{review_request}', 'Reviewed evidence')"
    )
    review = json_call(
        scoped_call(
            container,
            actor=REVIEWER,
            location=LOCATION,
            action="verify",
            expression=verification_expression,
        )
    )
    replay = json_call(
        scoped_call(
            container,
            actor=REVIEWER,
            location=LOCATION,
            action="verify",
            expression=verification_expression,
        )
    )
    if review["status"] != "verified" or review["replayed"] is not False:
        raise AssertionError("first verification response is invalid")
    if replay["replayed"] is not True or replay["metric_value_id"] != draft["metric_value_id"]:
        raise AssertionError("verification retry did not replay the original decision")

    self_review = scoped_call(
        container,
        actor=OPERATOR,
        location=LOCATION,
        action="verify",
        expression=(
            "kokonut_security.verify_location_metric_value("
            f"'{LOCATION}', '{second['metric_value_id']}', '{uuid.uuid4()}', NULL)"
        ),
        check=False,
    )
    if self_review.returncode == 0 or "P0001" not in (self_review.stdout + self_review.stderr):
        raise AssertionError("metric computation operator must not review their own draft")

    verified_row = docker_sql(
        container,
        f"""
        SELECT verified AND verified_by = 'a0000000-0000-4000-8000-000000000402'::uuid
          FROM public.metric_value
         WHERE id = '{draft['metric_value_id']}'::uuid;
        """,
    )
    if last_nonempty(verified_row.stdout) != "t":
        raise AssertionError("verification did not persist reviewer attribution")
    checks.append("verification requires another operator, sets reviewer attribution, and replays idempotently")

    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    container = f"kokonut-metric-check-{secrets.token_hex(5)}"
    password = secrets.token_urlsafe(24)
    evidence = {
        "check": "location-scoped metric-value Kernel SQL",
        "postgres_image": IMAGE,
        "network": "none",
        "candidate_or_legacy_database_touched": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "checks": [],
    }
    try:
        run(
            [
                "docker", "run", "--detach", "--rm", "--network", "none",
                "--name", container, "--env", f"POSTGRES_PASSWORD={password}",
                IMAGE,
            ]
        )
        for _ in range(60):
            ready = run(["docker", "exec", container, "pg_isready", "-U", "postgres"], check=False)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise TimeoutError("disposable PostgreSQL did not become ready")
        evidence["checks"] = run_acceptance(container)
        evidence["status"] = "passed"
    except Exception as exc:
        evidence["status"] = "failed"
        evidence["failure"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        run(["docker", "stop", container], check=False)
        evidence["finished_at"] = datetime.now(timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
