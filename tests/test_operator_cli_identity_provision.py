"""Fail-closed behavior for local OIDC identity provisioning."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from services.gateway import operator_cli


class Result:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class Connection:
    def __init__(self, row):
        self.row = row
        self.query = ""
        self.parameters = None
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc, _traceback):
        self.rolled_back = exc_type is not None
        return False

    def execute(self, query, parameters):
        self.query = " ".join(query.lower().split())
        self.parameters = parameters
        return Result(self.row)


@contextmanager
def _connection_context(connection):
    with connection:
        yield connection


def _arguments(**overrides):
    values = {
        "issuer": "https://identity.example.test",
        "subject": "subject-123",
        "display_name": "Operator One",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_provision_does_not_reenable_a_disabled_identity(monkeypatch):
    connection = Connection(row=None)
    monkeypatch.setattr(
        operator_cli,
        "get_connection",
        lambda: _connection_context(connection),
    )

    with pytest.raises(ValueError, match="disabled; provisioning will not re-enable"):
        operator_cli.provision_identity(_arguments())

    assert "where operator_identity.enabled = true" in connection.query
    update = connection.query.split("do update set", maxsplit=1)[1].split("where", maxsplit=1)[0]
    assert "enabled = true" not in update
    assert connection.parameters == {
        "issuer": "https://identity.example.test",
        "subject": "subject-123",
        "display_name": "Operator One",
    }
    assert connection.rolled_back is True


def test_provision_refreshes_an_existing_enabled_identity_without_changing_state(
    monkeypatch,
):
    identity = {
        "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "issuer": "https://identity.example.test",
        "subject": "subject-123",
        "display_name": "Updated Name",
        "enabled": True,
    }
    connection = Connection(row=identity)
    output = []
    monkeypatch.setattr(
        operator_cli,
        "get_connection",
        lambda: _connection_context(connection),
    )
    monkeypatch.setattr(operator_cli, "print_json", output.append)

    operator_cli.provision_identity(_arguments(display_name="Updated Name"))

    update = connection.query.split("do update set", maxsplit=1)[1].split("where", maxsplit=1)[0]
    assert "display_name = coalesce(excluded.display_name" in update
    assert "updated_at = now()" in update
    assert "enabled" not in update
    assert output == [identity]
    assert connection.rolled_back is False
