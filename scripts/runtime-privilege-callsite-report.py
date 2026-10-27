#!/usr/bin/env python3
"""Join effective runtime relation privileges to source SQL and explicit revokes.

The report contains schema metadata and source locations only. It does not read
application rows or credentials. Runtime SQL relation candidates are heuristic;
review the source before changing any database grant.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_REVOKE = re.compile(
    r"\bREVOKE\s+(?P<privileges>[A-Z_,\s]+?)\s+ON\s+TABLE\s+"
    r"(?P<relations>.*?)\s+FROM\s+(?:[^;]*?,\s*)?kokonut_runtime\b",
    re.IGNORECASE | re.DOTALL,
)
_PUBLIC_RELATION = re.compile(r"\bpublic\.(?:\"([^\"]+)\"|([a-zA-Z_][\w$]*))")
_DML_PRIVILEGES = {"INSERT", "UPDATE", "DELETE", "TRUNCATE"}


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {label} JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} JSON must contain an object")
    return value


def _source_revokes() -> dict[str, list[dict[str, str]]]:
    revokes: dict[str, list[dict[str, str]]] = defaultdict(list)
    for path in sorted((ROOT / "schemas/postgres").glob("*.sql")):
        source = path.read_text(encoding="utf-8")
        for match in _REVOKE.finditer(source):
            privileges = " ".join(match.group("privileges").split()).upper()
            for relation_match in _PUBLIC_RELATION.finditer(match.group("relations")):
                relation = relation_match.group(1) or relation_match.group(2)
                revokes[relation].append(
                    {"migration": path.name, "privileges": privileges}
                )
    return {
        relation: [
            {"migration": migration, "privileges": privileges}
            for migration, privileges in sorted({
                (entry["migration"], entry["privileges"])
                for entry in entries
            })
        ]
        for relation, entries in revokes.items()
    }


def build_report(probe: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    """Cross-reference observed ACLs, static SQL candidates and explicit revokes."""
    replay = probe
    scoped_probe = probe.get("operator_scope_probe")
    if isinstance(scoped_probe, dict):
        probe = scoped_probe
    acl_rows = probe.get("runtime_public_relation_acl")
    sites = inventory.get("execution_sites")
    if not isinstance(acl_rows, list) or not isinstance(sites, list):
        raise ValueError("inputs lack the relation ACL or execution-site inventory")

    relations: dict[str, dict[str, Any]] = {}
    for row in acl_rows:
        if not isinstance(row, dict) or row.get("schema") != "public":
            raise ValueError("runtime ACL inventory contains an invalid relation row")
        name = row.get("relation")
        if not isinstance(name, str) or not name:
            raise ValueError("runtime ACL inventory contains an invalid relation name")
        relations[name] = {**row, "sites": Counter(), "sources": defaultdict(Counter)}

    for site in sites:
        if not isinstance(site, dict):
            continue
        statement_kind = site.get("statement_kind")
        source = site.get("source")
        if not isinstance(source, str):
            continue
        for relation in site.get("candidate_relations", []):
            entry = relations.get(relation)
            if entry is None:
                continue
            if isinstance(statement_kind, str):
                entry["sites"][statement_kind] += 1
                entry["sources"][source][statement_kind] += 1

    revokes = _source_revokes()
    output_rows: list[dict[str, Any]] = []
    for name, row in sorted(relations.items()):
        dml = any(
            row.get(privilege) is True
            for privilege in ("insert", "update", "delete")
        )
        source_revokes = revokes.get(name, [])
        dml_revokes = [
            revoke for revoke in source_revokes
            if "ALL" in revoke["privileges"].split()
            or bool(_DML_PRIVILEGES.intersection(
                token.strip() for token in revoke["privileges"].split(",")
            ))
        ]
        output_rows.append({
            "relation": name,
            "kind": row.get("kind"),
            "effective_privileges": {
                privilege: row.get(privilege) is True
                for privilege in ("select", "insert", "update", "delete", "truncate")
            },
            "rls_enabled": row.get("rls_enabled") is True,
            "rls_forced": row.get("rls_forced") is True,
            "has_any_dml": dml,
            "candidate_execution_sites_by_statement": dict(
                sorted(row["sites"].items())
            ),
            "candidate_source_files": [
                {
                    "path": source,
                    "statement_counts": dict(sorted(counts.items())),
                }
                for source, counts in sorted(row["sources"].items())
            ],
            "explicit_runtime_revokes": source_revokes,
            "explicit_runtime_dml_revokes": dml_revokes,
            "dml_overlaps_explicit_revoke": bool(dml and dml_revokes),
        })

    dml_without_site = [
        row["relation"] for row in output_rows
        if row["has_any_dml"] and not row["candidate_execution_sites_by_statement"]
    ]
    overlapping = [
        row["relation"] for row in output_rows if row["dml_overlaps_explicit_revoke"]
    ]
    unprotected_dml = [
        row for row in output_rows
        if row["kind"] in {"r", "p"}
        and row["has_any_dml"]
        and not row["rls_enabled"]
    ]
    unprotected_without_site = [
        row["relation"] for row in unprotected_dml
        if not row["candidate_execution_sites_by_statement"]
    ]
    unprotected_overlapping = [
        row["relation"] for row in unprotected_dml
        if row["explicit_runtime_dml_revokes"]
    ]
    return {
        "result": "inventory",
        "source_revision": replay.get("source_revision"),
        "source_dirty": replay.get("working_tree_dirty"),
        "methodology": (
            "Effective table privileges are read from the isolated runtime-role probe. "
            "SQL relation candidates come from runtime-sql-inventory.json and may be "
            "heuristic; they are not proof of reachable execution. Explicit revokes "
            "are a static scan of ordered schema SQL and may omit dynamic SQL. Review "
            "source and database behavior before changing grants."
        ),
        "scope_limit": (
            "No application rows, operator identifiers, or secrets are included. The "
            "report does not cover column privileges, sequence ACLs, object ownership, "
            "security-definer behavior, Directus, external consumers, or production "
            "state."
        ),
        "summary": {
            "runtime_relations": len(output_rows),
            "relations_with_any_dml": sum(row["has_any_dml"] for row in output_rows),
            "tables_with_dml_and_rls_disabled": len(unprotected_dml),
            "relations_with_candidate_execution_sites": sum(
                bool(row["candidate_execution_sites_by_statement"])
                for row in output_rows
            ),
            "dml_relations_without_candidate_sites": len(dml_without_site),
            "dml_relations_matching_explicit_runtime_revoke": len(overlapping),
            "unprotected_dml_relations_without_candidate_sites": len(
                unprotected_without_site
            ),
            "unprotected_dml_relations_matching_explicit_runtime_revoke": len(
                unprotected_overlapping
            ),
        },
        "dml_relations_without_candidate_sites": dml_without_site,
        "dml_relations_matching_explicit_runtime_revoke": overlapping,
        "unprotected_dml_relations_without_candidate_sites": unprotected_without_site,
        "unprotected_dml_relations_matching_explicit_runtime_revoke": (
            unprotected_overlapping
        ),
        "relations": output_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--probe", type=Path, required=True, help="ACL inventory probe JSON"
    )
    parser.add_argument(
        "--sql-inventory", type=Path,
        default=ROOT / "docs/refactor/runtime-sql-inventory.json",
        help="runtime SQL inventory JSON",
    )
    parser.add_argument("--output", type=Path, required=True, help="report output JSON")
    args = parser.parse_args()
    report = build_report(
        _load_json(args.probe, "probe"),
        _load_json(args.sql_inventory, "SQL inventory"),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(args.output)
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
