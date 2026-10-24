"""Synthetic standalone/unified parity for current-weather ingestion."""

import pytest
from typer.testing import CliRunner

import services.cli as unified_cli
from services.ingestion import weather, weather_forecast

LOCATION_ID = "5e15b529-965d-4845-9c76-2f80fb781a8f"


class _Cursor:
    def __init__(self):
        self.query = None
        self.params = None
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_exc_info):
        self.close()

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchall(self):
        return []

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self):
        self.cursor_instance = _Cursor()
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    ("arguments", "expected_params", "expected_scope"),
    [
        pytest.param(
            ["--location-id", LOCATION_ID.upper()],
            (LOCATION_ID,),
            "WHERE id = %s AND status = 'active'",
            id="one-location",
        ),
        pytest.param(
            ["--all-locations"],
            None,
            "WHERE status = 'active'",
            id="explicit-all-locations",
        ),
    ],
)
def test_weather_cli_output_and_query_scope_match(
    monkeypatch, capsys, arguments, expected_params, expected_scope
):
    connections = []
    messages = []

    def make_connection():
        connection = _Connection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(weather, "OPENWEATHERMAP_API_KEY", "synthetic-key")
    monkeypatch.setattr(weather, "get_db", make_connection)
    monkeypatch.setattr(
        weather,
        "fetch_weather",
        lambda *_args: pytest.fail("empty synthetic location result must not contact provider"),
    )
    monkeypatch.setattr(weather.logger, "info", lambda message, *args: messages.append(message % args if args else message))

    weather.main(arguments)
    standalone_output = capsys.readouterr().out
    standalone_messages = list(messages)
    messages.clear()
    unified = CliRunner().invoke(unified_cli.app, ["ingestion", "--", "weather", *arguments])

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output == ""
    assert messages == standalone_messages
    assert len(connections) == 2
    for connection in connections:
        assert connection.closed
        assert connection.cursor_instance.closed
        assert expected_scope in connection.cursor_instance.query
        assert connection.cursor_instance.params == expected_params
    assert unified.stderr == ""


@pytest.mark.parametrize("entrypoint", ["standalone", "unified"])
def test_invalid_weather_location_fails_before_database(monkeypatch, entrypoint):
    monkeypatch.setattr(
        weather,
        "get_db",
        lambda: pytest.fail("invalid weather location must fail before DB setup"),
    )
    arguments = ["--location-id", "not-a-uuid"]

    if entrypoint == "standalone":
        with pytest.raises(SystemExit) as exc_info:
            weather.main(arguments)
        assert exc_info.value.code == 2
    else:
        result = CliRunner().invoke(unified_cli.app, ["ingestion", "--", "weather", *arguments])
        assert result.exit_code == 2
        assert "location_id must be a UUID" in result.output


@pytest.mark.parametrize(
    ("arguments", "expected_params", "expected_scope"),
    [
        pytest.param(
            ["--location-id", LOCATION_ID.upper()],
            (LOCATION_ID,),
            "WHERE id = %s AND status = 'active'",
            id="forecast-one-location",
        ),
        pytest.param(
            ["--all-locations"],
            None,
            "WHERE status = 'active'",
            id="forecast-explicit-all-locations",
        ),
    ],
)
def test_weather_forecast_cli_output_and_query_scope_match(
    monkeypatch, capsys, arguments, expected_params, expected_scope
):
    connections = []
    messages = []

    def make_connection():
        connection = _Connection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(weather_forecast, "OPENWEATHERMAP_API_KEY", "synthetic-key")
    monkeypatch.setattr(weather_forecast, "get_db", make_connection)
    monkeypatch.setattr(
        weather_forecast,
        "fetch_forecast_raw",
        lambda *_args: pytest.fail("empty synthetic location result must not contact provider"),
    )
    monkeypatch.setattr(
        weather_forecast.logger,
        "info",
        lambda message, *args: messages.append(message % args if args else message),
    )

    weather_forecast.main(arguments)
    standalone_output = capsys.readouterr().out
    standalone_messages = list(messages)
    messages.clear()
    unified = CliRunner().invoke(
        unified_cli.app, ["ingestion", "--", "weather_forecast", *arguments]
    )

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output == ""
    assert messages == standalone_messages
    assert len(connections) == 2
    for connection in connections:
        assert connection.closed
        assert connection.cursor_instance.closed
        assert expected_scope in connection.cursor_instance.query
        assert connection.cursor_instance.params == expected_params
    assert unified.stderr == ""


@pytest.mark.parametrize("entrypoint", ["standalone", "unified"])
def test_invalid_forecast_location_fails_before_database(monkeypatch, entrypoint):
    monkeypatch.setattr(
        weather_forecast,
        "get_db",
        lambda: pytest.fail("invalid forecast location must fail before DB setup"),
    )
    arguments = ["--location-id", "not-a-uuid"]

    if entrypoint == "standalone":
        with pytest.raises(SystemExit) as exc_info:
            weather_forecast.main(arguments)
        assert exc_info.value.code == 2
    else:
        result = CliRunner().invoke(
            unified_cli.app,
            ["ingestion", "--", "weather_forecast", *arguments],
        )
        assert result.exit_code == 2
        assert "location_id must be a UUID" in result.output
