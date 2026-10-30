"""Regression tests for joining observed runtime grants to source policy."""

import runpy
from pathlib import Path

from services.migration import runtime_role

ROOT = Path(__file__).resolve().parents[1]
REPORTER = runpy.run_path(
    str(ROOT / "scripts" / "runtime-privilege-callsite-report.py"),
    run_name="runtime_privilege_callsite_report_test_module",
)


def test_reporting_registry_dynamic_revokes_are_joined_to_runtime_policy():
    overrides = REPORTER["_SOURCE_REVOKE_POLICY_OVERRIDES"]

    assert overrides["gri_indicator"] == "runtime_mutations_denied"
    assert overrides["governance_framework"] == "runtime_mutations_denied"
    assert overrides["impact_framework"] == "runtime_mutations_denied"
    assert overrides["impact_dimension"] == "runtime_mutations_denied"
    assert overrides["expense_category"] == "runtime_mutations_denied"
    assert overrides["dfs_currency"] == "runtime_mutations_denied"
    assert overrides["crop_gdd_config"] == "runtime_mutations_denied"
    assert overrides["pest_degree_day_config"] == "runtime_mutations_denied"
    assert overrides["revenue_multiplier_config"] == "runtime_mutations_denied"
    assert overrides["farmer_credential_type"] == "runtime_mutations_denied"
    assert overrides["metric_definition"] == "runtime_mutations_denied"
    assert overrides["service_registry"] == "runtime_mutations_denied"


def _acl_row(
    relation: str,
    *,
    select: bool,
    insert: bool,
    update: bool,
    delete: bool,
    truncate: bool = False,
):
    return {
        "schema": "public",
        "relation": relation,
        "kind": "r",
        "select": select,
        "insert": insert,
        "update": update,
        "delete": delete,
        "truncate": truncate,
        "rls_enabled": False,
        "rls_forced": False,
    }


