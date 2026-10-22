"""CIDS export agent.

This agent prepares CIDS JSON-LD as a read-only task output. It does not publish
or attest records; downstream publication remains a human-reviewed action.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from services.common.cli import print_json
from services.registry.cids_export import _json_default


def run_cids_export(location_id: str) -> dict[str, Any]:
    """Return a validated CIDS export through the signed worker boundary."""
    from services.agents.worker_cli import run_worker_cids_export

    return run_worker_cids_export(location_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kokonut CIDS export agent")
    parser.add_argument("--location-id", required=True, help="Location UUID")
    parser.add_argument("--summary", action="store_true", help="Print compact summary instead of full JSON-LD")
    args = parser.parse_args()

    output = run_cids_export(args.location_id)
    if args.summary:
        print_json({k: output[k] for k in ("graph_count", "alignment_tier", "cids_version")})
    else:
        print(json.dumps(output, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
