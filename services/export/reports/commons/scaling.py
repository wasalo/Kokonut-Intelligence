"""Report generators: scaling."""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from services.common.database import query

from ..common import _serialize_rows


def generate_scaling_economics(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate public-safe scaling economics and unit-cost report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_farm_launch_unit_economics
            WHERE location_id = %s OR location_id IS NULL
            ORDER BY target_region, economics_name
            """,
            (location_id,),
        )
    else:
        cur.execute("SELECT * FROM v_public_farm_launch_unit_economics ORDER BY target_region, economics_name")
    economics = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT *
        FROM v_public_network_scaling_target
        WHERE (%s::date IS NULL OR target_date >= %s::date)
          AND (%s::date IS NULL OR target_date <= %s::date)
        ORDER BY target_date, target_name
        """,
        (period_start, period_start, period_end, period_end),
    )
    targets = [dict(r) for r in cur.fetchall()]
    cur.close()

    total_launch_cost = sum(float(row.get("total_launch_cost_usd") or 0) for row in economics)
    total_target_capital = sum(float(row.get("capital_required_usd") or 0) for row in targets)
    planned_farms = sum(int(row.get("planned_farm_count") or 0) for row in economics)
    target_farms = sum(int(row.get("target_farm_count") or 0) for row in targets)
    return {
        "report_type": "scaling_economics",
        "location_id": location_id,
        "unit_economics": _serialize_rows(economics),
        "network_targets": _serialize_rows(targets),
        "total_launch_cost_usd": round(total_launch_cost, 2),
        "total_target_capital_usd": round(total_target_capital, 2),
        "planned_farm_count": planned_farms,
        "target_farm_count": target_farms,
        "limitations": [
            "Scaling economics are planning evidence, not guaranteed ROI or securities-style return claims.",
            "Planned farm counts are roadmap targets unless backed by separate registry records.",
            "Private capital terms, side letters, and unsupported external integrations are excluded.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }




def generate_adoption_barriers(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate public-safe adoption and market barrier report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_adoption_barrier_assessment
            WHERE (location_id = %s OR location_id IS NULL)
              AND (%s::date IS NULL OR assessment_date >= %s::date)
              AND (%s::date IS NULL OR assessment_date <= %s::date)
            ORDER BY assessment_date DESC, barrier_category, barrier_name
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM v_public_adoption_barrier_assessment
            WHERE (%s::date IS NULL OR assessment_date >= %s::date)
              AND (%s::date IS NULL OR assessment_date <= %s::date)
            ORDER BY assessment_date DESC, barrier_category, barrier_name
            """,
            (period_start, period_start, period_end, period_end),
        )
    barriers = [dict(r) for r in cur.fetchall()]
    cur.close()
    active = [row for row in barriers if row.get("resolution_status") in {"open", "mitigating", "blocked"}]
    return {
        "report_type": "adoption_barriers",
        "location_id": location_id,
        "barriers": _serialize_rows(barriers),
        "active_barrier_count": len(active),
        "limitations": [
            "Barrier reports summarize public-safe categories and do not expose private stakeholder feedback.",
            "Regulatory and cultural readiness must be reviewed per location before expansion claims are made.",
            "Mitigation costs are planning estimates unless backed by verified expense records.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }




def generate_perpetual_value_stress(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    """Generate public-safe downside stress-test report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_perpetual_value_stress_test
            WHERE (location_id = %s OR location_id IS NULL)
              AND (%s::date IS NULL OR scenario_date >= %s::date)
              AND (%s::date IS NULL OR scenario_date <= %s::date)
            ORDER BY scenario_date DESC, stress_type, scenario_name
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM v_public_perpetual_value_stress_test
            WHERE (%s::date IS NULL OR scenario_date >= %s::date)
              AND (%s::date IS NULL OR scenario_date <= %s::date)
            ORDER BY scenario_date DESC, stress_type, scenario_name
            """,
            (period_start, period_start, period_end, period_end),
        )
    scenarios = [dict(r) for r in cur.fetchall()]
    cur.close()
    watchlist = [
        row
        for row in scenarios
        if row.get("solvency_status") in {"watchlist", "needs_mitigation", "insolvent_without_support"}
    ]
    return {
        "report_type": "perpetual_value_stress",
        "location_id": location_id,
        "stress_tests": _serialize_rows(scenarios),
        "watchlist_or_mitigation_count": len(watchlist),
        "limitations": [
            "Stress tests are planning evidence and do not guarantee solvency or capital availability.",
            "Down-cycle assumptions should be refreshed as market, climate, cost, and governance records mature.",
            "Private reserves or unpublished funder commitments are excluded.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }




def generate_open_source_impact(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    """Generate public-safe open-source artifact reuse report."""
    artifacts = query(conn,
        "SELECT * FROM v_public_open_source_impact_artifact ORDER BY reuse_count DESC, artifact_type, artifact_name"
    )
    return {
        "report_type": "open_source_impact",
        "location_id": location_id,
        "artifacts": _serialize_rows(artifacts),
        "artifact_count": len(artifacts),
        "total_reuse_count": sum(int(row.get("reuse_count") or 0) for row in artifacts),
        "limitations": [
            "Open-source artifact reuse counts are governed evidence signals, not claims of external adoption unless separately sourced.",
            "Hypercert, Ecocertain, or other external integrations should not be claimed until canonical records exist.",
            "Repository paths and public URLs may identify reusable artifacts but do not imply third-party certification.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


