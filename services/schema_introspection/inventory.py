"""Inspect PostgreSQL physical relationships without mutating the database."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from typing import Any, Iterable, Mapping

from services.ingestion.base import get_db


def _rows(conn, query: str) -> list[dict[str, Any]]:
    with conn.cursor() as cursor:
        cursor.execute(query)
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _column_type(row: Mapping[str, Any]) -> str:
    return str(row.get("udt_name") or row.get("data_type") or "")


def _polymorphic_columns(columns: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for column in columns:
        grouped[str(column["table_name"])].add(str(column["column_name"]))
    result = []
    for table, names in sorted(grouped.items()):
        for type_name in sorted(name for name in names if name.endswith("_type")):
            id_name = f"{type_name[:-5]}_id"
            if id_name in names:
                result.append({"table_name": table, "type_column": type_name, "id_column": id_name})
    return result


def build_inventory(
    tables: Iterable[Mapping[str, Any]],
    columns: Iterable[Mapping[str, Any]],
    primary_keys: Iterable[Mapping[str, Any]],
    foreign_keys: Iterable[Mapping[str, Any]],
    unique_constraints: Iterable[Mapping[str, Any]],
    indexes: Iterable[Mapping[str, Any]],
    views: Iterable[Mapping[str, Any]] = (),
    exclusion_constraints: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build a deterministic JSON-compatible schema inventory from catalog rows."""
    columns_list = sorted(
        (dict(row) for row in columns),
        key=lambda row: (str(row.get("table_name")), int(row.get("ordinal_position") or 0)),
    )
    table_names = sorted(str(row["table_name"]) for row in tables)
    primary_key_tables = {str(row["table_name"]) for row in primary_keys}
    columns_by_table: dict[str, set[str]] = defaultdict(set)
    for row in columns_list:
        columns_by_table[str(row["table_name"])].add(str(row["column_name"]))
    column_inventory = []
    for row in columns_list:
        column_inventory.append({
            "table_name": row["table_name"],
            "column_name": row["column_name"],
            "type": _column_type(row),
            "nullable": str(row.get("is_nullable", "YES")).upper() == "YES",
        })
    indexes_list = [dict(row) for row in indexes]
    exclusion_list = [dict(row) for row in exclusion_constraints]

    def supports_index(table_name: str, column_name: str) -> bool:
        for index in indexes_list:
            if str(index.get("table_name")) != table_name:
                continue
            definition = str(index.get("indexdef") or "").lower()
            column = column_name.lower()
            if re.search(rf"\(\s*{re.escape(column)}\b", definition):
                return True
            if re.search(rf",\s*{re.escape(column)}\b", definition):
                return True
        return False

    foreign_keys_list = [dict(row) for row in foreign_keys]
    fks_without_indexes = [
        {"table_name": row["table_name"], "column_name": row["column_name"], "constraint_name": row["constraint_name"]}
        for row in foreign_keys_list
        if not supports_index(str(row["table_name"]), str(row["column_name"]))
    ]
    lifecycle_missing = [
        table for table, names in sorted(columns_by_table.items())
        if "status" in names and ("created_at" not in names or "updated_at" not in names)
    ]
    temporal_candidates = [
        table for table, names in sorted(columns_by_table.items())
        if {"valid_from", "valid_until"}.issubset(names)
        or {"effective_from", "effective_until"}.issubset(names)
    ]
    exclusion_tables = {str(row["table_name"]) for row in exclusion_list}
    temporal_without_exclusion = [table for table in temporal_candidates if table not in exclusion_tables]
    suspicious_views = []
    for view in views:
        definition = str(view.get("definition") or "")
        if len(re.findall(r"\bJOIN\b", definition, flags=re.IGNORECASE)) >= 2 and re.search(
            r"\bCOUNT\s*\(", definition, flags=re.IGNORECASE
        ):
            suspicious_views.append(str(view["view_name"]))

    return {
        "tables": table_names,
        "tables_without_primary_keys": [table for table in table_names if table not in primary_key_tables],
        "primary_keys": sorted((dict(row) for row in primary_keys), key=lambda row: tuple(str(value) for value in row.values())),
        "foreign_keys": sorted(foreign_keys_list, key=lambda row: tuple(str(value) for value in row.values())),
        "foreign_keys_without_indexes": sorted(fks_without_indexes, key=lambda row: tuple(str(value) for value in row.values())),
        "unique_constraints": sorted((dict(row) for row in unique_constraints), key=lambda row: tuple(str(value) for value in row.values())),
        "indexes": sorted(indexes_list, key=lambda row: tuple(str(value) for value in row.values())),
        "exclusion_constraints": sorted(exclusion_list, key=lambda row: tuple(str(value) for value in row.values())),
        "columns": column_inventory,
        "lifecycle_tables_missing_governance": lifecycle_missing,
        "temporal_tables_without_overlap_protection": temporal_without_exclusion,
        "suspicious_views": sorted(suspicious_views),
        "polymorphic_references": _polymorphic_columns(columns_list),
        "relationship_shaped_columns": [
            row for row in column_inventory
            if row["type"] in {"_text", "_uuid", "json", "jsonb"}
            and (row["column_name"].endswith("_ids") or row["column_name"] in {"metadata", "evidence", "source_raw"})
        ],
    }


