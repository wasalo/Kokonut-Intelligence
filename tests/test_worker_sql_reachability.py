"""SQL reachability distinguishes static graph links from import proximity."""

from __future__ import annotations

import json

from scripts.worker_function_reachability import build_inventory as build_function_graph
from scripts.worker_sql_inventory import build_inventory as build_sql_inventory
from scripts.worker_sql_reachability import ROOT, _serialize, build_inventory

INVENTORY_PATH = ROOT / "docs" / "refactor" / "worker-sql-reachability.json"


def test_saved_worker_sql_reachability_matches_current_sources():
    saved = INVENTORY_PATH.read_text(encoding="utf-8")
    assert saved == _serialize(build_inventory())
    assert json.loads(saved)["version"] == 1


def test_sql_reachability_covers_every_inventory_site_without_query_text():
    report = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    source_inventory = build_sql_inventory()
    graph = build_function_graph()
    graph_functions = {
        (function["source"], function["qualname"])
        for operation in graph["operations"]
        for function in operation["reachable_functions"]
    }
    sites = report["execution_sites"]
    source_sites = source_inventory["execution_sites"]

    assert {site["id"] for site in sites} == {site["id"] for site in source_sites}
    assert report["summary"]["operation_roots"] == len(graph["operations"])
    assert len(sites) == source_inventory["summary"]["execution_sites"]
    for site in sites:
        assert set(site["statically_reachable_operations"]) <= set(site["import_closure_operations"])
        assert site["static_link_status"] == (
            "linked" if site["statically_reachable_operations"] else "no_static_function_match"
        )
        assert site["function_in_any_worker_graph"] == ((site["source"], site["scope"]) in graph_functions)
        assert site["review_status"] == (
            "linked_to_operation"
            if site["statically_reachable_operations"]
            else "function_reachable_elsewhere_without_matching_operation"
            if site["function_in_any_worker_graph"]
            else "function_not_reached_by_any_static_worker_root"
        )
        assert "sql" not in site and "query" not in site
        if site["statically_reachable_operations"]:
            assert (ROOT / site["source"]).is_file()


def test_operation_sql_site_lists_match_per_site_reachability():
    report = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    operation_ids = {operation["operation_ref"]: set() for operation in report["operations"]}
    for site in report["execution_sites"]:
        for operation_ref in site["statically_reachable_operations"]:
            operation_ids[operation_ref].add(site["id"])

    for operation in report["operations"]:
        assert operation["statically_reachable_sql_site_ids"] == sorted(operation_ids[operation["operation_ref"]])
        assert operation["statically_reachable_sql_site_count"] == len(operation["statically_reachable_sql_site_ids"])


def test_unmatched_sites_are_not_labeled_unreachable():
    report = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    unmatched = [site for site in report["execution_sites"] if not site["statically_reachable_operations"]]

    assert unmatched
    assert all(site["static_link_status"] == "no_static_function_match" for site in unmatched)
    assert all(not site["function_in_any_worker_graph"] for site in unmatched)
    assert all(site["review_status"] == "function_not_reached_by_any_static_worker_root" for site in unmatched)
    assert report["summary"]["sites_without_static_function_match"] == len(unmatched)
    assert report["summary"]["unmatched_functions_absent_from_all_worker_graphs"] == len(unmatched)


def test_isolated_worker_persistence_sql_is_reached_through_explicit_injection():
    report = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    adapter_sources = {
        "services/ingestion/baal_worker.py",
        "services/ingestion/gnosis_worker.py",
        "services/ingestion/freshness_worker.py",
    }
    unmatched_adapters = [
        site
        for site in report["execution_sites"]
        if site["source"] in adapter_sources and not site["statically_reachable_operations"]
    ]

    assert unmatched_adapters == []


def test_metric_calculator_sql_sites_follow_the_explicit_registry_edges():
    report = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    calculator_sites = [
        site for site in report["execution_sites"] if site["source"].startswith("services/metrics/calculators/")
    ]

    assert calculator_sites
    assert all(
        "scheduled_module:services.metrics" in site["statically_reachable_operations"] for site in calculator_sites
    )
