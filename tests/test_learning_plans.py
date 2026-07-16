"""Tests for operating competency and learning plans."""

import uuid

import pytest

from services.ingestion.base import get_db
from services.management import learning_plans


PARTY_ID = "b0000000-0000-0000-0000-000000002504"


def test_competency_gap_creates_learning_plan():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Learning Test', 'collective') RETURNING id", (f"learning-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Learner')", (PARTY_ID,))
        conn.commit()
        profile = learning_plans.record_competency(conn, PARTY_ID, "facilitation", 2, target_level=4)
        assert profile["status"] == "submitted"
        plan = learning_plans.create_learning_plan(conn, PARTY_ID, "internal", org_id, "Facilitation development", competency_goals=[{"key": "facilitation", "target": 4}])
        assert plan["scope_type"] == "internal"
        assert learning_plans.list_gaps(conn, PARTY_ID)[0]["gap_level"] == 2
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM operating_learning_plan WHERE party_id = %s::uuid", (PARTY_ID,))
            cur.execute("DELETE FROM operating_competency_profile WHERE party_id = %s::uuid", (PARTY_ID,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
