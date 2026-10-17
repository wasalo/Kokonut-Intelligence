"""Explicitly scoped replacements for legacy farm-activity Directus roles."""

from types import SimpleNamespace

import pytest

from services.gateway import operator_cli
from services.gateway.farm_activity_roles import get_farm_activity_role_scopes

OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ORGANIZATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
LOCATION_ID = "11111111-1111-4111-8111-111111111111"


def test_legacy_role_templates_map_to_bounded_gateway_scopes():
    assert get_farm_activity_role_scopes("Field Worker") == (
        ("farm_activity", "read"),
        ("farm_activity", "read_detail"),
        ("farm_activity", "create_draft"),
        ("farm_activity", "edit_draft"),
        ("mobile_collection_review", "read_detail"),
    )
    assert get_farm_activity_role_scopes("Analyst") == (
        ("farm_activity", "read_published"),
        ("farm_activity", "read_published_detail"),
    )
    assert ("farm_activity", "publish") in get_farm_activity_role_scopes("Manager")
    for role in ("Supervisor", "Manager", "Finance", "Analyst", "Auditor"):
        assert all(action != "delete" for _, action in get_farm_activity_role_scopes(role))


def test_unknown_role_template_fails_closed():
    with pytest.raises(ValueError, match="Unknown farm activity role template"):
        get_farm_activity_role_scopes("administrator")


class _Result:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class _RoleGrantConnection:
    def __init__(self, *, membership=True):
        self.membership = membership
        self.grants = []
        self.statements = []

    def execute(self, sql, parameters):
        normalized = " ".join(sql.split()).lower()
        self.statements.append((normalized, parameters))
        if "from operator_identity" in normalized:
            return _Result({"id": OPERATOR_ID})
        if "from location_tenant_owner_verification" in normalized:
            return _Result({"organization_id": ORGANIZATION_ID})
        if "from operator_organization_membership" in normalized:
            return _Result({"1": 1} if self.membership else None)
        if "from location_organization_share" in normalized:
            return _Result(None)
        if "from location where" in normalized:
            return _Result({"location_organization_id": ORGANIZATION_ID})
        if normalized.startswith("insert into operator_scope_grant"):
            row = {
                "id": f"grant-{len(self.grants) + 1}",
                "operator_id": parameters["operator_id"],
                "resource": parameters["resource"],
                "action": parameters["action"],
                "location_id": parameters["location_id"],
                "organization_id": parameters["organization_id"],
                "granted_by": parameters["granted_by"],
            }
            self.grants.append(row)
            return _Result(row)
        raise AssertionError(f"Unexpected SQL: {normalized}")


class _ConnectionContext:
    def __init__(self, connection):
        self.connection = connection
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, _exc, _tb):
        self.rolled_back = exc_type is not None
        self.committed = exc_type is None
        return False


def _args(role="analyst"):
    return SimpleNamespace(
        role=role,
        operator_id=OPERATOR_ID,
        organization_id=ORGANIZATION_ID,
        location_id=LOCATION_ID,
        granted_by="tenant-admin",
    )


def test_role_grant_atomically_creates_tenant_qualified_scopes(monkeypatch):
    connection = _RoleGrantConnection()
    transaction = _ConnectionContext(connection)
    output = []
    monkeypatch.setattr(operator_cli, "get_connection", lambda: transaction)
    monkeypatch.setattr(operator_cli, "print_json", output.append)

    operator_cli.grant_farm_activity_role(_args())

    assert transaction.committed and not transaction.rolled_back
    assert [(row["resource"], row["action"]) for row in connection.grants] == [
        ("farm_activity", "read_published"),
        ("farm_activity", "read_published_detail"),
    ]
    assert all(row["organization_id"] == ORGANIZATION_ID for row in connection.grants)
    assert output[0]["role"] == "analyst"
    assert len(output[0]["grants"]) == 2


def test_role_grant_checks_tenant_membership_before_writing(monkeypatch):
    connection = _RoleGrantConnection(membership=False)
    transaction = _ConnectionContext(connection)
    monkeypatch.setattr(operator_cli, "get_connection", lambda: transaction)
    monkeypatch.setattr(operator_cli, "print_json", lambda _value: None)

    with pytest.raises(ValueError, match="active membership"):
        operator_cli.grant_farm_activity_role(_args("field_worker"))

    assert transaction.rolled_back and not transaction.committed
    assert connection.grants == []

