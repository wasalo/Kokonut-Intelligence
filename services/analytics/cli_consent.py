"""CLI for canonical stakeholder consent."""

from __future__ import annotations

import argparse
import sys

from services.analytics.consent_resolver import (
    check_consent,
    list_effective_consent,
    record_consent,
    withdraw_consent,
)
from services.common.cli import print_json
from services.common.database import get_db


def _out(data):
    print_json(data)


def main():
    parser = argparse.ArgumentParser(description="Canonical stakeholder consent resolver")
    sub = parser.add_subparsers(dest="command")

    record = sub.add_parser("record")
    record.add_argument("party_id")
    record.add_argument("data_category")
    record.add_argument("purpose")
    record.add_argument("--event-type", default="grant", choices=["grant", "withdraw", "deny", "expire"])
    record.add_argument("--scope-type", default="network")
    record.add_argument("--scope-id")
    record.add_argument("--recipient-party-id")
    record.add_argument("--recipient-type", default="system")
    record.add_argument("--recipient-name")
    record.add_argument("--reason")
    record.add_argument("--source-system", default="stakeholder_registry")
    record.set_defaults(func=lambda conn, a: record_consent(
        conn, a.party_id, a.data_category, a.purpose, event_type=a.event_type,
        scope_type=a.scope_type, scope_id=a.scope_id, recipient_party_id=a.recipient_party_id,
        recipient_type=a.recipient_type, recipient_name=a.recipient_name,
        reason=a.reason, source_system=a.source_system,
    ))

    check = sub.add_parser("check")
    check.add_argument("party_id")
    check.add_argument("data_category")
    check.add_argument("purpose")
    check.add_argument("--scope-type", default="network")
    check.add_argument("--scope-id")
    check.add_argument("--recipient-party-id")
    check.add_argument("--recipient-type", default="system")
    check.set_defaults(func=lambda conn, a: check_consent(
        conn, a.party_id, a.data_category, a.purpose, scope_type=a.scope_type,
        scope_id=a.scope_id, recipient_party_id=a.recipient_party_id,
        recipient_type=a.recipient_type,
    ))

    listing = sub.add_parser("list")
    listing.add_argument("--party-id")
    listing.add_argument("--status")
    listing.set_defaults(func=lambda conn, a: list_effective_consent(
        conn, a.party_id, effective_status=a.status,
    ))

    withdraw = sub.add_parser("withdraw")
    withdraw.add_argument("consent_event_id")
    withdraw.add_argument("--reason", required=True)
    withdraw.set_defaults(func=lambda conn, a: withdraw_consent(conn, a.consent_event_id, a.reason))

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)
    conn = get_db()
    try:
        result = args.func(conn, args)
        _out(result)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
