"""The sensor CLI must not report a successful no-op for absent source input."""

import os
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

from services.ingestion import sensor_ingester


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--sensor", "sensor-1"],
        ["--value", "12.5"],
        ["--date", "2026-01-01"],
        ["--file", "readings.csv", "--sensor", "sensor-1", "--value", "12.5"],
        ["--list", "--calibration"],
        ["--file", "readings.csv"],
        ["--sensor", "sensor-1", "--value", "12.5"],
        ["--list"],
        ["--calibration"],
        ["--file", "readings.csv", "--location-id", "not-a-uuid"],
    ],
)
def test_missing_or_conflicting_source_arguments_fail_before_database_access(
    arguments, monkeypatch, capsys
):
    monkeypatch.setattr(
        sensor_ingester,
        "get_db",
        lambda: pytest.fail("invalid sensor CLI input must fail before database access"),
    )

    with pytest.raises(SystemExit) as error:
        sensor_ingester.main(arguments)

    assert error.value.code == 2
    assert "error:" in capsys.readouterr().err


def test_help_and_missing_input_do_not_load_sops_or_database_configuration():
    environment = os.environ.copy()
    environment["SOPS_AGE_KEY_FILE"] = "/path/that/does/not/exist"

    help_result = subprocess.run(
        [sys.executable, "-m", "services.ingestion.sensor_ingester", "--help"],
        capture_output=True,
        text=True,
        timeout=15,
        env=environment,
    )
    empty_result = subprocess.run(
        [sys.executable, "-m", "services.ingestion.sensor_ingester"],
        capture_output=True,
        text=True,
        timeout=15,
        env=environment,
    )

    assert help_result.returncode == 0
    assert "usage:" in help_result.stdout
    assert empty_result.returncode == 2
    assert "choose exactly one" in empty_result.stderr
    assert "SecretLoadError" not in empty_result.stderr


@pytest.mark.parametrize(
    ("arguments", "operation", "expected"),
    [
        (["--file", "readings.csv", "--location-id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
         "run_csv", ("readings.csv", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")),
        (["--sensor", "sensor-1", "--value", "12.5", "--location-id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
         "run_single", ("sensor-1", 12.5, None, None, "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")),
        (["--sensor", "sensor-1", "--value", "12.5", "--date", "2026-01-01", "--time", "08:30:00",
          "--location-id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
         "run_single", ("sensor-1", 12.5, "2026-01-01", "08:30:00", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")),
        (["--list", "--location-id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
         "list_sensors", ("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",)),
        (["--calibration", "--location-id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
         "list_calibration_status", ("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",)),
    ],
)
def test_explicit_sensor_cli_operations_keep_their_existing_dispatch(
    arguments, operation, expected, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        sensor_ingester,
        operation,
        lambda *args: calls.append(args),
    )

    sensor_ingester.main(arguments)

    assert calls == [expected]


def test_sensor_lookup_binds_the_explicit_location_to_the_device_query():
    location_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value

    sensor_ingester.get_sensor_by_id_or_slug(connection, "soil-probe", location_id)

    sql, parameters = cursor.execute.call_args.args
    assert "AND sd.location_id = %s" in sql
    assert parameters == ("soil-probe", "soil-probe", location_id)


def test_sensor_lookup_rejects_invalid_location_before_opening_a_cursor():
    connection = MagicMock()

    with pytest.raises(ValueError, match="location_id must be a UUID"):
        sensor_ingester.get_sensor_by_id_or_slug(connection, "soil-probe", "not-a-uuid")

    connection.cursor.assert_not_called()


@pytest.mark.parametrize(
    "operation",
    ["run_csv", "run_single"],
)
def test_sensor_ingestion_helpers_require_scope_before_opening_database(operation, monkeypatch):
    monkeypatch.setattr(
        sensor_ingester,
        "get_db",
        lambda: pytest.fail("unscoped sensor ingestion must fail before database access"),
    )

    with pytest.raises(ValueError, match="explicit location UUID"):
        if operation == "run_csv":
            sensor_ingester.run_csv("readings.csv")
        else:
            sensor_ingester.run_single("sensor-1", 12.5)
