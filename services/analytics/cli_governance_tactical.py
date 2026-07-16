"""CLI for tactical governance sessions and dispositions."""

from __future__ import annotations

import argparse
import json

from services.analytics.governance_tactical import (
    add_item,
    complete_session,
    create_session,
    dispose_item,
    list_items,
    list_sessions,
    start_item,
    start_session,
)


def _connection():
    from services.ingestion.base import get_db
    return get_db()


def _out(value):
    print(json.dumps(value, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokonut tactical governance CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    session = sub.add_parser("session-create")
    session.add_argument("circle_id")
    session.add_argument("session_type")
    session.add_argument("title")
    session.add_argument("--facilitator-role-id")
    session.add_argument("--recorder-role-id")
    session.add_argument("--agenda-scope")
    session.set_defaults(func=lambda a: _out(create_session(
        _connection(), a.circle_id, a.session_type, a.title,
        facilitator_role_id=a.facilitator_role_id, recorder_role_id=a.recorder_role_id,
        agenda_scope=a.agenda_scope,
    )))

    sessions = sub.add_parser("session-list")
    sessions.add_argument("--circle-id")
    sessions.add_argument("--status")
    sessions.set_defaults(func=lambda a: _out(list_sessions(_connection(), circle_id=a.circle_id, status=a.status)))

    session_start = sub.add_parser("session-start")
    session_start.add_argument("session_id")
    session_start.set_defaults(func=lambda a: _out(start_session(_connection(), a.session_id)))

    session_complete = sub.add_parser("session-complete")
    session_complete.add_argument("session_id")
    session_complete.add_argument("outcome_summary")
    session_complete.set_defaults(func=lambda a: _out(complete_session(_connection(), a.session_id, a.outcome_summary)))

    item = sub.add_parser("item-add")
    item.add_argument("session_id")
    item.add_argument("requested_next_action")
    item.add_argument("--tension-id")
    item.add_argument("--work-item-id")
    item.add_argument("--decision-id")
    item.add_argument("--owner-role-id")
    item.add_argument("--owner-party-id")
    item.add_argument("--priority", type=int, default=3)
    item.set_defaults(func=lambda a: _out(add_item(
        _connection(), a.session_id, a.requested_next_action, tension_id=a.tension_id,
        work_item_id=a.work_item_id, decision_id=a.decision_id,
        owner_role_id=a.owner_role_id, owner_party_id=a.owner_party_id, priority=a.priority,
    )))

    items = sub.add_parser("item-list")
    items.add_argument("session_id")
    items.add_argument("--status")
    items.set_defaults(func=lambda a: _out(list_items(_connection(), a.session_id, status=a.status)))

    item_start = sub.add_parser("item-start")
    item_start.add_argument("item_id")
    item_start.set_defaults(func=lambda a: _out(start_item(_connection(), a.item_id)))

    item_dispose = sub.add_parser("item-dispose")
    item_dispose.add_argument("item_id")
    item_dispose.add_argument("disposition_type")
    item_dispose.add_argument("disposition_summary")
    item_dispose.add_argument("disposed_by_party_id")
    item_dispose.set_defaults(func=lambda a: _out(dispose_item(
        _connection(), a.item_id, a.disposition_type, a.disposition_summary, a.disposed_by_party_id,
    )))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
