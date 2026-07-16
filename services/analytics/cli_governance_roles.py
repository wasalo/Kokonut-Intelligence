"""CLI for the Kokonut circle and role registry."""

from __future__ import annotations

import argparse
import json

from services.analytics.governance_roles import (
    add_accountability,
    create_circle,
    create_role,
    list_accountabilities,
    list_circles,
    list_roles,
)


def _out(value):
    print(json.dumps(value, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokonut governance circles and roles")
    sub = parser.add_subparsers(dest="command", required=True)

    circle = sub.add_parser("circle-create")
    circle.add_argument("circle_key")
    circle.add_argument("name")
    circle.add_argument("purpose")
    circle.add_argument("--scope-type", default="network")
    circle.add_argument("--scope-id")
    circle.add_argument("--parent-circle-id")
    circle.add_argument("--status", default="draft")
    circle.set_defaults(func=lambda a: _out(create_circle(
        _connection(), a.circle_key, a.name, a.purpose,
        scope_type=a.scope_type, scope_id=a.scope_id,
        parent_circle_id=a.parent_circle_id, status=a.status,
    )))

    listing = sub.add_parser("circle-list")
    listing.add_argument("--status")
    listing.add_argument("--scope-type")
    listing.set_defaults(func=lambda a: _out(list_circles(_connection(), status=a.status, scope_type=a.scope_type)))

    role = sub.add_parser("role-create")
    role.add_argument("circle_id")
    role.add_argument("role_key")
    role.add_argument("name")
    role.add_argument("purpose")
    role.add_argument("--status", default="draft")
    role.set_defaults(func=lambda a: _out(create_role(
        _connection(), a.circle_id, a.role_key, a.name, a.purpose, status=a.status,
    )))

    roles = sub.add_parser("role-list")
    roles.add_argument("--circle-id")
    roles.add_argument("--status")
    roles.set_defaults(func=lambda a: _out(list_roles(_connection(), circle_id=a.circle_id, status=a.status)))

    accountability = sub.add_parser("accountability-add")
    accountability.add_argument("role_id")
    accountability.add_argument("accountability")
    accountability.add_argument("--priority", type=int, default=3)
    accountability.add_argument("--optional", action="store_true")
    accountability.add_argument("--evidence-expectation")
    accountability.set_defaults(func=lambda a: _out(add_accountability(
        _connection(), a.role_id, a.accountability, priority=a.priority,
        required=not a.optional, evidence_expectation=a.evidence_expectation,
    )))

    accountabilities = sub.add_parser("accountability-list")
    accountabilities.add_argument("role_id")
    accountabilities.set_defaults(func=lambda a: _out(list_accountabilities(_connection(), a.role_id)))

    args = parser.parse_args()
    args.func(args)


def _connection():
    from services.ingestion.base import get_db
    return get_db()


if __name__ == "__main__":
    main()
