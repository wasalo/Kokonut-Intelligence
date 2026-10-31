#!/usr/bin/env python3
"""Exercise runtime scoped-write ACL revocation on a disposable PostgreSQL 16."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

POSTGRES_IMAGE = (
    "postgis/postgis:16-3.4@sha256:"
    "44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5"
)
ARM64_POSTGRES_IMAGE = "kokonut-kernel-postgis-arm64:local"
DEFAULT_OUTPUT = (
    ROOT
    / "docs/refactor/builds/2026-10-30-recovery/"
    "runtime-consent-data-type-696-disposable.json"
)
APPEND_ONLY_MIGRATION = (
    ROOT / "schemas/postgres/652_runtime_append_only_data_access_log.sql"
)
ADVISORY_RULE_MIGRATION = (
    ROOT / "schemas/postgres/653_runtime_advisory_rule_read_only.sql"
)
CROP_FAMILY_MIGRATION = (
    ROOT / "schemas/postgres/654_runtime_crop_family_read_only.sql"
)
CROP_NUTRIENT_FACTOR_MIGRATION = (
    ROOT / "schemas/postgres/655_runtime_crop_nutrient_removal_factor_read_only.sql"
)
CERTIFICATION_TYPE_MIGRATION = (
    ROOT / "schemas/postgres/656_runtime_certification_type_read_only.sql"
)
REFERENCE_CATALOGS_MIGRATION = (
    ROOT / "schemas/postgres/657_runtime_reference_catalogs_read_only.sql"
)
EVIDENCE_MATURITY_MIGRATION = (
    ROOT / "schemas/postgres/658_runtime_evidence_maturity_read_only.sql"
)
SENSOR_TYPE_MIGRATION = ROOT / "schemas/postgres/659_runtime_sensor_type_read_only.sql"
WASTE_REFERENCE_MIGRATION = (
    ROOT / "schemas/postgres/660_runtime_waste_reference_catalogs_read_only.sql"
)
GRAPH_PROJECTION_TYPES_MIGRATION = (
    ROOT / "schemas/postgres/661_runtime_graph_projection_types_read_only.sql"
)
ACCESS_AUDIT_LOG_MIGRATION = (
    ROOT / "schemas/postgres/662_runtime_access_audit_log_append_only.sql"
)
AGENT_ACTION_LOG_MIGRATION = (
    ROOT / "schemas/postgres/663_runtime_agent_action_log_read_only.sql"
)
CARBON_BENCHMARK_MIGRATION = (
    ROOT / "schemas/postgres/664_runtime_carbon_benchmark_read_only.sql"
)
GHG_EMISSION_FACTOR_MIGRATION = (
    ROOT / "schemas/postgres/665_runtime_ghg_emission_factor_read_only.sql"
)
OPERATIONS_PROTOCOL_MIGRATION = (
    ROOT / "schemas/postgres/666_runtime_operations_protocol_read_only.sql"
)
STATIC_REFERENCE_CATALOGS_MIGRATION = (
    ROOT / "schemas/postgres/667_runtime_static_reference_catalogs_read_only.sql"
)
REPORTING_REGISTRY_MIGRATION = (
    ROOT / "schemas/postgres/668_runtime_reporting_registry_read_only.sql"
)
IMPACT_FRAMEWORK_CATALOGS_MIGRATION = (
    ROOT / "schemas/postgres/669_runtime_impact_framework_catalogs_read_only.sql"
)
EXPENSE_CATEGORY_MIGRATION = ROOT / "schemas/postgres/670_runtime_expense_category_read_only.sql"
CRISP_RISK_DIMENSION_MIGRATION = (
    ROOT / "schemas/postgres/671_runtime_crisp_risk_dimension_read_only.sql"
)
DFS_CURRENCY_MIGRATION = (
    ROOT / "schemas/postgres/672_runtime_dfs_currency_read_only.sql"
)
CROP_GDD_CONFIG_MIGRATION = (
    ROOT / "schemas/postgres/673_runtime_crop_gdd_config_read_only.sql"
)
PEST_DEGREE_DAY_CONFIG_MIGRATION = (
    ROOT / "schemas/postgres/674_runtime_pest_degree_day_config_read_only.sql"
)
REVENUE_MULTIPLIER_CONFIG_MIGRATION = (
    ROOT / "schemas/postgres/675_runtime_revenue_multiplier_config_read_only.sql"
)
REFERENCE_CLASS_MIGRATION = (
    ROOT / "schemas/postgres/676_runtime_reference_class_read_only.sql"
)
FARMER_CREDENTIAL_TYPE_MIGRATION = (
    ROOT / "schemas/postgres/677_runtime_farmer_credential_type_read_only.sql"
)
MARKET_REFERENCE_DATA_MIGRATION = (
    ROOT / "schemas/postgres/678_runtime_market_reference_data_read_only.sql"
)
QUANTITY_UNIT_MIGRATION = (
    ROOT / "schemas/postgres/679_runtime_quantity_unit_read_only.sql"
)
YIELD_BENCHMARK_MIGRATION = (
    ROOT / "schemas/postgres/680_runtime_yield_benchmark_read_only.sql"
)
METRIC_DEFINITION_MIGRATION = (
    ROOT / "schemas/postgres/681_runtime_metric_definition_read_only.sql"
)
SERVICE_REGISTRY_MIGRATION = (
    ROOT / "schemas/postgres/682_runtime_service_registry_read_only.sql"
)
CAPEX_BREAKDOWN_MIGRATION = (
    ROOT / "schemas/postgres/690_runtime_capex_breakdown_read_only.sql"
)
WATER_ACCESS_ATTESTATION_PLAN_MIGRATION = (
    ROOT
    / "schemas/postgres/691_runtime_water_access_attestation_plan_read_only.sql"
)
POLLINATOR_HIVE_MIGRATION = (
    ROOT / "schemas/postgres/692_runtime_pollinator_hive_writes_read_only.sql"
)
POLLINATOR_CAPTURE_MIGRATION = (
    ROOT / "schemas/postgres/693_runtime_pollinator_capture_writes_read_only.sql"
)
EVENT_HANDLER_MIGRATION = (
    ROOT / "schemas/postgres/694_runtime_event_handler_registry_read_only.sql"
)
CAPITAL_SOURCE_MIGRATION = (
    ROOT / "schemas/postgres/695_runtime_capital_source_read_only.sql"
)
CONSENT_DATA_TYPE_MIGRATION = (
    ROOT / "schemas/postgres/696_runtime_consent_data_type_read_only.sql"
)
PROCESS_BENCHMARK_MIGRATION = (
    ROOT / "schemas/postgres/697_runtime_process_benchmark_read_only.sql"
)
PUBLIC_FARM_SUMMARY_MIGRATION = (
    ROOT / "schemas/postgres/699_runtime_public_farm_summary_read_only.sql"
)
REFERENCE_CATALOGS = (
    "carbon_benchmark", "crop_gdd_config", "dfs_currency", "ghg_emission_factor", "cooperative_type",
    "pest_degree_day_config",
    "revenue_multiplier_config",
    "reference_class",
    "farmer_credential_type",
    "market_reference_data",
    "quantity_unit",
    "yield_benchmark",
    "metric_definition",
    "service_registry",
    "operations_protocol", "dfs_insurance_product_type", "evidence_maturity_level",
    "sensor_type", "waste_type", "disposal_method", "graph_node_type",
    "graph_edge_type", "process_maturity_level", "pollinator_species_reference",
    "gri_indicator", "governance_framework", "impact_framework", "impact_dimension",
    "expense_category", "crisp_risk_dimension",
)


def run(command: list[str], *, timeout: int = 90) -> str:
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode:
        safe_command = [
            "<redacted>" if item.startswith("POSTGRES_PASSWORD=") else item
            for item in command
        ]
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed: {' '.join(safe_command)}\n{details}")
    return result.stdout


def wait_for_database(host: str, port: int, password: str) -> None:
    deadline = time.monotonic() + 60
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            with psycopg2.connect(
                host=host,
                port=port,
                dbname="postgres",
                user="postgres",
                password=password,
                connect_timeout=3,
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    if cursor.fetchone() == (1,):
                        return
        except psycopg2.Error as exc:
            last_error = type(exc).__name__
            time.sleep(0.25)
    raise RuntimeError(f"disposable PostgreSQL did not become ready ({last_error})")


def _relation_privileges(connection, table: str) -> tuple[bool, bool, bool, bool]:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT has_table_privilege('kokonut_runtime', %s, 'SELECT'),
                      has_table_privilege('kokonut_runtime', %s, 'INSERT'),
                      has_table_privilege('kokonut_runtime', %s, 'UPDATE'),
                      has_table_privilege('kokonut_runtime', %s, 'DELETE')""",
            (f"public.{table}",) * 4,
        )
        return cursor.fetchone()


