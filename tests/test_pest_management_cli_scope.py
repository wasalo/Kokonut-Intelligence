"""Location-scoped IPM commands reject malformed scope before database setup."""

from datetime import date
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


@pytest.mark.parametrize(
    "argv",
    [
        ["record-scouting", "--location-id", "00000000-0000-4000-8000-000000000001", "--pest", "aphid", "--date", "bad-date"],
        ["record-intervention", "--location-id", "00000000-0000-4000-8000-000000000001", "--type", "cultural", "--date", "2026-02-30"],
        ["record-pesticide", "--location-id", "00000000-0000-4000-8000-000000000001", "--product", "synthetic", "--date", "bad-date"],
        ["record-resistance", "--location-id", "00000000-0000-4000-8000-000000000001", "--pest", "aphid", "--class", "pyrethroid", "--level", "high", "--date", "2026-02-30"],
        ["record-degree-day", "--location-id", "00000000-0000-4000-8000-000000000001", "--pest", "aphid", "--date", "bad-date"],
        ["create-schedule", "--location-id", "00000000-0000-4000-8000-000000000001", "--pest", "aphid", "--start-date", "2026-02-30"],
        ["create-schedule", "--location-id", "00000000-0000-4000-8000-000000000001", "--pest", "aphid", "--end-date", "bad-date"],
        ["record-compliance", "--schedule-id", "schedule-1", "--scouting-id", "scouting-1", "--date", "bad-date"],
        ["schedule-re-scout", "--intervention-id", "intervention-1", "--date", "2026-02-30"],
        ["compliance-score", "--location-id", "00000000-0000-4000-8000-000000000001", "--period-start", "2026-02-30"],
        ["compliance-score", "--location-id", "00000000-0000-4000-8000-000000000001", "--period-end", "bad-date"],
        ["add-trap", "--location-id", "00000000-0000-4000-8000-000000000001", "--name", "trap", "--type", "sticky", "--date", "bad-date"],
        ["record-catch", "--trap-id", "trap-1", "--date", "2026-02-30"],
        ["organic-pest-score", "--location-id", "00000000-0000-4000-8000-000000000001", "--period-start", "bad-date"],
        ["generate-audit", "--location-id", "00000000-0000-4000-8000-000000000001", "--period-end", "2026-02-30"],
    ],
)
def test_date_inputs_reject_invalid_values_before_database(monkeypatch, capsys, argv):
    connection_factory = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr(
        cli_pest_management.cli, "_connection_factory", connection_factory
    )

    with pytest.raises(SystemExit) as error:
        cli_pest_management.main(argv)

    assert error.value.code == 2
    assert "must be a valid ISO date" in capsys.readouterr().err
    connection_factory.assert_not_called()


def test_schedule_re_scout_forwards_parsed_date(monkeypatch):
    connection = Mock()
    handler = Mock(return_value={"scheduled": True})
    monkeypatch.setattr(
        cli_pest_management.cli, "_connection_factory", lambda: connection
    )
    monkeypatch.setattr(cli_pest_management, "schedule_re_scout", handler)

    cli_pest_management.main(
        ["schedule-re-scout", "--intervention-id", "intervention-1", "--date", "2026-02-28"]
    )

    handler.assert_called_once_with(connection, "intervention-1", date(2026, 2, 28))
    connection.close.assert_called_once_with()


def test_record_scouting_forwards_optional_parsed_date(monkeypatch):
    connection = Mock()
    handler = Mock(return_value={"recorded": True})
    monkeypatch.setattr(
        cli_pest_management.cli, "_connection_factory", lambda: connection
    )
    monkeypatch.setattr(cli_pest_management, "record_scouting", handler)

    cli_pest_management.main(
        [
            "record-scouting", "--location-id", "00000000-0000-4000-8000-000000000001",
            "--pest", "aphid", "--date", "2026-02-28",
        ]
    )

    assert handler.call_args.kwargs["scout_date"] == date(2026, 2, 28)
    connection.close.assert_called_once_with()


def test_create_schedule_forwards_parsed_date_range(monkeypatch):
    connection = Mock()
    handler = Mock(return_value={"scheduled": True})
    monkeypatch.setattr(
        cli_pest_management.cli, "_connection_factory", lambda: connection
    )
    monkeypatch.setattr(cli_pest_management, "create_scouting_schedule", handler)

    cli_pest_management.main(
        [
            "create-schedule", "--location-id", "00000000-0000-4000-8000-000000000001",
            "--pest", "aphid", "--start-date", "2026-02-01", "--end-date", "2026-03-01",
        ]
    )

    assert handler.call_args.kwargs["start_date"] == date(2026, 2, 1)
    assert handler.call_args.kwargs["end_date"] == date(2026, 3, 1)
    connection.close.assert_called_once_with()


def test_compliance_score_forwards_parsed_date_range(monkeypatch):
    connection = Mock()
    handler = Mock(return_value={"score": 1})
    monkeypatch.setattr(
        cli_pest_management.cli, "_connection_factory", lambda: connection
    )
    monkeypatch.setattr(cli_pest_management, "compute_ipm_compliance_score", handler)

    cli_pest_management.main(
        [
            "compliance-score", "--location-id", "00000000-0000-4000-8000-000000000001",
            "--period-start", "2026-02-01", "--period-end", "2026-03-01",
        ]
    )

    assert handler.call_args.args[2:] == (date(2026, 2, 1), date(2026, 3, 1))
    connection.close.assert_called_once_with()
