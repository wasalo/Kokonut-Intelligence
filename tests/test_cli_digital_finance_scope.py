"""Digital-finance CLI validates location scope before database setup."""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.analytics import cli_digital_finance


@pytest.mark.parametrize(
    "argv",
    [
        ["create-account", "--location-id", "not-a-uuid", "--type", "checking"],
        ["list", "--location-id", "not-a-uuid"],
        [
            "create-insurance", "--location-id", "not-a-uuid", "--product", "crop",
            "--coverage", "100", "--premium", "1",
        ],
        [
            "create-loan", "--location-id", "not-a-uuid", "--amount", "100",
            "--rate", "0.1", "--term", "12",
        ],
        ["portfolio", "--location-id", "not-a-uuid"],
        ["premium", "--location-id", "not-a-uuid", "--product", "crop", "--coverage", "100"],
        ["eligibility", "--location-id", "not-a-uuid", "--amount", "100"],
    ],
)
def test_location_scoped_commands_reject_invalid_uuid_before_cli_runner(monkeypatch, argv):
    runner = Mock()
    connection_factory = Mock()
    monkeypatch.setattr(cli_digital_finance.cli, "run", runner)
    monkeypatch.setattr(
        cli_digital_finance.cli, "_connection_factory", connection_factory
    )

    with pytest.raises(SystemExit) as error:
        cli_digital_finance.main(argv)

    assert error.value.code == 2
    runner.assert_not_called()
    connection_factory.assert_not_called()


@pytest.mark.parametrize(
    "command_args",
    [
        ["create-account", "--type", "checking"],
        ["list"],
        ["create-insurance", "--product", "crop", "--coverage", "100", "--premium", "1"],
        ["create-loan", "--amount", "100", "--rate", "0.1", "--term", "12"],
        ["portfolio"],
        ["premium", "--product", "crop", "--coverage", "100"],
        ["eligibility", "--amount", "100"],
    ],
)
def test_location_scoped_commands_require_location_before_cli_runner(monkeypatch, command_args):
    runner = Mock()
    monkeypatch.setattr(cli_digital_finance.cli, "run", runner)

    with pytest.raises(SystemExit) as error:
        cli_digital_finance.main(command_args)

    assert error.value.code == 2
    runner.assert_not_called()


def test_valid_location_reaches_existing_runner(monkeypatch):
    argv = ["portfolio", "--location-id", str(uuid4())]
    runner = Mock()
    monkeypatch.setattr(cli_digital_finance.cli, "run", runner)

    cli_digital_finance.main(argv)

    runner.assert_called_once_with(argv)


def test_non_location_account_command_keeps_existing_behavior(monkeypatch):
    argv = ["balance", "--account-id", "account-1"]
    runner = Mock()
    monkeypatch.setattr(cli_digital_finance.cli, "run", runner)

    cli_digital_finance.main(argv)

    runner.assert_called_once_with(argv)
