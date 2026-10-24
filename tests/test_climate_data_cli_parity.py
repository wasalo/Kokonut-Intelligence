"""Standalone/unified parity for explicitly selected climate CLI operations."""

import json

import pytest

from services.ingestion import climate_data

LOCATION_ID = "12345678-1234-5678-1234-567812345678"


class _Connection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    ("arguments", "operation", "result"),
    [
        (["--worldclim"], "fetch_worldclim", {"dataset": "worldclim", "status": "success"}),
        (["--ncep"], "fetch_ncep", {"dataset": "ncep", "status": "success"}),
        (["--modis"], "fetch_modis", {"dataset": "modis", "status": "success"}),
        (["--smap"], "fetch_smap", {"dataset": "smap", "status": "success"}),
        (["--sentinel1"], "fetch_sentinel1", {"dataset": "sentinel1", "status": "success"}),
        (["--all"], "run_all", {"status": "success", "total": 5}),
    ],
)
def test_climate_cli_success_receipts_match_standalone_and_unified(
    monkeypatch, capsys, arguments, operation, result
):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    connections = []
    calls = []

    def make_connection():
        connection = _Connection()
        connections.append(connection)
        return connection

    def fake_operation(connection, location_id):
        calls.append((connection, location_id))
        return result

    monkeypatch.setattr(climate_data, "get_db", make_connection)
    monkeypatch.setattr(climate_data, operation, fake_operation)
    full_arguments = [*arguments, "--location-id", LOCATION_ID]

    assert climate_data.main(full_arguments) == 0
    standalone_output = capsys.readouterr().out
    standalone_calls = list(calls)
    calls.clear()
    unified = CliRunner().invoke(
        unified_cli.app, ["ingestion", "--", "climate_data", *full_arguments]
    )

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert json.loads(unified.output) == result
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert len(standalone_calls) == len(calls) == 1
    assert standalone_calls[0][1] == calls[0][1] == LOCATION_ID
    assert standalone_calls[0][0] is connections[0]
    assert calls[0][0] is connections[1]
    assert unified.stderr == ""


@pytest.mark.parametrize("entrypoint", ["standalone", "unified"])
def test_climate_cli_rejects_multiple_datasets_before_database(monkeypatch, entrypoint):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    monkeypatch.setattr(
        climate_data,
        "get_db",
        lambda: pytest.fail("conflicting climate selectors must fail before DB access"),
    )
    arguments = [
        "--worldclim",
        "--modis",
        "--location-id",
        LOCATION_ID,
    ]

    if entrypoint == "standalone":
        with pytest.raises(SystemExit) as exc_info:
            climate_data.main(arguments)
        assert exc_info.value.code == 2
    else:
        result = CliRunner().invoke(
            unified_cli.app, ["ingestion", "--", "climate_data", *arguments]
        )
        assert result.exit_code == 2
        assert "not allowed with argument" in result.output
