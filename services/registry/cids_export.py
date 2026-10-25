"""CIDS Essential Tier JSON-LD export helpers.

The exporter maps Kokonut's canonical farm, framework, metric, feedback, and
claim records into a Common Impact Data Standard compatible JSON-LD graph.
"""

from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from typing import Any

import psycopg2
import psycopg2.extras

CIDS_CONTEXTS = [
    "https://ontology.commonapproach.org/contexts/cidsContext.jsonld",
    "https://ontology.commonapproach.org/contexts/sffContext.jsonld",
]
CIDS_VERSION = "3.2.0"
CIDS_BASE_URL = os.environ.get("KOKONUT_CIDS_BASE_URL", "https://kokonut.network/cids")
SDG_BASE_URL = "https://metadata.un.org/sdg"


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _slug(value: str | None) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in (value or "unknown"))
    return "-".join(part for part in cleaned.split("-") if part)


def _uri(kind: str, identifier: str) -> str:
    return f"{CIDS_BASE_URL}/{kind}/{identifier}"


def _context(item: dict[str, Any]) -> dict[str, Any]:
    return {"@context": CIDS_CONTEXTS, **item}


def _measure(value: Any, unit_uri: str) -> dict[str, Any]:
    return _context(
        {
            "@type": "i72:Measure",
            "hasNumericalValue": str(value),
            "unit_of_measure": unit_uri,
        }
    )


def _unit_uri(unit: str | None) -> str:
    normalized = (unit or "count").lower()
    unit_map = {
        "usd": "https://ontology.commonapproach.org/cids#usd",
        "cad": "https://ontology.commonapproach.org/cids#cad",
        "count": "https://ontology.commonapproach.org/cids#countUnit",
        "percentage": "https://ontology.commonapproach.org/cids#percent",
        "percent": "https://ontology.commonapproach.org/cids#percent",
        "%": "https://ontology.commonapproach.org/cids#percent",
        "kg": "https://ontology.commonapproach.org/cids#kilogram",
        "kilogram": "https://ontology.commonapproach.org/cids#kilogram",
        "tco2e": "https://ontology.commonapproach.org/cids#tonneCO2e",
        "tonnes_co2e": "https://ontology.commonapproach.org/cids#tonneCO2e",
        "tonnes": "https://ontology.commonapproach.org/cids#tonne",
    }
    return unit_map.get(normalized, "https://ontology.commonapproach.org/cids#unspecifiedUnit")


def _ebf_pillar_from_metric(metric_key: str | None) -> str | None:
    if not metric_key or not metric_key.startswith("ebf_"):
        return None
    if metric_key == "ebf_overall_score":
        return "overall"
    return metric_key.removeprefix("ebf_").removesuffix("_score")


