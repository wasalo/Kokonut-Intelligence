"""NOI snapshot reconciliation validates tenant scope before database access."""

import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.metrics import cli


def _invoke(arguments):
    with patch.object(sys, "argv", ["services.metrics", *arguments]):
        cli.main()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--reconcile-noi-snapshots"],
        ["--reconcile-noi-snapshots", "--location-id", "not-a-uuid"],
        ["--reconcile-noi-snapshots", "--location-id", str(uuid4()), "--compute"],
        ["--reconcile-noi-snapshots", "--location-id", str(uuid4()), "--all"],
    ],
)
def test_invalid_reconciliation_scope_fails_before_database_access(arguments):
    with patch("services.metrics.cli.get_connection") as get_connection:
        with pytest.raises(SystemExit) as error:
            _invoke(arguments)

    assert error.value.code == 2
    get_connection.assert_not_called()


def test_location_reconciliation_binds_canonical_location_for_both_sources():
    location_id = uuid4()
    result = MagicMock(rowcount=3)
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.execute.return_value = result

    with (
        patch("services.metrics.cli.get_connection", return_value=connection),
        patch("services.metrics.cli.print_json") as print_json,
    ):
        _invoke(["--reconcile-noi-snapshots", "--location-id", str(location_id).upper()])

    statement, parameters = connection.execute.call_args.args
    assert "AND v.location_id = :location_id" in statement
    assert "AND cc.location_id = :location_id" in statement
    assert parameters == {"location_id": str(location_id)}
    assert print_json.call_args.args[0]["scope"] == "location"
    assert print_json.call_args.args[0]["location_id"] == str(location_id)


def test_manual_all_location_reconciliation_is_explicit_and_unfiltered():
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.execute.return_value = MagicMock(rowcount=5)

    with (
        patch("services.metrics.cli.get_connection", return_value=connection),
        patch("services.metrics.cli.print_json") as print_json,
    ):
        _invoke(["--reconcile-noi-snapshots", "--all-locations"])

    statement, parameters = connection.execute.call_args.args
    assert "v.location_id = :location_id" not in statement
    assert "cc.location_id = :location_id" not in statement
    assert parameters == {}
    assert print_json.call_args.args[0]["scope"] == "all_locations"
    assert "location_id" not in print_json.call_args.args[0]


def test_location_and_aggregate_scopes_are_mutually_exclusive_before_database_access():
    with patch("services.metrics.cli.get_connection") as get_connection:
        with pytest.raises(SystemExit) as error:
            _invoke([
                "--reconcile-noi-snapshots",
                "--location-id",
                str(uuid4()),
                "--all-locations",
            ])

    assert error.value.code == 2
    get_connection.assert_not_called()
