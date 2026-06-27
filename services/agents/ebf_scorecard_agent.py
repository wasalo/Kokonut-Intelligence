"""EBF scorecard draft agent.

Prepares a draft scorecard workspace summary. It does not verify or publish.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from services.agents.safety import assert_agent_action_allowed
from services.agents.tasks import validate_output


def draft_scorecard(location_id: str, period_start: str, period_end: str) -> dict[str, Any]:
    assert_agent_action_allowed("create", "ebf_scorecard", {"status": "draft", "evidence_maturity_level": 1})
    output = {
        "scorecard": {
            "location_id": location_id,
            "period_start": period_start,
            "period_end": period_end,
            "status": "draft",
            "rubric_version": "2026.1",
        },
        "evidence_gaps": [],
        "safety_note": "Draft only. Human review is required before submission, verification, or publication.",
    }
    errors = validate_output("ebf_scorecard_draft", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the EBF scorecard draft agent")
    parser.add_argument("--location-id", required=True, help="Location UUID")
    parser.add_argument("--period-start", required=True, help="Period start YYYY-MM-DD")
    parser.add_argument("--period-end", required=True, help="Period end YYYY-MM-DD")
    args = parser.parse_args()
    print(json.dumps(draft_scorecard(args.location_id, args.period_start, args.period_end), indent=2))


if __name__ == "__main__":
    main()
