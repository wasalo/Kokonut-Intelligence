"""Tests for advantage-to-operating-model links."""

import uuid

import pytest

from services.analytics import advantage_assessment
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002704"


def test_advantage_links_to_capability_and_fit_dashboard():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    plan_id = None
    advantage_id = None
    capability_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Fit Test', 'collective') RETURNING id", (f"fit-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Fit Owner')", (PARTY_ID,))
            cur.execute("INSERT INTO strategy_plan (scope_type, scope_id, name, planning_horizon_start, planning_horizon_end, diagnosis_summary, guiding_policy) VALUES ('organization', %s::uuid, 'Fit plan', '2026-01-01', '2026-12-31', 'Need fit', 'Build fit') RETURNING id", (org_id,))
            plan_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO business_capability (name, capability_type) VALUES ('Evidence capability', 'core') RETURNING id")
            capability_id = str(cur.fetchone()[0])
        conn.commit()
        advantage = advantage_assessment.create_advantage(conn, plan_id, "Evidence advantage", "Trusted evidence", owner_party_id=PARTY_ID)
        advantage_id = str(advantage["id"])
        link = advantage_assessment.link_advantage(conn, advantage_id, "capability", capability_id, "required")
        assert link["relationship"] == "required"
        assert advantage_assessment.fit_dashboard(conn, plan_id)[0]["fit_status"] == "partial"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if advantage_id:
                cur.execute("DELETE FROM strategy_advantage WHERE id = %s::uuid", (advantage_id,))
            if capability_id:
                cur.execute("DELETE FROM business_capability WHERE id = %s::uuid", (capability_id,))
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
