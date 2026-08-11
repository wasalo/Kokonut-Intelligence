"""CLI for canonical Guild reputation and Moloch observation helpers."""

from __future__ import annotations

import argparse
import json

from ..ingestion.base import get_db
from .kgp import build_claim_voucher, compute_award_id
from .moloch import MolochReadClient, link_guild_motion_to_moloch
from .reputation import canonical_balance
from services.common.cli import print_json

def main() -> None:
    parser = argparse.ArgumentParser(description="Kokonut Guild protocol tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    balance = subparsers.add_parser("balance")
    balance.add_argument("--guild-id", required=True)
    balance.add_argument("--domain-id", type=int, required=True)
    balance.add_argument("--wallet", required=True)

    link = subparsers.add_parser("link-moloch")
    link.add_argument("--guild-motion-id", required=True)
    link.add_argument("--proposal-code", required=True)

    token = subparsers.add_parser("moloch-balance")
    token.add_argument("--wallet", required=True)
    token.add_argument("--token", choices=["vkkn_token", "loot_token"], required=True)

    args = parser.parse_args()
    if args.command == "moloch-balance":
        print_json(MolochReadClient().token_balance(args.wallet, args.token))
        return

    db = get_db()
    try:
        with db.cursor() as cursor:
            if args.command == "balance":
                value = canonical_balance(cursor, args.guild_id, args.domain_id, args.wallet)
                print(json.dumps({"guild_id": args.guild_id, "domain_id": args.domain_id, "wallet": args.wallet, "kgp": value}))
            else:
                link_guild_motion_to_moloch(cursor, args.guild_motion_id, args.proposal_code)
                db.commit()
                print(json.dumps({"linked": True, "guild_motion_id": args.guild_motion_id, "proposal_code": args.proposal_code}))
    finally:
        db.close()


if __name__ == "__main__":
    main()
