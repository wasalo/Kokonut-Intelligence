"""CIDS export mapping tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from services.registry.cids_export import build_cids_graph, export_location


def _source() -> dict:
    return {
        "location": {
            "id": "a0000000-0000-0000-0000-000000000001",
            "name": "Kokonut Adelphi",
            "slug": "kokonut-adelphi",
            "description": "Syntropic regenerative pilot farm.",
            "farm_id": "a0000000-0000-0000-0000-000000000010",
            "farm_name": "Kokonut Adelphi",
            "farm_slug": "kokonut-adelphi",
            "farm_description": "Kokonut Adelphi farm profile.",
            "project_summary": "Adelphi farm impact program.",
            "local_problem": "Degraded soil and unstable farm income.",
            "proposed_solution": "Syntropic agriculture and governed MRV.",
        },
        "stakeholder_outcomes": [
            {
                "id": "a0000000-0000-0000-0000-000000000910",
                "outcome_name": "Improved farm operator capability",
                "outcome_description": "Operators gain practical capacity.",
                "stakeholder_group": "farm_operator",
                "importance": "high",
                "importance_perspective": "operator feedback",
                "is_underserved": False,
                "sdg_number": 8,
            }
        ],
        "framework_mappings": [
            {"sdg_number": 8, "sdg_name": "Decent Work and Economic Growth"}
        ],
        "metric_values": [
            {
                "metric_key": "value_flowed",
                "display_name": "Value flowed",
                "description": "Verified value attributable to Kokonut activity.",
                "unit": "USD",
                "metric_value_id": "a0000000-0000-0000-0000-000000000940",
                "period_start": date(2025, 10, 1),
                "period_end": date(2026, 3, 31),
                "value": Decimal("35682.00"),
                "value_unit": "USD",
                "computation_method": "metric engine",
            },
            {
                "metric_key": "ebf_soil_health_score",
                "display_name": "EBF Soil Health Score",
                "description": "Normalized 0-10 EBF score for soil health.",
                "unit": "score_0_10",
                "metric_value_id": "a0000000-0000-0000-0000-000000000941",
                "period_start": date(2025, 10, 1),
                "period_end": date(2026, 3, 31),
                "value": Decimal("7.00"),
                "value_unit": "score_0_10",
                "computation_method": "EBF rubric score",
            }
        ],
        "feedback": [
            {
                "id": "a0000000-0000-0000-0000-000000000900",
                "stakeholder_group": "farm_operator",
            }
        ],
        "impact_claims": [
            {
                "id": "a0000000-0000-0000-0000-000000000921",
                "claim_text": "Adelphi is modeled as a net-sequestering pilot.",
                "period_start": date(2025, 10, 1),
                "period_end": date(2026, 3, 31),
                "confidence_notes": "External review represented for public gating.",
                "evidence_maturity": 6,
                "evidence_maturity_label": "Externally verified record",
                "methodology_ref": "IPCC 2006 GHG Guidelines",
                "external_verifier": "External MRV reviewer",
                "attestation_uid": None,
            }
        ],
    }


def test_build_cids_graph_contains_essential_tier_classes() -> None:
    graph = build_cids_graph(_source())
    types = {item["@type"] for item in graph}

    assert "cids:Organization" in types
    assert "cids:Program" in types
    assert "cids:ImpactPathway" in types
    assert "cids:Stakeholder" in types
    assert "cids:StakeholderOutcome" in types
    assert "cids:Outcome" in types
    assert "cids:Indicator" in types
    assert "cids:IndicatorReport" in types
    assert "cids:ImpactReport" in types


def test_ebf_metric_values_export_as_indicator_reports_with_metadata() -> None:
    graph = build_cids_graph(_source())
    ebf_reports = [
        item for item in graph
        if item["@type"] == "cids:IndicatorReport" and item.get("kokonut:framework") == "ebf"
    ]
    assert ebf_reports
    assert ebf_reports[0]["kokonut:ebfPillar"] == "soil_health"
    assert ebf_reports[0]["kokonut:cidsMapping"] == "metric_value -> cids:IndicatorReport"


def test_export_location_wraps_graph_with_essential_tier(monkeypatch) -> None:
    class Conn:
        pass

    import services.registry.cids_export as cids_export

    monkeypatch.setattr(cids_export, "fetch_cids_source", lambda conn, location_id: _source())
    exported = export_location(Conn(), "a0000000-0000-0000-0000-000000000001")

    assert exported["kokonut:alignmentTier"] == "essential"
    assert exported["kokonut:cidsVersion"] == "3.2.0"
    assert exported["@graph"]
