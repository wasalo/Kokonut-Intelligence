"""CLI for stakeholder decision lineage."""

from __future__ import annotations

import argparse
import json
import sys

from services.analytics import stakeholder_decisions as decisions
from services.common.database import get_db


def _out(data):
    print(json.dumps(data, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Stakeholder decision lineage")
    sub = parser.add_subparsers(dest="command")

    create = sub.add_parser("create")
    create.add_argument("title")
    create.add_argument("description")
    create.add_argument("decision_type")
    create.add_argument("--decision-key")
    create.add_argument("--scope-type", default="network")
    create.add_argument("--scope-id")
    create.add_argument("--proposed-action")
    create.add_argument("--created-by-party-id")
    create.set_defaults(func=lambda c, a: decisions.create_decision(
        c, a.title, a.description, a.decision_type, decision_key=a.decision_key,
        scope_type=a.scope_type, scope_id=a.scope_id, proposed_action=a.proposed_action,
        created_by_party_id=a.created_by_party_id))

    submit = sub.add_parser("submit")
    submit.add_argument("decision_id")
    submit.set_defaults(func=lambda c, a: decisions.submit_decision(c, a.decision_id))

    approve = sub.add_parser("approve")
    approve.add_argument("decision_id")
    approve.add_argument("approved_by_party_id")
    approve.set_defaults(func=lambda c, a: decisions.approve_decision(c, a.decision_id, a.approved_by_party_id))

    reject = sub.add_parser("reject")
    reject.add_argument("decision_id")
    reject.add_argument("--reason")
    reject.set_defaults(func=lambda c, a: decisions.reject_decision(c, a.decision_id, reason=a.reason))

    execute = sub.add_parser("link-execution")
    execute.add_argument("decision_id")
    execute.add_argument("--work-item-id")
    execute.add_argument("--decision-log-id")
    execute.set_defaults(func=lambda c, a: decisions.link_execution(
        c, a.decision_id, work_item_id=a.work_item_id, decision_log_id=a.decision_log_id))

    complete = sub.add_parser("complete")
    complete.add_argument("decision_id")
    complete.set_defaults(func=lambda c, a: decisions.complete_decision(c, a.decision_id))

    participant = sub.add_parser("add-participant")
    participant.add_argument("decision_id")
    participant.add_argument("stakeholder_role")
    participant.add_argument("--party-id")
    participant.add_argument("--participation-id")
    participant.add_argument("--status", default="invited")
    participant.add_argument("--consent-checked", action="store_true")
    participant.add_argument("--perspective-summary")
    participant.add_argument("--minority-view", action="store_true")
    participant.set_defaults(func=lambda c, a: decisions.add_participant(
        c, a.decision_id, party_id=a.party_id, participation_id=a.participation_id,
        stakeholder_role=a.stakeholder_role, participation_status=a.status,
        consent_checked=a.consent_checked, perspective_summary=a.perspective_summary,
        minority_view=a.minority_view))

    tradeoff = sub.add_parser("add-tradeoff")
    tradeoff.add_argument("decision_id")
    tradeoff.add_argument("direction")
    tradeoff.add_argument("description")
    tradeoff.add_argument("--interest-id")
    tradeoff.add_argument("--party-id")
    tradeoff.add_argument("--severity", type=float)
    tradeoff.add_argument("--accepted", action="store_true")
    tradeoff.add_argument("--mitigation")
    tradeoff.set_defaults(func=lambda c, a: decisions.add_tradeoff(
        c, a.decision_id, a.description, a.direction, interest_id=a.interest_id,
        party_id=a.party_id, severity=a.severity, accepted=a.accepted, mitigation=a.mitigation))

    evidence = sub.add_parser("add-evidence")
    evidence.add_argument("decision_id")
    evidence.add_argument("source_type")
    evidence.add_argument("summary")
    evidence.add_argument("--role", default="supporting")
    evidence.add_argument("--source-id")
    evidence.add_argument("--source-key")
    evidence.add_argument("--content-hash")
    evidence.add_argument("--content-cid")
    evidence.add_argument("--maturity", type=int)
    evidence.add_argument("--verified", action="store_true")
    evidence.add_argument("--audience", default="internal")
    evidence.add_argument("--added-by-party-id")
    evidence.set_defaults(func=lambda c, a: decisions.add_evidence(
        c, a.decision_id, a.source_type, a.summary, evidence_role=a.role,
        source_id=a.source_id, source_key=a.source_key, content_hash=a.content_hash,
        content_cid=a.content_cid, evidence_maturity=a.maturity, verified=a.verified,
        audience=a.audience, added_by_party_id=a.added_by_party_id))

    outcome = sub.add_parser("record-outcome")
    outcome.add_argument("decision_id")
    outcome.add_argument("outcome_type")
    outcome.add_argument("summary")
    outcome.add_argument("--source-id")
    outcome.add_argument("--status", default="observed")
    outcome.add_argument("--recorded-by-party-id")
    outcome.set_defaults(func=lambda c, a: decisions.record_outcome(
        c, a.decision_id, a.outcome_type, a.summary, source_id=a.source_id,
        outcome_status=a.status, recorded_by_party_id=a.recorded_by_party_id))

    show = sub.add_parser("show")
    show.add_argument("decision_id")
    show.set_defaults(func=lambda c, a: decisions.get_decision(c, a.decision_id))

    listing = sub.add_parser("list")
    listing.add_argument("--status")
    listing.add_argument("--scope-id")
    listing.set_defaults(func=lambda c, a: decisions.list_decisions(c, status=a.status, scope_id=a.scope_id))

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
