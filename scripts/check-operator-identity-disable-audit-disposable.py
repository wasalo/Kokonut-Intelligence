#!/usr/bin/env python3
"""Check operator identity disable audit constraints and ACLs on disposable PostgreSQL."""

from __future__ import annotations

import json
import secrets
import subprocess
import time
import uuid
from pathlib import Path

import psycopg2
from psycopg2 import errors

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/525_operator_identity_disable_audit.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-039-identity-disable-audit.json"
IMAGE = "postgis/postgis:16-3.4"
ROLES = (
    "kokonut_runtime",
    "kokonut_worker_login",
    "kokonut_directus_runtime",
    "kokonut_operator_auth",
    "kokonut_operator_auth_owner",
    "kokonut_remote_sensing_login",
    "kokonut_analytics_reader",
    "kokonut_worker_execution",
)


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False
    )
    if result.returncode:
        rendered = [
            f"{item.split('=', 1)[0]}=<redacted>"
            if item.startswith(("POSTGRES_PASSWORD=", "PGPASSWORD="))
            else item
            for item in command
        ]
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed: {' '.join(rendered)}\n{details}")
    return result.stdout


def main() -> int:
    suffix = uuid.uuid4().hex[:12]
    container = f"kokonut-operator-disable-audit-{suffix}"
    password = secrets.token_urlsafe(32)
    evidence = {
        "migration": MIGRATION.name,
        "postgres_image": IMAGE,
        "checks": [],
        "candidate_or_legacy_database_touched": False,
    }
    try:
        run([
            "docker", "run", "--detach", "--rm", "--name", container,
            "--publish", "127.0.0.1::5432",
            "--env", f"POSTGRES_PASSWORD={password}", IMAGE,
        ])
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            ready = subprocess.run(
                ["docker", "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
                text=True,
                capture_output=True,
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")

        port_output = run(["docker", "port", container, "5432/tcp"]).strip()
        port = int(port_output.rsplit(":", 1)[1])
        connection = psycopg2.connect(
            host="127.0.0.1",
            port=port,
            dbname="postgres",
            user="postgres",
            password=password,
            connect_timeout=5,
        )
        connection.autocommit = True
        try:
            with connection.cursor() as cursor:
                for role in ROLES:
                    cursor.execute(f'CREATE ROLE "{role}" NOLOGIN')
                cursor.execute(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    "GRANT ALL ON TABLES TO PUBLIC, "
                    + ", ".join(f'"{role}"' for role in ROLES)
                )
                cursor.execute(
                    "CREATE TABLE public.operator_identity (id UUID PRIMARY KEY)"
                )
                cursor.execute(
                    "INSERT INTO public.operator_identity VALUES (%s)",
                    ("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",),
                )
                cursor.execute(MIGRATION.read_text(encoding="utf-8"))
                evidence["checks"].append("migration applies to minimal identity schema")

                cursor.execute(
                    """SELECT has_table_privilege(%s,
                                'public.operator_identity_admin_audit', %s)""",
                    ("postgres", "INSERT"),
                )
                if not cursor.fetchone()[0]:
                    raise AssertionError("migration owner cannot write the audit ledger")

                cursor.execute(
                    """SELECT rolname
                         FROM pg_roles
                        WHERE left(rolname, 8) = 'kokonut_'
                          AND (
                              has_table_privilege(rolname, 'public.operator_identity_admin_audit', 'SELECT')
                              OR has_table_privilege(rolname, 'public.operator_identity_admin_audit', 'INSERT')
                              OR has_table_privilege(rolname, 'public.operator_identity_admin_audit', 'UPDATE')
                              OR has_table_privilege(rolname, 'public.operator_identity_admin_audit', 'DELETE')
                              OR has_table_privilege(rolname, 'public.operator_identity_admin_audit', 'TRUNCATE')
                          )"""
                )
                if cursor.fetchall():
                    raise AssertionError("a Kokonut runtime/security role retains audit table access")
                cursor.execute(
                    """SELECT EXISTS (
                              SELECT 1
                                FROM pg_class AS relation
                                CROSS JOIN LATERAL aclexplode(
                                    COALESCE(relation.relacl,
                                             acldefault('r', relation.relowner))
                                ) AS privilege
                               WHERE relation.oid =
                                     'public.operator_identity_admin_audit'::regclass
                                 AND privilege.grantee = 0
                          )"""
                )
                if cursor.fetchone()[0]:
                    raise AssertionError("PUBLIC retains audit table privileges")
                evidence["checks"].append("all kokonut_* roles have no audit table privileges")
                evidence["checks"].append("PUBLIC has no audit table privileges despite a broad default grant")

                cursor.execute(
                    """INSERT INTO public.operator_identity_admin_audit
                             (operator_id, action, actor_label, reason)
                         VALUES (%s, 'identity_disabled', %s, %s)
                         RETURNING database_principal""",
                    (
                        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                        "fixture-admin",
                        "Synthetic disable review.",
                    ),
                )
                if cursor.fetchone()[0] != "postgres":
                    raise AssertionError("audit row did not capture PostgreSQL SESSION_USER")
                evidence["checks"].append("valid audit row captures authenticated database login")

                for sql, expected, label in (
                    (
                        "UPDATE public.operator_identity_admin_audit SET reason = 'changed'",
                        errors.RaiseException,
                        "update rejected",
                    ),
                    (
                        "DELETE FROM public.operator_identity_admin_audit",
                        errors.RaiseException,
                        "delete rejected",
                    ),
                    (
                        "TRUNCATE public.operator_identity_admin_audit",
                        errors.RaiseException,
                        "truncate rejected",
                    ),
                    (
                        "INSERT INTO public.operator_identity_admin_audit "
                        "(operator_id, action, actor_label, reason) "
                        "VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', "
                        "'identity_disabled', ' ', 'reason')",
                        errors.CheckViolation,
                        "blank actor rejected",
                    ),
                    (
                        "INSERT INTO public.operator_identity_admin_audit "
                        "(operator_id, action, actor_label, reason) "
                        "VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', "
                        "'identity_disabled', 'actor', ' ')",
                        errors.CheckViolation,
                        "blank reason rejected",
                    ),
                ):
                    try:
                        cursor.execute(sql)
                    except expected:
                        evidence["checks"].append(label)
                    else:
                        raise AssertionError(f"unexpectedly accepted {sql}")
                cursor.execute("SELECT count(*) FROM public.operator_identity_admin_audit")
                if cursor.fetchone()[0] != 1:
                    raise AssertionError("a denied mutation changed audit history")
                evidence["checks"].append("denied mutations preserve the original audit row")
        finally:
            connection.close()

        evidence["status"] = "passed"
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        subprocess.run(["docker", "rm", "--force", container], capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
