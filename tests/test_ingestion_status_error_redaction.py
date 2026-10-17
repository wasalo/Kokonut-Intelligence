"""Persisted ingestion errors must be redacted in status CLI output."""

import subprocess
import sys
from types import SimpleNamespace

import pytest

from services.ingestion import status

DIAGNOSTIC = "synthetic provider diagnostic marker"


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def execute(self, query, _params=None):
        self.query = query

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self, rows):
        self.cursor_instance = _Cursor(rows)
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
