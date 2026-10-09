"""Tests for strategic positions."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.analytics import strategic_positioning
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002702"


def test_position_preserves_private_value_proposition():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    plan_id = None
    position_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Position Test', 'collective') RETURNING id", (f"position-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Position Owner')", (PARTY_ID,))
            cur.execute("INSERT INTO strategy_plan (scope_type, scope_id, name, planning_horizon_start, planning_horizon_end, diagnosis_summary, guiding_policy) VALUES ('organization', %s::uuid, 'Position plan', '2026-01-01', '2026-12-31', 'Need focus', 'Differentiate') RETURNING id", (org_id,))
            plan_id = str(cur.fetchone()[0])
        conn.commit()
        position = strategic_positioning.create_position(conn, plan_id, "market_segment", "Evidence-conscious buyers", "Trustworthy impact evidence", "Verified local evidence", "Verified local evidence with ecological safeguards", created_by_party_id=PARTY_ID)
        position_id = str(position["id"])
        assert position["visibility"] == "private"
        assert strategic_positioning.list_positions(conn, plan_id)[0]["target_name"] == "Evidence-conscious buyers"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if position_id:
                cur.execute("DELETE FROM strategy_position WHERE id = %s::uuid", (position_id,))
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()


def test_clean_helper_converts_uuids():
    mock_uuid = uuid.uuid4()
    row = {"id": mock_uuid, "target_name": "Buyers"}
    cleaned = strategic_positioning._clean(row)
    assert cleaned["id"] == str(mock_uuid)


def test_approve_position_rejects_non_submitted():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with pytest.raises(ValueError, match="only submitted"):
        strategic_positioning.approve_position(mock_conn, "pos-id", "party-id")
