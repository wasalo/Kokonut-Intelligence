"""CLI for the canonical stakeholder registry."""

from __future__ import annotations

import argparse
import sys

from services.analytics.stakeholders import (
    add_identifier,
    add_interest,
    assess_salience,
    create_party,
    get_party,
    link_parties,
    list_landscape,
    list_parties,
)
from services.common.cli import print_json
from services.common.database import get_db


def _out(data):
    print_json(data)


def main():
    parser = argparse.ArgumentParser(description="Canonical stakeholder registry")
    sub = parser.add_subparsers(dest="command")

    create = sub.add_parser("create-party")
    create.add_argument("party_type")
    create.add_argument("display_name")
    create.add_argument("--description", default="")
    create.add_argument("--privacy-level", default="private", choices=["private", "limited", "public"])
    create.set_defaults(func=lambda conn, a: create_party(
        conn, a.party_type, a.display_name, description=a.description, privacy_level=a.privacy_level,
    ))

    listing = sub.add_parser("list")
    listing.add_argument("--party-type")
    listing.add_argument("--status")
    listing.set_defaults(func=lambda conn, a: list_parties(conn, party_type=a.party_type, status=a.status))

    landscape = sub.add_parser("landscape")
    landscape.add_argument("--party-type")
    landscape.set_defaults(func=lambda conn, a: list_landscape(conn, party_type=a.party_type))

    show = sub.add_parser("show")
    show.add_argument("party_id")
    show.set_defaults(func=lambda conn, a: get_party(conn, a.party_id))

    identifier = sub.add_parser("identifier")
    identifier.add_argument("party_id")
    identifier.add_argument("identifier_type")
    identifier.add_argument("identifier_value")
    identifier.add_argument("source_system")
    identifier.add_argument("--source-id")
    identifier.add_argument("--status", default="candidate", choices=["unreviewed", "candidate", "verified", "rejected"])
    identifier.add_argument("--confidence", type=float)
    identifier.set_defaults(func=lambda conn, a: add_identifier(
        conn, a.party_id, a.identifier_type, a.identifier_value, a.source_system,
        source_id=a.source_id, verification_status=a.status, confidence=a.confidence,
    ))

    relationship = sub.add_parser("relationship")
    relationship.add_argument("from_party_id")
    relationship.add_argument("to_party_id")
    relationship.add_argument("relationship_type")
    relationship.add_argument("--scope-type", default="network")
    relationship.add_argument("--scope-id")
    relationship.add_argument("--legitimacy", default="derivative")
    relationship.add_argument("--status", default="proposed")
    relationship.add_argument("--confidence", type=float)
    relationship.add_argument("--notes", default="")
    relationship.add_argument("--accountable-party-id")
    relationship.add_argument("--responsibility-id")
    relationship.set_defaults(func=lambda conn, a: link_parties(
        conn, a.from_party_id, a.to_party_id, a.relationship_type,
        scope_type=a.scope_type, scope_id=a.scope_id, legitimacy=a.legitimacy,
         status=a.status, confidence=a.confidence, notes=a.notes,
         accountable_party_id=a.accountable_party_id, responsibility_id=a.responsibility_id,
    ))

    interest = sub.add_parser("interest")
    interest.add_argument("party_id")
    interest.add_argument("interest_type")
    interest.add_argument("title")
    interest.add_argument("--description", default="")
    interest.add_argument("--legitimacy", default="normative")
    interest.add_argument("--priority", type=int, default=3)
    interest.add_argument("--scope-type", default="network")
    interest.add_argument("--scope-id")
    interest.set_defaults(func=lambda conn, a: add_interest(
        conn, a.party_id, a.interest_type, a.title, description=a.description,
        legitimacy=a.legitimacy, priority=a.priority, scope_type=a.scope_type, scope_id=a.scope_id,
    ))

    salience = sub.add_parser("salience")
    salience.add_argument("party_id")
    salience.add_argument("--interest-id")
    salience.add_argument("--power", type=float, default=0)
    salience.add_argument("--legitimacy-score", type=float, default=0)
    salience.add_argument("--urgency", type=float, default=0)
    salience.add_argument("--vulnerability", type=float, default=0)
    salience.add_argument("--harm-exposure", type=float, default=0)
    salience.add_argument("--representation", type=float, default=0)
    salience.add_argument("--rationale", required=True)
    salience.set_defaults(func=lambda conn, a: assess_salience(
        conn, a.party_id, interest_id=a.interest_id, power=a.power,
        legitimacy=a.legitimacy_score, urgency=a.urgency, vulnerability=a.vulnerability,
        harm_exposure=a.harm_exposure, representation=a.representation, rationale=a.rationale,
    ))

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)
    conn = get_db()
    try:
        result = args.func(conn, args)
        if result is None:
            print("Not found", file=sys.stderr)
            sys.exit(1)
        _out(result)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
