"""Regression tests for the read-only analytics runtime write inventory."""

import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = runpy.run_path(
    str(ROOT / "scripts" / "runtime-analytics-write-candidate-inventory.py"),
    run_name="runtime_analytics_write_candidate_inventory_test_module",
)


def _acl_relation(
    relation: str,
    *,
    rls_enabled: bool = False,
    source_files: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "relation": relation,
        "kind": "r",
        "has_any_dml": True,
        "rls_enabled": rls_enabled,
        "effective_privileges": {
            "select": True,
            "insert": True,
            "update": True,
            "delete": True,
        },
        "expected_runtime_boundary": None,
        "configured_runtime_boundary": None,
        "runtime_boundary_policy_matches_source": None,
        "candidate_source_files": source_files or [],
    }


def test_inventory_links_unprotected_analytics_candidate_to_exact_site():
    site = {
        "id": "services/analytics/farm.py:42:8",
        "source": "services/analytics/farm.py",
        "line": 42,
        "scope": "record_harvest",
        "method": "execute",
        "expression_kind": "literal",
        "statement_kind": "INSERT",
        "candidate_relations": ["harvest_event"],
        "write_target_relations": ["harvest_event"],
        "static_sql_sha256": "a" * 64,
        "operation_refs": ["farm.harvest.record"],
    }
    report = INVENTORY["build_inventory"](
        {
            "source_revision": "test-revision",
            "runtime_role_policy_source": {"sha256": "b" * 64},
            "relations": [
                _acl_relation(
                    "harvest_event",
                    source_files=[{
                        "path": "services/analytics/farm.py",
                        "statement_counts": {"INSERT": 1},
                    }],
                ),
                _acl_relation(
                    "verified_metrics",
                    rls_enabled=True,
                    source_files=[{
                        "path": "services/analytics/farm.py",
                        "statement_counts": {"INSERT": 1},
                    }],
                ),
                _acl_relation(
                    "other_service_table",
                    source_files=[{
                        "path": "services/agents/worker.py",
                        "statement_counts": {"INSERT": 1},
                    }],
                ),
            ],
        },
        {"version": 1, "execution_sites": [site]},
    )

    assert report["summary"]["relations"] == 1
    assert report["summary"]["candidate_sites"] == 1
    assert report["summary"]["sites_by_statement"] == {"INSERT": 1}
    row = report["relations"][0]
    assert row["relation"] == "harvest_event"
    assert row["candidate_write_sites"] == [{
        "id": site["id"],
        "path": site["source"],
        "line": 42,
        "scope": "record_harvest",
        "method": "execute",
        "statement_kind": "INSERT",
        "expression_kind": "literal",
        "static_sql_sha256": "a" * 64,
        "operation_refs": ["farm.harvest.record"],
    }]
    assert row["review_status"] == "source_and_caller_review_required"
    assert any("Do not revoke" in item for item in report["limitations"])


def test_inventory_does_not_treat_insert_select_sources_as_write_targets():
    insert_site = {
        "id": "services/analytics/advisor.py:371:4",
        "source": "services/analytics/advisor.py",
        "line": 371,
        "scope": "generate_recommendation",
        "method": "execute",
        "expression_kind": "literal",
        "statement_kind": "INSERT",
        "candidate_relations": ["advisory_recommendation", "advisory_rule"],
        "write_target_relations": ["advisory_recommendation"],
        "static_sql_sha256": "c" * 64,
        "operation_refs": [],
    }
    acl_relations = [
        _acl_relation(
            relation,
            source_files=[{
                "path": "services/analytics/advisor.py",
                "statement_counts": {"INSERT": 1},
            }],
        )
        for relation in ("advisory_recommendation", "advisory_rule")
    ]
    report = INVENTORY["build_inventory"](
        {"relations": acl_relations},
        {"execution_sites": [insert_site]},
    )

    rows = {row["relation"]: row for row in report["relations"]}
    assert rows["advisory_recommendation"]["candidate_write_sites"]
    assert rows["advisory_rule"]["candidate_write_sites"] == []
    assert rows["advisory_rule"]["review_status"] == (
        "write_target_not_confirmed_in_static_site_inventory"
    )
    assert report["summary"]["candidate_sites"] == 1
    assert report["summary"]["relations_missing_matching_sql_site"] == [
        "advisory_rule"
    ]


def test_inventory_keeps_candidate_visible_when_line_inventory_has_no_match():
    report = INVENTORY["build_inventory"](
        {
            "relations": [
                _acl_relation(
                    "unmatched_analytics_table",
                    source_files=[{
                        "path": "services/analytics/legacy.py",
                        "statement_counts": {"UPDATE": 1},
                    }],
                )
            ]
        },
        {"execution_sites": []},
    )

    assert report["summary"]["relations"] == 1
    assert report["summary"]["relations_missing_matching_sql_site"] == [
        "unmatched_analytics_table"
    ]
    assert report["relations"][0]["candidate_write_sites"] == []


@pytest.mark.parametrize(
    "acl_report,sql_inventory",
    [({}, {}), ({"relations": "invalid"}, {"execution_sites": []}),
     ({"relations": []}, {"execution_sites": "invalid"})],
)
def test_inventory_rejects_malformed_input_collections(acl_report, sql_inventory):
    with pytest.raises(ValueError, match="relation rows or SQL execution sites"):
        INVENTORY["build_inventory"](acl_report, sql_inventory)
