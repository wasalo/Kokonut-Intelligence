"""Unit checks for transaction-local operator tenant context setup."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from services.common.tenant_context import (
    GatewayTenantContext,
    MobileDeviceTenantContext,
    OperatorTenantContext,
    TenantContextDenied,
    bind_operator_session_token_hash,
    clear_operator_tenant_context,
    reset_operator_session_token_hash,
    set_gateway_tenant_context,
    set_mobile_device_tenant_context,
    set_operator_tenant_context,
)

TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OPERATOR_ID = "a0000000-0000-0000-0000-000000000904"
OPERATOR_SESSION_HASH = "b" * 64


@pytest.fixture
def operator_session_proof():
    token = bind_operator_session_token_hash(OPERATOR_SESSION_HASH)
    try:
        yield
    finally:
        reset_operator_session_token_hash(token)


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = list(connection.scope_rows)
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=()):
        self.connection.calls.append((sql, params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows


class FakeConnection:
    def __init__(self, scope_row=None, *, scope_rows=None, autocommit=False):
        self.scope_rows = list(scope_rows) if scope_rows is not None else (
            [scope_row] if scope_row is not None else []
        )
        self.autocommit = autocommit
        self.calls = []

    @contextmanager
    def cursor(self):
        yield FakeCursor(self)


def test_sets_database_derived_context_transaction_locally(operator_session_proof):
    connection = FakeConnection((TENANT_ID, LOCATION_ID, OPERATOR_ID, "operator"))

    context = set_operator_tenant_context(
        connection,
        operator_id=OPERATOR_ID,
        location_id=LOCATION_ID,
        resource="report_snapshot_review",
        action="read",
    )

    assert context == OperatorTenantContext(TENANT_ID, LOCATION_ID, OPERATOR_ID)
    assert len(connection.calls) == 2
    context_sql, context_params = connection.calls[1]
    assert "kokonut_security.set_operator_tenant_context" in context_sql
    assert context_params == (
        OPERATOR_SESSION_HASH,
        OPERATOR_ID,
        LOCATION_ID,
        "report_snapshot_review",
        "read",
        "[]",
    )


def test_denied_or_legacy_scope_is_cleared_and_never_set(operator_session_proof):
    connection = FakeConnection(scope_row=None)

    with pytest.raises(TenantContextDenied, match="session or tenant-qualified grants"):
        set_operator_tenant_context(
            connection,
            operator_id=OPERATOR_ID,
            location_id=LOCATION_ID,
            resource="report_snapshot_review",
            action="read",
        )

    assert len(connection.calls) == 2
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
    assert "kokonut_security.set_operator_tenant_context" in connection.calls[1][0]


def test_database_denial_clears_context(operator_session_proof):
    connection = FakeConnection(scope_row=None)

    with pytest.raises(TenantContextDenied, match="session or tenant-qualified grants"):
        set_operator_tenant_context(
            connection,
            operator_id=OPERATOR_ID,
            location_id=LOCATION_ID,
            resource="report_snapshot_review",
            action="read",
        )

    assert len(connection.calls) == 2
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
    assert "kokonut_security.set_operator_tenant_context" in connection.calls[1][0]


def test_multiple_required_scopes_must_resolve_to_one_tenant(operator_session_proof):
    connection = FakeConnection(
        scope_row=(TENANT_ID, LOCATION_ID, OPERATOR_ID, "operator")
    )

    context = set_operator_tenant_context(
        connection,
        operator_id=OPERATOR_ID,
        location_id=LOCATION_ID,
        resource="mobile_collection_retention",
        action="inventory",
        required_scopes=(("mobile_collection_review", "read"),),
    )

    assert context == OperatorTenantContext(TENANT_ID, LOCATION_ID, OPERATOR_ID)
    validation_sql, validation_params = connection.calls[1]
    assert "kokonut_security.set_operator_tenant_context" in validation_sql
    assert validation_params == (
        OPERATOR_SESSION_HASH,
        OPERATOR_ID,
        LOCATION_ID,
        "mobile_collection_retention",
        "inventory",
        '[{"resource":"mobile_collection_review","action":"read"}]',
    )


def test_multiple_required_scopes_fail_closed(operator_session_proof):
    connection = FakeConnection(scope_row=None)

    with pytest.raises(TenantContextDenied, match="session or tenant-qualified grants"):
        set_operator_tenant_context(
            connection,
            operator_id=OPERATOR_ID,
            location_id=LOCATION_ID,
            resource="mobile_collection_retention",
            action="inventory",
            required_scopes=(("mobile_collection_review", "read"),),
        )

    assert len(connection.calls) == 2
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
    assert "kokonut_security.set_operator_tenant_context" in connection.calls[1][0]


def test_required_scope_limit_clears_prior_context(operator_session_proof):
    connection = FakeConnection()
    required_scopes = tuple((f"resource_{index}", "read") for index in range(17))

    with pytest.raises(ValueError, match="at most 16 additional"):
        set_operator_tenant_context(
            connection,
            operator_id=OPERATOR_ID,
            location_id=LOCATION_ID,
            resource="primary_resource",
            action="read",
            required_scopes=required_scopes,
        )

    assert len(connection.calls) == 1
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]


@pytest.mark.parametrize(
    ("operator_id", "location_id", "resource", "action"),
    [
        ("bad", LOCATION_ID, "read", "read"),
        (OPERATOR_ID, "bad", "read", "read"),
        (OPERATOR_ID, LOCATION_ID, "Read", "read"),
        (OPERATOR_ID, LOCATION_ID, "read", "read:any"),
    ],
)
def test_invalid_context_inputs_clear_old_scope_without_authorization_query(
    operator_id, location_id, resource, action
):
    connection = FakeConnection((TENANT_ID, LOCATION_ID, OPERATOR_ID, "operator"))

    with pytest.raises(ValueError):
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource=resource,
            action=action,
        )

    assert len(connection.calls) == 1
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]


def test_operator_context_requires_authenticated_session_proof():
    connection = FakeConnection((TENANT_ID, LOCATION_ID, OPERATOR_ID, "operator"))

    with pytest.raises(TenantContextDenied, match="authenticated operator session"):
        set_operator_tenant_context(
            connection,
            operator_id=OPERATOR_ID,
            location_id=LOCATION_ID,
            resource="report_snapshot_review",
            action="read",
        )

    assert len(connection.calls) == 1
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]


def test_autocommit_connection_is_rejected_before_setting_context():
    connection = FakeConnection(autocommit=True)

    with pytest.raises(ValueError, match="non-autocommit transaction"):
        clear_operator_tenant_context(connection)

    assert connection.calls == []


def test_sets_mobile_context_only_from_current_verified_owner_transaction():
    connection = FakeConnection((TENANT_ID, LOCATION_ID, "device-row-1", "mobile_device"))

    context = set_mobile_device_tenant_context(
        connection,
        device_id="field-device-1",
        location_id=LOCATION_ID,
        device_token_hash="a" * 64,
    )

    assert context == MobileDeviceTenantContext(TENANT_ID, LOCATION_ID, "device-row-1")
    assert len(connection.calls) == 2
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
    context_sql, context_params = connection.calls[1]
    assert "kokonut_security.set_mobile_device_context" in context_sql
    assert context_params == ("a" * 64, "field-device-1", LOCATION_ID)


def test_stale_or_legacy_mobile_device_is_denied_after_context_clear():
    connection = FakeConnection(scope_row=None)

    with pytest.raises(TenantContextDenied, match="current verified location owner"):
        set_mobile_device_tenant_context(
            connection,
            device_id="former-owner-device",
            location_id=LOCATION_ID,
            device_token_hash="a" * 64,
        )

    assert len(connection.calls) == 2
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
    assert "kokonut_security.set_mobile_device_context" in connection.calls[1][0]


def test_mobile_context_requires_transaction_and_clears_before_input_validation():
    autocommit = FakeConnection(autocommit=True)
    with pytest.raises(ValueError, match="non-autocommit transaction"):
        set_mobile_device_tenant_context(
            autocommit,
            device_id="field-device-1",
            location_id=LOCATION_ID,
            device_token_hash="a" * 64,
        )
    assert autocommit.calls == []

    invalid = FakeConnection((TENANT_ID, LOCATION_ID, "device-row-1", "mobile_device"))
    with pytest.raises(ValueError, match="device-id must be a non-empty"):
        set_mobile_device_tenant_context(
            invalid,
            device_id=" ",
            location_id=LOCATION_ID,
            device_token_hash="a" * 64,
        )
    assert len(invalid.calls) == 1
    assert "set_config(%s, '', TRUE)" in invalid.calls[0][0]


def test_sets_gateway_context_from_current_verified_owner_after_route_auth():
    connection = FakeConnection((TENANT_ID, LOCATION_ID))

    context = set_gateway_tenant_context(
        connection,
        gateway_caller="field-enroller",
        location_id=LOCATION_ID,
        resource="mobile_device",
        action="enroll",
    )

    assert context == GatewayTenantContext(
        TENANT_ID, LOCATION_ID, "field-enroller", "gateway"
    )
    assert len(connection.calls) == 3
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
    owner_sql, owner_params = connection.calls[1]
    assert "owner.revoked_at IS NULL" in owner_sql
    assert "tenant.status = 'active'" in owner_sql
    assert "FOR SHARE OF loc, owner, tenant" in owner_sql
    assert owner_params == (LOCATION_ID,)
    context_sql, context_params = connection.calls[2]
    assert "set_config(%s, %s, TRUE)" in context_sql
    assert context_params == (
        "kokonut.tenant_id", TENANT_ID,
        "kokonut.location_id", LOCATION_ID,
        "kokonut.actor_id", "field-enroller",
        "kokonut.actor_type", "gateway",
    )


def test_gateway_context_denies_missing_verified_owner_after_clear():
    connection = FakeConnection(scope_row=None)

    with pytest.raises(TenantContextDenied, match="current verified owner"):
        set_gateway_tenant_context(
            connection,
            gateway_caller="field-enroller",
            location_id=LOCATION_ID,
            resource="mobile_device",
            action="revoke",
        )

    assert len(connection.calls) == 2
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
    assert "FOR SHARE OF loc, owner, tenant" in connection.calls[1][0]
    assert "set_config(%s, %s, TRUE)" not in connection.calls[1][0]


@pytest.mark.parametrize(
    ("gateway_caller", "resource", "action"),
    [
        (" ", "mobile_device", "enroll"),
        ("api\nkey", "mobile_device", "enroll"),
        ("field-enroller", "Mobile_Device", "enroll"),
        ("field-enroller", "mobile_device", "revoke:any"),
    ],
)
def test_gateway_context_clears_old_scope_before_rejecting_invalid_inputs(
    gateway_caller, resource, action
):
    connection = FakeConnection((TENANT_ID, LOCATION_ID))

    with pytest.raises(ValueError):
        set_gateway_tenant_context(
            connection,
            gateway_caller=gateway_caller,
            location_id=LOCATION_ID,
            resource=resource,
            action=action,
        )

    assert len(connection.calls) == 1
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
