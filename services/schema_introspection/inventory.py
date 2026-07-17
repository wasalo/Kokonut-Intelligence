"""Inspect PostgreSQL physical relationships without mutating the database."""

from __future__ import annotations

import argparse
import json
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
) -> dict[str, Any]:
    """Build a deterministic JSON-compatible schema inventory from catalog rows."""
    columns_list = sorted(
        (dict(row) for row in columns),
        key=lambda row: (str(row.get("table_name")), int(row.get("ordinal_position") or 0)),
    )
    table_names = sorted(str(row["table_name"]) for row in tables)
    column_inventory = []
    for row in columns_list:
        column_inventory.append({
            "table_name": row["table_name"],
            "column_name": row["column_name"],
            "type": _column_type(row),
            "nullable": str(row.get("is_nullable", "YES")).upper() == "YES",
        })
    return {
        "tables": table_names,
        "primary_keys": sorted((dict(row) for row in primary_keys), key=lambda row: tuple(str(value) for value in row.values())),
        "foreign_keys": sorted((dict(row) for row in foreign_keys), key=lambda row: tuple(str(value) for value in row.values())),
        "unique_constraints": sorted((dict(row) for row in unique_constraints), key=lambda row: tuple(str(value) for value in row.values())),
        "indexes": sorted((dict(row) for row in indexes), key=lambda row: tuple(str(value) for value in row.values())),
        "columns": column_inventory,
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
    return build_inventory(tables, columns, primary_keys, foreign_keys, unique_constraints, indexes)


def inventory_as_markdown(report: Mapping[str, Any]) -> str:
    """Render the inventory as concise, reviewable Markdown."""
    lines = ["# PostgreSQL ER Inventory", "", f"Tables: {len(report['tables'])}", ""]
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
