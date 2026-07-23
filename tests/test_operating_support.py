"""Tests for private coaching and resource decisions."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.ingestion.base import get_db
from services.management import operating_support


PARTY_ID = "b0000000-0000-0000-0000-000000002505"


def test_resource_request_and_private_coaching():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Support Test', 'collective') RETURNING id", (f"support-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Support Recipient')", (PARTY_ID,))
        conn.commit()
        session = operating_support.record_coaching_session(conn, "adelphi", org_id, PARTY_ID, "field data access", privacy_level="private")
        assert session["privacy_level"] == "private"
        request = operating_support.request_resource(conn, "adelphi", org_id, PARTY_ID, "connectivity", "Reliable field connectivity for reporting", urgency="high")
        decision = operating_support.decide_resource(conn, str(request["id"]), PARTY_ID, "approved", reason="Pilot infrastructure budget")
        assert decision["decision"] == "approved"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM operating_coaching_session WHERE scope_id = %s::uuid", (org_id,))
            cur.execute("DELETE FROM operating_resource_request WHERE scope_id = %s::uuid", (org_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()


def test_clean_helper_converts_uuids():
    mock_uuid = uuid.uuid4()
    row = {"id": mock_uuid, "privacy_level": "private"}
    cleaned = operating_support._clean(row)
    assert cleaned["id"] == str(mock_uuid)


def test_record_coaching_rejects_invalid_privacy_level():
    with pytest.raises(ValueError, match="invalid privacy_level"):
        operating_support.record_coaching_session(
            MagicMock(), "internal", "scope-id", "party-id", "focus",
            privacy_level="public"
        )
