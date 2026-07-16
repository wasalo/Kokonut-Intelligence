"""Tests for coordination accounting and learning integration."""

import pytest
import uuid

from services.agents.safety import assess_agent_action
from services.analytics.capability_map import create_capability
from services.analytics.coordination import add_benefit, add_risk, create_alliance
from services.analytics.coordination_accounting import (
    approve_benefit_distribution,
    assess_contribution_balance,
    explain_coordination_health,
    link_learning_target,
    record_benefit_delivery,
    record_contribution,
    record_exchange,
    record_metric_observation,
    record_market_performance,
    record_partner_event,
    review_risk,
)
from services.analytics.coordination_strategy import (
    declare_conflict, record_benefit_harm_analysis, review_and_renew,
    review_benefit_harm_analysis, review_conflict_declaration,
)
from services.ingestion.base import get_db


def _db():
    try:
        return get_db()
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")


def test_accounting_and_learning_round_trip():
    conn = _db()
    alliance = create_alliance("Accounting test alliance", "Test reciprocal coordination evidence")
    capability = create_capability(f"Coordination accounting test capability {uuid.uuid4()}", guild_key="test_coordination_accounting")
    try:
        declaration = declare_conflict(alliance["id"], "a0000000-0000-0000-0000-000000001000", "no_conflict", "No conflict declared")
        review_conflict_declaration(declaration["id"], "a0000000-0000-0000-0000-000000001000")
        analysis = record_benefit_harm_analysis(alliance["id"], "benefit", "Benefits and harms reviewed")
        review_benefit_harm_analysis(analysis["id"], "a0000000-0000-0000-0000-000000001000")
        from services.analytics.coordination import activate_alliance, approve_alliance
        approve_alliance(alliance["id"], "a0000000-0000-0000-0000-000000001000", "Reviewed accounting controls")
        activate_alliance(alliance["id"], "a0000000-0000-0000-0000-000000001000")
        participant_id = None
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO coordination_participant (alliance_id, party_id, role, status, consent_event_id) VALUES (%s::uuid, %s::uuid, 'participant', 'active', %s::uuid) RETURNING id",
                (alliance["id"], "a0000000-0000-0000-0000-000000001001", "a0000000-0000-0000-0000-000000001090"),
            )
            participant_id = str(cur.fetchone()[0])
            conn.commit()

        contribution = record_contribution(alliance["id"], participant_id, "knowledge", "Share field protocol", committed_value=10, value_unit="hours", idempotency_key="coord-test-contribution")
        assert record_contribution(alliance["id"], participant_id, "knowledge", "Duplicate retry", idempotency_key="coord-test-contribution")["id"] == contribution["id"]
        with conn.cursor() as cur:
            cur.execute("UPDATE coordination_contribution SET status = 'delivered' WHERE id = %s::uuid", (contribution["id"],))
            conn.commit()
        benefit = add_benefit(alliance["id"], "Peer learning access", "capability", participant_id=participant_id)
        assert approve_benefit_distribution(benefit["id"], "a0000000-0000-0000-0000-000000001000", "Reviewed for equitable access")["allocation_status"] == "approved"
        assert record_benefit_delivery(benefit["id"])["allocation_status"] == "delivered"
        risk = add_risk(alliance["id"], "dependency", "Single knowledge holder", likelihood=0.4, impact=0.7)
        assert review_risk(risk["id"], "monitoring", "a0000000-0000-0000-0000-000000001000")["status"] == "monitoring"
        assert assess_contribution_balance(alliance["id"])["warning"] is False
        assert record_partner_event(alliance["id"], "failure", "Knowledge holder unavailable", participant_id=participant_id)["event_type"] == "failure"
        assert record_market_performance(alliance["id"], "late", "Delivery missed the agreed date")["outcome"] == "late"
        assert record_exchange(alliance["id"], "a0000000-0000-0000-0000-000000001001", "Field protocol", "practice")["status"] == "proposed"
        link = link_learning_target(
            alliance["id"], "capability_maturity", "Close capability gap", "Track capability maturity change",
            target_id=capability["id"], baseline_value=2, current_value=3, target_value=4, unit="level",
        )
        assert link["capability_id"] == capability["id"]
        observation = record_metric_observation(
            alliance["id"], "reciprocal_contribution_ratio", 1, "contributions_per_participant",
            "Delivered contribution records divided by active participants.", numerator=1, denominator=1,
        )
        assert observation["status"] == "draft"
        health = explain_coordination_health(alliance["id"])
        assert health["metrics"]["unresolved_coordination_risk"]["value"] == 1
        assert "reputation" in health["interpretation"]
        assert set(health["metrics"]) == {
            "capability_gap_closed", "knowledge_transfer_completion_rate",
            "reciprocal_contribution_ratio", "stakeholder_outcome_improvement",
            "coordination_lead_time", "unresolved_coordination_risk",
            "benefit_distribution_equity", "dependency_concentration",
            "partner_substitution_resilience", "partner_failure_count",
            "market_performance_success_rate",
        }
        review = review_and_renew(
            alliance["id"], "2026-01-01", "2026-03-31", "a0000000-0000-0000-0000-000000001000",
            "One active participant", "One capability benefit delivered", "Dependency risk monitored",
            "Continue with a new term", "continue",
        )
        assert review["recommendation"] == "continue"
        with conn.cursor() as cur:
            cur.execute("SELECT ca.status, cr.findings FROM coordination_alliance ca JOIN coordination_review cr ON cr.alliance_id = ca.id WHERE ca.id = %s::uuid ORDER BY cr.created_at DESC LIMIT 1", (alliance["id"],))
            review_row = cur.fetchone()
            assert review_row[0] == "proposed"
            assert "Adverse market performance" in review_row[1]
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM coordination_alliance WHERE id = %s::uuid", (alliance["id"],))
            cur.execute("DELETE FROM business_capability WHERE id = %s::uuid", (capability["id"],))
        conn.commit()


