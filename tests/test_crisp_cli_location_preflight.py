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


@pytest.mark.parametrize("mode", ["--composite", "--rate"])
@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("not-a-date", "2026-12-31"),
        ("2026-02-30", "2026-12-31"),
        ("20260101", "2026-12-31"),
        ("2026-12-31", "2026-01-01"),
    ],
)
def test_invalid_period_is_rejected_before_database_access(monkeypatch, mode, start, end):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crisp",
            mode,
            "--location-id",
            LOCATION_ID,
            "--period-start",
            start,
            "--period-end",
            end,
        ],
    )
    monkeypatch.setattr(
        cli,
        "get_db",
        lambda: pytest.fail("invalid period must fail before database access"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    ("mode", "start", "end"),
    [
        ("--composite", "2026-06-01", "2026-06-01"),
        ("--rate", "2026-01-01", "2026-12-31"),
    ],
)
def test_valid_period_is_forwarded_as_canonical_iso_dates(monkeypatch, mode, start, end):
    calls = []
    connection = SimpleNamespace(close=lambda: calls.append(("close",)))
    result = SimpleNamespace(to_dict=lambda: {"rating": "A"})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crisp",
            mode,
            "--location-id",
            LOCATION_ID,
            "--period-start",
            start,
            "--period-end",
            end,
        ],
    )
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(cli, "print_json", lambda _value: None)
    monkeypatch.setattr(
        "services.crisp.scoring_engine.compute_composite_rating",
        lambda conn, location_id, period_start, period_end, **_kwargs: calls.append(
            ("compute", conn, location_id, period_start, period_end)
        ) or result,
    )
    if mode == "--rate":
        monkeypatch.setattr(
            "services.crisp.scoring_engine.persist_assessment",
            lambda conn, assessment: calls.append(("persist", conn, assessment)) or "assessment-id",
        )

    cli.main()

    assert calls[0] == ("compute", connection, CANONICAL_LOCATION_ID, start, end)
    assert calls[-1] == ("close",)
    if mode == "--rate":
        assert calls[1] == ("persist", connection, result)
