"""Strategic Reserve CLI.

Read-only health + biodiversity views, plus a release-proposal command
that creates a DRAFT ``strategic_reserve_release`` row for human approval
(never auto-executes a drawdown).
"""

from __future__ import annotations

import argparse

from services.common.cli import print_json, run
from services.common.database import get_db
from services.strategic_reserve import health


def cmd_list() -> None:
    conn = get_db()
    try:
        rows = health.reserve_health(conn)["reserves"]
    finally:
        conn.close()
    print_json(rows)


def cmd_health() -> None:
    conn = get_db()
    try:
        out = health.reserve_health(conn)
    finally:
        conn.close()
    print_json(out)


def cmd_seed_vault(location_id: str) -> None:
    conn = get_db()
    try:
        out = health.seed_vault_health(conn, location_id)
    finally:
        conn.close()
    print_json(out)


def cmd_propose_release(reserve_code: str, quantity: float, reason: str) -> None:
    """Propose a reserve drawdown (DRAFT; requires human approval)."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM strategic_reserve WHERE reserve_code = %s",
            (reserve_code,),
        )
        row = cur.fetchone()
        if not row:
            raise SystemExit(f"reserve not found: {reserve_code}")
        reserve_id = row[0]
        cur.execute(
            """INSERT INTO strategic_reserve_release
               (reserve_id, proposed_quantity, reason, status)
               VALUES (%s, %s, %s, 'draft') RETURNING id""",
            (reserve_id, quantity, reason),
        )
        release_id = cur.fetchone()[0]
        conn.commit()
        out = {"id": str(release_id), "status": "draft", "reserve_code": reserve_code}
    finally:
        conn.close()
    print_json(out)


def _cmd(args) -> None:
    if args.command == "list":
        cmd_list()
    elif args.command == "health":
        cmd_health()
    elif args.command == "seed-vault":
        cmd_seed_vault(args.location_id)
    elif args.command == "propose-release":
        cmd_propose_release(args.reserve_code, args.quantity, args.reason)


def main() -> None:
    p = argparse.ArgumentParser(description="Strategic Reserve (resilience layer)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("list")
    sub.add_parser("health")

    sv = sub.add_parser("seed-vault", help="Biodiversity/seed-vault proxy for a location")
    sv.add_argument("--location-id", required=True)

    pr = sub.add_parser("propose-release", help="Propose a drawdown (DRAFT, human-approved)")
    pr.add_argument("--reserve-code", required=True)
    pr.add_argument("--quantity", type=float, required=True)
    pr.add_argument("--reason", default=None)

    args = p.parse_args()
    _cmd(args)


if __name__ == "__main__":
    run(main)