def test_agents_cannot_write_accounting_or_learning_records():
    for collection in ("coordination_learning_link", "coordination_metric_observation"):
        decision = assess_agent_action("create", collection, {"status": "draft"})
        assert not decision.allowed
        assert decision.requires_human_approval


def test_unequal_contributions_produce_a_review_warning():
    conn = _db()
    alliance = create_alliance("Contribution balance test", "Test unequal contribution warning")
    try:
        declaration = declare_conflict(alliance["id"], "a0000000-0000-0000-0000-000000001000", "no_conflict", "No conflict")
        review_conflict_declaration(declaration["id"], "a0000000-0000-0000-0000-000000001000")
        analysis = record_benefit_harm_analysis(alliance["id"], "benefit", "Reviewed benefit")
        review_benefit_harm_analysis(analysis["id"], "a0000000-0000-0000-0000-000000001000")
        from services.analytics.coordination import activate_alliance, approve_alliance
        approve_alliance(alliance["id"], "a0000000-0000-0000-0000-000000001000", "Reviewed")
        activate_alliance(alliance["id"], "a0000000-0000-0000-0000-000000001000")
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO coordination_participant (alliance_id, party_id, role, status, consent_event_id)
                   VALUES (%s::uuid, %s::uuid, 'participant', 'active', %s::uuid),
                          (%s::uuid, %s::uuid, 'participant', 'active', %s::uuid)
                   RETURNING id""",
                (alliance["id"], "a0000000-0000-0000-0000-000000001001", "a0000000-0000-0000-0000-000000001090",
                 alliance["id"], "a0000000-0000-0000-0000-000000001002", "a0000000-0000-0000-0000-000000001090"),
            )
            participant_ids = [str(row[0]) for row in cur.fetchall()]
            for participant_id, value in zip(participant_ids, (100, 10)):
                cur.execute(
                    """INSERT INTO coordination_contribution
                       (alliance_id, participant_id, contribution_type, description, committed_value, value_unit, status)
                       VALUES (%s::uuid, %s::uuid, 'labor', 'Delivered work', %s, 'hours', 'delivered')""",
                    (alliance["id"], participant_id, value),
                )
            conn.commit()
        balance = assess_contribution_balance(alliance["id"])
        assert balance["warning"] is True
        assert balance["ratio"] == 10
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM coordination_alliance WHERE id = %s::uuid", (alliance["id"],))
        conn.commit()
