"""Integration tests for stakeholder engagement planning and commitments."""

from datetime import datetime, timedelta, timezone

import pytest

from services.analytics import stakeholder_engagement as engagement
from services.export.report_generator import generate_stakeholder_engagement
from services.ingestion.base import get_db


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def test_engagement_plan_commitment_and_outcome_lifecycle():
    conn = _db()
    plan_id = None
    try:
        plan = engagement.create_plan(
            conn,
            "Test engagement plan",
            "a0000000-0000-0000-0000-000000001002",
            owner_party_id="a0000000-0000-0000-0000-000000001000",
            scope_type="location",
            scope_id="a0000000-0000-0000-0000-000000000001",
            engagement_mode="collaborate",
        )
        plan_id = plan["id"]
        objective = engagement.add_objective(
            conn, plan_id, "Hear affected residents", "Community input is acknowledged",
            success_metric="acknowledged inputs", target_value=90, unit="percent", priority=5,
        )
        touchpoint = engagement.schedule_touchpoint(
            conn, plan_id, "Discuss water stewardship", objective_id=objective["id"],
            channel_type="sms", consent_checked=True,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        commitment = engagement.create_commitment(
            conn, plan_id, "Publish response summary", objective_id=objective["id"],
            touchpoint_id=touchpoint["id"],
            committed_by_party_id="a0000000-0000-0000-0000-000000001000",
            committed_to_party_id="a0000000-0000-0000-0000-000000001002",
            owner_party_id="a0000000-0000-0000-0000-000000001000",
            due_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        health = engagement.list_commitment_health(conn, plan_id=plan_id, overdue_only=True)
        outcome = engagement.record_outcome(
            conn, plan_id, "progress", "Response summary prepared", commitment_id=commitment["id"],
            satisfaction_score=8.5, recorded_by="a0000000-0000-0000-0000-000000001000",
        )
        updated = engagement.update_commitment(conn, commitment["id"], status="fulfilled")
        summary = engagement.list_plans(conn, stakeholder_party_id="a0000000-0000-0000-0000-000000001002")

        assert objective["priority"] == 5
        assert touchpoint["consent_checked"] is True
        assert health[0]["is_overdue"] is True
        assert outcome["outcome_type"] == "progress"
        assert updated["status"] == "fulfilled"
        assert any(
            row["plan_id"] == plan_id and row["fulfilled_commitment_count"] == 1
            for row in summary
        )
    finally:
        if plan_id:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM stakeholder_engagement_plan WHERE id = %s::uuid", (plan_id,))
            conn.commit()
        conn.close()


def test_seeded_engagement_plan_is_visible():
    conn = _db()
    try:
        plans = engagement.list_plans(conn, status="draft")
        assert any(plan["name"] == "Adelphi community engagement" for plan in plans)
        report = generate_stakeholder_engagement(
            conn, location_id="a0000000-0000-0000-0000-000000000001"
        )
        assert report["report_type"] == "stakeholder_engagement"
        assert report["plan_count"] >= 1
    finally:
        conn.close()


def test_invalid_engagement_mode_is_rejected():
    conn = _db()
    try:
        with pytest.raises(ValueError, match="engagement_mode"):
            engagement.create_plan(conn, "Invalid", "a0000000-0000-0000-0000-000000001002", engagement_mode="broadcast")
    finally:
        conn.close()


from unittest.mock import MagicMock


def test_create_plan_rejects_invalid_engagement_mode():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="engagement_mode"):
        engagement.create_plan(mock_conn, "Plan", "p1", engagement_mode="dictate")


def test_record_outcome_rejects_invalid_type():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="outcome_type"):
        engagement.record_outcome(mock_conn, "plan-id", "invalid_type", "summary")


def test_update_commitment_with_no_values_returns_existing():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"id": "c1", "status": "open"}
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    result = engagement.update_commitment(mock_conn, "c1")
    assert result["id"] == "c1"
