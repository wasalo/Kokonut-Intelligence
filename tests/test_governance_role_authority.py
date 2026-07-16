"""Tests for role assignments, domains, and authority controls."""

import uuid

import pytest

from services.analytics import governance_roles
from services.ingestion.base import get_db


PILOT_LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
PARTY_ID = "b0000000-0000-0000-0000-000000002431"
APPROVER_ID = "b0000000-0000-0000-0000-000000002432"
INVALID_APPROVER_ID = "b0000000-0000-0000-0000-000000002433"


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def _parties(conn):
    conn.rollback()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM governance_role_assignment WHERE party_id IN (%s::uuid, %s::uuid, %s::uuid)", (PARTY_ID, APPROVER_ID, INVALID_APPROVER_ID))
        cur.execute("DELETE FROM party WHERE id IN (%s::uuid, %s::uuid, %s::uuid)", (PARTY_ID, APPROVER_ID, INVALID_APPROVER_ID))
        cur.execute(
            "INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Role Holder'), (%s::uuid, 'person', 'Role Approver'), (%s::uuid, 'organization', 'Invalid Approver')",
            (PARTY_ID, APPROVER_ID, INVALID_APPROVER_ID),
        )
    conn.commit()


def _pilot_circle_id(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM governance_circle WHERE circle_key = 'adelphi-stakeholder-stewardship'"
        )
        return str(cur.fetchone()[0])


def test_assignment_requires_human_approval_and_domain_authority():
    conn = _db()
    role_id = None
    assignment_id = None
    try:
        _parties(conn)
        circle_id = _pilot_circle_id(conn)
        role_key = f"authority-test-{uuid.uuid4().hex[:8]}"
        role = governance_roles.create_role(
            conn, circle_id, role_key, "Authority Test", "Test authority", status="active",
        )
        role_id = str(role["id"])
        governance_roles.add_domain(
            conn, role_id, "work_item", "stakeholder_triage",
            scope_type="location", scope_id=PILOT_LOCATION_ID, authority_level="execute",
        )
        assignment = governance_roles.assign_role(conn, role_id, PARTY_ID)
        assignment_id = str(assignment["id"])
        with pytest.raises(Exception, match="human approver"):
            governance_roles.approve_assignment(conn, assignment_id, INVALID_APPROVER_ID)
        conn.rollback()
        governance_roles.approve_assignment(conn, assignment_id, APPROVER_ID)
        assert governance_roles.role_can_act(
            conn, PARTY_ID, "work_item", "stakeholder_triage",
            scope_type="location", scope_id=PILOT_LOCATION_ID, required_level="execute",
        )
        governance_roles.end_assignment(conn, assignment_id, recused=True)
        assert not governance_roles.role_can_act(
            conn, PARTY_ID, "work_item", "stakeholder_triage",
            scope_type="location", scope_id=PILOT_LOCATION_ID, required_level="observe",
        )
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if assignment_id:
                cur.execute("DELETE FROM governance_role_assignment WHERE id = %s::uuid", (assignment_id,))
            cur.execute("DELETE FROM governance_role_assignment WHERE party_id IN (%s::uuid, %s::uuid, %s::uuid)", (PARTY_ID, APPROVER_ID, INVALID_APPROVER_ID))
            if role_id:
                cur.execute("DELETE FROM governance_role WHERE id = %s::uuid", (role_id,))
            cur.execute("DELETE FROM party WHERE id IN (%s::uuid, %s::uuid, %s::uuid)", (PARTY_ID, APPROVER_ID, INVALID_APPROVER_ID))
        conn.commit()
        conn.close()


def test_delegate_requires_mandate_and_primary_is_unique():
    conn = _db()
    role_id = None
    try:
        _parties(conn)
        role = governance_roles.create_role(
            conn, _pilot_circle_id(conn), f"assignment-test-{uuid.uuid4().hex[:8]}",
            "Assignment Test", "Test assignment", status="active",
        )
        role_id = str(role["id"])
        with pytest.raises(ValueError):
            governance_roles.assign_role(conn, role_id, PARTY_ID, assignment_type="delegate")
        first = governance_roles.assign_role(conn, role_id, PARTY_ID)
        first_id = str(first["id"])
        governance_roles.approve_assignment(conn, first_id, APPROVER_ID)
        second = governance_roles.assign_role(conn, role_id, APPROVER_ID)
        second_id = str(second["id"])
        with pytest.raises(Exception):
            governance_roles.approve_assignment(conn, second_id, APPROVER_ID)
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM governance_role_assignment WHERE id IN (%s::uuid, %s::uuid)", (first_id, second_id))
        conn.commit()
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM governance_role_assignment WHERE party_id IN (%s::uuid, %s::uuid, %s::uuid)", (PARTY_ID, APPROVER_ID, INVALID_APPROVER_ID))
            if role_id:
                cur.execute("DELETE FROM governance_role WHERE id = %s::uuid", (role_id,))
            cur.execute("DELETE FROM party WHERE id IN (%s::uuid, %s::uuid, %s::uuid)", (PARTY_ID, APPROVER_ID, INVALID_APPROVER_ID))
        conn.commit()
        conn.close()
