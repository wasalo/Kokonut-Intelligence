"""Gross National Happiness alignment synthesis agent."""

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


def synthesize_gnh(conn, location_id: str | None = None) -> dict[str, Any]:
    """Summarize public-safe GNH, cultural, renewable, access, and foundational well-being evidence."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT gnh_domain, location_id, assessment_date, principle_refs, alignment_score,
               strengths, gaps, safeguards, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_gnh_alignment_summary
        {where}
        ORDER BY assessment_date DESC, gnh_domain
        """,
        params,
    )
    gnh_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT cultural_element, location_id, plan_date, preservation_type,
               local_language, digital_integration_strategy, consent_protocol,
               local_reviewer_role, implementation_status, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_cultural_preservation_summary
        {where}
        ORDER BY plan_date DESC, cultural_element
        """,
        params,
    )
    cultural_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT energy_use_case, location_id, plan_date, renewable_source,
               implementation_status, current_energy_source, planned_capacity_kw,
               estimated_annual_kwh, renewable_share_pct,
               fossil_displacement_estimate_co2e_tonnes, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_renewable_energy_summary
        {where}
        ORDER BY plan_date DESC, energy_use_case
        """,
        params,
    )
    renewable_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT access_scope, location_id, plan_date, vulnerable_groups, access_barriers,
               accommodations, participation_pathways, accountable_role,
               implementation_status, access_coverage_pct, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_vulnerable_access_summary
        {where}
        ORDER BY plan_date DESC, access_scope
        """,
        params,
    )
    access_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT wellbeing_domain, location_id, observation_date, stakeholder_group,
               score_value, count_value, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_foundational_wellbeing_summary
        {where}
        ORDER BY observation_date DESC, wellbeing_domain
        """,
        params,
    )
    wellbeing_rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    scores = [float(row["alignment_score"]) for row in gnh_rows if row.get("alignment_score") is not None]
    implemented_renewables = [row for row in renewable_rows if row.get("implementation_status") == "implemented"]
    planned_renewables = [row for row in renewable_rows if row.get("implementation_status") == "planned"]

    synthesis_lines = []
    if gnh_rows:
        synthesis_lines.append(f"{len(gnh_rows)} public GNH domain assessment(s) are available with average score {round(sum(scores) / len(scores), 2) if scores else 'n/a'}.")
    else:
        synthesis_lines.append("No public GNH alignment assessments are available.")
    if cultural_rows:
        synthesis_lines.append(f"{len(cultural_rows)} cultural preservation plan(s) are available.")
    if renewable_rows:
        synthesis_lines.append(f"{len(renewable_rows)} renewable energy plan(s) are available; {len(implemented_renewables)} implemented and {len(planned_renewables)} planned.")
    if access_rows:
        synthesis_lines.append(f"{len(access_rows)} vulnerable access plan(s) are available with privacy-safe group summaries.")
    if wellbeing_rows:
        synthesis_lines.append(f"{len(wellbeing_rows)} foundational well-being observation(s) are available.")

    return {
        "location_id": location_id,
        "gnh_alignment_count": len(gnh_rows),
        "cultural_preservation_count": len(cultural_rows),
        "renewable_energy_count": len(renewable_rows),
        "vulnerable_access_count": len(access_rows),
        "foundational_wellbeing_count": len(wellbeing_rows),
        "average_alignment_score": round(sum(scores) / len(scores), 2) if scores else None,
        "implemented_renewable_count": len(implemented_renewables),
        "planned_renewable_count": len(planned_renewables),
        "gnh_alignment": gnh_rows,
        "cultural_preservation": cultural_rows,
        "renewable_energy": renewable_rows,
        "vulnerable_access": access_rows,
        "foundational_wellbeing": wellbeing_rows,
        "synthesis": " ".join(synthesis_lines),
        "safety_note": "Public-safe summaries only; private cultural knowledge, raw vulnerable-group identity data, Bhutan-readiness claims, and implemented renewable claims without evidence are excluded.",
    }


def store_gnh_summary(conn, summary: dict[str, Any], model_version: str = "gnh-agent-v1") -> str:
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
        VALUES (%s, 'location', %s, 'gnh_alignment', %s, %s, %s, 'draft')
        RETURNING id
        """,
        (
            summary_id,
            subject_id,
            summary["synthesis"],
            [
                "gnh_alignment_assessment",
                "cultural_preservation_plan",
                "renewable_energy_plan",
                "vulnerable_group_access_plan",
                "foundational_wellbeing_observation",
            ],
            model_version,
        ),
    )
    stored_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return stored_id


def run_gnh_synthesis(location_id: str | None = None, store: bool = False) -> dict[str, Any]:
    assert_agent_action_allowed("read", "gnh_alignment_assessment", {"location_id": location_id})
    conn = get_connection()
    try:
        summary = synthesize_gnh(conn, location_id)
        output: dict[str, Any] = {"summary": summary}
        if store:
            output["ai_summary_id"] = store_gnh_summary(conn, summary)
    finally:
        conn.close()

    errors = validate_output("gnh_alignment_synthesis", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kokonut GNH alignment synthesis agent")
    parser.add_argument("--location-id", help="Optional location UUID")
    parser.add_argument("--store", action="store_true", help="Store draft ai_summary output for human review")
    args = parser.parse_args()

    print(json.dumps(run_gnh_synthesis(args.location_id, store=args.store), indent=2, default=str))


if __name__ == "__main__":
    main()
