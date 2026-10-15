"""Source contract for bounded Field Collector device-token revocation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/398_bounded_mobile_device_revocation.sql"
SCHEMA_USAGE_MIGRATION = ROOT / "schemas/postgres/399_runtime_security_schema_usage.sql"
OPERATOR_AUTH_SCHEMA_USAGE_MIGRATION = (
    ROOT / "schemas/postgres/400_operator_auth_security_schema_usage.sql"
)
API = ROOT / "services/mobile/api.py"
RESTORE_ROLE_PREREQUISITES = ROOT / "scripts/kernel-restore-role-prerequisites.sql"
RESTORE_ACCEPTANCE = ROOT / "tests/fixtures/security_definer_restore_acceptance.sql"


def test_revocation_function_uses_a_non_login_non_bypass_owner_and_fixed_search_path():
    sql = MIGRATION.read_text().lower()

    assert "create role kokonut_mobile_device_revoke_owner" in sql
    assert "nologin noinherit nosuperuser nocreatedb nocreaterole" in sql
    assert "noreplication nobypassrls" in sql
    assert "security definer" in sql
    assert "set search_path = pg_catalog" in sql
    assert "grant update (status, device_token_hash, revoked_at, updated_at)" in sql
    assert "grant update (status, device_token_hash, revoked_at, updated_at)\n    on table public.mobile_device to kokonut_runtime" not in sql
    assert "revoke all on function kokonut_security.revoke_mobile_device" in sql
    assert "to kokonut_runtime" in sql
    assert "execute 'create policy mobile_device_revoke_owner_update" in sql
    assert "context.tenant_id = mobile_device.tenant_organization_id" in sql
    assert "context.location_id = mobile_device.location_id" in sql
    assert "using (true)" not in sql


def test_revocation_revalidates_exact_actor_scope_and_hides_nonmatching_devices():
    sql = MIGRATION.read_text().lower()
    function = sql.split("create or replace function kokonut_security.revoke_mobile_device", 1)[1]
    function = function.split("alter function kokonut_security.revoke_mobile_device", 1)[0]

    assert "'mobile_device',\n              'revoke'" in function
    assert "set_gateway_tenant_context" in function
    assert "set_operator_tenant_context" in function
    assert "current_tenant_context()" in function
    assert "resolved_location_id is distinct from requested_location_id" in function
    assert "resolved_actor_type is distinct from expected_actor_type" in function
    assert "device.tenant_organization_id = resolved_tenant_id" in function
    assert "device.status = 'active'" in function
    assert "return query select 'denied'" in function
    assert "return query select 'not_found'" in function
    assert "device_token_hash = null" in function
    assert "return query select 'revoked'" in function
    assert "requested_gateway_credential_hash" in function
    assert "requested_operator_session_token_hash" in function


def test_mobile_api_calls_bounded_revocation_and_returns_only_public_status():
    source = API.read_text()
    assert "kokonut_security.revoke_mobile_device" in source
    revoke = source.split("async def _revoke_device(", 1)[1]
    revoke = revoke.split("def _same_sync_record(", 1)[0]
    assert "UPDATE mobile_device" not in revoke
    assert "current_operator_session_token_hash()" in revoke
    assert 'row[0] == "denied"' in revoke
    assert 'row[0] == "not_found"' in revoke
    assert 'return {"device_id": row[1], "status": "revoked"}' in revoke


def test_runtime_role_can_resolve_private_security_functions_after_acl_restore():
    sql = SCHEMA_USAGE_MIGRATION.read_text().lower()
    assert "grant usage on schema kokonut_security to kokonut_runtime" in sql

    provisioner = (ROOT / "services/migration/runtime_role.py").read_text()
    assert "GRANT USAGE ON SCHEMA kokonut_security TO {}" in provisioner
    assert "has_schema_privilege(%s, 'kokonut_security', 'USAGE')" in provisioner


def test_operator_auth_role_can_resolve_session_functions_after_acl_restore():
    migration = OPERATOR_AUTH_SCHEMA_USAGE_MIGRATION.read_text().lower()
    assert "if exists" in migration
    assert "rolname = 'kokonut_operator_auth'" in migration
    assert "grant usage on schema kokonut_security to kokonut_operator_auth" in migration

    provisioner = (ROOT / "services/migration/runtime_role.py").read_text()
    assert "GRANT USAGE ON SCHEMA kokonut_security TO {}" in provisioner
    assert "(runtime_user, operator_auth_user)" in provisioner
    assert "runtime or operator-auth role is missing usage on kokonut_security" in provisioner


def test_database_restore_recreates_role_prerequisites_and_validates_function_owners():
    prerequisites = RESTORE_ROLE_PREREQUISITES.read_text().lower()
    migration = OPERATOR_AUTH_SCHEMA_USAGE_MIGRATION.read_text().lower()
    assert "create role %i nologin noinherit nosuperuser nocreatedb" in prerequisites
    for role in (
        "kokonut_mobile_credential_owner",
        "kokonut_mobile_context_owner",
        "kokonut_operator_context_owner",
        "kokonut_operator_auth_owner",
        "kokonut_gateway_context_owner",
        "kokonut_mobile_device_revoke_owner",
    ):
        assert role in prerequisites
        assert role in migration
    assert "alter function kokonut_security.authenticate_operator_session(text)" in migration
    assert "owner to kokonut_operator_auth_owner" in migration
    assert "grant select on table kokonut_security.mobile_context_hmac_key" in migration

    provisioner = (ROOT / "services/migration/runtime_role.py").read_text()
    assert "_SECURITY_DEFINER_OWNERS" in provisioner
    assert "_verify_security_definer_owners(cur)" in provisioner
    assert "apply migration 400 before provisioning runtime roles" in provisioner

    acceptance = RESTORE_ACCEPTANCE.read_text().lower()
    assert "enable row level security" in acceptance
    assert "force row level security" in acceptance
    assert "incorrect_owner_count" in acceptance
    assert "kokonut_security.revoke_mobile_device" in acceptance
    assert "kokonut_security.authenticate_operator_session" in acceptance
