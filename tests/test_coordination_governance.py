"""Governance and agent-safety scenarios for coordination."""

import pytest
import psycopg2

from services.agents.safety import assess_agent_action
from services.analytics.coordination import add_knowledge_exchange, approve_alliance, create_alliance
from services.analytics.coordination_strategy import (
    declare_conflict, file_appeal, preserve_minority_view, propose_remedy,
    record_benefit_harm_analysis, review_benefit_harm_analysis,
    review_conflict_declaration, terminate_alliance,
)
from services.ingestion.base import get_db


def test_approval_requires_conflict_and_benefit_harm_review():
    conn = get_db()
    alliance = create_alliance("Governance gate test", "Test approval safeguards")
    try:
        with pytest.raises(psycopg2.Error, match="conflict or no-conflict"):
            approve_alliance(alliance["id"], "a0000000-0000-0000-0000-000000001000", "Review")
        conn.rollback()
        declaration = declare_conflict(alliance["id"], "a0000000-0000-0000-0000-000000001000", "conflict", "Potential procurement conflict", recusal_required=True, recused_from="benefit allocation")
        review_conflict_declaration(declaration["id"], "a0000000-0000-0000-0000-000000001000", "managed")
        analysis = record_benefit_harm_analysis(alliance["id"], "harm", "Possible exclusion risk", severity="medium", mitigation="Accessible participation")
        review_benefit_harm_analysis(analysis["id"], "a0000000-0000-0000-0000-000000001000")
        assert approve_alliance(alliance["id"], "a0000000-0000-0000-0000-000000001000", "Conflict managed and harms reviewed")["status"] == "approved"
        assert preserve_minority_view(alliance["id"], "Prioritize water access before procurement", anonymous_group="Affected households")["preservation_status"] == "preserved"
        appeal = file_appeal(alliance["id"], "alliance", alliance["id"], "a0000000-0000-0000-0000-000000001002", "Conflict handling needs community review", correction_requested=True)
        assert appeal["correction_requested"] is True
        assert terminate_alliance(alliance["id"], "a0000000-0000-0000-0000-000000001000", "Termination test after appeal review")["status"] == "dissolved"
        remedy = propose_remedy(alliance["id"], "Publish the conflict-management explanation", "explanation")
        assert remedy["status"] == "proposed"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM coordination_alliance WHERE id = %s::uuid", (alliance["id"],))
        conn.commit()


def test_agent_can_only_draft_alliance_options():
    assert assess_agent_action("create", "coordination_alliance", {"status": "draft"}).allowed
    for action, payload in (("update", {"status": "approved"}), ("update", {"status": "active"}), ("delete", {})):
        assert not assess_agent_action(action, "coordination_alliance", payload).allowed
    for collection in (
        "coordination_conflict_declaration", "coordination_benefit_harm_analysis",
        "coordination_minority_view", "coordination_appeal", "coordination_remedy",
    ):
        assert not assess_agent_action("create", collection, {"status": "draft"}).allowed


def test_completed_exchange_requires_consent():
    conn = get_db()
    alliance = create_alliance("Consent exchange test", "Test knowledge consent")
    try:
        exchange = add_knowledge_exchange(alliance["id"], "a0000000-0000-0000-0000-000000001000", "Private method", "practice")
        with pytest.raises(psycopg2.Error, match="consent"):
            with conn.cursor() as cur:
                cur.execute("UPDATE coordination_knowledge_exchange SET status = 'completed' WHERE id = %s::uuid", (exchange["id"],))
        conn.rollback()
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM coordination_alliance WHERE id = %s::uuid", (alliance["id"],))
        conn.commit()
