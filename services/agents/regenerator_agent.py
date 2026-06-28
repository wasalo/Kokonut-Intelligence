"""Regenerative outcomes and stewardship synthesis agent."""

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
        return f"WHERE {column} = %s", (location_id,)
    return "", ()


def synthesize_regenerator(conn, location_id: str | None = None) -> dict[str, Any]:
    """Summarize public-safe regenerative outcomes, governance, replication, and stewardship evidence."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT summary_name, location_id, period_start, period_end, hectares_restored,
               latest_species_count, species_diversity_delta, soil_carbon_delta_t_ha,
               trees_planted_count, tree_survival_rate_pct, regenerative_score,
               jobs_or_roles_supported_count, training_hours, beneficiary_count,
               evidence_confidence, public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_regenerative_outcome_summary
        {where}
        ORDER BY period_end DESC, summary_name
        """,
        params,
    )
    outcome_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT mechanism_name, location_id, governance_level, decision_body,
               decision_method, quorum_rule, voting_or_consensus_rights,
               community_veto_rights, escalation_path, power_distribution_summary,
               participation_cadence, public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_community_governance_mechanism
        {where}
        ORDER BY governance_level, mechanism_name
        """,
        params,
    )
    governance_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT target_region, location_id, assessment_date, farm_model, readiness_score,
               ecological_prerequisites, cultural_governance_prerequisites,
               infrastructure_prerequisites, barriers, enablers, support_structures,
               minimum_evidence_maturity, replication_status, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_replication_readiness_summary
        {where}
        ORDER BY assessment_date DESC, target_region
        """,
        params,
    )
    replication_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT stewardship_scope, location_id, review_date, review_period_start,
               review_period_end, review_cadence, trigger_thresholds, observed_triggers,
               corrective_actions, action_completion_pct, responsible_role,
               funding_continuity_plan, next_review_date, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_adaptive_stewardship_summary
        {where}
        ORDER BY review_date DESC, stewardship_scope
        """,
        params,
    )
    stewardship_rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    hectares = sum(float(row.get("hectares_restored") or 0) for row in outcome_rows)
    conditional_replications = [row for row in replication_rows if row.get("replication_status") in {"conditional", "ready_for_pilot"}]
    synthesis_lines = []
    if outcome_rows:
        synthesis_lines.append(f"{len(outcome_rows)} regenerative outcome summary record(s) cover {hectares:.4f} hectares.")
    else:
        synthesis_lines.append("No public regenerative outcome summaries are available.")
    if governance_rows:
        synthesis_lines.append(f"{len(governance_rows)} community governance mechanism(s) document decision method and power distribution.")
    if replication_rows:
        synthesis_lines.append(f"{len(replication_rows)} replication readiness assessment(s) are available; {len(conditional_replications)} are conditional or pilot-ready.")
    if stewardship_rows:
        synthesis_lines.append(f"{len(stewardship_rows)} adaptive stewardship review(s) document triggers and corrective actions.")

    return {
        "location_id": location_id,
        "regenerative_outcome_count": len(outcome_rows),
        "community_governance_count": len(governance_rows),
        "replication_readiness_count": len(replication_rows),
        "adaptive_stewardship_count": len(stewardship_rows),
        "total_hectares_restored": round(hectares, 4),
        "regenerative_outcomes": outcome_rows,
        "community_governance": governance_rows,
        "replication_readiness": replication_rows,
        "adaptive_stewardship": stewardship_rows,
        "synthesis": " ".join(synthesis_lines),
        "safety_note": "Public-safe summaries only; source tables remain canonical, private identities and terms are excluded, and replication readiness is not an unlimited-scaling claim.",
    }


def store_regenerator_summary(conn, summary: dict[str, Any], model_version: str = "regenerator-agent-v1") -> str:
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
        VALUES (%s, 'location', %s, 'regenerative_outcomes', %s, %s, %s, 'draft')
        RETURNING id
        """,
        (
            summary_id,
            subject_id,
            summary["synthesis"],
            [
                "regenerative_outcome_summary",
                "community_governance_mechanism",
                "replication_readiness_assessment",
                "adaptive_stewardship_review",
            ],
            model_version,
        ),
    )
    stored_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return stored_id


def run_regenerator_synthesis(location_id: str | None = None, store: bool = False) -> dict[str, Any]:
    assert_agent_action_allowed("read", "regenerative_outcome_summary", {"location_id": location_id})
    conn = get_connection()
    try:
        summary = synthesize_regenerator(conn, location_id)
        output: dict[str, Any] = {"summary": summary}
        if store:
            output["ai_summary_id"] = store_regenerator_summary(conn, summary)
    finally:
        conn.close()

    errors = validate_output("regenerator_synthesis", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kokonut regenerator synthesis agent")
    parser.add_argument("--location-id", help="Optional location UUID")
    parser.add_argument("--store", action="store_true", help="Store draft ai_summary output for human review")
    args = parser.parse_args()

    print(json.dumps(run_regenerator_synthesis(args.location_id, store=args.store), indent=2, default=str))


if __name__ == "__main__":
    main()
