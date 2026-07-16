"""Tests for tactical sessions and explicit dispositions."""

import uuid

import pytest

from services.analytics import governance_tactical, governance_roles
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002471"


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def test_tactical_session_and_item_disposition():
    conn = _db()
    session_id = None
    item_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM governance_circle WHERE circle_key = 'adelphi-stakeholder-stewardship'")
            circle_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Tactical Owner')", (PARTY_ID,))
        conn.commit()
        session = governance_tactical.create_session(conn, circle_id, "stakeholder_health", "Adelphi stakeholder health review")
        session_id = str(session["id"])
        governance_tactical.start_session(conn, session_id)
        item = governance_tactical.add_item(
            conn, session_id, "Assign owner to overdue engagement commitment", owner_party_id=PARTY_ID, priority=1,
        )
        item_id = str(item["id"])
        governance_tactical.start_item(conn, item_id)
        disposed = governance_tactical.dispose_item(
            conn, item_id, "next_action", "Create and assign a stakeholder commitment work item.", PARTY_ID,
        )
        assert disposed["status"] == "disposed"
        completed = governance_tactical.complete_session(conn, session_id, "One next action recorded and assigned.")
        assert completed["status"] == "completed"
        health = governance_tactical.list_sessions(conn, circle_id=circle_id)[0]
        assert health["disposed_item_count"] == 1
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if session_id:
                cur.execute("DELETE FROM governance_tactical_session WHERE id = %s::uuid", (session_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
        conn.commit()
        conn.close()


def test_tactical_item_requires_owner_and_disposition():
    conn = _db()
    session_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM governance_circle WHERE circle_key = 'adelphi-stakeholder-stewardship'")
            circle_id = str(cur.fetchone()[0])
        conn.commit()
        session = governance_tactical.create_session(conn, circle_id, "risk_triage", "Risk triage")
        session_id = str(session["id"])
        item = governance_tactical.add_item(conn, session_id, "Unowned action")
        with pytest.raises(Exception):
            governance_tactical.start_item(conn, str(item["id"]))
        conn.rollback()
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if session_id:
                cur.execute("DELETE FROM governance_tactical_session WHERE id = %s::uuid", (session_id,))
        conn.commit()
        conn.close()