def inventory(conn) -> dict[str, Any]:
    """Read the public PostgreSQL catalog and return a schema inventory."""
    tables = _rows(conn, """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    columns = _rows(conn, """
        SELECT table_name, column_name, data_type, udt_name, is_nullable, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
    """)
    primary_keys = _rows(conn, """
        SELECT tc.table_name, kcu.constraint_name, kcu.column_name, kcu.ordinal_position
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_name = tc.constraint_name
         AND kcu.table_schema = tc.table_schema
         AND kcu.table_name = tc.table_name
        WHERE tc.table_schema = 'public' AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY tc.table_name, kcu.ordinal_position
    """)
    foreign_keys = _rows(conn, """
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS referenced_table,
            ccu.column_name AS referenced_column,
            rc.delete_rule,
            tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_name = tc.constraint_name
         AND kcu.table_schema = tc.table_schema
         AND kcu.table_name = tc.table_name
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        JOIN information_schema.referential_constraints rc
          ON rc.constraint_name = tc.constraint_name
         AND rc.constraint_schema = tc.table_schema
        WHERE tc.table_schema = 'public' AND tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position
    """)
    unique_constraints = _rows(conn, """
        SELECT tc.table_name, tc.constraint_name, kcu.column_name, kcu.ordinal_position
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_name = tc.constraint_name
         AND kcu.table_schema = tc.table_schema
         AND kcu.table_name = tc.table_name
        WHERE tc.table_schema = 'public' AND tc.constraint_type = 'UNIQUE'
        ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position
    """)
    indexes = _rows(conn, """
        SELECT tablename AS table_name, indexname AS index_name, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname
    """)
    views = _rows(conn, """
        SELECT viewname AS view_name, definition
        FROM pg_views
        WHERE schemaname = 'public'
        ORDER BY viewname
    """)
    exclusion_constraints = _rows(conn, """
        SELECT cls.relname AS table_name, con.conname AS constraint_name
        FROM pg_constraint con
        JOIN pg_class cls ON cls.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace
        WHERE nsp.nspname = 'public' AND con.contype = 'x'
        ORDER BY cls.relname, con.conname
    """)
    return build_inventory(
        tables, columns, primary_keys, foreign_keys, unique_constraints, indexes,
        views, exclusion_constraints,
    )


def inventory_as_markdown(report: Mapping[str, Any]) -> str:
    """Render the inventory as concise, reviewable Markdown."""
    lines = ["# PostgreSQL ER Inventory", "", f"Tables: {len(report['tables'])}", ""]
    lines.extend(["## Structural Risks", ""])
    lines.extend(f"- Tables without primary keys: `{table}`" for table in report["tables_without_primary_keys"])
    lines.extend(
        f"- Foreign key without supporting index: `{item['table_name']}.{item['column_name']}`"
        for item in report["foreign_keys_without_indexes"]
    )
    lines.extend(f"- Lifecycle table missing timestamps: `{table}`" for table in report["lifecycle_tables_missing_governance"])
    lines.extend(
        f"- Temporal table without exclusion protection: `{table}`"
        for table in report["temporal_tables_without_overlap_protection"]
    )
    lines.extend(f"- Possible fan-trap view: `{view}`" for view in report["suspicious_views"])
    lines.extend(["## Polymorphic References", ""])
    if report["polymorphic_references"]:
        lines.extend(
            f"- `{item['table_name']}`: `{item['type_column']}` + `{item['id_column']}`"
            for item in report["polymorphic_references"]
        )
    else:
        lines.append("- None detected")
    lines.extend(["", "## Relationship-Shaped Columns", ""])
    if report["relationship_shaped_columns"]:
        lines.extend(
            f"- `{item['table_name']}.{item['column_name']}` ({item['type']})"
            for item in report["relationship_shaped_columns"]
        )
    else:
        lines.append("- None detected")
    lines.extend(["", "## Foreign Keys", ""])
    lines.extend(
        f"- `{item['table_name']}.{item['column_name']}` -> `{item['referenced_table']}.{item['referenced_column']}` ({item['delete_rule']})"
        for item in report["foreign_keys"]
    )
    return "\n".join(lines) + "\n"


def risk_findings(report: Mapping[str, Any]) -> list[str]:
    """Return actionable ER risks discovered by the physical inventory."""
    findings = [
        "polymorphic reference: "
        f"{item['table_name']}.{item['type_column']} + {item['id_column']}"
        for item in report["polymorphic_references"]
    ]
    findings.extend(
        "relationship-shaped column: "
        f"{item['table_name']}.{item['column_name']} ({item['type']})"
        for item in report["relationship_shaped_columns"]
    )
    findings.extend(f"table without primary key: {table}" for table in report.get("tables_without_primary_keys", []))
    findings.extend(
        "foreign key without supporting index: "
        f"{item['table_name']}.{item['column_name']}"
        for item in report.get("foreign_keys_without_indexes", [])
    )
    findings.extend(f"lifecycle table missing governance timestamps: {table}" for table in report.get("lifecycle_tables_missing_governance", []))
    findings.extend(f"temporal table without overlap protection: {table}" for table in report.get("temporal_tables_without_overlap_protection", []))
    findings.extend(f"possible fan-trap view: {view}" for view in report.get("suspicious_views", []))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect PostgreSQL ER relationships without changing data")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--fail-on-risk", action="store_true", help="exit non-zero when ER risk patterns are found")
    args = parser.parse_args()
    conn = get_db()
    try:
        report = inventory(conn)
    finally:
        conn.close()
    if args.format == "markdown":
        print(inventory_as_markdown(report), end="")
    else:
        print(json.dumps(report, indent=2, default=str, sort_keys=True))
    if args.fail_on_risk and risk_findings(report):
        for finding in risk_findings(report):
            print(f"ER risk: {finding}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
