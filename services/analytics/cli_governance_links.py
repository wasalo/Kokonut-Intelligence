"""CLI for cross-circle representative links."""

from __future__ import annotations

import argparse
import json

from services.analytics.governance_links import approve_link, create_link, end_link, list_links


def _connection():
    from services.common.database import get_db
    return get_db()


def _out(value):
    print(json.dumps(value, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokonut cross-circle links CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("source_circle_id")
    create.add_argument("target_circle_id")
    create.add_argument("link_type")
    create.add_argument("role_id")
    create.add_argument("party_id")
    create.add_argument("mandate")
    create.add_argument("--scope-type", default="network")
    create.add_argument("--scope-id")
    create.add_argument("--term-end")
    create.set_defaults(func=lambda a: _out(create_link(
        _connection(), a.source_circle_id, a.target_circle_id, a.link_type,
        a.role_id, a.party_id, a.mandate, scope_type=a.scope_type,
        scope_id=a.scope_id, term_end=a.term_end,
    )))

    listing = sub.add_parser("list")
    listing.add_argument("--source-circle-id")
    listing.add_argument("--target-circle-id")
    listing.add_argument("--party-id")
    listing.add_argument("--status")
    listing.set_defaults(func=lambda a: _out(list_links(
        _connection(), source_circle_id=a.source_circle_id,
        target_circle_id=a.target_circle_id, party_id=a.party_id, status=a.status,
    )))

    approve = sub.add_parser("approve")
    approve.add_argument("link_id")
    approve.add_argument("approved_by_party_id")
    approve.set_defaults(func=lambda a: _out(approve_link(_connection(), a.link_id, a.approved_by_party_id)))

    end = sub.add_parser("end")
    end.add_argument("link_id")
    end.add_argument("--recuse", action="store_true")
    end.set_defaults(func=lambda a: _out(end_link(_connection(), a.link_id, recused=a.recuse)))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
