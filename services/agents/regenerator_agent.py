"""Regenerative outcomes and stewardship synthesis agent."""

from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

from services.agents.base import SynthesisAgent, agent_cli


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


class RegeneratorSynthesisAgent(SynthesisAgent):
    task_key = "regenerator_synthesis"
    summary_type = "regenerative_outcomes"
    read_collection = "regenerative_outcome_summary"
    model_version = "regenerator-agent-v1"
    source_tables = ["regenerative_outcome_summary", "community_governance_mechanism", "replication_readiness_assessment", "adaptive_stewardship_review"]

    def synthesize(self, conn, location_id=None):
        return synthesize_regenerator(conn, location_id)


agent = RegeneratorSynthesisAgent()


def run_regenerator_synthesis(location_id: str | None = None, store: bool = False) -> dict[str, Any]:
    """Run the agent; delegates to the shared :class:`RegeneratorSynthesisAgent` flow."""
    return agent.run(location_id, store=store)


def main() -> None:
    agent_cli(agent, description="Run the Kokonut regenerator synthesis agent", location_required=False)


if __name__ == "__main__":
    main()