def test_zero_grant_private_relation_stays_in_source_policy_join():
    private_relation = "ai_summary_agent_draft_request"
    mutation_relation = "ai_summary"
    mutation_relation_count = len(runtime_role._RUNTIME_MUTATION_TABLES)
    scoped_policy = {
        "private_relations_expected": 79,
        "mutation_denied_relations_expected": mutation_relation_count,
        "private_relations_verified": 79,
        "mutation_denied_relations_verified": mutation_relation_count,
        "direct_table_privilege_violations": 0,
        "direct_column_privilege_violations": 0,
        "farm_activity_ledger_readable": 1,
        "service_registry_read_only_verified": 1,
        "append_only_relations_expected": 2,
        "append_only_relations_verified": 2,
        "append_only_select_insert_verified": 2,
        "append_only_mutations_denied": 2,
        "append_only_column_grants_denied": 2,
    }
    replay = {
        "result": "passed",
        "schema_files_applied": len(list((ROOT / "schemas/postgres").glob("*.sql"))),
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
                _acl_row(
                    "advisory_rule",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "crop_family",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "crop_nutrient_removal_factor",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "certification_type",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "cooperative_type",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "dfs_insurance_product_type",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "evidence_maturity_level",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "sensor_type",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "graph_node_type",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "graph_edge_type",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "waste_type",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "disposal_method",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "access_audit_log",
                    select=True,
                    insert=True,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "agent_action_log",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "carbon_benchmark",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "reference_class",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "service_registry",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
                _acl_row(
                    "yield_benchmark",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                ),
            ],
            "runtime_scoped_write_policy": scoped_policy,
            "runtime_append_only_policy": {
                "relations_expected": 2,
                "relations_verified": 2,
                "select_insert_verified": 2,
                "mutations_denied": 2,
                "column_grants_denied": 2,
                "verified_by_provisioner": True,
            },
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
    assert rows[private_relation]["runtime_boundary_policy_matches_source"] is True
    assert rows[mutation_relation]["effective_privileges"]["select"] is True
    assert rows[mutation_relation]["effective_privileges"]["insert"] is False
    assert rows["advisory_rule"]["expected_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["advisory_rule"]["configured_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["advisory_rule"]["runtime_boundary_policy_matches_source"] is True
    assert rows["crop_family"]["expected_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["crop_family"]["configured_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["crop_family"]["runtime_boundary_policy_matches_source"] is True
    assert rows["crop_nutrient_removal_factor"]["expected_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["crop_nutrient_removal_factor"]["configured_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["crop_nutrient_removal_factor"]["runtime_boundary_policy_matches_source"] is True
    assert rows["certification_type"]["expected_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["certification_type"]["configured_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["certification_type"]["runtime_boundary_policy_matches_source"] is True
    for relation in ("cooperative_type", "dfs_insurance_product_type"):
        assert rows[relation]["expected_runtime_boundary"] == "runtime_mutations_denied"
        assert rows[relation]["configured_runtime_boundary"] == "runtime_mutations_denied"
        assert rows[relation]["runtime_boundary_policy_matches_source"] is True
    assert rows["evidence_maturity_level"]["expected_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["evidence_maturity_level"]["configured_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["evidence_maturity_level"]["runtime_boundary_policy_matches_source"] is True
    assert rows["sensor_type"]["expected_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["sensor_type"]["configured_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["sensor_type"]["runtime_boundary_policy_matches_source"] is True
    for relation in ("waste_type", "disposal_method"):
        assert rows[relation]["expected_runtime_boundary"] == "runtime_mutations_denied"
        assert rows[relation]["configured_runtime_boundary"] == "runtime_mutations_denied"
        assert rows[relation]["runtime_boundary_policy_matches_source"] is True
    for relation in ("graph_node_type", "graph_edge_type"):
        assert rows[relation]["expected_runtime_boundary"] == "runtime_mutations_denied"
        assert rows[relation]["configured_runtime_boundary"] == "runtime_mutations_denied"
        assert rows[relation]["runtime_boundary_policy_matches_source"] is True
    assert rows["access_audit_log"]["expected_runtime_boundary"] == "runtime_append_only_read_insert"
    assert rows["access_audit_log"]["configured_runtime_boundary"] == "runtime_append_only_read_insert"
    assert rows["access_audit_log"]["runtime_boundary_policy_matches_source"] is True
    assert rows["agent_action_log"]["expected_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["agent_action_log"]["configured_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["agent_action_log"]["runtime_boundary_policy_matches_source"] is True
    assert rows["carbon_benchmark"]["expected_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["carbon_benchmark"]["configured_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["carbon_benchmark"]["runtime_boundary_policy_matches_source"] is True
    assert rows["reference_class"]["expected_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["reference_class"]["configured_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["reference_class"]["runtime_boundary_policy_matches_source"] is True
    assert rows["service_registry"]["expected_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["service_registry"]["configured_runtime_boundary"] == "runtime_mutations_denied"
    assert rows["service_registry"]["runtime_boundary_policy_matches_source"] is True
    assert report["summary"]["migration_revoked_relations_missing_or_mismatched_runtime_policy"] == 0
    assert report["runtime_role_acceptance"] == {
        "full_schema_replay_passed": True,
        "scoped_acl_checks_passed": True,
        "scoped_acl_summary": scoped_policy,
        "current_source_policy_coverage_observed": True,
        "acl_snapshot_latest_migration": None,
        "acl_snapshot_latest_migration_number": None,
        "repository_latest_migration_number": max(
            int(path.name.split("_", 1)[0])
            for path in (ROOT / "schemas/postgres").glob("*.sql")
        ),
        "current_migration_chain_observed": False,
        "api_key_column_boundary_passed": False,
        "service_registry_read_only_boundary_passed": True,
        "append_only_audit_ledgers_boundary_passed": True,
        "target_scope": "isolated disposable database only",
        "production_or_candidate_state_established": False,
    }


def test_api_key_revocation_matches_read_only_column_allowlist_boundary():
    api_key_policy = {
        "select_columns": [
            "id", "key_hash", "key_prefix", "role_id", "scopes", "expires_at", "is_active"
        ],
        "insert_columns": [],
        "update_columns": [],
        "delete": False,
        "verified_by_provisioner": True,
    }
    report = REPORTER["build_report"](
        {
            "result": "passed",
            "schema_files_applied": len(list((ROOT / "schemas/postgres").glob("*.sql"))),
            "schema_files_pending": 0,
            "schema_files_failed": 0,
            "seeds_applied": 0,
            "operator_scope_probe": {
                "runtime_public_relation_acl": [
                    _acl_row(
                        "api_key",
                        select=False,
                        insert=False,
                        update=False,
                        delete=False,
                    )
                ],
                "runtime_api_key_policy": api_key_policy,
                "runtime_append_only_policy": {
                    "relations_expected": 2,
                    "relations_verified": 2,
                    "select_insert_verified": 2,
                    "mutations_denied": 2,
                    "column_grants_denied": 2,
                    "verified_by_provisioner": True,
                },
            },
        },
        {"execution_sites": []},
    )

    api_key = next(row for row in report["relations"] if row["relation"] == "api_key")
    assert api_key["expected_runtime_boundary"] == "read_only_column_allowlist"
    assert api_key["configured_runtime_boundary"] == "read_only_column_allowlist"
    assert api_key["runtime_boundary_policy_matches_source"] is True
    assert report["runtime_role_acceptance"]["api_key_column_boundary_passed"] is True
    assert report["runtime_role_acceptance"]["append_only_audit_ledgers_boundary_passed"] is True
    assert report["summary"][
        "migration_revoked_relations_missing_or_mismatched_runtime_policy"
    ] == 0


def test_data_access_log_policy_preserves_append_only_runtime_access():
    report = REPORTER["build_report"](
        {
            "result": "inventory",
            "runtime_public_relation_acl": [
                _acl_row(
                    "data_access_log",
                    select=True,
                    insert=True,
                    update=False,
                    delete=False,
                )
            ],
        },
        {"execution_sites": []},
    )
    row = next(item for item in report["relations"] if item["relation"] == "data_access_log")
    assert row["expected_runtime_boundary"] == "runtime_append_only_read_insert"
    assert row["configured_runtime_boundary"] == "runtime_append_only_read_insert"
    assert row["runtime_boundary_policy_matches_source"] is True
    assert row["effective_dml_privileges"] == ["INSERT"]
    assert row["effective_dml_revokes"] == []
    assert row["dml_overlaps_explicit_revoke"] is False


def test_access_audit_log_policy_preserves_append_only_runtime_access():
    report = REPORTER["build_report"](
        {
            "result": "inventory",
            "runtime_public_relation_acl": [
                _acl_row(
                    "access_audit_log",
                    select=True,
                    insert=True,
                    update=False,
                    delete=False,
                )
            ],
        },
        {"execution_sites": []},
    )
    row = next(item for item in report["relations"] if item["relation"] == "access_audit_log")
    assert row["expected_runtime_boundary"] == "runtime_append_only_read_insert"
    assert row["configured_runtime_boundary"] == "runtime_append_only_read_insert"
    assert row["runtime_boundary_policy_matches_source"] is True
    assert row["effective_dml_privileges"] == ["INSERT"]
    assert row["effective_dml_revokes"] == []
    assert row["dml_overlaps_explicit_revoke"] is False


def test_source_report_does_not_claim_full_schema_role_acceptance_without_probe():
    report = REPORTER["build_report"](
        {"result": "inventory", "runtime_public_relation_acl": []},
        {"execution_sites": []},
    )

    assert report["runtime_role_acceptance"]["full_schema_replay_passed"] is False
    assert report["runtime_role_acceptance"]["scoped_acl_checks_passed"] is False


def test_boolean_does_not_satisfy_service_registry_acl_probe_count():
    scoped_policy = {
        "private_relations_expected": len(runtime_role._RUNTIME_PRIVATE_TABLES),
        "mutation_denied_relations_expected": len(runtime_role._RUNTIME_MUTATION_TABLES),
        "private_relations_verified": len(runtime_role._RUNTIME_PRIVATE_TABLES),
        "mutation_denied_relations_verified": len(runtime_role._RUNTIME_MUTATION_TABLES),
        "direct_table_privilege_violations": 0,
        "direct_column_privilege_violations": 0,
        "farm_activity_ledger_readable": 1,
        "service_registry_read_only_verified": True,
        "append_only_relations_expected": 2,
        "append_only_relations_verified": 2,
        "append_only_select_insert_verified": 2,
        "append_only_mutations_denied": 2,
        "append_only_column_grants_denied": 2,
    }
    replay = {
        "result": "passed",
        "schema_files_applied": len(list((ROOT / "schemas/postgres").glob("*.sql"))),
        "schema_files_pending": 0,
        "schema_files_failed": 0,
        "seeds_applied": 0,
        "operator_scope_probe": {
            "result": "passed",
            "runtime_public_relation_acl": [],
            "runtime_scoped_write_policy": scoped_policy,
        },
    }

    report = REPORTER["build_report"](replay, {"execution_sites": []})

    assert report["runtime_role_acceptance"]["scoped_acl_checks_passed"] is False
    assert report["runtime_role_acceptance"]["service_registry_read_only_boundary_passed"] is False


def test_insert_select_source_is_not_reported_as_a_dml_target():
    site = {
        "id": "services/analytics/multi_farm.py:39:4",
        "source": "services/analytics/multi_farm.py",
        "line": 39,
        "scope": "instantiate_farm_from_template",
        "method": "execute",
        "expression_kind": "literal",
        "statement_kind": "INSERT",
        "candidate_relations": ["farm", "farm_template_instance"],
        "write_target_relations": ["farm_template_instance"],
        "static_sql_sha256": "c" * 64,
        "operation_refs": [],
    }
    report = REPORTER["build_report"](
        {
            "result": "inventory",
            "runtime_public_relation_acl": [
                _acl_row("farm", select=True, insert=True, update=True, delete=True),
                _acl_row(
                    "farm_template_instance",
                    select=True,
                    insert=True,
                    update=True,
                    delete=True,
                ),
            ],
        },
        {"execution_sites": [site]},
    )

    rows = {row["relation"]: row for row in report["relations"]}
    farm = rows["farm"]
    assert farm["candidate_execution_sites_by_statement"] == {"INSERT": 1}
    assert farm["candidate_source_files"] == [{
        "path": "services/analytics/multi_farm.py",
        "statement_counts": {"INSERT": 1},
    }]
    assert farm["candidate_write_target_sites_by_statement"] == {}
    assert farm["candidate_write_target_source_files"] == []
    assert report["summary"]["unprotected_dml_relations_without_candidate_write_sites"] == 1
    assert report["unprotected_dml_relations_without_candidate_write_sites"] == ["farm"]
    assert report["unprotected_candidate_write_relations_by_service"] == {"analytics": 1}

    target = rows["farm_template_instance"]
    assert target["candidate_write_target_sites_by_statement"] == {"INSERT": 1}
    assert target["candidate_write_target_source_files"] == [{
        "path": "services/analytics/multi_farm.py",
        "statement_counts": {"INSERT": 1},
    }]


def test_truncate_privileges_and_targets_are_reported_separately_from_dml():
    site = {
        "id": "services/analytics/cleanup.py:12:4",
        "source": "services/analytics/cleanup.py",
        "line": 12,
        "scope": "clear_expired_cache",
        "method": "execute",
        "expression_kind": "literal",
        "statement_kind": "TRUNCATE",
        "candidate_relations": ["expired_cache"],
        "write_target_relations": ["expired_cache"],
        "static_sql_sha256": "d" * 64,
        "operation_refs": [],
    }
    report = REPORTER["build_report"](
        {
            "result": "inventory",
            "runtime_public_relation_acl": [
                _acl_row(
                    "expired_cache",
                    select=True,
                    insert=False,
                    update=False,
                    delete=False,
                    truncate=True,
                ),
            ],
        },
        {"execution_sites": [site]},
    )

    row = report["relations"][0]
    assert row["has_any_dml"] is False
    assert row["effective_truncate_privilege"] is True
    assert row["candidate_write_target_sites_by_statement"] == {"TRUNCATE": 1}
    assert report["relations_with_effective_truncate"] == ["expired_cache"]
    assert report["relations_with_effective_truncate_and_rls_disabled"] == [
        "expired_cache"
    ]
    assert report["summary"]["relations_with_effective_truncate"] == 1
    assert report["summary"]["relations_with_effective_truncate_and_rls_disabled"] == 1
