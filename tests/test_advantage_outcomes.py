"""Integration coverage for realized advantage outcomes and renewal."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.analytics import advantage_assessment, advantage_outcomes, strategy_kernel
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002707"


def test_advantage_performance_tracks_outcome_and_erosion():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = plan_id = advantage_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Advantage Outcome Test', 'collective') RETURNING id", (f"adv-outcome-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Outcome Assessor')", (PARTY_ID,))
        conn.commit()
        plan = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Advantage outcome plan", "2026-01-01", "2026-12-31")
        plan_id = str(plan["id"])
        advantage = advantage_assessment.create_advantage(conn, plan_id, "Trusted evidence", "Verified evidence improves buyer confidence", evidence=[{"source":"buyer-study"}], owner_party_id=PARTY_ID, valuable_score=80, rare_score=70, inimitable_score=75, organized_score=85)
        advantage_id = str(advantage["id"])
        advantage_assessment.assess_advantage(conn, advantage_id, PARTY_ID)
        advantage_outcomes.record_outcome(conn, advantage_id, "price_premium", "2026-01-01", "2026-03-31", baseline_value=100, actual_value=115, comparator_type="baseline", comparator_value=100, unit="USD", status="verified", evidence=[{"source":"sales-ledger"}], observed_by_party_id=PARTY_ID)
        advantage_outcomes.record_renewal_event(conn, advantage_id, "reinforce", "2026-02-01", "Expanded evidence verification", status="completed", created_by_party_id=PARTY_ID)
        advantage_outcomes.record_renewal_event(conn, advantage_id, "erode", "2026-03-01", "Competitor copied public reporting", status="approved", created_by_party_id=PARTY_ID)
        result = advantage_outcomes.performance(conn, plan_id)[0]
        assert float(result["outcome_delta"]) == 15
        assert result["renewal_event_count"] == 1
        assert result["erosion_event_count"] == 1
        assert result["completed_reinforcement_count"] == 1
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()


def test_clean_helper_converts_uuid_and_datetime():
    from datetime import datetime, timezone
    mock_uuid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    row = {"id": mock_uuid, "event_date": now, "outcome_type": "price_premium"}
    cleaned = advantage_outcomes._clean(row)
    assert cleaned["id"] == str(mock_uuid)
    assert cleaned["event_date"] == now
    assert cleaned["outcome_type"] == "price_premium"


def test_performance_returns_list_shape():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    result = advantage_outcomes.performance(mock_conn, "plan-id")
    assert isinstance(result, list)
    assert result == []