def _fetch_scoped_cids_source(conn, location_id: str) -> dict[str, Any]:
    """Fetch the CIDS projection through signed, exact-location source views."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        queries = (
            ("location", "SELECT * FROM kokonut_agent_source.cids_location WHERE id = %s"),
            (
                "stakeholder_outcomes",
                "SELECT * FROM kokonut_agent_source.cids_stakeholder_outcome "
                "WHERE location_id = %s AND status IN ('verified', 'published') "
                "ORDER BY created_at, id",
            ),
            (
                "framework_mappings",
                "SELECT * FROM kokonut_agent_source.cids_farm_impact_mapping "
                "WHERE location_id = %s AND status IN ('verified', 'published') "
                "ORDER BY framework_key, dimension_key, sdg_number, id",
            ),
            (
                "metric_values",
                "SELECT DISTINCT ON (metric_key) * "
                "FROM kokonut_agent_source.cids_metric_value "
                "WHERE location_id = %s AND verified = TRUE AND active = TRUE "
                "ORDER BY metric_key, computed_at DESC, metric_value_id DESC",
            ),
            (
                "feedback",
                "SELECT * FROM kokonut_agent_source.cids_stakeholder_feedback "
                "WHERE location_id = %s ORDER BY feedback_date, id",
            ),
            (
                "impact_claims",
                "SELECT * FROM kokonut_agent_source.cids_impact_claim "
                "WHERE location_id = %s AND status IN ('verified', 'published') "
                "ORDER BY claim_date, id",
            ),
        )
        result: dict[str, Any] = {}
        for key, query in queries:
            cur.execute(query, (location_id,))
            if key == "location":
                result[key] = cur.fetchone()
            else:
                result[key] = cur.fetchall()
        if not result["location"]:
            raise ValueError(f"Location not found: {location_id}")
        return result
    finally:
        close = getattr(cur, "close", None)
        if close:
            close()


def fetch_cids_source(
    conn, location_id: str, *, source_schema: str = "public"
) -> dict[str, Any]:
    """Fetch source rows needed to build the CIDS graph."""
    if source_schema == "kokonut_agent_source":
        return _fetch_scoped_cids_source(conn, location_id)
    if source_schema != "public":
        raise ValueError("source_schema must be public or kokonut_agent_source")
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
        SELECT l.*, f.id AS farm_id, f.name AS farm_name, f.slug AS farm_slug,
               f.description AS farm_description, f.total_area, f.area_unit,
               fr.id AS registry_id, fr.registry_slug, fr.project_date,
               fr.project_summary, fr.local_problem, fr.proposed_solution,
               fr.target_market, fr.revenue_streams, fr.governance_mechanism,
               fr.public_goods_allocation_pct, fr.status AS registry_status
        FROM location l
        LEFT JOIN farm f ON f.location_id = l.id
        LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
        WHERE l.id = %s
        ORDER BY fr.created_at DESC NULLS LAST, fr.id DESC NULLS LAST
        LIMIT 1
        """,
            (location_id,),
        )
        location = cur.fetchone()
        if not location:
            raise ValueError(f"Location not found: {location_id}")

        cur.execute(
            """
        SELECT so.*, em.label AS evidence_maturity_label
        FROM stakeholder_outcome so
        LEFT JOIN evidence_maturity_level em ON em.level = so.evidence_maturity
        WHERE so.location_id = %s AND so.status IN ('verified', 'published')
        ORDER BY so.created_at, so.id
        """,
            (location_id,),
        )
        stakeholder_outcomes = cur.fetchall()

        cur.execute(
            """
        SELECT fim.*, sdg.name AS sdg_name, foc.name AS capital_name, pov.name AS pillar_name
        FROM farm_impact_mapping fim
        LEFT JOIN sdg ON sdg.sdg_number = fim.sdg_number
        LEFT JOIN form_of_capital foc ON foc.capital_key = fim.capital_key
        LEFT JOIN pillar_of_value pov ON pov.pillar_key = fim.pillar_key
        WHERE fim.location_id = %s AND fim.status IN ('verified', 'published')
        ORDER BY fim.framework_key, fim.dimension_key, fim.sdg_number, fim.id
        """,
            (location_id,),
        )
        framework_mappings = cur.fetchall()

        cur.execute(
            """
        SELECT DISTINCT ON (md.metric_key)
               md.metric_key, md.display_name, md.description, md.unit, md.data_type,
               md.for_stakeholder_group, md.participatory, md.report_usage,
               mv.id AS metric_value_id, mv.period_start, mv.period_end, mv.value,
               mv.unit AS value_unit, mv.verified, mv.computation_method
        FROM metric_value mv
        JOIN metric_definition md ON md.id = mv.metric_id
        WHERE mv.location_id = %s AND mv.verified = TRUE AND md.active = TRUE
        ORDER BY md.metric_key, mv.computed_at DESC, mv.id DESC
        """,
            (location_id,),
        )
        metric_values = cur.fetchall()

        cur.execute(
            """
        SELECT sf.*, em.label AS evidence_maturity_label
        FROM stakeholder_feedback sf
        LEFT JOIN evidence_maturity_level em ON em.level = sf.evidence_maturity
        WHERE sf.location_id = %s
          AND sf.is_public = TRUE
          AND sf.consent_given = TRUE
          AND sf.consent_scope IN ('public_summary', 'public_quote', 'public_full')
          AND sf.status = 'published'
          AND NULLIF(TRIM(COALESCE(sf.public_summary, '')), '') IS NOT NULL
        ORDER BY sf.feedback_date, sf.id
        """,
            (location_id,),
        )
        feedback = cur.fetchall()

        cur.execute(
            """
        SELECT ic.*, em.label AS evidence_maturity_label
        FROM impact_claim ic
        LEFT JOIN evidence_maturity_level em ON em.level = ic.evidence_maturity
        WHERE ic.location_id = %s AND ic.status IN ('verified', 'published')
        ORDER BY ic.claim_date, ic.id
        """,
            (location_id,),
        )
        impact_claims = cur.fetchall()

        return {
            "location": location,
            "stakeholder_outcomes": stakeholder_outcomes,
            "framework_mappings": framework_mappings,
            "metric_values": metric_values,
            "feedback": feedback,
            "impact_claims": impact_claims,
        }
    finally:
        close = getattr(cur, "close", None)
        if close:
            close()


