"""Crop-rotation CLI location scope fails before shared database dispatch."""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.analytics import cli_crop_rotation


@pytest.mark.parametrize(
    "argv",
    [
        ["create-plan", "--location-id", "invalid", "--name", "Rotation"],
        ["list-plans", "--location-id", "invalid"],
        ["family-usage", "--location-id", "invalid"],
        ["recommend", "--location-id", "invalid"],
        ["dashboard", "--location-id", "invalid"],
        ["record-impact", "--location-id", "invalid"],
    ],
)
def test_invalid_location_fails_before_cli_runner(argv, monkeypatch):
    runner = Mock()
    connection_factory = Mock()
    monkeypatch.setattr(cli_crop_rotation.cli, "run", runner)
    monkeypatch.setattr(
        cli_crop_rotation.cli, "_connection_factory", connection_factory
    )

    with pytest.raises(SystemExit) as error:
        cli_crop_rotation.main(argv)

    assert error.value.code == 2
    runner.assert_not_called()
    connection_factory.assert_not_called()


def test_valid_required_location_is_forwarded_to_existing_runner(monkeypatch):
    argv = ["list-plans", "--location-id", str(uuid4())]
    runner = Mock()
    monkeypatch.setattr(cli_crop_rotation.cli, "run", runner)

    cli_crop_rotation.main(argv)

    runner.assert_called_once_with(argv)


@pytest.mark.parametrize(
    "prefix",
    [
        ["create-plan", "--name", "Rotation"],
        ["list-plans"],
        ["family-usage"],
        ["recommend"],
        ["dashboard"],
        ["record-impact"],
    ],
)
def test_valid_location_is_canonicalized_before_cli_runner(prefix, monkeypatch):
    location_id = uuid4()
    supplied_location_id = location_id.hex.upper()
    argv = [*prefix, "--location-id", supplied_location_id]
    expected_argv = [*prefix, "--location-id", str(location_id)]
    runner = Mock()
    monkeypatch.setattr(cli_crop_rotation.cli, "run", runner)

    cli_crop_rotation.main(argv)

    runner.assert_called_once_with(expected_argv)


def test_equals_form_location_is_canonicalized_before_cli_runner(monkeypatch):
    location_id = uuid4()
    argv = ["list-plans", f"--location-id={location_id.hex.upper()}"]
    runner = Mock()
    monkeypatch.setattr(cli_crop_rotation.cli, "run", runner)

    cli_crop_rotation.main(argv)

    runner.assert_called_once_with(["list-plans", f"--location-id={location_id}"])


def test_record_impact_keeps_location_optional(monkeypatch):
    argv = ["record-impact"]
    runner = Mock()
    monkeypatch.setattr(cli_crop_rotation.cli, "run", runner)

    cli_crop_rotation.main(argv)

    runner.assert_called_once_with(argv)


def test_help_still_exits_before_cli_runner(monkeypatch, capsys):
    runner = Mock()
    monkeypatch.setattr(cli_crop_rotation.cli, "run", runner)

    with pytest.raises(SystemExit) as error:
        cli_crop_rotation.main(["--help"])

    assert error.value.code == 0
    assert "create-plan" in capsys.readouterr().out
    runner.assert_not_called()
