"""Tests for coordination accounting and learning integration."""

import pytest

from services.agents.safety import assess_agent_action
from services.analytics.capability_map import create_capability
from services.analytics.coordination import add_benefit, add_risk, create_alliance
from services.analytics.coordination_accounting import (
    approve_benefit_distribution,
    explain_coordination_health,
    link_learning_target,
    record_benefit_delivery,
    record_contribution,
    record_exchange,
    record_metric_observation,
    review_risk,
)
from services.analytics.coordination_strategy import review_and_renew
from services.ingestion.base import get_db


def _db():
    try:
        return get_db()
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")


def test_accounting_and_learning_round_trip():
    conn = _db()
    alliance = create_alliance("Accounting test alliance", "Test reciprocal coordination evidence")
    capability = create_capability("Coordination accounting test capability", guild_key="test_coordination_accounting")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE coordination_alliance SET status = 'active', approved_by_party_id = %s::uuid, approved_at = NOW() WHERE id = %s::uuid",
                ("a0000000-0000-0000-0000-000000001000", alliance["id"]),
            )
            conn.commit()
        participant_id = None
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO coordination_participant (alliance_id, party_id, role, status, consent_event_id) VALUES (%s::uuid, %s::uuid, 'participant', 'active', %s::uuid) RETURNING id",
                (alliance["id"], "a0000000-0000-0000-0000-000000001001", "a0000000-0000-0000-0000-000000001090"),
            )
            participant_id = str(cur.fetchone()[0])
            conn.commit()

        contribution = record_contribution(alliance["id"], participant_id, "knowledge", "Share field protocol")
        with conn.cursor() as cur:
            cur.execute("UPDATE coordination_contribution SET status = 'delivered' WHERE id = %s::uuid", (contribution["id"],))
            conn.commit()
        benefit = add_benefit(alliance["id"], "Peer learning access", "capability", participant_id=participant_id)
        assert approve_benefit_distribution(benefit["id"], "a0000000-0000-0000-0000-000000001000", "Reviewed for equitable access")["allocation_status"] == "approved"
        assert record_benefit_delivery(benefit["id"])["allocation_status"] == "delivered"
        risk = add_risk(alliance["id"], "dependency", "Single knowledge holder", likelihood=0.4, impact=0.7)
        assert review_risk(risk["id"], "monitoring", "a0000000-0000-0000-0000-000000001000")["status"] == "monitoring"
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
            "partner_substitution_resilience",
        }
        review = review_and_renew(
            alliance["id"], "2026-01-01", "2026-03-31", "a0000000-0000-0000-0000-000000001000",
            "One active participant", "One capability benefit delivered", "Dependency risk monitored",
            "Continue with a new term", "continue",
        )
        assert review["recommendation"] == "continue"
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM coordination_alliance WHERE id = %s::uuid", (alliance["id"],))
            assert cur.fetchone()[0] == "proposed"
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM coordination_alliance WHERE id = %s::uuid", (alliance["id"],))
            cur.execute("DELETE FROM business_capability WHERE id = %s::uuid", (capability["id"],))
        conn.commit()


def test_agents_cannot_write_accounting_or_learning_records():
    for collection in ("coordination_learning_link", "coordination_metric_observation"):
        decision = assess_agent_action("create", collection, {"status": "draft"})
        assert not decision.allowed
        assert decision.requires_human_approval
