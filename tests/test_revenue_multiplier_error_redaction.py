"""Revenue multiplier analysis errors must not expose provider or DB details."""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock

from services.revenue_multiplier import analyzer
from services.revenue_multiplier.models import OpportunityDimension


def test_dimension_failure_is_redacted_and_analysis_continues(monkeypatch):
    connection = MagicMock()
    monkeypatch.setattr(analyzer, "get_db", lambda: connection)
    monkeypatch.setattr(analyzer, "_get_location_name", lambda _conn, _location: "Demo")
    monkeypatch.setattr(analyzer, "get_config", lambda _conn, _key: 1.0)

    module_names = (
        "crop_mix",
        "loss_reduction",
        "buyer_channel",
        "value_added",
        "web3_replication",
        "bioinput",
        "public_goods",
        "ecological_verification",
        "partner_sponsorship",
        "regional_clusters",
    )
    modules = {
        name: importlib.import_module(f"services.revenue_multiplier.dimensions.{name}")
        for name in module_names
    }

    def fail(_conn, _location_id):
        raise RuntimeError("synthetic analyzer diagnostic marker")

    monkeypatch.setattr(modules["crop_mix"], "analyze", fail)
    for name in module_names[1:]:
        monkeypatch.setattr(
            modules[name],
            "analyze",
            lambda _conn, _location_id, module_name=name: OpportunityDimension(
                dimension_id=module_name,
                dimension_name=module_name,
                score=10,
                impact_usd=100,
                confidence="low",
                current_state="synthetic",
                recommendation="synthetic",
                data_points=0,
            ),
        )

    result = analyzer.analyze_location("00000000-0000-0000-0000-000000000001")

    failed = result.dimensions[0]
    assert failed.current_state == "Analysis failed (RuntimeError)"
    assert "synthetic analyzer diagnostic marker" not in failed.current_state
    assert failed.recommendation == "Review analyzer availability"
    assert len(result.dimensions) == 10
    assert result.total_opportunity_usd == 900
    connection.close.assert_called_once()
