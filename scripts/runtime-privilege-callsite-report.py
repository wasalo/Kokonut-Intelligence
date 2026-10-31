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
_TABLE_DML_PRIVILEGES = {"INSERT", "UPDATE", "DELETE"}
_RUNTIME_POLICY_NAMES = {
    "private": "_RUNTIME_PRIVATE_TABLES",
    "mutations": "_RUNTIME_MUTATION_TABLES",
    "append_only": "_RUNTIME_APPEND_ONLY_TABLES",
}
# The role provisioner recognizes append-only audit ledgers separately from
# fully read-only relations; the farm-activity operator event remains a
# trigger-owned, read-only exception.
_SOURCE_REVOKE_POLICY_OVERRIDES = {
    # The migration revokes table-wide access, then restores a verified read-only
    # column allowlist for API-key authentication.
    "api_key": "read_only_column_allowlist",
    "farm_activity_operator_event": "runtime_mutations_denied",
    "advisory_rule": "runtime_mutations_denied",
    "crop_family": "runtime_mutations_denied",
    "crop_nutrient_removal_factor": "runtime_mutations_denied",
    "certification_type": "runtime_mutations_denied",
    "cooperative_type": "runtime_mutations_denied",
    "dfs_insurance_product_type": "runtime_mutations_denied",
    "evidence_maturity_level": "runtime_mutations_denied",
    "sensor_type": "runtime_mutations_denied",
    "waste_type": "runtime_mutations_denied",
    "disposal_method": "runtime_mutations_denied",
    "graph_node_type": "runtime_mutations_denied",
    "graph_edge_type": "runtime_mutations_denied",
    "agent_action_log": "runtime_mutations_denied",
    "carbon_benchmark": "runtime_mutations_denied",
    "crop_gdd_config": "runtime_mutations_denied",
    "pest_degree_day_config": "runtime_mutations_denied",
    "revenue_multiplier_config": "runtime_mutations_denied",
    "reference_class": "runtime_mutations_denied",
    "farmer_credential_type": "runtime_mutations_denied",
    "market_reference_data": "runtime_mutations_denied",
    "quantity_unit": "runtime_mutations_denied",
    "yield_benchmark": "runtime_mutations_denied",
    "metric_definition": "runtime_mutations_denied",
    "service_registry": "runtime_mutations_denied",
    # Migration 690 preserves reads after its table-wide REVOKE ALL, and 691
    # applies the same boundary through a loop over these two reporting inputs.
    "capex_breakdown": "runtime_mutations_denied",
    # Capital-source records are read by reporting code; reviewed pilot seeds
    # use the maintenance identity and Directus has a separate SQL role.
    "capital_source": "runtime_mutations_denied",
    # Consent categories have no application writer; migration 401 leaves
    # retention windows unset and the dynamic policy records live separately.
    "consent_data_type": "runtime_mutations_denied",
    # Benchmark references are globally readable, but writes belong to a
    # separate maintenance/import identity, not the application runtime role.
    "process_benchmark": "runtime_mutations_denied",
    # Application reads are location-filtered; benchmark reference writes use
    # a separate maintenance/import identity. External importer use through the
    # runtime login is not confirmed by repository source review.
    "living_wage_benchmark": "runtime_mutations_denied",
    # This grouped public projection is read-only in application code and is
    # guarded against becoming updatable before mutation grants are removed.
    "v_public_farm_summary": "runtime_mutations_denied",
    "water_access": "runtime_mutations_denied",
    "attestation_plan": "runtime_mutations_denied",
    # The existing location-scoped pollinator functions own narrow column
    # grants; migration 692 removes only direct app/Directus DML after the
    # legacy Python writer helpers were retired.
    "hive_record": "runtime_mutations_denied",
    "pollinator_hive_inspection": "runtime_mutations_denied",
    # Migrations 619–621 already define signed location-scoped capture;
    # migration 693 keeps the compatibility runtime grant from restoring DML.
    "pollinator_observation": "runtime_mutations_denied",
    "pollinator_habitat": "runtime_mutations_denied",
    "pesticide_impact_log": "runtime_mutations_denied",
    # Event definitions are read-only to the general runtime. The separate
    # dispatch owner and Directus grants are intentionally left unchanged.
    "event_handler": "runtime_mutations_denied",
    "dfs_currency": "runtime_mutations_denied",
    "ghg_emission_factor": "runtime_mutations_denied",
    "operations_protocol": "runtime_mutations_denied",
    "process_maturity_level": "runtime_mutations_denied",
    "pollinator_species_reference": "runtime_mutations_denied",
    "gri_indicator": "runtime_mutations_denied",
    "governance_framework": "runtime_mutations_denied",
    "impact_framework": "runtime_mutations_denied",
    "impact_dimension": "runtime_mutations_denied",
    "expense_category": "runtime_mutations_denied",
    "crisp_risk_dimension": "runtime_mutations_denied",
    "data_access_log": "runtime_append_only_read_insert",
    "access_audit_log": "runtime_append_only_read_insert",
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
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
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
    if (
        values[_RUNTIME_POLICY_NAMES["append_only"]]
        & (values[_RUNTIME_POLICY_NAMES["private"]] | values[_RUNTIME_POLICY_NAMES["mutations"]])
    ):
        raise ValueError("runtime-role append-only list overlaps another policy list")

    denials = {
        **{table: "no_direct_runtime_access" for table in values[_RUNTIME_POLICY_NAMES["private"]]},
        **{table: "runtime_mutations_denied" for table in values[_RUNTIME_POLICY_NAMES["mutations"]]},
        **{
            table: "runtime_append_only_read_insert"
            for table in values[_RUNTIME_POLICY_NAMES["append_only"]]
        },
    }
    provisioner = functions.get("provision_runtime_role")
    provisioner_calls = {
        node.func.id
        for node in ast.walk(provisioner)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    } if provisioner is not None else set()
    if (
        api_key_columns == (
            "id", "key_hash", "key_prefix", "role_id", "scopes", "expires_at", "is_active"
        )
        and {"_apply_api_key_boundary", "_verify_api_key_boundary"} <= functions.keys()
        and {"_apply_api_key_boundary", "_verify_api_key_boundary"} <= provisioner_calls
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
    schema_files = list((ROOT / "schemas/postgres").glob("*.sql"))
    expected_schema_files = len(schema_files)
    repository_latest_migration = max(
        (
            int(match.group(1))
            for path in schema_files
            if (match := re.match(r"(\d+)_", path.name)) is not None
        ),
        default=None,
    )
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
        relations[name] = {
            **row,
            "sites": Counter(),
            "sources": defaultdict(Counter),
            "write_target_sites": Counter(),
            "write_target_sources": defaultdict(Counter),
        }

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
        if statement_kind in {"INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE"}:
            for relation in site.get("write_target_relations", []):
                entry = relations.get(relation)
                if entry is None:
                    continue
                entry["write_target_sites"][statement_kind] += 1
                entry["write_target_sources"][source][statement_kind] += 1

    revokes = _source_revokes()
    runtime_boundaries, runtime_role_sha256 = _runtime_role_boundaries()
    scoped_write = probe.get("runtime_scoped_write_policy")
    private_relation_count = sum(
        policy == "no_direct_runtime_access" for policy in runtime_boundaries.values()
    )
    mutation_denial_count = sum(
        policy == "runtime_mutations_denied" for policy in runtime_boundaries.values()
    )
    expected_scoped_write = {
        "direct_table_privilege_violations": 0,
        "direct_column_privilege_violations": 0,
        "farm_activity_ledger_readable": 1,
        "service_registry_read_only_verified": 1,
        "append_only_relations_expected": 2,
        "append_only_relations_verified": 2,
        "append_only_select_insert_verified": 2,
        "append_only_mutations_denied": 2,
        "append_only_column_grants_denied": 2,
    }
    recorded_scoped_write_passed = (
        isinstance(scoped_write, dict)
        and type(scoped_write.get("service_registry_read_only_verified")) is int
        and all(scoped_write.get(key) == value for key, value in expected_scoped_write.items())
        and scoped_write.get("private_relations_expected")
        == scoped_write.get("private_relations_verified")
        and scoped_write.get("mutation_denied_relations_expected")
        == scoped_write.get("mutation_denied_relations_verified")
    )
    current_scoped_write_coverage_observed = (
        recorded_scoped_write_passed
        and scoped_write.get("private_relations_expected") == private_relation_count
        and scoped_write.get("mutation_denied_relations_expected") == mutation_denial_count
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
    append_only_policy = probe.get("runtime_append_only_policy")
    append_only_boundary_passed = append_only_policy == {
        "relations_expected": 2,
        "relations_verified": 2,
        "select_insert_verified": 2,
        "mutations_denied": 2,
        "column_grants_denied": 2,
        "verified_by_provisioner": True,
    }
    recorded_schema_files_expected = replay.get("schema_files_expected")
    if not isinstance(recorded_schema_files_expected, int):
        # Older probes predate the self-reported expected count. For those
        # artifacts, preserve the prior best-effort check against the checkout.
        recorded_schema_files_expected = expected_schema_files
    full_schema_replay_passed = (
        replay.get("result") == "passed"
        and replay.get("schema_files_applied") == recorded_schema_files_expected
        and replay.get("schema_files_pending") == 0
        and replay.get("schema_files_failed") == 0
        and replay.get("seeds_applied") == 0
    )
    observed_latest_migration = (
        replay.get("latest_applied_migration")
        or replay.get("latest_migration")
        or replay.get("schema_status", {}).get("latest")
    )
    observed_migration_match = (
        re.match(r"(?:schema:)?(\d+)_", observed_latest_migration)
        if isinstance(observed_latest_migration, str)
        else None
    )
    observed_latest_migration_number = (
        int(observed_migration_match.group(1))
        if observed_migration_match is not None
        else None
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
        revoked_dml_privileges: set[str] = set()
        for revoke in dml_revokes:
            tokens = {token.strip().upper() for token in revoke["privileges"].split(",")}
            if tokens & {"ALL", "ALL PRIVILEGES"}:
                revoked_dml_privileges.update(_TABLE_DML_PRIVILEGES)
            else:
                revoked_dml_privileges.update(
                    _TABLE_DML_PRIVILEGES.intersection(tokens)
                )
        effective_dml_privileges = {
            privilege
            for privilege in _TABLE_DML_PRIVILEGES
            if row.get(privilege.lower()) is True
        }
        # data_access_log restores INSERT after a migration-level REVOKE ALL;
        # its only intended runtime DML privilege is the append operation.
        policy_allowed_dml = (
            {"INSERT"}
            if expected_boundary == "runtime_append_only_read_insert"
            else set()
        )
        effective_dml_revokes = sorted(
            (effective_dml_privileges & revoked_dml_privileges) - policy_allowed_dml
        )
        output_rows.append({
            "relation": name,
            "kind": row.get("kind"),
            "effective_privileges": {
                privilege: row.get(privilege) is True
                for privilege in ("select", "insert", "update", "delete", "truncate")
            },
            "effective_truncate_privilege": row.get("truncate") is True,
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
            "candidate_write_target_sites_by_statement": dict(
                sorted(row["write_target_sites"].items())
            ),
            "candidate_write_target_source_files": [
                {
                    "path": source,
                    "statement_counts": dict(sorted(counts.items())),
                }
                for source, counts in sorted(row["write_target_sources"].items())
            ],
            "explicit_runtime_revokes": source_revokes,
            "explicit_runtime_dml_revokes": dml_revokes,
            "effective_dml_privileges": sorted(effective_dml_privileges),
            "effective_dml_revokes": effective_dml_revokes,
            "dml_overlaps_explicit_revoke": bool(effective_dml_revokes),
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
        if not row["candidate_write_target_sites_by_statement"]
    ]
    unprotected_overlapping = [
        row["relation"] for row in unprotected_dml
        if row["dml_overlaps_explicit_revoke"]
    ]
    write_relations_by_service: dict[str, set[str]] = defaultdict(set)
    for row in unprotected_dml:
        for source in row["candidate_write_target_source_files"]:
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
            # This describes whether the checks recorded by this historical
            # probe passed for the migration set it actually applied. It does
            # not claim that the snapshot includes today's source policy.
            "scoped_acl_checks_passed": recorded_scoped_write_passed,
            "scoped_acl_summary": scoped_write if isinstance(scoped_write, dict) else None,
            "current_source_policy_coverage_observed": current_scoped_write_coverage_observed,
            "acl_snapshot_latest_migration": observed_latest_migration,
            "acl_snapshot_latest_migration_number": observed_latest_migration_number,
            "repository_latest_migration_number": repository_latest_migration,
            "current_migration_chain_observed": (
                observed_latest_migration_number is not None
                and observed_latest_migration_number == repository_latest_migration
            ),
            "service_registry_read_only_boundary_passed": (
                isinstance(scoped_write, dict)
                and type(scoped_write.get("service_registry_read_only_verified")) is int
                and scoped_write.get("service_registry_read_only_verified") == 1
            ),
            "api_key_column_boundary_passed": api_key_boundary_passed,
            "append_only_audit_ledgers_boundary_passed": append_only_boundary_passed,
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
            "relations_with_effective_truncate": sum(
                row["effective_truncate_privilege"] for row in output_rows
            ),
            "relations_with_effective_truncate_and_rls_disabled": sum(
                row["effective_truncate_privilege"] and not row["rls_enabled"]
                for row in output_rows
            ),
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
        "relations_with_effective_truncate": [
            row["relation"] for row in output_rows
            if row["effective_truncate_privilege"]
        ],
        "relations_with_effective_truncate_and_rls_disabled": [
            row["relation"] for row in output_rows
            if row["effective_truncate_privilege"] and not row["rls_enabled"]
        ],
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
