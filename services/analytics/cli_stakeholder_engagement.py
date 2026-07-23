"""CLI for stakeholder engagement plans and commitments."""

from __future__ import annotations

import argparse
import json
import sys

from services.analytics.stakeholder_engagement import (
    add_objective, create_commitment, create_plan, list_commitment_health,
    list_plans, record_outcome, schedule_touchpoint, update_commitment,
)
from services.common.database import get_db


def _out(data):
    print(json.dumps(data, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Stakeholder engagement management")
    sub = parser.add_subparsers(dest="command")

    plan = sub.add_parser("create-plan")
    plan.add_argument("name")
    plan.add_argument("--stakeholder-party-id", required=True)
    plan.add_argument("--description", default="")
    plan.add_argument("--owner-party-id")
    plan.add_argument("--organization-id")
    plan.add_argument("--scope-type", default="network")
    plan.add_argument("--scope-id")
    plan.add_argument("--engagement-mode", default="collaborate")
    plan.add_argument("--cadence-days", type=int, default=90)
    plan.set_defaults(func=lambda conn, a: create_plan(
        conn, a.name, a.stakeholder_party_id, description=a.description,
        owner_party_id=a.owner_party_id, organization_id=a.organization_id,
        scope_type=a.scope_type, scope_id=a.scope_id,
        engagement_mode=a.engagement_mode, cadence_days=a.cadence_days,
    ))

    listing = sub.add_parser("list-plans")
    listing.add_argument("--stakeholder-party-id")
    listing.add_argument("--status")
    listing.set_defaults(func=lambda conn, a: list_plans(
        conn, stakeholder_party_id=a.stakeholder_party_id, status=a.status,
    ))

    objective = sub.add_parser("add-objective")
    objective.add_argument("plan_id")
    objective.add_argument("title")
    objective.add_argument("desired_outcome")
    objective.add_argument("--description", default="")
    objective.add_argument("--success-metric")
    objective.add_argument("--target-value", type=float)
    objective.add_argument("--unit")
    objective.add_argument("--target-date")
    objective.add_argument("--priority", type=int, default=3)
    objective.set_defaults(func=lambda conn, a: add_objective(
        conn, a.plan_id, a.title, a.desired_outcome, description=a.description,
        success_metric=a.success_metric, target_value=a.target_value, unit=a.unit,
        target_date=a.target_date, priority=a.priority,
    ))

    touchpoint = sub.add_parser("schedule-touchpoint")
    touchpoint.add_argument("plan_id")
    touchpoint.add_argument("purpose")
    touchpoint.add_argument("--objective-id")
    touchpoint.add_argument("--channel-type")
    touchpoint.add_argument("--interaction-type", default="engagement")
    touchpoint.add_argument("--scheduled-at")
    touchpoint.add_argument("--consent-checked", action="store_true")
    touchpoint.add_argument("--notes")
    touchpoint.set_defaults(func=lambda conn, a: schedule_touchpoint(
        conn, a.plan_id, a.purpose, objective_id=a.objective_id,
        channel_type=a.channel_type, interaction_type=a.interaction_type,
        scheduled_at=a.scheduled_at, consent_checked=a.consent_checked, notes=a.notes,
    ))

    commitment = sub.add_parser("create-commitment")
    commitment.add_argument("plan_id")
    commitment.add_argument("title")
    commitment.add_argument("--description", default="")
    commitment.add_argument("--objective-id")
    commitment.add_argument("--touchpoint-id")
    commitment.add_argument("--committed-by-party-id")
    commitment.add_argument("--committed-to-party-id")
    commitment.add_argument("--owner-party-id")
    commitment.add_argument("--due-at")
    commitment.add_argument("--work-item-id")
    commitment.add_argument("--responsibility-id")
    commitment.set_defaults(func=lambda conn, a: create_commitment(
        conn, a.plan_id, a.title, description=a.description, objective_id=a.objective_id,
        touchpoint_id=a.touchpoint_id, committed_by_party_id=a.committed_by_party_id,
        committed_to_party_id=a.committed_to_party_id, owner_party_id=a.owner_party_id,
        due_at=a.due_at, work_item_id=a.work_item_id, responsibility_id=a.responsibility_id,
    ))

    update = sub.add_parser("update-commitment")
    update.add_argument("commitment_id")
    update.add_argument("--status", choices=["open", "in_progress", "fulfilled", "overdue", "waived", "cancelled"])
    update.add_argument("--work-item-id")
    update.add_argument("--responsibility-id")
    update.add_argument("--owner-party-id")
    update.set_defaults(func=lambda conn, a: update_commitment(
        conn, a.commitment_id, status=a.status, work_item_id=a.work_item_id,
        responsibility_id=a.responsibility_id, owner_party_id=a.owner_party_id,
    ))

    health = sub.add_parser("commitment-health")
    health.add_argument("--plan-id")
    health.add_argument("--overdue-only", action="store_true")
    health.set_defaults(func=lambda conn, a: list_commitment_health(
        conn, plan_id=a.plan_id, overdue_only=a.overdue_only,
    ))

    outcome = sub.add_parser("record-outcome")
    outcome.add_argument("plan_id")
    outcome.add_argument("outcome_type")
    outcome.add_argument("outcome_summary")
    outcome.add_argument("--objective-id")
    outcome.add_argument("--commitment-id")
    outcome.add_argument("--satisfaction-score", type=float)
    outcome.add_argument("--recorded-by")
    outcome.set_defaults(func=lambda conn, a: record_outcome(
        conn, a.plan_id, a.outcome_type, a.outcome_summary,
        objective_id=a.objective_id, commitment_id=a.commitment_id,
        satisfaction_score=a.satisfaction_score, recorded_by=a.recorded_by,
    ))

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
