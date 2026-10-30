"""Tests for bounded cross-circle representation links."""

import sys
import uuid
from datetime import datetime, timezone

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


def test_link_types_constant():
    assert "representative_link" in governance_links.LINK_TYPES
    assert "lead_link" in governance_links.LINK_TYPES
    assert "liaison" in governance_links.LINK_TYPES
    assert "observer" in governance_links.LINK_TYPES


def test_value_helper_converts_uuid_and_datetime():
    mock_uuid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    assert governance_links._value(mock_uuid) == str(mock_uuid)
    assert governance_links._value(now) == now.isoformat()


@pytest.mark.parametrize("value", ["not-a-timestamp", "2026-10-30T12:00:00"])
def test_governance_link_term_end_fails_before_database_access(monkeypatch, value):
    from services.analytics import cli_governance_links

    monkeypatch.setattr(
        cli_governance_links,
        "_connection",
        lambda: pytest.fail("invalid timestamp opened a database connection"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "governance-links", "create", "source", "target", "observer",
            "role", PARTY_ID, "A bounded representation mandate.",
            "--term-end", value,
        ],
    )

    with pytest.raises(SystemExit) as exc:
        cli_governance_links.main()
    assert exc.value.code == 2


def test_governance_link_term_end_passes_aware_timestamp_to_service(monkeypatch):
    from services.analytics import cli_governance_links

    expected = datetime(2027, 1, 1, 12, 0, tzinfo=timezone.utc)
    connection = object()
    calls = []
    monkeypatch.setattr(cli_governance_links, "_connection", lambda: connection)
    monkeypatch.setattr(
        cli_governance_links,
        "create_link",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {"id": "link"},
    )
    monkeypatch.setattr(cli_governance_links, "_out", lambda _value: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "governance-links", "create", "source", "target", "observer",
            "role", PARTY_ID, "A bounded representation mandate.",
            "--term-end", "2027-01-01T12:00:00Z",
        ],
    )

    cli_governance_links.main()

    assert calls[0][0][0] is connection
    assert calls[0][1]["term_end"] == expected