def _source_views(source_schema: str, source_key: str) -> tuple[str, ...]:
    signed_views = {
        "location": ("kokonut_agent_source.cids_location",),
        "stakeholder_outcomes": ("kokonut_agent_source.cids_stakeholder_outcome",),
        "framework_mappings": ("kokonut_agent_source.cids_farm_impact_mapping",),
        "metric_values": ("kokonut_agent_source.cids_metric_value",),
        "feedback": ("kokonut_agent_source.cids_stakeholder_feedback",),
        "impact_claims": ("kokonut_agent_source.cids_impact_claim",),
    }
    public_tables = {
        "location": ("public.location", "public.farm", "public.farm_registry_record"),
        "stakeholder_outcomes": ("public.stakeholder_outcome",),
        "framework_mappings": ("public.farm_impact_mapping", "public.sdg"),
        "metric_values": ("public.metric_value", "public.metric_definition"),
        "feedback": ("public.stakeholder_feedback",),
        "impact_claims": ("public.impact_claim", "public.evidence_maturity_level"),
    }
    if source_schema == "kokonut_agent_source":
        return signed_views[source_key]
    if source_schema == "public":
        return public_tables[source_key]
    raise ValueError("source_schema must be public or kokonut_agent_source")


def _with_source_views(
    item: dict[str, Any],
    source_views: tuple[str, ...] | set[str],
    property_source_views: dict[str, tuple[str, ...] | set[str]] | None = None,
) -> dict[str, Any]:
    clean_item = _strip_none(item)
    if property_source_views is None:
        property_source_views = {
            key: source_views
            for key in clean_item
            if key not in {"@context", "@type"}
        }
    normalized_property_views = {
        key: sorted(set(views))
        for key, views in property_source_views.items()
        if key in clean_item and key not in {"@context", "@type"}
    }
    node_views = set(source_views)
    for views in normalized_property_views.values():
        node_views.update(views)
    return _context(
        {
            **clean_item,
            "kokonut:sourceViews": sorted(node_views),
            "kokonut:propertySourceViews": normalized_property_views,
        }
    )


