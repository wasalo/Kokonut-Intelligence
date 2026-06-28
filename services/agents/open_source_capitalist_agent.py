"""Open Source Capitalist scaling economics synthesis agent."""

from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

import psycopg2
import psycopg2.extras

from services.agents.safety import assert_agent_action_allowed
from services.agents.tasks import validate_output
from services.common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER


def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
    )


def _location_filter(column: str, location_id: str | None) -> tuple[str, tuple[Any, ...]]:
    if location_id:
        return f"WHERE {column} = %s OR {column} IS NULL", (location_id,)
    return "", ()


def synthesize_open_source_capitalist(conn, location_id: str | None = None) -> dict[str, Any]:
    """Summarize public-safe scaling economics, barriers, stress tests, and open-source reuse."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT economics_name, location_id, target_region, farm_model,
               planned_farm_count, planned_hectares, expected_beneficiary_count,
               total_launch_cost_usd, cost_per_farm_usd, cost_per_hectare_usd,
               cost_per_beneficiary_usd, projected_annual_revenue_usd,
               projected_annual_noi_usd, projected_roi_pct, payback_months,
               launch_timeline_months, assumptions, evidence_confidence,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_farm_launch_unit_economics
        {where}
        ORDER BY target_region, economics_name
        """,
        params,
    )
    economics_rows = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT target_name, target_region, farm_model, target_date, target_farm_count,
               target_hectares, target_beneficiary_count, capital_required_usd,
               capital_required_per_farm_usd, expected_public_goods_value_usd,
               expected_verification_outputs, readiness_score, dependency_summary,
               risk_gate_summary, target_status, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_network_scaling_target
        ORDER BY target_date, target_name
        """
    )
    target_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT assessment_date, barrier_category, barrier_name, affected_scope,
               severity, likelihood, resolution_status, owner_role,
               estimated_mitigation_cost_usd, target_resolution_date,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_adoption_barrier_assessment
        {where}
        ORDER BY assessment_date DESC, barrier_category, barrier_name
        """,
        params,
    )
    barrier_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT scenario_name, location_id, scenario_date, stress_type,
               revenue_change_pct, cost_change_pct, grant_delay_months,
               yield_change_pct, baseline_runway_months, downside_runway_months,
               baseline_noi_usd, downside_noi_usd, solvency_status,
               mitigation_actions, public_summary, evidence_maturity,
               evidence_maturity_label
        FROM v_public_perpetual_value_stress_test
        {where}
        ORDER BY scenario_date DESC, stress_type, scenario_name
        """,
        params,
    )
    stress_rows = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT artifact_name, artifact_type, repository_path, external_url,
               license, version, reuse_status, reuse_count, supported_use_cases,
               verification_outputs, maintenance_owner, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_open_source_impact_artifact
        ORDER BY reuse_count DESC, artifact_type, artifact_name
        """
    )
    artifact_rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    total_launch_cost = sum(float(row.get("total_launch_cost_usd") or 0) for row in economics_rows)
    planned_farms = sum(int(row.get("planned_farm_count") or 0) for row in economics_rows)
    target_farms = sum(int(row.get("target_farm_count") or 0) for row in target_rows)
    active_barriers = [row for row in barrier_rows if row.get("resolution_status") in {"open", "mitigating", "blocked"}]
    stress_gaps = [row for row in stress_rows if row.get("solvency_status") in {"watchlist", "needs_mitigation", "insolvent_without_support"}]

    synthesis_lines = []
    if economics_rows:
        synthesis_lines.append(f"{len(economics_rows)} launch economics record(s) cover {planned_farms} planned farm(s) and ${total_launch_cost:,.0f} launch cost.")
    else:
        synthesis_lines.append("No public launch economics records are available.")
    if target_rows:
        synthesis_lines.append(f"{len(target_rows)} network scaling target(s) cover {target_farms} planned farm(s).")
    if barrier_rows:
        synthesis_lines.append(f"{len(barrier_rows)} adoption barrier(s) are documented; {len(active_barriers)} remain open, mitigating, or blocked.")
    if stress_rows:
        synthesis_lines.append(f"{len(stress_rows)} stress-test scenario(s) are available; {len(stress_gaps)} require watchlist or mitigation attention.")
    if artifact_rows:
        synthesis_lines.append(f"{len(artifact_rows)} open-source impact artifact(s) are published with governed reuse signals.")

    return {
        "location_id": location_id,
        "launch_economics_count": len(economics_rows),
        "network_scaling_target_count": len(target_rows),
        "adoption_barrier_count": len(barrier_rows),
        "active_adoption_barrier_count": len(active_barriers),
        "perpetual_stress_test_count": len(stress_rows),
        "stress_watchlist_count": len(stress_gaps),
        "open_source_artifact_count": len(artifact_rows),
        "planned_farm_count": planned_farms,
        "target_farm_count": target_farms,
        "total_launch_cost_usd": round(total_launch_cost, 2),
        "launch_economics": economics_rows,
        "network_scaling_targets": target_rows,
        "adoption_barriers": barrier_rows,
        "perpetual_value_stress_tests": stress_rows,
        "open_source_artifacts": artifact_rows,
        "synthesis": " ".join(synthesis_lines),
        "safety_note": "Public-safe planning evidence only; planned farm counts are not live-farm claims, ROI is not guaranteed, private capital terms are excluded, and external integrations require governed records before being claimed.",
    }


def store_open_source_capitalist_summary(conn, summary: dict[str, Any], model_version: str = "open-source-capitalist-agent-v1") -> str:
    """Store a draft AI summary for human review."""
    assert_agent_action_allowed("create", "ai_summary", {"status": "draft"})
    summary_id = str(uuid.uuid4())
    subject_id = summary.get("location_id") or "00000000-0000-0000-0000-000000000000"
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ai_summary
            (id, subject_type, subject_id, summary_type, content,
             source_tables, model_version, status)
        VALUES (%s, 'location', %s, 'open_source_capitalist', %s, %s, %s, 'draft')
        RETURNING id
        """,
        (
            summary_id,
            subject_id,
            summary["synthesis"],
            [
                "farm_launch_unit_economics",
                "network_scaling_target",
                "adoption_barrier_assessment",
                "perpetual_value_stress_test",
                "open_source_impact_artifact",
            ],
            model_version,
        ),
    )
    stored_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return stored_id


def run_open_source_capitalist_synthesis(location_id: str | None = None, store: bool = False) -> dict[str, Any]:
    assert_agent_action_allowed("read", "farm_launch_unit_economics", {"location_id": location_id})
    conn = get_connection()
    try:
        summary = synthesize_open_source_capitalist(conn, location_id)
        output: dict[str, Any] = {"summary": summary}
        if store:
            output["ai_summary_id"] = store_open_source_capitalist_summary(conn, summary)
    finally:
        conn.close()

    errors = validate_output("open_source_capitalist_synthesis", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kokonut Open Source Capitalist synthesis agent")
    parser.add_argument("--location-id", help="Optional location UUID")
    parser.add_argument("--store", action="store_true", help="Store draft ai_summary output for human review")
    args = parser.parse_args()

    print(json.dumps(run_open_source_capitalist_synthesis(args.location_id, store=args.store), indent=2, default=str))


if __name__ == "__main__":
    main()
