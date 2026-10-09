"""CLI for human-reviewed canonical stakeholder identity links."""

from __future__ import annotations

import argparse
import sys

from services.analytics import stakeholder_identity_resolution as identity
from services.common.cli import print_json
from services.common.database import get_db


def _out(value):
    print_json(value)


def main():
    parser = argparse.ArgumentParser(description="Canonical stakeholder identity resolution")
    sub = parser.add_subparsers(dest="command")

    propose = sub.add_parser("propose")
    propose.add_argument("source_system")
    propose.add_argument("source_type")
    propose.add_argument("source_id")
    propose.add_argument("party_id")
    propose.add_argument("party_type")
    propose.add_argument("--match-method", default="manual")
    propose.add_argument("--confidence", type=float)
    propose.set_defaults(func=lambda c, a: identity.propose_link(
        c, a.source_system, a.source_type, a.source_id, a.party_id, a.party_type,
        match_method=a.match_method, confidence=a.confidence))

    review = sub.add_parser("review")
    review.add_argument("case_id")
    review.add_argument("reviewer_party_id")
    review.add_argument("notes")
    review.add_argument("--reject", action="store_true")
    review.set_defaults(func=lambda c, a: identity.review_link(
        c, a.case_id, a.reviewer_party_id, approved=not a.reject, notes=a.notes))

    queue = sub.add_parser("queue")
    queue.set_defaults(func=lambda c, a: identity.resolution_queue(c))

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)
    conn = get_db()
    try:
        _out(args.func(conn, args))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
