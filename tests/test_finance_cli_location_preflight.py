"""The finance CLI rejects invalid location scope before connecting."""

import sys
from uuid import UUID, uuid4

import pytest

from services.finance import cli

REPORT_FLAGS = (
    "--income-statement",
    "--balance-sheet",
    "--cash-flow-statement",
    "--investment-analysis",
)


@pytest.mark.parametrize("report_flag", REPORT_FLAGS)
@pytest.mark.parametrize("location_id", ["", "not-a-uuid", "123"])
def test_invalid_location_fails_before_database_connection(
    monkeypatch, report_flag, location_id
):
    monkeypatch.setattr(
        sys,
        "argv",
        ["finance", report_flag, "--location-id", location_id],
    )
    monkeypatch.setattr(
        cli, "get_pg", lambda: pytest.fail("invalid scope must not open PostgreSQL")
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2


@pytest.mark.parametrize("report_flag", REPORT_FLAGS)
def test_missing_location_fails_before_database_connection(monkeypatch, report_flag):
    monkeypatch.setattr(sys, "argv", ["finance", report_flag])
    monkeypatch.setattr(
        cli, "get_pg", lambda: pytest.fail("missing scope must not open PostgreSQL")
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2


def test_valid_location_is_canonicalized_before_report(monkeypatch):
    connection = type("Connection", (), {"close": lambda self: None})()
    source_location = str(uuid4()).upper()
    expected_location = str(UUID(source_location))
    calls = []
    monkeypatch.setattr(
        sys,
        "argv",
        ["finance", "--income-statement", "--location-id", source_location],
    )
    monkeypatch.setattr(cli, "get_pg", lambda: connection)
    monkeypatch.setattr(
        cli,
        "generate_income_statement",
        lambda conn, location_id: calls.append((conn, location_id)) or {"ok": True},
    )
    monkeypatch.setattr(cli, "print_json", lambda result: None)

    cli.main()

    assert calls == [(connection, expected_location)]


def test_list_remains_database_free_without_location(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["finance", "--list"])
    monkeypatch.setattr(
        cli, "get_pg", lambda: pytest.fail("listing finance reports is offline")
    )

    cli.main()

    assert "Available finance reports" in capsys.readouterr().out
