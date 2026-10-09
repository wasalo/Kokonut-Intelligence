"""Tests for VRIO-style advantage assessment."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from services.analytics import advantage_assessment
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002703"


def test_advantage_assessment_computes_defensibility():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    plan_id = None
    advantage_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Advantage Test', 'collective') RETURNING id", (f"advantage-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Advantage Assessor')", (PARTY_ID,))
            cur.execute("INSERT INTO strategy_plan (scope_type, scope_id, name, planning_horizon_start, planning_horizon_end, diagnosis_summary, guiding_policy) VALUES ('organization', %s::uuid, 'Advantage plan', '2026-01-01', '2026-12-31', 'Need advantage', 'Build trust') RETURNING id", (org_id,))
            plan_id = str(cur.fetchone()[0])
        conn.commit()
        advantage = advantage_assessment.create_advantage(conn, plan_id, "Verified evidence network", "Trusted local evidence is hard to replicate", evidence=[{"source":"independent_assessment","confidence":"high"}], valuable_score=90, rare_score=80, inimitable_score=75, organized_score=85, switching_cost_score=80, network_effect_score=70, evidence_advantage_score=95, ecological_score=85, social_score=80, governance_trust_score=90, owner_party_id=PARTY_ID)
        advantage_id = str(advantage["id"])
        assessed = advantage_assessment.assess_advantage(conn, advantage_id, PARTY_ID, imitation_risk="low", capture_risk="medium")
        assert assessed["status"] == "verified"
        assert assessed["defensibility_score"] > 80
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if advantage_id:
                cur.execute("DELETE FROM strategy_advantage WHERE id = %s::uuid", (advantage_id,))
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()


def test_clean_helper_converts_uuids_to_strings():
    mock_uuid = uuid.uuid4()
    row = {"id": mock_uuid, "name": "Test", "score": 85}
    cleaned = advantage_assessment._clean(row)
    assert cleaned["id"] == str(mock_uuid)
    assert cleaned["name"] == "Test"
    assert cleaned["score"] == 85


def test_score_fields_constant():
    assert "valuable_score" in advantage_assessment.SCORE_FIELDS
    assert "rare_score" in advantage_assessment.SCORE_FIELDS
    assert "inimitable_score" in advantage_assessment.SCORE_FIELDS
    assert "organized_score" in advantage_assessment.SCORE_FIELDS
    assert len(advantage_assessment.SCORE_FIELDS) == 10


def test_link_advantage_rejects_invalid_entity_type():
    with pytest.raises(ValueError, match="invalid advantage link entity type"):
        advantage_assessment.link_advantage(
            MagicMock(), "adv-id", "invalid_type", "entity-id", "required"
        )


def test_link_advantage_rejects_invalid_relationship():
    with pytest.raises(ValueError, match="invalid advantage link relationship"):
        advantage_assessment.link_advantage(
            MagicMock(), "adv-id", "capability", "entity-id", "invalid_rel"
        )


def test_assess_advantage_rejects_missing_advantage():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with pytest.raises(ValueError, match="advantage not found"):
        advantage_assessment.assess_advantage(mock_conn, "missing-id", "party-id")
