"""Integration tests for protected grievance handling."""

from datetime import datetime, timedelta, timezone

import pytest

from services.analytics import stakeholder_grievances as grievances
from services.ingestion.base import get_db


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def test_grievance_investigation_remedy_appeal_and_closure():
    conn = _db()
    case_id = None
    try:
        case = grievances.create_case(
            conn,
            "representation",
            "Community input was not acknowledged",
            complainant_party_id="a0000000-0000-0000-0000-000000001002",
            affected_party_id="a0000000-0000-0000-0000-000000001002",
            owner_party_id="a0000000-0000-0000-0000-000000001000",
            severity="high",
            retaliation_risk=True,
            due_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        case_id = case["id"]
        acknowledged = grievances.acknowledge_case(conn, case_id)
        investigation = grievances.assign_investigation(
            conn, case_id, "a0000000-0000-0000-0000-000000001001", "Review participation records"
        )
        evidence = grievances.add_evidence(
            conn, case_id, "statement", "Community statement", investigation_id=investigation["id"],
            submitted_by_party_id="a0000000-0000-0000-0000-000000001002",
        )
        remedy = grievances.propose_remedy(
            conn, case_id, "explanation", "Publish a response and explain the decision process",
            owner_party_id="a0000000-0000-0000-0000-000000001000",
        )
        with pytest.raises(ValueError, match="open remedies"):
            grievances.close_case(conn, case_id, "Premature closure")
        completed = grievances.update_remedy(
            conn, remedy["id"], "completed", affected_party_confirmed=True,
            completion_evidence=[{"source": "test"}],
        )
        health_before_close = grievances.list_case_health(conn, overdue_only=True)
        appeal = grievances.appeal_case(conn, case_id, "Request independent review")
        decided = grievances.decide_appeal(
            conn, appeal["id"], "upheld", "a0000000-0000-0000-0000-000000001003", "Remedy was adequate"
        )
        closed = grievances.close_case(
            conn, case_id, "Remedy completed and appeal recorded",
            satisfaction_score=7.5, complainant_confirmed=True, independent_review_completed=True,
            closed_by_party_id="a0000000-0000-0000-0000-000000001000",
        )

        assert acknowledged["status"] == "acknowledged"
        assert evidence["confidentiality"] == "restricted"
        assert completed["status"] == "completed"
        assert appeal["status"] == "submitted"
        assert decided["status"] == "upheld"
        assert closed["case"]["status"] == "closed"
        assert any(row["case_id"] == case_id and row["is_overdue"] is True for row in health_before_close)
    finally:
        if case_id:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM stakeholder_grievance_case WHERE id = %s::uuid", (case_id,))
            conn.commit()
        conn.close()


def test_conflicted_investigator_is_rejected():
    conn = _db()
    case_id = None
    try:
        case = grievances.create_case(
            conn, "conduct", "Conflict test",
            complainant_party_id="a0000000-0000-0000-0000-000000001002",
            owner_party_id="a0000000-0000-0000-0000-000000001000",
        )
        case_id = case["id"]
        with pytest.raises(ValueError, match="conflict of interest"):
            grievances.assign_investigation(
                conn, case_id, "a0000000-0000-0000-0000-000000001002", "Review conflict"
            )
    finally:
        if case_id:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM stakeholder_grievance_case WHERE id = %s::uuid", (case_id,))
            conn.commit()
        conn.close()


from unittest.mock import MagicMock


def test_close_case_rejects_empty_reason():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="closure reason is required"):
        grievances.close_case(mock_conn, "case-id", "  ")


def test_appeal_rejects_empty_reason():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="appeal reason is required"):
        grievances.appeal_case(mock_conn, "case-id", "  ")


def test_decide_appeal_rejects_invalid_status():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="appeal decision"):
        grievances.decide_appeal(mock_conn, "appeal-id", "invalid", "reviewer", "Notes")


def test_update_remedy_rejects_invalid_status():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="invalid remedy status"):
        grievances.update_remedy(mock_conn, "remedy-id", "invalid_status")


def test_assign_investigation_rejects_conflict_flag():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "complainant_party_id": "p1",
        "affected_party_id": "p2",
        "owner_party_id": "p3",
    }
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with pytest.raises(ValueError, match="conflicted investigators"):
        grievances.assign_investigation(
            mock_conn, "case-id", "p4", "scope", conflict_check_status="conflict"
        )
