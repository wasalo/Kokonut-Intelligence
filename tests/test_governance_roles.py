"""Tests for the Adelphi circle and role registry."""

import pytest

from services.analytics import governance_roles
from services.ingestion.base import get_db


PILOT_CIRCLE = "a0000000-0000-0000-0000-000000002421"


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def test_circle_and_role_registry_lifecycle():
    conn = _db()
    circle_id = None
    role_id = None
    try:
        circle = governance_roles.create_circle(
            conn, "test-governance-circle", "Test Governance Circle",
            "Resolve test coordination tensions.", scope_type="location",
            scope_id="a0000000-0000-0000-0000-000000000001",
        )
        circle_id = str(circle["id"])
        role = governance_roles.create_role(
            conn, circle_id, "test-steward", "Test Steward",
            "Maintain test accountability.",
        )
        role_id = str(role["id"])
        accountability = governance_roles.add_accountability(
            conn, role_id, "Review test evidence", priority=1,
        )
        assert accountability["role_id"] == role["id"]
        assert governance_roles.list_circles(conn, scope_type="location")[0]
        roles = governance_roles.list_roles(conn, circle_id=circle_id)
        assert roles[0]["role_key"] == "test-steward"
        assert roles[0]["accountability_count"] == 1
        assert governance_roles.list_accountabilities(conn, role_id)[0]["accountability"] == "Review test evidence"
    finally:
        with conn.cursor() as cur:
            if role_id:
                cur.execute("DELETE FROM governance_role WHERE id = %s::uuid", (role_id,))
            if circle_id:
                cur.execute("DELETE FROM governance_circle WHERE id = %s::uuid", (circle_id,))
        conn.commit()
        conn.close()


def test_registry_validates_scope_and_required_fields():
    conn = _db()
    try:
        with pytest.raises(ValueError):
            governance_roles.create_circle(conn, "bad", "Bad", "Purpose", scope_type="invalid")
        with pytest.raises(ValueError):
            governance_roles.create_role(conn, PILOT_CIRCLE, "", "Role", "Purpose")
    finally:
        conn.close()


def test_adelphi_pilot_registry_is_seeded():
    conn = _db()
    try:
        circles = governance_roles.list_circles(conn, status="active")
        pilot = [row for row in circles if row["circle_key"] == "adelphi-stakeholder-stewardship"]
        assert len(pilot) == 1
        roles = governance_roles.list_roles(conn, circle_id=pilot[0]["circle_id"], status="active")
        assert {row["role_key"] for row in roles} >= {
            "stakeholder-steward", "circle-steward", "evidence-custodian",
            "consent-custodian", "grievance-owner", "ecological-proxy-steward",
            "market-relationship-owner", "governance-facilitator", "governance-recorder",
        }
    finally:
        conn.close()
