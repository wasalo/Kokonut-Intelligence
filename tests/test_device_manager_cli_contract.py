"""Safe CLI contract checks for location-scoped device inventory reads."""

import json

import pytest

from services.ingestion import device_manager


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.params = None
        self.closed = False

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, rows):
        self.cursor_instance = _Cursor(rows)
        self.closed = False

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    ("arguments", "row", "query_marker", "expected_params", "expected_output"),
    [
        (
            ["--list", "--location-id", "12345678-1234-5678-1234-567812345678"],
            {
                "id": "device-id",
                "name": "Synthetic soil sensor",
                "slug": "soil-01",
                "status": "active",
                "sensor_type": "soil_moisture",
                "connectivity": "online",
            },
            "WHERE sd.location_id = %s",
            ["12345678-1234-5678-1234-567812345678"],
            "list",
        ),
        (
            [
                "--health",
                "--device-id",
                "soil-01",
                "--location-id",
                "12345678-1234-5678-1234-567812345678",
            ],
            {
                "name": "Synthetic soil sensor",
                "slug": "soil-01",
                "sensor_type": "soil_moisture",
                "connectivity": "online",
            },
            "WHERE (sd.slug = %s OR sd.id::text = %s)",
            (
                "soil-01",
                "soil-01",
                "12345678-1234-5678-1234-567812345678",
            ),
            "health",
        ),
    ],
)
def test_device_read_cli_output_and_location_filter_match(
    monkeypatch,
    capsys,
    arguments,
    row,
    query_marker,
    expected_params,
    expected_output,
):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    connections = []

    def make_connection():
        connection = _Connection([row])
        connections.append(connection)
        return connection

    monkeypatch.setattr(device_manager, "get_db", make_connection)

    device_manager.main(arguments)
    standalone_output = capsys.readouterr().out
    unified = CliRunner().invoke(
        unified_cli.app, ["ingestion", "--", "device_manager", *arguments]
    )

    assert unified.exit_code == 0, unified.output
    expected = [row] if expected_output == "list" else row
    assert json.loads(unified.output) == json.loads(standalone_output) == expected
    assert len(connections) == 2
    for connection in connections:
        assert connection.closed
        assert connection.cursor_instance.closed
        assert query_marker in connection.cursor_instance.query
        assert connection.cursor_instance.params == expected_params
    assert unified.stderr == ""


@pytest.mark.parametrize("entrypoint", ["standalone", "unified"])
@pytest.mark.parametrize("location_id", [None, "not-a-uuid"])
@pytest.mark.parametrize(
    "operation", [["--list"], ["--health", "--device-id", "soil-01"]]
)
def test_device_list_cli_rejects_missing_or_invalid_location_before_database(
    monkeypatch, entrypoint, location_id, operation
):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    database_calls = []

    def unexpected_database_access():
        database_calls.append(True)
        raise AssertionError("database must not be opened for invalid scope")

    monkeypatch.setattr(device_manager, "get_db", unexpected_database_access)
    arguments = list(operation)
    if location_id is not None:
        arguments.extend(["--location-id", location_id])

    if entrypoint == "standalone":
        with pytest.raises(SystemExit) as exc_info:
            device_manager.main(arguments)
        assert exc_info.value.code == 2
    else:
        result = CliRunner().invoke(
            unified_cli.app,
            ["ingestion", "--", "device_manager", *arguments],
        )
        assert result.exit_code == 2
        assert "location" in result.output.lower()

    assert database_calls == []
