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


def test_valid_uppercase_location_is_canonical_before_database_handler(monkeypatch):
    supplied_location = "A0000000-0000-4000-8000-000000000001"
    canonical_location = supplied_location.lower()
    connection = Mock()
    connection_factory = Mock(return_value=connection)
    summary = Mock(return_value={"location_id": canonical_location})
    monkeypatch.setattr(
        cli_digital_finance.cli, "_connection_factory", connection_factory
    )
    monkeypatch.setattr(cli_digital_finance, "get_portfolio_summary", summary)

    cli_digital_finance.main(
        ["portfolio", "--location-id", supplied_location]
    )

    summary.assert_called_once_with(connection, canonical_location)
    connection.close.assert_called_once_with()


def test_non_location_account_command_keeps_existing_behavior(monkeypatch):
    argv = ["balance", "--account-id", "account-1"]
    runner = Mock()
    monkeypatch.setattr(cli_digital_finance.cli, "run", runner)

    cli_digital_finance.main(argv)

    runner.assert_called_once_with(argv)


def test_file_claim_rejects_malformed_evidence_json_before_database_setup(monkeypatch):
    argv = [
        "file-claim", "--policy-id", "policy-1", "--type", "hail", "--amount", "10",
        "--evidence", "{not-json}",
    ]
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


def test_file_claim_passes_decoded_evidence_to_handler(monkeypatch):
    argv = [
        "file-claim", "--policy-id", "policy-1", "--type", "hail", "--amount", "10",
        "--evidence", '{"invoice":"photo-1","measurements":[1,2]}',
    ]
    connection = Mock()
    connection_factory = Mock(return_value=connection)
    claim = Mock(return_value={"claim_id": "claim-1"})
    output = Mock()
    monkeypatch.setattr("services.common.commands.print_json", output)
    monkeypatch.setattr(
        cli_digital_finance.cli, "_connection_factory", connection_factory
    )
    monkeypatch.setattr(cli_digital_finance, "file_insurance_claim", claim)

    cli_digital_finance.main(argv)

    claim.assert_called_once_with(
        connection, "policy-1", "hail", 10.0,
        evidence={"invoice": "photo-1", "measurements": [1, 2]},
        event_date=None, description=None,
    )
    output.assert_called_once_with({"claim_id": "claim-1"})
    connection.close.assert_called_once_with()
