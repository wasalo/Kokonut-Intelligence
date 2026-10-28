"""Precision-irrigation location identifiers fail before database access."""

import sys
from types import SimpleNamespace

import pytest

from services.analytics import cli_precision_irrigation as cli

LOCATION_ID = "A0000000-0000-4000-8000-000000000001"
CANONICAL_LOCATION_ID = "a0000000-0000-4000-8000-000000000001"


@pytest.mark.parametrize("command", ["create-zone", "create-rule", "irrigation-status", "water-efficiency", "efficiency-report"])
@pytest.mark.parametrize("location_id", ["not-a-uuid", "", "all"])
def test_location_commands_reject_invalid_scope_before_database(monkeypatch, command, location_id):
    argv = ["precision-irrigation", command, "--location-id", location_id]
    if command == "create-zone":
        argv.extend(["--name", "Test zone"])
    elif command == "create-rule":
        argv.extend(["--name", "Test rule", "--metric", "soil_moisture", "--operator", "lt", "--threshold", "20"])
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(
        "services.ingestion.base.get_db",
        lambda: pytest.fail("invalid scope must fail before DB access"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    ("command", "handler_name", "tail"),
    [
        ("create-zone", "create_zone", ["--name", "Test zone"]),
        (
            "create-rule",
            "create_automation_rule",
            ["--name", "Test rule", "--metric", "soil_moisture", "--operator", "lt", "--threshold", "20"],
        ),
        ("irrigation-status", "get_irrigation_status", []),
        ("water-efficiency", "get_water_efficiency", []),
        ("efficiency-report", "get_efficiency_report", []),
    ],
)
def test_valid_location_scope_is_canonicalized_before_handler(monkeypatch, command, handler_name, tail):
    db = SimpleNamespace(close=lambda: None)
    calls = []
    monkeypatch.setattr("services.ingestion.base.get_db", lambda: db)
    monkeypatch.setattr(cli, handler_name, lambda _db, location_id, *args, **kwargs: calls.append(location_id) or {})
    monkeypatch.setattr(cli, "print_json", lambda _value: None)
    monkeypatch.setattr(sys, "argv", ["precision-irrigation", command, "--location-id", LOCATION_ID, *tail])

    cli.main()

    assert calls == [CANONICAL_LOCATION_ID]

