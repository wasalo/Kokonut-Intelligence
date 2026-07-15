"""CLI for stakeholder representation and equity records."""

from __future__ import annotations

import argparse
import json
import sys

from services.analytics.stakeholder_representation import (
    list_distribution_summary, record_accessibility_request,
    record_distribution, record_minority_view, record_participation,
    representation_metrics,
)
from services.ingestion.base import get_db


def _out(data):
    print(json.dumps(data, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Stakeholder representation and equity")
    sub = parser.add_subparsers(dest="command")

    participation = sub.add_parser("record-participation")
    participation.add_argument("activity_type")
    participation.add_argument("activity_id")
    participation.add_argument("--party-id")
    participation.add_argument("--anonymous-group")
    participation.add_argument("--stakeholder-role")
    participation.add_argument("--status", default="invited")
    participation.add_argument("--contribution-count", type=int, default=0)
    participation.add_argument("--consent-checked", action="store_true")
    participation.add_argument("--language")
    participation.set_defaults(func=lambda conn, a: record_participation(
        conn, a.activity_type, a.activity_id, party_id=a.party_id,
        anonymous_group=a.anonymous_group, stakeholder_role=a.stakeholder_role,
        invitation_status=a.status, contribution_count=a.contribution_count,
        consent_checked=a.consent_checked, language=a.language,
    ))

    accessibility = sub.add_parser("request-accessibility")
    accessibility.add_argument("participation_id")
    accessibility.add_argument("need_type")
    accessibility.add_argument("requested_support")
    accessibility.add_argument("--party-id")
    accessibility.set_defaults(func=lambda conn, a: record_accessibility_request(
        conn, a.participation_id, a.need_type, a.requested_support, party_id=a.party_id,
    ))

    minority = sub.add_parser("record-minority-view")
    minority.add_argument("activity_type")
    minority.add_argument("activity_id")
    minority.add_argument("view_summary")
    minority.add_argument("--party-id")
    minority.add_argument("--anonymous-group")
    minority.add_argument("--concern-or-risk")
    minority.add_argument("--not-preserved", action="store_true")
    minority.add_argument("--decision-response")
    minority.set_defaults(func=lambda conn, a: record_minority_view(
        conn, a.activity_type, a.activity_id, a.view_summary, party_id=a.party_id,
        anonymous_group=a.anonymous_group, concern_or_risk=a.concern_or_risk,
        preserved=not a.not_preserved, decision_response=a.decision_response,
    ))

    distribution = sub.add_parser("record-distribution")
    distribution.add_argument("scope_type")
    distribution.add_argument("distribution_type")
    distribution.add_argument("metric_name")
    distribution.add_argument("amount", type=float)
    distribution.add_argument("unit")
    distribution.add_argument("--scope-id")
    distribution.add_argument("--beneficiary-party-id")
    distribution.add_argument("--stakeholder-type")
    distribution.add_argument("--period-start")
    distribution.add_argument("--period-end")
    distribution.add_argument("--status", default="draft")
    distribution.add_argument("--created-by")
    distribution.set_defaults(func=lambda conn, a: record_distribution(
        conn, a.scope_type, a.distribution_type, a.metric_name, a.amount, a.unit,
        scope_id=a.scope_id, beneficiary_party_id=a.beneficiary_party_id,
        stakeholder_type=a.stakeholder_type, period_start=a.period_start,
        period_end=a.period_end, status=a.status, created_by=a.created_by,
    ))

    metrics = sub.add_parser("metrics")
    metrics.add_argument("activity_type")
    metrics.add_argument("activity_id")
    metrics.set_defaults(func=lambda conn, a: representation_metrics(conn, a.activity_type, a.activity_id))

    summary = sub.add_parser("distribution-summary")
    summary.add_argument("--scope-type")
    summary.add_argument("--scope-id")
    summary.set_defaults(func=lambda conn, a: list_distribution_summary(conn, scope_type=a.scope_type, scope_id=a.scope_id))

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
