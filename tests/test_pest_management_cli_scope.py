"""Location-scoped IPM commands reject malformed scope before database setup."""

from unittest.mock import Mock

import pytest

from services.analytics import cli_pest_management


@pytest.mark.parametrize(
    "argv",
    [
        ["record-scouting", "--location-id", "bad", "--pest", "aphid"],
        ["set-threshold", "--location-id", "bad", "--pest", "aphid"],
        ["check-threshold", "--location-id", "bad", "--pest", "aphid", "--count", "1"],
        ["record-intervention", "--location-id", "bad", "--type", "cultural"],
        ["record-pesticide", "--location-id", "bad", "--product", "synthetic"],
        ["record-resistance", "--location-id", "bad", "--pest", "aphid", "--class", "pyrethroid", "--level", "high"],
        ["record-degree-day", "--location-id", "bad", "--pest", "aphid"],
        ["summary", "--location-id", "bad"],
        ["pesticide-usage", "--location-id", "bad"],
        ["degree-day-tracking", "--location-id", "bad", "--pest", "aphid"],
        ["dashboard", "--location-id", "bad"],
        ["create-schedule", "--location-id", "bad", "--pest", "aphid"],
        ["due-scouting", "--location-id", "bad"],
        ["compliance-report", "--location-id", "bad"],
        ["compliance-score", "--location-id", "bad"],
        ["add-trap", "--location-id", "bad", "--name", "trap", "--type", "sticky"],
        ["check-rotation", "--location-id", "bad", "--class", "pyrethroid"],
        ["rotation-history", "--location-id", "bad"],
        ["spray-windows", "--location-id", "bad", "--pest", "aphid"],
        ["organic-pest-score", "--location-id", "bad"],
        ["generate-audit", "--location-id", "bad"],
    ],
)
def test_location_commands_reject_invalid_uuid_before_connection(monkeypatch, argv, capsys):
    connection_calls = []

    def connect():
        connection_calls.append(True)
        raise AssertionError("database connection must not be opened")

    monkeypatch.setattr(cli_pest_management.cli, "_connection_factory", connect)

    with pytest.raises(SystemExit) as exc_info:
        cli_pest_management.main(argv)

    assert exc_info.value.code == 2
    assert "--location-id must be a valid UUID" in capsys.readouterr().err
    assert connection_calls == []


def test_non_location_command_does_not_require_a_location_id(monkeypatch):
    connection = Mock()
    handler = Mock(return_value=[])
    monkeypatch.setattr(cli_pest_management.cli, "_connection_factory", lambda: connection)
    monkeypatch.setattr(cli_pest_management, "list_pest_references", handler)

    cli_pest_management.main(["list-references"])

    handler.assert_called_once_with(connection, pest_category=None, host_crop=None)
    connection.close.assert_called_once()


@pytest.mark.parametrize(
    "argv, operation",
    [
        (
            ["record-scouting", "--location-id", "A0000000-0000-4000-8000-000000000001",
             "--pest", "aphid", "--json"],
            "record_scouting",
        ),
        (["summary", "--location-id", "A0000000-0000-4000-8000-000000000001", "--json"],
         "get_pest_summary"),
        (
            ["add-trap", "--location-id", "A0000000-0000-4000-8000-000000000001",
             "--name", "synthetic", "--type", "sticky", "--json"],
            "add_trap",
        ),
        (["generate-audit", "--location-id", "A0000000-0000-4000-8000-000000000001", "--json"],
         "generate_ipm_audit"),
    ],
)
def test_valid_uppercase_location_is_canonical_before_database_handler(
    monkeypatch, argv, operation
):
    canonical_location = "a0000000-0000-4000-8000-000000000001"
    connection = Mock()
    handler = Mock(return_value={})
    monkeypatch.setattr(cli_pest_management.cli, "_connection_factory", lambda: connection)
    monkeypatch.setattr(cli_pest_management, operation, handler)

    cli_pest_management.main(argv)

    assert handler.call_args.args[1] == canonical_location
    connection.close.assert_called_once()
