"""Financial resilience and scaling synthesis agent."""

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


def store_resilience_summary(conn, summary: dict[str, Any], model_version: str = "resilience-agent-v1") -> str:
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
        VALUES (%s, 'location', %s, 'financial_resilience', %s, %s, %s, 'draft')
        RETURNING id
        """,
        (
            summary_id,
            subject_id,
            summary["synthesis"],
            ["financial_sustainability_plan", "risk_mitigation_register", "scaling_roadmap_milestone", "green_paper_publication_review"],
            model_version,
        ),
    )
    stored_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return stored_id


def run_resilience_synthesis(location_id: str | None = None, store: bool = False) -> dict[str, Any]:
    assert_agent_action_allowed("read", "financial_sustainability_plan", {"location_id": location_id})
    conn = get_connection()
    try:
        summary = synthesize_resilience(conn, location_id)
        output: dict[str, Any] = {"summary": summary}
        if store:
            output["ai_summary_id"] = store_resilience_summary(conn, summary)
    finally:
        conn.close()

    errors = validate_output("financial_resilience_synthesis", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kokonut financial resilience synthesis agent")
    parser.add_argument("--location-id", help="Optional location UUID")
    parser.add_argument("--store", action="store_true", help="Store draft ai_summary output for human review")
    args = parser.parse_args()

    print(json.dumps(run_resilience_synthesis(args.location_id, store=args.store), indent=2, default=str))


if __name__ == "__main__":
    main()
