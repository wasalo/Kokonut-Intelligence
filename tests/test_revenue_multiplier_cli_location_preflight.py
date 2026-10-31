"""Location preflight for the Revenue Multiplier CLI."""

import sys
from dataclasses import dataclass
from types import ModuleType
from uuid import uuid4

import pytest

from services.revenue_multiplier import cli


@pytest.mark.parametrize("location_id", ["", "not-a-uuid", "1234"])
def test_invalid_location_fails_before_database_or_analyzer(monkeypatch, location_id):
    monkeypatch.setattr(
        "sys.argv",
        ["revenue-multiplier", "--location-id", location_id],
    )
    monkeypatch.setattr(
        "services.common.database.get_db",
        lambda: pytest.fail("invalid location must fail before DB access"),
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2


@dataclass
class _DimensionResult:
    dimension_name: str = "Crop Mix"
    score: int = 50
    impact_usd: float = 100.0
    confidence: str = "medium"
    current_state: str = "Mixed cropping"
    recommendation: str = "Diversify"
    details: dict | None = None


def test_dimension_mode_receives_canonical_uuid(monkeypatch):
    location_id = str(uuid4())
    seen = []
    connection = type("Connection", (), {"close": lambda self: seen.append("closed")})()
    module = ModuleType("services.revenue_multiplier.dimensions.crop_mix")
    module.analyze = lambda conn, scope: seen.append((conn, scope)) or _DimensionResult()
    monkeypatch.setattr(
        "sys.argv",
        [
            "revenue-multiplier",
            "--location-id",
            location_id.upper(),
            "--dimension",
            "crop_mix_optimization",
            "--json",
        ],
    )
    monkeypatch.setitem(
        sys.modules, "services.revenue_multiplier.dimensions.crop_mix", module
    )
    monkeypatch.setattr("services.common.database.get_db", lambda: connection)

    cli.main()

    assert seen == [(connection, location_id), "closed"]


def test_list_dimensions_stays_offline(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["revenue-multiplier", "--list-dimensions"])
    monkeypatch.setattr(
        "services.common.database.get_db",
        lambda: pytest.fail("dimension listing must not access DB"),
    )

    cli.main()

    assert "crop_mix_optimization" in capsys.readouterr().out

