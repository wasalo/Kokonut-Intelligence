"""Tests for competitive landscape evidence."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.analytics import competitive_landscape
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002701"


def test_landscape_records_actor_force_and_signal():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    plan_id = None
    landscape_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Competitive Test', 'collective') RETURNING id", (f"competitive-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'organization', 'Market Alternative')", (PARTY_ID,))
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO strategy_plan (scope_type, scope_id, name, planning_horizon_start, planning_horizon_end, diagnosis_summary, guiding_policy) VALUES ('organization', %s::uuid, 'Market plan', '2026-01-01', '2026-12-31', 'Market pressure', 'Differentiate on evidence') RETURNING id", (org_id,))
            plan_id = str(cur.fetchone()[0])
        conn.commit()
        landscape = competitive_landscape.create_landscape(conn, plan_id, "organization", org_id, "2026-01-01", "2026-12-31", industry="regenerative agriculture")
        landscape_id = str(landscape["id"])
        actor = competitive_landscape.add_actor(conn, landscape_id, PARTY_ID, "substitute", threat_level="high")
        force = competitive_landscape.record_force(conn, landscape_id, "substitutes", 75, "Alternative evidence providers are expanding", trend="worsening")
        signal = competitive_landscape.record_signal(conn, landscape_id, "competitor", "market_watch", "New verification service launched", materiality="high")
        result = competitive_landscape.get_landscape(conn, landscape_id)
        assert actor["actor_type"] == "substitute"
        assert force["pressure_score"] == 75
        assert signal["materiality"] == "high"
        assert len(result["actors"]) == len(result["forces"]) == len(result["signals"]) == 1
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if landscape_id:
                cur.execute("DELETE FROM competitive_landscape WHERE id = %s::uuid", (landscape_id,))
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()


def test_clean_helper_converts_uuids():
    mock_uuid = uuid.uuid4()
    row = {"id": mock_uuid, "name": "Landscape"}
    cleaned = competitive_landscape._clean(row)
    assert cleaned["id"] == str(mock_uuid)


def test_create_landscape_rejects_invalid_scope_type():
    with pytest.raises(ValueError, match="scope_type must be"):
        competitive_landscape.create_landscape(
            MagicMock(), "plan-id", "invalid", "scope-id", "2026-01-01", "2026-12-31"
        )
