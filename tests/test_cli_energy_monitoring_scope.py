"""Energy source CLI rejects malformed location IDs before DB setup."""

from datetime import date
from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.analytics import cli_energy_monitoring


@pytest.mark.parametrize(
    "argv, option",
    [
        (
            [
                "add-source", "--location-id", str(uuid4()), "--name", "Solar array",
                "--type", "solar", "--installation-date", "not-a-date",
            ],
            "--installation-date",
        ),
        (
            [
                "record", "--source-id", "source", "--type", "consumption",
                "--kwh", "1", "--date", "2026-02-30",
            ],
            "--date",
        ),
    ],
)
def test_date_arguments_reject_malformed_values_before_database_access(
    monkeypatch, capsys, argv, option
):
    runner = Mock()
    connection_factory = Mock()
    monkeypatch.setattr(cli_energy_monitoring.cli, "run", runner)
    monkeypatch.setattr(
        cli_energy_monitoring.cli, "_connection_factory", connection_factory
    )

    with pytest.raises(SystemExit) as error:
        cli_energy_monitoring.main(argv)

    assert error.value.code == 2
    assert option in capsys.readouterr().err
    runner.assert_not_called()
    connection_factory.assert_not_called()


@pytest.mark.parametrize(
    "argv, operation, expected_date, keyword",
    [
        (
            [
                "add-source", "--location-id", str(uuid4()), "--name", "Solar array",
                "--type", "solar", "--installation-date", "2026-02-28", "--json",
            ],
            "add_source",
            date(2026, 2, 28),
            "installation_date",
        ),
        (
            [
                "record", "--source-id", "source", "--type", "consumption",
                "--kwh", "1", "--date", "2026-02-28", "--json",
            ],
            "record_reading",
            date(2026, 2, 28),
            None,
        ),
    ],
)
def test_valid_iso_date_reaches_domain_handler(
    monkeypatch, argv, operation, expected_date, keyword
):
    connection = Mock()
    handler = Mock(return_value={})
    monkeypatch.setattr(
        cli_energy_monitoring.cli, "_connection_factory", lambda: connection
    )
    monkeypatch.setattr(cli_energy_monitoring, operation, handler)

    cli_energy_monitoring.main(argv)

    if keyword:
        assert handler.call_args.kwargs[keyword] == expected_date
    else:
        assert handler.call_args.args[2] == expected_date
    connection.close.assert_called_once()


@pytest.mark.parametrize("installation_date", [None, ""])
def test_add_source_missing_or_empty_date_keeps_none_fallback(
    monkeypatch, installation_date
):
    argv = [
        "add-source", "--location-id", str(uuid4()), "--name", "Solar array",
        "--type", "solar", "--json",
    ]
    if installation_date is not None:
        argv.extend(["--installation-date", installation_date])
    connection = Mock()
    handler = Mock(return_value={})
    monkeypatch.setattr(
        cli_energy_monitoring.cli, "_connection_factory", lambda: connection
    )
    monkeypatch.setattr(cli_energy_monitoring, "add_source", handler)

    cli_energy_monitoring.main(argv)

    assert handler.call_args.kwargs["installation_date"] is None
    connection.close.assert_called_once()


@pytest.mark.parametrize("reading_date", [None, ""])
def test_record_missing_or_empty_date_keeps_today_fallback(
    monkeypatch, reading_date
):
    today = date(2026, 10, 29)

    class FixedDate:
        @staticmethod
        def fromisoformat(value):
            return date.fromisoformat(value)

        @staticmethod
        def today():
            return today

    argv = ["record", "--source-id", "source", "--type", "consumption", "--kwh", "1", "--json"]
    if reading_date is not None:
        argv.extend(["--date", reading_date])
    connection = Mock()
    handler = Mock(return_value={})
    monkeypatch.setattr(cli_energy_monitoring, "date", FixedDate)
    monkeypatch.setattr(
        cli_energy_monitoring.cli, "_connection_factory", lambda: connection
    )
    monkeypatch.setattr(cli_energy_monitoring, "record_reading", handler)

    cli_energy_monitoring.main(argv)

    assert handler.call_args.args[2] == today
    connection.close.assert_called_once()


