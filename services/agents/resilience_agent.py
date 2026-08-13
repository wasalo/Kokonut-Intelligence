"""Financial resilience and scaling synthesis agent."""

from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

from services.agents.base import SynthesisAgent, agent_cli


def _location_filter(column: str, location_id: str | None) -> tuple[str, tuple[Any, ...]]:
    if location_id:
        return f"WHERE {column} = %s", (location_id,)
    return "", ()


def synthesize_resilience(conn, location_id: str | None = None) -> dict[str, Any]:
    """Summarize public-safe financial resilience, risks, scaling, and publication status."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT plan_name, location_id, farm_model, sustainability_status,
               grant_dependency_pct, reinvestment_pct, public_goods_allocation_pct,
               runway_months, projected_annual_revenue_usd, projected_annual_noi_usd,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_financial_sustainability_summary
        {where}
        ORDER BY plan_period_start DESC, plan_name
        """,
        params,
    )
    financial_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT risk_category, location_id, likelihood, impact_level, residual_risk_level,
               owner_role, review_cadence, next_review_date, insurance_scope,
               oversight_mechanism, technical_support_provider, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_risk_mitigation_summary
        {where}
        ORDER BY next_review_date NULLS LAST, risk_category
        """,
        params,
    )
    risk_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT roadmap_name, location_id, target_region, farm_model, planned_farm_count,
               capital_required_usd, partner_requirements, operational_dependencies,
               risk_gates, target_date, milestone_status, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_scaling_roadmap_summary
        {where}
        ORDER BY target_date, roadmap_name
        """,
        params,
    )
    scaling_rows = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT version, document_path, review_status, review_owner,
               target_publication_date, open_question_count, approval_record_count,
               publication_cid, publication_hash, published_at, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_green_paper_publication_status
        ORDER BY target_publication_date DESC, version DESC
        """
    )
    publication_rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    total_capital_required = sum(float(row.get("capital_required_usd") or 0) for row in scaling_rows)
    high_or_critical_risks = [
        row for row in risk_rows
        if row.get("impact_level") in {"high", "critical"} or row.get("residual_risk_level") in {"high", "critical"}
    ]

    synthesis_lines = []
    if financial_rows:
        synthesis_lines.append(f"{len(financial_rows)} public financial sustainability plan(s) are available.")
    else:
        synthesis_lines.append("No public financial sustainability plans are available.")
    if risk_rows:
        synthesis_lines.append(f"{len(risk_rows)} public risk mitigation register entrie(s) are available; {len(high_or_critical_risks)} remain high or critical.")
    if scaling_rows:
        synthesis_lines.append(f"{len(scaling_rows)} public scaling roadmap milestone(s) require approximately ${total_capital_required:,.0f} in capital.")
    if publication_rows:
        latest = publication_rows[0]
        synthesis_lines.append(f"Green Paper {latest.get('version')} publication status is {latest.get('review_status')}.")

    return {
        "location_id": location_id,
        "financial_plan_count": len(financial_rows),
        "risk_register_count": len(risk_rows),
        "high_or_critical_risk_count": len(high_or_critical_risks),
        "scaling_milestone_count": len(scaling_rows),
        "total_scaling_capital_required_usd": round(total_capital_required, 2),
        "publication_review_count": len(publication_rows),
        "financial_sustainability": financial_rows,
        "risk_mitigation": risk_rows,
        "scaling_roadmap": scaling_rows,
        "green_paper_publication": publication_rows,
        "synthesis": " ".join(synthesis_lines),
        "safety_note": "Public-safe summaries only; private financial terms, unpublished insurance policies, and draft roadmap assumptions are not included.",
    }


class ResilienceSynthesisAgent(SynthesisAgent):
    task_key = "financial_resilience_synthesis"
    summary_type = "financial_resilience"
    read_collection = "financial_sustainability_plan"
    model_version = "resilience-agent-v1"
    source_tables = ["financial_sustainability_plan", "risk_mitigation_register", "scaling_roadmap_milestone", "green_paper_publication_review"]

    def synthesize(self, conn, location_id=None):
        return synthesize_resilience(conn, location_id)


agent = ResilienceSynthesisAgent()


def run_resilience_synthesis(location_id: str | None = None, store: bool = False) -> dict[str, Any]:
    """Run the agent; delegates to the shared :class:`ResilienceSynthesisAgent` flow."""
    return agent.run(location_id, store=store)


def main() -> None:
    agent_cli(agent, description="Run the Kokonut financial resilience synthesis agent", location_required=False)


if __name__ == "__main__":
    main()
