"""Persisted ingestion errors must be redacted in status CLI output."""

import subprocess
import sys
from types import SimpleNamespace

import pytest

from services.ingestion import status

DIAGNOSTIC = "synthetic provider diagnostic marker"


class _Cursor:
    def __init__(self, rows, fail_execute=False):
        self.rows = rows
        self.fail_execute = fail_execute
        self.query = None
        self.params = None
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def execute(self, query, params=None):
        self.query = query
        self.params = params
        if self.fail_execute:
            raise RuntimeError("synthetic query failure")

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self, rows, fail_execute=False):
        self.cursor_instance = _Cursor(rows, fail_execute=fail_execute)
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


def test_status_cli_help_does_not_load_database_or_secrets():
    completed = subprocess.run(
        [sys.executable, "-s", "-m", "services.ingestion.status", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0
    assert "Ingestion status monitoring" in completed.stdout
    assert "log" in completed.stdout


@pytest.mark.parametrize(
    ("query", "row", "args"),
    [
        (
            status.query_ingestion_log,
            ("provider", "farm", "failed", DIAGNOSTIC, 0, 10, "2026-10-17"),
            SimpleNamespace(source=None, status_filter=None, errors_only=True, limit=5),
        ),
        (
            status.query_indexer_status,
            ("celo", "eas", 12, "error", DIAGNOSTIC, "2026-10-17"),
            SimpleNamespace(),
        ),
    ],
)
def test_status_output_redacts_persisted_error_and_closes_connection(
    monkeypatch, capsys, query, row, args
):
    conn = _Connection([row])
    monkeypatch.setattr(status, "get_db", lambda: conn)

    query(args)

    output = capsys.readouterr().out
    assert DIAGNOSTIC not in output
    assert "[details redacted]" in output
    assert conn.closed
    assert conn.cursor_instance.closed
    if query is status.query_ingestion_log:
        assert "status = 'failed'" in conn.cursor_instance.query


@pytest.mark.parametrize(
    ("query", "args"),
    [
        (
            status.query_ingestion_log,
            SimpleNamespace(source=None, status_filter=None, errors_only=False, limit=5),
        ),
        (status.query_indexer_status, SimpleNamespace()),
        (status.show_summary, SimpleNamespace()),
    ],
)
def test_status_queries_close_connection_when_query_fails(monkeypatch, query, args):
    conn = _Connection([], fail_execute=True)
    monkeypatch.setattr(status, "get_db", lambda: conn)

    with pytest.raises(RuntimeError, match="synthetic query failure"):
        query(args)

    assert conn.cursor_instance.closed
    assert conn.closed


@pytest.mark.parametrize(
    ("arguments", "row", "expected_params", "redacts_diagnostics"),
    [
        (
            [
                "log",
                "--source",
                "synthetic-provider",
                "--status",
                "failed",
                "--errors-only",
                "--limit",
                "7",
            ],
            (
                "synthetic-provider",
                "synthetic-table",
                "failed",
                DIAGNOSTIC,
                0,
                12,
                "2026-10-21 10:00:00",
            ),
            ["synthetic-provider", "failed", 7],
            True,
        ),
        (
            ["indexers"],
            ("synthetic-chain", "synthetic-indexer", 12, "error", DIAGNOSTIC, "2026-10-21"),
            None,
            True,
        ),
        (
            ["summary"],
            ("synthetic-provider", "success", 2, 10),
            None,
            False,
        ),
    ],
)
def test_ingestion_status_standalone_and_unified_output_match(
    monkeypatch, capsys, arguments, row, expected_params, redacts_diagnostics
):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    connections = []

    def make_connection():
        connection = _Connection([row])
        connections.append(connection)
        return connection

    monkeypatch.setattr(status, "get_db", make_connection)

    status.main(arguments)
    standalone_output = capsys.readouterr().out
    unified = CliRunner().invoke(
        unified_cli.app, ["ingestion", "--", "status", *arguments]
    )

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    if redacts_diagnostics:
        assert "[details redacted]" in unified.output
        assert DIAGNOSTIC not in unified.output
    assert len(connections) == 2
    for connection in connections:
        assert connection.closed
        assert connection.cursor_instance.closed
        if expected_params is not None:
            assert "source_system = %s" in connection.cursor_instance.query
            assert "status = %s" in connection.cursor_instance.query
        assert connection.cursor_instance.params == expected_params
    assert unified.stderr == ""