@pytest.mark.parametrize(
    "argv",
    [
        ["add-source", "--location-id", "not-a-uuid", "--name", "Solar array", "--type", "solar"],
        ["add-renewable", "--location-id", "not-a-uuid", "--source-id", "source", "--renewable-type", "solar_pv", "--capacity", "1"],
        ["consumption", "--location-id", "not-a-uuid"],
        ["efficiency", "--location-id", "not-a-uuid"],
        ["renewable-summary", "--location-id", "not-a-uuid"],
        ["dashboard", "--location-id", "not-a-uuid"],
        ["carbon-intensity", "--location-id", "not-a-uuid"],
        ["cost-analysis", "--location-id", "not-a-uuid"],
    ],
)
def test_location_scoped_commands_reject_invalid_uuid_before_cli_runner(monkeypatch, argv):
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


def test_add_renewable_valid_location_reaches_existing_runner(monkeypatch):
    argv = [
        "add-renewable", "--location-id", str(uuid4()), "--source-id", "source",
        "--renewable-type", "solar_pv", "--capacity", "1",
    ]
    runner = Mock()
    monkeypatch.setattr(cli_energy_monitoring.cli, "run", runner)

    cli_energy_monitoring.main(argv)

    runner.assert_called_once_with(argv)


def test_location_scoped_command_still_requires_location_before_cli_runner(monkeypatch):
    runner = Mock()
    monkeypatch.setattr(cli_energy_monitoring.cli, "run", runner)

    with pytest.raises(SystemExit) as error:
        cli_energy_monitoring.main(["consumption"])

    assert error.value.code == 2
    runner.assert_not_called()


def test_help_still_exits_before_cli_runner(monkeypatch, capsys):
    runner = Mock()
    monkeypatch.setattr(cli_energy_monitoring.cli, "run", runner)

    with pytest.raises(SystemExit) as error:
        cli_energy_monitoring.main(["--help"])

    assert error.value.code == 0
    assert "add-source" in capsys.readouterr().out
    runner.assert_not_called()


@pytest.mark.parametrize(
    "argv, operation",
    [
        (
            ["add-source", "--location-id", "A0000000-0000-4000-8000-000000000001",
             "--name", "Solar array", "--type", "solar", "--json"],
            "add_source",
        ),
        (["add-renewable", "--location-id", "A0000000-0000-4000-8000-000000000001",
          "--source-id", "source", "--renewable-type", "solar_pv", "--capacity", "1", "--json"],
         "add_renewable"),
        (["consumption", "--location-id", "A0000000-0000-4000-8000-000000000001", "--json"],
         "get_consumption"),
        (["efficiency", "--location-id", "A0000000-0000-4000-8000-000000000001", "--json"],
         "get_efficiency"),
        (["renewable-summary", "--location-id", "A0000000-0000-4000-8000-000000000001", "--json"],
         "get_renewable_summary"),
        (["dashboard", "--location-id", "A0000000-0000-4000-8000-000000000001", "--json"],
         "get_energy_dashboard"),
        (["carbon-intensity", "--location-id", "A0000000-0000-4000-8000-000000000001", "--json"],
         "compute_carbon_intensity"),
        (["cost-analysis", "--location-id", "A0000000-0000-4000-8000-000000000001", "--json"],
         "get_cost_analysis"),
    ],
)
def test_valid_uppercase_location_is_canonical_before_database_handler(
    monkeypatch, argv, operation
):
    canonical_location = "a0000000-0000-4000-8000-000000000001"
    connection = Mock()
    handler = Mock(return_value={})
    monkeypatch.setattr(cli_energy_monitoring.cli, "_connection_factory", lambda: connection)
    monkeypatch.setattr(cli_energy_monitoring, operation, handler)

    cli_energy_monitoring.main(argv)

    assert handler.call_args.args[1] == canonical_location
    connection.close.assert_called_once()


def test_reading_command_remains_location_free(monkeypatch):
    connection = Mock()
    handler = Mock(return_value={})
    monkeypatch.setattr(cli_energy_monitoring.cli, "_connection_factory", lambda: connection)
    monkeypatch.setattr(cli_energy_monitoring, "record_reading", handler)

    cli_energy_monitoring.main(
        ["record", "--source-id", "source", "--type", "consumption", "--kwh", "1", "--json"]
    )

    handler.assert_called_once()
    assert handler.call_args.args[:2] == (connection, "source")
    connection.close.assert_called_once()
