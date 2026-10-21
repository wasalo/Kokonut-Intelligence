"""Source-only tests for report helper query tracing."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report_generator_helper_scope_inventory import (  # noqa: E402
    _absolute_import_module,
    _import_bindings,
    _resolve_call_target,
    _resolve_function_cached,
    build_inventory,
)


def test_report_relative_import_resolves_to_services_analytics():
    source_path = ROOT / "services/export/reports/strategy.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "generate_capability_dashboard"
    )
    module = "services.export.reports.strategy"
    bindings = _import_bindings(module, tree, function)
    call = next(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "get_capability_dashboard"
    )

    assert _absolute_import_module(module, 3, "analytics.capability_map") == (
        "services.analytics.capability_map"
    )
    assert _resolve_call_target(call, module, bindings) == (
        "services.analytics.capability_map",
        "get_capability_dashboard",
    )


def test_report_serializer_alias_resolves_without_importing_services():
    resolved = _resolve_function_cached("services.export.reports.core", "_serialize_rows")

    assert resolved is not None
    source_path, function = resolved
    assert source_path == ROOT / "services/common/utils.py"
    assert function.name == "serialize_rows"


def test_reachable_helper_queries_inventory_static_positional_bind_arity():
    inventory = build_inventory()
    summary = inventory["summary"]
    query_sites = [
        site
        for report in inventory["reports"]
        for site in report["reachable_helper_query_sites"]
    ]
    static_sites = [
        site for site in query_sites if site["positional_bind_arity"] is not None
    ]
    mismatches = [
        site
        for site in static_sites
        if site["positional_bind_arity"]["mismatch"]
    ]

    assert summary["reachable_helper_query_sites_per_report"] == len(query_sites)
    assert summary["helper_query_sites_with_static_positional_arity"] == len(static_sites)
    assert summary["helper_query_sites_with_positional_arity_mismatch"] == len(mismatches)
    assert static_sites
    assert not mismatches

