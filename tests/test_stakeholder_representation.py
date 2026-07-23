"""Integration tests for representation and equity metrics."""

import pytest

from services.analytics import stakeholder_representation as representation
from services.ingestion.base import get_db


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def test_participation_accessibility_minority_and_distribution():
    conn = _db()
    activity_id = "a0000000-0000-0000-0000-000000009901"
    participation_ids = []
    distribution_id = None
    try:
        participants = [
            ("a0000000-0000-0000-0000-000000001000", "attended", 1),
            ("a0000000-0000-0000-0000-000000001001", "attended", 0),
            ("a0000000-0000-0000-0000-000000001002", "declined", 0),
            (None, "attended", 1),
            (None, "absent", 0),
        ]
        for party_id, status, contributions in participants:
            row = representation.record_participation(
                conn, "decision", activity_id, party_id=party_id,
                anonymous_group=None if party_id else f"group-{len(participation_ids)}",
                invitation_status=status, contribution_count=contributions,
                consent_checked=True,
            )
            participation_ids.append(row["id"])

        access = representation.record_accessibility_request(
            conn, participation_ids[0], "language", "Provide Haitian Creole interpretation",
            party_id="a0000000-0000-0000-0000-000000001000",
        )
        minority = representation.record_minority_view(
            conn, "decision", activity_id, "Prioritize water access before expansion",
            anonymous_group="water-dependent households", concern_or_risk="Drought exposure",
        )
        distribution = representation.record_distribution(
            conn, "location", "benefit", "training_hours", 12, "hours",
            scope_id="a0000000-0000-0000-0000-000000000001",
            beneficiary_party_id="a0000000-0000-0000-0000-000000001002",
            stakeholder_type="community", status="verified",
        )
        distribution_id = distribution["id"]
        metrics = representation.representation_metrics(conn, "decision", activity_id)
        public_rows = []
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM v_public_stakeholder_representation WHERE activity_id = %s::uuid", (activity_id,))
            public_rows = cur.fetchall()
        summary = representation.list_distribution_summary(
            conn, scope_type="location", scope_id="a0000000-0000-0000-0000-000000000001"
        )

        assert access["need_type"] == "language"
        assert minority["preserved"] is True
        assert metrics["invited_count"] == 5
        assert metrics["participated_count"] == 3
        assert float(metrics["participation_rate_pct"]) == 60.0
        assert len(public_rows) == 1
        assert summary[0]["beneficiary_count"] == 1
        assert float(summary[0]["total_amount"]) == 12.0
    finally:
        with conn.cursor() as cur:
            if participation_ids:
                cur.execute("DELETE FROM stakeholder_participation WHERE id = ANY(%s::uuid[])", (participation_ids,))
            if distribution_id:
                cur.execute("DELETE FROM stakeholder_distribution WHERE id = %s::uuid", (distribution_id,))
        conn.commit()
        conn.close()


def test_small_activity_is_suppressed_from_public_representation():
    conn = _db()
    activity_id = "a0000000-0000-0000-0000-000000009902"
    participation_id = None
    try:
        row = representation.record_participation(
            conn, "feedback", activity_id,
            anonymous_group="single small group", invitation_status="attended",
        )
        participation_id = row["id"]
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM v_public_stakeholder_representation WHERE activity_id = %s::uuid", (activity_id,))
            assert cur.fetchone() is None
    finally:
        if participation_id:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM stakeholder_participation WHERE id = %s::uuid", (participation_id,))
            conn.commit()
        conn.close()


from unittest.mock import MagicMock


def test_record_participation_rejects_invalid_activity_type():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="activity_type"):
        representation.record_participation(mock_conn, "invalid_type", "act-id")


def test_record_participation_requires_party_or_anonymous():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="party_id or anonymous_group"):
        representation.record_participation(mock_conn, "decision", "act-id")


def test_record_accessibility_request_rejects_invalid_need_type():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="need_type"):
        representation.record_accessibility_request(mock_conn, "part-id", "invalid", "Support")


def test_record_distribution_rejects_invalid_type():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="distribution_type"):
        representation.record_distribution(mock_conn, "location", "invalid", "metric", 10.0, "hours")
