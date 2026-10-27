#!/usr/bin/env python3
"""Join effective runtime relation privileges to source SQL and explicit revokes.

The report contains schema metadata and source locations only. It does not read
application rows or credentials. Runtime SQL relation candidates are heuristic;
review the source before changing any database grant.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_REVOKE = re.compile(
    r"\bREVOKE\s+(?P<privileges>[^;]+?)\s+ON\s+TABLE\s+"
    r"(?P<relations>[^;]+?)\s+FROM\s+(?P<grantees>[^;]+);",
    re.IGNORECASE | re.DOTALL,
)
_PUBLIC_RELATION = re.compile(r"\bpublic\.(?:\"([^\"]+)\"|([a-zA-Z_][\w$]*))")
_DML_PRIVILEGES = {"INSERT", "UPDATE", "DELETE", "TRUNCATE"}
_RUNTIME_POLICY_NAMES = {
    "private": "_RUNTIME_PRIVATE_TABLES",
    "mutations": "_RUNTIME_MUTATION_TABLES",
}
# This append-only event ledger intentionally restores only SELECT after its
# migration revokes ALL; the dedicated trigger owner remains the sole writer.
_SOURCE_REVOKE_POLICY_OVERRIDES = {
    # The migration revokes table-wide access, then restores a verified read-only
    # column allowlist for API-key authentication.
    "api_key": "read_only_column_allowlist",
    "farm_activity_operator_event": "runtime_mutations_denied",
}


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
            if not re.search(
                r"\bkokonut_runtime\b", match.group("grantees"), re.IGNORECASE
            ):
                continue
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


def _runtime_role_boundaries() -> tuple[dict[str, str], str]:
    """Read table-denial and special column-boundary declarations without importing."""
    source_path = ROOT / "services/migration/runtime_role.py"
    try:
        source_text = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source_text, filename=str(source_path))
    except (OSError, SyntaxError) as exc:
        raise ValueError("could not parse runtime-role policy lists") from exc

    values: dict[str, set[str]] = {}
    api_key_columns: tuple[str, ...] | None = None
    function_names = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "_API_KEY_COLUMNS":
            if not isinstance(node.value, (ast.Tuple, ast.List)) or any(
                not isinstance(item, ast.Constant) or not isinstance(item.value, str)
                for item in node.value.elts
            ):
                raise ValueError("_API_KEY_COLUMNS must be a literal tuple or list")
            api_key_columns = tuple(item.value for item in node.value.elts)
        if not isinstance(target, ast.Name) or target.id not in _RUNTIME_POLICY_NAMES.values():
            continue
        if not isinstance(node.value, (ast.Tuple, ast.List)):
            raise ValueError(f"{target.id} must be a literal tuple or list")
        if any(not isinstance(item, ast.Constant) or not isinstance(item.value, str) for item in node.value.elts):
            raise ValueError(f"{target.id} must contain only literal relation names")
        values[target.id] = {item.value for item in node.value.elts}

    if set(values) != set(_RUNTIME_POLICY_NAMES.values()):
        raise ValueError("runtime-role source lacks an explicit scoped denial list")
    if values[_RUNTIME_POLICY_NAMES["private"]] & values[_RUNTIME_POLICY_NAMES["mutations"]]:
        raise ValueError("runtime-role private and mutation-only lists overlap")

    denials = {
        **{table: "no_direct_runtime_access" for table in values[_RUNTIME_POLICY_NAMES["private"]]},
        **{table: "runtime_mutations_denied" for table in values[_RUNTIME_POLICY_NAMES["mutations"]]},
    }
    if (
        api_key_columns == (
            "id", "key_hash", "key_prefix", "role_id", "scopes", "expires_at", "is_active"
        )
        and {"_apply_api_key_boundary", "_verify_api_key_boundary"} <= function_names
    ):
        denials["api_key"] = "read_only_column_allowlist"
    return denials, hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def _expected_runtime_denial(revokes: list[dict[str, str]]) -> str | None:
    if not revokes:
        return None
    if any("ALL" in entry["privileges"].split() for entry in revokes):
        return "no_direct_runtime_access"
    if any(
        _DML_PRIVILEGES.intersection(
            token.strip() for token in entry["privileges"].split(",")
        )
        for entry in revokes
    ):
        return "runtime_mutations_denied"
    return None


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
    runtime_boundaries, runtime_role_sha256 = _runtime_role_boundaries()
    scoped_write = probe.get("runtime_scoped_write_policy")
    expected_scoped_write = {
        "private_relations_expected": 79,
        "mutation_denied_relations_expected": 12,
        "private_relations_verified": 79,
        "mutation_denied_relations_verified": 12,
        "direct_table_privilege_violations": 0,
        "direct_column_privilege_violations": 0,
        "farm_activity_ledger_readable": 1,
    }
    runtime_role_acl_checks_passed = (
        isinstance(scoped_write, dict)
        and all(scoped_write.get(key) == value for key, value in expected_scoped_write.items())
    )
    api_key_policy = probe.get("runtime_api_key_policy")
    api_key_boundary_passed = api_key_policy == {
        "select_columns": [
            "id", "key_hash", "key_prefix", "role_id", "scopes", "expires_at", "is_active"
        ],
        "insert_columns": [],
        "update_columns": [],
        "delete": False,
        "verified_by_provisioner": True,
    }
    full_schema_replay_passed = (
        replay.get("result") == "passed"
        and replay.get("schema_files_applied") == 642
        and replay.get("schema_files_pending") == 0
        and replay.get("schema_files_failed") == 0
        and replay.get("seeds_applied") == 0
    )
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
        expected_boundary = _SOURCE_REVOKE_POLICY_OVERRIDES.get(name)
        if expected_boundary is None:
            expected_boundary = _expected_runtime_denial(dml_revokes)
        configured_boundary = runtime_boundaries.get(name)
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
            "expected_runtime_boundary": expected_boundary,
            "configured_runtime_boundary": configured_boundary,
            "runtime_boundary_policy_matches_source": (
                configured_boundary == expected_boundary
                if expected_boundary is not None else None
            ),
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
    unprotected_without_write_site = [
        row["relation"] for row in unprotected_dml
        if not any(
            row["candidate_execution_sites_by_statement"].get(kind, 0)
            for kind in ("INSERT", "UPDATE", "DELETE")
        )
    ]
    unprotected_overlapping = [
        row["relation"] for row in unprotected_dml
        if row["explicit_runtime_dml_revokes"]
    ]
    write_relations_by_service: dict[str, set[str]] = defaultdict(set)
    for row in unprotected_dml:
        for source in row["candidate_source_files"]:
            if not any(
                source["statement_counts"].get(kind, 0)
                for kind in ("INSERT", "UPDATE", "DELETE")
            ):
                continue
            parts = Path(source["path"]).parts
            service = parts[1] if len(parts) > 2 and parts[0] == "services" else "other"
            write_relations_by_service[service].add(row["relation"])
    policy_rows = [row for row in output_rows if row["expected_runtime_boundary"] is not None]
    policy_gaps = [
        row["relation"] for row in policy_rows
        if not row["runtime_boundary_policy_matches_source"]
    ]
    return {
        "result": "inventory",
        "source_revision": replay.get("source_revision"),
        "source_dirty": replay.get("working_tree_dirty"),
        "methodology": (
            "Effective table privileges are read from the isolated runtime-role probe. "
            "SQL relation candidates come from runtime-sql-inventory.json and may be "
            "heuristic; they are not proof of reachable execution. Explicit revokes "
            "are a static scan of ordered schema SQL and may omit dynamic SQL. The "
            "provisioning-policy comparison statically parses runtime_role.py lists; "
            "the runtime_role_acceptance record separately states whether this probe "
            "also exercised full-schema role provisioning and its scoped ACL checks. "
            "Review source and database behavior before changing grants."
        ),
        "scope_limit": (
            "No application rows, operator identifiers, or secrets are included. The "
            "report does not include a full column ACL inventory, sequence ACLs, object "
            "ownership, security-definer behavior, Directus, external consumers, or "
            "production state. The API-key read-only column allowlist is separately "
            "verified by the runtime provisioner. Static policy coverage and its source "
            "digest do not prove that the provisioner has executed."
        ),
        "runtime_role_acceptance": {
            "full_schema_replay_passed": full_schema_replay_passed,
            "scoped_acl_checks_passed": runtime_role_acl_checks_passed,
            "scoped_acl_summary": scoped_write if isinstance(scoped_write, dict) else None,
            "api_key_column_boundary_passed": api_key_boundary_passed,
            "target_scope": "isolated disposable database only",
            "production_or_candidate_state_established": False,
        },
        "runtime_role_policy_source": {
            "path": "services/migration/runtime_role.py",
            "sha256": runtime_role_sha256,
        },
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
            "unprotected_dml_relations_without_candidate_write_sites": len(
                unprotected_without_write_site
            ),
            "unprotected_dml_relations_matching_explicit_runtime_revoke": len(
                unprotected_overlapping
            ),
            "migration_revoked_relations_with_runtime_policy": len(policy_rows) - len(policy_gaps),
            "migration_revoked_relations_missing_or_mismatched_runtime_policy": len(policy_gaps),
        },
        "dml_relations_without_candidate_sites": dml_without_site,
        "dml_relations_matching_explicit_runtime_revoke": overlapping,
        "unprotected_dml_relations_without_candidate_sites": unprotected_without_site,
        "unprotected_dml_relations_without_candidate_write_sites": (
            unprotected_without_write_site
        ),
        "unprotected_candidate_write_relations_by_service": {
            service: len(relations)
            for service, relations in sorted(
                write_relations_by_service.items(), key=lambda item: item[0]
            )
        },
        "unprotected_dml_relations_matching_explicit_runtime_revoke": (
            unprotected_overlapping
        ),
        "migration_revoked_relations_missing_or_mismatched_runtime_policy": policy_gaps,
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
