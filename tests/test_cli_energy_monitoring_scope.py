"""Energy source CLI rejects malformed location IDs before DB setup."""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.analytics import cli_energy_monitoring


def test_add_source_rejects_invalid_location_before_cli_runner(monkeypatch):
    argv = [
        "add-source",
        "--location-id",
        "not-a-uuid",
        "--name",
        "Solar array",
        "--type",
        "solar",
    ]
    runner = Mock()
    connection_factory = Mock()
    monkeypatch.setattr(cli_energy_monitoring.cli, "run", runner)
    monkeypatch.setattr(
        cli_energy_monitoring.cli, "_connection_factory", connection_factory
    )

    with pytest.raises(SystemExit) as error:
        cli_energy_monitoring.main(argv)

    assert error.value.code == 2
    runner.assert_not_called()
    connection_factory.assert_not_called()


def test_add_source_valid_location_reaches_existing_runner(monkeypatch):
    argv = ["add-source", "--location-id", str(uuid4()), "--name", "Solar array", "--type", "solar"]
    runner = Mock()
    monkeypatch.setattr(cli_energy_monitoring.cli, "run", runner)

    cli_energy_monitoring.main(argv)

    runner.assert_called_once_with(argv)


def test_help_still_exits_before_cli_runner(monkeypatch, capsys):
    runner = Mock()
    monkeypatch.setattr(cli_energy_monitoring.cli, "run", runner)

    with pytest.raises(SystemExit) as error:
        cli_energy_monitoring.main(["--help"])

    assert error.value.code == 0
    assert "add-source" in capsys.readouterr().out
    runner.assert_not_called()
