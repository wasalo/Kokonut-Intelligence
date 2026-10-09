"""Tests for dual-scope capacity and demand signals."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from services.ingestion.base import get_db
from services.management import capacity_signals


PARTY_ID = "b0000000-0000-0000-0000-000000002503"


def test_capacity_gap_is_visible_after_approval():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Capacity Test', 'collective') RETURNING id", (f"capacity-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Capacity Owner')", (PARTY_ID,))
        conn.commit()
        profile = capacity_signals.record_capacity(conn, "internal", org_id, PARTY_ID, "2026-07-01", "2026-07-31", 20, committed_hours=4, protected_hours=2)
        signal = capacity_signals.record_demand(conn, "internal", org_id, "evidence_review", "2026-07-01", "2026-07-31", 18, priority="high")
        capacity_signals.approve_capacity(conn, str(profile["id"]))
        capacity_signals.approve_demand(conn, str(signal["id"]))
        gaps = capacity_signals.list_gaps(conn, scope_type="internal", scope_id=org_id)
        assert gaps[0]["net_hours"] == -4
        assert gaps[0]["coverage_status"] == "gap"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM operating_demand_signal WHERE scope_id = %s::uuid", (org_id,))
            cur.execute("DELETE FROM operating_capacity_profile WHERE scope_id = %s::uuid", (org_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()


def test_capacity_cannot_overcommit():
    with pytest.raises(ValueError, match="cannot exceed"):
        capacity_signals.record_capacity(None, "adelphi", str(uuid.uuid4()), PARTY_ID, "2026-07-01", "2026-07-31", 2, committed_hours=2, protected_hours=1)


def test_scopes_constant():
    assert capacity_signals.SCOPES == ("internal", "adelphi")


def test_record_demand_rejects_negative_hours():
    with pytest.raises(ValueError, match="negative"):
        capacity_signals.record_demand(
            None, "internal", str(uuid.uuid4()), "test", "2026-07-01", "2026-07-31", -5
        )
