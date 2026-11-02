"""Forecast CLI location scope fails before database-backed work."""

import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.forecast import cli

LOCATION_ID = str(uuid4())


@pytest.mark.parametrize(
    "args",
    [
        ["--all", "--location-id", "bad"],
        ["--all", "--location-id", ""],
        ["--reference-class", "--location-id", "bad"],
        ["--reference-class", "--location-id", ""],
        ["--reference-class"],
    ],
)
def test_invalid_scoped_arguments_fail_before_database_or_engine(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["forecast", *args])
    monkeypatch.setattr(
        "services.ingestion.base.get_db",
        lambda: pytest.fail("invalid scope must fail before DB connection"),
        raising=False,
    )
    monkeypatch.setattr(
        cli,
        "run_all_scenarios",
        lambda *_args: pytest.fail("invalid scope must fail before the engine"),
    )

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 2


def test_all_without_location_keeps_global_mode(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["forecast", "--all"])
    monkeypatch.setattr(cli, "run_all_scenarios", lambda value: calls.append(value) or [])

    cli.main()

    assert calls == [None]


def test_all_canonicalizes_valid_location_before_engine(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["forecast", "--all", "--location-id", LOCATION_ID.upper()])
    monkeypatch.setattr(cli, "run_all_scenarios", lambda value: calls.append(value) or [])

    cli.main()

    assert calls == [LOCATION_ID]


def test_reference_class_canonicalizes_scope_before_database_work(monkeypatch):
    calls = []
    db = SimpleNamespace(close=lambda: calls.append("closed"))
    monkeypatch.setattr(
        sys,
        "argv",
        ["forecast", "--reference-class", "--location-id", LOCATION_ID.upper()],
    )
    monkeypatch.setattr("services.ingestion.base.get_db", lambda: db)
    monkeypatch.setattr(
        "services.forecast.reference_class.apply_reference_class",
        lambda conn, location_id, metric, alpha: calls.append(
            (conn, location_id, metric, alpha)
        ) or {"status": "ok"},
    )
    monkeypatch.setattr(cli, "print_json", lambda value: calls.append(value))

    cli.main()

    assert calls == [(db, LOCATION_ID, "crop_noi", 0.5), "closed", {"status": "ok"}]

