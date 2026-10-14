"""Unit checks for transaction-local operator tenant context setup."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from services.common.tenant_context import (
    OperatorTenantContext,
    TenantContextDenied,
    clear_operator_tenant_context,
    set_operator_tenant_context,
)

TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OPERATOR_ID = "a0000000-0000-0000-0000-000000000904"


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


def test_sets_database_derived_context_transaction_locally():
    connection = FakeConnection((TENANT_ID, LOCATION_ID, OPERATOR_ID))

    context = set_operator_tenant_context(
        connection,
        operator_id=OPERATOR_ID,
        location_id=LOCATION_ID,
        resource="report_snapshot_review",
        action="read",
    )

    assert context == OperatorTenantContext(TENANT_ID, LOCATION_ID, OPERATOR_ID)
    assert len(connection.calls) == 3
    validation_sql, validation_params = connection.calls[1]
    assert "organization_id IS NOT NULL" in validation_sql
    assert "operator_scope_grant_allows" in validation_sql
    assert validation_params == (OPERATOR_ID, LOCATION_ID, "report_snapshot_review", "read")
    set_sql, set_params = connection.calls[2]
    assert "set_config(%s, %s, TRUE)" in set_sql
    assert set_params == (
        "kokonut.tenant_id", TENANT_ID,
        "kokonut.location_id", LOCATION_ID,
        "kokonut.actor_id", OPERATOR_ID,
        "kokonut.actor_type", "operator",
    )


def test_denied_or_legacy_scope_is_cleared_and_never_set():
    connection = FakeConnection(scope_row=None)

    with pytest.raises(TenantContextDenied, match="tenant-qualified operator grant"):
        set_operator_tenant_context(
            connection,
            operator_id=OPERATOR_ID,
            location_id=LOCATION_ID,
            resource="report_snapshot_review",
            action="read",
        )

    assert len(connection.calls) == 2
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
    assert "set_config(%s, %s, TRUE)" not in connection.calls[1][0]


def test_ambiguous_tenant_scope_is_denied_and_cleared():
    other_tenant = "a0000000-0000-0000-0000-000000000802"
    connection = FakeConnection(
        scope_rows=[
            (TENANT_ID, LOCATION_ID, OPERATOR_ID),
            (other_tenant, LOCATION_ID, OPERATOR_ID),
        ]
    )

    with pytest.raises(TenantContextDenied, match="scope ambiguous"):
        set_operator_tenant_context(
            connection,
            operator_id=OPERATOR_ID,
            location_id=LOCATION_ID,
            resource="report_snapshot_review",
            action="read",
        )

    assert len(connection.calls) == 2
    assert "set_config(%s, '', TRUE)" in connection.calls[0][0]
    assert "LIMIT 2" in connection.calls[1][0]
    assert "set_config(%s, %s, TRUE)" not in connection.calls[1][0]


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
    connection = FakeConnection((TENANT_ID, LOCATION_ID, OPERATOR_ID))

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


def test_autocommit_connection_is_rejected_before_setting_context():
    connection = FakeConnection(autocommit=True)

    with pytest.raises(ValueError, match="non-autocommit transaction"):
        clear_operator_tenant_context(connection)

    assert connection.calls == []
