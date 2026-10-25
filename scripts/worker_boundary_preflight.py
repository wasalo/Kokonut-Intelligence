#!/usr/bin/env python3
"""Build an aggregate-only static preflight for worker tenant-boundary work.

This report reads source inventories only. It does not connect to PostgreSQL,
read secrets, or establish database-role, migration, or ownership readiness.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.worker_function_reachability as worker_function_reachability  # noqa: E402
import scripts.worker_source_closure as worker_source_closure  # noqa: E402
import scripts.worker_sql_inventory as worker_sql_inventory  # noqa: E402
import scripts.worker_sql_reachability as worker_sql_reachability  # noqa: E402
from services.security.execution_allowlist import (  # noqa: E402
    ALLOWED_EVENT_HANDLERS,
    ALLOWED_SCHEDULED_MODULES,
)


def _operation_ref(operation: dict) -> str:
    return f"{operation['kind']}:{operation['name']}"


def build_preflight() -> dict:
    source_closure = worker_source_closure.build_inventory()
    function_graph = worker_function_reachability.build_inventory()
    sql_inventory = worker_sql_inventory.build_inventory()
    sql_reachability = worker_sql_reachability.build_inventory(function_graph, sql_inventory)

    expected_operations = {
        *(f"scheduled_module:{module}" for module in ALLOWED_SCHEDULED_MODULES),
        *(f"event_handler:{module}.{function}" for module, function in ALLOWED_EVENT_HANDLERS),
    }
    function_operations = {_operation_ref(operation): operation for operation in function_graph["operations"]}
    closure_operations = {_operation_ref(operation): operation for operation in source_closure["operations"]}
    missing_function_operations = sorted(expected_operations - function_operations.keys())
    missing_closure_operations = sorted(expected_operations - closure_operations.keys())
    unresolved_module_count = sum(
        len(operation["unresolved_local_modules"]) for operation in source_closure["operations"]
    )
    dynamic_import_sites = {
        (site["source"], site["line"], site["kind"])
        for operation in source_closure["operations"]
        for site in operation["dynamic_import_sites"]
    }
    unresolved_roots = function_graph["summary"]["operations_without_resolved_entry_functions"]

    unmatched_sites = [
        {
            "site": site["id"],
            "review_status": site["review_status"],
            "import_closure_operation_count": len(site["import_closure_operations"]),
        }
        for site in sql_reachability["execution_sites"]
        if not site["statically_reachable_operations"]
    ]
    unmatched_sites.sort(key=lambda site: site["site"])

    source_coverage_passes = not missing_closure_operations and unresolved_module_count == 0
    operation_roots_pass = not missing_function_operations and unresolved_roots == 0
    identity_bound = False
    static_effects_complete = not unmatched_sites
    static_status = (
        "ready_for_database_preflight"
        if source_coverage_passes and operation_roots_pass and identity_bound and static_effects_complete
        else "review_required"
    )

    return {
        "version": 1,
        "generated_by": "scripts/worker_boundary_preflight.py",
        "scope": (
            "Static source preflight only. It does not connect to a database or inspect live role grants, "
            "applied migrations, enabled schedules, tenant ownership, or external dispatchers."
        ),
        "status": static_status,
        "operation_coverage": {
            "scheduled_allowlist_count": len(ALLOWED_SCHEDULED_MODULES),
            "event_handler_allowlist_count": len(ALLOWED_EVENT_HANDLERS),
            "expected_operation_count": len(expected_operations),
            "source_closure_operation_count": len(closure_operations),
            "function_graph_operation_count": len(function_operations),
            "missing_source_closure_operations": missing_closure_operations,
            "missing_function_graph_operations": missing_function_operations,
            "unresolved_function_roots": unresolved_roots,
            "passed": source_coverage_passes and operation_roots_pass,
        },
        "source_closure": {
            "source_file_count": len(
                {source for operation in source_closure["operations"] for source in operation["source_files"]}
            ),
            "unresolved_local_module_count": unresolved_module_count,
            "dynamic_import_site_count": len(dynamic_import_sites),
            "passed": source_coverage_passes,
        },
        "worker_identity": {
            "database_identity": "shared_configured_runtime_identity",
            "signed_tenant_context_established_by_dispatch": False,
            "unbound_operation_root_count": len(expected_operations),
            "status": "not_tenant_bound",
        },
        "sql_reachability": {
            "execution_site_count": sql_inventory["summary"]["execution_sites"],
            "sites_with_static_operation_path": sql_reachability["summary"]["unique_sites_with_static_operation_path"],
            "sites_without_static_function_match": len(unmatched_sites),
            "site_refs_for_review": unmatched_sites,
            "static_effects_complete": static_effects_complete,
        },
        "database_checks": {
            "runtime_role_attributes_and_grants": "not_assessed",
            "migration_prerequisites_and_drift": "not_assessed",
            "pending_tenant_ownership_mappings": "not_assessed",
            "active_persisted_schedule_contracts": "not_assessed",
            "rls_readiness": "not_ready",
        },
        "limitations": [
            "A SQL site outside the current worker-root graph is not proven dead or unreachable.",
            "The EventBus handler dispatch and code-allowlisted scheduled sensor-driver dispatch are represented in source inventories; the legacy data-selected driver loader and other dynamic callbacks remain open.",
            "This static report is not a database ACL, tenant policy, or authorization decision.",
            "No database, migration, or secret was accessed.",
        ],
    }


def _serialize(value: dict) -> str:
    return json.dumps(value, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write the static preflight report")
    group.add_argument("--check", type=Path, help="Fail if the saved report is stale")
    args = parser.parse_args(argv)
    expected = _serialize(build_preflight())

    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(expected, encoding="utf-8")
        return 0

    check = args.check if args.check.is_absolute() else ROOT / args.check
    try:
        actual = check.read_text(encoding="utf-8")
    except OSError:
        print(f"Missing worker boundary preflight report: {check}", file=sys.stderr)
        return 1
    if actual != expected:
        print(f"Worker boundary preflight report is stale: {check}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
