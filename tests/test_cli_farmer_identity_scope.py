"""Farmer-identity optional location scopes fail before database setup."""

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
