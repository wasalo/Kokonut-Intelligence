"""CLI for governance proposals and integrative objections."""

from __future__ import annotations

import argparse

from services.analytics.governance_proposals import (
    add_objection,
    approve_proposal,
    create_proposal,
    get_proposal,
    implement_proposal,
    list_proposals,
    record_review,
    respond_to_objection,
    start_review,
    submit_proposal,
)
from services.common.cli import print_json


def _connection():
    from services.common.database import get_db
    return get_db()


def _out(value):
    print_json(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokonut governance proposal CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("proposal_key")
    create.add_argument("circle_id")
    create.add_argument("proposal_type")
    create.add_argument("title")
    create.add_argument("purpose")
    create.add_argument("proposed_state")
    create.add_argument("--current-state")
    create.add_argument("--tension-id")
    create.add_argument("--proposed-by-party-id")
    create.add_argument("--proposed-by-role-id")
    create.add_argument("--harm-review-status", default="not_required")
    create.add_argument("--minority-review-status", default="not_required")
    create.set_defaults(func=lambda a: _out(create_proposal(
        _connection(), a.proposal_key, a.circle_id, a.proposal_type, a.title,
        a.purpose, a.proposed_state, current_state=a.current_state,
        tension_id=a.tension_id, proposed_by_party_id=a.proposed_by_party_id,
        proposed_by_role_id=a.proposed_by_role_id,
        harm_review_status=a.harm_review_status,
        minority_review_status=a.minority_review_status,
    )))

    listing = sub.add_parser("list")
    listing.add_argument("--circle-id")
    listing.add_argument("--status")
    listing.set_defaults(func=lambda a: _out(list_proposals(_connection(), circle_id=a.circle_id, status=a.status)))

    show = sub.add_parser("show")
    show.add_argument("proposal_id")
    show.set_defaults(func=lambda a: _out(get_proposal(_connection(), a.proposal_id)))

    submit = sub.add_parser("submit")
    submit.add_argument("proposal_id")
    submit.set_defaults(func=lambda a: _out(submit_proposal(_connection(), a.proposal_id)))

    review = sub.add_parser("review")
    review.add_argument("proposal_id")
    review.set_defaults(func=lambda a: _out(start_review(_connection(), a.proposal_id)))

    objection = sub.add_parser("objection-add")
    objection.add_argument("proposal_id")
    objection.add_argument("objection_type")
    objection.add_argument("objection_text")
    objection.add_argument("--objector-party-id")
    objection.add_argument("--objector-role-id")
    objection.add_argument("--severity", type=int, default=3)
    objection.set_defaults(func=lambda a: _out(add_objection(
        _connection(), a.proposal_id, a.objection_type, a.objection_text,
        objector_party_id=a.objector_party_id, objector_role_id=a.objector_role_id,
        severity=a.severity,
    )))

    response = sub.add_parser("objection-respond")
    response.add_argument("objection_id")
    response.add_argument("status")
    response.add_argument("response")
    response.add_argument("resolved_by_party_id")
    response.set_defaults(func=lambda a: _out(respond_to_objection(
        _connection(), a.objection_id, a.status, a.response, a.resolved_by_party_id,
    )))

    human_review = sub.add_parser("record-review")
    human_review.add_argument("proposal_id")
    human_review.add_argument("reviewer_party_id")
    human_review.add_argument("review_type")
    human_review.add_argument("result")
    human_review.add_argument("notes")
    human_review.set_defaults(func=lambda a: _out(record_review(
        _connection(), a.proposal_id, a.reviewer_party_id, a.review_type,
        a.result, a.notes,
    )))

    approve = sub.add_parser("approve")
    approve.add_argument("proposal_id")
    approve.add_argument("approved_by_party_id")
    approve.set_defaults(func=lambda a: _out(approve_proposal(_connection(), a.proposal_id, a.approved_by_party_id)))

    implement = sub.add_parser("implement")
    implement.add_argument("proposal_id")
    implement.add_argument("work_item_id")
    implement.add_argument("implementation_summary")
    implement.set_defaults(func=lambda a: _out(implement_proposal(_connection(), a.proposal_id, a.work_item_id, a.implementation_summary)))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