def check_boundary(
    *,
    image: str = POSTGRES_IMAGE,
    platform: str | None = None,
    dsn: str | None = None,
    database_image_id: str | None = None,
) -> dict[str, object]:
    from services.migration import runtime_role

    container = f"kokonut-runtime-acl-{uuid.uuid4().hex[:12]}"
    password = secrets.token_urlsafe(32)
    host = "127.0.0.1"
    created = False
    try:
        if dsn is None:
            image_info = run(
                [
                    "docker", "image", "inspect", image,
                    "--format", "{{.Os}}/{{.Architecture}} {{.Id}}",
                ]
            ).strip().split(maxsplit=1)
            if len(image_info) != 2:
                raise RuntimeError("could not identify the disposable PostgreSQL image")
            if platform is not None and image_info[0] != platform:
                raise RuntimeError("local PostgreSQL image does not match requested platform")

            command = ["docker", "run"]
            if platform is not None:
                command.extend(("--platform", platform))
            command.extend(
                (
                    "--pull=never", "--detach", "--rm", "--name", container,
                    "--publish", "127.0.0.1::5432",
                    "--env", f"POSTGRES_PASSWORD={password}", image,
                )
            )
            run(command)
            created = True
            published = run(["docker", "port", container, "5432/tcp"]).strip()
            port = int(published.rsplit(":", 1)[1])
            wait_for_database(host, port, password)
            connection = psycopg2.connect(
                host=host,
                port=port,
                dbname="postgres",
                user="postgres",
                password=password,
                connect_timeout=5,
            )
        else:
            image_info = [
                platform or "network-isolated",
                database_image_id or "image-identity-supplied-by-host-runner",
            ]
            connection = psycopg2.connect(dsn, connect_timeout=5)
        try:
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute(
                    "CREATE ROLE kokonut_runtime NOLOGIN NOSUPERUSER "
                    "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                )
                cursor.execute(
                    "CREATE ROLE kokonut_directus_runtime NOLOGIN NOSUPERUSER "
                    "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                )
                cursor.execute(
                    "CREATE ROLE kokonut_unrelated_probe NOLOGIN NOSUPERUSER "
                    "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                )
                cursor.execute(
                    "CREATE ROLE kokonut_event_dispatch_owner NOLOGIN NOINHERIT "
                    "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                )
                for role in (
                    "kokonut_pollinator_hive_writer",
                    "kokonut_pollinator_inspection_writer",
                    "kokonut_pollinator_hive_lifecycle_writer",
                    "kokonut_pollinator_review_writer",
                    "kokonut_pollinator_observation_writer",
                    "kokonut_pesticide_impact_writer",
                    "kokonut_pollinator_habitat_writer",
                ):
                    cursor.execute(
                        sql.SQL(
                            "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB "
                            "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                        ).format(sql.Identifier(role))
                    )
                relations = tuple(
                    dict.fromkeys(
                        (*runtime_role._RUNTIME_PRIVATE_TABLES,
                         *runtime_role._RUNTIME_MUTATION_TABLES)
                    )
                )
                service_registry_id = str(uuid.uuid4())
                capability_id = str(uuid.uuid4())
                for table in relations:
                    if table == "service_registry":
                        cursor.execute(
                            "CREATE TABLE public.service_registry ("
                            "id uuid PRIMARY KEY, name text NOT NULL UNIQUE, marker text NOT NULL)"
                        )
                        cursor.execute(
                            "INSERT INTO public.service_registry (id, name, marker) "
                            "VALUES (%s, 'gateway', 'synthetic-service-registry')",
                            (service_registry_id,),
                        )
                    elif table == "event_handler":
                        cursor.execute(
                            "CREATE TABLE public.event_handler ("
                            "id uuid PRIMARY KEY, handler_name text NOT NULL, "
                            "event_type text NOT NULL, module_path text NOT NULL, "
                            "function_name text NOT NULL, is_enabled boolean NOT NULL, "
                            "priority_order integer NOT NULL, timeout_seconds integer NOT NULL, "
                            "max_concurrency integer NOT NULL, created_at timestamptz NOT NULL, "
                            "updated_at timestamptz NOT NULL, marker text)"
                        )
                        cursor.execute(
                            "INSERT INTO public.event_handler ("
                            "id, handler_name, event_type, module_path, function_name, "
                            "is_enabled, priority_order, timeout_seconds, max_concurrency, "
                            "created_at, updated_at, marker) VALUES ("
                            "%s, 'synthetic-handler', 'synthetic.event', 'tests.handlers', "
                            "'handle', true, 1, 30, 1, now(), now(), 'synthetic')",
                            (str(uuid.uuid4()),),
                        )
                    elif table == "v_public_farm_summary":
                        cursor.execute(
                            "CREATE TABLE public.farm_summary_probe_source "
                            "(location_id uuid NOT NULL)"
                        )
                        cursor.execute(
                            "INSERT INTO public.farm_summary_probe_source "
                            "(location_id) VALUES (%s)",
                            (str(uuid.uuid4()),),
                        )
                        cursor.execute(
                            "CREATE VIEW public.v_public_farm_summary AS "
                            "SELECT location_id, count(*) AS farm_count "
                            "FROM public.farm_summary_probe_source GROUP BY location_id"
                        )
                    elif table == "consent_data_type":
                        cursor.execute(
                            "CREATE TABLE public.consent_data_type ("
                            "id uuid PRIMARY KEY, name text NOT NULL UNIQUE, "
                            "category text NOT NULL, default_retention_days integer, "
                            "marker text NOT NULL)"
                        )
                        cursor.execute(
                            "INSERT INTO public.consent_data_type "
                            "(id, name, category, default_retention_days, marker) "
                            "VALUES (%s, 'synthetic_category', 'environmental', NULL, 'synthetic')",
                            (str(uuid.uuid4()),),
                        )
                    else:
                        cursor.execute(
                            sql.SQL("CREATE TABLE {} (id uuid PRIMARY KEY, marker text)").format(
                                sql.Identifier("public", table)
                            )
                        )
                cursor.execute(
                    "CREATE TABLE public.business_capability (id uuid PRIMARY KEY)"
                )
                cursor.execute(
                    "INSERT INTO public.business_capability (id) VALUES (%s)",
                    (capability_id,),
                )
                cursor.execute(
                    "CREATE TABLE public.capability_service_map ("
                    "id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "
                    "capability_id uuid NOT NULL REFERENCES public.business_capability(id) ON DELETE CASCADE, "
                    "service_name text NOT NULL REFERENCES public.service_registry(name) ON DELETE CASCADE, "
                    "is_primary boolean NOT NULL DEFAULT true, UNIQUE (capability_id, service_name))"
                )
                cursor.execute(
                    "INSERT INTO public.yield_benchmark (id, marker) "
                    "VALUES (%s, %s)",
                    (str(uuid.uuid4()), "synthetic-yield-benchmark"),
                )
                cursor.execute(
                    "INSERT INTO public.metric_definition (id, marker) "
                    "VALUES (%s, %s)",
                    (str(uuid.uuid4()), "synthetic-metric-definition"),
                )
                cursor.execute(
                    "CREATE TABLE public.data_access_log "
                    "(id uuid PRIMARY KEY, marker text NOT NULL)"
                )
                cursor.execute(
                    "CREATE TABLE public.access_audit_log "
                    "(id uuid PRIMARY KEY, marker text NOT NULL)"
                )
                cursor.execute(
                    "INSERT INTO public.process_benchmark (id, marker) VALUES (%s, %s)",
                    (str(uuid.uuid4()), "synthetic-process-benchmark"),
                )
                cursor.execute(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
                    "IN SCHEMA public TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                    "ON public.agent_action_log TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON public.agent_action_log "
                    "TO kokonut_directus_runtime"
                )
                cursor.execute(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON public.carbon_benchmark "
                    "TO kokonut_directus_runtime"
                )
                cursor.execute(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON public.ghg_emission_factor "
                    "TO kokonut_directus_runtime"
                )
                cursor.execute(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON public.operations_protocol "
                    "TO kokonut_directus_runtime"
                )
                cursor.execute(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON public.event_handler "
                    "TO kokonut_directus_runtime"
                )
                cursor.execute(
                    "GRANT ALL PRIVILEGES ON public.capital_source "
                    "TO kokonut_directus_runtime"
                )
                cursor.execute(
                    "GRANT ALL PRIVILEGES ON public.consent_data_type "
                    "TO kokonut_directus_runtime"
                )
                cursor.execute(
                    "GRANT ALL PRIVILEGES ON public.process_benchmark "
                    "TO kokonut_directus_runtime"
                )
                cursor.execute(
                    "REVOKE ALL PRIVILEGES ON public.farm_summary_probe_source "
                    "FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime"
                )
                cursor.execute(
                    "GRANT SELECT, INSERT, UPDATE, DELETE "
                    "ON public.v_public_farm_summary TO kokonut_directus_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (marker), UPDATE (marker), REFERENCES (id) "
                    "ON public.capital_source TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (marker), UPDATE (marker), REFERENCES (id) "
                    "ON public.consent_data_type TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (marker), UPDATE (marker), REFERENCES (id) "
                    "ON public.process_benchmark TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (location_id), UPDATE (farm_count), "
                    "REFERENCES (location_id) ON public.v_public_farm_summary "
                    "TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT SELECT (id, event_type, module_path, function_name, is_enabled, "
                    "priority_order, timeout_seconds) ON public.event_handler "
                    "TO kokonut_event_dispatch_owner"
                )
                cursor.execute(
                    "GRANT SELECT, INSERT, UPDATE, DELETE "
                    "ON public.water_access, public.attestation_plan "
                    "TO kokonut_directus_runtime"
                )
                cursor.execute(
                    "GRANT ALL PRIVILEGES "
                    "ON public.hive_record, public.pollinator_hive_inspection "
                    "TO kokonut_directus_runtime, PUBLIC"
                )
                cursor.execute(
                    "GRANT INSERT (marker), UPDATE (marker), REFERENCES (id) "
                    "ON public.hive_record, public.pollinator_hive_inspection "
                    "TO kokonut_runtime, kokonut_directus_runtime, PUBLIC"
                )
                cursor.execute(
                    "GRANT ALL PRIVILEGES ON public.pollinator_observation, "
                    "public.pollinator_habitat, public.pesticide_impact_log "
                    "TO kokonut_directus_runtime, PUBLIC"
                )
                cursor.execute(
                    "GRANT INSERT (marker), UPDATE (marker), REFERENCES (id) "
                    "ON public.pollinator_observation, public.pollinator_habitat, "
                    "public.pesticide_impact_log "
                    "TO kokonut_runtime, kokonut_directus_runtime, PUBLIC"
                )
                for table, owner_role in (
                    ("pollinator_observation", "kokonut_pollinator_observation_writer"),
                    ("pollinator_habitat", "kokonut_pollinator_habitat_writer"),
                    ("pesticide_impact_log", "kokonut_pesticide_impact_writer"),
                ):
                    cursor.execute(
                        sql.SQL("GRANT INSERT (marker) ON public.{} TO {}").format(
                            sql.Identifier(table), sql.Identifier(owner_role)
                        )
                    )
                cursor.execute(
                    "SELECT "
                    "has_table_privilege('kokonut_runtime', 'public.pollinator_observation', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.pollinator_habitat', 'INSERT'), "
                    "has_table_privilege('kokonut_unrelated_probe', 'public.pesticide_impact_log', 'INSERT'), "
                    "has_column_privilege('kokonut_runtime', 'public.pollinator_observation', 'marker', 'INSERT'), "
                    "has_column_privilege('kokonut_directus_runtime', 'public.pollinator_habitat', 'marker', 'UPDATE'), "
                    "has_column_privilege('kokonut_unrelated_probe', 'public.pesticide_impact_log', 'id', 'REFERENCES')"
                )
                if cursor.fetchone() != (True,) * 6:
                    raise AssertionError(
                        "disposable pollinator fixture failed to create stale write grants"
                    )
                cursor.execute(
                    "SELECT "
                    "has_column_privilege('kokonut_runtime', 'public.hive_record', 'marker', 'INSERT'), "
                    "has_column_privilege('kokonut_runtime', 'public.hive_record', 'marker', 'UPDATE'), "
                    "has_column_privilege('kokonut_runtime', 'public.hive_record', 'id', 'REFERENCES'), "
                    "has_column_privilege('kokonut_directus_runtime', 'public.hive_record', 'marker', 'INSERT'), "
                    "has_column_privilege('kokonut_directus_runtime', 'public.hive_record', 'marker', 'UPDATE'), "
                    "has_column_privilege('kokonut_directus_runtime', 'public.hive_record', 'id', 'REFERENCES'), "
                    "has_column_privilege('kokonut_unrelated_probe', 'public.hive_record', 'marker', 'INSERT'), "
                    "has_column_privilege('kokonut_unrelated_probe', 'public.hive_record', 'marker', 'UPDATE'), "
                    "has_column_privilege('kokonut_unrelated_probe', 'public.hive_record', 'id', 'REFERENCES')"
                )
                if cursor.fetchone() != (True,) * 9:
                    raise AssertionError(
                        "disposable fixture failed to create the expected stale column grants"
                    )
                cursor.execute(
                    "GRANT INSERT (marker) ON public.hive_record "
                    "TO kokonut_pollinator_hive_writer"
                )
                cursor.execute(
                    "GRANT UPDATE (marker) ON public.hive_record "
                    "TO kokonut_pollinator_inspection_writer, "
                    "kokonut_pollinator_hive_lifecycle_writer"
                )
                cursor.execute(
                    "GRANT INSERT (marker) ON public.pollinator_hive_inspection "
                    "TO kokonut_pollinator_inspection_writer"
                )
                cursor.execute(
                    "GRANT UPDATE (marker) ON public.pollinator_hive_inspection "
                    "TO kokonut_pollinator_review_writer"
                )
                for table in (
                    "process_maturity_level", "pollinator_species_reference",
                    "gri_indicator", "governance_framework",
                    "impact_framework", "impact_dimension",
                    "expense_category", "crisp_risk_dimension",
                    "dfs_currency",
                    "crop_gdd_config",
                    "pest_degree_day_config",
                    "revenue_multiplier_config",
                    "reference_class",
                    "farmer_credential_type",
                    "market_reference_data",
                    "quantity_unit",
                    "yield_benchmark",
                    "metric_definition",
                    "service_registry",
                ):
                    cursor.execute(
                        sql.SQL(
                            "GRANT SELECT, INSERT, UPDATE, DELETE ON public.{} "
                            "TO kokonut_directus_runtime"
                        ).format(sql.Identifier(table))
                    )
                cursor.execute(
                    "GRANT SELECT (marker), INSERT (id, marker), UPDATE (marker), REFERENCES (id) "
                    "ON public.data_access_log TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT SELECT (marker), INSERT (id, marker), UPDATE (marker), REFERENCES (id) "
                    "ON public.access_audit_log TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                    "ON public.advisory_rule TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                    "ON public.crop_family TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                    "ON public.crop_nutrient_removal_factor TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                    "ON public.certification_type TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (id, marker), UPDATE (marker), REFERENCES (id) "
                    "ON public.consent_data_type TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                    "ON public.capex_breakdown TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                    "ON public.evidence_maturity_level TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                    "ON public.sensor_type TO kokonut_runtime"
                )
                for table in ("waste_type", "disposal_method"):
                    cursor.execute(
                        sql.SQL(
                            "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                            "ON public.{} TO kokonut_runtime"
                        ).format(sql.Identifier(table))
                    )
                migration = APPEND_ONLY_MIGRATION.read_text(encoding="utf-8")
                cursor.execute(migration)
                cursor.execute(migration)
                advisory_migration = ADVISORY_RULE_MIGRATION.read_text(encoding="utf-8")
                cursor.execute(advisory_migration)
                cursor.execute(advisory_migration)
                crop_family_migration = CROP_FAMILY_MIGRATION.read_text(encoding="utf-8")
                cursor.execute(crop_family_migration)
                cursor.execute(crop_family_migration)
                crop_nutrient_factor_migration = (
                    CROP_NUTRIENT_FACTOR_MIGRATION.read_text(encoding="utf-8")
                )
                cursor.execute(crop_nutrient_factor_migration)
                cursor.execute(crop_nutrient_factor_migration)
                certification_type_migration = CERTIFICATION_TYPE_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(certification_type_migration)
                cursor.execute(certification_type_migration)
                cursor.execute(REFERENCE_CATALOGS_MIGRATION.read_text(encoding="utf-8"))
                cursor.execute(REFERENCE_CATALOGS_MIGRATION.read_text(encoding="utf-8"))
                cursor.execute(EVIDENCE_MATURITY_MIGRATION.read_text(encoding="utf-8"))
                cursor.execute(EVIDENCE_MATURITY_MIGRATION.read_text(encoding="utf-8"))
                cursor.execute(SENSOR_TYPE_MIGRATION.read_text(encoding="utf-8"))
                cursor.execute(SENSOR_TYPE_MIGRATION.read_text(encoding="utf-8"))
                waste_reference_migration = WASTE_REFERENCE_MIGRATION.read_text(encoding="utf-8")
                cursor.execute(waste_reference_migration)
                cursor.execute(waste_reference_migration)
                graph_projection_types_migration = (
                    GRAPH_PROJECTION_TYPES_MIGRATION.read_text(encoding="utf-8")
                )
                cursor.execute(graph_projection_types_migration)
                cursor.execute(graph_projection_types_migration)
                access_audit_log_migration = ACCESS_AUDIT_LOG_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(access_audit_log_migration)
                cursor.execute(access_audit_log_migration)
                agent_action_log_migration = AGENT_ACTION_LOG_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(agent_action_log_migration)
                cursor.execute(agent_action_log_migration)
                carbon_benchmark_migration = CARBON_BENCHMARK_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(carbon_benchmark_migration)
                cursor.execute(carbon_benchmark_migration)
                ghg_emission_factor_migration = GHG_EMISSION_FACTOR_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(ghg_emission_factor_migration)
                cursor.execute(ghg_emission_factor_migration)
                operations_protocol_migration = OPERATIONS_PROTOCOL_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(operations_protocol_migration)
                cursor.execute(operations_protocol_migration)
                static_reference_catalogs_migration = (
                    STATIC_REFERENCE_CATALOGS_MIGRATION.read_text(encoding="utf-8")
                )
                cursor.execute(static_reference_catalogs_migration)
                cursor.execute(static_reference_catalogs_migration)
                reporting_registry_migration = REPORTING_REGISTRY_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(reporting_registry_migration)
                cursor.execute(reporting_registry_migration)
                impact_framework_catalogs_migration = (
                    IMPACT_FRAMEWORK_CATALOGS_MIGRATION.read_text(encoding="utf-8")
                )
                cursor.execute(impact_framework_catalogs_migration)
                cursor.execute(impact_framework_catalogs_migration)
                expense_category_migration = EXPENSE_CATEGORY_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(expense_category_migration)
                cursor.execute(expense_category_migration)
                crisp_risk_dimension_migration = CRISP_RISK_DIMENSION_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(crisp_risk_dimension_migration)
                cursor.execute(crisp_risk_dimension_migration)
                dfs_currency_migration = DFS_CURRENCY_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(dfs_currency_migration)
                cursor.execute(dfs_currency_migration)
                crop_gdd_config_migration = CROP_GDD_CONFIG_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(crop_gdd_config_migration)
                cursor.execute(crop_gdd_config_migration)
                pest_degree_day_config_migration = PEST_DEGREE_DAY_CONFIG_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(pest_degree_day_config_migration)
                cursor.execute(pest_degree_day_config_migration)
                revenue_multiplier_config_migration = (
                    REVENUE_MULTIPLIER_CONFIG_MIGRATION.read_text(encoding="utf-8")
                )
                cursor.execute(revenue_multiplier_config_migration)
                cursor.execute(revenue_multiplier_config_migration)
                reference_class_migration = REFERENCE_CLASS_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(reference_class_migration)
                cursor.execute(reference_class_migration)
                farmer_credential_type_migration = FARMER_CREDENTIAL_TYPE_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(farmer_credential_type_migration)
                cursor.execute(farmer_credential_type_migration)
                market_reference_data_migration = MARKET_REFERENCE_DATA_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(market_reference_data_migration)
                cursor.execute(market_reference_data_migration)
                quantity_unit_migration = QUANTITY_UNIT_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(quantity_unit_migration)
                cursor.execute(quantity_unit_migration)
                yield_benchmark_migration = YIELD_BENCHMARK_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(yield_benchmark_migration)
                cursor.execute(yield_benchmark_migration)
                metric_definition_migration = METRIC_DEFINITION_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(metric_definition_migration)
                cursor.execute(metric_definition_migration)
                service_registry_migration = SERVICE_REGISTRY_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(service_registry_migration)
                cursor.execute(service_registry_migration)
                capex_breakdown_migration = CAPEX_BREAKDOWN_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(capex_breakdown_migration)
                cursor.execute(capex_breakdown_migration)
                water_access_attestation_plan_migration = (
                    WATER_ACCESS_ATTESTATION_PLAN_MIGRATION.read_text(
                        encoding="utf-8"
                    )
                )
                cursor.execute(water_access_attestation_plan_migration)
                cursor.execute(water_access_attestation_plan_migration)
                pollinator_hive_migration = POLLINATOR_HIVE_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(pollinator_hive_migration)
                cursor.execute(pollinator_hive_migration)
                pollinator_capture_migration = POLLINATOR_CAPTURE_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(pollinator_capture_migration)
                cursor.execute(pollinator_capture_migration)
                event_handler_migration = EVENT_HANDLER_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(event_handler_migration)
                cursor.execute(event_handler_migration)
                capital_source_migration = CAPITAL_SOURCE_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(capital_source_migration)
                cursor.execute(capital_source_migration)
                consent_data_type_migration = CONSENT_DATA_TYPE_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(consent_data_type_migration)
                cursor.execute(consent_data_type_migration)
                process_benchmark_migration = PROCESS_BENCHMARK_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(process_benchmark_migration)
                cursor.execute(process_benchmark_migration)
                public_farm_summary_migration = PUBLIC_FARM_SUMMARY_MIGRATION.read_text(
                    encoding="utf-8"
                )
                cursor.execute(public_farm_summary_migration)
                cursor.execute(public_farm_summary_migration)

            with connection.cursor() as cursor:
                runtime_role._verify_runtime_append_only_boundary(
                    cursor, "kokonut_runtime"
                )
            if _relation_privileges(connection, "data_access_log") != (
                True, True, False, False
            ):
                raise AssertionError("migration 652 did not establish read/insert-only rights")
            if _relation_privileges(connection, "access_audit_log") != (
                True, True, False, False
            ):
                raise AssertionError("migration 662 did not establish read/insert-only rights")
            if _relation_privileges(connection, "agent_action_log") != (
                True, False, False, False
            ):
                raise AssertionError("migration 663 did not establish read-only rights")
            if _relation_privileges(connection, "capex_breakdown") != (
                True, False, False, False
            ):
                raise AssertionError("migration 690 did not establish read-only CAPEX rights")
            if _relation_privileges(connection, "event_handler") != (
                True, False, False, False
            ):
                raise AssertionError("migration 694 did not establish read-only event registry rights")
            if _relation_privileges(connection, "capital_source") != (
                True, False, False, False
            ):
                raise AssertionError("migration 695 did not establish read-only capital-source rights")
            if _relation_privileges(connection, "consent_data_type") != (
                True, False, False, False
            ):
                raise AssertionError("migration 696 did not establish read-only consent-category rights")
            if _relation_privileges(connection, "process_benchmark") != (
                True, False, False, False
            ):
                raise AssertionError("migration 697 did not establish read-only process-benchmark rights")
            if _relation_privileges(connection, "v_public_farm_summary") != (
                True, False, False, False
            ):
                raise AssertionError("migration 699 did not establish read-only public-summary rights")
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_relation_is_updatable('public.v_public_farm_summary'::regclass, TRUE), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.v_public_farm_summary', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.v_public_farm_summary', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.v_public_farm_summary', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.v_public_farm_summary', 'DELETE'), "
                    "has_column_privilege('kokonut_runtime', 'public.v_public_farm_summary', 'location_id', 'INSERT'), "
                    "has_column_privilege('kokonut_runtime', 'public.v_public_farm_summary', 'farm_count', 'UPDATE'), "
                    "has_column_privilege('kokonut_runtime', 'public.v_public_farm_summary', 'location_id', 'REFERENCES')"
                )
                if cursor.fetchone() != (0, True, True, True, True, False, False, False):
                    raise AssertionError(
                        "migration 699 changed Directus grants, left column grants, "
                        "or accepted an updatable view"
                    )
                cursor.execute("SET ROLE kokonut_runtime")
                cursor.execute(
                    "SELECT location_id, farm_count FROM public.v_public_farm_summary"
                )
                if len(cursor.fetchall()) != 1:
                    raise AssertionError("runtime could not read the public farm summary")
                for statement in (
                    "INSERT INTO public.v_public_farm_summary (location_id, farm_count) "
                    "VALUES ('00000000-0000-0000-0000-000000000001', 1)",
                    "UPDATE public.v_public_farm_summary SET farm_count = 9",
                    "DELETE FROM public.v_public_farm_summary",
                ):
                    try:
                        cursor.execute(statement)
                    except psycopg2.Error as exc:
                        if exc.pgcode not in {"42501", "55000"}:
                            raise AssertionError(
                                f"expected runtime ACL denial or non-updatable view; got {exc.pgcode}"
                            ) from exc
                        connection.rollback()
                        with connection.cursor() as retry_cursor:
                            retry_cursor.execute("SET ROLE kokonut_runtime")
                    else:
                        connection.rollback()
                        raise AssertionError("runtime mutated the public farm summary view")
                cursor.execute("RESET ROLE")

                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', 'public.consent_data_type', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.consent_data_type', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.consent_data_type', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.consent_data_type', 'DELETE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.consent_data_type', 'TRUNCATE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.consent_data_type', 'REFERENCES'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.consent_data_type', 'TRIGGER'), "
                    "has_column_privilege('kokonut_runtime', 'public.consent_data_type', 'marker', 'INSERT'), "
                    "has_column_privilege('kokonut_runtime', 'public.consent_data_type', 'marker', 'UPDATE'), "
                    "has_column_privilege('kokonut_runtime', 'public.consent_data_type', 'id', 'REFERENCES')"
                )
                if cursor.fetchone() != (
                    True, True, True, True, True, True, True, False, False, False
                ):
                    raise AssertionError(
                        "migration 696 changed Directus grants or left runtime column grants"
                    )
                cursor.execute("SET ROLE kokonut_runtime")
                cursor.execute(
                    "SELECT name, default_retention_days "
                    "FROM public.consent_data_type"
                )
                if cursor.fetchone() != ("synthetic_category", None):
                    raise AssertionError(
                        "runtime could not read the consent category or its unset retention default"
                    )
                cursor.execute("RESET ROLE")
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', 'public.capital_source', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.capital_source', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.capital_source', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.capital_source', 'DELETE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.capital_source', 'TRUNCATE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.capital_source', 'REFERENCES'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.capital_source', 'TRIGGER'), "
                    "has_column_privilege('kokonut_runtime', 'public.capital_source', 'marker', 'INSERT'), "
                    "has_column_privilege('kokonut_runtime', 'public.capital_source', 'marker', 'UPDATE'), "
                    "has_column_privilege('kokonut_runtime', 'public.capital_source', 'id', 'REFERENCES')"
                )
                if cursor.fetchone() != (
                    True, True, True, True, True, True, True, False, False, False
                ):
                    raise AssertionError(
                        "migration 695 changed Directus grants or left runtime column grants"
                    )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', 'public.process_benchmark', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.process_benchmark', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.process_benchmark', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.process_benchmark', 'DELETE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.process_benchmark', 'TRUNCATE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.process_benchmark', 'REFERENCES'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.process_benchmark', 'TRIGGER'), "
                    "has_column_privilege('kokonut_runtime', 'public.process_benchmark', 'marker', 'INSERT'), "
                    "has_column_privilege('kokonut_runtime', 'public.process_benchmark', 'marker', 'UPDATE'), "
                    "has_column_privilege('kokonut_runtime', 'public.process_benchmark', 'id', 'REFERENCES')"
                )
                if cursor.fetchone() != (
                    True, True, True, True, True, True, True, False, False, False
                ):
                    raise AssertionError(
                        "migration 697 changed Directus grants or left runtime column grants"
                    )
                cursor.execute("SET ROLE kokonut_runtime")
                cursor.execute("SELECT marker FROM public.process_benchmark")
                if cursor.fetchone() != ("synthetic-process-benchmark",):
                    raise AssertionError("runtime role could not read process benchmarks")
                cursor.execute("RESET ROLE")
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', 'public.event_handler', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.event_handler', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.event_handler', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.event_handler', 'DELETE'), "
                    "has_column_privilege('kokonut_event_dispatch_owner', 'public.event_handler', 'event_type', 'SELECT'), "
                    "has_column_privilege('kokonut_event_dispatch_owner', 'public.event_handler', 'module_path', 'SELECT'), "
                    "has_column_privilege('kokonut_event_dispatch_owner', 'public.event_handler', 'event_type', 'UPDATE'), "
                    "EXISTS (SELECT 1 FROM pg_class AS relation "
                    "CROSS JOIN LATERAL aclexplode(COALESCE(relation.relacl, "
                    "acldefault('r', relation.relowner))) AS privilege "
                    "WHERE relation.oid = 'public.event_handler'::regclass "
                    "AND privilege.grantee = 0 AND privilege.privilege_type IN "
                    "('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'))"
                )
                if cursor.fetchone() != (True, True, True, True, True, True, False, False):
                    raise AssertionError(
                        "migration 694 changed Directus/dispatch-owner grants or left PUBLIC writes"
                    )
                cursor.execute("SET ROLE kokonut_runtime")
                cursor.execute("SELECT handler_name FROM public.event_handler")
                if cursor.fetchone() != ("synthetic-handler",):
                    raise AssertionError("runtime role could not read event-handler configuration")
                cursor.execute("RESET ROLE")
                cursor.execute("SET ROLE kokonut_runtime")
                for statement in (
                    "INSERT INTO public.consent_data_type "
                    "(id, name, category, marker) VALUES "
                    "('00000000-0000-0000-0000-000000000096', 'forbidden', 'test', 'forbidden')",
                    "UPDATE public.consent_data_type SET marker = 'forbidden'",
                    "DELETE FROM public.consent_data_type",
                    "TRUNCATE public.consent_data_type",
                ):
                    try:
                        cursor.execute(statement)
                    except psycopg2.Error as exc:
                        if exc.pgcode != "42501":
                            raise AssertionError(
                                f"expected privilege denial for {statement}; got {exc.pgcode}"
                            ) from exc
                        connection.rollback()
                        with connection.cursor() as retry_cursor:
                            retry_cursor.execute("SET ROLE kokonut_runtime")
                    else:
                        connection.rollback()
                        raise AssertionError(
                            "runtime consent-category write unexpectedly succeeded"
                        )
                cursor.execute("RESET ROLE")
                cursor.execute("SET ROLE kokonut_event_dispatch_owner")
                cursor.execute(
                    "SELECT event_type, module_path FROM public.event_handler"
                )
                if cursor.fetchone() != ("synthetic.event", "tests.handlers"):
                    raise AssertionError("event-dispatch owner lost its bounded registry read")
                cursor.execute("RESET ROLE")
                cursor.execute("SET ROLE kokonut_runtime")
                cursor.execute("SELECT marker FROM public.capital_source")
                for statement in (
                    "INSERT INTO public.capital_source (id, marker) "
                    "VALUES ('00000000-0000-0000-0000-000000000095', 'forbidden')",
                    "UPDATE public.capital_source SET marker = 'forbidden'",
                    "DELETE FROM public.capital_source",
                    "TRUNCATE public.capital_source",
                ):
                    try:
                        cursor.execute(statement)
                    except psycopg2.Error as exc:
                        if exc.pgcode != "42501":
                            raise AssertionError(
                                f"expected privilege denial for {statement}; got {exc.pgcode}"
                            ) from exc
                        connection.rollback()
                        with connection.cursor() as retry_cursor:
                            retry_cursor.execute("SET ROLE kokonut_runtime")
                    else:
                        connection.rollback()
                        raise AssertionError(
                            "runtime capital-source write unexpectedly succeeded"
                        )
                for statement in (
                    "INSERT INTO public.process_benchmark (id, marker) "
                    "VALUES ('00000000-0000-0000-0000-000000000097', 'forbidden')",
                    "UPDATE public.process_benchmark SET marker = 'forbidden'",
                    "DELETE FROM public.process_benchmark",
                    "TRUNCATE public.process_benchmark",
                ):
                    try:
                        cursor.execute(statement)
                    except psycopg2.Error as exc:
                        if exc.pgcode != "42501":
                            raise AssertionError(
                                f"expected privilege denial for {statement}; got {exc.pgcode}"
                            ) from exc
                        connection.rollback()
                        with connection.cursor() as retry_cursor:
                            retry_cursor.execute("SET ROLE kokonut_runtime")
                    else:
                        connection.rollback()
                        raise AssertionError(
                            "runtime process-benchmark write unexpectedly succeeded"
                        )
                cursor.execute("RESET ROLE")
            for table in ("water_access", "attestation_plan"):
                if _relation_privileges(connection, table) != (
                    True, False, False, False
                ):
                    raise AssertionError(
                        f"migration 691 did not establish read-only rights for {table}"
                    )
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT has_table_privilege('kokonut_directus_runtime', %s, 'SELECT'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'INSERT'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'UPDATE'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'DELETE')",
                        (f"public.{table}",) * 4,
                    )
                    if cursor.fetchone() != (True, True, True, True):
                        raise AssertionError(
                            f"migration 691 changed separate Directus SQL role on {table}"
                        )
            for table in ("hive_record", "pollinator_hive_inspection"):
                if _relation_privileges(connection, table) != (
                    True, False, False, False
                ):
                    raise AssertionError(
                        f"migration 692 did not establish read-only runtime rights for {table}"
                    )
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT has_table_privilege('kokonut_directus_runtime', %s, 'SELECT'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'INSERT'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'UPDATE'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'DELETE'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'TRUNCATE'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'REFERENCES'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'TRIGGER'), "
                        "has_table_privilege('kokonut_unrelated_probe', %s, 'INSERT'), "
                        "has_table_privilege('kokonut_unrelated_probe', %s, 'UPDATE'), "
                        "has_table_privilege('kokonut_unrelated_probe', %s, 'DELETE'), "
                        "has_column_privilege('kokonut_runtime', %s, 'marker', 'INSERT'), "
                        "has_column_privilege('kokonut_runtime', %s, 'marker', 'UPDATE'), "
                        "has_column_privilege('kokonut_runtime', %s, 'id', 'REFERENCES'), "
                        "has_column_privilege('kokonut_directus_runtime', %s, 'marker', 'INSERT'), "
                        "has_column_privilege('kokonut_directus_runtime', %s, 'marker', 'UPDATE'), "
                        "has_column_privilege('kokonut_directus_runtime', %s, 'id', 'REFERENCES'), "
                        "has_column_privilege('kokonut_unrelated_probe', %s, 'marker', 'INSERT'), "
                        "has_column_privilege('kokonut_unrelated_probe', %s, 'marker', 'UPDATE'), "
                        "has_column_privilege('kokonut_unrelated_probe', %s, 'id', 'REFERENCES')",
                        (f"public.{table}",) * 19,
                    )
                    if cursor.fetchone() != (
                        True, False, False, False, False, False, False,
                        False, False, False, False, False, False,
                        False, False, False,
                        False, False, False,
                    ):
                        raise AssertionError(
                            f"migration 692 did not clear table and stale column grants while preserving reads on {table}"
                        )

                for role_name in (
                    "kokonut_runtime",
                    "kokonut_directus_runtime",
                    "kokonut_unrelated_probe",
                ):
                    with connection.cursor() as cursor:
                        cursor.execute(
                            sql.SQL("SET ROLE {}").format(sql.Identifier(role_name))
                        )
                        cursor.execute(
                            sql.SQL("SELECT marker FROM public.{}").format(
                                sql.Identifier(table)
                            )
                        )
                        statements = (
                            (
                                sql.SQL(
                                    "INSERT INTO public.{} (id, marker) VALUES (%s, %s)"
                                ).format(sql.Identifier(table)),
                                (str(uuid.uuid4()), "forbidden"),
                            ),
                            (
                                sql.SQL("UPDATE public.{} SET marker = %s").format(
                                    sql.Identifier(table)
                                ),
                                ("forbidden",),
                            ),
                            (
                                sql.SQL("DELETE FROM public.{}").format(
                                    sql.Identifier(table)
                                ),
                                None,
                            ),
                            (
                                sql.SQL("TRUNCATE public.{}").format(
                                    sql.Identifier(table)
                                ),
                                None,
                            ),
                        )
                        for statement, parameters in statements:
                            try:
                                cursor.execute(statement, parameters)
                            except psycopg2.Error as exc:
                                if exc.pgcode != "42501":
                                    raise AssertionError(
                                        f"expected write denial for {role_name} on {table}; got {exc.pgcode}"
                                    ) from exc
                                connection.rollback()
                                with connection.cursor() as retry_cursor:
                                    retry_cursor.execute(
                                        sql.SQL("SET ROLE {}").format(
                                            sql.Identifier(role_name)
                                        )
                                    )
                            else:
                                connection.rollback()
                                raise AssertionError(
                                    f"{role_name} unexpectedly wrote {table}"
                                )
                        cursor.execute("RESET ROLE")
            for table in (
                "pollinator_observation",
                "pollinator_habitat",
                "pesticide_impact_log",
            ):
                if _relation_privileges(connection, table) != (
                    True, False, False, False
                ):
                    raise AssertionError(
                        f"migration 693 did not establish read-only runtime rights for {table}"
                    )
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT has_table_privilege('kokonut_directus_runtime', %s, 'SELECT'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'INSERT'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'UPDATE'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'DELETE'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'TRUNCATE'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'REFERENCES'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'TRIGGER'), "
                        "has_table_privilege('kokonut_unrelated_probe', %s, 'SELECT'), "
                        "has_table_privilege('kokonut_unrelated_probe', %s, 'INSERT'), "
                        "has_table_privilege('kokonut_unrelated_probe', %s, 'UPDATE'), "
                        "has_table_privilege('kokonut_unrelated_probe', %s, 'DELETE'), "
                        "has_column_privilege('kokonut_runtime', %s, 'marker', 'INSERT'), "
                        "has_column_privilege('kokonut_runtime', %s, 'marker', 'UPDATE'), "
                        "has_column_privilege('kokonut_runtime', %s, 'id', 'REFERENCES'), "
                        "has_column_privilege('kokonut_directus_runtime', %s, 'marker', 'INSERT'), "
                        "has_column_privilege('kokonut_directus_runtime', %s, 'marker', 'UPDATE'), "
                        "has_column_privilege('kokonut_directus_runtime', %s, 'id', 'REFERENCES'), "
                        "has_column_privilege('kokonut_unrelated_probe', %s, 'marker', 'INSERT'), "
                        "has_column_privilege('kokonut_unrelated_probe', %s, 'marker', 'UPDATE'), "
                        "has_column_privilege('kokonut_unrelated_probe', %s, 'id', 'REFERENCES')",
                        (f"public.{table}",) * 20,
                    )
                    if cursor.fetchone() != (
                        True, False, False, False, False, False, False,
                        True, False, False, False,
                        False, False, False, False, False, False,
                        False, False, False,
                    ):
                        raise AssertionError(
                            f"migration 693 failed to revoke runtime, Directus, PUBLIC, or stale column writes on {table}"
                        )

                for role_name in (
                    "kokonut_runtime",
                    "kokonut_directus_runtime",
                    "kokonut_unrelated_probe",
                ):
                    with connection.cursor() as cursor:
                        cursor.execute(
                            sql.SQL("SET ROLE {}").format(sql.Identifier(role_name))
                        )
                        cursor.execute(
                            sql.SQL("SELECT marker FROM public.{}").format(
                                sql.Identifier(table)
                            )
                        )
                        statements = (
                            (
                                sql.SQL(
                                    "INSERT INTO public.{} (id, marker) VALUES (%s, %s)"
                                ).format(sql.Identifier(table)),
                                (str(uuid.uuid4()), "forbidden"),
                            ),
                            (
                                sql.SQL("UPDATE public.{} SET marker = %s").format(
                                    sql.Identifier(table)
                                ),
                                ("forbidden",),
                            ),
                            (sql.SQL("DELETE FROM public.{}").format(sql.Identifier(table)), None),
                            (sql.SQL("TRUNCATE public.{}").format(sql.Identifier(table)), None),
                        )
                        for statement, parameters in statements:
                            try:
                                cursor.execute(statement, parameters)
                            except psycopg2.Error as exc:
                                if exc.pgcode != "42501":
                                    raise AssertionError(
                                        f"expected migration 693 privilege denial for {role_name}/{table}; got {exc.pgcode}"
                                    ) from exc
                                connection.rollback()
                                with connection.cursor() as retry_cursor:
                                    retry_cursor.execute(
                                        sql.SQL("SET ROLE {}").format(
                                            sql.Identifier(role_name)
                                        )
                                    )
                            else:
                                connection.rollback()
                                raise AssertionError(
                                    f"migration 693 allowed {role_name} write on {table}: {statement}"
                                )
                        cursor.execute("RESET ROLE")
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_runtime', "
                    "'public.agent_action_log', 'TRUNCATE'), "
                    "has_table_privilege('kokonut_runtime', "
                    "'public.agent_action_log', 'REFERENCES'), "
                    "EXISTS (SELECT 1 FROM pg_attribute "
                    "WHERE attrelid = 'public.agent_action_log'::regclass "
                    "AND attnum > 0 AND NOT attisdropped AND ("
                    "has_column_privilege('kokonut_runtime', 'public.agent_action_log', attname, 'INSERT') "
                    "OR has_column_privilege('kokonut_runtime', 'public.agent_action_log', attname, 'UPDATE') "
                    "OR has_column_privilege('kokonut_runtime', 'public.agent_action_log', attname, 'REFERENCES')))"
                )
                if cursor.fetchone() != (False, False, False):
                    raise AssertionError(
                        "migration 663 retained truncate/reference/column write grants"
                    )
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', "
                    "'public.agent_action_log', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.agent_action_log', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.agent_action_log', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.agent_action_log', 'DELETE')"
                )
                if cursor.fetchone() != (True, True, True, True):
                    raise AssertionError(
                        "migration 663 unexpectedly changed the separate Directus role"
                    )
            if _relation_privileges(connection, "advisory_rule") != (
                True, False, False, False
            ):
                raise AssertionError("migration 653 did not establish read-only rights")
            if _relation_privileges(connection, "crop_family") != (
                True, False, False, False
            ):
                raise AssertionError("migration 654 did not establish read-only rights")
            if _relation_privileges(connection, "crop_nutrient_removal_factor") != (
                True, False, False, False
            ):
                raise AssertionError("migration 655 did not establish read-only rights")
            if _relation_privileges(connection, "certification_type") != (
                True, False, False, False
            ):
                raise AssertionError("migration 656 did not establish read-only rights")
            for table in REFERENCE_CATALOGS:
                if _relation_privileges(connection, table) != (
                    True, False, False, False
                ):
                    migration_number = {
                        "cooperative_type": 657,
                        "dfs_insurance_product_type": 657,
                        "evidence_maturity_level": 658,
                        "sensor_type": 659,
                        "waste_type": 660,
                        "disposal_method": 660,
                        "graph_node_type": 661,
                        "graph_edge_type": 661,
                        "carbon_benchmark": 664,
                        "ghg_emission_factor": 665,
                        "operations_protocol": 666,
                        "process_maturity_level": 667,
                        "pollinator_species_reference": 667,
                        "gri_indicator": 668,
                        "governance_framework": 668,
                        "impact_framework": 669,
                        "impact_dimension": 669,
                        "expense_category": 670,
                        "crisp_risk_dimension": 671,
                        "dfs_currency": 672,
                        "crop_gdd_config": 673,
                        "pest_degree_day_config": 674,
                        "revenue_multiplier_config": 675,
                        "reference_class": 676,
                        "farmer_credential_type": 677,
                        "market_reference_data": 678,
                        "quantity_unit": 679,
                        "yield_benchmark": 680,
                        "metric_definition": 681,
                        "service_registry": 682,
                    }[table]
                    raise AssertionError(
                        f"migration {migration_number} did not establish read-only rights on {table}"
                    )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', "
                    "'public.service_registry', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.service_registry', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.service_registry', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.service_registry', 'DELETE')"
                )
                if cursor.fetchone() != (True, True, True, True):
                    raise AssertionError(
                        "migration 682 unexpectedly changed the separate Directus role"
                    )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', "
                    "'public.carbon_benchmark', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.carbon_benchmark', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.carbon_benchmark', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.carbon_benchmark', 'DELETE')"
                )
                if cursor.fetchone() != (True, True, True, True):
                    raise AssertionError(
                        "migration 664 unexpectedly changed the separate Directus role"
                    )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', "
                    "'public.ghg_emission_factor', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.ghg_emission_factor', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.ghg_emission_factor', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.ghg_emission_factor', 'DELETE')"
                )
                if cursor.fetchone() != (True, True, True, True):
                    raise AssertionError(
                        "migration 665 unexpectedly changed the separate Directus role"
                    )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', "
                    "'public.operations_protocol', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.operations_protocol', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.operations_protocol', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.operations_protocol', 'DELETE')"
                )
                if cursor.fetchone() != (True, True, True, True):
                    raise AssertionError(
                        "migration 666 unexpectedly changed the separate Directus role"
                    )
            with connection.cursor() as cursor:
                for table in (
                    "process_maturity_level", "pollinator_species_reference",
                    "gri_indicator", "governance_framework",
                    "impact_framework", "impact_dimension",
                    "expense_category", "crisp_risk_dimension", "reference_class",
                    "farmer_credential_type", "market_reference_data",
                    "yield_benchmark",
                ):
                    cursor.execute(
                        "SELECT has_table_privilege('kokonut_directus_runtime', %s, 'SELECT'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'INSERT'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'UPDATE'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'DELETE')",
                        (f"public.{table}",) * 4,
                    )
                    if cursor.fetchone() != (True, True, True, True):
                        raise AssertionError(
                            f"static catalog migration unexpectedly changed Directus grants on {table}"
                        )
            with connection.cursor() as cursor:
                for table, migration_number in (
                    ("advisory_rule", 653),
                    ("crop_family", 654),
                    ("crop_nutrient_removal_factor", 655),
                    ("certification_type", 656),
                    ("cooperative_type", 657),
                    ("dfs_insurance_product_type", 657),
                    ("evidence_maturity_level", 658),
                    ("sensor_type", 659),
                    ("waste_type", 660),
                    ("disposal_method", 660),
                    ("graph_node_type", 661),
                    ("graph_edge_type", 661),
                    ("carbon_benchmark", 664),
                    ("ghg_emission_factor", 665),
                    ("operations_protocol", 666),
                    ("process_maturity_level", 667),
                    ("pollinator_species_reference", 667),
                    ("gri_indicator", 668),
                    ("governance_framework", 668),
                    ("impact_framework", 669),
                    ("impact_dimension", 669),
                    ("expense_category", 670),
                    ("crisp_risk_dimension", 671),
                    ("dfs_currency", 672),
                    ("crop_gdd_config", 673),
                    ("pest_degree_day_config", 674),
                    ("revenue_multiplier_config", 675),
                    ("reference_class", 676),
                    ("farmer_credential_type", 677),
                    ("market_reference_data", 678),
                    ("quantity_unit", 679),
                    ("yield_benchmark", 680),
                    ("metric_definition", 681),
                    ("capex_breakdown", 690),
                    ("water_access", 691),
                    ("attestation_plan", 691),
                    ("hive_record", 692),
                    ("pollinator_hive_inspection", 692),
                    ("pollinator_observation", 693),
                    ("pollinator_habitat", 693),
                    ("pesticide_impact_log", 693),
                ):
                    cursor.execute(
                        "SELECT has_table_privilege('kokonut_runtime', %s, 'REFERENCES'), "
                        "has_table_privilege('kokonut_runtime', %s, 'TRUNCATE'), "
                        "has_table_privilege('kokonut_runtime', %s, 'TRIGGER')",
                        (f"public.{table}",) * 3,
                    )
                    if any(cursor.fetchone()):
                        raise AssertionError(
                            f"migration {migration_number} retained REFERENCES/TRUNCATE/TRIGGER privilege"
                        )
                    cursor.execute(
                        "SELECT EXISTS (SELECT 1 FROM pg_attribute "
                        "WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped AND ("
                        "has_column_privilege('kokonut_runtime', %s, attname, 'INSERT') "
                        "OR has_column_privilege('kokonut_runtime', %s, attname, 'UPDATE') "
                        "OR has_column_privilege('kokonut_runtime', %s, attname, 'REFERENCES'))) ",
                        (f"public.{table}",) * 4,
                    )
                    if cursor.fetchone()[0]:
                        raise AssertionError(
                            f"migration {migration_number} retained column-level write/reference grants"
                        )

            # Reproduce the normal provisioner order: its compatibility grant
            # follows migrations, so the scoped policy must be reapplied.
            with connection.cursor() as cursor:
                cursor.execute(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
                    "IN SCHEMA public TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT SELECT (marker), INSERT (id, marker), UPDATE (marker), REFERENCES (id) "
                    "ON public.data_access_log TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT SELECT (marker), INSERT (id, marker), UPDATE (marker), REFERENCES (id) "
                    "ON public.access_audit_log TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                    "ON public.advisory_rule TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                    "ON public.crop_family TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                    "ON public.crop_nutrient_removal_factor TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                    "ON public.certification_type TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                    "ON public.evidence_maturity_level TO kokonut_runtime"
                )
                for table in REFERENCE_CATALOGS:
                    cursor.execute(
                        sql.SQL(
                            "GRANT INSERT (id), UPDATE (marker), REFERENCES (id) "
                            "ON public.{} TO kokonut_runtime"
                        ).format(sql.Identifier(table))
                    )
                applied = runtime_role._apply_runtime_append_only_boundary(
                    cursor, sql.Identifier("kokonut_runtime")
                )
                scoped_applied = runtime_role._apply_scoped_write_boundary(
                    cursor, sql.Identifier("kokonut_runtime")
                )
                runtime_role._verify_runtime_append_only_boundary(
                    cursor, "kokonut_runtime"
                )
                runtime_role._verify_scoped_write_boundary(cursor, "kokonut_runtime")
            if applied["relations"] != {
                "data_access_log": True,
                "access_audit_log": True,
            }:
                raise AssertionError("runtime provisioner did not reapply append-only audit policies")
            if _relation_privileges(connection, "data_access_log") != (
                True, True, False, False
            ):
                raise AssertionError("runtime provisioner left broad audit-table rights")
            if _relation_privileges(connection, "access_audit_log") != (
                True, True, False, False
            ):
                raise AssertionError("runtime provisioner reopened capability-audit writes")
            if _relation_privileges(connection, "agent_action_log") != (
                True, False, False, False
            ):
                raise AssertionError("runtime provisioner reopened agent-action-log writes")
            if scoped_applied["relations"].get("agent_action_log") is not True:
                raise AssertionError("runtime provisioner skipped agent-action-log boundary")
            if _relation_privileges(connection, "event_handler") != (
                True, False, False, False
            ):
                raise AssertionError("runtime provisioner reopened event-handler registry writes")
            if scoped_applied["relations"].get("event_handler") is not True:
                raise AssertionError("runtime provisioner skipped event-handler registry boundary")
            if _relation_privileges(connection, "capital_source") != (
                True, False, False, False
            ):
                raise AssertionError("runtime provisioner reopened capital-source writes")
            if scoped_applied["relations"].get("capital_source") is not True:
                raise AssertionError("runtime provisioner skipped capital-source mutation denial")
            if _relation_privileges(connection, "consent_data_type") != (
                True, False, False, False
            ):
                raise AssertionError(
                    "runtime provisioner reopened consent-category writes"
                )
            if scoped_applied["relations"].get("consent_data_type") is not True:
                raise AssertionError(
                    "runtime provisioner skipped consent-category mutation denial"
                )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', 'public.consent_data_type', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.consent_data_type', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.consent_data_type', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.consent_data_type', 'DELETE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.consent_data_type', 'TRUNCATE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.consent_data_type', 'REFERENCES'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.consent_data_type', 'TRIGGER')"
                )
                if cursor.fetchone() != (True, True, True, True, True, True, True):
                    raise AssertionError(
                        "runtime provisioner changed the separate Directus SQL role"
                    )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', 'public.capital_source', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.capital_source', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.capital_source', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.capital_source', 'DELETE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.capital_source', 'TRUNCATE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.capital_source', 'REFERENCES'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.capital_source', 'TRIGGER')"
                )
                if cursor.fetchone() != (True, True, True, True, True, True, True):
                    raise AssertionError(
                        "runtime provisioner changed the separate Directus SQL role"
                    )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', 'public.event_handler', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.event_handler', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.event_handler', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', 'public.event_handler', 'DELETE'), "
                    "has_column_privilege('kokonut_event_dispatch_owner', 'public.event_handler', 'event_type', 'SELECT'), "
                    "has_column_privilege('kokonut_event_dispatch_owner', 'public.event_handler', 'event_type', 'UPDATE')"
                )
                if cursor.fetchone() != (True, True, True, True, True, False):
                    raise AssertionError(
                        "runtime provisioner changed Directus or event-dispatch owner rights"
                    )
            if _relation_privileges(connection, "capex_breakdown") != (
                True, False, False, False
            ):
                raise AssertionError("runtime provisioner reopened CAPEX breakdown writes")
            if scoped_applied["relations"].get("capex_breakdown") is not True:
                raise AssertionError("runtime provisioner skipped CAPEX breakdown boundary")
            for table in ("water_access", "attestation_plan"):
                if _relation_privileges(connection, table) != (
                    True, False, False, False
                ):
                    raise AssertionError(
                        f"runtime provisioner reopened {table} writes"
                    )
                if scoped_applied["relations"].get(table) is not True:
                    raise AssertionError(
                        f"runtime provisioner skipped {table} mutation denial"
                    )
            for table in ("hive_record", "pollinator_hive_inspection"):
                if _relation_privileges(connection, table) != (
                    True, False, False, False
                ):
                    raise AssertionError(
                        f"runtime provisioner reopened {table} writes"
                    )
                if scoped_applied["relations"].get(table) is not True:
                    raise AssertionError(
                        f"runtime provisioner skipped {table} mutation denial"
                    )
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT has_table_privilege('kokonut_directus_runtime', %s, 'SELECT'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'INSERT'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'UPDATE'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'DELETE'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'TRUNCATE'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'REFERENCES'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'TRIGGER'), "
                        "has_column_privilege('kokonut_runtime', %s, 'marker', 'INSERT'), "
                        "has_column_privilege('kokonut_runtime', %s, 'marker', 'UPDATE'), "
                        "has_column_privilege('kokonut_runtime', %s, 'id', 'REFERENCES'), "
                        "has_column_privilege('kokonut_directus_runtime', %s, 'marker', 'INSERT'), "
                        "has_column_privilege('kokonut_directus_runtime', %s, 'marker', 'UPDATE'), "
                        "has_column_privilege('kokonut_directus_runtime', %s, 'id', 'REFERENCES')",
                        (f"public.{table}",) * 13,
                    )
                    if cursor.fetchone() != (
                        True, False, False, False, False, False, False,
                        False, False, False,
                        False, False, False,
                    ):
                        raise AssertionError(
                            f"migration 692 or provisioner left a direct write grant on {table}"
                        )
            for table in (
                "pollinator_observation",
                "pollinator_habitat",
                "pesticide_impact_log",
            ):
                if _relation_privileges(connection, table) != (
                    True, False, False, False
                ):
                    raise AssertionError(
                        f"runtime provisioner reopened {table} writes"
                    )
                if scoped_applied["relations"].get(table) is not True:
                    raise AssertionError(
                        f"runtime provisioner skipped {table} mutation denial"
                    )
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT has_table_privilege('kokonut_directus_runtime', %s, 'SELECT'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'INSERT'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'UPDATE'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'DELETE'), "
                        "has_column_privilege('kokonut_runtime', %s, 'marker', 'INSERT'), "
                        "has_column_privilege('kokonut_runtime', %s, 'marker', 'UPDATE'), "
                        "has_column_privilege('kokonut_directus_runtime', %s, 'marker', 'INSERT'), "
                        "has_column_privilege('kokonut_directus_runtime', %s, 'marker', 'UPDATE'), "
                        "has_table_privilege('kokonut_unrelated_probe', %s, 'INSERT')",
                        (f"public.{table}",) * 9,
                    )
                    actual_capture_privileges = cursor.fetchone()
                    if actual_capture_privileges != (
                        True, False, False, False, False, False, False, False, False
                    ):
                        raise AssertionError(
                            f"migration 693 or provisioner left DML grants on {table}: "
                            f"{actual_capture_privileges}"
                        )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_column_privilege('kokonut_pollinator_hive_writer', "
                    "'public.hive_record', 'marker', 'INSERT'), "
                    "has_column_privilege('kokonut_pollinator_inspection_writer', "
                    "'public.hive_record', 'marker', 'UPDATE'), "
                    "has_column_privilege('kokonut_pollinator_hive_lifecycle_writer', "
                    "'public.hive_record', 'marker', 'UPDATE'), "
                    "has_column_privilege('kokonut_pollinator_inspection_writer', "
                    "'public.pollinator_hive_inspection', 'marker', 'INSERT'), "
                    "has_column_privilege('kokonut_pollinator_review_writer', "
                    "'public.pollinator_hive_inspection', 'marker', 'UPDATE')"
                )
                if cursor.fetchone() != (True, True, True, True, True):
                    raise AssertionError(
                        "migration 692 changed bounded pollinator function-owner grants"
                    )
                cursor.execute(
                    "SELECT has_column_privilege('kokonut_pollinator_observation_writer', "
                    "'public.pollinator_observation', 'marker', 'INSERT'), "
                    "has_column_privilege('kokonut_pollinator_habitat_writer', "
                    "'public.pollinator_habitat', 'marker', 'INSERT'), "
                    "has_column_privilege('kokonut_pesticide_impact_writer', "
                    "'public.pesticide_impact_log', 'marker', 'INSERT')"
                )
                if cursor.fetchone() != (True, True, True):
                    raise AssertionError(
                        "migration 693 changed dedicated pollinator capture-owner grants"
                    )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', "
                    "'public.agent_action_log', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.agent_action_log', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.agent_action_log', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.agent_action_log', 'DELETE')"
                )
                if cursor.fetchone() != (True, True, True, True):
                    raise AssertionError(
                        "runtime provisioner changed the separate Directus role"
                    )
            if _relation_privileges(connection, "advisory_rule") != (
                True, False, False, False
            ):
                raise AssertionError("runtime provisioner reopened advisory-rule writes")
            if scoped_applied["relations"].get("advisory_rule") is not True:
                raise AssertionError("runtime provisioner skipped advisory-rule boundary")
            if _relation_privileges(connection, "crop_family") != (
                True, False, False, False
            ):
                raise AssertionError("runtime provisioner reopened crop-family writes")
            if scoped_applied["relations"].get("crop_family") is not True:
                raise AssertionError("runtime provisioner skipped crop-family boundary")
            if _relation_privileges(connection, "crop_nutrient_removal_factor") != (
                True, False, False, False
            ):
                raise AssertionError("runtime provisioner reopened nutrient-factor writes")
            if scoped_applied["relations"].get("crop_nutrient_removal_factor") is not True:
                raise AssertionError("runtime provisioner skipped nutrient-factor boundary")
            if _relation_privileges(connection, "certification_type") != (
                True, False, False, False
            ):
                raise AssertionError("runtime provisioner reopened certification-type writes")
            if scoped_applied["relations"].get("certification_type") is not True:
                raise AssertionError("runtime provisioner skipped certification-type boundary")
            for table in REFERENCE_CATALOGS:
                if _relation_privileges(connection, table) != (
                    True, False, False, False
                ):
                    raise AssertionError(
                        f"runtime provisioner reopened writes on {table}"
                    )
                if scoped_applied["relations"].get(table) is not True:
                    raise AssertionError(
                        f"runtime provisioner skipped the {table} boundary"
                    )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', "
                    "'public.carbon_benchmark', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.carbon_benchmark', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.carbon_benchmark', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.carbon_benchmark', 'DELETE')"
                )
                if cursor.fetchone() != (True, True, True, True):
                    raise AssertionError(
                        "migration 664 or runtime provisioner changed the Directus role"
                    )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', "
                    "'public.ghg_emission_factor', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.ghg_emission_factor', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.ghg_emission_factor', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.ghg_emission_factor', 'DELETE')"
                )
                if cursor.fetchone() != (True, True, True, True):
                    raise AssertionError(
                        "migration 665 or runtime provisioner changed the Directus role"
                    )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege('kokonut_directus_runtime', "
                    "'public.operations_protocol', 'SELECT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.operations_protocol', 'INSERT'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.operations_protocol', 'UPDATE'), "
                    "has_table_privilege('kokonut_directus_runtime', "
                    "'public.operations_protocol', 'DELETE')"
                )
                if cursor.fetchone() != (True, True, True, True):
                    raise AssertionError(
                        "migration 666 or runtime provisioner changed the Directus role"
                    )
            with connection.cursor() as cursor:
                for table in (
                    "process_maturity_level", "pollinator_species_reference",
                    "reference_class", "farmer_credential_type",
                    "market_reference_data",
                    "quantity_unit", "yield_benchmark", "metric_definition",
                    "service_registry",
                ):
                    cursor.execute(
                        "SELECT has_table_privilege('kokonut_directus_runtime', %s, 'SELECT'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'INSERT'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'UPDATE'), "
                        "has_table_privilege('kokonut_directus_runtime', %s, 'DELETE')",
                        (f"public.{table}",) * 4,
                    )
                    if cursor.fetchone() != (True, True, True, True):
                        raise AssertionError(
                            f"migration 667 or runtime provisioner changed Directus grants on {table}"
                        )

            with connection.cursor() as cursor:
                cursor.execute("SET ROLE kokonut_runtime")
                cursor.execute("SELECT marker FROM public.advisory_rule")
                for statement in (
                    "INSERT INTO public.advisory_rule (id, marker) "
                    "VALUES ('00000000-0000-0000-0000-000000000001', 'forbidden')",
                    "UPDATE public.advisory_rule SET marker = 'forbidden'",
                    "DELETE FROM public.advisory_rule",
                ):
                    try:
                        cursor.execute(statement)
                    except psycopg2.Error as exc:
                        if exc.pgcode != "42501":
                            raise AssertionError(
                                f"expected privilege denial for {statement}; got {exc.pgcode}"
                            ) from exc
                        connection.rollback()
                        with connection.cursor() as retry_cursor:
                            retry_cursor.execute("SET ROLE kokonut_runtime")
                    else:
                        connection.rollback()
                        raise AssertionError(f"runtime advisory-rule write unexpectedly succeeded: {statement}")
                cursor.execute("RESET ROLE")

            with connection.cursor() as cursor:
                cursor.execute("SET ROLE kokonut_runtime")
                cursor.execute("SELECT marker FROM public.agent_action_log")
                for statement in (
                    "INSERT INTO public.agent_action_log (id, marker) "
                    "VALUES ('00000000-0000-0000-0000-000000000005', 'forbidden')",
                    "UPDATE public.agent_action_log SET marker = 'forbidden'",
                    "DELETE FROM public.agent_action_log",
                    "TRUNCATE public.agent_action_log",
                ):
                    try:
                        cursor.execute(statement)
                    except psycopg2.Error as exc:
                        if exc.pgcode != "42501":
                            raise AssertionError(
                                f"expected privilege denial for {statement}; got {exc.pgcode}"
                            ) from exc
                        connection.rollback()
                        with connection.cursor() as retry_cursor:
                            retry_cursor.execute("SET ROLE kokonut_runtime")
                    else:
                        connection.rollback()
                        raise AssertionError(
                            f"runtime agent-action-log write unexpectedly succeeded: {statement}"
                        )
                cursor.execute("RESET ROLE")

            with connection.cursor() as cursor:
                cursor.execute("SET ROLE kokonut_runtime")
                for table in REFERENCE_CATALOGS:
                    identifier = sql.Identifier(table)
                    cursor.execute(
                        sql.SQL("SELECT marker FROM public.{}").format(identifier)
                    )
                    rows = cursor.fetchall()
                    if table == "yield_benchmark" and rows != [
                        ("synthetic-yield-benchmark",)
                    ]:
                        raise AssertionError(
                            "runtime SELECT did not return the synthetic yield benchmark"
                        )
                    if table == "metric_definition" and rows != [
                        ("synthetic-metric-definition",)
                    ]:
                        raise AssertionError(
                            "runtime SELECT did not return the synthetic metric definition"
                        )
                    statements = (
                        (
                            sql.SQL(
                                "INSERT INTO public.{} (id, marker) VALUES (%s, %s)"
                            ).format(identifier),
                            (str(uuid.uuid4()), "forbidden"),
                        ),
                        (sql.SQL("UPDATE public.{} SET marker = 'forbidden'").format(identifier), None),
                        (sql.SQL("DELETE FROM public.{}").format(identifier), None),
                        (sql.SQL("TRUNCATE public.{}").format(identifier), None),
                    )
                    for statement, parameters in statements:
                        try:
                            if parameters is None:
                                cursor.execute(statement)
                            else:
                                cursor.execute(statement, parameters)
                        except psycopg2.Error as exc:
                            if exc.pgcode != "42501":
                                raise AssertionError(
                                    f"expected privilege denial for {table}; got {exc.pgcode}"
                                ) from exc
                            connection.rollback()
                            with connection.cursor() as retry_cursor:
                                retry_cursor.execute("SET ROLE kokonut_runtime")
                        else:
                            connection.rollback()
                            raise AssertionError(
                                f"runtime write unexpectedly succeeded on {table}"
                            )
                cursor.execute("RESET ROLE")

            # Catalog rows stay immutable while the dependent capability map
            # remains writable through its existing operation.
            with connection.cursor() as cursor:
                cursor.execute("SET ROLE kokonut_runtime")
                cursor.execute(
                    "INSERT INTO public.capability_service_map "
                    "(capability_id, service_name, is_primary) VALUES (%s, 'gateway', true)",
                    (capability_id,),
                )
                cursor.execute(
                    "SELECT sr.marker FROM public.capability_service_map csm "
                    "JOIN public.service_registry sr ON sr.name = csm.service_name "
                    "WHERE csm.capability_id = %s",
                    (capability_id,),
                )
                if cursor.fetchone() != ("synthetic-service-registry",):
                    raise AssertionError(
                        "runtime could not create/read a capability-service mapping"
                    )
                cursor.execute("RESET ROLE")

            with connection.cursor() as cursor:
                cursor.execute("SET ROLE kokonut_runtime")
                cursor.execute("SELECT marker FROM public.certification_type")
                for statement in (
                    "INSERT INTO public.certification_type (id, marker) "
                    "VALUES ('00000000-0000-0000-0000-000000000004', 'forbidden')",
                    "UPDATE public.certification_type SET marker = 'forbidden'",
                    "DELETE FROM public.certification_type",
                    "TRUNCATE public.certification_type",
                ):
                    try:
                        cursor.execute(statement)
                    except psycopg2.Error as exc:
                        if exc.pgcode != "42501":
                            raise AssertionError(
                                f"expected privilege denial for {statement}; got {exc.pgcode}"
                            ) from exc
                        connection.rollback()
                        with connection.cursor() as retry_cursor:
                            retry_cursor.execute("SET ROLE kokonut_runtime")
                    else:
                        connection.rollback()
                        raise AssertionError(
                            f"runtime certification-type write unexpectedly succeeded: {statement}"
                        )
                cursor.execute("RESET ROLE")

            with connection.cursor() as cursor:
                cursor.execute("SET ROLE kokonut_runtime")
                cursor.execute("SELECT marker FROM public.capex_breakdown")
                for statement in (
                    "INSERT INTO public.capex_breakdown (id, marker) "
                    "VALUES ('00000000-0000-0000-0000-000000000006', 'forbidden')",
                    "UPDATE public.capex_breakdown SET marker = 'forbidden'",
                    "DELETE FROM public.capex_breakdown",
                    "TRUNCATE public.capex_breakdown",
                ):
                    try:
                        cursor.execute(statement)
                    except psycopg2.Error as exc:
                        if exc.pgcode != "42501":
                            raise AssertionError(
                                f"expected privilege denial for {statement}; got {exc.pgcode}"
                            ) from exc
                        connection.rollback()
                        with connection.cursor() as retry_cursor:
                            retry_cursor.execute("SET ROLE kokonut_runtime")
                    else:
                        connection.rollback()
                        raise AssertionError(
                            "runtime CAPEX breakdown write unexpectedly succeeded"
                        )
                cursor.execute("RESET ROLE")

            with connection.cursor() as cursor:
                cursor.execute("SET ROLE kokonut_runtime")
                for table in ("water_access", "attestation_plan"):
                    cursor.execute(
                        sql.SQL("SELECT marker FROM public.{}").format(
                            sql.Identifier(table)
                        )
                    )
                    for statement, parameters in (
                        (
                            sql.SQL(
                            "INSERT INTO public.{} (id, marker) "
                            "VALUES (%s, 'forbidden')"
                            ).format(sql.Identifier(table)),
                            (str(uuid.uuid4()),),
                        ),
                        (
                            sql.SQL(
                            "UPDATE public.{} SET marker = 'forbidden'"
                            ).format(sql.Identifier(table)),
                            None,
                        ),
                        (
                            sql.SQL("DELETE FROM public.{}").format(
                                sql.Identifier(table)
                            ),
                            None,
                        ),
                        (
                            sql.SQL("TRUNCATE public.{}").format(
                                sql.Identifier(table)
                            ),
                            None,
                        ),
                    ):
                        try:
                            cursor.execute(statement, parameters)
                        except psycopg2.Error as exc:
                            if exc.pgcode != "42501":
                                raise AssertionError(
                                    f"expected privilege denial for {table}; got {exc.pgcode}"
                                ) from exc
                            connection.rollback()
                            with connection.cursor() as retry_cursor:
                                retry_cursor.execute("SET ROLE kokonut_runtime")
                        else:
                            connection.rollback()
                            raise AssertionError(
                                f"runtime {table} write unexpectedly succeeded"
                            )
                cursor.execute("RESET ROLE")

            with connection.cursor() as cursor:
                cursor.execute("SET ROLE kokonut_runtime")
                cursor.execute("SELECT marker FROM public.crop_family")
                for statement in (
                    "INSERT INTO public.crop_family (id, marker) "
                    "VALUES ('00000000-0000-0000-0000-000000000002', 'forbidden')",
                    "UPDATE public.crop_family SET marker = 'forbidden'",
                    "DELETE FROM public.crop_family",
                    "TRUNCATE public.crop_family",
                ):
                    try:
                        cursor.execute(statement)
                    except psycopg2.Error as exc:
                        if exc.pgcode != "42501":
                            raise AssertionError(
                                f"expected privilege denial for {statement}; got {exc.pgcode}"
                            ) from exc
                        connection.rollback()
                        with connection.cursor() as retry_cursor:
                            retry_cursor.execute("SET ROLE kokonut_runtime")
                    else:
                        connection.rollback()
                        raise AssertionError(f"runtime crop-family write unexpectedly succeeded: {statement}")
                cursor.execute("RESET ROLE")

            with connection.cursor() as cursor:
                cursor.execute("SET ROLE kokonut_runtime")
                cursor.execute(
                    "SELECT marker FROM public.crop_nutrient_removal_factor"
                )
                for statement in (
                    "INSERT INTO public.crop_nutrient_removal_factor (id, marker) "
                    "VALUES ('00000000-0000-0000-0000-000000000003', 'forbidden')",
                    "UPDATE public.crop_nutrient_removal_factor SET marker = 'forbidden'",
                    "DELETE FROM public.crop_nutrient_removal_factor",
                    "TRUNCATE public.crop_nutrient_removal_factor",
                ):
                    try:
                        cursor.execute(statement)
                    except psycopg2.Error as exc:
                        if exc.pgcode != "42501":
                            raise AssertionError(
                                f"expected privilege denial for {statement}; got {exc.pgcode}"
                            ) from exc
                        connection.rollback()
                        with connection.cursor() as retry_cursor:
                            retry_cursor.execute("SET ROLE kokonut_runtime")
                    else:
                        connection.rollback()
                        raise AssertionError(
                            f"runtime nutrient-factor write unexpectedly succeeded: {statement}"
                        )
                cursor.execute("RESET ROLE")

            with connection.cursor() as cursor:
                cursor.execute("SET ROLE kokonut_runtime")
                row_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO public.data_access_log (id, marker) VALUES (%s, %s)",
                    (row_id, "synthetic-append-only-check"),
                )
                cursor.execute(
                    "SELECT marker FROM public.data_access_log WHERE id = %s",
                    (row_id,),
                )
                if cursor.fetchone() != ("synthetic-append-only-check",):
                    raise AssertionError("runtime role could not read its appended audit row")
                for statement in (
                    "UPDATE public.data_access_log SET marker = 'changed'",
                    "DELETE FROM public.data_access_log",
                    "TRUNCATE public.data_access_log",
                ):
                    try:
                        cursor.execute(statement)
                    except psycopg2.Error as exc:
                        if exc.pgcode != "42501":
                            raise AssertionError(
                                f"expected privilege denial for {statement}; got {exc.pgcode}"
                            ) from exc
                        connection.rollback()
                        with connection.cursor() as retry_cursor:
                            retry_cursor.execute("SET ROLE kokonut_runtime")
                    else:
                        connection.rollback()
                        raise AssertionError(f"runtime mutation unexpectedly succeeded: {statement}")
                cursor.execute("RESET ROLE")

            with connection.cursor() as cursor:
                cursor.execute("SET ROLE kokonut_runtime")
                row_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO public.access_audit_log (id, marker) VALUES (%s, %s)",
                    (row_id, "synthetic-capability-audit-check"),
                )
                cursor.execute(
                    "SELECT marker FROM public.access_audit_log WHERE id = %s",
                    (row_id,),
                )
                if cursor.fetchone() != ("synthetic-capability-audit-check",):
                    raise AssertionError("runtime role could not read its appended capability audit row")
                for statement in (
                    "UPDATE public.access_audit_log SET marker = 'changed'",
                    "DELETE FROM public.access_audit_log",
                    "TRUNCATE public.access_audit_log",
                ):
                    try:
                        cursor.execute(statement)
                    except psycopg2.Error as exc:
                        if exc.pgcode != "42501":
                            raise AssertionError(
                                f"expected privilege denial for {statement}; got {exc.pgcode}"
                            ) from exc
                        connection.rollback()
                        with connection.cursor() as retry_cursor:
                            retry_cursor.execute("SET ROLE kokonut_runtime")
                    else:
                        connection.rollback()
                        raise AssertionError(
                            f"capability audit mutation unexpectedly succeeded: {statement}"
                        )
                cursor.execute("RESET ROLE")

            with connection.cursor() as cursor:
                cursor.execute(
                    "GRANT SELECT, INSERT, UPDATE, DELETE "
                    "ON public.v_public_farm_summary TO kokonut_runtime"
                )
                cursor.execute(
                    "GRANT INSERT (location_id), UPDATE (farm_count), "
                    "REFERENCES (location_id) ON public.v_public_farm_summary "
                    "TO kokonut_runtime"
                )
                result = runtime_role._apply_scoped_write_boundary(
                    cursor, sql.Identifier("kokonut_runtime")
                )
            if set(result["relations"]) != set(relations) or not all(
                result["relations"].values()
            ):
                raise AssertionError("the provisioner did not visit every ACL relation")
            with connection.cursor() as cursor:
                runtime_role._verify_scoped_write_boundary(cursor, "kokonut_runtime")
                cursor.execute(
                    "SELECT has_column_privilege('kokonut_runtime', "
                    "'public.v_public_farm_summary', 'location_id', 'INSERT'), "
                    "has_column_privilege('kokonut_runtime', "
                    "'public.v_public_farm_summary', 'farm_count', 'UPDATE'), "
                    "has_column_privilege('kokonut_runtime', "
                    "'public.v_public_farm_summary', 'location_id', 'REFERENCES')"
                )
                if cursor.fetchone() != (False, False, False):
                    raise AssertionError(
                        "runtime-role provisioner left column-level public-view grants"
                    )

            private_denied = 0
            for table in runtime_role._RUNTIME_PRIVATE_TABLES:
                if _relation_privileges(connection, table) != (False, False, False, False):
                    raise AssertionError(f"private runtime access remains on {table}")
                private_denied += 1

            mutation_denied = 0
            for table in runtime_role._RUNTIME_MUTATION_TABLES:
                select, insert, update, delete = _relation_privileges(connection, table)
                if (select, insert, update, delete) != (True, False, False, False):
                    raise AssertionError(f"mutation boundary is wrong on {table}")
                mutation_denied += 1

            with connection.cursor() as cursor:
                cursor.execute("GRANT SELECT (marker) ON public.ai_summary_review_decision TO kokonut_runtime")
            try:
                with connection.cursor() as cursor:
                    runtime_role._verify_scoped_write_boundary(cursor, "kokonut_runtime")
            except RuntimeError as exc:
                if "column privileges" not in str(exc):
                    raise
            else:
                raise AssertionError("the verifier missed a residual private column grant")

            return {
                "result": "passed",
                "engine": "PostgreSQL 16",
                "database_image": {
                    "name": image,
                    "platform": image_info[0],
                    "image_id": image_info[1],
                },
                "requested_platform": platform or "docker-default",
                "database_scope": (
                    "temporary PostgreSQL container on Docker network none, with the test "
                    "client sharing its isolated namespace; no external network or host port; "
                    "empty database and synthetic relation definitions"
                    if dsn is not None
                    else "temporary container, empty database, synthetic relation definitions"
                ),
                "tables_exercised": len(relations) + 2,
                "private_tables_without_runtime_access": private_denied,
                "mutation_only_tables_select_only": mutation_denied,
                "append_only_data_access_log": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_and_insert_allowed": True,
                    "update_delete_truncate_denied": True,
                    "stale_column_grants_removed": True,
                },
                "append_only_access_audit_log": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_and_insert_allowed": True,
                    "update_delete_truncate_denied": True,
                    "stale_column_grants_removed": True,
                },
                "read_only_advisory_rule": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_denied": True,
                    "references_and_column_grants_denied": True,
                },
                "read_only_agent_action_log": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_write_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_crop_family": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                },
                "read_only_crop_nutrient_removal_factor": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                },
                "read_only_certification_type": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                },
                "read_only_cooperative_type": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                },
                "read_only_dfs_insurance_product_type": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                },
                "read_only_evidence_maturity_level": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                },
                "read_only_sensor_type": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                },
                "read_only_waste_type": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                },
                "read_only_disposal_method": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                },
                "read_only_graph_node_type": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                },
                "read_only_graph_edge_type": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                },
                "read_only_carbon_benchmark": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_ghg_emission_factor": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_operations_protocol": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_process_maturity_level": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_pollinator_species_reference": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_gri_indicator": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_governance_framework": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_impact_framework": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_impact_dimension": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_expense_category": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_crisp_risk_dimension": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_dfs_currency": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_crop_gdd_config": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_pest_degree_day_config": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_revenue_multiplier_config": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_reference_class": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_farmer_credential_type": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_market_reference_data": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_quantity_unit": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                },
                "read_only_yield_benchmark": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "synthetic_row_read": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_triggers_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                    "tenant_isolation_established": False,
                },
                "read_only_metric_definition": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_triggers_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                    "tenant_isolation_established": False,
                },
                "read_only_service_registry": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_triggers_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                    "capability_service_mapping_remains_writable": True,
                    "tenant_isolation_established": False,
                },
                "read_only_capex_breakdown": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "tenant_isolation_established": False,
                },
                "read_only_water_access": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                    "tenant_isolation_established": False,
                },
                "read_only_attestation_plan": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "insert_update_delete_truncate_denied": True,
                    "references_and_column_grants_denied": True,
                    "directus_role_unchanged": True,
                    "tenant_isolation_established": False,
                },
                "read_only_pollinator_hive_records": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "select_allowed": True,
                    "runtime_directus_and_public_dml_denied": True,
                    "references_truncate_and_column_grants_denied": True,
                    "bounded_function_owner_column_grants_preserved": True,
                    "tenant_isolation_established": False,
                },
                "read_only_pollinator_capture_tables": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "runtime_select_only": True,
                    "directus_select_preserved_and_dml_denied": True,
                    "public_inherited_select_preserved_and_dml_denied": True,
                    "stale_table_and_column_grants_removed": True,
                    "runtime_directus_public_writes_denied": True,
                    "dedicated_capture_owner_grants_preserved": True,
                },
                "read_only_event_handler": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "runtime_select_only": True,
                    "directus_dml_unchanged": True,
                    "event_dispatch_owner_select_columns_preserved": True,
                    "public_write_grants_absent": True,
                    "tenant_isolation_established": False,
                },
                "read_only_capital_source": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "runtime_select_only": True,
                    "directus_sql_role_unchanged": True,
                    "insert_update_delete_truncate_denied": True,
                    "column_reference_grants_denied": True,
                    "tenant_isolation_established": False,
                },
                "read_only_consent_data_type": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "runtime_select_only": True,
                    "directus_sql_role_unchanged": True,
                    "insert_update_delete_truncate_denied": True,
                    "column_reference_grants_denied": True,
                    "dynamic_retention_policy_untouched": True,
                    "tenant_isolation_established": False,
                },
                "read_only_process_benchmark": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "runtime_select_only": True,
                    "directus_sql_role_unchanged": True,
                    "insert_update_delete_truncate_denied": True,
                    "column_reference_grants_denied": True,
                    "tenant_isolation_established": False,
                },
                "read_only_public_farm_summary": {
                    "migration_applied_and_replayed": True,
                    "provisioner_reapplied_after_compatibility_grants": True,
                    "view_remains_non_updatable": True,
                    "runtime_select_only": True,
                    "runtime_dml_and_column_grants_denied": True,
                    "directus_view_grants_unchanged": True,
                    "tenant_isolation_established": False,
                },
                "column_level_privilege_regression_detected": True,
                "bounded_gateway_function_behavior": "not exercised; source migrations are not installed",
            }
        finally:
            connection.close()
    finally:
        if created:
            run(["docker", "rm", "--force", container])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("linux/amd64", "linux/arm64"))
    parser.add_argument(
        "--connect-env",
        action="store_true",
        help=(
            "connect to KOKONUT_RUNTIME_ACL_TEST_DSN instead of creating a local "
            "container (for a client sharing a network-disabled PostgreSQL namespace)"
        ),
    )
    parser.add_argument(
        "--image",
        help=(
            "PostgreSQL image override (default: pinned postgis/postgis on AMD64; "
            "local kokonut-kernel-postgis-arm64:local image on ARM64)"
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    image = args.image or (
        ARM64_POSTGRES_IMAGE if args.platform == "linux/arm64" else POSTGRES_IMAGE
    )
    dsn = os.environ.get("KOKONUT_RUNTIME_ACL_TEST_DSN") if args.connect_env else None
    if args.connect_env and not dsn:
        parser.error("--connect-env requires KOKONUT_RUNTIME_ACL_TEST_DSN")
    database_image_id = (
        os.environ.get("KOKONUT_RUNTIME_ACL_TEST_IMAGE_ID")
        if args.connect_env
        else None
    )
    evidence = check_boundary(
        image=image,
        platform=args.platform,
        dsn=dsn,
        database_image_id=database_image_id,
    )
    evidence["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(args.output)
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
