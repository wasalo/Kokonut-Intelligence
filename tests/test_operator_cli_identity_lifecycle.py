"""Transactional behavior for local operator identity disablement."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from services.gateway import operator_cli

OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
DISABLED_BY = "local-admin@example.test"
REASON = "Access ended after operator role change."


class Result:
    def __init__(self, row=None):
        self.row = row

    def first(self):
        return self.row


class Transaction:
    def __init__(self, *, fail_on_session_revoke=False, fail_on_audit=False,
                 omit_audit_receipt=False):
        self.statements = []
        self.fail_on_session_revoke = fail_on_session_revoke
        self.fail_on_audit = fail_on_audit
        self.omit_audit_receipt = omit_audit_receipt
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc, _traceback):
        self.rolled_back = exc_type is not None
        self.committed = exc_type is None
        return False

    def execute(self, sql, parameters=None):
        normalized = " ".join(sql.lower().split())
        self.statements.append((normalized, parameters or {}))
        if normalized.startswith("update operator_identity"):
            return Result({"id": OPERATOR_ID, "enabled": False})
        if normalized.startswith("update operator_session"):
            if self.fail_on_session_revoke:
                raise RuntimeError("synthetic session update failure")
            return Result()
        if normalized.startswith("insert into operator_identity_admin_audit"):
            if self.fail_on_audit:
                raise RuntimeError("synthetic audit insert failure")
            if self.omit_audit_receipt:
                return Result()
            return Result({"id": "audit-id", "database_principal": "kokonut"})
        raise AssertionError(f"unexpected SQL: {normalized}")


@contextmanager
def _connection_context(transaction):
    with transaction:
        yield transaction


def test_disabling_identity_revokes_sessions_in_same_transaction(monkeypatch):
    transaction = Transaction()
    output = []
    monkeypatch.setattr(
        operator_cli,
        "get_connection",
        lambda: _connection_context(transaction),
    )
    monkeypatch.setattr(operator_cli, "print_json", output.append)

    operator_cli.disable_identity(SimpleNamespace(
        operator_id=OPERATOR_ID,
        disabled_by=DISABLED_BY,
        reason=REASON,
    ))

    assert transaction.statements[0][0].startswith("update operator_identity")
    assert transaction.statements[1][0].startswith("update operator_session")
    assert transaction.statements[2][0].startswith(
        "insert into operator_identity_admin_audit"
    )
    assert transaction.statements[0][1] == {"operator_id": OPERATOR_ID}
    assert transaction.statements[1][1] == {"operator_id": OPERATOR_ID}
    assert transaction.statements[2][1] == {
        "operator_id": OPERATOR_ID,
        "actor_label": DISABLED_BY,
        "reason": REASON,
    }
    assert "enabled = false" in transaction.statements[0][0]
    assert "revoked_at = now()" in transaction.statements[1][0]
    assert output == [{
        "identity": {"id": OPERATOR_ID, "enabled": False},
        "audit": {"id": "audit-id", "database_principal": "kokonut"},
    }]
    assert transaction.committed is True
    assert transaction.rolled_back is False


def test_session_revocation_failure_rolls_back_identity_disable(monkeypatch):
    transaction = Transaction(fail_on_session_revoke=True)
    output = []
    monkeypatch.setattr(
        operator_cli,
        "get_connection",
        lambda: _connection_context(transaction),
    )
    monkeypatch.setattr(operator_cli, "print_json", output.append)

    with pytest.raises(RuntimeError, match="synthetic session update failure"):
        operator_cli.disable_identity(SimpleNamespace(
            operator_id=OPERATOR_ID,
            disabled_by=DISABLED_BY,
            reason=REASON,
        ))

    assert len(transaction.statements) == 2
    assert transaction.committed is False
    assert transaction.rolled_back is True
    assert output == []


def test_audit_insert_failure_rolls_back_identity_and_session_changes(monkeypatch):
    transaction = Transaction(fail_on_audit=True)
    output = []
    monkeypatch.setattr(
        operator_cli,
        "get_connection",
        lambda: _connection_context(transaction),
    )
    monkeypatch.setattr(operator_cli, "print_json", output.append)

    with pytest.raises(RuntimeError, match="synthetic audit insert failure"):
        operator_cli.disable_identity(SimpleNamespace(
            operator_id=OPERATOR_ID,
            disabled_by=DISABLED_BY,
            reason=REASON,
        ))

    assert len(transaction.statements) == 3
    assert transaction.committed is False
    assert transaction.rolled_back is True
    assert output == []


def test_missing_audit_receipt_rolls_back_inside_transaction(monkeypatch):
    transaction = Transaction(omit_audit_receipt=True)
    output = []
    monkeypatch.setattr(
        operator_cli,
        "get_connection",
        lambda: _connection_context(transaction),
    )
    monkeypatch.setattr(operator_cli, "print_json", output.append)

    with pytest.raises(RuntimeError, match="audit was not recorded"):
        operator_cli.disable_identity(SimpleNamespace(
            operator_id=OPERATOR_ID,
            disabled_by=DISABLED_BY,
            reason=REASON,
        ))

    assert len(transaction.statements) == 3
    assert transaction.committed is False
    assert transaction.rolled_back is True
    assert output == []


@pytest.mark.parametrize(
    ("disabled_by", "reason"),
    [(" ", REASON), ("a" * 201, REASON), (DISABLED_BY, " "), (DISABLED_BY, "r" * 2001)],
)
def test_disable_audit_text_is_validated_before_connecting(
    monkeypatch, disabled_by, reason
):
    monkeypatch.setattr(
        operator_cli,
        "get_connection",
        lambda: pytest.fail("invalid audit input must not connect to the database"),
    )

    with pytest.raises(ValueError):
        operator_cli.disable_identity(SimpleNamespace(
            operator_id=OPERATOR_ID,
            disabled_by=disabled_by,
            reason=reason,
        ))
