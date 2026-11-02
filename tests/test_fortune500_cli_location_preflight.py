"""Fortune 500 CLI validates supplied location scope before calculator access."""

import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.fortune500 import cli

LOCATION_ID = str(uuid4())


@pytest.mark.parametrize(
    "args",
    [
        ["--location-id", "bad"],
        ["--location-id", ""],
        ["--farm", "bad"],
        ["--farm", ""],
        ["--location-id", LOCATION_ID, "--farm", "bad"],
    ],
)
def test_malformed_supplied_location_fails_before_calculator(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["fortune500", *args])
    monkeypatch.setattr(
        cli,
        "get_farm_metrics",
        lambda *_args: pytest.fail("malformed location must fail before calculator DB access"),
    )

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 2


@pytest.mark.parametrize("option", ["--location-id", "--farm"])
def test_valid_location_alias_is_canonicalized_before_calculator(monkeypatch, option):
    metrics_calls = []
    output = []
    metrics = SimpleNamespace(location_name="Kokonut Genesis")
    score = SimpleNamespace(
        financial_score=1.0,
        ecological_score=2.0,
        governance_score=3.0,
        growth_score=4.0,
        composite_score=5.0,
        tier="Developing",
        breakdown={},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["fortune500", option, LOCATION_ID.upper(), "--json"],
    )
    monkeypatch.setattr(
        cli,
        "get_farm_metrics",
        lambda location_id: metrics_calls.append(location_id) or metrics,
    )
    monkeypatch.setattr(cli, "calculate_score", lambda _metrics: score)
    monkeypatch.setattr(cli, "print_json", output.append)

    cli.main()

    assert metrics_calls == [LOCATION_ID]
    assert output[0]["location_id"] == LOCATION_ID


def test_global_all_mode_does_not_require_or_pass_location(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["fortune500", "--all", "--json"])
    monkeypatch.setattr(cli, "get_farm_metrics", lambda *_args: pytest.fail("single-farm path not expected"))
    monkeypatch.setattr(cli, "calculate_all_farms", lambda: calls.append("global") or [])
    monkeypatch.setattr(cli, "print_json", lambda value: calls.append(value))

    cli.main()

    assert calls == ["global", []]

