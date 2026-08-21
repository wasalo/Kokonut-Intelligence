"""CLI for protected stakeholder grievance cases."""

from __future__ import annotations

import argparse
import sys

from services.analytics.stakeholder_grievances import (
    acknowledge_case,
    add_evidence,
    appeal_case,
    assign_investigation,
    close_case,
    create_case,
    decide_appeal,
    list_case_health,
    propose_remedy,
    update_remedy,
)
from services.common.cli import print_json
from services.common.database import get_db


def _out(data):
    print_json(data)


def main():
    parser = argparse.ArgumentParser(description="Stakeholder grievance and remedy workflow")
    sub = parser.add_subparsers(dest="command")

    case = sub.add_parser("create-case")
    case.add_argument("category")
    case.add_argument("summary")
    case.add_argument("--feedback-id")
    case.add_argument("--complainant-party-id")
    case.add_argument("--affected-party-id")
    case.add_argument("--location-id")
    case.add_argument("--severity", default="medium", choices=["low", "medium", "high", "critical"])
    case.add_argument("--confidentiality", default="restricted", choices=["private", "restricted", "internal"])
    case.add_argument("--protected-details")
    case.add_argument("--retaliation-risk", action="store_true")
    case.add_argument("--owner-party-id")
    case.add_argument("--due-at")
    case.add_argument("--work-item-id")
    case.set_defaults(func=lambda conn, a: create_case(
        conn, a.category, a.summary, feedback_id=a.feedback_id,
        complainant_party_id=a.complainant_party_id, affected_party_id=a.affected_party_id,
        location_id=a.location_id, severity=a.severity, confidentiality=a.confidentiality,
        protected_details=a.protected_details, retaliation_risk=a.retaliation_risk,
        owner_party_id=a.owner_party_id, due_at=a.due_at, work_item_id=a.work_item_id,
    ))

    acknowledge = sub.add_parser("acknowledge")
    acknowledge.add_argument("case_id")
    acknowledge.add_argument("--owner-party-id")
    acknowledge.set_defaults(func=lambda conn, a: acknowledge_case(conn, a.case_id, owner_party_id=a.owner_party_id))

    investigation = sub.add_parser("assign-investigation")
    investigation.add_argument("case_id")
    investigation.add_argument("investigator_party_id")
    investigation.add_argument("scope")
    investigation.add_argument("--conflict-check-status", default="clear", choices=["pending", "clear", "waived"])
    investigation.set_defaults(func=lambda conn, a: assign_investigation(
        conn, a.case_id, a.investigator_party_id, a.scope, conflict_check_status=a.conflict_check_status,
    ))

    evidence = sub.add_parser("add-evidence")
    evidence.add_argument("case_id")
    evidence.add_argument("evidence_type")
    evidence.add_argument("title")
    evidence.add_argument("--investigation-id")
    evidence.add_argument("--description")
    evidence.add_argument("--content-hash")
    evidence.add_argument("--content-cid")
    evidence.add_argument("--submitted-by-party-id")
    evidence.add_argument("--confidentiality", default="restricted")
    evidence.set_defaults(func=lambda conn, a: add_evidence(
        conn, a.case_id, a.evidence_type, a.title, investigation_id=a.investigation_id,
        description=a.description, content_hash=a.content_hash, content_cid=a.content_cid,
        submitted_by_party_id=a.submitted_by_party_id, confidentiality=a.confidentiality,
    ))

    remedy = sub.add_parser("propose-remedy")
    remedy.add_argument("case_id")
    remedy.add_argument("remedy_type")
    remedy.add_argument("proposal")
    remedy.add_argument("--owner-party-id")
    remedy.add_argument("--due-at")
    remedy.set_defaults(func=lambda conn, a: propose_remedy(
        conn, a.case_id, a.remedy_type, a.proposal, owner_party_id=a.owner_party_id, due_at=a.due_at,
    ))

    remedy_update = sub.add_parser("update-remedy")
    remedy_update.add_argument("remedy_id")
    remedy_update.add_argument("status", choices=["proposed", "accepted", "in_progress", "completed", "rejected", "waived"])
    remedy_update.add_argument("--affected-party-confirmed", action="store_true")
    remedy_update.set_defaults(func=lambda conn, a: update_remedy(
        conn, a.remedy_id, a.status, affected_party_confirmed=a.affected_party_confirmed,
    ))

    appeal = sub.add_parser("appeal")
    appeal.add_argument("case_id")
    appeal.add_argument("reason")
    appeal.add_argument("--appealed-by-party-id")
    appeal.set_defaults(func=lambda conn, a: appeal_case(conn, a.case_id, a.reason, appealed_by_party_id=a.appealed_by_party_id))

    appeal_decide = sub.add_parser("decide-appeal")
    appeal_decide.add_argument("appeal_id")
    appeal_decide.add_argument("status", choices=["upheld", "overturned", "closed"])
    appeal_decide.add_argument("reviewer_party_id")
    appeal_decide.add_argument("decision_notes")
    appeal_decide.set_defaults(func=lambda conn, a: decide_appeal(
        conn, a.appeal_id, a.status, a.reviewer_party_id, a.decision_notes,
    ))

    close = sub.add_parser("close")
    close.add_argument("case_id")
    close.add_argument("closure_reason")
    close.add_argument("--satisfaction-score", type=float)
    close.add_argument("--complainant-confirmed", action="store_true")
    close.add_argument("--independent-review-completed", action="store_true")
    close.add_argument("--closed-by-party-id")
    close.add_argument("--closure-notes")
    close.set_defaults(func=lambda conn, a: close_case(
        conn, a.case_id, a.closure_reason, satisfaction_score=a.satisfaction_score,
        complainant_confirmed=a.complainant_confirmed,
        independent_review_completed=a.independent_review_completed,
        closed_by_party_id=a.closed_by_party_id, closure_notes=a.closure_notes,
    ))

    health = sub.add_parser("health")
    health.add_argument("--status")
    health.add_argument("--overdue-only", action="store_true")
    health.set_defaults(func=lambda conn, a: list_case_health(conn, status=a.status, overdue_only=a.overdue_only))

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
