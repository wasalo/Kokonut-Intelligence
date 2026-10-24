"""Audit attribution for local operator-grant revocation paths."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from services.gateway import operator_cli

GRANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OPERATOR_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ORGANIZATION_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
LOCATION_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"


class Result:
    def __init__(self, row=None):
        self.row = row

    def first(self):
        return self.row


class Transaction:
    def __init__(self, handler):
        self.handler = handler
        self.statements = []
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc, _traceback):
        self.rolled_back = exc_type is not None
        self.committed = exc_type is None
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.lower().split())
        self.statements.append((normalized, params or {}))
        return Result(self.handler(normalized, params or {}))


@contextmanager
def _context(transaction):
    with transaction:
        yield transaction


def test_scope_revocation_requires_and_persists_audit_actor_and_reason(monkeypatch):
    returned = {
        "id": GRANT_ID,
        "operator_id": OPERATOR_ID,
        "resource": "farm_activity",
        "action": "read",
        "location_id": LOCATION_ID,
        "revoked_by": "local-admin",
        "revocation_reason": "operator access ended",
    }
    transaction = Transaction(lambda _sql, _params: returned)
    output = []
    monkeypatch.setattr(operator_cli, "get_connection", lambda: _context(transaction))
    monkeypatch.setattr(operator_cli, "print_json", output.append)

    operator_cli.revoke_scope(SimpleNamespace(
        grant_id=GRANT_ID,
        revoked_by=" local-admin ",
        reason=" operator access ended ",
    ))

    sql, params = transaction.statements[0]
    assert "set revoked_at = now(), revoked_by = :revoked_by" in sql
    assert "revocation_reason = :reason" in sql
    assert params == {"grant_id": GRANT_ID, "revoked_by": "local-admin", "reason": "operator access ended"}
    assert output == [returned]
    assert transaction.committed is True
    assert transaction.rolled_back is False


@pytest.mark.parametrize(
    "field,value",
    [("revoked_by", "  "), ("reason", "  ")],
)
def test_scope_revocation_rejects_missing_audit_text_before_database_access(monkeypatch, field, value):
    def unexpected_connection():
        raise AssertionError("invalid audit input must fail before connecting")

    monkeypatch.setattr(operator_cli, "get_connection", unexpected_connection)
    args = {"grant_id": GRANT_ID, "revoked_by": "local-admin", "reason": "reviewed"}
    args[field] = value

    with pytest.raises(ValueError, match="revoked-by and reason are required"):
        operator_cli.revoke_scope(SimpleNamespace(**args))


def test_membership_revocation_attributes_cascaded_scope_grants(monkeypatch):
    membership = {
        "id": "membership-id",
        "operator_id": OPERATOR_ID,
        "organization_id": ORGANIZATION_ID,
        "revoked_by": "tenant-admin",
        "revocation_reason": "operator left organization",
    }

    def execute(sql, _params):
        if sql.startswith("update operator_organization_membership"):
            return membership
        if sql.startswith("update operator_scope_grant"):
            return None
        raise AssertionError(f"unexpected SQL: {sql}")

    transaction = Transaction(execute)
    output = []
    monkeypatch.setattr(operator_cli, "get_connection", lambda: _context(transaction))
    monkeypatch.setattr(operator_cli, "print_json", output.append)

    operator_cli.revoke_organization_membership(SimpleNamespace(
        membership_id="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        revoked_by=" tenant-admin ",
        reason=" operator left organization ",
    ))

    sql, params = transaction.statements[1]
    assert "set revoked_at = now(), revoked_by = :revoked_by" in sql
    assert "revocation_reason = :reason" in sql
    assert params == {
        "operator_id": OPERATOR_ID,
        "organization_id": ORGANIZATION_ID,
        "revoked_by": "tenant-admin",
        "reason": "operator left organization",
    }
    assert output == [membership]
    assert transaction.committed is True


def test_share_revocation_attributes_cascaded_scope_grants(monkeypatch):
    share = {
        "share_id": "share-id",
        "location_id": LOCATION_ID,
        "organization_id": ORGANIZATION_ID,
        "owner_organization_id": "ffffffff-ffff-4fff-8fff-ffffffffffff",
    }
    revoked_share = {
        "id": "share-id",
        "location_id": LOCATION_ID,
        "organization_id": ORGANIZATION_ID,
        "revocation_reason": "partnership ended",
    }

    def execute(sql, _params):
        if sql.startswith("select share.id as share_id"):
            return share
        if sql.startswith("select 1 from operator_identity as identity"):
            return {"1": 1}
        if sql.startswith("update location_organization_share"):
            return revoked_share
        if sql.startswith("update operator_scope_grant"):
            return None
        raise AssertionError(f"unexpected SQL: {sql}")

    transaction = Transaction(execute)
    output = []
    monkeypatch.setattr(operator_cli, "get_connection", lambda: _context(transaction))
    monkeypatch.setattr(operator_cli, "print_json", output.append)

    operator_cli.revoke_location_share(SimpleNamespace(
        share_id="99999999-9999-4999-8999-999999999999",
        revoked_by_operator_id="12121212-1212-4212-8212-121212121212",
        reason=" partnership ended ",
    ))

    sql, params = transaction.statements[3]
    assert "set revoked_at = now(), revoked_by = :revoked_by" in sql
    assert "revocation_reason = :reason" in sql
    assert params == {
        "location_id": LOCATION_ID,
        "organization_id": ORGANIZATION_ID,
        "revoked_by": "12121212-1212-4212-8212-121212121212",
        "reason": "partnership ended",
    }
    assert output == [revoked_share]
    assert transaction.committed is True
