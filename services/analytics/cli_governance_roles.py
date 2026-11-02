"""CLI for the Kokonut circle and role registry."""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from services.analytics.governance_roles import (
    add_accountability,
    add_domain,
    add_policy,
    approve_assignment,
    assign_role,
    create_circle,
    create_role,
    end_assignment,
    list_accountabilities,
    list_assignments,
    list_circles,
    list_domains,
    list_roles,
)
from services.common.cli import print_json


def _out(value):
    print_json(value)


def _parse_json_object(value: str) -> dict:
    """Parse a JSON object before the command opens PostgreSQL."""
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("--constraints must be a valid JSON object") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("--constraints must be a valid JSON object")
    return parsed


def _parse_review_due_at(value: str) -> datetime:
    """Parse TIMESTAMPTZ input before assignment-add opens PostgreSQL."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(
            "--review-due-at must be an ISO timestamp with an explicit timezone"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError(
            "--review-due-at must include an explicit timezone"
        )
    return parsed


def _run_with_connection(operation) -> None:
    """Own and close the database connection for one CLI read command."""
    conn = _connection()
    try:
        result = operation(conn)
    finally:
        conn.close()
    _out(result)


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
    listing.set_defaults(func=lambda a: _run_with_connection(
        lambda conn: list_circles(conn, status=a.status, scope_type=a.scope_type)
    ))

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
    roles.set_defaults(func=lambda a: _run_with_connection(
        lambda conn: list_roles(conn, circle_id=a.circle_id, status=a.status)
    ))

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
    accountabilities.set_defaults(func=lambda a: _run_with_connection(
        lambda conn: list_accountabilities(conn, a.role_id)
    ))

    domain = sub.add_parser("domain-add")
    domain.add_argument("role_id")
    domain.add_argument("domain_type")
    domain.add_argument("domain_key")
    domain.add_argument("--scope-type", default="network")
    domain.add_argument("--scope-id")
    domain.add_argument("--authority-level", default="recommend", choices=["observe", "recommend", "decide", "execute"])
    domain.add_argument(
        "--constraints", type=_parse_json_object, default=_parse_json_object("{}")
    )
    domain.add_argument("--no-human-approval", action="store_true")
    domain.set_defaults(func=lambda a: _out(add_domain(
        _connection(), a.role_id, a.domain_type, a.domain_key,
        scope_type=a.scope_type, scope_id=a.scope_id,
        authority_level=a.authority_level, constraints=a.constraints,
        requires_human_approval=not a.no_human_approval,
    )))

    domains = sub.add_parser("domain-list")
    domains.add_argument("role_id")
    domains.set_defaults(func=lambda a: _run_with_connection(
        lambda conn: list_domains(conn, a.role_id)
    ))

    policy = sub.add_parser("policy-add")
    policy.add_argument("role_id")
    policy.add_argument("policy_key")
    policy.add_argument("policy_text")
    policy.add_argument("--status", default="draft")
    policy.set_defaults(func=lambda a: _out(add_policy(_connection(), a.role_id, a.policy_key, a.policy_text, status=a.status)))

    assignment = sub.add_parser("assignment-add")
    assignment.add_argument("role_id")
    assignment.add_argument("party_id")
    assignment.add_argument("--type", dest="assignment_type", default="primary")
    assignment.add_argument("--assigned-by-party-id")
    assignment.add_argument("--mandate")
    assignment.add_argument("--review-due-at", type=_parse_review_due_at)
    assignment.set_defaults(func=lambda a: _out(assign_role(
        _connection(), a.role_id, a.party_id, assignment_type=a.assignment_type,
        assigned_by_party_id=a.assigned_by_party_id, mandate=a.mandate,
        review_due_at=a.review_due_at,
    )))

    assignment_approve = sub.add_parser("assignment-approve")
    assignment_approve.add_argument("assignment_id")
    assignment_approve.add_argument("approved_by_party_id")
    assignment_approve.set_defaults(func=lambda a: _out(approve_assignment(_connection(), a.assignment_id, a.approved_by_party_id)))

    assignment_end = sub.add_parser("assignment-end")
    assignment_end.add_argument("assignment_id")
    assignment_end.add_argument("--recuse", action="store_true")
    assignment_end.set_defaults(func=lambda a: _out(end_assignment(_connection(), a.assignment_id, recused=a.recuse)))

    assignments = sub.add_parser("assignment-list")
    assignments.add_argument("--role-id")
    assignments.add_argument("--party-id")
    assignments.add_argument("--status")
    assignments.set_defaults(func=lambda a: _run_with_connection(
        lambda conn: list_assignments(conn, role_id=a.role_id, party_id=a.party_id, status=a.status)
    ))

    args = parser.parse_args()
    args.func(args)


def _connection():
    from services.common.database import get_db
    return get_db()


if __name__ == "__main__":
    main()
