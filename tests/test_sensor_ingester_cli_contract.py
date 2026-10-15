"""The sensor CLI must not report a successful no-op for absent source input."""

import os
import subprocess
import sys

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
        (["--file", "readings.csv"], "run_csv", ("readings.csv",)),
        (["--sensor", "sensor-1", "--value", "12.5"], "run_single", ("sensor-1", 12.5, None, None)),
        (["--sensor", "sensor-1", "--value", "12.5", "--date", "2026-01-01", "--time", "08:30:00"],
         "run_single", ("sensor-1", 12.5, "2026-01-01", "08:30:00")),
        (["--list"], "list_sensors", ()),
        (["--calibration"], "list_calibration_status", ()),
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
