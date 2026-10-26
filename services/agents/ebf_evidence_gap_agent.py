"""EBF evidence gap agent.

Read-only helper that summarizes EBF evidence gaps for a scorecard.
"""

from __future__ import annotations

import argparse
from typing import Any

import psycopg2
import psycopg2.extras

from services.common.cli import print_json


def analyze_evidence_gaps(
    conn, scorecard_id: str, location_id: str
) -> dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT pillar_key, pillar_name, normalized_score, confidence_level,
                   evidence_maturity_level, evidence_maturity_label, evidence_count,
                   public_safe_evidence_count, gap_status
            FROM v_ebf_evidence_gap_summary
            WHERE scorecard_id = %s AND location_id = %s
            ORDER BY pillar_key
            """,
            (scorecard_id, location_id),
        )
        gaps = [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
    recommendations = [
        {
            "pillar_key": row.get("pillar_key"),
            "recommendation": "Add public-safe evidence or reviewer notes before publication.",
            "gap_status": row.get("gap_status"),
        }
        for row in gaps
        if row.get("gap_status") != "ready_for_review"
    ]
    return {"evidence_gaps": gaps, "recommendations": recommendations}


def run_ebf_evidence_gap(scorecard_id: str, location_id: str) -> dict[str, Any]:
    """Summarize evidence gaps through the signed EBF source-reader boundary."""
    from services.agents.worker_cli import run_worker_ebf_evidence_gap

    return run_worker_ebf_evidence_gap(scorecard_id, location_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the EBF evidence gap agent")
    parser.add_argument("--scorecard-id", required=True, help="EBF scorecard UUID")
    parser.add_argument("--location-id", required=True, help="Location UUID")
    args = parser.parse_args()
    print_json(run_ebf_evidence_gap(args.scorecard_id, args.location_id))


if __name__ == "__main__":
    main()