def build_cids_graph(
    source: dict[str, Any], *, source_schema: str = "public"
) -> list[dict[str, Any]]:
    """Build a CIDS Essential Tier JSON-LD graph from fetched Kokonut rows."""
    location = source["location"]
    location_slug = _slug(location.get("slug"))
    location_views = _source_views(source_schema, "location")
    org_id = _uri("Organization", location_slug)
    program_id = _uri("Program", f"{location_slug}-farm-program")
    impact_pathway_id = _uri("ImpactPathway", f"{location_slug}-impact-pathway")

    outcome_ids = [
        _uri("Outcome", f"{location_slug}-{_slug(row.get('outcome_name'))}") for row in source["stakeholder_outcomes"]
    ]
    indicator_ids = [
        _uri("Indicator", f"{location_slug}-{_slug(row.get('metric_key'))}") for row in source["metric_values"]
    ]
    stakeholder_sources: dict[str, set[str]] = {}
    for source_key in ("stakeholder_outcomes", "feedback"):
        views = _source_views(source_schema, source_key)
        for row in source[source_key]:
            group = row.get("stakeholder_group")
            if group:
                stakeholder_id = _uri("Stakeholder", _slug(group))
                stakeholder_sources.setdefault(stakeholder_id, set()).update(views)
    stakeholder_ids = sorted(stakeholder_sources)
    outcome_views = _source_views(source_schema, "stakeholder_outcomes")
    metric_views = _source_views(source_schema, "metric_values")
    stakeholder_views = tuple(
        sorted({view for views in stakeholder_sources.values() for view in views})
    )

    graph: list[dict[str, Any]] = []
    graph.append(
        _with_source_views(
            {
                "@type": "cids:Organization",
                "@id": org_id,
                "hasName": location.get("farm_name") or location.get("name"),
                "hasLegalName": location.get("farm_name") or location.get("name"),
                "hasDescription": location.get("farm_description") or location.get("description"),
                "hasProgram": [program_id],
                "hasOutcome": outcome_ids,
                "hasIndicator": indicator_ids,
                "hasStakeholder": stakeholder_ids,
            },
            location_views,
            {
                "@id": location_views,
                "hasName": location_views,
                "hasLegalName": location_views,
                "hasDescription": location_views,
                "hasProgram": location_views,
                "hasOutcome": outcome_views if outcome_ids else (),
                "hasIndicator": metric_views if indicator_ids else (),
                "hasStakeholder": stakeholder_views,
            },
        )
    )

    graph.append(
        _with_source_views(
            {
                "@type": "cids:Program",
                "@id": program_id,
                "hasName": location.get("project_summary") or f"{location.get('name')} farm program",
                "hasDescription": location.get("proposed_solution") or location.get("description"),
                "forOrganization": org_id,
                "hasImpactModel": [impact_pathway_id],
            },
            location_views,
            {
                "@id": location_views,
                "hasName": location_views,
                "hasDescription": location_views,
                "forOrganization": location_views,
                "hasImpactModel": location_views,
            },
        )
    )

    graph.append(
        _with_source_views(
            {
                "@type": "cids:ImpactPathway",
                "@id": impact_pathway_id,
                "hasName": f"{location.get('name')} impact pathway",
                "hasDescription": location.get("local_problem") or "Kokonut farm impact pathway",
                "forOrganization": org_id,
                "hasOutcome": outcome_ids,
                "hasIndicator": indicator_ids,
            },
            location_views,
            {
                "@id": location_views,
                "hasName": location_views,
                "hasDescription": location_views,
                "forOrganization": location_views,
                "hasOutcome": outcome_views if outcome_ids else (),
                "hasIndicator": metric_views if indicator_ids else (),
            },
        )
    )

    added_themes: set[str] = set()
    for row in source["framework_mappings"]:
        if row.get("sdg_number"):
            theme_id = f"{SDG_BASE_URL}/{row['sdg_number']}"
            if theme_id not in added_themes:
                graph.append(
                    _with_source_views(
                        {
                            "@type": "cids:Theme",
                            "@id": theme_id,
                            "hasName": row.get("sdg_name") or f"SDG {row['sdg_number']}",
                            "hasDescription": f"UN Sustainable Development Goal {row['sdg_number']}",
                            "hasCode": [theme_id],
                        },
                        _source_views(source_schema, "framework_mappings"),
                        {
                            "@id": _source_views(source_schema, "framework_mappings"),
                            "hasName": _source_views(source_schema, "framework_mappings"),
                            "hasDescription": _source_views(source_schema, "framework_mappings"),
                            "hasCode": _source_views(source_schema, "framework_mappings"),
                        },
                    )
                )
                added_themes.add(theme_id)

    for stakeholder_id in stakeholder_ids:
        group = stakeholder_id.rsplit("/", 1)[-1]
        graph.append(
            _with_source_views(
                {
                    "@type": "cids:Stakeholder",
                    "@id": stakeholder_id,
                    "hasName": group.replace("-", " ").title(),
                    "forOrganization": org_id,
                },
                stakeholder_sources[stakeholder_id] | set(location_views),
                {
                    "@id": stakeholder_sources[stakeholder_id],
                    "hasName": stakeholder_sources[stakeholder_id],
                    "forOrganization": location_views,
                },
            )
        )

    for row in source["stakeholder_outcomes"]:
        outcome_id = _uri("Outcome", f"{location_slug}-{_slug(row.get('outcome_name'))}")
        stakeholder_id = _uri("Stakeholder", _slug(row.get("stakeholder_group")))
        stakeholder_outcome_id = _uri("StakeholderOutcome", str(row["id"]))
        theme_ids = []
        if row.get("sdg_number"):
            theme_ids.append(f"{SDG_BASE_URL}/{row['sdg_number']}")
        graph.append(
            _with_source_views(
                {
                    "@type": "cids:Outcome",
                    "@id": outcome_id,
                    "hasName": row.get("outcome_name"),
                    "hasDescription": row.get("outcome_description"),
                    "forOrganization": org_id,
                    "forTheme": theme_ids,
                    "hasStakeholderOutcome": [stakeholder_outcome_id],
                },
                outcome_views,
                {
                    "@id": set(outcome_views) | set(location_views),
                    "hasName": outcome_views,
                    "hasDescription": outcome_views,
                    "forOrganization": location_views,
                    "forTheme": outcome_views,
                    "hasStakeholderOutcome": outcome_views,
                },
            )
        )
        graph.append(
            _with_source_views(
                {
                    "@type": "cids:StakeholderOutcome",
                    "@id": stakeholder_outcome_id,
                    "hasName": row.get("outcome_name"),
                    "hasDescription": row.get("outcome_description"),
                    "forStakeholder": stakeholder_id,
                    "forOutcome": outcome_id,
                    "hasImportance": row.get("importance"),
                    "isUnderserved": bool(row.get("is_underserved")),
                    "hasImpactManagementNormsDefinition": row.get("importance_perspective"),
                },
                outcome_views,
                {
                    "@id": outcome_views,
                    "hasName": outcome_views,
                    "hasDescription": outcome_views,
                    "forStakeholder": outcome_views,
                    "forOutcome": outcome_views,
                    "hasImportance": outcome_views,
                    "isUnderserved": outcome_views,
                    "hasImpactManagementNormsDefinition": outcome_views,
                },
            )
        )

    seen_indicators: set[str] = set()
    for row in source["metric_values"]:
        indicator_id = _uri("Indicator", f"{location_slug}-{_slug(row.get('metric_key'))}")
        report_id = _uri("IndicatorReport", str(row["metric_value_id"]))
        unit_uri = _unit_uri(row.get("value_unit") or row.get("unit"))
        ebf_pillar = _ebf_pillar_from_metric(row.get("metric_key"))
        if indicator_id not in seen_indicators:
            graph.append(
                _with_source_views(
                    {
                        "@type": "cids:Indicator",
                        "@id": indicator_id,
                        "hasName": row.get("display_name"),
                        "hasDescription": row.get("description"),
                        "unit_of_measure": unit_uri,
                        "forOrganization": org_id,
                        "hasIndicatorReport": [report_id],
                        "hasComment": "Kokonut governed metric definition",
                        "kokonut:framework": "ebf" if ebf_pillar else None,
                        "kokonut:ebfPillar": ebf_pillar,
                    },
                    set(metric_views) | set(location_views),
                    {
                        "@id": set(metric_views) | set(location_views),
                        "hasName": metric_views,
                        "hasDescription": metric_views,
                        "unit_of_measure": metric_views,
                        "forOrganization": location_views,
                        "hasIndicatorReport": metric_views,
                        "hasComment": (),
                        "kokonut:framework": metric_views,
                        "kokonut:ebfPillar": metric_views,
                    },
                )
            )
            seen_indicators.add(indicator_id)
        graph.append(
            _with_source_views(
                {
                    "@type": "cids:IndicatorReport",
                    "@id": report_id,
                    "hasName": f"{location.get('name')} - {row.get('display_name')}",
                    "value": _measure(row.get("value"), unit_uri),
                    "startedAtTime": f"{row['period_start']}T00:00:00Z" if row.get("period_start") else None,
                    "endedAtTime": f"{row['period_end']}T23:59:59Z" if row.get("period_end") else None,
                    "forIndicator": indicator_id,
                    "forOrganization": org_id,
                    "hasComment": row.get("computation_method"),
                    "kokonut:framework": "ebf" if ebf_pillar else None,
                    "kokonut:ebfPillar": ebf_pillar,
                    "kokonut:cidsMapping": "metric_value -> cids:IndicatorReport" if ebf_pillar else None,
                },
                set(metric_views) | set(location_views),
                {
                    "@id": metric_views,
                    "hasName": set(metric_views) | set(location_views),
                    "value": metric_views,
                    "startedAtTime": metric_views,
                    "endedAtTime": metric_views,
                    "forIndicator": metric_views,
                    "forOrganization": location_views,
                    "hasComment": metric_views,
                    "kokonut:framework": metric_views,
                    "kokonut:ebfPillar": metric_views,
                    "kokonut:cidsMapping": metric_views,
                },
            )
        )

    for row in source["impact_claims"]:
        claim_id = _uri("ImpactReport", str(row["id"]))
        graph.append(
            _with_source_views(
                {
                    "@type": "cids:ImpactReport",
                    "@id": claim_id,
                    "hasName": row.get("claim_text")[:120] if row.get("claim_text") else "Impact claim",
                    "hasDescription": row.get("claim_text"),
                    "forOrganization": org_id,
                    "startedAtTime": f"{row['period_start']}T00:00:00Z" if row.get("period_start") else None,
                    "endedAtTime": f"{row['period_end']}T23:59:59Z" if row.get("period_end") else None,
                    "hasComment": row.get("confidence_notes"),
                    "kokonut:evidenceMaturity": row.get("evidence_maturity"),
                    "kokonut:evidenceMaturityLabel": row.get("evidence_maturity_label"),
                    "kokonut:methodologyRef": row.get("methodology_ref"),
                    "kokonut:externalVerifier": row.get("external_verifier"),
                    "kokonut:attestationUid": row.get("attestation_uid"),
                },
                set(_source_views(source_schema, "impact_claims")) | set(location_views),
                {
                    "@id": _source_views(source_schema, "impact_claims"),
                    "hasName": _source_views(source_schema, "impact_claims"),
                    "hasDescription": _source_views(source_schema, "impact_claims"),
                    "forOrganization": location_views,
                    "startedAtTime": _source_views(source_schema, "impact_claims"),
                    "endedAtTime": _source_views(source_schema, "impact_claims"),
                    "hasComment": _source_views(source_schema, "impact_claims"),
                    "kokonut:evidenceMaturity": _source_views(source_schema, "impact_claims"),
                    "kokonut:evidenceMaturityLabel": _source_views(source_schema, "impact_claims"),
                    "kokonut:methodologyRef": _source_views(source_schema, "impact_claims"),
                    "kokonut:externalVerifier": _source_views(source_schema, "impact_claims"),
                    "kokonut:attestationUid": _source_views(source_schema, "impact_claims"),
                },
            )
        )

    return graph


def _strip_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_strip_none(item) for item in value if item is not None]
    return value


def export_location(
    conn, location_id: str, *, source_schema: str = "public"
) -> dict[str, Any]:
    """Export a location as a CIDS Essential Tier JSON-LD document."""
    source = fetch_cids_source(conn, location_id, source_schema=source_schema)
    return {
        "@context": CIDS_CONTEXTS,
        "@graph": build_cids_graph(source, source_schema=source_schema),
        "kokonut:cidsVersion": CIDS_VERSION,
        "kokonut:alignmentTier": "essential",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Kokonut records as CIDS JSON-LD")
    parser.add_argument("--location-id", required=True, help="Location UUID to export")
    args = parser.parse_args()
    from services.agents.worker_cli import run_worker_cids_export

    result = run_worker_cids_export(args.location_id)
    print(json.dumps(result["document"], indent=2, default=_json_default))


if __name__ == "__main__":
    main()
