"""Synthetic standalone/unified parity for the global alert-rule catalogue."""

import pytest
from typer.testing import CliRunner

import services.cli as unified_cli
from services.ingestion import anomaly_detector

LOCATION_ID = "a0000000-0000-0000-0000-000000000001"


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_exc_info):
        self.close()

    def execute(self, query, *_args):
        self.query = query

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, rows):
        self.cursor_instance = _Cursor(rows)
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


def test_global_rule_listing_matches_across_clis(monkeypatch, capsys):
    rows = [
        (
            "rule-id",
            "Synthetic soil alert",
            "soil_moisture",
            "soil_moisture",
            "<",
            20,
            "warning",
            True,
            False,
            60,
        )
    ]
    connections = []
    messages = []

    def make_connection():
        connection = _Connection(rows)
        connections.append(connection)
        return connection

    monkeypatch.setattr(anomaly_detector, "get_db", make_connection)
    monkeypatch.setattr(
        anomaly_detector.logger,
        "info",
        lambda message, *args: messages.append(message % args if args else message),
    )

    anomaly_detector.main(["--list-rules"])
    standalone_output = capsys.readouterr().out
    standalone_messages = list(messages)
    messages.clear()
    unified = CliRunner().invoke(
        unified_cli.app,
        ["ingestion", "--", "anomaly_detector", "--list-rules"],
    )

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output == ""
    assert messages == standalone_messages
    assert len(connections) == 2
    for connection in connections:
        assert connection.closed
        assert connection.cursor_instance.closed
        assert "FROM alert_rule" in connection.cursor_instance.query
        assert "location_id" not in connection.cursor_instance.query
    assert unified.stderr == ""


@pytest.mark.parametrize("selector", ["--location-id", "--all-locations"])
@pytest.mark.parametrize("entrypoint", ["standalone", "unified"])
def test_global_rule_listing_rejects_location_selectors_before_database(
    monkeypatch, entrypoint, selector
):
    monkeypatch.setattr(
        anomaly_detector,
        "get_db",
        lambda: pytest.fail("global rule listing with a location selector must fail before DB setup"),
    )
    arguments = ["--list-rules", selector]
    if selector == "--location-id":
        arguments.append(LOCATION_ID)

    if entrypoint == "standalone":
        with pytest.raises(SystemExit) as exc_info:
            anomaly_detector.main(arguments)
        assert exc_info.value.code == 2
    else:
        result = CliRunner().invoke(
            unified_cli.app,
            ["ingestion", "--", "anomaly_detector", *arguments],
        )
        assert result.exit_code == 2
        assert "does not accept a location selector" in result.output
