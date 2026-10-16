"""Read-only scheduler entrypoint for carbon-credit adjustment checks.

The interactive ``carbon_credits`` CLI also supports issuance, adjustment,
retirement, and human review. Scheduler dispatch must use this narrow entrypoint
so its reachable code contains only the recompute-and-report operation.
"""

from __future__ import annotations

import argparse
from uuid import UUID

from services.analytics.carbon_credits import check_adjustments
from services.common.cli import get_connection, print_json, run


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Read-only carbon-credit adjustment check")
    parser.add_argument("--location-id", type=UUID, help="Optionally limit the check to one location")
    args = parser.parse_args(argv)

    with get_connection(readonly=True) as connection:
        results = check_adjustments(
            connection,
            location_id=str(args.location_id) if args.location_id is not None else None,
        )
    print_json(results)


if __name__ == "__main__":
    run(main)
