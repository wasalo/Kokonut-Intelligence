"""CLI for governance tension intake and triage."""

from __future__ import annotations

import argparse
import json

from services.analytics.governance_tensions import (
    attach_work_item,
    defer_tension,
    get_tension,
    link_record,
    list_tensions,
    report_tension,
    resolve_tension,
    start_tension,
    submit_tension,
    triage_tension,
)


def _connection():
    from services.common.database import get_db
    return get_db()


def _out(value):
    print(json.dumps(value, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokonut governance tension CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    report = sub.add_parser("report")
    report.add_argument("tension_key")
    report.add_argument("title")
    report.add_argument("description")
    report.add_argument("tension_type")
    report.add_argument("--circle-id")
    report.add_argument("--scope-type", default="network")
    report.add_argument("--scope-id")
    report.add_argument("--reported-by-party-id")
    report.add_argument("--affected-party-id")
    report.add_argument("--affected-interest-id")
    report.add_argument("--severity", type=int, default=3)
    report.add_argument("--urgency", type=int, default=3)
    report.set_defaults(func=lambda a: _out(report_tension(
        _connection(), a.tension_key, a.title, a.description, a.tension_type,
        circle_id=a.circle_id, scope_type=a.scope_type, scope_id=a.scope_id,
        reported_by_party_id=a.reported_by_party_id,
        affected_party_id=a.affected_party_id, affected_interest_id=a.affected_interest_id,
        severity=a.severity, urgency=a.urgency,
    )))

    listing = sub.add_parser("list")
    listing.add_argument("--circle-id")
    listing.add_argument("--status")
    listing.add_argument("--overdue-only", action="store_true")
    listing.set_defaults(func=lambda a: _out(list_tensions(_connection(), circle_id=a.circle_id, status=a.status, overdue_only=a.overdue_only)))

    show = sub.add_parser("show")
    show.add_argument("tension_id")
    show.set_defaults(func=lambda a: _out(get_tension(_connection(), a.tension_id)))

    submit = sub.add_parser("submit")
    submit.add_argument("tension_id")
    submit.add_argument("--actor-party-id")
    submit.set_defaults(func=lambda a: _out(submit_tension(_connection(), a.tension_id, actor_party_id=a.actor_party_id)))

    triage = sub.add_parser("triage")
    triage.add_argument("tension_id")
    triage.add_argument("--owner-role-id")
    triage.add_argument("--owner-party-id")
    triage.add_argument("--actor-party-id")
    triage.add_argument("--note")
    triage.set_defaults(func=lambda a: _out(triage_tension(
        _connection(), a.tension_id, owner_role_id=a.owner_role_id,
        owner_party_id=a.owner_party_id, actor_party_id=a.actor_party_id, note=a.note,
    )))

    start = sub.add_parser("start")
    start.add_argument("tension_id")
    start.add_argument("--actor-party-id")
    start.set_defaults(func=lambda a: _out(start_tension(_connection(), a.tension_id, actor_party_id=a.actor_party_id)))

    link = sub.add_parser("link")
    link.add_argument("tension_id")
    link.add_argument("link_type")
    link.add_argument("entity_type")
    link.add_argument("entity_id")
    link.add_argument("--summary")
    link.add_argument("--created-by-party-id")
    link.set_defaults(func=lambda a: _out(link_record(
        _connection(), a.tension_id, a.link_type, a.entity_type, a.entity_id,
        summary=a.summary, created_by_party_id=a.created_by_party_id,
    )))

    work = sub.add_parser("link-work-item")
    work.add_argument("tension_id")
    work.add_argument("work_item_id")
    work.add_argument("--actor-party-id")
    work.set_defaults(func=lambda a: _out(attach_work_item(_connection(), a.tension_id, a.work_item_id, actor_party_id=a.actor_party_id)))

    resolve = sub.add_parser("resolve")
    resolve.add_argument("tension_id")
    resolve.add_argument("resolution_summary")
    resolve.add_argument("--actor-party-id")
    resolve.set_defaults(func=lambda a: _out(resolve_tension(_connection(), a.tension_id, a.resolution_summary, actor_party_id=a.actor_party_id)))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
