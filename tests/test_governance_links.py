"""Tests for bounded cross-circle representation links."""

import uuid

import pytest

from services.analytics import governance_links, governance_roles
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002481"
APPROVER_ID = "b0000000-0000-0000-0000-000000002482"


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def test_representative_link_requires_assignment_and_human_approval():
    conn = _db()
    role_id = None
    assignment_id = None
    link_id = None
    target_circle = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM governance_circle WHERE circle_key = 'adelphi-stakeholder-stewardship'")
            source_circle = str(cur.fetchone()[0])
            cur.execute("INSERT INTO governance_circle (circle_key, name, purpose, status) VALUES (%s, %s, %s, 'active') RETURNING id", (f"test-link-{uuid.uuid4().hex[:8]}", "Test Link Circle", "Test representation"))
            target_circle = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id IN (%s::uuid, %s::uuid)", (PARTY_ID, APPROVER_ID))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Representative'), (%s::uuid, 'person', 'Link Approver')", (PARTY_ID, APPROVER_ID))
        conn.commit()
        role = governance_roles.create_role(conn, source_circle, f"link-role-{uuid.uuid4().hex[:8]}", "Link Role", "Represent the source circle", status="active")
        role_id = str(role["id"])
        assignment = governance_roles.assign_role(conn, role_id, PARTY_ID)
        assignment_id = str(assignment["id"])
        governance_roles.approve_assignment(conn, assignment_id, APPROVER_ID)
        link = governance_links.create_link(
            conn, source_circle, target_circle, "representative_link", role_id, PARTY_ID,
            "Carry stakeholder tensions and operational needs to the target circle.",
            scope_type="network",
        )
        link_id = str(link["id"])
        approved = governance_links.approve_link(conn, link_id, APPROVER_ID)
        assert approved["status"] == "active"
        governance_links.end_link(conn, link_id, recused=True)
        assert governance_links.list_links(conn, party_id=PARTY_ID)[0]["status"] == "suspended"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if link_id:
                cur.execute("DELETE FROM governance_circle_link WHERE id = %s::uuid", (link_id,))
            if assignment_id:
                cur.execute("DELETE FROM governance_role_assignment WHERE id = %s::uuid", (assignment_id,))
            if role_id:
                cur.execute("DELETE FROM governance_role WHERE id = %s::uuid", (role_id,))
            if target_circle:
                cur.execute("DELETE FROM governance_circle WHERE id = %s::uuid", (target_circle,))
            cur.execute("DELETE FROM party WHERE id IN (%s::uuid, %s::uuid)", (PARTY_ID, APPROVER_ID))
        conn.commit()
