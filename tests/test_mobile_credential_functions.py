"""Source checks for the bounded PostgreSQL Field Collector credential API."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/392_mobile_credential_functions.sql"
API = ROOT / "services/mobile/api.py"


def test_credential_migration_uses_non_login_non_bypass_owner_and_fixed_search_path():
    sql = MIGRATION.read_text().lower()

    assert "create role kokonut_mobile_credential_owner" in sql
    assert "nologin noinherit nosuperuser nocreatedb nocreaterole" in sql
    assert "noreplication nobypassrls" in sql
    assert sql.count("security definer") == 2
    assert sql.count("set search_path = pg_catalog") == 3
    assert "grant insert on table public.mobile_device" in sql
    assert "grant update (used_at, consumed_device_id)" in sql
    assert "grant insert, update on table public.mobile_device" not in sql
    assert "grant update on table public.mobile_device_enrollment" not in sql
    assert "public.guard_mobile_tenant_binding()" in sql
    assert "from public.location as loc" in sql
    assert "join public.location_tenant_owner_verification as owner" in sql
    assert "execute format" not in sql
    assert "bypassrls" in sql


def test_device_resolution_returns_only_identity_and_current_owner_state():
    sql = MIGRATION.read_text().lower()
    function_sql = sql.split("function kokonut_security.resolve_mobile_device_token", 1)[1]
    function_sql = function_sql.split("alter function", 1)[0]

    assert "returns table" in function_sql
    assert "owner_binding_current boolean" in function_sql
    assert "device.device_token_hash = requested_token_hash" in function_sql
    assert "device.tenant_organization_id = location.organization_id" in function_sql
    assert "owner.revoked_at is null" in function_sql
    assert "tenant.status = 'active'" in function_sql
    assert "payload" not in function_sql
    assert "device_token_hash," not in function_sql


def test_enrollment_redemption_is_atomic_and_has_bounded_outcomes():
    sql = MIGRATION.read_text().lower()
    function_sql = sql.split("function kokonut_security.redeem_mobile_enrollment", 1)[1]
    function_sql = function_sql.split("alter function", 1)[0]

    assert "for update" in function_sql
    assert "for share of location, owner, tenant" in function_sql
    assert "inserted_device_id" in function_sql
    assert "on conflict (device_id) do nothing" in function_sql
    assert "set used_at = statement_timestamp()" in function_sql
    assert "result := 'invalid'" in function_sql
    assert "result := 'owner_changed'" in function_sql
    assert "result := 'device_conflict'" in function_sql
    assert "result := 'registered'" in function_sql
    assert "execute format" not in function_sql


def test_mobile_api_calls_the_credential_functions_instead_of_direct_lookups():
    source = API.read_text().lower()
    assert "kokonut_security.resolve_mobile_device_token(%s)" in source
    assert "kokonut_security.redeem_mobile_enrollment(" in source
    assert "from mobile_device\n            where device_token_hash" not in source
    assert "from mobile_device_enrollment\n            where code_hash" not in source
