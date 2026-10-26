#!/usr/bin/env python3
"""Inventory literal Directus permission declarations in the curated SQL seed.

This is a source inventory only. Conditional SQL, later mutations, built-in
policies, and deployed database state can change effective permissions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


def _mask_comments(sql: str) -> str:
    """Replace SQL comments with spaces while preserving offsets and lines."""
    output = list(sql)
    index = 0
    quote: str | None = None
    while index < len(sql):
        char = sql[index]
        if quote == "'":
            if char == "'":
                if index + 1 < len(sql) and sql[index + 1] == "'":
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if quote == '"':
            if char == '"':
                if index + 1 < len(sql) and sql[index + 1] == '"':
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if char == "'":
            quote = "'"
            index += 1
            continue
        if char == '"':
            quote = '"'
            index += 1
            continue
        if sql.startswith("--", index):
            end = sql.find("\n", index)
            end = len(sql) if end < 0 else end
            for position in range(index, end):
                output[position] = " "
            index = end
            continue
        if sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            end = len(sql) if end < 0 else end + 2
            for position in range(index, end):
                if output[position] != "\n":
                    output[position] = " "
            index = end
            continue
        index += 1
    return "".join(output)


def _split_top_level(source: str) -> list[str]:
    values: list[str] = []
    start = 0
    depth = 0
    quote = False
    index = 0
    while index < len(source):
        char = source[index]
        if quote:
            if char == "'":
                if index + 1 < len(source) and source[index + 1] == "'":
                    index += 2
                    continue
                quote = False
        elif char == "'":
            quote = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            values.append(source[start:index].strip())
            start = index + 1
        index += 1
    values.append(source[start:].strip())
    return values


def _literal(value: str) -> Any:
    if value.upper() == "NULL":
        return None
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def _insert_rows(sql: str, table: str) -> list[dict[str, Any]]:
    clean = _mask_comments(sql)
    pattern = re.compile(
        rf"INSERT\s+INTO\s+(?:public\.)?{re.escape(table)}\s*\((.*?)\)\s*VALUES\b",
        re.IGNORECASE | re.DOTALL,
    )
    records = []
    for match in pattern.finditer(clean):
        columns = [part.strip().strip('"') for part in _split_top_level(match.group(1))]
        index = match.end()
        row_start: int | None = None
        row_depth = 0
        quote = False
        while index < len(clean):
            char = clean[index]
            if quote:
                if char == "'":
                    if index + 1 < len(clean) and clean[index + 1] == "'":
                        index += 2
                        continue
                    quote = False
            elif char == "'":
                quote = True
            elif char == ";" and row_depth == 0:
                break
            elif char == "(" and row_depth == 0:
                row_start = index + 1
                row_depth = 1
            elif char == "(" and row_depth > 0:
                row_depth += 1
            elif char == ")" and row_depth > 0:
                row_depth -= 1
                if row_depth == 0 and row_start is not None:
                    values = [_literal(item) for item in _split_top_level(clean[row_start:index])]
                    if len(values) != len(columns):
                        raise ValueError(
                            f"{table} insert at line {clean.count(chr(10), 0, row_start) + 1} "
                            f"has {len(values)} values for {len(columns)} columns"
                        )
                    records.append(
                        {
                            "line": clean.count("\n", 0, row_start) + 1,
                            **dict(zip(columns, values, strict=True)),
                        }
                    )
                    row_start = None
            index += 1
    return records


def _permission_mutations(sql: str) -> list[dict[str, Any]]:
    clean = _mask_comments(sql)
    pattern = re.compile(
        r"\b(UPDATE|DELETE\s+FROM)\s+(?:public\.)?directus_permissions\b",
        re.IGNORECASE,
    )
    mutations = []
    for match in pattern.finditer(clean):
        quote = False
        index = match.end()
        while index < len(clean):
            char = clean[index]
            if quote:
                if char == "'":
                    if index + 1 < len(clean) and clean[index + 1] == "'":
                        index += 2
                        continue
                    quote = False
            elif char == "'":
                quote = True
            elif char == ";":
                break
            index += 1
        statement = " ".join(clean[match.start():index].split())
        operation = "delete" if match.group(1).upper().startswith("DELETE") else "update"
        mutations.append(
            {
                "line": clean.count("\n", 0, match.start()) + 1,
                "operation": operation,
                "target": "directus_permissions",
                "statement": statement,
            }
        )
    return mutations


def build_inventory(source: Path, root: Path) -> dict[str, Any]:
    sql = source.read_text(encoding="utf-8")
    policies = {
        str(row.get("id")): row.get("name")
        for row in _insert_rows(sql, "directus_policies")
        if row.get("id") and row.get("name")
    }
    role_names = {
        str(row.get("id")): row.get("name")
        for row in _insert_rows(sql, "directus_roles")
        if row.get("id") and row.get("name")
    }
    policy_roles: dict[str, set[str]] = {}
    for access in _insert_rows(sql, "directus_access"):
        policy_id = str(access.get("policy") or "")
        role_id = str(access.get("role") or "")
        if policy_id and role_id:
            policy_roles.setdefault(policy_id, set()).add(role_names.get(role_id, role_id))

    rules = []
    for row in _insert_rows(sql, "directus_permissions"):
        raw_fields = row.get("fields")
        fields = None if raw_fields is None else (
            ["*"] if raw_fields == "*" else [field.strip() for field in str(raw_fields).split(",")]
        )
        policy_id = str(row.get("policy") or "")
        rules.append(
            {
                "line": row["line"],
                "policy_id": policy_id,
                "policy": policies.get(policy_id, policy_id or None),
                "roles": sorted(policy_roles.get(policy_id, set())),
                "collection": row.get("collection"),
                "action": row.get("action"),
                "row_filter": row.get("permissions"),
                "validation": row.get("validation"),
                "fields": fields,
                "field_access": "wildcard" if fields == ["*"] else "explicit" if fields else "unknown",
            }
        )
    rules.sort(key=lambda item: (str(item["policy"]), str(item["collection"]), str(item["action"]), item["line"]))
    mutations = _permission_mutations(sql)
    wildcard = [rule for rule in rules if rule["field_access"] == "wildcard"]
    summary = {
        "literal_permission_rows": len(rules),
        "wildcard_field_rows": len(wildcard),
        "explicit_field_rows": sum(rule["field_access"] == "explicit" for rule in rules),
        "unknown_field_rows": sum(rule["field_access"] == "unknown" for rule in rules),
        "update_statements": sum(mutation["operation"] == "update" for mutation in mutations),
        "delete_statements": sum(mutation["operation"] == "delete" for mutation in mutations),
        "wildcard_rows_by_collection": dict(
            sorted(
                (collection, sum(rule["collection"] == collection for rule in wildcard))
                for collection in {rule["collection"] for rule in wildcard}
            )
        ),
        "wildcard_rows_by_policy": dict(
            sorted(
                (policy, sum(rule["policy"] == policy for rule in wildcard))
                for policy in {rule["policy"] for rule in wildcard}
            )
        ),
        "declared_farm_activity_rules": sum(rule["collection"] == "farm_activity" for rule in rules),
    }
    return {
        "format_version": 1,
        "source": source.relative_to(root).as_posix(),
        "source_sha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        "scope": "literal INSERT declarations in the curated Directus SQL seed",
        "limitations": [
            "This is not effective deployed permission state.",
            "Conditional inserts, later UPDATE or DELETE statements, built-in policies, and operator-created policies may change effective access.",
            "Field lists do not establish row, relation, hook, or runtime-role parity.",
            "No database, credentials, Directus provider, or business records are read.",
        ],
        "summary": summary,
        "rules": rules,
        "source_mutations": mutations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write JSON inventory to this path")
    parser.add_argument("--check", type=Path, help="Fail if this JSON file differs from source")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / "config/directus/permissions.sql"
    rendered = json.dumps(build_inventory(source, root), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not args.check.exists() or args.check.read_text(encoding="utf-8") != rendered:
            print(f"Directus permission inventory is stale: {args.check}", file=sys.stderr)
            return 1
        print(f"Directus permission inventory is current: {args.check}")
        return 0
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        summary = build_inventory(source, root)["summary"]
        print(
            "Directus permission inventory: "
            f"{summary['literal_permission_rows']} literal rules, "
            f"{summary['wildcard_field_rows']} wildcard field rules"
        )
        return 0
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
