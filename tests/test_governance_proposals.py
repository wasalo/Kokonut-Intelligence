"""Tests for governance proposals, objections, and human gates."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from services.analytics import governance_proposals
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002461"
APPROVER_ID = "b0000000-0000-0000-0000-000000002462"
INVALID_APPROVER_ID = "b0000000-0000-0000-0000-000000002463"


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def _setup(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM party WHERE id IN (%s::uuid, %s::uuid, %s::uuid)", (PARTY_ID, APPROVER_ID, INVALID_APPROVER_ID))
        cur.execute(
            "INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Proposal Author'), (%s::uuid, 'person', 'Proposal Approver'), (%s::uuid, 'organization', 'Invalid Approver')",
            (PARTY_ID, APPROVER_ID, INVALID_APPROVER_ID),
        )
        cur.execute("SELECT id FROM governance_circle WHERE circle_key = 'adelphi-stakeholder-stewardship'")
        circle_id = str(cur.fetchone()[0])
    conn.commit()
    return circle_id


def test_proposal_objection_review_and_approval():
    conn = _db()
    proposal_id = None
    objection_id = None
    try:
        circle_id = _setup(conn)
        proposal = governance_proposals.create_proposal(
            conn, f"test-proposal-{uuid.uuid4().hex[:8]}", circle_id,
            "change_policy", "Clarify evidence duty", "Reduce evidence ambiguity.",
            "The evidence custodian must record uncertainty.",
            proposed_by_party_id=PARTY_ID, harm_review_status="required",
            minority_review_status="required",
        )
        proposal_id = str(proposal["id"])
        governance_proposals.submit_proposal(conn, proposal_id)
        governance_proposals.start_review(conn, proposal_id)
        objection = governance_proposals.add_objection(
            conn, proposal_id, "material_harm", "This could expose protected evidence.",
            objector_party_id=PARTY_ID,
        )
        objection_id = str(objection["id"])
        with pytest.raises(Exception, match="unresolved material"):
            governance_proposals.approve_proposal(conn, proposal_id, APPROVER_ID)
        conn.rollback()
        governance_proposals.respond_to_objection(
            conn, objection_id, "resolved", "Private evidence remains internal.", APPROVER_ID,
        )
        governance_proposals.record_review(conn, proposal_id, APPROVER_ID, "harm", "clear", "Privacy controls remain unchanged.")
        governance_proposals.record_review(conn, proposal_id, APPROVER_ID, "minority", "reviewed", "Minority concern recorded and answered.")
        with pytest.raises(Exception, match="human approver"):
            governance_proposals.approve_proposal(conn, proposal_id, INVALID_APPROVER_ID)
        conn.rollback()
        approved = governance_proposals.approve_proposal(conn, proposal_id, APPROVER_ID)
        assert approved["status"] == "approved"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if proposal_id:
                cur.execute("DELETE FROM governance_proposal WHERE id = %s::uuid", (proposal_id,))
            cur.execute("DELETE FROM party WHERE id IN (%s::uuid, %s::uuid, %s::uuid)", (PARTY_ID, APPROVER_ID, INVALID_APPROVER_ID))
        conn.commit()
        conn.close()


def test_proposal_requires_human_review_for_implementation():
    conn = _db()
    proposal_id = None
    try:
        circle_id = _setup(conn)
        proposal = governance_proposals.create_proposal(
            conn, f"test-proposal-{uuid.uuid4().hex[:8]}", circle_id,
            "create_role", "Create a role", "Cover a governance gap.",
            "Create a bounded role.", proposed_by_party_id=PARTY_ID,
        )
        proposal_id = str(proposal["id"])
        with pytest.raises(Exception):
            governance_proposals.approve_proposal(conn, proposal_id, INVALID_APPROVER_ID)
        conn.rollback()
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if proposal_id:
                cur.execute("DELETE FROM governance_proposal WHERE id = %s::uuid", (proposal_id,))
            cur.execute("DELETE FROM party WHERE id IN (%s::uuid, %s::uuid, %s::uuid)", (PARTY_ID, APPROVER_ID, INVALID_APPROVER_ID))
        conn.commit()
        conn.close()


def test_proposal_types_and_objection_types_constants():
    assert "change_policy" in governance_proposals.PROPOSAL_TYPES
    assert "create_role" in governance_proposals.PROPOSAL_TYPES
    assert "material_harm" in governance_proposals.OBJECTION_TYPES
    assert "consent_failure" in governance_proposals.OBJECTION_TYPES


def test_value_helper_converts_uuid_and_datetime():
    mock_uuid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    assert governance_proposals._value(mock_uuid) == str(mock_uuid)
    assert governance_proposals._value(now) == now.isoformat()
