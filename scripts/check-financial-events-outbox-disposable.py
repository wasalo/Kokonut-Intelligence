#!/usr/bin/env python3
"""Apply/replay migration 434 and verify financial outbox writes on disposable PostgreSQL."""

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
OUTBOX_SCHEMA = ROOT / "schemas/postgres/335_clickhouse_outbox.sql"
MIGRATION = ROOT / "schemas/postgres/434_financial_events_clickhouse_outbox.sql"
DEFAULT_OUTPUT = (
    ROOT
    / "docs/refactor/builds/2026-10-18-recovery/financial-events-outbox-disposable.json"
)
LOCATION_ID = "11111111-1111-4111-8111-111111111111"
SALE_ID = "22222222-2222-4222-8222-222222222222"
ZERO_SALE_ID = "33333333-3333-4333-8333-333333333333"
EXPENSE_ID = "44444444-4444-4444-8444-444444444444"
ROLLED_BACK_ID = "55555555-5555-4555-8555-555555555555"


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


def docker_sql(docker: str, container: str, statement: str, *, check: bool = True):
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


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        check = run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
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

    container = f"kokonut-finance-outbox-{uuid.uuid4().hex[:10]}"
    image = os.environ.get("FINANCIAL_OUTBOX_POSTGRES_IMAGE", "postgres:16-alpine")
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
            "CREATE EXTENSION IF NOT EXISTS pgcrypto;\n"
            'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";\n'
            "CREATE SCHEMA kokonut_security;\n"
            "CREATE TABLE public.sales_event ("
            "id UUID PRIMARY KEY, location_id UUID NOT NULL, total_amount NUMERIC(15,2) NOT NULL, "
            "currency VARCHAR(10), buyer_type TEXT, status TEXT NOT NULL DEFAULT 'draft', created_at TIMESTAMPTZ);\n"
            "CREATE TABLE public.expense_event ("
            "id UUID PRIMARY KEY, location_id UUID NOT NULL, category TEXT NOT NULL, "
            "amount NUMERIC(15,2) NOT NULL, currency VARCHAR(10), status TEXT NOT NULL DEFAULT 'draft', "
            "created_at TIMESTAMPTZ);\n",
        )
        docker_sql(docker, container, OUTBOX_SCHEMA.read_text(encoding="utf-8"))
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        docker_sql(docker, container, migration_sql)
        docker_sql(docker, container, migration_sql)
        docker_sql(
            docker,
            container,
            "ALTER TABLE public.clickhouse_outbox ENABLE ROW LEVEL SECURITY;\n"
            "ALTER TABLE public.clickhouse_outbox FORCE ROW LEVEL SECURITY;\n",
        )

        docker_sql(
            docker,
            container,
            "CREATE ROLE financial_projection_test_writer NOLOGIN;\n"
            "GRANT INSERT ON public.sales_event, public.expense_event "
            "TO financial_projection_test_writer;\n"
            "SET ROLE financial_projection_test_writer;\n"
            f"INSERT INTO public.sales_event (id, location_id, total_amount, currency, buyer_type, status, created_at) "
            f"VALUES ('{SALE_ID}', '{LOCATION_ID}', 120.50, 'USD', 'direct', 'draft', '2026-10-18 12:34:56.789+00');\n"
            f"INSERT INTO public.sales_event (id, location_id, total_amount, currency, buyer_type, status, created_at) "
            f"VALUES ('{ZERO_SALE_ID}', '{LOCATION_ID}', 0, 'USD', 'direct', 'draft', '2026-10-18 12:34:56.789+00');\n"
            f"INSERT INTO public.expense_event (id, location_id, category, amount, currency, status, created_at) "
            f"VALUES ('{EXPENSE_ID}', '{LOCATION_ID}', 'irrigation', 400.25, 'DOP', 'draft', '2026-10-18 13:00:00+00');\n"
            "RESET ROLE;\n"
            f"BEGIN; SET ROLE financial_projection_test_writer; "
            f"INSERT INTO public.sales_event (id, location_id, total_amount, currency, created_at) "
            f"VALUES ('{ROLLED_BACK_ID}', '{LOCATION_ID}', 7.00, 'USD', '2026-10-18 14:00:00+00'); "
            "RESET ROLE;\n"
            "DO $$ BEGIN IF (SELECT count(*) FROM public.clickhouse_outbox) <> 3 THEN "
            "RAISE EXCEPTION 'trigger did not enqueue inside the caller transaction'; END IF; END $$;\n"
            "ROLLBACK;\n",
        )

        access_denied = docker_sql(
            docker,
            container,
            "SET ROLE financial_projection_test_writer;\n"
            "INSERT INTO public.clickhouse_outbox "
            "(event_key, source_table, source_id, target_table, columns, rows, payload_hash) "
            "VALUES ('forbidden', 'sales_event', 'synthetic', 'financial_events', '[]', '[]', repeat('0',64));\n",
            check=False,
        )
        if access_denied.returncode == 0 or "permission denied" not in access_denied.stderr.lower():
            raise AssertionError("source writer unexpectedly received direct outbox access")

        raw = docker_sql(
            docker,
            container,
            "SELECT jsonb_build_object("
            "'event_key', event_key, 'source_table', source_table, 'source_id', source_id, "
            "'target_table', target_table, 'columns', columns, 'rows', rows, "
            "'payload_hash', payload_hash) "
            "FROM public.clickhouse_outbox ORDER BY event_key;\n",
        ).stdout.splitlines()
        projections = [json.loads(line) for line in raw if line.strip()]
        if len(projections) != 2:
            raise AssertionError(f"expected two nonzero projections, received {len(projections)}")

        by_source = {projection["source_table"]: projection for projection in projections}
        if set(by_source) != {"sales_event", "expense_event"}:
            raise AssertionError("sales/expense source identity was not preserved")

        sales = by_source["sales_event"]
        sales_row = sales["rows"][0]
        if sales["event_key"] != f"financial:sales_event:{SALE_ID}":
            raise AssertionError("sales event key is not stable by source identity")
        if sales_row[1:7] != [SALE_ID, LOCATION_ID, "sales", "sales", "120.50", "USD"]:
            raise AssertionError(f"unexpected sales projection fields: {sales_row[1:7]}")
        if sales_row[7] != "120.50" or sales_row[8:10] != [None, None]:
            raise AssertionError("USD or nullable chain/token mapping is incorrect")

        expense = by_source["expense_event"]
        expense_row = expense["rows"][0]
        if expense_row[1:7] != [EXPENSE_ID, LOCATION_ID, "expense", "irrigation", "400.25", "DOP"]:
            raise AssertionError(f"unexpected expense projection fields: {expense_row[1:7]}")
        if expense_row[7] is not None:
            raise AssertionError("non-USD expense was incorrectly converted to USD")

        if any(len(projection["payload_hash"]) != 64 for projection in projections):
            raise AssertionError("projection payload hash is not SHA-256 hex")
        privileges = docker_sql(
            docker,
            container,
            "SELECT (SELECT rolcanlogin::TEXT FROM pg_roles WHERE rolname = 'kokonut_financial_projection_owner') "
            "|| ':' || has_column_privilege('kokonut_financial_projection_owner', 'public.clickhouse_outbox', 'event_key', 'INSERT')::TEXT "
            "|| ':' || has_column_privilege('kokonut_financial_projection_owner', 'public.clickhouse_outbox', 'event_key', 'SELECT')::TEXT "
            "|| ':' || has_column_privilege('kokonut_financial_projection_owner', 'public.clickhouse_outbox', 'rows', 'SELECT')::TEXT "
            "|| ':' || has_table_privilege('financial_projection_test_writer', 'public.clickhouse_outbox', 'INSERT')::TEXT;\n",
        ).stdout.strip().splitlines()[-1]
        if privileges != "false:true:true:false:false":
            raise AssertionError(f"unexpected owner/source writer ACL: {privileges}")

        result.update(
            {
                "result": "passed",
                "migration_apply": "passed",
                "migration_replay": "passed",
                "sales_projection": "passed",
                "expense_projection": "passed",
                "non_usd_amount_usd": "null",
                "zero_amount_omitted": True,
                "outbox_write_in_source_transaction": "passed; rollback removed source and outbox row",
                "forced_outbox_rls": "passed",
                "source_login_direct_outbox_write": "denied",
                "financial_projection_owner_can_login": False,
                "source_login_can_insert_outbox": False,
                "outbox_rows": len(projections),
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
