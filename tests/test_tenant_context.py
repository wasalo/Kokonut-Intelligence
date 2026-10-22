"""Unit checks for transaction-local tenant context setup."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager

import pytest

from services.common.tenant_context import (
    GatewayTenantContext,
    MobileDeviceTenantContext,
    OperatorTenantContext,
    TenantContextDenied,
    WorkerTenantContext,
    bind_operator_session_token_hash,
    clear_operator_tenant_context,
    reset_operator_session_token_hash,
    set_agent_summary_source_tenant_context,
    set_gateway_tenant_context,
    set_mobile_device_tenant_context,
    set_operator_tenant_context,
    set_worker_tenant_context,
)

TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OPERATOR_ID = "a0000000-0000-0000-0000-000000000904"
GATEWAY_API_KEY_ID = "a0000000-0000-0000-0000-000000000910"
OPERATOR_SESSION_HASH = "b" * 64
GATEWAY_API_KEY_HASH = "c" * 64


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


def test_sets_gateway_context_from_database_verified_api_key_scope():
    connection = FakeConnection(
        (TENANT_ID, LOCATION_ID, GATEWAY_API_KEY_ID, "gateway_api_key")
    )

    context = set_gateway_tenant_context(
        connection,
        credential_type="api_key",
        credential_hash=GATEWAY_API_KEY_HASH,
        location_id=LOCATION_ID,
        resource="mobile_device",
        action="enroll",
    )

    assert context == GatewayTenantContext(
        TENANT_ID, LOCATION_ID, GATEWAY_API_KEY_ID, "gateway_api_key"
    )
    assert len(connection.calls) == 2
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
    context_sql, context_params = connection.calls[1]
    assert "kokonut_security.set_gateway_tenant_context" in context_sql
    assert context_params == (
        "api_key",
        GATEWAY_API_KEY_HASH,
        LOCATION_ID,
        "mobile_device",
        "enroll",
    )


def test_gateway_context_denies_missing_verified_owner_after_clear():
    connection = FakeConnection(scope_row=None)

    with pytest.raises(TenantContextDenied, match="active credential scope"):
        set_gateway_tenant_context(
            connection,
            credential_type="api_key",
            credential_hash=GATEWAY_API_KEY_HASH,
            location_id=LOCATION_ID,
            resource="mobile_device",
            action="revoke",
        )

    assert len(connection.calls) == 2
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
    assert "kokonut_security.set_gateway_tenant_context" in connection.calls[1][0]


def test_sets_gateway_context_from_database_verified_capability():
    connection = FakeConnection(
        (TENANT_ID, LOCATION_ID, GATEWAY_API_KEY_ID, "gateway_capability")
    )

    context = set_gateway_tenant_context(
        connection,
        credential_type="capability_token",
        credential_hash=GATEWAY_API_KEY_HASH,
        location_id=LOCATION_ID,
        resource="mobile_device",
        action="revoke",
    )

    assert context == GatewayTenantContext(
        TENANT_ID, LOCATION_ID, GATEWAY_API_KEY_ID, "gateway_capability"
    )
    assert connection.calls[1][1] == (
        "capability_token",
        GATEWAY_API_KEY_HASH,
        LOCATION_ID,
        "mobile_device",
        "revoke",
    )


@pytest.mark.parametrize(
    "credential_type",
    ["unsupported", None],
)
def test_gateway_context_rejects_unsupported_credential_types(credential_type):
    connection = FakeConnection()
    with pytest.raises(ValueError, match="credential-type"):
        set_gateway_tenant_context(
            connection,
            credential_type=credential_type,
            credential_hash=GATEWAY_API_KEY_HASH,
            location_id=LOCATION_ID,
            resource="mobile_device",
            action="enroll",
        )
    assert len(connection.calls) == 1


@pytest.mark.parametrize(
    ("credential_hash", "resource", "action"),
    [
        ("bad", "mobile_device", "enroll"),
        ("c" * 64, "Mobile_Device", "enroll"),
        ("c" * 64, "mobile_device", "revoke:any"),
    ],
)
def test_gateway_context_clears_old_scope_before_rejecting_invalid_inputs(
    credential_hash, resource, action
):
    connection = FakeConnection(
        (TENANT_ID, LOCATION_ID, GATEWAY_API_KEY_ID, "gateway_api_key")
    )

    with pytest.raises(ValueError):
        set_gateway_tenant_context(
            connection,
            credential_type="api_key",
            credential_hash=credential_hash,
            location_id=LOCATION_ID,
            resource=resource,
            action=action,
        )

    assert len(connection.calls) == 1
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]


def test_sets_worker_context_with_secret_hash_and_exact_role_scope():
    raw_credential = "worker-secret-with-at-least-32-bytes"
    connection = FakeConnection((TENANT_ID, LOCATION_ID, OPERATOR_ID, "system_worker"))

    context = set_worker_tenant_context(
        connection,
        credential=raw_credential,
        location_id=LOCATION_ID,
        resource="sensor_reading",
        action="process",
    )

    assert context == WorkerTenantContext(
        TENANT_ID, LOCATION_ID, OPERATOR_ID, "sensor_reading", "process"
    )
    assert len(connection.calls) == 3
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
    assert connection.calls[1] == ("SET LOCAL ROLE kokonut_worker_execution", ())
    context_sql, context_params = connection.calls[2]
    assert "kokonut_security.set_worker_tenant_context" in context_sql
    assert context_params == (
        hashlib.sha256(raw_credential.encode("utf-8")).hexdigest(),
        LOCATION_ID,
        "sensor_reading",
        "process",
    )
    assert raw_credential not in repr(context_params)


def test_sets_agent_summary_source_context_without_worker_execution_role():
    raw_credential = "agent-summary-source-secret-with-32-bytes"
    connection = FakeConnection((TENANT_ID, LOCATION_ID, OPERATOR_ID, "system_worker"))

    context = set_agent_summary_source_tenant_context(
        connection,
        credential=raw_credential,
        location_id=LOCATION_ID,
    )

    assert context == WorkerTenantContext(
        TENANT_ID, LOCATION_ID, OPERATOR_ID, "ai_summary", "read"
    )
    assert len(connection.calls) == 2
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
    context_sql, context_params = connection.calls[1]
    assert "kokonut_security.set_worker_tenant_context" in context_sql
    assert context_params == (
        hashlib.sha256(raw_credential.encode("utf-8")).hexdigest(),
        LOCATION_ID,
        "ai_summary",
        "read",
    )
    assert raw_credential not in repr(context_params)
    assert all("SET LOCAL ROLE kokonut_worker_execution" not in sql
               for sql, _params in connection.calls)


def test_worker_context_denial_clears_scope_and_never_sends_raw_credential():
    raw_credential = "worker-secret-with-at-least-32-bytes"
    connection = FakeConnection(scope_row=None)

    with pytest.raises(TenantContextDenied, match="active grant"):
        set_worker_tenant_context(
            connection,
            credential=raw_credential,
            location_id=LOCATION_ID,
            resource="sensor_reading",
            action="process",
        )

    assert len(connection.calls) == 3
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
    assert raw_credential not in repr(connection.calls)


@pytest.mark.parametrize(
    ("credential", "location_id", "resource", "action"),
    [
        ("short", LOCATION_ID, "sensor_reading", "process"),
        ("\ud800" * 32, LOCATION_ID, "sensor_reading", "process"),
        ("x" * 40, "not-a-uuid", "sensor_reading", "process"),
        ("x" * 40, LOCATION_ID, "Sensor_Reading", "process"),
        ("x" * 40, LOCATION_ID, "sensor_reading", "Process"),
    ],
)
def test_worker_context_clears_scope_before_rejecting_invalid_inputs(
    credential, location_id, resource, action
):
    connection = FakeConnection()

    with pytest.raises(ValueError):
        set_worker_tenant_context(
            connection,
            credential=credential,
            location_id=location_id,
            resource=resource,
            action=action,
        )

    assert len(connection.calls) == 1
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]


def test_worker_context_rejects_autocommit_before_database_access():
    connection = FakeConnection(autocommit=True)

    with pytest.raises(ValueError, match="non-autocommit transaction"):
        set_worker_tenant_context(
            connection,
            credential="worker-secret-with-at-least-32-bytes",
            location_id=LOCATION_ID,
            resource="sensor_reading",
            action="process",
        )

    assert connection.calls == []
