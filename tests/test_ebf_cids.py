"""EBF CIDS compatibility tests."""

from datetime import date
from decimal import Decimal

from services.registry.cids_export import build_cids_graph


def test_ebf_score_exports_as_indicator_report_not_new_class() -> None:
    graph = build_cids_graph({
        "location": {"name": "Kokonut Adelphi", "slug": "kokonut-adelphi"},
        "stakeholder_outcomes": [],
        "framework_mappings": [],
        "feedback": [],
        "impact_claims": [],
        "metric_values": [{"metric_key": "ebf_soil_health_score", "display_name": "EBF Soil Health Score", "description": "Score", "unit": "score_0_10", "metric_value_id": "a0000000-0000-0000-0000-000000000941", "period_start": date(2026, 1, 1), "period_end": date(2026, 12, 31), "value": Decimal("7"), "value_unit": "score_0_10", "computation_method": "EBF rubric"}],
    })
    types = {item["@type"] for item in graph}
    assert "cids:IndicatorReport" in types
    assert "cids:EBFScorecard" not in types
    assert any(item.get("kokonut:ebfPillar") == "soil_health" for item in graph)


if __name__ == "__main__":
    test_ebf_score_exports_as_indicator_report_not_new_class()
