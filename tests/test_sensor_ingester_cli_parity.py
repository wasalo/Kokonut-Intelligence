"""Synthetic parity checks for location-scoped sensor inventory CLI reads."""

import pytest

from services.ingestion import sensor_ingester


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
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


@pytest.mark.parametrize(
    ("arguments", "rows", "expected_messages"),
    [
        (
            ["--list", "--location-id", "12345678-1234-5678-1234-567812345678"],
            [
                (
                    "sensor-id",
                    "Synthetic soil probe",
                    "soil-01",
                    "sensor-type-id",
                    "soil_moisture",
                    "12345678-1234-5678-1234-567812345678",
                    None,
                    "active",
                    "manual",
                )
            ],
            [
                "1 active sensors:",
                "  Synthetic soil probe | soil_moisture | 12345678 | manual | sensor-id",
            ],
        ),
        (
            [
                "--calibration",
                "--location-id",
                "12345678-1234-5678-1234-567812345678",
            ],
            [("Synthetic soil probe", "soil_moisture", None, 365, "Genesis")],
            [
                "Calibration status for 1 active sensors:",
                "  Synthetic soil probe | soil_moisture | Genesis | No calibration date set",
            ],
        ),
    ],
)
def test_sensor_inventory_output_matches_standalone_and_unified(
    monkeypatch, arguments, rows, expected_messages
):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    connections = []
    messages = []

    def make_connection():
        connection = _Connection(rows)
        connections.append(connection)
        return connection

    def record_log(message, *args):
        messages.append(message % args if args else message)

    monkeypatch.setattr(sensor_ingester, "get_db", make_connection)
    monkeypatch.setattr(sensor_ingester.logger, "info", record_log)

    sensor_ingester.main(arguments)
    standalone_messages = list(messages)
    messages.clear()
    unified = CliRunner().invoke(
        unified_cli.app, ["ingestion", "--", "sensor_ingester", *arguments]
    )

    assert unified.exit_code == 0, unified.output
    assert messages == standalone_messages == expected_messages
    assert len(connections) == 2
    for connection in connections:
        assert connection.closed
        assert connection.cursor_instance.closed
        assert "sd.location_id = %s" in connection.cursor_instance.query
        assert connection.cursor_instance.params == (
            "12345678-1234-5678-1234-567812345678",
        )
    assert unified.stderr == ""


@pytest.mark.parametrize("entrypoint", ["standalone", "unified"])
@pytest.mark.parametrize("location_id", [None, "not-a-uuid"])
def test_sensor_inventory_rejects_invalid_location_before_database(
    monkeypatch, entrypoint, location_id
):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    monkeypatch.setattr(
        sensor_ingester,
        "get_db",
        lambda: pytest.fail("invalid sensor scope must fail before database access"),
    )
    arguments = ["--list"]
    if location_id is not None:
        arguments.extend(["--location-id", location_id])

    if entrypoint == "standalone":
        with pytest.raises(SystemExit) as exc_info:
            sensor_ingester.main(arguments)
        assert exc_info.value.code == 2
    else:
        result = CliRunner().invoke(
            unified_cli.app, ["ingestion", "--", "sensor_ingester", *arguments]
        )
        assert result.exit_code == 2
        assert "location" in result.output.lower()


@pytest.mark.parametrize(
    ("arguments", "operation", "expected"),
    [
        (
            [
                "--sensor",
                "soil-01",
                "--value",
                "12.5",
                "--location-id",
                "12345678-1234-5678-1234-567812345678",
            ],
            "run_single",
            (
                "soil-01",
                12.5,
                None,
                None,
                "12345678-1234-5678-1234-567812345678",
            ),
        ),
        (
            [
                "--file",
                "synthetic-readings.csv",
                "--location-id",
                "12345678-1234-5678-1234-567812345678",
            ],
            "run_csv",
            ("synthetic-readings.csv", "12345678-1234-5678-1234-567812345678"),
        ),
        (
            [
                "--driver-instance-id",
                "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "--location-id",
                "12345678-1234-5678-1234-567812345678",
            ],
            "run_driver_instance",
            (
                "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "12345678-1234-5678-1234-567812345678",
            ),
        ),
    ],
)
def test_sensor_write_and_driver_cli_arguments_match_across_entrypoints(
    monkeypatch, capsys, arguments, operation, expected
):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    calls = []
    monkeypatch.setattr(
        sensor_ingester,
        operation,
        lambda *args: calls.append(args),
    )

    sensor_ingester.main(arguments)
    standalone_output = capsys.readouterr().out
    standalone_calls = list(calls)
    calls.clear()
    unified = CliRunner().invoke(
        unified_cli.app, ["ingestion", "--", "sensor_ingester", *arguments]
    )

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert calls == standalone_calls == [expected]
    assert unified.stderr == ""
