"""Precision-irrigation location identifiers fail before database access."""

import sys
from datetime import datetime, timezone
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


@pytest.mark.parametrize("priority", [-1, 101])
def test_create_rule_rejects_priority_outside_schema_bounds_before_database(
    monkeypatch, priority
):
    monkeypatch.setattr(sys, "argv", [
        "precision-irrigation", "create-rule", "--location-id", LOCATION_ID,
        "--name", "Test rule", "--metric", "soil_moisture", "--operator", "lt",
        "--threshold", "20", "--priority", str(priority),
    ])
    monkeypatch.setattr(
        "services.ingestion.base.get_db",
        lambda: pytest.fail("out-of-range rule priority must fail before DB access"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2


@pytest.mark.parametrize("priority", [0, 100])
def test_create_rule_forwards_valid_priority_boundaries(monkeypatch, priority):
    db = SimpleNamespace(close=lambda: None)
    calls = []
    monkeypatch.setattr("services.ingestion.base.get_db", lambda: db)
    monkeypatch.setattr(
        cli,
        "create_automation_rule",
        lambda _db, *_args, **kwargs: calls.append(kwargs["priority"]) or {},
    )
    monkeypatch.setattr(cli, "print_json", lambda _value: None)
    monkeypatch.setattr(sys, "argv", [
        "precision-irrigation", "create-rule", "--location-id", LOCATION_ID,
        "--name", "Test rule", "--metric", "soil_moisture", "--operator", "lt",
        "--threshold", "20", "--priority", str(priority),
    ])

    cli.main()

    assert calls == [priority]


@pytest.mark.parametrize("readings", ["not-json", "[]", "null"])
def test_eval_rules_rejects_non_object_json_before_database(monkeypatch, readings):
    monkeypatch.setattr(sys, "argv", [
        "precision-irrigation", "eval-rules", "--zone-id", "zone-id",
        "--readings", readings,
    ])
    monkeypatch.setattr(
        "services.ingestion.base.get_db",
        lambda: pytest.fail("invalid readings must fail before DB access"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2


def test_eval_rules_accepts_empty_json_object_before_handler(monkeypatch):
    db = SimpleNamespace(close=lambda: None)
    calls = []
    monkeypatch.setattr("services.ingestion.base.get_db", lambda: db)
    monkeypatch.setattr(
        cli,
        "evaluate_automation_rules",
        lambda _db, zone_id, readings: calls.append((zone_id, readings)) or {},
    )
    monkeypatch.setattr(cli, "print_json", lambda _value: None)
    monkeypatch.setattr(sys, "argv", [
        "precision-irrigation", "eval-rules", "--zone-id", "zone-id",
        "--readings", "{}",
    ])

    cli.main()

    assert calls == [("zone-id", {})]


def test_schedule_rejects_invalid_start_before_database(monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "precision-irrigation", "schedule", "--zone-id", "zone-id",
        "--etc", "1.5", "--start", "tomorrow morning",
    ])
    monkeypatch.setattr(
        "services.ingestion.base.get_db",
        lambda: pytest.fail("invalid schedule time must fail before DB access"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2


def test_schedule_forwards_parsed_iso_start_to_handler(monkeypatch):
    db = SimpleNamespace(close=lambda: None)
    calls = []
    scheduled_start = datetime(2026, 10, 29, 8, 30, tzinfo=timezone.utc)
    monkeypatch.setattr("services.ingestion.base.get_db", lambda: db)
    monkeypatch.setattr(
        cli,
        "generate_schedule",
        lambda _db, _zone, _etc, **kwargs: calls.append(kwargs["scheduled_start"]) or {},
    )
    monkeypatch.setattr(cli, "print_json", lambda _value: None)
    monkeypatch.setattr(sys, "argv", [
        "precision-irrigation", "schedule", "--zone-id", "zone-id",
        "--etc", "1.5", "--start", scheduled_start.isoformat(),
    ])

    cli.main()

    assert calls == [scheduled_start]

