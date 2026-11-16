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


def test_regional_cluster_query_returns_only_distance_and_uses_read_only_lookups(monkeypatch):
    module = importlib.import_module("services.revenue_multiplier.dimensions.regional_clusters")
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchall.side_effect = [
        [{"distance_km": 5.0}, {"distance_km": 12.0}],
        [{"resource_type": "synthetic", "capacity": 0, "usage_count": 0}],
    ]
    cursor.fetchone.return_value = None
    monkeypatch.setattr(module, "get_config", lambda _conn, _key: 1.0)

    result = module.analyze(connection, "location-1")

    query, params = cursor.execute.call_args_list[0].args
    assert query.lstrip().upper().startswith("WITH TARGET")
    assert "l.name" not in query
    assert "l.id," not in query
    assert not any(token in query.upper() for token in ("INSERT INTO", "UPDATE ", "DELETE FROM", "MERGE INTO"))
    assert params == ("location-1", "location-1")
    assert result.details["nearby_farm_count"] == 2
    assert result.details["nearest_farm_km"] == 5.0
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_not_called()
    cursor.close.assert_called_once()
