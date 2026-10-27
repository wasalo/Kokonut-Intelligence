"""Regression tests for joining observed runtime grants to source policy."""

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTER = runpy.run_path(
    str(ROOT / "scripts" / "runtime-privilege-callsite-report.py"),
    run_name="runtime_privilege_callsite_report_test_module",
)


def _acl_row(relation: str, *, select: bool, insert: bool, update: bool, delete: bool):
    return {
        "schema": "public",
        "relation": relation,
        "kind": "r",
        "select": select,
        "insert": insert,
        "update": update,
        "delete": delete,
        "truncate": False,
        "rls_enabled": False,
        "rls_forced": False,
    }


def test_zero_grant_private_relation_stays_in_source_policy_join():
    private_relation = "ai_summary_agent_draft_request"
    mutation_relation = "ai_summary"
    scoped_policy = {
        "private_relations_expected": 79,
        "mutation_denied_relations_expected": 12,
        "private_relations_verified": 79,
        "mutation_denied_relations_verified": 12,
        "direct_table_privilege_violations": 0,
        "direct_column_privilege_violations": 0,
        "farm_activity_ledger_readable": 1,
    }
    replay = {
        "result": "passed",
        "schema_files_applied": 642,
        "schema_files_pending": 0,
        "schema_files_failed": 0,
        "seeds_applied": 0,
        "operator_scope_probe": {
            "result": "passed",
            "runtime_public_relation_acl": [
                _acl_row(
                    private_relation,
                    select=False,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    mutation_relation,
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
            ],
            "runtime_scoped_write_policy": scoped_policy,
        },
    }

    report = REPORTER["build_report"](replay, {"execution_sites": []})

    rows = {row["relation"]: row for row in report["relations"]}
    assert rows[private_relation]["effective_privileges"] == {
        "select": False,
        "insert": False,
        "update": False,
        "delete": False,
        "truncate": False,
    }
    assert rows[private_relation]["runtime_denial_policy_matches_source"] is True
    assert rows[mutation_relation]["effective_privileges"]["select"] is True
    assert rows[mutation_relation]["effective_privileges"]["insert"] is False
    assert report["summary"]["migration_revoked_relations_missing_or_mismatched_runtime_policy"] == 0
    assert report["runtime_role_acceptance"] == {
        "full_schema_replay_passed": True,
        "scoped_acl_checks_passed": True,
        "scoped_acl_summary": scoped_policy,
        "target_scope": "isolated disposable database only",
        "production_or_candidate_state_established": False,
    }


def test_source_report_does_not_claim_full_schema_role_acceptance_without_probe():
    report = REPORTER["build_report"](
        {"result": "inventory", "runtime_public_relation_acl": []},
        {"execution_sites": []},
    )

    assert report["runtime_role_acceptance"]["full_schema_replay_passed"] is False
    assert report["runtime_role_acceptance"]["scoped_acl_checks_passed"] is False
