"""Capital efficiency and utility synthesis agent."""

from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

from services.agents.base import SynthesisAgent, agent_cli


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


class CapitalEfficiencySynthesisAgent(SynthesisAgent):
    task_key = "capital_efficiency_synthesis"
    summary_type = "capital_efficiency"
    read_collection = "capital_efficiency_scenario"
    model_version = "capital-efficiency-agent-v1"
    source_tables = ["capital_efficiency_scenario", "regenerative_efficiency_observation", "governance_throughput_observation", "capital_provider_utility_scenario"]

    _source_reference_views = {
        "capital_efficiency_scenario": "v_public_capital_efficiency_summary",
        "regenerative_efficiency_observation": "v_public_regenerative_efficiency_summary",
        "governance_throughput_observation": "v_public_governance_throughput_summary",
        "capital_provider_utility_scenario": "v_public_capital_provider_utility_summary",
    }

    def synthesize(self, conn, location_id=None):
        return synthesize_capital_efficiency(conn, location_id)

    def collect_source_references(self, conn, location_id):
        """Capture only published rows visible through the public summary views."""
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                """
                WITH sources AS MATERIALIZED (
                    SELECT 'capital_efficiency_scenario'::text AS source_table, id
                    FROM v_public_capital_efficiency_summary WHERE location_id = %s
                    UNION ALL
                    SELECT 'regenerative_efficiency_observation'::text, id
                    FROM v_public_regenerative_efficiency_summary WHERE location_id = %s
                    UNION ALL
                    SELECT 'governance_throughput_observation'::text, id
                    FROM v_public_governance_throughput_summary WHERE location_id = %s
                    UNION ALL
                    SELECT 'capital_provider_utility_scenario'::text, id
                    FROM v_public_capital_provider_utility_summary WHERE location_id = %s
                ), counts AS (
                    SELECT source_table, count(*) AS row_count
                    FROM sources
                    GROUP BY source_table
                ), numbered AS (
                    SELECT source_table, id,
                           row_number() OVER (PARTITION BY source_table ORDER BY id) AS ordinal
                    FROM sources
                )
                SELECT counts.source_table, counts.row_count,
                       array_agg(numbered.id ORDER BY numbered.ordinal)
                           FILTER (WHERE numbered.ordinal <= 50) AS record_ids
                FROM counts
                JOIN numbered USING (source_table)
                GROUP BY counts.source_table, counts.row_count
                ORDER BY counts.source_table
                """,
                (location_id, location_id, location_id, location_id),
            )
            rows = cur.fetchall()
        finally:
            cur.close()
        references: dict[str, dict[str, Any]] = {}
        for row in rows:
            source_table = row["source_table"]
            row_count = int(row["row_count"])
            record_ids = [str(record_id) for record_id in row["record_ids"]]
            references[source_table] = {
                "record_ids": record_ids,
                "row_count": row_count,
                "truncated": row_count > len(record_ids),
            }
        return references


agent = CapitalEfficiencySynthesisAgent()


def run_capital_efficiency_synthesis(location_id: str | None = None, store: bool = False) -> dict[str, Any]:
    """Run the agent; delegates to the shared :class:`CapitalEfficiencySynthesisAgent` flow."""
    return agent.run(location_id, store=store)


def main() -> None:
    agent_cli(agent, description="Run the Kokonut capital efficiency synthesis agent", location_required=False)


if __name__ == "__main__":
    main()
