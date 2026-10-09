"""Integration coverage for strategy consultation and communication governance."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.analytics import strategy_consultation, strategy_kernel
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002606"


def test_submit_response_rejects_missing_consent():
    with pytest.raises(ValueError, match="consent"):
        strategy_consultation.submit_response(None, str(uuid.uuid4()), "response", consent_checked=False)


def test_publish_communication_rejects_non_draft():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with pytest.raises(ValueError, match="only draft"):
        strategy_consultation.publish_communication(mock_conn, str(uuid.uuid4()), str(uuid.uuid4()))


def test_open_consultation_rejects_non_draft():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with pytest.raises(ValueError, match="only draft"):
        strategy_consultation.open_consultation(mock_conn, str(uuid.uuid4()))


def test_consultation_requires_consent_and_communication_approval():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = plan_id = consultation_id = communication_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Consultation Test', 'collective') RETURNING id", (f"consultation-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Consultation Reviewer')", (PARTY_ID,))
        conn.commit()
        plan = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Consultation plan", "2026-01-01", "2026-12-31", PARTY_ID)
        plan_id = str(plan["id"])
        consultation = strategy_consultation.create_consultation(conn, plan_id, "Farmer priorities", "What should the next plan protect?", "farmer", created_by_party_id=PARTY_ID)
        consultation_id = str(consultation["id"])
        strategy_consultation.open_consultation(conn, consultation_id)
        with pytest.raises(ValueError, match="consent"):
            strategy_consultation.submit_response(conn, consultation_id, "Protect water access")
        strategy_consultation.submit_response(conn, consultation_id, "Protect water access", respondent_party_id=PARTY_ID, consent_checked=True)
        summary = strategy_consultation.synthesize_consultation(conn, consultation_id)
        assert summary["synthesis"]["response_count"] == 1
        communication = strategy_consultation.create_communication(conn, plan_id, "The consultation is open.", "farmer", "sms", created_by_party_id=PARTY_ID)
        communication_id = str(communication["id"])
        published = strategy_consultation.publish_communication(conn, communication_id, PARTY_ID)
        assert published["status"] == "published"
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
