"""Capital efficiency and utility synthesis agent."""

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


def synthesize_capital_efficiency(conn, location_id: str | None = None) -> dict[str, Any]:
    """Summarize public-safe capital efficiency, regenerative ROI, governance throughput, and utility scenarios."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT scenario_name, location_id, scenario_type, period_start, period_end,
               capital_deployed_usd, gross_output_value_usd, net_output_value_usd,
               public_goods_value_usd, capital_leverage_ratio, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_capital_efficiency_summary
        {where}
        ORDER BY period_start DESC, scenario_name
        """,
        params,
    )
    capital_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT practice_type, location_id, observation_date, baseline_cost_usd,
               observed_cost_usd, cost_savings_pct, incremental_output_value_usd,
               implementation_cost_usd, payback_months, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_regenerative_efficiency_summary
        {where}
        ORDER BY observation_date DESC, practice_type
        """,
        params,
    )
    regenerative_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT proposal_code, location_id, venue, proposal_type, proposal_created_at,
               decision_at, executed_at, decision_latency_days, execution_latency_days,
               decision_result, public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_governance_throughput_summary
        {where}
        ORDER BY proposal_created_at DESC, proposal_code
        """,
        params,
    )
    governance_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT scenario_name, location_id, provider_type, capital_amount_usd,
               expected_financial_return_usd, expected_public_goods_value_usd,
               expected_verification_outputs, expected_payback_months, utility_score,
               public_summary, limitations, evidence_maturity, evidence_maturity_label
        FROM v_public_capital_provider_utility_summary
        {where}
        ORDER BY utility_score DESC NULLS LAST, scenario_name
        """,
        params,
    )
    utility_rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    total_capital_deployed = sum(float(row.get("capital_deployed_usd") or 0) for row in capital_rows)
    average_latency_values = [float(row["decision_latency_days"]) for row in governance_rows if row.get("decision_latency_days") is not None]
    average_decision_latency = round(sum(average_latency_values) / len(average_latency_values), 2) if average_latency_values else None

    synthesis_lines = []
    if capital_rows:
        synthesis_lines.append(f"{len(capital_rows)} public capital efficiency scenario(s) cover ${total_capital_deployed:,.0f} of deployed capital.")
    else:
        synthesis_lines.append("No public capital efficiency scenarios are available.")
    if regenerative_rows:
        synthesis_lines.append(f"{len(regenerative_rows)} regenerative efficiency observation(s) include cost savings or payback signals.")
    if governance_rows:
        synthesis_lines.append(f"{len(governance_rows)} governance throughput observation(s) have average decision latency of {average_decision_latency} days.")
    if utility_rows:
        synthesis_lines.append(f"{len(utility_rows)} capital-provider utility scenario(s) are available with explicit public limitations.")

    return {
        "location_id": location_id,
        "capital_efficiency_count": len(capital_rows),
        "regenerative_efficiency_count": len(regenerative_rows),
        "governance_throughput_count": len(governance_rows),
        "capital_provider_utility_count": len(utility_rows),
        "total_capital_deployed_usd": round(total_capital_deployed, 2),
        "average_decision_latency_days": average_decision_latency,
        "capital_efficiency": capital_rows,
        "regenerative_efficiency": regenerative_rows,
        "governance_throughput": governance_rows,
        "capital_provider_utility": utility_rows,
        "synthesis": " ".join(synthesis_lines),
        "safety_note": "Public-safe scenario evidence only; private capital terms, securities-style return promises, and draft assumptions are excluded.",
    }


def store_capital_efficiency_summary(conn, summary: dict[str, Any], model_version: str = "capital-efficiency-agent-v1") -> str:
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
        VALUES (%s, 'location', %s, 'capital_efficiency', %s, %s, %s, 'draft')
        RETURNING id
        """,
        (
            summary_id,
            subject_id,
            summary["synthesis"],
            [
                "capital_efficiency_scenario",
                "regenerative_efficiency_observation",
                "governance_throughput_observation",
                "capital_provider_utility_scenario",
            ],
            model_version,
        ),
    )
    stored_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return stored_id


def run_capital_efficiency_synthesis(location_id: str | None = None, store: bool = False) -> dict[str, Any]:
    assert_agent_action_allowed("read", "capital_efficiency_scenario", {"location_id": location_id})
    conn = get_connection()
    try:
        summary = synthesize_capital_efficiency(conn, location_id)
        output: dict[str, Any] = {"summary": summary}
        if store:
            output["ai_summary_id"] = store_capital_efficiency_summary(conn, summary)
    finally:
        conn.close()

    errors = validate_output("capital_efficiency_synthesis", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kokonut capital efficiency synthesis agent")
    parser.add_argument("--location-id", help="Optional location UUID")
    parser.add_argument("--store", action="store_true", help="Store draft ai_summary output for human review")
    args = parser.parse_args()

    print(json.dumps(run_capital_efficiency_synthesis(args.location_id, store=args.store), indent=2, default=str))


if __name__ == "__main__":
    main()
