"""Tests for governed coordination alliances and knowledge networks."""

import pytest

from services.ingestion.base import get_db
from services.analytics.coordination import (
    activate_alliance,
    activate_participant,
    add_benefit,
    add_contribution,
    add_knowledge_exchange,
    add_objective,
    add_participant,
    add_risk,
    approve_alliance,
    create_alliance,
    get_coordination_health,
)
from services.agents.safety import assess_agent_action


def _db():
    try:
        return get_db()
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")


def test_coordination_round_trip():
    conn = _db()
    alliance = create_alliance(
        "Adelphi knowledge network",
        "Share regenerative practice and market learning without equity transfer.",
        coordination_type="knowledge_network",
        steward_party_id="a0000000-0000-0000-0000-000000001000",
        created_by_party_id="a0000000-0000-0000-0000-000000001000",
    )
    try:
        approved = approve_alliance(
            alliance["id"], "a0000000-0000-0000-0000-000000001000", "Reviewed scope, risks, and participant protections",
        )
        assert approved["status"] == "approved"
        active = activate_alliance(alliance["id"], "a0000000-0000-0000-0000-000000001000")
        assert active["status"] == "active"

        participant = add_participant(
            alliance["id"], "a0000000-0000-0000-0000-000000001001",
            role="participant", consent_event_id="a0000000-0000-0000-0000-000000001090",
        )
        participant = activate_participant(participant["id"], "a0000000-0000-0000-0000-000000001090")
        assert participant["status"] == "active"
        assert add_objective(alliance["id"], "Share field learning", "Exchange practical evidence", "knowledge")["alliance_id"] == alliance["id"]
        assert add_contribution(alliance["id"], participant["id"], "knowledge", "Spanish-language field note")["participant_id"] == participant["id"]
        assert add_benefit(alliance["id"], "Access to peer learning", "capability")["alliance_id"] == alliance["id"]
        assert add_risk(alliance["id"], "exclusion", "Language access may limit participation")["alliance_id"] == alliance["id"]
        exchange = add_knowledge_exchange(alliance["id"], participant["party_id"], "Syntropic bed design", "practice", to_party_id=alliance["steward_party_id"], consent_scope="network")
        assert exchange["status"] == "proposed"
        assert get_coordination_health(alliance["id"])[0]["active_participant_count"] == 1
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM coordination_alliance WHERE id = %s::uuid", (alliance["id"],))
        conn.commit()


def test_coordination_agents_cannot_write_governed_records():
    decision = assess_agent_action("create", "coordination_alliance", {"status": "draft"})
    assert not decision.allowed
    assert decision.requires_human_approval
