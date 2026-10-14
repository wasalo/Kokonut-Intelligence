"""The aggregate worker preflight keeps database gates explicit and closed."""

from __future__ import annotations

import json

import pytest

from scripts.worker_boundary_preflight import ROOT, _serialize, build_preflight

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

    assert coverage["scheduled_allowlist_count"] == 12
    assert coverage["event_handler_allowlist_count"] == 5
    assert coverage["expected_operation_count"] == 17
    assert coverage["missing_source_closure_operations"] == []
    assert coverage["missing_function_graph_operations"] == []
    assert coverage["unresolved_function_roots"] == 0
    assert coverage["passed"] is True
    assert report["source_closure"]["known_allowlisted_dynamic_import_site_count"] == 1
    assert report["source_closure"]["passed"] is True
    assert report["worker_identity"]["signed_tenant_context_established_by_dispatch"] is False
    assert report["worker_identity"]["unbound_operation_root_count"] == 17
    assert report["worker_identity"]["status"] == "not_tenant_bound"
    assert report["status"] == "review_required"


def test_preflight_lists_unmatched_sql_without_query_text_or_database_claims(report):
    sql = report["sql_reachability"]

    assert sql["execution_site_count"] == 196
    assert sql["sites_with_static_operation_path"] == 175
    assert sql["sites_without_static_function_match"] == 21
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
