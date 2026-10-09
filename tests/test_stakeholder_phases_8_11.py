"""Integration coverage for stakeholder phases 8 through 11."""

import pytest

from services.analytics import stakeholder_trust as trust
from services.export.report_generator import REPORT_GENERATORS
from services.ingestion.base import get_db


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def test_trust_profile_is_explainable_and_contestable():
    conn = _db()
    party_id = "b0000000-0000-0000-0000-000000008001"
    evidence_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (party_id,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'organization', 'Trust Test Buyer')", (party_id,))
        conn.commit()
        evidence = trust.record_evidence(
            conn, party_id, "payment", "supporting", "financial_transaction",
            "Payment settled within agreed terms", confidence=0.9, uncertainty=0.1,
        )
        evidence_id = evidence["id"]
        profile = trust.profile(conn, party_id)
        assert profile["evidence_count"] == 1
        assert profile["supporting_evidence_count"] == 1
        assert "No universal reputation score" in profile["interpretation"]
        timeline = trust.evidence_timeline(conn, party_id)
        assert timeline[0]["dimension"] == "payment"
    finally:
        with conn.cursor() as cur:
            if evidence_id:
                cur.execute("DELETE FROM party_trust_evidence WHERE id = %s::uuid", (evidence_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (party_id,))
        conn.commit()
        conn.close()


def test_phase_8_to_11_views_and_reports_exist():
    conn = _db()
    try:
        with conn.cursor() as cur:
            for view in (
                "v_cooperative_governance_health",
                "v_party_trust_profile",
                "v_stakeholder_capability_value_stream",
                "v_nature_stewardship_status",
                "v_public_ecological_stewardship",
                "v_stakeholder_cockpit_internal",
                "v_public_stakeholder_cockpit",
            ):
                cur.execute(f"SELECT * FROM {view} LIMIT 1")
        assert {
            "stakeholder_ecosystem",
            "stakeholder_outcomes",
            "stakeholder_trust",
            "stakeholder_value_streams",
            "stakeholder_cockpit",
        }.issubset(REPORT_GENERATORS)
    finally:
        conn.close()


from unittest.mock import MagicMock


def test_trust_profile_returns_none_for_missing_party():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    result = trust.profile(mock_conn, "nonexistent-party-id")
    assert result is None


def test_trust_record_evidence_with_valid_data():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "id": "e1", "subject_party_id": "p1", "dimension": "payment",
        "direction": "supporting", "source_type": "financial_transaction",
    }
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    result = trust.record_evidence(
        mock_conn, "p1", "payment", "supporting", "financial_transaction",
        "Payment settled", confidence=0.9, uncertainty=0.1,
    )
    assert result["dimension"] == "payment"
    assert result["direction"] == "supporting"
