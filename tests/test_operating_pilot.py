"""Tests for dual-scope operating pilot boundaries."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.ingestion.base import get_db
from services.management import operating_pilot


def test_bootstrap_registers_internal_and_adelphi_boundaries():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_ids = []
    try:
        with conn.cursor() as cur:
            for name in ("Pilot Internal", "Pilot Adelphi"):
                cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, %s, 'collective') RETURNING id", (f"pilot-{uuid.uuid4().hex[:8]}", name))
                org_ids.append(str(cur.fetchone()[0]))
        conn.commit()
        rows = operating_pilot.bootstrap(conn, org_ids[0], org_ids[1])
        assert [row["scope_type"] for row in rows] == ["adelphi", "internal"]
        assert all(row["status"] == "submitted" for row in rows)
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM operating_pilot_scope WHERE scope_id = ANY(%s::uuid[])", (org_ids,))
            cur.execute("DELETE FROM governance_role WHERE circle_id IN (SELECT id FROM governance_circle WHERE scope_id = ANY(%s::uuid[]))", (org_ids,))
            cur.execute("DELETE FROM governance_circle WHERE scope_id = ANY(%s::uuid[])", (org_ids,))
            cur.execute("DELETE FROM organization WHERE id = ANY(%s::uuid[])", (org_ids,))
        conn.commit()
        conn.close()


def test_boundaries_constant_has_both_scopes():
    assert "internal" in operating_pilot.BOUNDARIES
    assert "adelphi" in operating_pilot.BOUNDARIES
    assert "kokonut-internal-operations" == operating_pilot.BOUNDARIES["internal"]["key"]
    assert "kokonut-adelphi-field-operations" == operating_pilot.BOUNDARIES["adelphi"]["key"]


def test_clean_helper_converts_uuids():
    mock_uuid = uuid.uuid4()
    row = {"id": mock_uuid, "scope_type": "internal"}
    cleaned = operating_pilot._clean(row)
    assert cleaned["id"] == str(mock_uuid)
    assert cleaned["scope_type"] == "internal"
