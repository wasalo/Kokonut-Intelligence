"""EBF calibration memo agent.

Drafts calibration memo structure. Human approval is required for decisions.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from services.agents.safety import assert_agent_action_allowed
from services.agents.tasks import validate_output


def draft_calibration_memo(session_id: str) -> dict[str, Any]:
    assert_agent_action_allowed("create", "ebf_calibration_decision", {"decision_status": "draft"})
    output = {
        "memo": {
            "session_id": session_id,
            "status": "draft",
            "review_note": "Calibration decisions require human approval and evidence references.",
        },
        "proposed_decisions": [],
        "safety_note": "Draft memo only. Agents cannot verify calibration decisions or publish scorecards.",
    }
    errors = validate_output("ebf_calibration_memo", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the EBF calibration memo agent")
    parser.add_argument("--session-id", required=True, help="EBF calibration session UUID")
    args = parser.parse_args()
    print(json.dumps(draft_calibration_memo(args.session_id), indent=2))


if __name__ == "__main__":
    main()
