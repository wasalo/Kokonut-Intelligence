"""CRISP CLI location UUIDs are validated before opening PostgreSQL."""

import sys
from types import SimpleNamespace

import pytest

from services.crisp import cli

LOCATION_ID = "A0000000-0000-4000-8000-000000000001"
CANONICAL_LOCATION_ID = "a0000000-0000-4000-8000-000000000001"


@pytest.mark.parametrize(
    ("mode", "extra"),
    [
        ("--carbon-yield", []),
        ("--climate", []),
        ("--policy", []),
        ("--financial", []),
        ("--implementation", []),
        ("--composite", ["--period-start", "2026-01-01", "--period-end", "2026-12-31"]),
        ("--rate", ["--period-start", "2026-01-01", "--period-end", "2026-12-31"]),
        ("--weights", []),
    ],
)
@pytest.mark.parametrize("location_id", ["invalid", "all", ""])
def test_invalid_location_is_rejected_before_database_access(monkeypatch, mode, extra, location_id):
    monkeypatch.setattr(sys, "argv", ["crisp", mode, "--location-id", location_id, *extra])
    monkeypatch.setattr(
        cli,
        "get_db",
        lambda: pytest.fail("invalid location scope must fail before database access"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2


def test_valid_location_is_canonicalized_before_database_work(monkeypatch):
    calls = []
    connection = SimpleNamespace(close=lambda: None)

    monkeypatch.setattr(sys, "argv", ["crisp", "--weights", "--location-id", LOCATION_ID])
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(cli, "print_json", lambda _value: None)
    monkeypatch.setattr(
        "services.crisp.scoring_engine._query_location_weights",
        lambda conn, location_id: calls.append((conn, location_id)) or {},
    )

    cli.main()

    assert calls == [(connection, CANONICAL_LOCATION_ID)]


def test_missing_location_still_reports_mode_specific_requirement(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["crisp", "--weights"])
    monkeypatch.setattr(
        cli,
        "get_db",
        lambda: pytest.fail("missing required location must fail before DB access"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2
