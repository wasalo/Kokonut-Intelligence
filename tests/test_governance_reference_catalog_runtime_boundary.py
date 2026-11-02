"""Source contract for migration 721's read-only global catalogs."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/721_runtime_governance_reference_catalogs_read_only.sql"
CHECKER = ROOT / "scripts/check-governance-reference-catalog-runtime-boundary-disposable.py"


def test_migration_only_restricts_runtime_on_the_two_reference_catalogs():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "data_governance_category" in sql
    assert "data_governance_scope" in sql
    assert "kokonut_runtime" in sql
    assert "if exists" in sql
    assert "revoke all privileges on table" in sql
    assert "revoke insert" in sql
    assert "update (%1$i)" in sql
    assert "references (%1$i)" in sql
    assert "grant select on table" in sql
    assert "create role" not in sql
    assert "kokonut_directus_runtime" not in sql
    assert "security definer" not in sql


def test_migration_fails_closed_if_catalog_relations_are_missing_or_changed():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "required relation public.% is missing" in sql
    assert "relation_kind not in ('r', 'p')" in sql
    assert "begin;" in sql
    assert "commit;" in sql


def test_disposable_checker_is_network_isolated_and_covers_bootstrap_replay():
    checker = CHECKER.read_text(encoding="utf-8").lower()

    assert '"--network", "none"' in checker
    assert '"-p"' not in checker
    assert "gov_catalog_role_absent" in checker
    assert "gov_catalog_role_present" in checker
    assert "grant insert (category_key), update (display_name), references (category_key)" in checker
    assert "grant insert (scope_key), update (display_name), references (scope_key)" in checker
    assert "kokonut_directus_runtime" in checker
    assert "has_column_privilege" in checker
    assert "insufficient_privilege" in checker
