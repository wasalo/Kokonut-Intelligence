#!/usr/bin/env python3
"""Verify migrations 735–738 and role reprovisioning on disposable PostgreSQL 16."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MIGRATIONS = (
    ROOT / "schemas/postgres/735_runtime_location_baseline_read_only.sql",
    ROOT / "schemas/postgres/736_runtime_bio_ingredient_composition_reference_read_only.sql",
    ROOT / "schemas/postgres/737_runtime_data_freshness_config_read_only.sql",
    ROOT / "schemas/postgres/738_directus_reference_relations_read_only.sql",
)
FRESHNESS_WORKER_MIGRATION = ROOT / "schemas/postgres/645_isolated_data_freshness_worker.sql"
IMAGE = os.environ.get(
    "LOCATION_BASELINE_ACL_TEST_IMAGE",
    "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5",
)
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-11-01-recovery/runtime-read-only-735-738-disposable.json"
RUNTIME = "kokonut_runtime"
DIRECTUS = "kokonut_directus_runtime"
DIRECTUS_PASSWORD = secrets.token_urlsafe(32)
MUTATING_PRIVILEGES = ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
DIRECTUS_POLICY_SOURCES = {
    "location_baseline": "735_runtime_location_baseline_read_only.sql",
    "bio_ingredient_composition_reference": "736_runtime_bio_ingredient_composition_reference_read_only.sql",
    "bio_regional_input_availability": "736_runtime_bio_ingredient_composition_reference_read_only.sql",
    "data_freshness_config": "737_runtime_data_freshness_config_read_only.sql",
}
TABLES = {
    "location_baseline": {
        "owner": "kokonut_location_baseline_owner",
        "ddl": (
            "CREATE TABLE public.location_baseline ("
            "id uuid PRIMARY KEY, location_id uuid NOT NULL, effective_from date NOT NULL, "
            "marker text NOT NULL)"
        ),
        "fixture_insert": (
            "INSERT INTO public.location_baseline "
            "(id, location_id, effective_from, marker) VALUES "
            "(%s::uuid, %s::uuid, DATE '2026-01-01', 'fixture')"
        ),
        "fixture_params": (
            "b7350000-0000-0000-0000-000000000002",
            "b7350000-0000-0000-0000-000000000001",
        ),
        "column_grants": (
            "GRANT INSERT (id, marker), UPDATE (marker), REFERENCES (id) "
            "ON TABLE public.location_baseline TO kokonut_runtime"
        ),
        "read_sql": "SELECT marker FROM public.location_baseline WHERE id = %s::uuid",
        "read_params": ("b7350000-0000-0000-0000-000000000002",),
        "read_result": ("fixture",),
        "denied_writes": (
            "INSERT INTO public.location_baseline "
            "(id, location_id, effective_from, marker) VALUES "
            "('b7350000-0000-0000-0000-000000000003', "
            "'b7350000-0000-0000-0000-000000000001', DATE '2026-02-01', 'denied')",
            "UPDATE public.location_baseline SET marker = 'denied'",
            "DELETE FROM public.location_baseline",
            "TRUNCATE public.location_baseline",
        ),
        "writer_insert": (
            "INSERT INTO public.location_baseline "
            "(id, location_id, effective_from, marker) VALUES "
            "(%s::uuid, %s::uuid, DATE '2026-03-01', %s)"
        ),
        "writer_insert_params": (
            "b7350000-0000-0000-0000-00000000000a",
            "b7350000-0000-0000-0000-000000000001",
            "writer-check",
        ),
        "writer_update": ("UPDATE public.location_baseline SET marker = %s WHERE id = %s::uuid"),
        "writer_update_params": (
            "writer-check-updated",
            "b7350000-0000-0000-0000-000000000002",
        ),
        "writer_delete": "DELETE FROM public.location_baseline WHERE id = %s::uuid",
        "writer_delete_params": ("b7350000-0000-0000-0000-00000000000a",),
    },
    "bio_ingredient_composition_reference": {
        "owner": "kokonut_bio_ingredient_reference_owner",
        "ddl": (
            "CREATE TABLE public.bio_ingredient_composition_reference ("
            "id uuid PRIMARY KEY, ingredient_name text NOT NULL UNIQUE, "
            "ingredient_category text NOT NULL, composition_summary text NOT NULL, "
            "status text NOT NULL DEFAULT 'published')"
        ),
        "fixture_insert": (
            "INSERT INTO public.bio_ingredient_composition_reference "
            "(id, ingredient_name, ingredient_category, composition_summary) "
            "VALUES (%s::uuid, 'Synthetic bone meal', 'animal_concentrate', 'fixture')"
        ),
        "fixture_params": ("b7360000-0000-0000-0000-000000000002",),
        "column_grants": (
            "GRANT INSERT (ingredient_name), UPDATE (status), "
            "REFERENCES (ingredient_name) ON TABLE "
            "public.bio_ingredient_composition_reference TO kokonut_runtime"
        ),
        "read_sql": ("SELECT composition_summary FROM public.bio_ingredient_composition_reference WHERE id = %s::uuid"),
        "read_params": ("b7360000-0000-0000-0000-000000000002",),
        "read_result": ("fixture",),
        "denied_writes": (
            "INSERT INTO public.bio_ingredient_composition_reference "
            "(id, ingredient_name, ingredient_category, composition_summary) VALUES "
            "('b7360000-0000-0000-0000-000000000003', 'Denied', 'other', 'denied')",
            "UPDATE public.bio_ingredient_composition_reference SET status = 'draft'",
            "DELETE FROM public.bio_ingredient_composition_reference",
            "TRUNCATE public.bio_ingredient_composition_reference",
        ),
        "writer_insert": (
            "INSERT INTO public.bio_ingredient_composition_reference "
            "(id, ingredient_name, ingredient_category, composition_summary) VALUES "
            "(%s::uuid, 'Synthetic seed-admin row', 'other', %s)"
        ),
        "writer_insert_params": (
            "b7360000-0000-0000-0000-00000000000a",
            "writer-check",
        ),
        "writer_update": (
            "UPDATE public.bio_ingredient_composition_reference SET status = 'draft' WHERE id = %s::uuid"
        ),
        "writer_update_params": ("b7360000-0000-0000-0000-000000000002",),
        "writer_delete": ("DELETE FROM public.bio_ingredient_composition_reference WHERE id = %s::uuid"),
        "writer_delete_params": ("b7360000-0000-0000-0000-00000000000a",),
        "seed_upsert": (
            "INSERT INTO public.bio_ingredient_composition_reference "
            "(id, ingredient_name, ingredient_category, composition_summary) VALUES "
            "(%s::uuid, 'Synthetic bone meal', 'animal_concentrate', 'updated summary') "
            "ON CONFLICT (ingredient_name) DO UPDATE SET "
            "composition_summary = EXCLUDED.composition_summary"
        ),
        "seed_upsert_params": ("b7360000-0000-0000-0000-000000000004",),
        "seed_upsert_result_sql": (
            "SELECT id::text, composition_summary "
            "FROM public.bio_ingredient_composition_reference "
            "WHERE ingredient_name = 'Synthetic bone meal'"
        ),
        "seed_upsert_result": (
            "b7360000-0000-0000-0000-000000000002",
            "updated summary",
        ),
        "seed_runtime_read_result": ("updated summary",),
    },
    "bio_regional_input_availability": {
        "owner": "kokonut_bio_regional_reference_owner",
        "ddl": (
            "CREATE TABLE public.bio_regional_input_availability ("
            "id uuid PRIMARY KEY, region_scope text NOT NULL, input_name text NOT NULL, "
            "input_category text NOT NULL, country text, subregion text, seasonality text, "
            "cautions text[] NOT NULL DEFAULT '{}', quality_considerations text, "
            "typical_suppliers text, source_reference text, regional_summary text NOT NULL, "
            "public_summary text, evidence_maturity integer NOT NULL DEFAULT 3, "
            "status text NOT NULL DEFAULT 'published', metadata jsonb NOT NULL DEFAULT '{}', "
            "UNIQUE (region_scope, input_name))"
        ),
        "fixture_insert": (
            "INSERT INTO public.bio_regional_input_availability "
            "(id, region_scope, input_name, input_category, regional_summary, "
            "public_summary, evidence_maturity, status) VALUES "
            "(%s::uuid, 'caribbean', 'Synthetic seaweed', 'marine_material', "
            "'fixture regional summary', 'fixture public summary', 3, 'published')"
        ),
        "fixture_params": ("b7360000-0000-0000-0000-000000000102",),
        "column_grants": (
            "GRANT INSERT (input_name), UPDATE (status), REFERENCES (input_name) "
            "ON TABLE public.bio_regional_input_availability TO kokonut_runtime"
        ),
        "read_sql": ("SELECT input_name FROM public.v_public_bio_regional_input_summary WHERE id = %s::uuid"),
        "read_params": ("b7360000-0000-0000-0000-000000000102",),
        "read_result": ("Synthetic seaweed",),
        "denied_writes": (
            "INSERT INTO public.bio_regional_input_availability "
            "(id, region_scope, input_name, input_category, regional_summary) VALUES "
            "('b7360000-0000-0000-0000-000000000103', 'caribbean', 'Denied', "
            "'other', 'denied')",
            "UPDATE public.bio_regional_input_availability SET status = 'draft'",
            "DELETE FROM public.bio_regional_input_availability",
            "TRUNCATE public.bio_regional_input_availability",
        ),
        "writer_insert": (
            "INSERT INTO public.bio_regional_input_availability "
            "(id, region_scope, input_name, input_category, regional_summary) VALUES "
            "(%s::uuid, 'caribbean', 'Synthetic seed-admin input', 'other', %s)"
        ),
        "writer_insert_params": (
            "b7360000-0000-0000-0000-00000000010a",
            "writer-check",
        ),
        "writer_update": ("UPDATE public.bio_regional_input_availability SET status = 'draft' WHERE id = %s::uuid"),
        "writer_update_params": ("b7360000-0000-0000-0000-000000000102",),
        "writer_delete": ("DELETE FROM public.bio_regional_input_availability WHERE id = %s::uuid"),
        "writer_delete_params": ("b7360000-0000-0000-0000-00000000010a",),
        "seed_upsert": (
            "INSERT INTO public.bio_regional_input_availability "
            "(id, region_scope, input_name, input_category, regional_summary, "
            "public_summary, evidence_maturity, status) VALUES "
            "(%s::uuid, 'caribbean', 'Synthetic seaweed', 'marine_material', "
            "'updated regional summary', 'updated public summary', 3, 'published') "
            "ON CONFLICT (region_scope, input_name) DO UPDATE SET "
            "regional_summary = EXCLUDED.regional_summary, "
            "public_summary = EXCLUDED.public_summary"
        ),
        "seed_upsert_params": ("b7360000-0000-0000-0000-000000000104",),
        "seed_upsert_result_sql": (
            "SELECT id::text, regional_summary, public_summary "
            "FROM public.bio_regional_input_availability "
            "WHERE region_scope = 'caribbean' AND input_name = 'Synthetic seaweed'"
        ),
        "seed_upsert_result": (
            "b7360000-0000-0000-0000-000000000102",
            "updated regional summary",
            "updated public summary",
        ),
    },
    "data_freshness_config": {
        "owner": "kokonut_data_freshness_config_owner",
        "ddl": (
            "CREATE TABLE public.data_freshness_config ("
            "id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "
            "source_system varchar(100) NOT NULL UNIQUE, "
            "description text, expected_interval_minutes integer NOT NULL, "
            "stale_threshold_minutes integer NOT NULL, critical_threshold_minutes integer NOT NULL, "
            "location_scoped boolean DEFAULT false, is_active boolean DEFAULT true, "
            "metadata jsonb DEFAULT '{}', created_at timestamptz DEFAULT now(), "
            "updated_at timestamptz DEFAULT now(), alert_cooldown_minutes integer DEFAULT 60, "
            "escalation_cooldown_minutes integer DEFAULT 15)"
        ),
        "fixture_insert": (
            "INSERT INTO public.data_freshness_config "
            "(id, source_system, description, expected_interval_minutes, "
            "stale_threshold_minutes, critical_threshold_minutes, location_scoped, is_active, "
            "alert_cooldown_minutes, escalation_cooldown_minutes) VALUES "
            "(%s::uuid, 'synthetic_weather', 'fixture', 30, 60, 120, true, true, 10, 5)"
        ),
        "fixture_params": ("b7370000-0000-0000-0000-000000000001",),
        "column_grants": (
            "GRANT INSERT (source_system), UPDATE (is_active), REFERENCES (source_system) "
            "ON TABLE public.data_freshness_config TO kokonut_runtime"
        ),
        "read_sql": ("SELECT source_system FROM public.data_freshness_config WHERE id = %s::uuid"),
        "read_params": ("b7370000-0000-0000-0000-000000000001",),
        "read_result": ("synthetic_weather",),
        "denied_writes": (
            "INSERT INTO public.data_freshness_config "
            "(id, source_system, expected_interval_minutes, stale_threshold_minutes, "
            "critical_threshold_minutes) VALUES "
            "('b7370000-0000-0000-0000-000000000002', 'denied', 30, 60, 120)",
            "UPDATE public.data_freshness_config SET is_active = false",
            "DELETE FROM public.data_freshness_config",
            "TRUNCATE public.data_freshness_config",
        ),
        "writer_insert": (
            "INSERT INTO public.data_freshness_config "
            "(id, source_system, expected_interval_minutes, stale_threshold_minutes, "
            "critical_threshold_minutes) VALUES (%s::uuid, 'seed-admin-source', 30, 60, 120)"
        ),
        "writer_insert_params": ("b7370000-0000-0000-0000-00000000000a",),
        "writer_update": ("UPDATE public.data_freshness_config SET is_active = false WHERE id = %s::uuid"),
        "writer_update_params": ("b7370000-0000-0000-0000-000000000001",),
        "writer_delete": "DELETE FROM public.data_freshness_config WHERE id = %s::uuid",
        "writer_delete_params": ("b7370000-0000-0000-0000-00000000000a",),
        "seed_upsert": (
            "INSERT INTO public.data_freshness_config "
            "(source_system, description, expected_interval_minutes, stale_threshold_minutes, "
            "critical_threshold_minutes, location_scoped, is_active, alert_cooldown_minutes, "
            "escalation_cooldown_minutes) VALUES "
            "('synthetic_weather', 'updated fixture', 45, 90, 180, true, true, 20, 10) "
            "ON CONFLICT (source_system) DO UPDATE SET "
            "description = EXCLUDED.description, "
            "expected_interval_minutes = EXCLUDED.expected_interval_minutes, "
            "stale_threshold_minutes = EXCLUDED.stale_threshold_minutes, "
            "critical_threshold_minutes = EXCLUDED.critical_threshold_minutes, "
            "location_scoped = EXCLUDED.location_scoped, is_active = EXCLUDED.is_active"
        ),
        "seed_upsert_params": (),
        "seed_upsert_result_sql": (
            "SELECT description, expected_interval_minutes, stale_threshold_minutes, "
            "critical_threshold_minutes, location_scoped, is_active "
            "FROM public.data_freshness_config WHERE source_system = 'synthetic_weather'"
        ),
        "seed_upsert_result": ("updated fixture", 45, 90, 180, True, True),
    },
}


def run(
    command: list[str],
    *,
    input_text: str | None = None,
    check: bool = True,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if check and result.returncode:
        safe = ["POSTGRES_PASSWORD=<redacted>" if part.startswith("POSTGRES_PASSWORD=") else part for part in command]
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(safe[:6])} …\n{details[-3000:]}")
    return result


def connect(port: int, password: str):
    deadline = time.monotonic() + 60
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            return psycopg2.connect(
                host="127.0.0.1",
                port=port,
                dbname="postgres",
                user="postgres",
                password=password,
                connect_timeout=3,
            )
        except psycopg2.Error as exc:
            last_error = type(exc).__name__
            time.sleep(0.25)
    raise RuntimeError(f"disposable PostgreSQL did not become ready ({last_error})")


def _fixture(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE ROLE kokonut_runtime NOLOGIN NOINHERIT NOSUPERUSER "
            "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
        )
        cursor.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN PASSWORD %s INHERIT NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            ).format(sql.Identifier(DIRECTUS)),
            (DIRECTUS_PASSWORD,),
        )
        cursor.execute("CREATE SCHEMA kokonut_security")
        cursor.execute(
            "CREATE TABLE kokonut_security.directus_relation_privilege_policy ("
            "schema_name text NOT NULL, relation_name text NOT NULL, "
            "access_mode text NOT NULL, source_migration text NOT NULL, "
            "PRIMARY KEY (schema_name, relation_name))"
        )
        for relation, config in TABLES.items():
            owner = config["owner"]
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                ).format(sql.Identifier(owner))
            )
            cursor.execute(config["ddl"])
            cursor.execute(
                sql.SQL("ALTER TABLE {} OWNER TO {}").format(sql.Identifier("public", relation), sql.Identifier(owner))
            )
            cursor.execute(config["fixture_insert"], config["fixture_params"])
            # Simulate a compatibility table grant plus independent stale
            # column grants which table-level REVOKE does not remove.
            cursor.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON TABLE {} TO {}").format(
                    sql.Identifier("public", relation), sql.Identifier(RUNTIME)
                )
            )
            cursor.execute(config["column_grants"])
            cursor.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON TABLE {} TO {}").format(
                    sql.Identifier("public", relation), sql.Identifier(DIRECTUS)
                )
            )
            cursor.execute(
                config["column_grants"].replace(
                    "TO kokonut_runtime", "TO kokonut_directus_runtime"
                )
            )
        cursor.execute("CREATE TABLE public.evidence_maturity_level (level integer PRIMARY KEY, label text NOT NULL)")
        cursor.execute("INSERT INTO public.evidence_maturity_level (level, label) VALUES (3, 'verified')")
        cursor.execute(
            "CREATE VIEW public.v_public_bio_regional_input_summary AS "
            "SELECT r.id, r.region_scope, r.input_name, r.input_category, r.country, "
            "r.subregion, r.seasonality, r.cautions, r.quality_considerations, "
            "r.typical_suppliers, r.source_reference, r.public_summary, "
            "r.evidence_maturity, em.label AS evidence_maturity_label, r.metadata "
            "FROM public.bio_regional_input_availability AS r "
            "LEFT JOIN public.evidence_maturity_level AS em ON em.level = r.evidence_maturity "
            "WHERE r.status = 'published' AND r.evidence_maturity >= 3 "
            "AND NULLIF(TRIM(COALESCE(r.public_summary, '')), '') IS NOT NULL"
        )
        cursor.execute("GRANT SELECT ON TABLE public.v_public_bio_regional_input_summary TO kokonut_runtime")
        cursor.execute(
            "CREATE ROLE kokonut_freshness_owner NOLOGIN NOINHERIT NOSUPERUSER "
            "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
        )
        cursor.execute(
            "CREATE ROLE kokonut_freshness_login LOGIN NOINHERIT NOSUPERUSER "
            "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
        )
        cursor.execute("GRANT USAGE ON SCHEMA public TO kokonut_freshness_owner")
        cursor.execute("GRANT USAGE, CREATE ON SCHEMA kokonut_security TO kokonut_freshness_owner")
        cursor.execute("GRANT USAGE ON SCHEMA kokonut_security TO kokonut_freshness_login")
        cursor.execute(
            "GRANT SELECT (id, source_system, is_active, location_scoped, "
            "stale_threshold_minutes, critical_threshold_minutes, alert_cooldown_minutes, "
            "escalation_cooldown_minutes) ON public.data_freshness_config "
            "TO kokonut_freshness_owner"
        )
        freshness_source = FRESHNESS_WORKER_MIGRATION.read_text(encoding="utf-8")
        freshness_function = re.search(
            r"CREATE OR REPLACE FUNCTION kokonut_security\.list_freshness_configs\(.*?\n\$\$;",
            freshness_source,
            re.IGNORECASE | re.DOTALL,
        )
        if freshness_function is None:
            raise AssertionError("migration 645's bounded freshness config function was not found")
        cursor.execute(freshness_function.group(0))
        cursor.execute("ALTER FUNCTION kokonut_security.list_freshness_configs(text) OWNER TO kokonut_freshness_owner")
        cursor.execute("REVOKE ALL ON FUNCTION kokonut_security.list_freshness_configs(text) FROM PUBLIC")
        cursor.execute(
            "GRANT EXECUTE ON FUNCTION kokonut_security.list_freshness_configs(text) TO kokonut_freshness_login"
        )
    connection.commit()


def _table_privileges(connection, role: str, relation: str) -> dict[str, bool]:
    privileges = ("SELECT", *MUTATING_PRIVILEGES)
    qualified_relation = f"public.{relation}"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT " + ", ".join("has_table_privilege(%s, %s, %s)" for _ in privileges),
            tuple(value for privilege in privileges for value in (role, qualified_relation, privilege)),
        )
        values = cursor.fetchone()
    return dict(zip(privileges, values, strict=True))


def _column_write_privileges(connection, role: str, relation: str) -> dict[str, dict[str, bool]]:
    result: dict[str, dict[str, bool]] = {}
    qualified_relation = f"public.{relation}"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT attname FROM pg_catalog.pg_attribute "
            "WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped",
            (qualified_relation,),
        )
        columns = [row[0] for row in cursor.fetchall()]
        for column in columns:
            cursor.execute(
                "SELECT has_column_privilege(%s, %s, %s, 'INSERT'), "
                "has_column_privilege(%s, %s, %s, 'UPDATE'), "
                "has_column_privilege(%s, %s, %s, 'REFERENCES')",
                (role, qualified_relation, column) * 3,
            )
            insert, update, references = cursor.fetchone()
            result[column] = {
                "INSERT": insert,
                "UPDATE": update,
                "REFERENCES": references,
            }
    return result


def _assert_read_only(connection) -> None:
    for relation in TABLES:
        privileges = _table_privileges(connection, RUNTIME, relation)
        if not privileges["SELECT"] or any(privileges[name] for name in MUTATING_PRIVILEGES):
            raise AssertionError(f"unexpected runtime table ACL for {relation}: {privileges}")
        column_privileges = _column_write_privileges(connection, RUNTIME, relation)
        if any(any(privilege.values()) for privilege in column_privileges.values()):
            raise AssertionError(f"runtime column write grants remain for {relation}: {column_privileges}")


def _assert_directus_read_only(connection) -> None:
    connection.commit()
    if connection.autocommit:
        connection.autocommit = False
    for relation, config in TABLES.items():
        privileges = _table_privileges(connection, DIRECTUS, relation)
        if not privileges["SELECT"] or any(
            privileges[name] for name in MUTATING_PRIVILEGES
        ):
            raise AssertionError(f"unexpected Directus table ACL for {relation}: {privileges}")
        column_privileges = _column_write_privileges(connection, DIRECTUS, relation)
        if any(any(privilege.values()) for privilege in column_privileges.values()):
            raise AssertionError(
                f"Directus column write grants remain for {relation}: {column_privileges}"
            )
        with connection.cursor() as cursor:
            cursor.execute("SET ROLE kokonut_directus_runtime")
            cursor.execute(f"SELECT count(*) >= 0 FROM public.{relation}")
            if cursor.fetchone() != (True,):
                raise AssertionError(f"Directus SELECT could not read {relation}")
            cursor.execute("RESET ROLE")
            cursor.execute(
                "SELECT source_migration FROM kokonut_security.directus_relation_privilege_policy "
                "WHERE schema_name = 'public' AND relation_name = %s",
                (relation,),
            )
            source_migration = cursor.fetchone()
            if source_migration != (DIRECTUS_POLICY_SOURCES[relation],):
                raise AssertionError(
                    f"Directus policy source is wrong for {relation}: {source_migration}"
                )
        connection.commit()
        for index, statement in enumerate(config["denied_writes"]):
            with connection.cursor() as cursor:
                savepoint = f"directus_{relation}_write_{index}"
                cursor.execute(sql.SQL("SAVEPOINT {}").format(sql.Identifier(savepoint)))
                try:
                    cursor.execute("SET LOCAL ROLE kokonut_directus_runtime")
                    cursor.execute(statement)
                except psycopg2.errors.InsufficientPrivilege:
                    cursor.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(sql.Identifier(savepoint)))
                    cursor.execute("RESET ROLE")
                else:
                    cursor.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(sql.Identifier(savepoint)))
                    cursor.execute("RESET ROLE")
                    raise AssertionError(
                        f"Directus mutation unexpectedly succeeded on {relation}: {statement}"
                    )
                cursor.execute(sql.SQL("RELEASE SAVEPOINT {}").format(sql.Identifier(savepoint)))
            connection.commit()
    connection.rollback()


def _assert_runtime_behavior(connection) -> None:
    connection.commit()
    if connection.autocommit:
        connection.autocommit = False
    with connection.cursor() as cursor:
        cursor.execute("SET ROLE kokonut_runtime")
        for relation, config in TABLES.items():
            cursor.execute(config["read_sql"], config["read_params"])
            if cursor.fetchone() != config["read_result"]:
                raise AssertionError(f"runtime SELECT could not read {relation}")
            for index, statement in enumerate(config["denied_writes"]):
                savepoint = f"runtime_{relation}_write_{index}"
                cursor.execute(sql.SQL("SAVEPOINT {}").format(sql.Identifier(savepoint)))
                try:
                    cursor.execute(statement)
                except psycopg2.errors.InsufficientPrivilege:
                    cursor.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(sql.Identifier(savepoint)))
                else:
                    raise AssertionError(f"runtime mutation unexpectedly succeeded on {relation}: {statement}")
        cursor.execute("RESET ROLE")
    connection.rollback()


def _assert_seed_upserts(connection) -> dict[str, str]:
    results = {}
    connection.commit()
    if connection.autocommit:
        connection.autocommit = False
    with connection.cursor() as cursor:
        # This disposable checker runs as the PostgreSQL superuser. It models
        # production seed/admin activity, which uses administrative `kokonut`,
        # rather than inventing a dedicated maintenance login.
        cursor.execute("SET ROLE postgres")
        for relation, config in TABLES.items():
            if "seed_upsert" not in config:
                continue
            cursor.execute(config["seed_upsert"], config["seed_upsert_params"])
            cursor.execute(config["seed_upsert_result_sql"])
            if cursor.fetchone() != config["seed_upsert_result"]:
                raise AssertionError(f"seed/admin upsert failed on {relation}")
            if "seed_runtime_read_result" in config:
                config["read_result"] = config["seed_runtime_read_result"]
            results[relation] = "synthetic ON CONFLICT seed upsert succeeded"
        cursor.execute("RESET ROLE")
    connection.commit()
    return results


def _assert_freshness_worker_read(connection) -> dict[str, str]:
    # PostgreSQL requires SET SESSION AUTHORIZATION outside an explicit
    # transaction. Autocommit also makes the function execute under the
    # synthetic worker session identity without altering the host role.
    connection.commit()
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION AUTHORIZATION kokonut_freshness_login")
            cursor.execute("SELECT * FROM kokonut_security.list_freshness_configs(%s)", (None,))
            rows = cursor.fetchall()
            if len(rows) != 1:
                raise AssertionError("bounded freshness config read returned the wrong row count")
            observed = (
                str(rows[0][0]),
                rows[0][1],
                rows[0][2],
                rows[0][3],
                rows[0][4],
                rows[0][5],
                rows[0][6],
            )
            expected = (
                "b7370000-0000-0000-0000-000000000001",
                "synthetic_weather",
                90,
                180,
                True,
                10,
                5,
            )
            if observed != expected:
                raise AssertionError(f"bounded freshness config read changed: {observed}")
            cursor.execute("RESET SESSION AUTHORIZATION")
    finally:
        connection.autocommit = False
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_table_privilege('kokonut_freshness_login', "
            "'public.data_freshness_config', 'SELECT'), "
            "has_function_privilege('kokonut_freshness_login', "
            "'kokonut_security.list_freshness_configs(text)', 'EXECUTE')"
        )
        if cursor.fetchone() != (False, True):
            raise AssertionError("freshness worker direct-table/function grants changed")
    connection.rollback()
    return {"migration-645 bounded config reader": "preserved and callable"}


def _capture_preserved_access(connection) -> dict[str, object]:
    result = {}
    for relation, config in TABLES.items():
        owner = config["owner"]
        owner_privileges = _table_privileges(connection, owner, relation)
        seed_admin_privileges = _table_privileges(connection, "postgres", relation)
        if not all(owner_privileges.values()) or not all(seed_admin_privileges.values()):
            raise AssertionError(f"owner/seed-admin privileges are incomplete on {relation}")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE oid = %s::regclass",
                (f"public.{relation}",),
            )
            if cursor.fetchone() != (owner,):
                raise AssertionError(f"unexpected owner for {relation}")
        result[relation] = {
            "owner": owner,
            "owner_privileges": owner_privileges,
            "seed_admin_privileges": seed_admin_privileges,
        }
    return result


def _assert_preserved_writers(connection, before: dict[str, object]) -> dict[str, object]:
    connection.commit()
    if connection.autocommit:
        connection.autocommit = False
    with connection.cursor() as cursor:
        for relation, config in TABLES.items():
            for role in (config["owner"], "postgres"):
                cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
                cursor.execute(config["writer_insert"], config["writer_insert_params"])
                cursor.execute(config["writer_update"], config["writer_update_params"])
                cursor.execute(config["writer_delete"], config["writer_delete_params"])
                cursor.execute("RESET ROLE")
    connection.rollback()
    after = _capture_preserved_access(connection)
    if before != after:
        raise AssertionError("migration changed table owner or seed-admin/owner grants")
    return {relation: "owner and seed/admin writes preserved" for relation in TABLES}


def check_database(port: int, password: str) -> dict[str, object]:
    from services.migration import runtime_role

    connection = connect(port, password)
    try:
        _fixture(connection)
        preserved_before = _capture_preserved_access(connection)
        connection.commit()
        connection.autocommit = True
        migration_hashes = {}
        for migration_path in MIGRATIONS:
            migration = migration_path.read_text(encoding="utf-8")
            migration_hashes[migration_path.name] = hashlib.sha256(migration.encode()).hexdigest()
            with connection.cursor() as cursor:
                cursor.execute(migration)
                cursor.execute(migration)
        _assert_read_only(connection)
        _assert_directus_read_only(connection)
        _assert_runtime_behavior(connection)
        seed_upserts = _assert_seed_upserts(connection)
        freshness_worker_read = _assert_freshness_worker_read(connection)
        preserved = _assert_preserved_writers(connection, preserved_before)
        connection.commit()

        from services.migration.directus_role import provision_directus_role

        directus_provisioning = provision_directus_role(
            connection,
            database="postgres",
            admin_user="postgres",
            directus_user=DIRECTUS,
            directus_password=DIRECTUS_PASSWORD,
        )
        _assert_directus_read_only(connection)

        # Simulate later one-time compatibility grants and reapply the actual
        # scoped-boundary helper used by runtime-role provisioning.
        with connection.cursor() as cursor:
            for relation, config in TABLES.items():
                cursor.execute(
                    sql.SQL("GRANT ALL PRIVILEGES ON TABLE {} TO {}").format(
                        sql.Identifier("public", relation), sql.Identifier(RUNTIME)
                    )
                )
                cursor.execute(config["column_grants"])
            applied = runtime_role._apply_scoped_write_boundary(cursor, sql.Identifier(RUNTIME))
            runtime_role._verify_scoped_write_boundary(cursor, RUNTIME)
        connection.commit()
        if any(applied["relations"].get(relation) is not True for relation in TABLES):
            raise AssertionError("runtime provisioner omitted a reviewed C1 relation")
        _assert_read_only(connection)
        _assert_runtime_behavior(connection)
        _assert_directus_read_only(connection)
        _assert_freshness_worker_read(connection)
        _assert_preserved_writers(connection, preserved_before)

        return {
            "ok": True,
            "migrations": list(migration_hashes),
            "migration_sha256": migration_hashes,
            "migration_apply_and_replay": "passed",
            "relations": list(TABLES),
            "runtime_select": "preserved for all four reviewed relations",
            "runtime_table_and_column_dml": "denied for all four reviewed relations",
            "runtime_provisioner_reapplication": "passed",
            "directus_role_provisioner": directus_provisioning["status"],
            "directus_select_and_denied_mutation_before_and_after_provisioning": "passed",
            "seed_style_upserts": seed_upserts,
            "isolated_freshness_worker_read": freshness_worker_read,
            "seed_admin_and_owner_access": preserved,
            "database": "disposable PostgreSQL 16 only",
            "container_network": "dedicated disposable bridge; no external service calls",
            "host_binding": "ephemeral 127.0.0.1 only",
            "candidate_legacy_production_touched": False,
        }
    finally:
        connection.close()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is required for disposable PostgreSQL acceptance")

    suffix = uuid.uuid4().hex[:10]
    network = f"kokonut-reference-acl-{suffix}"
    container = f"kokonut-reference-acl-pg16-{suffix}"
    password = secrets.token_urlsafe(32)
    network_created = False
    container_started = False
    try:
        run([docker, "network", "create", network])
        network_created = True
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
                network,
                "--env",
                f"POSTGRES_PASSWORD={password}",
                "-p",
                "127.0.0.1::5432",
                IMAGE,
            ]
        )
        container_started = True
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            ready = run([docker, "exec", container, "pg_isready", "-U", "postgres"], check=False)
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")

        bindings = json.loads(run([docker, "inspect", "--format", "{{json .NetworkSettings.Ports}}", container]).stdout)
        candidates = bindings.get("5432/tcp") or []
        binding = next((item for item in candidates if item.get("HostIp") == "127.0.0.1"), None)
        if binding is None:
            raise RuntimeError("disposable database did not bind to loopback only")

        evidence = check_database(int(binding["HostPort"]), password)
        evidence["docker_image"] = IMAGE
        evidence["completed_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 0
    finally:
        if container_started:
            run([docker, "rm", "--force", container], check=False)
        if network_created:
            run([docker, "network", "rm", network], check=False)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"location_baseline runtime boundary check failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)
