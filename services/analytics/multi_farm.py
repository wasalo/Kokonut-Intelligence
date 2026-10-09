"""Multi-farm onboarding — template instantiation, cross-farm portfolio."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("analytics.multi_farm")


def instantiate_farm_from_template(
    conn,
    template_id: str,
    location_id: str,
    customizations: dict = None,
) -> Dict[str, Any]:
    """Apply a farm template to a location.

    Creates farm_template_instance and generates onboarding workflow steps.
    """
    # Get template
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM farm_template WHERE id = %s", (template_id,))
    template = cur.fetchone()
    if not template:
        cur.close()
        return {"status": "error", "message": "Template not found"}

    template = dict(template)

    # Create template instance
    cur2 = conn.cursor()
    cur2.execute("""
        INSERT INTO farm_template_instance (farm_id, location_id, template_id, template_version, customizations)
        SELECT f.id, %s, %s, %s, %s
        FROM farm f WHERE f.location_id = %s
        RETURNING id
    """, (location_id, template_id, template.get("version", "1.0"), json.dumps(customizations or {}), location_id))
    instance_id = str(cur2.fetchone()[0])

    # Generate onboarding workflow steps
    steps = [
        ("land_assessment", "Land Assessment"),
        ("community_engagement", "Community Engagement"),
        ("template_selection", "Template Selection"),
        ("farm_specification", "Farm Specification"),
        ("zone_setup", "Zone Setup"),
        ("governance_setup", "Governance Setup"),
        ("token_binding", "Token Binding"),
        ("soil_baseline", "Soil Baseline"),
        ("planting", "Planting"),
        ("monitoring_setup", "Monitoring Setup"),
        ("mrve_setup", "MRV Setup"),
        ("certification", "Certification"),
        ("go_live", "Go Live"),
    ]

    for i, (step_type, step_name) in enumerate(steps):
        cur2.execute("""
            INSERT INTO farm_onboarding_workflow (farm_id, location_id, step_order, step_name, step_type, status)
            SELECT f.id, %s, %s, %s, %s, 'pending'
            FROM farm f WHERE f.location_id = %s
        """, (location_id, i + 1, step_name, step_type, location_id))

    conn.commit()
    cur.close()
    cur2.close()

    logger.info("Instantiated farm from template %s at location %s", template_id[:8], location_id[:8])
    return {
        "instance_id": instance_id,
        "template_name": template.get("template_name"),
        "template_version": template.get("version"),
        "steps_created": len(steps),
    }


def compute_cross_farm_portfolio(conn) -> Dict[str, Any]:
    """Aggregate metrics across all active farms."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Farm count and area
    cur.execute("""
        SELECT COUNT(*) AS farm_count,
               COALESCE(SUM(frr.land_size_m2), 0) AS total_area_m2
        FROM farm_registry_record frr
        WHERE frr.status IN ('verified', 'published')
    """)
    farms = dict(cur.fetchone() or {})

    # Tree count
    cur.execute("SELECT COUNT(*) AS total_trees FROM tree_record WHERE status = 'alive'")
    trees = dict(cur.fetchone() or {})

    # Revenue
    cur.execute("SELECT COALESCE(SUM(amount), 0) AS total_revenue FROM revenue_event")
    revenue = dict(cur.fetchone() or {})

    # Carbon
    cur.execute("SELECT COALESCE(SUM(total_sequestration_tonnes_co2e), 0) AS total_carbon FROM climate_impact_summary")
    carbon = dict(cur.fetchone() or {})

    # Regen score
    cur.execute("SELECT COALESCE(AVG(total_score), 0) AS avg_regen FROM regenerative_outcome_summary")
    regen = dict(cur.fetchone() or {})

    # EBF score
    cur.execute("SELECT COALESCE(AVG(overall_score), 0) AS avg_ebf FROM ebf_scorecard WHERE status = 'published'")
    ebf = dict(cur.fetchone() or {})

    cur.close()

    return {
        "total_farm_count": int(farms.get("farm_count", 0) or 0),
        "total_area_m2": round(float(farms.get("total_area_m2", 0) or 0), 2),
        "total_trees": int(trees.get("total_trees", 0) or 0),
        "total_revenue_usd": round(float(revenue.get("total_revenue", 0) or 0), 2),
        "total_carbon_sequestered": round(float(carbon.get("total_carbon", 0) or 0), 4),
        "avg_regen_score": round(float(regen.get("avg_regen", 0) or 0), 2),
        "avg_ebf_score": round(float(ebf.get("avg_ebf", 0) or 0), 2),
    }


def get_farm_comparison(conn, location_ids: List[str]) -> List[Dict[str, Any]]:
    """Compare multiple farms side-by-side."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    results = []
    for loc_id in location_ids:
        cur.execute("SELECT name FROM location WHERE id = %s", (loc_id,))
        loc = cur.fetchone()
        name = loc["name"] if loc else "Unknown"

        # Tree count
        cur.execute("SELECT COUNT(*) AS trees FROM tree_record WHERE location_id = %s AND status = 'alive'", (loc_id,))
        trees = int(cur.fetchone()["trees"] or 0)

        # Revenue
        cur.execute("SELECT COALESCE(SUM(amount), 0) AS revenue FROM revenue_event WHERE location_id = %s", (loc_id,))
        rev = float(cur.fetchone()["revenue"] or 0)

        # Carbon
        cur.execute("SELECT COALESCE(SUM(total_sequestration_tonnes_co2e), 0) AS carbon FROM climate_impact_summary WHERE location_id = %s", (loc_id,))
        carbon = float(cur.fetchone()["carbon"] or 0)

        # Regen score
        cur.execute("SELECT COALESCE(AVG(total_score), 0) AS regen FROM regenerative_outcome_summary WHERE location_id = %s", (loc_id,))
        regen = float(cur.fetchone()["regen"] or 0)

        results.append({
            "location_id": loc_id,
            "location_name": name,
            "total_trees": trees,
            "total_revenue_usd": round(rev, 2),
            "total_carbon_sequestered": round(carbon, 4),
            "avg_regen_score": round(regen, 2),
        })

    cur.close()
    return results
