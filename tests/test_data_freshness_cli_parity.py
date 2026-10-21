"""Synthetic standalone/unified parity for data-freshness summary reads."""

import json

import pytest
from typer.testing import CliRunner

import services.cli as unified_cli
from services.ingestion import data_freshness


class _Cursor:
    def __init__(self, rows, fail_at=None):
        self.rows = rows
        self.fail_at = fail_at
        self.query = None
        self.closed = False

    def execute(self, query, *_args):
        self.query = query
        if self.fail_at == "execute":
            raise RuntimeError("synthetic freshness query failure")

    def fetchall(self):
        if self.fail_at == "fetchall":
            raise RuntimeError("synthetic freshness fetch failure")
        return self.rows

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, rows, fail_at=None):
        self.cursor_instance = _Cursor(rows, fail_at=fail_at)
        self.closed = False

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def close(self):
        self.closed = True


def test_freshness_summary_matches_across_standalone_and_unified_clis(
    monkeypatch, capsys
):
    rows = [
        {
            "source_system": "weather",
            "location_name": "Synthetic farm",
            "status": "fresh",
            "gap_minutes": 5,
        }
    ]
    connections = []

    def make_connection():
        connection = _Connection(rows)
        connections.append(connection)
        return connection

    monkeypatch.setattr(data_freshness, "get_db", make_connection)

    data_freshness.main(["--summary"])
    standalone_output = capsys.readouterr().out
    unified = CliRunner().invoke(
        unified_cli.app,
        ["ingestion", "--", "data_freshness", "--summary"],
    )

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert json.loads(unified.output) == rows
    assert len(connections) == 2
    for connection in connections:
        assert connection.cursor_instance.query == "SELECT * FROM v_data_freshness_summary"
        assert connection.cursor_instance.closed
        assert connection.closed
    assert unified.stderr == ""


@pytest.mark.parametrize("failure_stage", ["execute", "fetchall"])
@pytest.mark.parametrize("entrypoint", ["standalone", "unified"])
def test_freshness_summary_failure_closes_cursor_and_connection(
    monkeypatch, entrypoint, failure_stage
):
    connection = _Connection([], fail_at=failure_stage)
    monkeypatch.setattr(data_freshness, "get_db", lambda: connection)

    if entrypoint == "standalone":
        with pytest.raises(RuntimeError, match="synthetic freshness"):
            data_freshness.main(["--summary"])
    else:
        result = CliRunner().invoke(
            unified_cli.app,
            ["ingestion", "--", "data_freshness", "--summary"],
        )
        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        assert result.exception.code == 1

    assert connection.cursor_instance.closed
    assert connection.closed
