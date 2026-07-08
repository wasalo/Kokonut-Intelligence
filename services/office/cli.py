#!/usr/bin/env python3
"""
Impact Office CLI

Usage:
    python3 -m services.office --run full-cycle [--location-id UUID]
    python3 -m services.office --run bounty-cycle [--location-id UUID]
    python3 -m services.office --run funding-cycle [--location-id UUID]
    python3 -m services.office --run landscape-refresh
    python3 -m services.office --status RUN-ID
    python3 -m services.office --alerts [--location-id UUID] [--open-only]
"""

import argparse
import json
import sys

from services.common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER
from services.office import (
    get_alerts,
    get_run_status,
    run_bounty_cycle,
    run_funding_cycle,
    run_full_cycle,
    run_landscape_refresh,
)


def get_pg():
    import psycopg2
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )


def main():
    parser = argparse.ArgumentParser(description="Impact Office CLI")
    parser.add_argument("--run", choices=["full-cycle", "bounty-cycle", "funding-cycle", "landscape-refresh"],
                        help="Run an orchestration cycle")
    parser.add_argument("--location-id", help="Location UUID (optional)")
    parser.add_argument("--status", help="Get status of a run by ID")
    parser.add_argument("--alerts", action="store_true", help="List open alerts")
    parser.add_argument("--open-only", action="store_true", default=True, help="Show only open alerts")
    args = parser.parse_args()

    if not args.run and not args.status and not args.alerts:
        parser.error("Specify --run, --status, or --alerts")

    conn = get_pg()

    if args.status:
        result = get_run_status(conn, args.status)
        print(json.dumps(result, indent=2, default=str))
        conn.close()
        return

    if args.alerts:
        alerts = get_alerts(conn, args.location_id, args.open_only)
        if not alerts:
            print("No open alerts.")
        else:
            for a in alerts:
                print(f"[{a['severity'].upper()}] {a['type']}: {a['message']}")
        conn.close()
        return

    if args.run == "full-cycle":
        result = run_full_cycle(conn, args.location_id)
    elif args.run == "bounty-cycle":
        result = run_bounty_cycle(conn, args.location_id)
    elif args.run == "funding-cycle":
        result = run_funding_cycle(conn, args.location_id)
    elif args.run == "landscape-refresh":
        result = run_landscape_refresh(conn)
    else:
        parser.error(f"Unknown run type: {args.run}")

    conn.close()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
