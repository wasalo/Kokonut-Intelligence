"""CIDS export mapping tests."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from decimal import Decimal

from services.registry.cids_contract import CIDS_ALIGNMENT_TIER, CIDS_VERSION
from services.registry.cids_export import (
    build_cids_graph,
    build_cids_property_row_lineage,
    export_location,
    fetch_cids_source,
)


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
            {
                "id": "a0000000-0000-0000-0000-000000000930",
                "sdg_number": 8,
                "sdg_name": "Decent Work and Economic Growth",
            }
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


def test_cids_graph_attributes_each_node_to_its_signed_source_views() -> None:
    graph = build_cids_graph(_source(), source_schema="kokonut_agent_source")
    by_type = {
        item["@type"]: item
        for item in graph
        if item["@type"] not in {"cids:IndicatorReport", "cids:StakeholderOutcome"}
    }
    signed_views = {
        item["@id"]: item["kokonut:sourceViews"]
        for item in graph
    }

    assert by_type["cids:Organization"]["kokonut:sourceViews"] == [
        "kokonut_agent_source.cids_location",
        "kokonut_agent_source.cids_metric_value",
        "kokonut_agent_source.cids_stakeholder_feedback",
        "kokonut_agent_source.cids_stakeholder_outcome",
    ]
    assert by_type["cids:Program"]["kokonut:sourceViews"] == [
        "kokonut_agent_source.cids_location"
    ]
    assert by_type["cids:ImpactPathway"]["kokonut:sourceViews"] == [
        "kokonut_agent_source.cids_location",
        "kokonut_agent_source.cids_metric_value",
        "kokonut_agent_source.cids_stakeholder_outcome",
    ]
    assert by_type["cids:Theme"]["kokonut:sourceViews"] == [
        "kokonut_agent_source.cids_farm_impact_mapping"
    ]
    stakeholder = next(item for item in graph if item["@type"] == "cids:Stakeholder")
    assert stakeholder["kokonut:sourceViews"] == [
        "kokonut_agent_source.cids_location",
        "kokonut_agent_source.cids_stakeholder_feedback",
        "kokonut_agent_source.cids_stakeholder_outcome",
    ]
    assert by_type["cids:Outcome"]["kokonut:sourceViews"] == [
        "kokonut_agent_source.cids_location",
        "kokonut_agent_source.cids_stakeholder_outcome"
    ]
    stakeholder_outcome = next(
        item for item in graph if item["@type"] == "cids:StakeholderOutcome"
    )
    assert stakeholder_outcome["kokonut:sourceViews"] == [
        "kokonut_agent_source.cids_stakeholder_outcome"
    ]
    assert by_type["cids:Indicator"]["kokonut:sourceViews"] == [
        "kokonut_agent_source.cids_location",
        "kokonut_agent_source.cids_metric_value"
    ]
    indicator_report = next(
        item for item in graph if item["@type"] == "cids:IndicatorReport"
    )
    assert indicator_report["kokonut:sourceViews"] == [
        "kokonut_agent_source.cids_location",
        "kokonut_agent_source.cids_metric_value"
    ]
    assert by_type["cids:ImpactReport"]["kokonut:sourceViews"] == [
        "kokonut_agent_source.cids_impact_claim",
        "kokonut_agent_source.cids_location",
    ]
    assert all(views for views in signed_views.values())
    assert all(isinstance(views, list) for views in signed_views.values())


def test_cids_graph_attributes_each_property_to_source_views_without_row_ids() -> None:
    graph = build_cids_graph(_source(), source_schema="kokonut_agent_source")
    by_type = {item["@type"]: item for item in graph if item["@type"] in {
        "cids:Organization", "cids:ImpactPathway", "cids:Indicator",
        "cids:IndicatorReport", "cids:ImpactReport",
    }}
    location_view = "kokonut_agent_source.cids_location"
    outcome_view = "kokonut_agent_source.cids_stakeholder_outcome"
    metric_view = "kokonut_agent_source.cids_metric_value"
    feedback_view = "kokonut_agent_source.cids_stakeholder_feedback"
    claim_view = "kokonut_agent_source.cids_impact_claim"

    organization = by_type["cids:Organization"]["kokonut:propertySourceViews"]
    assert organization["hasName"] == [location_view]
    assert organization["hasOutcome"] == [outcome_view]
    assert organization["hasIndicator"] == [metric_view]
    assert organization["hasStakeholder"] == [feedback_view, outcome_view]

    impact_pathway = by_type["cids:ImpactPathway"]["kokonut:propertySourceViews"]
    assert impact_pathway["hasName"] == [location_view]
    assert impact_pathway["hasOutcome"] == [outcome_view]
    assert impact_pathway["hasIndicator"] == [metric_view]

    indicator = next(
        item["kokonut:propertySourceViews"]
        for item in graph
        if item["@type"] == "cids:Indicator" and "value-flowed" in item["@id"]
    )
    assert indicator["hasName"] == [metric_view]
    assert indicator["forOrganization"] == [location_view]
    assert indicator["hasComment"] == []

    indicator_report = next(
        item["kokonut:propertySourceViews"]
        for item in graph
        if item["@type"] == "cids:IndicatorReport"
    )
    assert indicator_report["hasName"] == [location_view, metric_view]
    assert indicator_report["forOrganization"] == [location_view]
    impact_report = by_type["cids:ImpactReport"]["kokonut:propertySourceViews"]
    assert impact_report["hasDescription"] == [claim_view]
    assert impact_report["forOrganization"] == [location_view]

    for item in graph:
        property_views = item["kokonut:propertySourceViews"]
        expected_properties = set(item) - {
            "@context", "@type", "kokonut:sourceViews", "kokonut:propertySourceViews"
        }
        assert set(property_views) == expected_properties
        assert item["kokonut:sourceViews"] == sorted(
            {view for views in property_views.values() for view in views}
        )
        assert all(
            not re.fullmatch(r"[0-9a-f-]{36}", view)
            for views in property_views.values()
            for view in views
        )


def test_cids_private_lineage_maps_properties_to_exact_signed_projection_rows() -> None:
    source = _source()
    graph = build_cids_graph(source, source_schema="kokonut_agent_source")
    lineage = build_cids_property_row_lineage(
        source, graph, source_schema="kokonut_agent_source"
    )
    by_type = {item["@type"]: item for item in graph}
    by_node = {item["node_id"]: item for item in lineage}

    organization = by_node[by_type["cids:Organization"]["@id"]]
    organization_properties = {
        item["property"]: item for item in organization["properties"]
    }
    assert organization_properties["hasName"]["records"] == [
        {
            "view": "kokonut_agent_source.cids_location",
            "record_id": source["location"]["id"],
        }
    ]
    assert organization_properties["hasOutcome"]["records"] == [
        {
            "view": "kokonut_agent_source.cids_stakeholder_outcome",
            "record_id": source["stakeholder_outcomes"][0]["id"],
        }
    ]
    assert {
        record["record_id"]
        for record in organization_properties["hasIndicator"]["records"]
    } == {row["metric_value_id"] for row in source["metric_values"]}
    assert organization_properties["hasStakeholder"]["row_count"] == 2

    outcome = next(item for item in graph if item["@type"] == "cids:Outcome")
    outcome_properties = {
        item["property"]: item for item in by_node[outcome["@id"]]["properties"]
    }
    assert outcome_properties["hasName"]["records"][0]["record_id"] == source[
        "stakeholder_outcomes"
    ][0]["id"]
    assert outcome_properties["forOrganization"]["records"][0]["record_id"] == source[
        "location"
    ]["id"]

    impact_report = next(item for item in graph if item["@type"] == "cids:ImpactReport")
    claim = source["impact_claims"][0]
    description = next(
        item
        for item in by_node[impact_report["@id"]]["properties"]
        if item["property"] == "hasDescription"
    )
    assert description["records"] == [
        {
            "view": "kokonut_agent_source.cids_impact_claim",
            "record_id": claim["id"],
        }
    ]
    assert all(
        "kokonut:propertySourceRecords" not in node and "record_id" not in node
        for node in graph
    )


def test_cids_public_schema_lineage_maps_global_and_location_reference_rows() -> None:
    source = _source()
    source["location"]["registry_id"] = "a0000000-0000-0000-0000-000000000011"
    graph = build_cids_graph(source, source_schema="public")
    lineage = build_cids_property_row_lineage(source, graph, source_schema="public")
    lineage_by_node = {item["node_id"]: item for item in lineage}

    organization = next(item for item in graph if item["@type"] == "cids:Organization")
    organization_name = next(
        item
        for item in lineage_by_node[organization["@id"]]["properties"]
        if item["property"] == "hasName"
    )
    assert organization_name["records"] == [
        {"view": "public.farm", "record_id": source["location"]["farm_id"]},
        {
            "view": "public.farm_registry_record",
            "record_id": source["location"]["registry_id"],
        },
        {"view": "public.location", "record_id": source["location"]["id"]},
    ]

    theme = next(item for item in graph if item["@type"] == "cids:Theme")
    theme_name = next(
        item
        for item in lineage_by_node[theme["@id"]]["properties"]
        if item["property"] == "hasName"
    )
    assert theme_name["records"] == [
        {
            "view": "public.farm_impact_mapping",
            "record_id": source["framework_mappings"][0]["id"],
        },
        {"view": "public.sdg", "record_id": "sdg:8"},
    ]

    indicator = next(item for item in graph if item["@type"] == "cids:Indicator")
    indicator_name = next(
        item
        for item in lineage_by_node[indicator["@id"]]["properties"]
        if item["property"] == "hasName"
    )
    assert {
        (record["view"], record["record_id"])
        for record in indicator_name["records"]
    } == {
        ("public.metric_definition", "value_flowed"),
        ("public.metric_value", source["metric_values"][0]["metric_value_id"]),
    }

    impact_report = next(item for item in graph if item["@type"] == "cids:ImpactReport")
    maturity_label = next(
        item
        for item in lineage_by_node[impact_report["@id"]]["properties"]
        if item["property"] == "kokonut:evidenceMaturityLabel"
    )
    assert maturity_label["records"] == [
        {
            "view": "public.evidence_maturity_level",
            "record_id": "level:6",
        },
        {
            "view": "public.impact_claim",
            "record_id": source["impact_claims"][0]["id"],
        },
    ]


def test_cids_private_property_lineage_caps_row_ids_and_reports_truncation() -> None:
    source = _source()
    source["stakeholder_outcomes"] = [
        {
            "id": f"a0000000-0000-4000-8000-{index:012d}",
            "outcome_name": f"Outcome {index}",
            "stakeholder_group": "farmer",
        }
        for index in range(55)
    ]
    graph = build_cids_graph(source, source_schema="kokonut_agent_source")
    lineage = build_cids_property_row_lineage(
        source, graph, source_schema="kokonut_agent_source"
    )
    organization = next(item for item in graph if item["@type"] == "cids:Organization")
    organization_lineage = next(
        item for item in lineage if item["node_id"] == organization["@id"]
    )
    has_outcomes = next(
        item
        for item in organization_lineage["properties"]
        if item["property"] == "hasOutcome"
    )
    assert has_outcomes["row_count"] == 55
    assert len(has_outcomes["records"]) == 50
    assert has_outcomes["truncated"] is True


def test_export_location_wraps_graph_with_essential_tier(monkeypatch) -> None:
    class Conn:
        pass

    import services.registry.cids_export as cids_export

    monkeypatch.setattr(
        cids_export, "fetch_cids_source", lambda conn, location_id, **_kwargs: _source()
    )
    exported = export_location(Conn(), "a0000000-0000-0000-0000-000000000001")

    assert exported["kokonut:alignmentTier"] == CIDS_ALIGNMENT_TIER
    assert exported["kokonut:cidsVersion"] == CIDS_VERSION
    assert CIDS_ALIGNMENT_TIER == "essential"
    assert CIDS_VERSION == "3.2.0"
    assert exported["@graph"]
    assert exported["@graph"][0]["kokonut:sourceViews"] == [
        "public.farm",
        "public.farm_registry_record",
        "public.location",
        "public.metric_definition",
        "public.metric_value",
        "public.stakeholder_feedback",
        "public.stakeholder_outcome",
    ]


def test_cids_source_query_requires_public_feedback_opt_in() -> None:
    class Cursor:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def execute(self, query: str, params: tuple[str]) -> None:
            self.queries.append(query)

        def fetchone(self) -> dict[str, str]:
            return {"id": "location-id", "name": "Kokonut Adelphi"}

        def fetchall(self) -> list[dict]:
            return []

    class Connection:
        def __init__(self, cursor: Cursor) -> None:
            self._cursor = cursor

        def cursor(self, **kwargs: object) -> Cursor:
            return self._cursor

    cursor = Cursor()
    fetch_cids_source(Connection(cursor), "location-id")
    feedback_query = next(query for query in cursor.queries if "FROM stakeholder_feedback" in query)

    assert "sf.is_public = TRUE" in feedback_query
    assert "sf.consent_given = TRUE" in feedback_query
    assert "sf.consent_scope IN ('public_summary', 'public_quote', 'public_full')" in feedback_query
    assert "sf.status = 'published'" in feedback_query
    assert "NULLIF(TRIM(COALESCE(sf.public_summary, '')), '') IS NOT NULL" in feedback_query


def test_scoped_cids_source_reads_only_signed_projection_views() -> None:
    class Cursor:
        def __init__(self) -> None:
            self.queries: list[str] = []
            self.fetchone_calls = 0

        def execute(self, query: str, params: tuple[str]) -> None:
            assert params == ("location-id",)
            self.queries.append(query)

        def fetchone(self) -> dict[str, str]:
            self.fetchone_calls += 1
            return {"id": "location-id", "name": "Kokonut Adelphi"}

        def fetchall(self) -> list[dict]:
            return []

        def close(self) -> None:
            pass

    class Connection:
        def __init__(self, cursor: Cursor) -> None:
            self._cursor = cursor

        def cursor(self, **kwargs: object) -> Cursor:
            return self._cursor

    cursor = Cursor()
    source = fetch_cids_source(
        Connection(cursor), "location-id", source_schema="kokonut_agent_source"
    )

    assert source["location"]["id"] == "location-id"
    assert len(cursor.queries) == 6
    assert all("kokonut_agent_source.cids_" in query for query in cursor.queries)
    assert all("public." not in query for query in cursor.queries)
    assert "public_summary" not in cursor.queries[4]
    assert "consent" not in cursor.queries[4].lower()


def test_cids_export_rejects_unapproved_source_schema() -> None:
    class Conn:
        pass

    import pytest

    with pytest.raises(ValueError, match="source_schema"):
        export_location(Conn(), "location-id", source_schema="public; DROP TABLE location")


def test_registry_export_cli_uses_signed_worker(monkeypatch, capsys) -> None:
    import services.registry.cids_export as cids_export
    from services.agents import worker_cli

    document = {
        "@context": [],
        "@graph": [{"@type": "cids:Organization"}],
        "kokonut:cidsVersion": "3.2.0",
        "kokonut:alignmentTier": "essential",
    }
    monkeypatch.setattr(sys, "argv", ["cids_export", "--location-id", "location-id"])
    monkeypatch.setattr(
        worker_cli,
        "run_worker_cids_export",
        lambda _location_id: {"document": document, "graph_count": 1},
    )

    cids_export.main()

    assert json.loads(capsys.readouterr().out) == document
