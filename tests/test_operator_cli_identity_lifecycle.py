"""Transactional behavior for local operator identity disablement."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from services.gateway import operator_cli

OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


class Result:
    def __init__(self, row=None):
        self.row = row

    def first(self):
        return self.row


class Transaction:
    def __init__(self, *, fail_on_session_revoke=False):
        self.statements = []
        self.fail_on_session_revoke = fail_on_session_revoke
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

    operator_cli.disable_identity(SimpleNamespace(operator_id=OPERATOR_ID))

    assert [sql.split(" ", 3)[1] for sql, _params in transaction.statements] == [
        "operator_identity",
        "operator_session",
    ]
    assert all(params == {"operator_id": OPERATOR_ID} for _sql, params in transaction.statements)
    assert "enabled = false" in transaction.statements[0][0]
    assert "revoked_at = now()" in transaction.statements[1][0]
    assert output == [{"id": OPERATOR_ID, "enabled": False}]
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
        operator_cli.disable_identity(SimpleNamespace(operator_id=OPERATOR_ID))

    assert len(transaction.statements) == 2
    assert transaction.committed is False
    assert transaction.rolled_back is True
    assert output == []
