"""Inventory Metabase source metadata without exposing connection values."""

from __future__ import annotations

import ipaddress
import json
import os
from collections import Counter

import psycopg2
from psycopg2 import sql


def host_category(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return "unset"
    host = value.strip().lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return "localhost"
    if host in {"database", "clickhouse", "host.docker.internal"}:
        return "local_or_container_name"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "dns_name"
    return "private_ip" if address.is_private else "public_ip"


def database_category(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return "unset"
    name = value.strip().lower()
    if name == "kokonut_intelligence":
        return "application_database"
    if name == "kokonut_analytics":
        return "analytics_database"
    return "other_database"


def table_count(cur, table_name: str) -> int | None:
    cur.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
    if cur.fetchone()[0] is None:
        return None
    cur.execute(sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table_name)))
    return int(cur.fetchone()[0])


def main() -> int:
    password = os.environ.get("KOKONUT_DB_ADMIN_PASSWORD", "")
    if not password:
        raise SystemExit("isolated database admin credential is required")
    conn = psycopg2.connect(
        host=os.environ.get("PG_HOST", "database"),
        port=int(os.environ.get("PG_PORT", "5432")),
        dbname=os.environ.get("PG_DB", "metabase"),
        user=os.environ.get("KOKONUT_DB_ADMIN_USER", "kokonut"),
        password=password,
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT engine, details, is_sample, is_stub FROM public.metabase_database ORDER BY id")
            sources = cur.fetchall()
            engines: Counter[str] = Counter()
            hosts: Counter[str] = Counter()
            database_names: Counter[str] = Counter()
            source_flags: Counter[tuple[str, bool, bool]] = Counter()
            detail_keys: set[str] = set()
            credential_configs = 0
            for engine, details, is_sample, is_stub in sources:
                if isinstance(details, str):
                    details = json.loads(details)
                if not isinstance(details, dict):
                    details = {}
                engine_name = str(engine or "unknown")
                engines[engine_name] += 1
                source_flags[(engine_name, bool(is_sample), bool(is_stub))] += 1
                detail_keys.update(str(key) for key in details)
                hosts[host_category(details.get("host"))] += 1
                database_names[database_category(details.get("dbname"))] += 1
                if details.get("password"):
                    credential_configs += 1
            cur.execute(
                """SELECT COALESCE(db.engine, 'unassigned'),
                          COALESCE(card.query_type, 'unknown'), count(*)
                   FROM public.report_card AS card
                   LEFT JOIN public.metabase_database AS db ON db.id = card.database_id
                   GROUP BY 1, 2 ORDER BY 1, 2"""
            )
            card_categories = [
                {"source_engine": engine, "query_type": query_type, "count": int(count)}
                for engine, query_type, count in cur.fetchall()
            ]
            cur.execute(
                """SELECT COALESCE(db.engine, 'unassigned'), count(*)
                   FROM public.report_dashboardcard AS dashboard_card
                   JOIN public.report_card AS card ON card.id = dashboard_card.card_id
                   LEFT JOIN public.metabase_database AS db ON db.id = card.database_id
                   GROUP BY 1 ORDER BY 1"""
            )
            dashboard_card_sources = [
                {"source_engine": engine, "count": int(count)}
                for engine, count in cur.fetchall()
            ]
            counts = {
                "saved_cards": table_count(cur, "report_card"),
                "dashboards": table_count(cur, "report_dashboard"),
                "users": table_count(cur, "core_user"),
            }
        print(
            json.dumps(
                {
                    "result": "passed",
                    "scope": "read-only metadata inventory from isolated restored Metabase database",
                    "source_count": len(sources),
                    "source_engines": dict(sorted(engines.items())),
                    "source_detail_keys": sorted(detail_keys),
                    "host_categories": dict(sorted(hosts.items())),
                    "database_categories": dict(sorted(database_names.items())),
                    "registered_source_flags": [
                        {
                            "engine": engine,
                            "is_sample": is_sample,
                            "is_stub": is_stub,
                            "count": count,
                        }
                        for (engine, is_sample, is_stub), count in sorted(source_flags.items())
                    ],
                    "source_entries_with_password_field": credential_configs,
                    "saved_content_counts": counts,
                    "saved_card_source_query_categories": card_categories,
                    "dashboard_card_source_categories": dashboard_card_sources,
                    "connection_details_examined_in_memory": True,
                    "connection_values_printed": False,
                    "saved_query_sql_read": False,
                    "saved_content_definitions_read": False,
                    "saved_content_and_source_categories_only": True,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
