"""CLI contract for the read-only DAO framework catalogue."""

from __future__ import annotations

import json
from types import SimpleNamespace

from typer.testing import CliRunner

import services.cli as unified_cli
from services.governance import cli as governance_cli


class _Cursor:
    def fetchall(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(framework_key="moloch_v3_baal", is_active=True)]


class _Connection:
    def __init__(self) -> None:
        self.closed = False

    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.closed = True

    def execute(self, query: str) -> _Cursor:
        assert query == "SELECT framework_key, is_active FROM governance_framework"
        return _Cursor()


def test_documented_framework_list_matches_standalone_and_unified_cli(monkeypatch) -> None:
    connections: list[_Connection] = []

    def open_connection() -> _Connection:
        connection = _Connection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(governance_cli, "get_connection", open_connection)
    runner = CliRunner()

    standalone = runner.invoke(governance_cli.app, ["framework", "list"])
    unified = runner.invoke(unified_cli.app, ["dao", "framework", "list"])

    assert standalone.exit_code == 0, standalone.output
    assert unified.exit_code == 0, unified.output
    assert json.loads(standalone.stdout) == json.loads(unified.stdout)
    baal = next(
        row for row in json.loads(unified.stdout) if row["key"] == "moloch_v3_baal"
    )
    assert baal["is_active"] is True
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)


def test_legacy_framework_command_without_list_argument_remains_supported(monkeypatch) -> None:
    connection = _Connection()
    monkeypatch.setattr(governance_cli, "get_connection", lambda: connection)

    result = CliRunner().invoke(governance_cli.app, ["framework"])

    assert result.exit_code == 0, result.output
    assert any(
        row["key"] == "moloch_v3_baal" for row in json.loads(result.stdout)
    )
    assert connection.closed is True


def test_unknown_framework_action_fails_before_database_access(monkeypatch) -> None:
    connection_opened = False

    def unexpected_connection() -> _Connection:
        nonlocal connection_opened
        connection_opened = True
        return _Connection()

    monkeypatch.setattr(governance_cli, "get_connection", unexpected_connection)

    result = CliRunner().invoke(governance_cli.app, ["framework", "delete"])

    assert result.exit_code != 0
    assert "framework supports only the 'list' action" in str(result.exception)
    assert connection_opened is False
