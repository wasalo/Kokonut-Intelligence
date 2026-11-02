"""Report generators: scaling."""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from services.common.database import query

from ..common import _looks_like_uuid, _serialize_rows
from ..scope import require_network_scope


def generate_scaling_economics(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate public-safe scaling economics and unit-cost report."""
    network_scope = location_id in (None, "all")
    if not network_scope and not _looks_like_uuid(location_id):
        raise ValueError("scaling_economics requires a valid location_id or network scope")

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if network_scope:
            cur.execute(
                """
                SELECT id,
                       location_id,
                       source_scaling_milestone_id,
                       economics_name,
                       farm_model,
                       target_region,
                       planned_farm_count,
                       planned_hectares,
                       expected_beneficiary_count,
                       setup_cost_usd,
                       first_year_operating_cost_usd,
                       verification_overhead_usd,
                       total_launch_cost_usd,
                       cost_per_farm_usd,
                       cost_per_hectare_usd,
                       cost_per_beneficiary_usd,
                       projected_annual_revenue_usd,
                       projected_annual_noi_usd,
                       projected_roi_pct,
                       payback_months,
                       launch_timeline_months,
                       assumptions,
                       evidence_confidence,
                       public_summary,
                       evidence_maturity,
                       evidence_maturity_label,
                       metadata
                FROM v_public_farm_launch_unit_economics
                ORDER BY target_region, economics_name
                """
            )
        else:
            cur.execute(
                """
                SELECT id,
                       location_id,
                       source_scaling_milestone_id,
                       economics_name,
                       farm_model,
                       target_region,
                       planned_farm_count,
                       planned_hectares,
                       expected_beneficiary_count,
                       setup_cost_usd,
                       first_year_operating_cost_usd,
                       verification_overhead_usd,
                       total_launch_cost_usd,
                       cost_per_farm_usd,
                       cost_per_hectare_usd,
                       cost_per_beneficiary_usd,
                       projected_annual_revenue_usd,
                       projected_annual_noi_usd,
                       projected_roi_pct,
                       payback_months,
                       launch_timeline_months,
                       assumptions,
                       evidence_confidence,
                       public_summary,
                       evidence_maturity,
                       evidence_maturity_label,
                       metadata
                FROM v_public_farm_launch_unit_economics
                WHERE location_id = %s::uuid
                ORDER BY target_region, economics_name
                """,
                (location_id,),
            )
        economics = [dict(r) for r in cur.fetchall()]

        targets = []
        if network_scope:
            cur.execute(
                """
                SELECT id,
                       target_name,
                       target_region,
                       farm_model,
                       target_date,
                       target_farm_count,
                       target_hectares,
                       target_beneficiary_count,
                       capital_required_usd,
                       capital_required_per_farm_usd,
                       expected_public_goods_value_usd,
                       expected_verification_outputs,
                       readiness_score,
                       dependency_summary,
                       risk_gate_summary,
                       target_status,
                       public_summary,
                       evidence_maturity,
                       evidence_maturity_label,
                       metadata
                FROM v_public_network_scaling_target
                WHERE (%s::date IS NULL OR target_date >= %s::date)
                  AND (%s::date IS NULL OR target_date <= %s::date)
                ORDER BY target_date, target_name
                """,
                (period_start, period_start, period_end, period_end),
            )
            targets = [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()

    total_launch_cost = sum(float(row.get("total_launch_cost_usd") or 0) for row in economics)
    total_target_capital = sum(float(row.get("capital_required_usd") or 0) for row in targets)
    planned_farms = sum(int(row.get("planned_farm_count") or 0) for row in economics)
    target_farms = sum(int(row.get("target_farm_count") or 0) for row in targets) if network_scope else None
    limitations = [
        "Scaling economics are planning evidence, not guaranteed ROI or securities-style return claims.",
        "Planned farm counts are roadmap targets unless backed by separate registry records.",
        "Private capital terms, side letters, and unsupported external integrations are excluded.",
    ]
    if not network_scope:
        limitations.append("Network-wide scaling targets are omitted from farm-scoped snapshots.")
    return {
        "report_type": "scaling_economics",
        "location_id": None if network_scope else location_id,
        "scope": "network" if network_scope else "location",
        "unit_economics": _serialize_rows(economics),
        "network_targets": _serialize_rows(targets),
        "total_launch_cost_usd": round(total_launch_cost, 2) if network_scope else None,
        "total_target_capital_usd": round(total_target_capital, 2) if network_scope else None,
        "planned_farm_count": planned_farms,
        "target_farm_count": target_farms,
        "limitations": limitations,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }




def generate_adoption_barriers(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe barrier report with an explicit location scope."""
    if not _looks_like_uuid(location_id):
        raise ValueError("adoption_barriers requires an explicit location_id")

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT id,
                   location_id,
                   assessment_date,
                   barrier_category,
                   barrier_name,
                   affected_scope,
                   severity,
                   likelihood,
                   resolution_status,
                   owner_role,
                   mitigation_plan,
                   estimated_mitigation_cost_usd,
                   target_resolution_date,
                   public_summary,
                   evidence_maturity,
                   evidence_maturity_label,
                   metadata
            FROM v_public_adoption_barrier_assessment
            WHERE (location_id = %s OR location_id IS NULL)
              AND (%s::date IS NULL OR assessment_date >= %s::date)
              AND (%s::date IS NULL OR assessment_date <= %s::date)
            ORDER BY assessment_date DESC, barrier_category, barrier_name
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
        barriers = [dict(r) for r in cur.fetchall()]
    finally:
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
    if not _looks_like_uuid(location_id):
        raise ValueError("perpetual_value_stress requires an explicit location_id")

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT id,
                   location_id,
                   financial_sustainability_plan_id,
                   scenario_name,
                   scenario_date,
                   stress_type,
                   revenue_change_pct,
                   cost_change_pct,
                   grant_delay_months,
                   yield_change_pct,
                   baseline_runway_months,
                   downside_runway_months,
                   baseline_noi_usd,
                   downside_noi_usd,
                   solvency_status,
                   mitigation_actions,
                   public_summary,
                   evidence_maturity,
                   evidence_maturity_label,
                   metadata
            FROM v_public_perpetual_value_stress_test
            WHERE (location_id = %s OR location_id IS NULL)
              AND (%s::date IS NULL OR scenario_date >= %s::date)
              AND (%s::date IS NULL OR scenario_date <= %s::date)
            ORDER BY scenario_date DESC, stress_type, scenario_name
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
        scenarios = [dict(r) for r in cur.fetchall()]
    finally:
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
    require_network_scope("open_source_impact", location_id)
    artifacts = query(conn,
        """SELECT id,
                  artifact_name,
                  artifact_type,
                  repository_path,
                  external_url,
                  license,
                  version,
                  reuse_status,
                  reuse_count,
                  supported_use_cases,
                  verification_outputs,
                  maintenance_owner,
                  public_summary,
                  evidence_maturity,
                  evidence_maturity_label,
                  metadata
           FROM v_public_open_source_impact_artifact
           ORDER BY reuse_count DESC, artifact_type, artifact_name"""
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


