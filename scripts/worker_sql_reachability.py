#!/usr/bin/env python3
"""Join direct SQL execution sites to the conservative worker call graph.

The report distinguishes source-import closure membership from a direct,
statically resolved function path. A SQL site without a static path is not
proved dead: dynamic dispatch, callbacks, import-time work, and unknown object
methods may still reach it. No SQL text or runtime values are copied.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.worker_function_reachability as worker_function_reachability  # noqa: E402
import scripts.worker_sql_inventory as worker_sql_inventory  # noqa: E402


def build_inventory(function_graph: dict | None = None, sql_inventory: dict | None = None) -> dict:
    function_graph = function_graph or worker_function_reachability.build_inventory()
    sql_inventory = sql_inventory or worker_sql_inventory.build_inventory()
    operation_functions: dict[str, set[tuple[str, str]]] = {}
    operation_site_ids: dict[str, set[str]] = {}
    all_graph_functions: set[tuple[str, str]] = set()
    for operation in function_graph["operations"]:
        reference = f"{operation['kind']}:{operation['name']}"
        operation_functions[reference] = {
            (function["source"], function["qualname"]) for function in operation["reachable_functions"]
        }
        all_graph_functions.update(operation_functions[reference])
        operation_site_ids[reference] = set()

    sites = []
    for site in sql_inventory["execution_sites"]:
        matched_operations = sorted(
            reference
            for reference, functions in operation_functions.items()
            if (site["source"], site["scope"]) in functions
        )
        for reference in matched_operations:
            operation_site_ids[reference].add(site["id"])
        in_any_graph = (site["source"], site["scope"]) in all_graph_functions
        sites.append(
            {
                "id": site["id"],
                "source": site["source"],
                "line": site["line"],
                "scope": site["scope"],
                "method": site["method"],
                "expression_kind": site["expression_kind"],
                "statement_kind": site["statement_kind"],
                "candidate_relations": site["candidate_relations"],
                "import_closure_operations": site["operation_refs"],
                "statically_reachable_operations": matched_operations,
                "static_link_status": "linked" if matched_operations else "no_static_function_match",
                "function_in_any_worker_graph": in_any_graph,
                "review_status": (
                    "linked_to_operation"
                    if matched_operations
                    else "function_reachable_elsewhere_without_matching_operation"
                    if in_any_graph
                    else "function_not_reached_by_any_static_worker_root"
                ),
            }
        )

    operation_records = [
        {
            "kind": operation["kind"],
            "name": operation["name"],
            "operation_ref": f"{operation['kind']}:{operation['name']}",
            "statically_reachable_sql_site_count": len(operation_site_ids[f"{operation['kind']}:{operation['name']}"]),
            "statically_reachable_sql_site_ids": sorted(operation_site_ids[f"{operation['kind']}:{operation['name']}"]),
        }
        for operation in function_graph["operations"]
    ]
    linked = [site for site in sites if site["statically_reachable_operations"]]
    return {
        "version": 1,
        "generated_by": "scripts/worker_sql_reachability.py",
        "scope": (
            "Direct SQL execution sites joined to the statically resolved worker function graph. "
            "A missing graph edge does not prove code is unreachable; dynamic dispatch, callbacks, "
            "import-time work, and methods on unknown instances may reach a site. This is not a "
            "complete effect map, ACL, authorization policy, or least-privilege grant list."
        ),
        "summary": {
            "operation_roots": len(operation_records),
            "sql_execution_sites": len(sites),
            "statically_reachable_site_memberships": sum(
                len(site["statically_reachable_operations"]) for site in sites
            ),
            "unique_sites_with_static_operation_path": len(linked),
            "sites_without_static_function_match": len(sites) - len(linked),
            "unmatched_functions_absent_from_all_worker_graphs": sum(
                not site["function_in_any_worker_graph"]
                for site in sites
                if not site["statically_reachable_operations"]
            ),
            "sites_reached_by_multiple_operations": sum(
                len(site["statically_reachable_operations"]) > 1 for site in sites
            ),
        },
        "operations": operation_records,
        "execution_sites": sites,
    }


def _serialize(value: dict) -> str:
    return json.dumps(value, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write the generated reachability report")
    group.add_argument("--check", type=Path, help="Fail if the saved report is stale")
    args = parser.parse_args(argv)
    expected = _serialize(build_inventory())

    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(expected, encoding="utf-8")
        return 0

    check = args.check if args.check.is_absolute() else ROOT / args.check
    try:
        actual = check.read_text(encoding="utf-8")
    except OSError:
        print(f"Missing worker SQL reachability report: {check}", file=sys.stderr)
        return 1
    if actual != expected:
        print(f"Worker SQL reachability report is stale: {check}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
