"""Explicit-scope preflight for the tactical analytics CLI."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.analytics import cli


@pytest.mark.parametrize(
    "flag",
    (
        "--promotion-ladder",
        "--zwischenzug",
        "--propose-zwischenzug",
        "--tactical-layer",
    ),
)
def test_tactical_cli_requires_explicit_scope_before_database_access(
    monkeypatch, flag
):
    monkeypatch.setattr(sys, "argv", ["analytics", flag])
    with patch("services.analytics.cli.get_connection") as get_connection:
        with pytest.raises(SystemExit) as error:
            cli.main()

    assert error.value.code == 2
    get_connection.assert_not_called()


@pytest.mark.parametrize(
    "flag",
    (
        "--promotion-ladder",
        "--zwischenzug",
        "--propose-zwischenzug",
        "--tactical-layer",
    ),
)
def test_tactical_cli_rejects_malformed_location_before_database_access(
    monkeypatch, flag
):
    monkeypatch.setattr(
        sys, "argv", ["analytics", flag, "--location-id", "not-a-uuid"]
    )
    with patch("services.analytics.cli.get_connection") as get_connection:
        with pytest.raises(SystemExit) as error:
            cli.main()

    assert error.value.code == 2
    get_connection.assert_not_called()


@pytest.mark.parametrize("attr, _module, _function", cli._DB_LOCATION_COMMANDS)
def test_database_location_commands_reject_malformed_uuid_before_connection(
    monkeypatch, attr, _module, _function
):
    flag = "--" + attr.replace("_", "-")
    monkeypatch.setattr(
        sys,
        "argv",
        ["analytics", flag, "--location-id", "not-a-uuid"],
    )
    with patch("services.analytics.cli.get_connection") as get_connection:
        with pytest.raises(SystemExit) as error:
            cli.main()

    assert error.value.code == 2
    get_connection.assert_not_called()


def test_database_location_command_canonicalizes_uuid_before_query(monkeypatch):
    location_id = "A0000000-0000-4000-8000-000000000001"
    canonical_location_id = location_id.lower()
    connection = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = connection
    context.__exit__.return_value = False
    monkeypatch.setattr(
        sys,
        "argv",
        ["analytics", "--soil-carbon", "--location-id", location_id],
    )

    with patch("services.analytics.cli.get_connection", return_value=context), patch(
        "services.analytics.ecology.compare_soil_carbon", return_value={}
    ) as compare_soil_carbon, patch("services.analytics.cli.print_json"):
        cli.main()

    compare_soil_carbon.assert_called_once_with(connection, canonical_location_id)


def test_database_location_command_preserves_missing_scope_error(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["analytics", "--soil-carbon"])
    with patch("services.analytics.cli.get_connection") as get_connection:
        with pytest.raises(SystemExit) as error:
            cli.main()

    assert error.value.code == 2
    get_connection.assert_not_called()


def test_tactical_layer_requires_one_location_not_all_locations(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["analytics", "--tactical-layer", "--all-locations"],
    )
    with patch("services.analytics.cli.get_connection") as get_connection:
        with pytest.raises(SystemExit) as error:
            cli.main()

    assert error.value.code == 2
    get_connection.assert_not_called()


def test_scope_flags_cannot_select_location_and_all_locations_together(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["analytics", "--promotion-ladder", "--all-locations", "--location-id", str(uuid4())],
    )
    with patch("services.analytics.cli.get_connection") as get_connection:
        with pytest.raises(SystemExit) as error:
            cli.main()

    assert error.value.code == 2
    get_connection.assert_not_called()


@pytest.mark.parametrize("flag", ("--promotion-ladder", "--zwischenzug", "--propose-zwischenzug"))
def test_supported_network_scope_requires_explicit_all_locations(monkeypatch, flag):
    monkeypatch.setattr(sys, "argv", ["analytics", flag, "--all-locations"])
    connection = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = connection
    context.__exit__.return_value = False

    with patch("services.analytics.cli.get_connection", return_value=context), patch(
        "services.analytics.cli.print_json"
    ), patch(
        "services.analytics.promotion_ladder.compute_promotion_ladder", return_value={}
    ) as promotion, patch(
        "services.feedback.automation.detect_zwischenzug", return_value={}
    ) as detect, patch(
        "services.feedback.automation.propose_zwischenzug", return_value={}
    ) as propose:
        cli.main()

    if flag == "--promotion-ladder":
        promotion.assert_called_once_with(connection, location_id=None)
    elif flag == "--zwischenzug":
        detect.assert_called_once_with(connection, location_id=None)
    else:
        propose.assert_called_once_with(
            connection, location_id=None, actor="cli"
        )
