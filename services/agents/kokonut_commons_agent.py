"""Kokonut commons governance synthesis agent."""

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
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)


def _fetch(cur, view: str, location_id: str | None = None) -> list[dict[str, Any]]:
    if location_id:
        cur.execute(f"SELECT * FROM {view} WHERE location_id = %s OR location_id IS NULL", (location_id,))
    else:
        cur.execute(f"SELECT * FROM {view}")
    return [dict(r) for r in cur.fetchall()]


def synthesize_kokonut_commons(conn, location_id: str | None = None) -> dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    anti_capture = _fetch(cur, "v_public_anti_capture_governance_policy", location_id)
    redistribution = _fetch(cur, "v_public_commons_redistribution_policy", location_id)
    federation = _fetch(cur, "v_public_federation_protocol")
    mechanisms = _fetch(cur, "v_public_algorithmic_redistribution_mechanism", location_id)
    signals = _fetch(cur, "v_public_participatory_signal_experiment")
    cur.close()

    active_policies = [row for row in redistribution if row.get("policy_status") == "active"]
    proposed_policies = [row for row in redistribution if row.get("policy_status") == "proposed"]
    synthesis = (
        f"{len(anti_capture)} anti-capture governance policie(s), {len(redistribution)} redistribution policie(s), "
        f"{len(federation)} federation protocol(s), {len(mechanisms)} algorithmic redistribution mechanism(s), "
        f"and {len(signals)} participatory signal experiment(s) are publicly available. "
        f"{len(active_policies)} redistribution policie(s) are active and {len(proposed_policies)} are proposed scenarios."
    )
    return {
        "location_id": location_id,
        "anti_capture_policy_count": len(anti_capture),
        "redistribution_policy_count": len(redistribution),
        "active_redistribution_policy_count": len(active_policies),
        "proposed_redistribution_policy_count": len(proposed_policies),
        "federation_protocol_count": len(federation),
        "algorithmic_redistribution_count": len(mechanisms),
        "participatory_signal_count": len(signals),
        "anti_capture_governance": anti_capture,
        "redistribution_policies": redistribution,
        "federation_protocols": federation,
        "algorithmic_redistribution": mechanisms,
        "participatory_signals": signals,
        "synthesis": synthesis,
        "safety_note": "Public-safe governance evidence only; proposed redistribution scenarios are not commitments, meme/vibes signals are advisory unless reviewed, and unsupported Hypercert/Ecocertain/Venus/AMUSA claims are excluded.",
    }


def store_kokonut_commons_summary(conn, summary: dict[str, Any], model_version: str = "kokonut-commons-agent-v1") -> str:
    assert_agent_action_allowed("create", "ai_summary", {"status": "draft"})
    summary_id = str(uuid.uuid4())
    subject_id = summary.get("location_id") or "00000000-0000-0000-0000-000000000000"
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ai_summary (id, subject_type, subject_id, summary_type, content, source_tables, model_version, status)
        VALUES (%s, 'location', %s, 'kokonut_commons', %s, %s, %s, 'draft')
        RETURNING id
        """,
        (
            summary_id,
            subject_id,
            summary["synthesis"],
            ["anti_capture_governance_policy", "commons_redistribution_policy", "federation_protocol", "algorithmic_redistribution_mechanism", "participatory_signal_experiment"],
            model_version,
        ),
    )
    stored_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return stored_id


def run_kokonut_commons_synthesis(location_id: str | None = None, store: bool = False) -> dict[str, Any]:
    assert_agent_action_allowed("read", "anti_capture_governance_policy", {"location_id": location_id})
    conn = get_connection()
    try:
        summary = synthesize_kokonut_commons(conn, location_id)
        output: dict[str, Any] = {"summary": summary}
        if store:
            output["ai_summary_id"] = store_kokonut_commons_summary(conn, summary)
    finally:
        conn.close()
    errors = validate_output("kokonut_commons_synthesis", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kokonut commons governance synthesis agent")
    parser.add_argument("--location-id", help="Optional location UUID")
    parser.add_argument("--store", action="store_true", help="Store draft ai_summary output for human review")
    args = parser.parse_args()
    print(json.dumps(run_kokonut_commons_synthesis(args.location_id, store=args.store), indent=2, default=str))


if __name__ == "__main__":
    main()
