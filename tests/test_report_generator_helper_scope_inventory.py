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
    _query_forwarder_execute_lines,
    _resolve_call_target,
    _resolve_function_cached,
    build_inventory,
)
from report_generator_query_scope_inventory import (  # noqa: E402
    build_inventory as build_report_query_inventory,
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


def test_shared_query_adapter_is_only_excluded_when_it_forwards_sql_unchanged():
    source_path = ROOT / "services/common/database.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    query = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "query"
    )

    assert _query_forwarder_execute_lines(source_path, query) == [77, 80]

    changed_tree = ast.parse(
        """
def query(conn, sql, params=None):
    sql = f"SELECT * FROM {sql}"
    conn.execute(sql, params)
"""
    )
    changed_query = next(
        node for node in changed_tree.body if isinstance(node, ast.FunctionDef)
    )
    assert _query_forwarder_execute_lines(source_path, changed_query) is None


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


def test_query_forwarding_wrappers_link_to_report_or_helper_call_sites():
    inventory = build_inventory()
    direct_inventory = build_report_query_inventory()
    reports = {
        report["report_type"]: report
        for report in inventory["reports"]
        if report["report_type"] in {
            "bio_regional_input",
            "climate_impact",
            "open_source_impact",
        }
    }

    assert set(reports) == {"bio_regional_input", "climate_impact", "open_source_impact"}
    for report in reports.values():
        assert len(report["forwarded_query_wrappers"]) == 1
        wrapper = report["forwarded_query_wrappers"][0]
        assert wrapper["source_file"] == "services/common/database.py"
        assert wrapper["callable"] == "query"
        assert wrapper["execution_lines"] == [77, 80]
        assert wrapper["caller_sites"]
        assert not any(
            site["source_file"] == "services/common/database.py"
            for site in report["reachable_helper_query_sites"]
        )
    assert inventory["summary"]["reports_with_forwarded_query_wrappers"] == 3
    assert inventory["summary"]["forwarded_query_wrapper_caller_sites"] == 4
    assert inventory["summary"]["helper_query_sites_with_unresolved_sql_source"] == 0
    direct_reports = {
        report["report_type"]: report
        for report in direct_inventory["reports"]
    }
    for report_type, expected_relation in {
        "bio_regional_input": "v_public_bio_regional_input_summary",
        "open_source_impact": "v_public_open_source_impact_artifact",
    }.items():
        callsite = next(
            site
            for site in direct_reports[report_type]["queries"]
            if expected_relation in site["relations"]
        )
        assert callsite["sql_source"] == "static_or_resolved"
    climate_report = reports["climate_impact"]
    climate_helper_callsites = [
        site
        for site in climate_report["reachable_helper_query_sites"]
        if site["source_file"] == "services/analytics/carbon_balance.py"
        and site["callable"] in {"compute_tree_carbon", "compute_regenerative_score"}
    ]
    assert {site["callable"] for site in climate_helper_callsites} == {
        "compute_tree_carbon",
        "compute_regenerative_score",
    }
    assert all(site["sql_source"] == "static_or_resolved" for site in climate_helper_callsites)


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
    value_stream_sites = [
        site
        for site in static_sites
        if site["source_file"] == "services/analytics/value_stream.py"
        and site["callable"] in {"stage_lead_times", "first_time_through"}
    ]
    assert len(static_sites) == 8
    assert len(value_stream_sites) == 6
    assert all(not site["named_bind_contract"]["mismatch"] for site in value_stream_sites)
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


def test_value_stream_pipeline_queries_have_static_sql_and_location_bind_contracts():
    inventory = build_inventory()
    report_types = {"business_plan", "process_health", "value_stream_map"}
    expected_callables = {"wip_by_stage", "stage_lead_times", "first_time_through"}

    for report in inventory["reports"]:
        if report["report_type"] not in report_types:
            continue
        queries = [
            site
            for site in report["reachable_helper_query_sites"]
            if site["source_file"] == "services/analytics/value_stream.py"
            and site["callable"] in expected_callables
        ]
        assert {site["callable"] for site in queries} == expected_callables
        for site in queries:
            assert site["sql_source"] == "static_or_resolved"
            assert site["bound_location_scope_signal"] is True
            if site["callable"] == "wip_by_stage":
                assert site["positional_bind_arity"] == {
                    "placeholder_count": 1,
                    "supplied_count": 1,
                    "mismatch": False,
                }
            else:
                assert site["named_bind_contract"]["mismatch"] is False


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


def test_business_plan_listing_query_has_static_positional_bind_contract():
    inventory = build_inventory()
    report = next(item for item in inventory["reports"] if item["report_type"] == "business_plan")
    query = next(
        site
        for site in report["reachable_helper_query_sites"]
        if site["source_file"] == "services/planning/budget.py"
        and site["callable"] == "list_plans"
    )

    assert query["sql_source"] == "static_or_resolved"
    assert query["positional_bind_arity"] == {
        "placeholder_count": 3,
        "supplied_count": 3,
        "mismatch": False,
    }
    assert query["bound_location_scope_signal"] is False


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
        assert site["bound_location_scope_signal"] is True
        assert site["location_scope_conditionally_added"] is True
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
        assert [
            item["bound_location_scope_signal"]
            for item in site["location_scope_variants"]
        ] == [True, False, False]


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

