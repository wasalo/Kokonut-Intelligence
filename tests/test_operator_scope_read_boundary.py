"""Source and provider contracts for isolated operator scope reads."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/750_operator_scope_read_functions.sql"


def test_scope_read_migration_uses_an_isolated_owner_and_bounded_functions():
    sql = MIGRATION.read_text().lower()
    provisioner = (ROOT / "services/migration/runtime_role.py").read_text()

    assert "create role kokonut_operator_scope_read_owner" in sql
    assert "nologin noinherit nosuperuser nocreatedb nocreaterole" in sql
    assert "noreplication nobypassrls" in sql
    assert "must not own database relations" in sql
    assert "must own only its two bounded functions" in sql
    assert "revoke select (%1$i), insert (%1$i), update (%1$i), references (%1$i)" in sql
    assert "security definer" in sql
    assert "set search_path = pg_catalog" in sql
    assert "grant select on table public.operator_scope_grant" not in sql
    assert "to kokonut_operator_auth" in sql
    assert "from public" in sql
    assert "from kokonut_runtime" in sql
    assert "operator_scope_grant_read_allows(uuid,text,text,uuid)" in provisioner
    assert "operator_scope_grant_read_scopes(uuid)" in provisioner
    assert "kokonut_operator_scope_read_owner" in provisioner
    assert "migration 750 operator-scope read functions" in provisioner


def test_scope_read_migration_preserves_tenant_checks_and_forced_rls_access():
    sql = MIGRATION.read_text().lower()

    for required in (
        "identity.enabled",
        "grant_row.revoked_at is null",
        "grant_row.organization_id is null",
        "membership.revoked_at is null",
        "tenant.status = 'active'",
        "owner.organization_id = loc.organization_id",
        "share.revoked_at is null",
        "share.expires_at > pg_catalog.now()",
        "order by grant_row.resource, grant_row.action, grant_row.location_id",
        "for select to kokonut_operator_scope_read_owner using (true)",
    ):
        assert required in sql


def test_oidc_provider_scope_reads_use_the_operator_auth_database_functions():
    source = (ROOT / "services/gateway/operator_auth.py").read_text()
    provider_source = source.split("class OIDCOperatorProvider", 1)[1]
    scope_methods = provider_source.split("    def has_scope(", 1)[1].split("    def revoke_session(", 1)[0]

    assert "_get_operator_auth_db(self.settings)" in scope_methods
    assert "_get_db()" not in scope_methods
    assert "kokonut_security.operator_scope_grant_read_allows" in scope_methods
    assert "kokonut_security.operator_scope_grant_read_scopes" in scope_methods
    assert "SET TRANSACTION READ ONLY" in scope_methods
    assert "SET LOCAL statement_timeout = '5s'" in scope_methods
    assert "SET LOCAL lock_timeout = '2s'" in scope_methods


def test_restore_role_bootstrap_includes_scope_read_function_owner():
    source = (ROOT / "scripts/kernel-restore-role-prerequisites.sql").read_text()

    assert "'kokonut_operator_scope_read_owner'" in source
