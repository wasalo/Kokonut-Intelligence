"""Tests for organization-to-location strategy cascades."""

import uuid

import pytest

from services.analytics import strategy_kernel
from services.ingestion.base import get_db


def test_location_plan_can_adapt_organization_plan():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    parent_id = None
    child_id = None
    location_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Cascade Test', 'collective') RETURNING id", (f"cascade-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO location (name, slug, organization_id) VALUES ('Cascade Location', %s, %s::uuid) RETURNING id", (f"cascade-location-{uuid.uuid4().hex[:8]}", org_id))
            location_id = str(cur.fetchone()[0])
        conn.commit()
        parent = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Organization strategy", "2026-01-01", "2026-12-31", diagnosis_summary="Parent diagnosis", guiding_policy="Parent policy")
        parent_id = str(parent["id"])
        child = strategy_kernel.create_strategy_plan(conn, "location", location_id, "Location adaptation", "2026-01-01", "2026-12-31", diagnosis_summary="Local diagnosis", guiding_policy="Local adaptation", parent_strategy_plan_id=parent_id, cascade_mode="adapted", cascade_rationale="Local water constraints")
        child_id = str(child["id"])
        assert child["parent_strategy_plan_id"] == parent_id
        assert child["cascade_mode"] == "adapted"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if child_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (child_id,))
            if parent_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (parent_id,))
            if org_id:
                if location_id:
                    cur.execute("DELETE FROM location WHERE id = %s::uuid", (location_id,))
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
