"""Tests for instrumented work opportunities and self-selection."""

import uuid

import pytest

from services.ingestion.base import get_db
from services.management import work_selection


PARTY_ID = "b0000000-0000-0000-0000-000000002501"
REVIEWER_ID = "b0000000-0000-0000-0000-000000002502"


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")


def test_work_opportunity_claim_and_review():
    conn = _db()
    org_id = None
    item_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Work Selection Test', 'collective') RETURNING id", (f"work-selection-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id IN (%s::uuid, %s::uuid)", (PARTY_ID, REVIEWER_ID))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Claimant'), (%s::uuid, 'person', 'Reviewer')", (PARTY_ID, REVIEWER_ID))
        conn.commit()
        item = work_selection.create_opportunity(
            conn, org_id, "Review stakeholder evidence", "system",
            work_type="evidence_review", selection_mode="self_selected",
            estimated_effort_hours=4, skill_requirements=[{"key": "evidence_review", "level": 2}],
        )
        item_id = str(item["id"])
        claim = work_selection.claim_work(conn, item_id, PARTY_ID, proposed_effort_hours=3)
        assert claim["status"] == "proposed"
        reviewed = work_selection.review_claim(conn, str(claim["id"]), REVIEWER_ID, "accepted", reason="Capability evidence reviewed")
        assert reviewed["status"] == "accepted"
        assert work_selection.list_opportunities(conn, organization_id=org_id) == []
        with conn.cursor() as cur:
            cur.execute("SELECT allocation_status FROM work_item WHERE id = %s::uuid", (item_id,))
            assert cur.fetchone()[0] == "allocated"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if item_id:
                cur.execute("DELETE FROM work_item WHERE id = %s::uuid", (item_id,))
            cur.execute("DELETE FROM party WHERE id IN (%s::uuid, %s::uuid)", (PARTY_ID, REVIEWER_ID))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()


def test_assigned_work_cannot_be_claimed():
    conn = _db()
    org_id = None
    item_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Assigned Work Test', 'collective') RETURNING id", (f"assigned-work-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
        conn.commit()
        item = work_selection.create_opportunity(conn, org_id, "Assigned work", "system", selection_mode="assigned")
        item_id = str(item["id"])
        with pytest.raises(ValueError, match="assigned work"):
            work_selection.claim_work(conn, item_id, PARTY_ID)
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if item_id:
                cur.execute("DELETE FROM work_item WHERE id = %s::uuid", (item_id,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
