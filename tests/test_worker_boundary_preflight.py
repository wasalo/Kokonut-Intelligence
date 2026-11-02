"""The aggregate worker preflight keeps database gates explicit and closed."""

from __future__ import annotations

import json

import pytest

from scripts.worker_boundary_preflight import ROOT, _serialize, build_preflight
from scripts.worker_function_reachability import build_inventory as build_function_graph
from scripts.worker_sql_reachability import build_inventory as build_sql_reachability
from services.security.execution_allowlist import (
    ALLOWED_EVENT_HANDLERS,
    ALLOWED_SCHEDULED_MODULES,
    ISOLATED_WORKER_ENTRYPOINTS,
    ISOLATED_WORKER_MODULES,
    SIGNED_SOURCE_FUNCTIONS,
)

REPORT_PATH = ROOT / "docs" / "refactor" / "worker-boundary-preflight.json"


@pytest.fixture(scope="module")
def report():
    return build_preflight()


def test_saved_worker_boundary_preflight_matches_current_sources(report):
    saved = REPORT_PATH.read_text(encoding="utf-8")
    assert saved == _serialize(report)
    assert json.loads(saved)["version"] == 1


def test_preflight_covers_every_worker_root_but_keeps_identity_gate_blocked(report):
    coverage = report["operation_coverage"]

    assert coverage["scheduled_allowlist_count"] == len(ALLOWED_SCHEDULED_MODULES)
    assert coverage["isolated_worker_root_count"] == len(ISOLATED_WORKER_MODULES)
    assert coverage["event_handler_allowlist_count"] == len(ALLOWED_EVENT_HANDLERS)
    assert coverage["signed_source_function_count"] == len(SIGNED_SOURCE_FUNCTIONS)
    assert coverage["expected_operation_count"] == (
        len(ALLOWED_SCHEDULED_MODULES)
        + len(ISOLATED_WORKER_MODULES)
        + len(SIGNED_SOURCE_FUNCTIONS)
        + len(ALLOWED_EVENT_HANDLERS)
    )
    assert "services.events.notification_delivery_worker" in ISOLATED_WORKER_MODULES
    assert "services.events.notification_delivery_worker" not in ALLOWED_SCHEDULED_MODULES
    assert "services.agents.worker_cli" in ISOLATED_WORKER_MODULES
    assert "services.agents.worker_cli" not in ALLOWED_SCHEDULED_MODULES
    assert "services.export.report_snapshot_export_worker" in ISOLATED_WORKER_MODULES
    assert "services.export.report_snapshot_export_worker" not in ALLOWED_SCHEDULED_MODULES
    assert set(ISOLATED_WORKER_ENTRYPOINTS) == set(ISOLATED_WORKER_MODULES)
    assert coverage["missing_source_closure_operations"] == []
    assert coverage["missing_function_graph_operations"] == []
    assert coverage["unresolved_function_roots"] == 0
    assert coverage["passed"] is True
    assert report["source_closure"]["dynamic_import_site_count"] == 4
    assert report["source_closure"]["passed"] is True
    assert report["worker_identity"]["signed_tenant_context_established_by_dispatch"] is False
    assert report["worker_identity"]["unbound_operation_root_count"] == (
        coverage["expected_operation_count"] - len(SIGNED_SOURCE_FUNCTIONS)
    )
    assert report["worker_identity"]["signed_source_function_roots_establish_context_in_function"] == len(
        SIGNED_SOURCE_FUNCTIONS
    )
    assert report["worker_identity"]["status"] == "not_tenant_bound"
    assert report["status"] == "review_required"
    assert any("code-allowlisted scheduled sensor-driver dispatch" in item for item in report["limitations"])


def test_isolated_delivery_worker_is_traced_without_becoming_schedulable():
    operation = next(
        item
        for item in build_function_graph()["operations"]
        if item["kind"] == "isolated_worker"
        and item["name"] == "services.events.notification_delivery_worker"
    )
    assert [entry["function"] for entry in operation["entry_functions"]] == [
        "services.events.notification_delivery_worker:run_once"
    ]
    assert any(
        function["qualname"] == "_claim"
        for function in operation["reachable_functions"]
    )
    assert any(
        function["qualname"] == "_finish"
        for function in operation["reachable_functions"]
    )


def test_report_snapshot_export_worker_is_traced_as_an_isolated_entrypoint():
    operation = next(
        item
        for item in build_function_graph()["operations"]
        if item["kind"] == "isolated_worker"
        and item["name"] == "services.export.report_snapshot_export_worker"
    )
    assert [entry["function"] for entry in operation["entry_functions"]] == [
        "services.export.report_snapshot_export_worker:run_once"
    ]
    reachable = {function["qualname"] for function in operation["reachable_functions"]}
    assert {"_claim", "_read_source", "_process_claim", "_finish"} <= reachable


def test_preflight_lists_unmatched_sql_without_query_text_or_database_claims(report):
    sql = report["sql_reachability"]

    summary = build_sql_reachability()["summary"]
    assert sql["execution_site_count"] == summary["sql_execution_sites"]
    assert sql["sites_with_static_operation_path"] == summary["unique_sites_with_static_operation_path"]
    assert sql["sites_without_static_function_match"] == summary["sites_without_static_function_match"]
    assert sql["static_effects_complete"] is False
    assert all(
        site["review_status"] == "function_not_reached_by_any_static_worker_root"
        for site in sql["site_refs_for_review"]
    )
    assert all(
        set(site) == {"site", "review_status", "import_closure_operation_count"} for site in sql["site_refs_for_review"]
    )
    assert set(report["database_checks"].values()) == {"not_assessed", "not_ready"}
    assert "sql_text" not in json.dumps(sql)
