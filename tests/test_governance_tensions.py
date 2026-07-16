"""Tests for tension intake, ownership, linkage, and resolution."""

import uuid

import pytest

from services.analytics import governance_tensions, governance_roles
from services.ingestion.base import get_db


PILOT_LOCATION_ID = "a0000000-0000-0000-0000-000000000001"


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def _circle(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM governance_circle WHERE circle_key = 'adelphi-stakeholder-stewardship'")
        return str(cur.fetchone()[0])


def test_tension_lifecycle_and_work_item_link():
    conn = _db()
    tension_id = None
    role_id = None
    try:
        role = governance_roles.create_role(
            conn, _circle(conn), f"tension-owner-{uuid.uuid4().hex[:8]}",
            "Tension Owner", "Own tension triage", status="active",
        )
        role_id = str(role["id"])
        tension = governance_tensions.report_tension(
            conn, f"test-tension-{uuid.uuid4().hex[:8]}",
            "Unclear stakeholder ownership", "The pilot commitment has no clear owner.",
            "unclear_accountability", circle_id=_circle(conn),
            scope_type="location", scope_id=PILOT_LOCATION_ID, severity=4, urgency=5,
        )
        tension_id = str(tension["id"])
        governance_tensions.submit_tension(conn, tension_id)
        governance_tensions.triage_tension(conn, tension_id, owner_role_id=role_id)
        governance_tensions.start_tension(conn, tension_id)
        link = governance_tensions.link_record(conn, tension_id, "evidence", "metric_value", str(uuid.uuid4()), summary="Test evidence")
        assert link["tension_id"] == tension["id"]
        resolved = governance_tensions.resolve_tension(conn, tension_id, "Assigned to the stewardship role.")
        assert resolved["status"] == "resolved"
        result = governance_tensions.get_tension(conn, tension_id)
        assert result["link_count"] == 1
        assert result["owner_role_id"] == role["id"]
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if tension_id:
                cur.execute("DELETE FROM governance_tension WHERE id = %s::uuid", (tension_id,))
            if role_id:
                cur.execute("DELETE FROM governance_role WHERE id = %s::uuid", (role_id,))
        conn.commit()
        conn.close()


def test_tension_requires_owner_before_triage_and_resolution_summary():
    conn = _db()
    tension_id = None
    try:
        tension = governance_tensions.report_tension(
            conn, f"test-tension-{uuid.uuid4().hex[:8]}", "Test tension",
            "A test gap requires triage.", "evidence_gap",
        )
        tension_id = str(tension["id"])
        governance_tensions.submit_tension(conn, tension_id)
        with pytest.raises(ValueError):
            governance_tensions.triage_tension(conn, tension_id)
        with pytest.raises(ValueError):
            governance_tensions.resolve_tension(conn, tension_id, "")
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if tension_id:
                cur.execute("DELETE FROM governance_tension WHERE id = %s::uuid", (tension_id,))
        conn.commit()
        conn.close()
