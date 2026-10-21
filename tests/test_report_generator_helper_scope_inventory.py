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


def test_reachable_helper_queries_inventory_static_named_bind_contracts():
    inventory = build_inventory()
    summary = inventory["summary"]
    query_sites = [
        site
        for report in inventory["reports"]
        for site in report["reachable_helper_query_sites"]
    ]
    static_sites = [
        site for site in query_sites if site["named_bind_contract"] is not None
    ]
    mismatches = [
        site for site in static_sites if site["named_bind_contract"]["mismatch"]
    ]
    reference_class_sites = {
        site["line"]: site["named_bind_contract"]
        for site in static_sites
        if site["source_file"] == "services/forecast/reference_class.py"
    }

    assert summary["helper_query_sites_with_static_named_bind_contract"] == len(static_sites)
    assert summary["helper_query_sites_with_named_bind_contract_mismatch"] == len(mismatches)
    assert len(static_sites) == 2
    assert not mismatches
    assert reference_class_sites[35]["required_names"] == ["loc", "metric"]
    assert reference_class_sites[35]["supplied_names"] == ["loc", "metric"]
    assert reference_class_sites[50]["required_names"] == ["loc"]
    assert reference_class_sites[50]["supplied_names"] == ["loc"]
    assert summary["helper_query_sites_with_static_sql_source"] == sum(
        site["sql_source"] == "static_or_resolved" for site in query_sites
    )
    assert summary["helper_query_sites_with_unresolved_sql_source"] == sum(
        site["sql_source"] != "static_or_resolved" for site in query_sites
    )


def test_reachable_helper_queries_resolve_literal_module_sql_constants():
    inventory = build_inventory()
    business_plan = next(
        report for report in inventory["reports"] if report["report_type"] == "business_plan"
    )
    marketplace_queries = [
        site
        for site in business_plan["reachable_helper_query_sites"]
        if site["source_file"] == "services/analytics/marketplace.py"
        and site["callable"] == "get_market_overview"
    ]
    listing_queries = [
        site for site in marketplace_queries if "market_listing" in site["relations"]
    ]

    assert len(marketplace_queries) == 4
    assert all(site["sql_source"] == "static_or_resolved" for site in marketplace_queries)
    assert len(listing_queries) == 3
    assert all(site["bound_location_scope_signal"] for site in listing_queries)
    assert all(site["positional_bind_arity"]["mismatch"] is False for site in marketplace_queries)


def test_reachable_helper_queries_correlate_optional_filter_bind_variants():
    inventory = build_inventory()
    for report_type in {"business_plan", "strategy_execution"}:
        report = next(
            item for item in inventory["reports"] if item["report_type"] == report_type
        )
        queries = [
            site
            for site in report["reachable_helper_query_sites"]
            if site["source_file"] == "services/analytics/strategy_execution.py"
            and site["callable"] == "dashboard"
        ]

        assert len(queries) == 1
        assert queries[0]["sql_source"] == "static_or_resolved"
        assert queries[0]["positional_bind_arity"]["mismatch"] is False
        assert len(queries[0]["positional_bind_arity"]["variants"]) == 8


def test_reachable_helper_query_wrapper_uses_all_literal_local_callsites():
    inventory = build_inventory()
    report = next(item for item in inventory["reports"] if item["report_type"] == "business_plan")
    query = next(
        site
        for site in report["reachable_helper_query_sites"]
        if site["source_file"] == "services/planning/sandop.py"
        and site["callable"] == "_rows"
    )

    assert query["sql_source"] == "static_or_resolved"
    assert query["bound_location_scope_signal"] is False
    assert query["positional_bind_arity"]["mismatch"] is False
    assert [
        (variant["call_site_line"], variant["placeholder_count"], variant["supplied_count"])
        for variant in query["positional_bind_arity"]["variants"]
    ] == [(29, 1, 1), (43, 1, 1), (55, 1, 1)]


def test_reachable_helper_inventory_resolves_fail_closed_org_location_filter_pairs():
    inventory = build_inventory()
    targets = {
        ("business_model_canvas", "services/analytics/business_model_canvas.py", "list_canvas"),
        ("business_plan", "services/analytics/swot.py", "list_swot"),
    }
    found = set()
    for report in inventory["reports"]:
        for site in report["reachable_helper_query_sites"]:
            key = (report["report_type"], site["source_file"], site["callable"])
            if key not in targets:
                continue
            found.add(key)
            assert site["sql_source"] == "static_or_resolved"
            assert site["positional_bind_arity"]["mismatch"] is False
            assert [
                (item["placeholder_count"], item["supplied_count"])
                for item in site["positional_bind_arity"]["variants"]
            ] == [(1, 1), (1, 1)]
            # Resolving a location predicate is not proof that the parameter
            # is an authorization context or that every branch is tenant-safe.
            assert site["bound_location_scope_signal"] is False
    assert found == targets


def test_reachable_helper_inventory_resolves_literal_filter_return_variants():
    inventory = build_inventory()
    report = next(item for item in inventory["reports"] if item["report_type"] == "business_plan")
    queries = [
        site
        for site in report["reachable_helper_query_sites"]
        if site["source_file"] == "services/analytics/swot.py"
        and site["callable"] == "suggest"
    ]

    assert [site["line"] for site in queries] == [107, 126, 144]
    for site in queries:
        assert site["sql_source"] == "static_or_resolved"
        assert site["bound_location_scope_signal"] is False
        assert site["positional_bind_arity"] == {
            "mismatch": False,
            "variants": [
                {
                    "helper_return_line": 82,
                    "placeholder_count": 1,
                    "supplied_count": 1,
                    "mismatch": False,
                },
                {
                    "helper_return_line": 88,
                    "placeholder_count": 0,
                    "supplied_count": 0,
                    "mismatch": False,
                },
                {
                    "helper_return_line": 89,
                    "placeholder_count": 1,
                    "supplied_count": 1,
                    "mismatch": False,
                },
            ],
        }


def test_reachable_helper_inventory_resolves_public_view_wrapper_identifiers():
    inventory = build_inventory()
    expected_reports = {
        "anti_capture_governance",
        "redistribution_policy",
        "federation_mutual_aid",
        "algorithmic_redistribution",
        "participatory_signal",
    }
    found = set()
    for report in inventory["reports"]:
        queries = [
            site
            for site in report["reachable_helper_query_sites"]
            if site["source_file"] == "services/export/reports/commons/kokonut.py"
            and site["callable"] == "_fetch_public_view"
        ]
        if not queries:
            continue
        found.add(report["report_type"])
        assert [site["line"] for site in queries] == [25, 30]
        for site in queries:
            assert site["sql_source"] == "static_or_resolved"
            assert site["bound_location_scope_signal"] is False
            assert site["positional_bind_arity"]["mismatch"] is False
            assert len(site["positional_bind_arity"]["variants"]) == 5
            assert {
                item["caller"] for item in site["positional_bind_arity"]["variants"]
            } == {
                "generate_anti_capture_governance",
                "generate_redistribution_policy",
                "generate_federation_mutual_aid",
                "generate_algorithmic_redistribution",
                "generate_participatory_signal",
            }
        location_query = queries[0]
        network_query = queries[1]
        assert all(
            item["placeholder_count"] == item["supplied_count"] == 1
            for item in location_query["positional_bind_arity"]["variants"]
        )
        assert all(
            item["placeholder_count"] == item["supplied_count"] == 0
            for item in network_query["positional_bind_arity"]["variants"]
        )
    assert found == expected_reports

