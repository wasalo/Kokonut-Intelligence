"""CLI for governed coordination alliances and knowledge networks."""

from __future__ import annotations

import argparse
import json

from services.analytics.coordination import (
    activate_alliance, activate_participant, add_benefit, add_contribution,
    add_knowledge_exchange, add_objective, add_participant, add_risk,
    approve_alliance, create_alliance, get_coordination_health, list_alliances,
)


def _out(value):
    print(json.dumps(value, indent=2, default=str))


def build_parser(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="coordination_cmd", required=True)

    create = sub.add_parser("create", help="Create a draft alliance or network")
    create.add_argument("name")
    create.add_argument("purpose")
    create.add_argument("--type", dest="coordination_type", default="alliance",
                        choices=["alliance", "cooperative_network", "knowledge_network", "ecological_alliance", "joint_venture", "equity_alliance", "nonequity_alliance"])
    create.add_argument("--scope-type", default="network")
    create.add_argument("--scope-id")
    create.add_argument("--strategy-id")
    create.add_argument("--value-stream-id")
    create.add_argument("--stakeholder-decision-id")
    create.add_argument("--cooperative-proposal-id")
    create.add_argument("--steward-party-id")
    create.add_argument("--created-by-party-id")
    create.add_argument("--market-cycle", choices=["slow", "standard", "fast"], default="standard")
    create.add_argument("--work-item-id")
    create.add_argument("--proxy-authority-id")
    create.add_argument("--review-due-at")
    create.add_argument("--approval-quorum", type=int, default=1)
    create.set_defaults(func=lambda a: _out(create_alliance(
        a.name, a.purpose, coordination_type=a.coordination_type, scope_type=a.scope_type,
        scope_id=a.scope_id, strategy_map_id=a.strategy_id, value_stream_id=a.value_stream_id,
        stakeholder_decision_id=a.stakeholder_decision_id, cooperative_proposal_id=a.cooperative_proposal_id,
        steward_party_id=a.steward_party_id, created_by_party_id=a.created_by_party_id,
        market_cycle=a.market_cycle, work_item_id=a.work_item_id,
        proxy_authority_id=a.proxy_authority_id, review_due_at=a.review_due_at,
         approval_quorum_required=a.approval_quorum)))

    listing = sub.add_parser("list", help="List alliances")
    listing.add_argument("--status")
    listing.add_argument("--type", dest="coordination_type")
    listing.set_defaults(func=lambda a: _out(list_alliances(status=a.status, coordination_type=a.coordination_type)))

    approve = sub.add_parser("approve", help="Human-approve an alliance")
    approve.add_argument("alliance_id")
    approve.add_argument("approved_by_party_id")
    approve.add_argument("approval_basis")
    approve.set_defaults(func=lambda a: _out(approve_alliance(a.alliance_id, a.approved_by_party_id, a.approval_basis)))

    activate = sub.add_parser("activate", help="Human-activate an approved alliance")
    activate.add_argument("alliance_id")
    activate.add_argument("approved_by_party_id")
    activate.set_defaults(func=lambda a: _out(activate_alliance(a.alliance_id, a.approved_by_party_id)))

    participant = sub.add_parser("participant-add", help="Add a proposed participant")
    participant.add_argument("alliance_id")
    participant.add_argument("party_id")
    participant.add_argument("--role", default="participant")
    participant.add_argument("--consent-event-id")
    participant.add_argument("--contribution-expectation")
    participant.add_argument("--benefit-expectation")
    participant.set_defaults(func=lambda a: _out(add_participant(
        a.alliance_id, a.party_id, role=a.role, consent_event_id=a.consent_event_id,
        contribution_expectation=a.contribution_expectation, benefit_expectation=a.benefit_expectation)))

    participant_activate = sub.add_parser("participant-activate", help="Activate a consented participant")
    participant_activate.add_argument("participant_id")
    participant_activate.add_argument("consent_event_id")
    participant_activate.set_defaults(func=lambda a: _out(activate_participant(a.participant_id, a.consent_event_id)))

    objective = sub.add_parser("objective-add", help="Add a shared objective")
    objective.add_argument("alliance_id")
    objective.add_argument("title")
    objective.add_argument("description")
    objective.add_argument("--type", dest="objective_type", required=True)
    objective.add_argument("--target-value", type=float)
    objective.add_argument("--target-unit")
    objective.add_argument("--harm-if-missed")
    objective.set_defaults(func=lambda a: _out(add_objective(
        a.alliance_id, a.title, a.description, a.objective_type,
        target_value=a.target_value, target_unit=a.target_unit, harm_if_missed=a.harm_if_missed)))

    contribution = sub.add_parser("contribution-add", help="Record a proposed contribution")
    contribution.add_argument("alliance_id")
    contribution.add_argument("participant_id")
    contribution.add_argument("description")
    contribution.add_argument("--type", dest="contribution_type", required=True)
    contribution.add_argument("--value", type=float, dest="committed_value")
    contribution.add_argument("--unit", dest="value_unit")
    contribution.set_defaults(func=lambda a: _out(add_contribution(
        a.alliance_id, a.participant_id, a.contribution_type, a.description,
        committed_value=a.committed_value, value_unit=a.value_unit)))

    benefit = sub.add_parser("benefit-add", help="Record a proposed benefit")
    benefit.add_argument("alliance_id")
    benefit.add_argument("description")
    benefit.add_argument("--type", dest="benefit_type", required=True)
    benefit.add_argument("--participant-id")
    benefit.add_argument("--value", type=float, dest="expected_value")
    benefit.add_argument("--unit", dest="value_unit")
    benefit.set_defaults(func=lambda a: _out(add_benefit(
        a.alliance_id, a.description, a.benefit_type, participant_id=a.participant_id,
        expected_value=a.expected_value, value_unit=a.value_unit)))

    risk = sub.add_parser("risk-add", help="Record a coordination risk")
    risk.add_argument("alliance_id")
    risk.add_argument("description")
    risk.add_argument("--type", dest="risk_type", required=True)
    risk.add_argument("--likelihood", type=float)
    risk.add_argument("--impact", type=float)
    risk.add_argument("--mitigation")
    risk.add_argument("--owner-party-id")
    risk.set_defaults(func=lambda a: _out(add_risk(
        a.alliance_id, a.risk_type, a.description, likelihood=a.likelihood,
        impact=a.impact, mitigation=a.mitigation, owner_party_id=a.owner_party_id)))

    exchange = sub.add_parser("exchange-add", help="Record a proposed knowledge exchange")
    exchange.add_argument("alliance_id")
    exchange.add_argument("from_party_id")
    exchange.add_argument("topic")
    exchange.add_argument("--type", dest="exchange_type", required=True)
    exchange.add_argument("--to-party-id")
    exchange.add_argument("--artifact-uri")
    exchange.add_argument("--consent-scope")
    exchange.add_argument("--consent-event-id")
    exchange.set_defaults(func=lambda a: _out(add_knowledge_exchange(
        a.alliance_id, a.from_party_id, a.topic, a.exchange_type,
        to_party_id=a.to_party_id, artifact_uri=a.artifact_uri, consent_scope=a.consent_scope,
        consent_event_id=a.consent_event_id)))

    health = sub.add_parser("health", help="Show coordination health")
    health.add_argument("--alliance-id")
    health.set_defaults(func=lambda a: _out(get_coordination_health(a.alliance_id)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Coordination Strategy CLI")
    build_parser(parser)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
