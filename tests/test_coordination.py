"""Tests for governed coordination alliances and knowledge networks."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

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
from services.analytics.coordination_strategy import (
    declare_conflict, record_benefit_harm_analysis,
    review_benefit_harm_analysis, review_conflict_declaration,
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
        declaration = declare_conflict(alliance["id"], "a0000000-0000-0000-0000-000000001000", "no_conflict", "No conflict declared")
        review_conflict_declaration(declaration["id"], "a0000000-0000-0000-0000-000000001000")
        analysis = record_benefit_harm_analysis(alliance["id"], "benefit", "Benefits and harms reviewed")
        review_benefit_harm_analysis(analysis["id"], "a0000000-0000-0000-0000-000000001000")
        approved = approve_alliance(
            alliance["id"], "a0000000-0000-0000-0000-000000001000", "Reviewed scope, risks, and participant protections",
        )
        assert approved["status"] == "approved"
        active = activate_alliance(alliance["id"], "a0000000-0000-0000-0000-000000001000")
        assert active["status"] == "active"
        with conn.cursor() as cur:
            cur.execute(
                "SELECT from_status, to_status FROM lifecycle_transition "
                "WHERE entity_type = 'coordination_alliance' AND entity_id = %s::uuid "
                "ORDER BY transitioned_at",
                (alliance["id"],),
            )
            assert cur.fetchall()[-2:] == [("draft", "approved"), ("approved", "active")]

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
    assert decision.allowed
    assert not assess_agent_action("update", "coordination_alliance", {"status": "approved"}).allowed


def test_row_helper_converts_uuid_and_datetime():
    from services.analytics.coordination import _row
    mock_uuid = uuid_mod.uuid4()
    now = datetime.now(timezone.utc)
    row = MagicMock()
    row.__iter__ = lambda s: iter({"id": mock_uuid, "created_at": now, "name": "test"}.items())
    result = _row(row)
    assert result["id"] == str(mock_uuid)
    assert result["created_at"] == now.isoformat()
    assert result["name"] == "test"


def test_row_helper_returns_none_for_none():
    from services.analytics.coordination import _row
    assert _row(None) is None
