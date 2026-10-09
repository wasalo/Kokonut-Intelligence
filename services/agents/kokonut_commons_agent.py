"""Kokonut commons governance synthesis agent."""

from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

from services.agents.base import SynthesisAgent, agent_cli


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


class KokonutCommonsSynthesisAgent(SynthesisAgent):
    task_key = "kokonut_commons_synthesis"
    summary_type = "kokonut_commons"
    read_collection = "anti_capture_governance_policy"
    model_version = "kokonut-commons-agent-v1"
    source_tables = ["anti_capture_governance_policy", "commons_redistribution_policy", "federation_protocol", "algorithmic_redistribution_mechanism", "participatory_signal_experiment"]

    def synthesize(self, conn, location_id=None):
        return synthesize_kokonut_commons(conn, location_id)


agent = KokonutCommonsSynthesisAgent()


def run_kokonut_commons_synthesis(location_id: str | None = None, store: bool = False) -> dict[str, Any]:
    """Run the agent; delegates to the shared :class:`KokonutCommonsSynthesisAgent` flow."""
    return agent.run(location_id, store=store)


def main() -> None:
    agent_cli(agent, description="Run the Kokonut commons governance synthesis agent", location_required=False)


if __name__ == "__main__":
    main()
