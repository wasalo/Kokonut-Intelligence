"""Pollinator CLI location scope fails before the shared DB runner opens."""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.analytics import cli_pollinator_health


@pytest.mark.parametrize(
    "argv",
    [
        ["summary", "--location-id", "not-a-uuid"],
        ["habitat-inventory", "--location-id", "not-a-uuid"],
        ["pesticide-risk", "--location-id", "not-a-uuid"],
        ["hive-status", "--location-id", "not-a-uuid"],
        ["dashboard", "--location-id", "not-a-uuid"],
    ],
)
def test_invalid_db_read_location_fails_before_runner(argv, monkeypatch):
    runner = Mock()
    connection_factory = Mock()
    monkeypatch.setattr(cli_pollinator_health.cli, "run", runner)
    monkeypatch.setattr(
        cli_pollinator_health.cli, "_connection_factory", connection_factory
    )

    with pytest.raises(SystemExit) as error:
        cli_pollinator_health.main(argv)

    assert error.value.code == 2
    runner.assert_not_called()
    connection_factory.assert_not_called()


@pytest.mark.parametrize(
    "command",
    ["summary", "habitat-inventory", "pesticide-risk", "hive-status", "dashboard"],
)
def test_valid_db_read_location_is_canonical_before_runner(command, monkeypatch):
    location_id = uuid4()
    argv = [command, "--location-id", location_id.hex.upper()]
    expected_argv = [command, "--location-id", str(location_id)]
    runner = Mock()
    monkeypatch.setattr(cli_pollinator_health.cli, "run", runner)

    cli_pollinator_health.main(argv)

    runner.assert_called_once_with(expected_argv)


def test_equals_form_db_read_location_is_canonical_before_runner(monkeypatch):
    location_id = uuid4()
    runner = Mock()
    monkeypatch.setattr(cli_pollinator_health.cli, "run", runner)

    cli_pollinator_health.main(
        ["summary", f"--location-id={location_id.hex.upper()}"]
    )

    runner.assert_called_once_with(["summary", f"--location-id={location_id}"])


def test_retired_write_command_remains_outside_db_read_preflight(monkeypatch):
    argv = [
        "record-observation",
        "--location-id",
        "legacy-location",
        "--type",
        "wild_bee",
        "--count",
        "1",
    ]
    runner = Mock()
    monkeypatch.setattr(cli_pollinator_health.cli, "run", runner)

    cli_pollinator_health.main(argv)

    runner.assert_called_once_with(argv)


def test_help_still_exits_before_cli_runner(monkeypatch, capsys):
    runner = Mock()
    monkeypatch.setattr(cli_pollinator_health.cli, "run", runner)

    with pytest.raises(SystemExit) as error:
        cli_pollinator_health.main(["--help"])

    assert error.value.code == 0
    assert "summary" in capsys.readouterr().out
    runner.assert_not_called()
