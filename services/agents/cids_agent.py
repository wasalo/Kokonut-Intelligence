"""CIDS export agent.

This agent prepares CIDS JSON-LD as a read-only task output. It does not publish
or attest records; downstream publication remains a human-reviewed action.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from services.agents.safety import assert_agent_action_allowed
from services.agents.tasks import validate_output
from services.registry.cids_export import export_location, get_connection, _json_default


def run_cids_export(location_id: str) -> dict[str, Any]:
    """Return a validated CIDS export task output."""
    assert_agent_action_allowed("read", "cids_export", {"location_id": location_id})
    conn = get_connection()
    try:
        document = export_location(conn, location_id)
    finally:
        conn.close()

    output = {
        "document": document,
        "graph_count": len(document.get("@graph", [])),
        "alignment_tier": document.get("kokonut:alignmentTier"),
        "cids_version": document.get("kokonut:cidsVersion"),
    }
    errors = validate_output("cids_export", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kokonut CIDS export agent")
    parser.add_argument("--location-id", required=True, help="Location UUID")
    parser.add_argument("--summary", action="store_true", help="Print compact summary instead of full JSON-LD")
    args = parser.parse_args()

    output = run_cids_export(args.location_id)
    if args.summary:
        print(json.dumps({k: output[k] for k in ("graph_count", "alignment_tier", "cids_version")}, indent=2))
    else:
        print(json.dumps(output, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
