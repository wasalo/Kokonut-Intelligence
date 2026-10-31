"""Farmer-identity optional location scopes fail before database setup."""

from datetime import date, datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.analytics import cli_farmer_identity


@pytest.mark.parametrize(
    "argv",
    [
        ["create-profile", "--first-name", "Test", "--location-id", "invalid"],
        ["list-farmers", "--location-id", "invalid"],
        [
            "assign-role",
            "--farmer-id",
            str(uuid4()),
            "--role",
            "observer",
            "--location-id",
            "invalid",
        ],
        [
            "register-device",
            "--farmer-id",
            str(uuid4()),
            "--device-id",
            "synthetic-device",
            "--device-type",
            "mobile",
            "--location-id",
            "invalid",
        ],
        ["access-matrix", "--location-id", "invalid"],
        ["directory", "--location-id", "invalid"],
    ],
)
def test_invalid_optional_location_fails_before_database_runner(monkeypatch, argv):
    runner = Mock()
    connection_factory = Mock()
    monkeypatch.setattr(cli_farmer_identity.cli, "run", runner)
    monkeypatch.setattr(cli_farmer_identity.cli, "_connection_factory", connection_factory)

    with pytest.raises(SystemExit) as error:
        cli_farmer_identity.main(argv)

    assert error.value.code == 2
    runner.assert_not_called()
    connection_factory.assert_not_called()


@pytest.mark.parametrize(
    "argv",
    [
        ["list-farmers"],
        ["directory", "--location-id", str(uuid4())],
        ["access-matrix", "--location-id", str(uuid4())],
    ],
)
def test_valid_or_omitted_optional_location_keeps_existing_dispatch(monkeypatch, argv):
    runner = Mock(return_value="dispatched")
    monkeypatch.setattr(cli_farmer_identity.cli, "run", runner)

    assert cli_farmer_identity.main(argv) == "dispatched"
    runner.assert_called_once_with(argv)


@pytest.mark.parametrize(
    "prefix",
    [
        ["create-profile", "--first-name", "Test"],
        ["list-farmers"],
        ["assign-role", "--farmer-id", str(uuid4()), "--role", "observer"],
        [
            "register-device",
            "--farmer-id",
            str(uuid4()),
            "--device-id",
            "synthetic-device",
            "--device-type",
            "mobile",
        ],
        ["access-matrix"],
        ["directory"],
    ],
)
def test_supplied_location_is_canonicalized_before_database_runner(prefix, monkeypatch):
    location_id = uuid4()
    argv = [*prefix, "--location-id", location_id.hex.upper()]
    expected_argv = [*prefix, "--location-id", str(location_id)]
    runner = Mock(return_value="dispatched")
    monkeypatch.setattr(cli_farmer_identity.cli, "run", runner)

    assert cli_farmer_identity.main(argv) == "dispatched"

    runner.assert_called_once_with(expected_argv)


def test_equals_form_location_is_canonicalized_before_database_runner(monkeypatch):
    location_id = uuid4()
    argv = ["list-farmers", f"--location-id={location_id.hex.upper()}"]
    runner = Mock()
    monkeypatch.setattr(cli_farmer_identity.cli, "run", runner)

    cli_farmer_identity.main(argv)

    runner.assert_called_once_with(["list-farmers", f"--location-id={location_id}"])


@pytest.mark.parametrize(
    "argv",
    [
        ["create-profile", "--first-name", "Test", "--dob", "not-a-date"],
        ["update-profile", "--farmer-id", "farmer-1", "--dob", "2026-02-30"],
        [
            "add-credential", "--farmer-id", "farmer-1", "--type", "organic",
            "--name", "Certificate", "--issued-date", "2026-02-30",
        ],
        [
            "add-credential", "--farmer-id", "farmer-1", "--type", "organic",
            "--name", "Certificate", "--expiry-date", "not-a-date",
        ],
        [
            "assign-role", "--farmer-id", "farmer-1", "--role", "observer",
            "--expires-at", "not-a-datetime",
        ],
    ],
)
def test_malformed_date_values_fail_before_database_access(monkeypatch, capsys, argv):
    connection_factory = Mock()
    monkeypatch.setattr(
        cli_farmer_identity.cli, "_connection_factory", connection_factory
    )

    with pytest.raises(SystemExit) as error:
        cli_farmer_identity.main(argv)

    assert error.value.code == 2
    assert "must be a valid ISO" in capsys.readouterr().err
    connection_factory.assert_not_called()


def test_create_profile_forwards_parsed_date(monkeypatch):
    connection = Mock()
    handler = Mock(return_value={"created": True})
    monkeypatch.setattr(
        cli_farmer_identity.cli, "_connection_factory", lambda: connection
    )
    monkeypatch.setattr(cli_farmer_identity, "create_profile", handler)

    cli_farmer_identity.main(
        ["create-profile", "--first-name", "Test", "--dob", "1980-05-12"]
    )

    assert handler.call_args.kwargs["date_of_birth"] == date(1980, 5, 12)
    connection.close.assert_called_once()


def test_update_profile_forwards_parsed_date(monkeypatch):
    connection = Mock()
    handler = Mock(return_value={"updated": True})
    monkeypatch.setattr(
        cli_farmer_identity.cli, "_connection_factory", lambda: connection
    )
    monkeypatch.setattr(cli_farmer_identity, "update_profile", handler)

    cli_farmer_identity.main(
        ["update-profile", "--farmer-id", "farmer-1", "--dob", "1980-05-12"]
    )

    assert handler.call_args.args[2]["date_of_birth"] == date(1980, 5, 12)
    connection.close.assert_called_once()


def test_add_credential_forwards_parsed_dates(monkeypatch):
    connection = Mock()
    handler = Mock(return_value={"created": True})
    monkeypatch.setattr(
        cli_farmer_identity.cli, "_connection_factory", lambda: connection
    )
    monkeypatch.setattr(cli_farmer_identity, "add_credential", handler)

    cli_farmer_identity.main(
        [
            "add-credential", "--farmer-id", "farmer-1", "--type", "organic",
            "--name", "Certificate", "--issued-date", "2025-01-15",
            "--expiry-date", "2027-01-15",
        ]
    )

    assert handler.call_args.kwargs["issued_date"] == date(2025, 1, 15)
    assert handler.call_args.kwargs["expiry_date"] == date(2027, 1, 15)
    connection.close.assert_called_once()


def test_assign_role_forwards_parsed_datetime(monkeypatch):
    connection = Mock()
    handler = Mock(return_value={"assigned": True})
    monkeypatch.setattr(
        cli_farmer_identity.cli, "_connection_factory", lambda: connection
    )
    monkeypatch.setattr(cli_farmer_identity, "assign_role", handler)

    cli_farmer_identity.main(
        [
            "assign-role", "--farmer-id", "farmer-1", "--role", "observer",
            "--expires-at", "2027-01-15T10:30:00+00:00",
        ]
    )

    assert handler.call_args.kwargs["expires_at"] == datetime(
        2027, 1, 15, 10, 30, tzinfo=timezone.utc
    )
    connection.close.assert_called_once()
