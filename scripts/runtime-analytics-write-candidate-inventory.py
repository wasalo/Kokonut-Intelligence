#!/usr/bin/env python3
"""Build a review inventory of analytics SQL candidates against observed ACLs.

The result joins the generated SQL-site inventory to a disposable runtime ACL
report. It is a source-review aid only: static SQL candidates do not prove that
an operation is reachable, authorized for a tenant, or safe to execute.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WRITE_KINDS = {"INSERT", "UPDATE", "DELETE"}
ANALYTICS_PREFIX = "services/analytics/"


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {label} JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} JSON must contain an object")
    return value


def _file_sha256(path: Path) -> str:
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError("could not fingerprint inventory input") from exc
    return digest


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def build_inventory(acl_report: dict[str, Any], sql_inventory: dict[str, Any]) -> dict[str, Any]:
    """Join analytics write candidates to current observed public table ACLs."""
    relation_rows = acl_report.get("relations")
    sites = sql_inventory.get("execution_sites")
    if not isinstance(relation_rows, list) or not isinstance(sites, list):
        raise ValueError("input reports lack relation rows or SQL execution sites")

    sites_by_relation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for site in sites:
        if not isinstance(site, dict):
            raise ValueError("SQL inventory contains a malformed execution site")
        source = site.get("source")
        kind = site.get("statement_kind")
        relations = site.get("candidate_relations")
        if not isinstance(source, str) or not isinstance(relations, list):
            continue
        if not source.startswith(ANALYTICS_PREFIX) or kind not in WRITE_KINDS:
            continue
        for relation in relations:
            if isinstance(relation, str):
                sites_by_relation[relation].append(site)

    entries: list[dict[str, Any]] = []
    candidate_site_ids: set[str] = set()
    source_files: set[str] = set()
    statement_counts: Counter[str] = Counter()
    expression_counts: Counter[str] = Counter()
    missing_site_relations: list[str] = []

    for row in relation_rows:
        if not isinstance(row, dict):
            raise ValueError("ACL report contains a malformed relation row")
        relation = row.get("relation")
        if not isinstance(relation, str) or row.get("kind") not in {"r", "p"}:
            continue
        if row.get("rls_enabled") is True or row.get("has_any_dml") is not True:
            continue

        analytics_sources = [
            source for source in row.get("candidate_source_files", [])
            if isinstance(source, dict)
            and isinstance(source.get("path"), str)
            and source["path"].startswith(ANALYTICS_PREFIX)
            and any(
                int(source.get("statement_counts", {}).get(kind, 0) or 0) > 0
                for kind in WRITE_KINDS
            )
        ]
        if not analytics_sources:
            continue

        source_paths = {source["path"] for source in analytics_sources}
        matching_sites = [
            site for site in sites_by_relation.get(relation, [])
            if site.get("source") in source_paths
        ]
        locations = []
        for site in matching_sites:
            site_id = site.get("id")
            kind = site.get("statement_kind")
            expression_kind = site.get("expression_kind")
            if not isinstance(site_id, str) or kind not in WRITE_KINDS:
                continue
            candidate_site_ids.add(site_id)
            source_files.add(str(site["source"]))
            statement_counts[str(kind)] += 1
            if isinstance(expression_kind, str):
                expression_counts[expression_kind] += 1
            locations.append({
                "id": site_id,
                "path": site["source"],
                "line": site.get("line"),
                "scope": site.get("scope"),
                "method": site.get("method"),
                "statement_kind": kind,
                "expression_kind": expression_kind,
                "static_sql_sha256": site.get("static_sql_sha256"),
                "operation_refs": sorted(
                    ref for ref in site.get("operation_refs", []) if isinstance(ref, str)
                ),
            })
        if not locations:
            missing_site_relations.append(relation)

        entries.append({
            "relation": relation,
            "observed_acl": {
                "select": row.get("effective_privileges", {}).get("select") is True,
                "insert": row.get("effective_privileges", {}).get("insert") is True,
                "update": row.get("effective_privileges", {}).get("update") is True,
                "delete": row.get("effective_privileges", {}).get("delete") is True,
                "rls_enabled": row.get("rls_enabled") is True,
            },
            "migration_boundary": {
                "expected": row.get("expected_runtime_boundary"),
                "configured": row.get("configured_runtime_boundary"),
                "matches_source": row.get("runtime_boundary_policy_matches_source"),
            },
            "static_candidate_source_files": sorted(source_paths),
            "candidate_write_sites": sorted(
                locations,
                key=lambda site: (site["path"], site["line"] or 0, site["id"]),
            ),
            "review_status": "source_and_caller_review_required",
        })

    entries.sort(key=lambda entry: entry["relation"])
    unique_site_count = len(candidate_site_ids)
    return {
        "result": "inventory",
        "generated_by": "scripts/runtime-analytics-write-candidate-inventory.py",
        "scope": (
            "Unprotected public ordinary/partitioned relations with an analytics-package "
            "INSERT/UPDATE/DELETE candidate, joined to generated runtime SQL sites."
        ),
        "limitations": [
            "Static SQL relation candidates are heuristic and do not prove execution reachability.",
            "No caller authorization, tenant identity, RLS, worker identity, or Directus behavior is inferred.",
            "No application rows, SQL text, credentials, or database state are included.",
            "Do not revoke grants from this inventory alone; review source callers and transaction contracts first.",
        ],
        "inputs": {
            "acl_report_source_revision": acl_report.get("source_revision"),
            "runtime_role_policy_sha256": acl_report.get("runtime_role_policy_source", {}).get("sha256"),
            "sql_inventory_version": sql_inventory.get("version"),
        },
        "summary": {
            "relations": len(entries),
            "candidate_sites": unique_site_count,
            "source_files": len(source_files),
            "sites_by_statement": dict(sorted(statement_counts.items())),
            "sites_by_expression_kind": dict(sorted(expression_counts.items())),
            "relations_missing_matching_sql_site": sorted(missing_site_relations),
            "relations_with_declared_boundary": sum(
                entry["migration_boundary"]["expected"] is not None for entry in entries
            ),
        },
        "relations": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--acl-report", type=Path,
        default=ROOT / "docs/refactor/builds/2026-10-26-recovery/sprint-runtime-privilege-callsite-report.json",
    )
    parser.add_argument(
        "--sql-inventory", type=Path,
        default=ROOT / "docs/refactor/runtime-sql-inventory.json",
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="output JSON path",
    )
    args = parser.parse_args()
    report = build_inventory(
        _read_json(args.acl_report, "ACL report"),
        _read_json(args.sql_inventory, "SQL inventory"),
    )
    report["inputs"].update({
        "acl_report_path": _display_path(args.acl_report),
        "acl_report_sha256": _file_sha256(args.acl_report),
        "sql_inventory_path": _display_path(args.sql_inventory),
        "sql_inventory_sha256": _file_sha256(args.sql_inventory),
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
